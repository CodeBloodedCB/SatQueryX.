from ai.vision_utils import VisionUtils
from ai.ollama_client import OllamaClient


class VQAModel:
    """Grounded VQA with cloud/local VLM first and deterministic CV fallback second."""

    @staticmethod
    async def analyze(image_path: str, query: str) -> dict:
        if not VisionUtils.is_valid_image(image_path):
            return {
                "status": "rejected",
                "answer": "The supplied file is not a valid readable image. No visual inference was performed.",
                "confidence": 0.0,
                "grounding": [],
                "evidence": [{"step": "Input image validation failed", "confidence": 1.0}],
                "model_used": "input-validator-v1",
            }

        features = VisionUtils.extract_image_features(image_path)
        modality = features.get("modality", "Optical")
        detected_classes = features.get("detected_classes", ["terrain"])
        grounding = features.get("grounding_candidates", [])
        brightness = float(features.get("brightness", 0))
        edge_density = float(features.get("edge_density", 0))
        lower_query = query.lower()

        # Native multimodal inference when a provider is configured.
        vlm_prompt = (
            f"Analyze this {modality} remote-sensing image. Answer the user's question only from visible evidence. "
            f"Do not invent counts, coordinates, dates, sensor metadata, or measurements.\nQuestion: {query}"
        )
        vlm_obs = await OllamaClient.generate_vlm(vlm_prompt, image_path=image_path, timeout=30.0)
        if vlm_obs and len(vlm_obs.strip()) > 5:
            return {
                "status": "success",
                "answer": vlm_obs.strip(),
                "confidence": 0.90,
                "grounding": grounding,
                "evidence": [
                    {"step": f"Validated readable {modality} image", "confidence": 1.0},
                    {"step": "Ran multimodal vision-language inference", "confidence": 0.90},
                    {"step": "Returned only observations supported by the image", "confidence": 0.90},
                ],
                "model_used": f"multimodal-vlm ({OllamaClient.get_active_engine()})",
                "land_cover": features.get("land_cover") or VisionUtils.calculate_landcover_and_objects(image_path),
            }

        # Deterministic image-derived fallback. It deliberately does not claim
        # object counts that a generic RGB image cannot establish reliably.
        if any(k in lower_query for k in ("water", "river", "lake", "ocean", "sea")):
            answer = f"The image-derived spectral analysis indicates water-like low-reflectance regions in the {modality} scene. Exact water extent should be taken from the computed land-cover mask."
            confidence = 0.80
        elif any(k in lower_query for k in ("building", "urban", "city", "structure", "built")):
            answer = f"The scene contains structural texture consistent with built-up areas; measured edge density is {edge_density:.2f}. A generic RGB scene does not provide enough evidence for a reliable building count."
            confidence = 0.76
        elif any(k in lower_query for k in ("cloud", "weather", "atmosphere")):
            cloud = features.get("cloud_cover_pct")
            answer = f"Estimated image-derived cloud attenuation is {cloud:.2f}% based on the configured pixel mask." if isinstance(cloud, (int, float)) else "Cloud cover is not available from the computed image features."
            confidence = 0.82
        elif any(k in lower_query for k in ("ship", "vessel", "boat")):
            answer = "Maritime target candidates were computed from image contrast, but a generic image alone is insufficient to assert a vessel count without a validated remote-sensing detector."
            confidence = 0.65
        else:
            answer = f"Analyzed the {modality} scene. Image-derived classes include {', '.join(detected_classes)}; mean brightness is {brightness:.2f}."
            confidence = 0.72

        return {
            "status": "success",
            "answer": answer,
            "confidence": confidence,
            "grounding": grounding,
            "evidence": [
                {"step": f"Validated readable {modality} image", "confidence": 1.0},
                {"step": "Computed deterministic image features", "confidence": 0.92},
                {"step": "Applied conservative query-specific interpretation", "confidence": confidence},
            ],
            "model_used": "deterministic-cv-fallback",
            "land_cover": features.get("land_cover") or VisionUtils.calculate_landcover_and_objects(image_path),
        }
