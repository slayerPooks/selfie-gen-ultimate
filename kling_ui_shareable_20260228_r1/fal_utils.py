"""Shared fal.ai utilities: upload, queue submit, poll, download."""

import os
import time
import requests
import logging
from pathlib import Path
from typing import Optional, Callable
from PIL import Image
import io
import base64

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, str], None]]  # (message, level)

# Freeimage.host API key — env override, else public guest key
_FREEIMAGE_KEY = os.getenv("FREEIMAGE_API_KEY", "6d207e02198a847aa98d0a2a901485a5")


def upload_to_freeimage(
    image_path: str,
    max_size: int = 1200,
    progress_cb: ProgressCallback = None,
    api_key: Optional[str] = None,
) -> Optional[str]:
    """Upload image to freeimage.host, return public URL.

    Resizes image if larger than max_size on longest side.
    Converts transparent images to RGB JPEG before upload.
    Returns None on failure.

    Args:
        api_key: Explicit freeimage key. Falls back to FREEIMAGE_API_KEY env var.
    """
    key = api_key or _FREEIMAGE_KEY
    if not key:
        if progress_cb:
            progress_cb("FREEIMAGE_API_KEY not set — set via environment or config", "error")
        return None

    try:
        img = Image.open(image_path)
        img.load()  # Read pixel data into memory, releasing file handle

        # Resize if needed
        if img.width > max_size or img.height > max_size:
            if progress_cb:
                progress_cb(f"Resizing from {img.width}x{img.height}", "resize")
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Convert to RGB (handles RGBA, LA, P modes)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(
                img,
                mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None,
            )
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Compress to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        if progress_cb:
            progress_cb(
                f"Uploading {Path(image_path).name} to freeimage.host...", "upload"
            )

        response = requests.post(
            "https://freeimage.host/api/1/upload",
            data={
                "key": key,
                "action": "upload",
                "source": image_base64,
                "format": "json",
            },
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status_code") == 200:
                url = result["image"]["url"]
                if progress_cb:
                    progress_cb(f"Uploaded: {url}", "upload")
                return url

        logger.error("Upload failed: %s", response.status_code)
        if progress_cb:
            progress_cb(f"Upload failed: HTTP {response.status_code}", "error")
        return None

    except Exception as e:
        logger.error("Upload error: %s", e)
        if progress_cb:
            progress_cb(f"Upload error: {e}", "error")
        return None


def fal_queue_submit(
    api_key: str,
    endpoint: str,
    payload: dict,
    progress_cb: ProgressCallback = None,
) -> Optional[dict]:
    """Submit a job to fal.ai queue API.

    Returns dict with 'request_id' and 'status_url', or None on failure.
    Retries up to 3 times on transient errors.
    """
    url = f"https://queue.fal.run/{endpoint}"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 429:
                logger.warning("Rate limited — waiting 30 s before retry")
                if progress_cb:
                    progress_cb("Rate limited — waiting 30 s...", "warning")
                time.sleep(30)
                continue

            elif response.status_code == 503:
                logger.warning("Service unavailable — retrying")
                if progress_cb:
                    progress_cb(
                        f"Service unavailable, retrying ({attempt + 1}/{max_retries})...",
                        "warning",
                    )
                time.sleep(10)
                continue

            elif response.status_code == 402:
                logger.error("Payment required — insufficient fal.ai credits")
                if progress_cb:
                    progress_cb("Insufficient fal.ai credits", "error")
                return None

            elif response.status_code != 200:
                logger.error("Queue submit failed: %s — %s", response.status_code, response.text)
                if progress_cb:
                    progress_cb(f"Submit failed: HTTP {response.status_code}", "error")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None

            result = response.json()
            request_id = result.get("request_id")
            status_url = result.get("status_url")

            if not request_id or not status_url:
                logger.error("No request_id or status_url in response")
                if progress_cb:
                    progress_cb("No request_id/status_url in response", "error")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None

            if progress_cb:
                progress_cb(f"Task created: {request_id}", "task")
            return result

        except requests.exceptions.Timeout:
            logger.warning("Request timeout (attempt %d/%d)", attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            if progress_cb:
                progress_cb("Submit timed out", "error")
            return None

        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error: %s (attempt %d/%d)", e, attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            if progress_cb:
                progress_cb(f"Connection error: {e}", "error")
            return None

        except Exception as e:
            logger.error("Unexpected submit error: %s", e)
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            if progress_cb:
                progress_cb(f"Submit error: {e}", "error")
            return None

    return None


def fal_queue_poll(
    api_key: str,
    status_url: str,
    progress_cb: ProgressCallback = None,
) -> Optional[dict]:
    """Poll fal.ai queue until completion.

    Uses the same exponential backoff as kling_generator_falai.py:
      - First 2 min: 5 s polls
      - Next 3 min: 10 s polls
      - After 5 min: 15 s polls
    Max wait: 20 minutes (240 attempts at 5 s base).

    Returns the final result dict (output/data/images key) or None on failure.
    """
    status_headers = {"Authorization": f"Key {api_key}"}
    max_attempts = 240
    base_delay = 5
    consecutive_errors = 0
    max_consecutive_errors = 10
    start_time = time.monotonic()

    for attempt in range(1, max_attempts + 1):
        # Backoff schedule
        if attempt <= 24:
            delay = base_delay
        elif attempt <= 60:
            delay = 10
        else:
            delay = 15

        time.sleep(delay)

        # Periodic progress update
        if attempt % 12 == 0:
            elapsed = int((time.monotonic() - start_time) / 60)
            if progress_cb:
                progress_cb(f"Still waiting... {elapsed} min elapsed", "progress")

        try:
            resp = requests.get(status_url, headers=status_headers, timeout=30)

            if resp.status_code == 404:
                logger.error("Job not found (404) — request may have expired")
                if progress_cb:
                    progress_cb("Job not found (404)", "error")
                return None

            elif resp.status_code == 429:
                logger.warning("Rate limited during polling — waiting 30 s")
                time.sleep(30)
                continue

            elif resp.status_code == 503:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many service errors — giving up")
                    if progress_cb:
                        progress_cb("Too many service errors", "error")
                    return None
                time.sleep(10)
                continue

            elif resp.status_code not in (200, 202):
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many errors (%d) — giving up", consecutive_errors)
                    if progress_cb:
                        progress_cb(f"Too many errors, giving up", "error")
                    return None
                continue

            consecutive_errors = 0
            data = resp.json()
            status = data.get("status")

            if status in ("IN_QUEUE", "IN_PROGRESS"):
                continue

            elif status == "COMPLETED":
                if progress_cb:
                    progress_cb("Generation complete", "success")

                # Try to extract result — handle response_url indirection
                result = _extract_result(data, status_headers, progress_cb)
                return result

            elif status in ("FAILED", "ERROR"):
                error_msg = data.get("error", "Unknown error")
                logger.error("Generation failed: %s", error_msg)
                if progress_cb:
                    progress_cb(f"Generation failed: {error_msg}", "error")
                return None

            else:
                logger.debug("Unknown status: %s", status)

        except requests.exceptions.Timeout:
            logger.warning("Poll timeout on attempt %d", attempt)
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                if progress_cb:
                    progress_cb("Too many poll timeouts", "error")
                return None

        except Exception as e:
            logger.error("Poll error on attempt %d: %s", attempt, e)
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                if progress_cb:
                    progress_cb(f"Poll error: {e}", "error")
                return None

    logger.error("Polling timed out after %d attempts", max_attempts)
    if progress_cb:
        progress_cb("Polling timed out", "error")
    return None


def _extract_result(
    status_result: dict,
    status_headers: dict,
    progress_cb: ProgressCallback = None,
) -> Optional[dict]:
    """Extract the final result payload from a COMPLETED status response.

    Handles all the response structure variants seen in production:
    - output.video.url / output.images
    - video.url
    - data.video.url / data.images
    - response_url indirection (fetches the actual result)
    Returns the raw result dict so callers can inspect keys they care about.
    """
    # Structure 1: has an 'output' key
    if "output" in status_result:
        return status_result["output"]

    # Structure 2: direct video key
    if "video" in status_result or "images" in status_result:
        return status_result

    # Structure 3: has a 'data' key
    if "data" in status_result:
        return status_result["data"]

    # Structure 4: response_url indirection
    response_url = status_result.get("response_url")
    if response_url:
        if progress_cb:
            progress_cb("Fetching result from response_url...", "api")
        try:
            r = requests.get(response_url, headers=status_headers, timeout=30)
            if r.status_code == 200:
                result_data = r.json()
                # Check for API-level errors inside result
                if "error" in result_data:
                    logger.error("API error in response_url: %s", result_data["error"])
                    if progress_cb:
                        progress_cb(f"API error: {result_data['error']}", "error")
                    return None
                if "detail" in result_data:
                    detail = result_data["detail"]
                    if isinstance(detail, list):
                        for err in detail:
                            logger.error("Validation error: %s", err.get("msg", err))
                    else:
                        logger.error("API detail: %s", detail)
                    if progress_cb:
                        progress_cb("API validation error in result", "error")
                    return None
                return result_data
        except Exception as e:
            logger.warning("Failed to fetch response_url: %s", e)

    logger.error("Could not extract result from COMPLETED response")
    if progress_cb:
        progress_cb("Could not extract result from completed response", "error")
    return None


def fal_download_file(
    url: str,
    output_path: str,
    progress_cb: ProgressCallback = None,
) -> bool:
    """Download a file from URL to output_path using streaming.

    Returns True on success, False on failure.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=120) as resp:
                if resp.status_code != 200:
                    logger.warning(
                        "Download failed: HTTP %s (attempt %d/%d)",
                        resp.status_code, attempt + 1, max_retries,
                    )
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    if progress_cb:
                        progress_cb(
                            f"Download failed: HTTP {resp.status_code}", "error"
                        )
                    return False

                out_dir = os.path.dirname(os.path.abspath(output_path))
                os.makedirs(out_dir, exist_ok=True)
                tmp_path = output_path + ".tmp"
                try:
                    with open(tmp_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    os.replace(tmp_path, output_path)
                except BaseException:
                    # Clean up partial temp file on any failure
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    raise

            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            if progress_cb:
                progress_cb(f"Downloaded: {file_size_mb:.2f} MB", "download")
            logger.info("Downloaded %s (%.2f MB)", output_path, file_size_mb)
            return True

        except Exception as e:
            logger.warning(
                "Download error (attempt %d/%d): %s", attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            if progress_cb:
                progress_cb(f"Download error: {e}", "error")
            return False

    return False
