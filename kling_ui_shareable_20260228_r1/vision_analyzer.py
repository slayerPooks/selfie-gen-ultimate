"""Vision analysis via OpenRouter API (chat completions with image input)."""

import os
import base64
import requests
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Analyze portrait images using OpenRouter vision models."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_SYSTEM_PROMPT = (
        "You are a portrait photo analyzer for AI image generation. "
        "Analyze the provided portrait image and generate a detailed prompt that "
        "describes the person's physical appearance, facial features, expression, "
        "hair, clothing, pose, and lighting for a static portrait photo. "
        "DO NOT mention video, animation, or movement. Focus strictly on physical "
        "identity, expression, and lighting to be used as an image generation prompt. "
        "Return ONLY the prompt text, no explanations or formatting."
    )
    DEFAULT_USER_PROMPT = (
        "Analyze this portrait and generate a static portrait photo prompt."
    )

    def __init__(
        self,
        api_key: str,
        model: str = "bytedance-seed/seed-1.6-flash",
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.system_prompt = (
            system_prompt.strip() if system_prompt and system_prompt.strip() else self.DEFAULT_SYSTEM_PROMPT
        )
        self.user_prompt = (
            user_prompt.strip() if user_prompt and user_prompt.strip() else self.DEFAULT_USER_PROMPT
        )
        self._progress_callback: Optional[Callable[[str, str], None]] = None

    def set_progress_callback(self, cb: Callable[[str, str], None]):
        self._progress_callback = cb

    def _report(self, msg: str, level: str = "info"):
        if self._progress_callback:
            self._progress_callback(msg, level)

    def analyze_image(self, image_path: str) -> Optional[dict]:
        """Analyze a portrait image, return dict with 'prompt' key.

        Sends image as base64 data URI to OpenRouter chat completions.
        Returns {"prompt": "..."} or None on failure.
        """
        self._report(f"Reading image: {os.path.basename(image_path)}", "upload")

        # Read and encode image as base64
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except OSError as e:
            self._report(f"Cannot read image: {e}", "error")
            logger.error("VisionAnalyzer read error: %s", e)
            return None

        # Determine MIME type
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "bmp": "image/bmp",
        }.get(ext, "image/jpeg")

        data_uri = f"data:{mime};base64,{image_data}"

        self._report(f"Sending to {self.model}...", "api")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                        {
                            "type": "text",
                            "text": self.user_prompt,
                        },
                    ],
                },
            ],
            "max_tokens": 500,
            "temperature": 0.7,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                self.ENDPOINT, json=payload, headers=headers, timeout=30
            )
            resp.raise_for_status()
            result = resp.json()
            prompt = result["choices"][0]["message"]["content"].strip()
            self._report("Analysis complete", "success")
            return {"prompt": prompt}
        except requests.RequestException as e:
            self._report(f"API error: {e}", "error")
            logger.error("VisionAnalyzer error: %s", e)
            return None
        except (KeyError, IndexError) as e:
            self._report(f"Unexpected response format: {e}", "error")
            logger.error("VisionAnalyzer parse error: %s", e)
            return None
