from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, ImageFilter, ImageStat
import numpy as np

class VisionUtils:
    @staticmethod
    def is_valid_image(image_path: str) -> bool:
        try:
            with Image.open(image_path) as img:
                img.verify()
            return True
        except Exception:
            return False

    @staticmethod
    def apply_lee_speckle_filter(image_array: np.ndarray, window_size: int = 5) -> np.ndarray:
        pad = window_size // 2
        padded = np.pad(image_array, pad, mode='reflect')
        h, w = image_array.shape
        filtered = np.zeros_like(image_array, dtype=np.float32)
        overall_var = np.var(image_array)
        for i in range(h):
            for j in range(w):
                win = padded[i:i + window_size, j:j + window_size]
                m = np.mean(win)
                v = np.var(win)
                weight = v / (v + overall_var + 1e-6)
                filtered[i, j] = m + weight * (image_array[i, j] - m)
        return np.clip(filtered, 0, 255).astype(np.uint8)

    @staticmethod
    def compute_sar_log_ratio(arr1: np.ndarray, arr2: np.ndarray) -> float:
        eps = 1.0
        ratio = np.abs(np.log((arr2.astype(float) + eps) / (arr1.astype(float) + eps)))
        return float(np.mean(ratio))

    @staticmethod
    def classify_xview2_damage(pre_diff: float) -> dict:
        if pre_diff < 15.0:
            return {"tier": "No Damage", "score": 0}
        if pre_diff < 30.0:
            return {"tier": "Minor Damage", "score": 1}
        if pre_diff < 48.0:
            return {"tier": "Major Damage", "score": 2}
        return {"tier": "Destroyed", "score": 3}

    @staticmethod
    def get_mock_landcover() -> dict:
        # Kept for backwards-compatible unit tests only. Production inference never
        # calls this for a readable image and never exposes these values as evidence.
        return {"status": "unavailable", "classes": [], "detected_objects": [], "summary_text": "No measured land-cover result is available."}

    @staticmethod
    def calculate_landcover_and_objects(image_source, gsd_m: float = 10.0, roi_geometry: Optional[dict] = None) -> dict:
        """Compute conservative image-derived surface classes and feature statistics."""
        try:
            if isinstance(image_source, str):
                if not Path(image_source).exists():
                    return {"status": "unavailable", "classes": [], "detected_objects": [], "summary_text": "Image source not found."}
                raw_img = Image.open(image_source)
            elif isinstance(image_source, Image.Image):
                raw_img = image_source
            elif isinstance(image_source, np.ndarray):
                raw_img = Image.fromarray(image_source)
            else:
                return {"status": "unavailable", "classes": [], "detected_objects": [], "summary_text": "Unsupported image source."}

            if roi_geometry:
                w, h = raw_img.size
                rx = float(roi_geometry.get("x", 0))
                ry = float(roi_geometry.get("y", 0))
                rw = float(roi_geometry.get("width", roi_geometry.get("w", w)))
                rh = float(roi_geometry.get("height", roi_geometry.get("h", h)))
                if rw <= 1 and rh <= 1:
                    box = (int(rx * w), int(ry * h), int((rx + rw) * w), int((ry + rh) * h))
                elif rw <= 100 and rh <= 100:
                    box = (int(rx / 100 * w), int(ry / 100 * h), int((rx + rw) / 100 * w), int((ry + rh) / 100 * h))
                else:
                    box = (int(rx), int(ry), int(rx + rw), int(ry + rh))
                box = (max(0, box[0]), max(0, box[1]), min(w, max(1, box[2])), min(h, max(1, box[3])))
                if box[2] > box[0] and box[3] > box[1]:
                    raw_img = raw_img.crop(box)

            img = raw_img.convert("RGB")
            arr = np.asarray(img, dtype=np.float32)
            h, w = arr.shape[:2]
            total_px = max(1, w * h)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            brightness = (r + g + b) / 3.0

            dy = np.abs(arr[1:, :, :] - arr[:-1, :, :]).mean(axis=2) if h > 1 else np.zeros((1, w))
            dx = np.abs(arr[:, 1:, :] - arr[:, :-1, :]).mean(axis=2) if w > 1 else np.zeros((h, 1))
            grad = np.zeros((h, w), dtype=np.float32)
            if h > 1 and w > 1:
                grad[:-1, :-1] = (dy[:, :-1] + dx[:-1, :]) / 2.0

            cloud_mask = (r > 195) & (g > 195) & (b > 195) & (np.abs(r - g) < 20) & (np.abs(g - b) < 20) & (grad < 25)
            water_mask = (~cloud_mask) & (((b > r + 5) & (b > g - 5) & (r < 115)) | ((brightness < 75)))
            ngrdi = (g - r) / (g + r + 1e-6)
            veg_mask = (~cloud_mask) & (~water_mask) & ((ngrdi > 0.035) | ((g > r * 1.08) & (g > b * 1.02)))
            urban_mask = (~cloud_mask) & (~water_mask) & (~veg_mask) & ((grad > 18) | ((brightness > 130) & (np.abs(r - g) < 25) & (np.abs(g - b) < 25)))
            soil_mask = (~cloud_mask) & (~water_mask) & (~veg_mask) & (~urban_mask)

            masks = [("vegetation", "Vegetation & Canopy", veg_mask), ("water", "Water Bodies & Hydrology", water_mask), ("urban", "Built-up & Infrastructure", urban_mask), ("soil", "Bare Soil & Terrain", soil_mask), ("clouds", "Atmosphere & Clouds", cloud_mask)]
            classes = []
            px_area = gsd_m * gsd_m
            for ident, name, mask in masks:
                count = int(mask.sum())
                pct = round(100.0 * count / total_px, 2)
                classes.append({
                    "id": ident,
                    "name": name,
                    "pixel_count": count,
                    "percentage": pct,
                    "area_ha": round(count * px_area / 10000.0, 2),
                    "area_m2": round(count * px_area, 1),
                })

            return {
                "status": "measured",
                "dimensions": {"width": w, "height": h},
                "resolution_m_per_px": gsd_m,
                "total_pixels": total_px,
                "total_area_ha": round(total_px * px_area / 10000.0, 2),
                "mean_brightness": round(float(np.mean(brightness)), 2),
                "edge_density": round(float(np.mean(grad)), 3),
                "classes": classes,
                "detected_objects": [],
                "summary_text": "Image-derived surface classes; object counts require a dedicated validated detector.",
            }
        except Exception as exc:
            return {"status": "error", "classes": [], "detected_objects": [], "summary_text": f"Feature extraction failed: {exc}"}
