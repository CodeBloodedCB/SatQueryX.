"""Fine-grained bi-temporal and multi-temporal change detection service."""
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from backend.config import UPLOAD_DIR
from ai.pair_validator import ImagePairValidator
from ai.models.change_detection import ChangeDetectionModel
from backend.services.audit_service import AuditService


class ChangeService:
    @staticmethod
    async def process_change(image_id_1: str, image_id_2: str, timeline_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        def locate(image_id: str):
            return [f for f in UPLOAD_DIR.glob(f"{image_id}.*") if f.suffix.lower() not in ('.json', '.meta')]

        matched_1 = locate(image_id_1)
        matched_2 = locate(image_id_2)
        if not matched_1 or not matched_2:
            raise HTTPException(status_code=404, detail="One or both images not found")

        path_1, path_2 = str(matched_1[0]), str(matched_2[0])
        validation_report = await ImagePairValidator.validate_pair(path_1, path_2, task="change_detection")

        if validation_report.get("decision") == "BLOCK":
            report = validation_report
            result = {
                "status": "REJECTED",
                "classification": report.get("classification", "INCOMPATIBLE_PAIR"),
                "decision": "BLOCK",
                "reason_codes": report.get("reason_codes", []),
                "spatial_overlap": report.get("spatial_overlap"),
                "distance": report.get("distance"),
                "has_georeference": report.get("has_georeference"),
                "llm_override_status": "DENIED",
                "answer": report.get("direct_explanation", "The image pair failed the spatial compatibility gate."),
                "confidence": report.get("confidence_breakdown", {}).get("overall_confidence", 0.0),
                "changed_regions": [],
                "total_regions": 0,
                "grounding": [],
                "evidence": [
                    {"step": "Executed Image Pair Validation Safety Gate", "confidence": 0.99},
                    {"step": f"Pair rejected: {report.get('classification', 'INCOMPATIBLE_PAIR')}", "confidence": 0.99},
                ],
                "model_used": "pair-validator-v1",
                "validation_report": report,
            }
            blocked = {"status": "blocked", "image_id_1": image_id_1, "image_id_2": image_id_2, "result": result}
            AuditService.log(f"{image_id_1} vs {image_id_2}", "[CHANGE-BLOCKED] spatial compatibility gate", result)
            return blocked

        result = await ChangeDetectionModel.analyze(path_1, path_2)
        result["validation_report"] = validation_report

        timeline_results = []
        current_path = path_2
        for idx, next_id in enumerate(timeline_ids or []):
            next_files = locate(next_id)
            if not next_files:
                continue
            next_path = str(next_files[0])
            step_result = await ChangeDetectionModel.analyze(current_path, next_path)
            timeline_results.append({
                "step_index": idx + 1,
                "interval": f"T{idx + 1} -> T{idx + 2}",
                "target_image_id": next_id,
                "changed_regions_count": step_result.get("total_regions", 0),
                "top_change": (step_result.get("changed_regions") or [{}])[0].get("change_type", "Stable"),
                "confidence": step_result.get("confidence", 0.0),
            })
            current_path = next_path

        result["multi_temporal_timeline"] = timeline_results or None
        final = {"status": "success", "image_id_1": image_id_1, "image_id_2": image_id_2, "result": result}
        AuditService.log(f"{image_id_1} vs {image_id_2}", f"[CHANGE] {result.get('total_regions', 0)} regions", result)
        return final
