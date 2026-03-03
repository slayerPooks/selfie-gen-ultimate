"""Outpaint (expand) images using fal.ai outpaint API."""

import os
import logging
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class OutpaintGenerator:
    """Expand images using fal.ai outpaint."""

    ENDPOINT = "fal-ai/image-apps-v2/outpaint"

    def __init__(self, api_key: str, freeimage_key: Optional[str] = None):
        self.api_key = api_key
        self._freeimage_key = freeimage_key
        self._progress_callback: Optional[Callable[[str, str], None]] = None

    def set_progress_callback(self, cb: Callable[[str, str], None]):
        self._progress_callback = cb

    def _report(self, msg: str, level: str = "info"):
        if self._progress_callback:
            self._progress_callback(msg, level)

    def outpaint(
        self,
        image_path: str,
        output_folder: str,
        expand_left: int = 140,
        expand_right: int = 140,
        expand_top: int = 140,
        expand_bottom: int = 140,
        prompt: str = "",
        output_format: str = "png",
    ) -> Optional[str]:
        """Outpaint (expand) an image.

        Args:
            image_path: Path to input image
            output_folder: Where to save output
            expand_left: Pixels to expand on the left
            expand_right: Pixels to expand on the right
            expand_top: Pixels to expand on the top
            expand_bottom: Pixels to expand on the bottom
            prompt: Optional guidance prompt
            output_format: Output format ("png" or "jpg")

        Returns:
            Absolute path to expanded image, or None on failure.
        """
        from fal_utils import (
            upload_to_freeimage,
            fal_queue_submit,
            fal_queue_poll,
            fal_download_file,
        )

        # Upload image (use higher max_size for outpainting — preserve more detail)
        self._report("Uploading image for outpainting...", "upload")
        image_url = upload_to_freeimage(
            image_path, max_size=2048, progress_cb=self._progress_callback,
            api_key=self._freeimage_key,
        )
        if not image_url:
            self._report("Failed to upload image", "error")
            return None

        # Build payload
        payload = {
            "image_url": image_url,
            "expand_left": expand_left,
            "expand_right": expand_right,
            "expand_top": expand_top,
            "expand_bottom": expand_bottom,
            "num_images": 1,
            "output_format": output_format,
        }
        if prompt.strip():
            payload["prompt"] = prompt.strip()

        self._report(
            f"Submitting outpaint (L={expand_left} R={expand_right} "
            f"T={expand_top} B={expand_bottom})...",
            "task",
        )

        # Submit to queue
        result = fal_queue_submit(
            self.api_key, self.ENDPOINT, payload, self._progress_callback
        )
        if not result:
            self._report("Failed to submit outpaint job", "error")
            return None

        status_url = result.get("status_url")
        if not status_url:
            self._report("No status URL in response", "error")
            return None

        self._report("Waiting for outpaint...", "progress")
        final = fal_queue_poll(self.api_key, status_url, self._progress_callback)
        if not final:
            self._report("Outpaint failed or timed out", "error")
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
        ext = f".{output_format}"
        output_path = os.path.join(output_folder, f"{stem}_outpaint{ext}")
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(
                output_folder, f"{stem}_outpaint_{counter}{ext}"
            )
            counter += 1

        self._report("Downloading result...", "download")
        if fal_download_file(image_url_result, output_path, self._progress_callback):
            self._report(f"Saved: {os.path.basename(output_path)}", "success")
            return output_path

        self._report("Download failed", "error")
        return None
