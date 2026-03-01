"""Generate selfie-style portraits using fal.ai FLUX PuLID."""

import os
import random
import logging
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class SelfieGenerator:
    """Generate selfie images using FLUX PuLID via fal.ai queue API."""

    ENDPOINT = "fal-ai/flux-pulid"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._progress_callback: Optional[Callable[[str, str], None]] = None

    def set_progress_callback(self, cb: Callable[[str, str], None]):
        self._progress_callback = cb

    def _report(self, msg: str, level: str = "info"):
        if self._progress_callback:
            self._progress_callback(msg, level)

    def generate(
        self,
        image_path: str,
        prompt: str,
        output_folder: str,
        id_weight: float = 0.8,
        width: int = 896,
        height: int = 1152,
        seed: int = -1,
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
            image_path, progress_cb=self._progress_callback
        )
        if not image_url:
            self._report("Failed to upload image", "error")
            return None

        # Resolve seed
        actual_seed = random.randint(0, 2**32 - 1) if seed == -1 else seed

        # Build payload
        payload = {
            "prompt": prompt,
            "reference_images": [{"url": image_url}],
            "id_weight": id_weight,
            "width": width,
            "height": height,
            "seed": actual_seed,
            "num_images": 1,
        }

        self._report(f"Submitting to FLUX PuLID (seed={actual_seed})...", "task")

        # Submit to queue
        result = fal_queue_submit(
            self.api_key, self.ENDPOINT, payload, self._progress_callback
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
        output_path = os.path.join(output_folder, f"{stem}_selfie_{actual_seed}.png")
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(
                output_folder, f"{stem}_selfie_{actual_seed}_{counter}.png"
            )
            counter += 1

        self._report("Downloading result...", "download")
        if fal_download_file(image_url_result, output_path, self._progress_callback):
            self._report(f"Saved: {os.path.basename(output_path)}", "success")
            return output_path

        self._report("Download failed", "error")
        return None
