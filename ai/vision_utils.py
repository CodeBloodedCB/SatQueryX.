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
        return float(np.mean(np.abs(np.log((arr2.astype(float) + eps) / (arr1.astype(float) + eps)))))

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
        return {"status": "unavailable", "classes": [], "detected_objects": [], "summary_text": "No measured land-cover result is available."}

    @staticmethod
    def _image_metrics(image_source, roi_geometry: Optional[dict] = None):
        if isinstance(image_source, str):
            raw_img = Image.open(image_source)
        elif isinstance(image_source, Image.Image):
            raw_img = image_source.copy()
        elif isinstance(image_source, np.ndarray):
            raw_img = Image.fromarray(image_source)
        else:
            raise ValueError("Unsupported image source")

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
        return raw_img, arr, brightness, grad, total_px

    @staticmethod
    def extract_image_features(image_path: str, roi_geometry: Optional[dict] = None) -> dict:
        """Return real image-derived features used by the conservative VQA fallback."""
        try:
            raw_img, arr, brightness, grad, total_px = VisionUtils._image_metrics(image_path, roi_geometry)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            gray_like = np.mean(np.abs(r - g)) < 2 and np.mean(np.abs(g - b)) < 2
            modality = "SAR" if gray_like and raw_img.mode in ("L", "I", "F") else "Optical/RGB"
            cloud_mask = (r > 195) & (g > 195) & (b > 195) & (np.abs(r - g) < 20) & (np.abs(g - b) < 20) & (grad < 25)
            water_mask = (~cloud_mask) & (((b > r + 5) & (r < 115)) | (brightness < 75))
            ngrdi = (g - r) / (g + r + 1e-6)
            veg_mask = (~cloud_mask) & (~water_mask) & ((ngrdi > 0.035) | ((g > r * 1.08) & (g > b * 1.02)))
            urban_mask = (~cloud_mask) & (~water_mask) & (~veg_mask) & ((grad > 18) | ((brightness > 130) & (np.abs(r - g) < 25) & (np.abs(g - b) < 25)))
            soil_mask = (~cloud_mask) & (~water_mask) & (~veg_mask) & (~urban_mask)
            masks = [("vegetation", veg_mask), ("water", water_mask), ("urban", urban_mask), ("soil", soil_mask), ("clouds", cloud_mask)]
            detected = [name for name, mask in masks if int(mask.sum()) > 0]
            cloud_pct = round(float(cloud_mask.sum() / total_px * 100), 2)
            return {
                "width": int(arr.shape[1]),
                "height": int(arr.shape[0]),
                "modality": modality,
                "mean_rgb": [round(float(np.mean(c)), 2) for c in (r, g, b)],
                "brightness": round(float(np.mean(brightness)), 2),
                "edge_density": round(float(np.mean(grad)), 3),
                "cloud_cover_pct": cloud_pct,
                "detected_classes": detected,
                "grounding_candidates": [],
                "land_cover": VisionUtils.calculate_landcover_and_objects(image_path, roi_geometry=roi_geometry),
            }
        except Exception as exc:
            return {"modality": "Unknown", "detected_classes": [], "grounding_candidates": [], "error": str(exc)}

    @staticmethod
    def calculate_landcover_and_objects(image_source, gsd_m: float = 10.0, roi_geometry: Optional[dict] = None) -> dict:
        """Compute conservative image-derived surface classes and feature statistics."""
        try:
            raw_img, arr, brightness, grad, total_px = VisionUtils._image_metrics(image_source, roi_geometry)
            h, w = arr.shape[:2]
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            cloud_mask = (r > 195) & (g > 195) & (b > 195) & (np.abs(r - g) < 20) & (np.abs(g - b) < 20) & (grad < 25)
            water_mask = (~cloud_mask) & (((b > r + 5) & (b > g - 5) & (r < 115)) | (brightness < 75))
            ngrdi = (g - r) / (g + r + 1e-6)
            veg_mask = (~cloud_mask) & (~water_mask) & ((ngrdi > 0.035) | ((g > r * 1.08) & (g > b * 1.02)))
            urban_mask = (~cloud_mask) & (~water_mask) & (~veg_mask) & ((grad > 18) | ((brightness > 130) & (np.abs(r - g) < 25) & (np.abs(g - b) < 25)))
            soil_mask = (~cloud_mask) & (~water_mask) & (~veg_mask) & (~urban_mask)
            masks = [("vegetation", "Vegetation & Canopy", veg_mask), ("water", "Water Bodies & Hydrology", water_mask), ("urban", "Built-up & Infrastructure", urban_mask), ("soil", "Bare Soil & Terrain", soil_mask), ("clouds", "Atmosphere & Clouds", cloud_mask)]
            px_area = gsd_m * gsd_m
            classes = []
            for ident, name, mask in masks:
                count = int(mask.sum())
                classes.append({"id": ident, "name": name, "pixel_count": count, "percentage": round(100.0 * count / total_px, 2), "area_ha": round(count * px_area / 10000.0, 2), "area_m2": round(count * px_area, 1)})
            return {"status": "measured", "dimensions": {"width": w, "height": h}, "resolution_m_per_px": gsd_m, "total_pixels": total_px, "total_area_ha": round(total_px * px_area / 10000.0, 2), "mean_brightness": round(float(np.mean(brightness)), 2), "edge_density": round(float(np.mean(grad)), 3), "classes": classes, "detected_objects": [], "summary_text": "Image-derived surface classes; object counts require a dedicated validated detector."}
        except Exception as exc:
            return {"status": "error", "classes": [], "detected_objects": [], "summary_text": f"Feature extraction failed: {exc}"}
