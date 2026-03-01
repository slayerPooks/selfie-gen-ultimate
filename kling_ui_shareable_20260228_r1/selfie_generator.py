"""Generate selfie-style portraits using fal.ai identity image models."""

import os
import random
import logging
from typing import Optional, Callable, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class SelfieGenerator:
    """Generate selfie images using fal.ai image-to-image identity models."""

    DEFAULT_ENDPOINT = "fal-ai/flux-pulid"
    AVAILABLE_MODELS = [
        {
            "endpoint": "fal-ai/flux-pulid",
            "label": "PuLID Flux",
            "api_url": "https://fal.ai/models/fal-ai/flux-pulid/api",
        },
        {
            "endpoint": "fal-ai/pulid",
            "label": "PuLID",
            "api_url": "https://fal.ai/models/fal-ai/pulid/api",
        },
        {
            "endpoint": "fal-ai/instant-character",
            "label": "Instant Character",
            "api_url": "https://fal.ai/models/fal-ai/instant-character/api",
        },
    ]

    def __init__(self, api_key: str, freeimage_key: Optional[str] = None):
        self.api_key = api_key
        self._freeimage_key = freeimage_key
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
    def _model_short_name(cls, endpoint: str) -> str:
        mapping = {
            "fal-ai/flux-pulid": "fluxpulid",
            "fal-ai/pulid": "pulid",
            "fal-ai/instant-character": "instchar",
        }
        return mapping.get(endpoint, endpoint.split("/")[-1].replace("-", ""))

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
            return {
                "prompt": prompt,
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

        raise ValueError(f"Unsupported selfie model endpoint: {model_endpoint}")

    def generate(
        self,
        image_path: str,
        prompt: str,
        output_folder: str,
        id_weight: float = 0.8,
        width: int = 896,
        height: int = 1152,
        seed: int = -1,
        model_endpoint: str = "",
        model_label: str = "",
    ) -> Optional[str]:
        """Generate a selfie from an identity reference image.

        Args:
            image_path: Path to identity reference image
            prompt: Text prompt for the selfie
            output_folder: Where to save output
            id_weight: Identity preservation strength (0.0–1.0)
            width: Output width in pixels
            height: Output height in pixels
            seed: Random seed (-1 for random)

        Returns:
            Absolute path to generated image, or None on failure.
        """
        from fal_utils import (
            upload_to_freeimage,
            fal_queue_submit,
            fal_queue_poll,
            fal_download_file,
        )

        # Upload identity image
        self._report("Uploading identity reference...", "upload")
        image_url = upload_to_freeimage(
            image_path, progress_cb=self._progress_callback,
            api_key=self._freeimage_key,
        )
        if not image_url:
            self._report("Failed to upload image", "error")
            return None

        # Resolve seed
        actual_seed = random.randint(0, 2**32 - 1) if seed == -1 else seed
        resolved_endpoint = model_endpoint or self.DEFAULT_ENDPOINT
        resolved_label = model_label or self.get_model_label(resolved_endpoint)

        # Build payload
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

        # Submit to queue
        result = fal_queue_submit(
            self.api_key, resolved_endpoint, payload, self._progress_callback
        )
        if not result:
            self._report("Failed to submit job", "error")
            return None

        status_url = result.get("status_url")
        if not status_url:
            self._report("No status URL in response", "error")
            return None

        self._report("Waiting for generation...", "progress")
        final = fal_queue_poll(self.api_key, status_url, self._progress_callback)
        if not final:
            self._report("Generation failed or timed out", "error")
            return None

        # Extract image URL from result
        images = final.get("images", [])
        if not images:
            self._report("No images in result", "error")
            return None

        image_url_result = images[0].get("url") if isinstance(images[0], dict) else images[0]
        if not image_url_result:
            self._report("No image URL in result", "error")
            return None

        # Build output path (unique)
        os.makedirs(output_folder, exist_ok=True)
        stem = Path(image_path).stem
        model_short = self._model_short_name(resolved_endpoint)
        output_path = os.path.join(
            output_folder, f"{stem}_selfie_{model_short}_{actual_seed}.png"
        )
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(
                output_folder, f"{stem}_selfie_{model_short}_{actual_seed}_{counter}.png"
            )
            counter += 1

        self._report("Downloading result...", "download")
        if fal_download_file(image_url_result, output_path, self._progress_callback):
            self._report(f"Saved: {os.path.basename(output_path)}", "success")
            return output_path

        self._report("Download failed", "error")
        return None
