"""Generate selfie-style portraits using fal.ai identity image models."""

import os
import random
import logging
import re
import base64
import time
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SelfieGenerator:
    """Generate selfie images using fal.ai image-to-image identity models."""

    DEFAULT_ENDPOINT = "fal-ai/flux-pulid"
    HANDOFF_JSON_KEYS = (
        "hair",
        "skin",
        "eyes",
        "face_shape",
        "age_range",
        "gender",
        "clothing",
        "expression",
    )
    FLUX_PULID_PROMPT_APPEND = (
        "Photorealistic, natural skin texture, amateur photography aesthetic, "
        "unfiltered iPhone 7 quality. Not illustrated, not anime, not painting."
    )
    @staticmethod
    def resolve_wildcards(template: str) -> str:
        """Resolve {opt1|opt2|opt3} blocks by randomly picking one option per block."""
        def _pick(match):
            options = [o.strip() for o in match.group(1).split("|") if o.strip()]
            return random.choice(options) if options else ""
        return re.sub(r"\{([^{}]+)\}", _pick, template)

    AVAILABLE_MODELS = [
        {
            "endpoint": "bfl/flux-kontext-pro",
            "label": "FLUX Kontext Pro (BFL)",
            "slug": "flux-kontext-pro",
            "provider": "bfl",
            "api_url": "https://api.bfl.ai/v1/flux-kontext-pro",
        },
        {
            "endpoint": "bfl/flux-kontext-max",
            "label": "FLUX Kontext Max (BFL)",
            "slug": "flux-kontext-max",
            "provider": "bfl",
            "api_url": "https://api.bfl.ai/v1/flux-kontext-max",
        },
        {
            "endpoint": "bfl/flux-2-pro",
            "label": "FLUX 2 Pro (BFL)",
            "slug": "flux-2-pro",
            "provider": "bfl",
            "api_url": "https://api.bfl.ai/v1/flux-2-pro",
        },
        {
            "endpoint": "fal-ai/flux-pulid",
            "label": "FLUX.1 + PuLID",
            "slug": "flux-pulid",
            "api_url": "https://fal.ai/models/fal-ai/flux-pulid/api",
        },
        {
            "endpoint": "fal-ai/pulid",
            "label": "PuLID",
            "slug": "pulid",
            "api_url": "https://fal.ai/models/fal-ai/pulid/api",
        },
        {
            "endpoint": "fal-ai/instant-character",
            "label": "Instant Character",
            "slug": "instant-character",
            "api_url": "https://fal.ai/models/fal-ai/instant-character/api",
        },
        {
            "endpoint": "fal-ai/z-image/turbo/image-to-image",
            "label": "Z-Image Turbo",
            "slug": "z-image-turbo",
            "api_url": "https://fal.ai/models/fal-ai/z-image/turbo/image-to-image/api",
        },
        {
            "endpoint": "fal-ai/nano-banana-pro/edit",
            "label": "Nano Banana Pro",
            "slug": "nano-banana-pro-edit",
            "api_url": "https://fal.ai/models/fal-ai/nano-banana-pro/edit/api",
        },
        {
            "endpoint": "fal-ai/qwen-image-edit",
            "label": "Qwen Portrait / Image Edit",
            "slug": "qwen-image-edit",
            "api_url": "https://fal.ai/models/fal-ai/qwen-image-edit/api",
        },
        {
            "endpoint": "fal-ai/bytedance/seedream/v4.5/edit",
            "label": "Seedream 4.5",
            "slug": "seedream-4-5",
            "api_url": "https://fal.ai/models/fal-ai/bytedance/seedream/v4.5/edit/api",
        },
        {
            # Keep v5 endpoint selectable if account supports it; if unavailable,
            # API will return a clear submit error in the GUI log.
            "endpoint": "fal-ai/bytedance/seedream/v5/edit",
            "label": "Seedream v5",
            "slug": "seedream-v5",
            "api_url": "https://fal.ai/models/fal-ai/bytedance/seedream/v5/edit/api",
        },
        {
            "endpoint": "fal-ai/bytedance/seedream/v5/lite/edit",
            "label": "Seedream v5 Lite",
            "slug": "seedream-v5-lite",
            "api_url": "https://fal.ai/models/fal-ai/bytedance/seedream/v5/lite/edit/api",
        },
    ]

    def __init__(self, api_key: str, freeimage_key: Optional[str] = None, bfl_api_key: Optional[str] = None):
        self.api_key = api_key
        self._freeimage_key = freeimage_key
        self._bfl_api_key = bfl_api_key or ""
        self._progress_callback: Optional[Callable[[str, str], None]] = None

    def set_progress_callback(self, cb: Callable[[str, str], None]):
        self._progress_callback = cb

    def _report(self, msg: str, level: str = "info"):
        if self._progress_callback:
            self._progress_callback(msg, level)

    @classmethod
    def get_available_models(cls) -> List[Dict[str, str]]:
        """Return supported selfie model metadata for UI rendering."""
        return [dict(model) for model in cls.AVAILABLE_MODELS]

    @classmethod
    def get_model_label(cls, endpoint: str) -> str:
        for model in cls.AVAILABLE_MODELS:
            if model["endpoint"] == endpoint:
                return model["label"]
        return endpoint

    @classmethod
    def normalize_handoff_identity(cls, payload: Any) -> Optional[Dict[str, str]]:
        """Normalize Step 1 JSON payload into the expected identity field map."""
        if not isinstance(payload, dict):
            return None
        normalized: Dict[str, str] = {}
        for key in cls.HANDOFF_JSON_KEYS:
            value = payload.get(key)
            if value is None:
                return None
            normalized[key] = str(value).strip()
        return normalized

    @classmethod
    def _model_short_name(cls, endpoint: str) -> str:
        for model in cls.AVAILABLE_MODELS:
            if model["endpoint"] == endpoint:
                slug = model.get("slug", "")
                if slug:
                    return re.sub(r"[^a-z0-9\-]+", "-", slug.lower()).strip("-")
        fallback = endpoint.split("/")[-1].lower()
        return re.sub(r"[^a-z0-9\-]+", "-", fallback).strip("-")

    @staticmethod
    def _closest_aspect_ratio(width: int, height: int) -> str:
        target = width / max(1, height)
        options = {
            "21:9": 21 / 9,
            "16:9": 16 / 9,
            "3:2": 3 / 2,
            "4:3": 4 / 3,
            "5:4": 5 / 4,
            "1:1": 1.0,
            "4:5": 4 / 5,
            "3:4": 3 / 4,
            "2:3": 2 / 3,
            "9:16": 9 / 16,
        }
        return min(options.items(), key=lambda kv: abs(kv[1] - target))[0]

    @staticmethod
    def _next_indexed_output_path(output_folder: str, prefix: str) -> str:
        max_index = 0
        for name in os.listdir(output_folder):
            if not name.lower().endswith(".png"):
                continue
            if not name.startswith(prefix):
                continue
            suffix = os.path.splitext(name)[0][len(prefix):]
            if suffix.isdigit():
                max_index = max(max_index, int(suffix))
        next_index = max_index + 1
        output_path = os.path.join(output_folder, f"{prefix}{next_index:03d}.png")
        while os.path.exists(output_path):
            next_index += 1
            output_path = os.path.join(output_folder, f"{prefix}{next_index:03d}.png")
        return output_path

    @staticmethod
    def _compute_similarity_percent(
        source_image_path: str,
        generated_image_path: str,
    ) -> Optional[int]:
        try:
            from deepface import DeepFace
        except Exception:
            return None

        try:
            result = DeepFace.verify(
                img1_path=source_image_path,
                img2_path=generated_image_path,
                model_name="Facenet",
                enforce_detection=False,
            )
            distance = float(result.get("distance", 0.0))
            threshold = float(result.get("threshold", 0.0))
            if threshold <= 0:
                return None
            # Scale over 2x threshold so scores degrade gracefully rather
            # than cliff-dropping to 0% at the verification boundary.
            # distance=0 → 100%, distance=threshold → 50%, distance=2*threshold → 0%.
            max_distance = threshold * 2.0
            similarity = max(0, round((1 - distance / max_distance) * 100))
            return min(100, similarity)
        except Exception:
            return None

    @classmethod
    def _build_payload(
        cls,
        model_endpoint: str,
        prompt: str,
        image_url: str,
        id_weight: float,
        width: int,
        height: int,
        seed: int,
    ) -> dict:
        if model_endpoint == "fal-ai/flux-pulid":
            flux_prompt = f"{prompt.strip()} {cls.FLUX_PULID_PROMPT_APPEND}".strip()
            return {
                "prompt": flux_prompt,
                "reference_image_url": image_url,
                "id_weight": id_weight,
                "width": width,
                "height": height,
                "seed": seed,
                "num_images": 1,
            }

        if model_endpoint == "fal-ai/pulid":
            return {
                "prompt": prompt,
                "reference_images": [{"image_url": image_url}],
                "id_scale": id_weight,
                "image_size": {"width": width, "height": height},
                "seed": seed,
                "num_images": 1,
            }

        if model_endpoint == "fal-ai/instant-character":
            return {
                "prompt": prompt,
                "image_url": image_url,
                # Instant Character uses `scale`; map Face Resemblance into it.
                "scale": max(0.1, round(id_weight * 1.5, 3)),
                "image_size": {"width": width, "height": height},
                "seed": seed,
                "num_images": 1,
            }

        if model_endpoint == "fal-ai/z-image/turbo/image-to-image":
            return {
                "prompt": prompt,
                "image_url": image_url,
                "image_size": {"width": width, "height": height},
                "strength": 0.85,
                "num_images": 1,
                "output_format": "png",
                "seed": seed,
            }

        if model_endpoint == "fal-ai/nano-banana-pro/edit":
            nano_prompt = (
                "zoomed out, full upper body visible, arm's length distance, "
                f"{prompt}"
            )
            return {
                "prompt": nano_prompt,
                "image_urls": [image_url],
                "num_images": 1,
                "aspect_ratio": SelfieGenerator._closest_aspect_ratio(width, height),
                "resolution": "1K",
                "output_format": "png",
                "seed": seed,
            }

        if model_endpoint == "fal-ai/qwen-image-edit":
            return {
                "prompt": prompt,
                "image_url": image_url,
                "num_images": 1,
                "seed": seed,
            }

        if model_endpoint in {
            "fal-ai/bytedance/seedream/v4.5/edit",
            "fal-ai/bytedance/seedream/v5/edit",
            "fal-ai/bytedance/seedream/v5/lite/edit",
        }:
            return {
                "prompt": prompt,
                "image_urls": [image_url],
                "image_size": {"width": width, "height": height},
                "num_images": 1,
                "seed": seed,
            }

        raise ValueError(f"Unsupported selfie model endpoint: {model_endpoint}")

    @classmethod
    def _get_model_provider(cls, endpoint: str) -> str:
        """Return 'bfl' or 'fal' based on the model's provider field."""
        for model in cls.AVAILABLE_MODELS:
            if model["endpoint"] == endpoint:
                return model.get("provider", "fal")
        return "fal"

    def _generate_fal_raw(
        self,
        image_path: str,
        prompt: str,
        temp_output_path: str,
        resolved_endpoint: str,
        resolved_label: str,
        id_weight: float,
        width: int,
        height: int,
        actual_seed: int,
    ) -> bool:
        """Run the fal.ai generation pipeline. Returns True on success."""
        from fal_utils import (
            upload_to_freeimage,
            fal_queue_submit,
            fal_queue_poll,
            fal_download_file,
        )

        self._report("Uploading identity reference...", "upload")
        image_url = upload_to_freeimage(
            image_path, progress_cb=self._progress_callback,
            api_key=self._freeimage_key,
        )
        if not image_url:
            self._report("Failed to upload image", "error")
            return False

        payload = self._build_payload(
            model_endpoint=resolved_endpoint,
            prompt=prompt,
            image_url=image_url,
            id_weight=id_weight,
            width=width,
            height=height,
            seed=actual_seed,
        )

        self._report(
            f"Submitting to {resolved_label} ({resolved_endpoint}, seed={actual_seed})...",
            "task",
        )

        result = fal_queue_submit(
            self.api_key, resolved_endpoint, payload, self._progress_callback
        )
        if not result:
            self._report("Failed to submit job", "error")
            return False

        status_url = result.get("status_url")
        if not status_url:
            self._report("No status URL in response", "error")
            return False

        self._report("Waiting for generation...", "progress")
        final = fal_queue_poll(
            self.api_key, status_url, self._progress_callback,
            max_wait_seconds=120,
        )
        if not final:
            self._report("Generation failed or timed out", "error")
            return False

        images = final.get("images", [])
        if not images:
            self._report("No images in result", "error")
            return False

        image_url_result = images[0].get("url") if isinstance(images[0], dict) else images[0]
        if not image_url_result:
            self._report("No image URL in result", "error")
            return False

        self._report("Downloading result...", "download")
        return fal_download_file(image_url_result, temp_output_path, self._progress_callback)

    def _generate_bfl_raw(
        self,
        image_path: str,
        prompt: str,
        temp_output_path: str,
        resolved_endpoint: str,
        resolved_label: str,
        actual_seed: int = -1,
    ) -> bool:
        """Run the BFL (api.bfl.ai) generation pipeline. Returns True on success."""
        import requests
        from PIL import Image
        from io import BytesIO

        if not self._bfl_api_key:
            self._report("BFL API key is not set", "error")
            return False

        # Determine API URL from model metadata
        api_url = None
        for model in self.AVAILABLE_MODELS:
            if model["endpoint"] == resolved_endpoint:
                api_url = model.get("api_url")
                break
        if not api_url:
            self._report(f"No API URL for BFL model: {resolved_endpoint}", "error")
            return False

        # Base64-encode the image (resize to fit reasonable bounds, JPEG for size)
        self._report("Encoding image for BFL upload...", "upload")
        try:
            img = Image.open(image_path)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.thumbnail((1024, 1024), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=90)
            image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as exc:
            self._report(f"Failed to encode image: {exc}", "error")
            return False

        # Submit to BFL — field is "input_image" with raw base64 (no data URI prefix)
        headers = {
            "x-key": self._bfl_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "input_image": image_b64,
            "output_format": "png",
        }
        if actual_seed >= 0:
            payload["seed"] = actual_seed

        self._report(f"Submitting to {resolved_label}...", "task")
        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            submit_data = resp.json()
        except requests.exceptions.HTTPError as exc:
            body = ""
            try:
                body = exc.response.text[:300]
            except Exception:
                pass
            self._report(f"BFL submit failed ({exc.response.status_code}): {body}", "error")
            return False
        except Exception as exc:
            self._report(f"BFL submit failed: {exc}", "error")
            return False

        polling_url = submit_data.get("polling_url")
        task_id = submit_data.get("id", "")
        if polling_url:
            self._report(f"BFL task {task_id} queued, polling...", "task")
        else:
            # Some BFL endpoints may return the result directly
            result_obj = submit_data.get("result")
            sample_url = (
                result_obj.get("sample") if isinstance(result_obj, dict) else None
            ) or submit_data.get("sample")
            if sample_url:
                return self._bfl_download(sample_url, temp_output_path)
            self._report(f"No polling_url in BFL response: {submit_data}", "error")
            return False

        # Poll for result (BFL status values: Pending, Ready, Error)
        self._report("Waiting for BFL generation...", "progress")
        max_polls = 120
        for i in range(max_polls):
            time.sleep(5)
            try:
                poll_resp = requests.get(polling_url, headers={"x-key": self._bfl_api_key}, timeout=30)
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
            except Exception as exc:
                self._report(f"BFL poll error: {exc}", "warning")
                continue

            status = poll_data.get("status", "")
            status_lower = status.lower()
            if status_lower in ("ready", "succeeded"):
                result_obj = poll_data.get("result")
                sample_url = (
                    result_obj.get("sample") if isinstance(result_obj, dict) else None
                ) or poll_data.get("sample")
                if sample_url:
                    return self._bfl_download(sample_url, temp_output_path)
                self._report(f"BFL result missing sample URL: {poll_data}", "error")
                return False
            elif status_lower in ("error", "failed"):
                err_msg = poll_data.get("error", "Unknown BFL error")
                self._report(f"BFL generation failed: {err_msg}", "error")
                return False
            else:
                if i % 6 == 0:
                    self._report(f"BFL status: {status} (poll {i+1})...", "progress")

        self._report("BFL generation timed out", "error")
        return False

    def _bfl_download(self, url: str, output_path: str) -> bool:
        """Download a BFL result image to disk."""
        import requests

        self._report("Downloading BFL result...", "download")
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return True
        except Exception as exc:
            self._report(f"BFL download failed: {exc}", "error")
            return False

    def generate(
        self,
        image_path: str,
        prompt: str,
        output_folder: str,
        id_weight: float = 1.0,
        width: int = 896,
        height: int = 1152,
        seed: int = -1,
        model_endpoint: str = "",
        model_label: str = "",
    ) -> Optional[str]:
        """Generate a selfie from an identity reference image.

        Dispatches to fal.ai or BFL depending on the model's provider.

        Returns:
            Absolute path to generated image, or None on failure.
        """
        actual_seed = random.randint(0, 2**32 - 1) if seed == -1 else seed
        resolved_endpoint = model_endpoint or self.DEFAULT_ENDPOINT
        resolved_label = model_label or self.get_model_label(resolved_endpoint)
        provider = self._get_model_provider(resolved_endpoint)

        os.makedirs(output_folder, exist_ok=True)
        stem = Path(image_path).stem
        model_short = self._model_short_name(resolved_endpoint)
        temp_output_path = os.path.join(
            output_folder, f"{stem}_{model_short}_tmp_{actual_seed}.png"
        )
        temp_counter = 1
        while os.path.exists(temp_output_path):
            temp_counter += 1
            temp_output_path = os.path.join(
                output_folder, f"{stem}_{model_short}_tmp_{actual_seed}_{temp_counter}.png"
            )

        # Provider dispatch
        if provider == "bfl":
            success = self._generate_bfl_raw(
                image_path=image_path,
                prompt=prompt,
                temp_output_path=temp_output_path,
                resolved_endpoint=resolved_endpoint,
                resolved_label=resolved_label,
                actual_seed=actual_seed,
            )
        else:
            success = self._generate_fal_raw(
                image_path=image_path,
                prompt=prompt,
                temp_output_path=temp_output_path,
                resolved_endpoint=resolved_endpoint,
                resolved_label=resolved_label,
                id_weight=id_weight,
                width=width,
                height=height,
                actual_seed=actual_seed,
            )

        if not success:
            return None

        # Shared post-processing: similarity + final rename
        similarity = self._compute_similarity_percent(image_path, temp_output_path)
        if similarity is None:
            self._report(f"[{resolved_label}] Similarity: n/a", "info")
            similarity_tag = "simna"
        else:
            self._report(f"[{resolved_label}] Similarity: {similarity}%", "info")
            similarity_tag = f"sim{similarity}"

        final_prefix = f"{stem}_{model_short}_{similarity_tag}_"
        final_output_path = self._next_indexed_output_path(output_folder, final_prefix)
        try:
            os.replace(temp_output_path, final_output_path)
        except Exception:
            try:
                os.remove(temp_output_path)
            except Exception:
                pass
            self._report("Download finalization failed", "error")
            return None

        self._report(f"Saved: {os.path.basename(final_output_path)}", "success")
        return final_output_path
