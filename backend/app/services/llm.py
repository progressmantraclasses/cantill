"""Thin Gemini REST wrapper. The LLM only translates text into data; humans approve it and the engine never calls it."""
from __future__ import annotations

import base64
import json
import os
import re

import requests

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLM:
    def __init__(self):
        self.key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    def available(self) -> bool:
        return bool(self.key)

    def _call(self, parts: list[dict], system: str | None = None, json_mode: bool = True) -> str:
        body = {"contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": 0.1}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        r = requests.post(ENDPOINT.format(model=self.model), json=body, timeout=90,
                          headers={"x-goog-api-key": self.key, "content-type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Gemini returned no content: {str(data)[:300]}") from e

    def json_call(self, prompt: str, system: str | None = None, pdf: bytes | None = None) -> dict:
        parts = [{"text": prompt}]
        if pdf:
            parts.append({"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf).decode()}})
        text = self._call(parts, system)
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        return json.loads(text)


llm = LLM()
