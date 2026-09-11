"""Cloud inference adapters for SatQuery AI.

Gemini is the preferred multimodal provider. OpenRouter and Groq are supported
as configurable fallbacks. Secrets are read only from environment variables.
"""
import base64
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("satquery.cloud_ai")

SYSTEM_PROMPT = """You are SatQuery AI, an expert remote-sensing assistant for SIH26167.
Use only evidence present in the supplied imagery or upstream deterministic analysis.
Never invent coordinates, dates, sensor metadata, object counts, areas, or change percentages.
If something cannot be established from the evidence, say that it is not discernible.
"""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class CloudAI:
    @staticmethod
    def is_available() -> bool:
        return any(_env(k) for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"))

    @staticmethod
    def get_active_provider() -> str:
        if _env("GEMINI_API_KEY"):
            return f"Google Gemini ({_env('GEMINI_MODEL', 'gemini-2.5-flash')})"
        if _env("OPENROUTER_API_KEY"):
            return f"OpenRouter ({_env('OPENROUTER_MODEL', 'openrouter/free')})"
        if _env("GROQ_API_KEY"):
            return f"Groq ({_env('GROQ_MODEL', 'llama-3.3-70b-versatile')})"
        if _env("OPENAI_API_KEY"):
            return f"OpenAI ({_env('OPENAI_MODEL', 'gpt-4o-mini')})"
        return "None"

    @staticmethod
    def _gemini_candidates() -> List[str]:
        return list(dict.fromkeys([
            _env("GEMINI_MODEL", "gemini-2.5-flash"),
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
        ]))

    @staticmethod
    async def generate_vlm(prompt: str, image_path: str, system: Optional[str] = None, timeout: float = 30.0) -> Optional[str]:
        if not os.path.exists(image_path):
            return None
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError:
            return None

        ext = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".tif": "image/tiff", ".tiff": "image/tiff"}.get(ext, "image/jpeg")
        system_text = system or SYSTEM_PROMPT

        # 1. Gemini native multimodal inference.
        key = _env("GEMINI_API_KEY")
        if key:
            headers = {"Content-Type": "application/json", "X-goog-api-key": key}
            payload = {
                "contents": [{"role": "user", "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": image_b64}},
                ]}],
                "system_instruction": {"parts": [{"text": system_text}]},
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
            }
            for model in CloudAI._gemini_candidates():
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            return text
                    logger.warning("Gemini VLM %s returned %s", model, response.status_code)
                except Exception as exc:
                    logger.warning("Gemini VLM %s failed: %s", model, exc)

        # 2. OpenRouter/OpenAI-compatible multimodal fallback.
        router_key = _env("OPENROUTER_API_KEY")
        openai_key = _env("OPENAI_API_KEY")
        if router_key or openai_key:
            base = "https://openrouter.ai/api/v1" if router_key else "https://api.openai.com/v1"
            key = router_key or openai_key
            model = _env("OPENROUTER_VISION_MODEL", "openrouter/free") if router_key else _env("OPENAI_MODEL", "gpt-4o-mini")
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            if router_key:
                headers.update({"HTTP-Referer": _env("OPENROUTER_SITE_URL", "https://satqueryx-workspace.vercel.app"), "X-Title": "SatQuery AI"})
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ]},
                ],
                "temperature": 0.1,
                "max_tokens": 500,
            }
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
                if response.status_code == 200:
                    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip() or None
                logger.warning("Vision provider returned %s: %s", response.status_code, response.text[:300])
            except Exception as exc:
                logger.warning("OpenAI-compatible VLM failed: %s", exc)
        return None

    @staticmethod
    async def generate(prompt: str, system: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
        system_text = system or SYSTEM_PROMPT

        key = _env("GEMINI_API_KEY")
        if key:
            headers = {"Content-Type": "application/json", "X-goog-api-key": key}
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "system_instruction": {"parts": [{"text": system_text}]},
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
            }
            for model in CloudAI._gemini_candidates():
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            return text
                except Exception as exc:
                    logger.warning("Gemini text failed: %s", exc)

        # OpenRouter and OpenAI share the OpenAI chat-completions protocol.
        compatible = [
            ("https://openrouter.ai/api/v1", _env("OPENROUTER_API_KEY"), _env("OPENROUTER_MODEL", "openrouter/free")),
            ("https://api.openai.com/v1", _env("OPENAI_API_KEY"), _env("OPENAI_MODEL", "gpt-4o-mini")),
        ]
        for base, key, model in compatible:
            if not key:
                continue
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            if "openrouter" in base:
                headers.update({"HTTP-Referer": _env("OPENROUTER_SITE_URL", "https://satqueryx-workspace.vercel.app"), "X-Title": "SatQuery AI"})
            payload = {"model": model, "messages": [{"role": "system", "content": system_text}, {"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500}
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
                if response.status_code == 200:
                    text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if text:
                        return text
            except Exception as exc:
                logger.warning("OpenAI-compatible text failed: %s", exc)

        # Groq is text-only here; vision requests should use Gemini/OpenRouter/OpenAI.
        key = _env("GROQ_API_KEY")
        if key:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {"model": _env("GROQ_MODEL", "llama-3.3-70b-versatile"), "messages": [{"role": "system", "content": system_text}, {"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500}
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if response.status_code == 200:
                    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip() or None
            except Exception as exc:
                logger.warning("Groq text failed: %s", exc)
        return None

    @staticmethod
    async def chat(messages: List[Dict[str, str]], system: Optional[str] = None, timeout: float = 20.0) -> Optional[str]:
        system_text = system or SYSTEM_PROMPT
        prompt = "\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages)
        return await CloudAI.generate(prompt, system=system_text, timeout=timeout)
