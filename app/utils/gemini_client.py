import json
import os
from typing import Any, Dict, List, Optional

import google.generativeai as genai


class GeminiClient:
    def __init__(self, model_name: str = "gemini-2.5-flash") -> None:
        api_key = ""
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required to call Gemini")
        genai.configure(api_key=api_key)
        self.model_name = model_name

    def build_model(self, tools: Optional[List[Dict[str, Any]]] = None, system_instruction: Optional[str] = None):
        return genai.GenerativeModel(
            model_name=self.model_name,
            tools=tools or None,
            system_instruction=system_instruction
        )

    def detect_and_translate(self, text: str, target_language: str = "en") -> Dict[str, str]:
        prompt = (
            "You are a translation helper. Detect the ISO-639-1 language code for the provided text "
            f"and translate it to {target_language}. Respond ONLY with JSON using keys 'language' "
            "and 'translation'."
        )
        model = self.build_model()
        resp = model.generate_content([
            {"role": "user", "parts": [f"{prompt}\n\nText:\n{text}"]}
        ])
        lang = "en"
        translation = text
        try:
            payload = json.loads((resp.text or "{}"))
            lang = payload.get("language") or lang
            translation = payload.get("translation") or translation
        except Exception:
            pass
        return {"language": lang, "translation": translation}

    def translate_text(self, text: str, target_language: str) -> str:
        prompt = (
            f"Translate the following text to {target_language}. Return only the translated text without extra narration.\n\n"
            f"Text:\n{text}"
        )
        model = self.build_model()
        resp = model.generate_content([{"role": "user", "parts": [prompt]}])
        return resp.text or text

    def generate(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        model = self.build_model(tools=tools, system_instruction=kwargs.pop("system_instruction", None))
        return model.generate_content(messages, tools=tools, **kwargs)
