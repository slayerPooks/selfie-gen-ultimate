import os
import time
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import requests
import logging
from PIL import Image
import io
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import traceback
from datetime import datetime

from model_schema_manager import ModelSchemaManager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FalAIKlingGenerator:
    def __init__(
        self,
        api_key: str,
        verbose: bool = True,
        model_endpoint: Optional[str] = None,
        model_display_name: Optional[str] = None,
        prompt_slot: int = 1,
    ):
        self.api_key = api_key
        self.verbose = verbose

        # Initialize schema manager for dynamic parameter detection
        self.schema_manager = ModelSchemaManager(api_key)

        # Store model display name for logging
        self.model_display_name = model_display_name or "Kling 2.1 Professional"

        # Store prompt slot for filename generation
        self.prompt_slot = prompt_slot

        # Configurable model endpoint - defaults to Kling 2.1 Professional
        if model_endpoint:
            self.base_url = f"https://queue.fal.run/{model_endpoint}"
            self.model_endpoint = model_endpoint
        else:
            self.base_url = (
                "https://queue.fal.run/fal-ai/kling-video/v2.1/pro/image-to-video"
            )
            self.model_endpoint = "fal-ai/kling-video/v2.1/pro/image-to-video"

        # Freeimage.host guest API key
        self.freeimage_key = os.getenv(
            "FREEIMAGE_API_KEY", "6d207e02198a847aa98d0a2a901485a5"
        )

        # Default prompt for head movement
        self.default_prompt = (
            "Turn head to the right slowly then all the way to the left slowly then to the right slowly, and to the left slowly. "
            "Make sure the body is kept still while doing this - ONLY turn THE HEAD NOT THE BODY. The subject should perform smooth, "
            "natural head movements with no body movement whatsoever. Keep shoulders, neck, and torso completely stationary. "
            "Head movements should be slow, deliberate, and realistic. Eyes can follow natural movement patterns. "
            "Maintain neutral facial expression throughout. Camera remains fixed and stationary. "
            "Generate in maximum resolution and professional quality with no blur, pixelation, or quality degradation."
        )

        # Downloads folder
        self.downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")

        # Progress callback for GUI verbose mode
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set a callback for progress updates (used by GUI verbose mode)."""
        self._progress_callback = callback

    def update_model(self, model_endpoint: str, model_display_name: str):
        """Update the model endpoint and display name.

        Called when user changes model in GUI settings.
        """
        self.model_display_name = model_display_name or "Kling 2.1 Professional"
        if model_endpoint:
            self.base_url = f"https://queue.fal.run/{model_endpoint}"
            self.model_endpoint = model_endpoint
        else:
            self.base_url = (
                "https://queue.fal.run/fal-ai/kling-video/v2.1/pro/image-to-video"
            )
            self.model_endpoint = "fal-ai/kling-video/v2.1/pro/image-to-video"

    def update_prompt_slot(self, slot: int):
        """Update the current prompt slot.

        Called when user changes prompt slot in GUI settings.
        """
        self.prompt_slot = slot

    def get_model_short_name(self) -> str:
        """Get a short identifier for the current model based on the endpoint.

        Used in video filenames to indicate which model was used.
        Examples:
            fal-ai/kling-video/v2.1/pro/image-to-video -> k21pro
            fal-ai/kling-video/v2.5-turbo/pro/image-to-video -> k25turbo
            fal-ai/wan-25-preview/image-to-video -> wan25
            fal-ai/veo3/image-to-video -> veo3
        """
        endpoint = self.model_endpoint.lower()

        # Common model mappings
        if "kling" in endpoint:
            # Extract version info
            if "v2.5-turbo" in endpoint or "v2.5turbo" in endpoint:
                return "k25turbo"
            elif "v2.5" in endpoint:
                return "k25"
            elif "v2.1/master" in endpoint:
                return "k21master"
            elif "v2.1" in endpoint:
                return "k21pro"
            elif "o1" in endpoint:
                return "kO1"
            else:
                return "kling"
        elif "wan" in endpoint:
            if "25" in endpoint:
                return "wan25"
            return "wan"
        elif "veo3" in endpoint:
            return "veo3"
        elif "veo" in endpoint:
            return "veo"
        elif "ovi" in endpoint:
            return "ovi"
        elif "ltx" in endpoint:
            return "ltx2"
        elif "pixverse" in endpoint:
            if "v5" in endpoint:
                return "pix5"
            return "pixverse"
        elif "hunyuan" in endpoint:
            return "hunyuan"
        elif "minimax" in endpoint:
            return "minimax"
        else:
            # Fallback: extract last meaningful segment
            parts = endpoint.replace("/image-to-video", "").split("/")
            for part in reversed(parts):
                if part and part != "fal-ai":
                    # Clean up and truncate
                    clean = part.replace("-", "").replace("_", "")[:8]
                    return clean
            return "video"

    def sanitize_prompt_description(self, prompt_text: str, max_length: int = 35) -> str:
        """Extract a clean filename-safe description from prompt text.

        Takes first 3-5 meaningful words, removes special chars,
        converts spaces to underscores.

        Args:
            prompt_text: The full prompt text to extract from
            max_length: Maximum length for the resulting description (default 35)

        Returns:
            Cleaned filename-safe string like "Generate_lifelike_video_animation"

        Examples:
            "Generate a lifelike video animation..." → "Generate_lifelike_video_animation"
            "Turn head to the right slowly..." → "Turn_head_right_slowly"
            "Framing: medium shot, head and upper torso visible" → "medium_shot_head_upper_torso"
        """
        if not prompt_text:
            return "prompt"

        # Take first sentence or first 100 chars
        text = prompt_text[:100].split('.')[0].strip()

        # Remove common formatting prefixes
        prefixes_to_remove = [
            "Framing:", "Camera:", "Subject:", "Action:", "Movement:",
            "Generate", "Create", "Make", "The subject should", "This should"
        ]
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Split into words
        words = text.split()

        # Filter out common filler words
        filler_words = {'a', 'an', 'the', 'with', 'from', 'to', 'and', 'or', 'of', 'in', 'on', 'at', 'by'}
        meaningful_words = [w for w in words if w.lower() not in filler_words]

        # Take first 3-5 meaningful words (or all if less)
        selected_words = meaningful_words[:5] if len(meaningful_words) >= 3 else words[:5]

        # Join with underscores
        description = '_'.join(selected_words)

        # Remove special characters except underscores and dashes
        description = ''.join(c if c.isalnum() or c in ('_', '-') else '' for c in description)

        # Truncate to max length
        if len(description) > max_length:
            description = description[:max_length].rstrip('_-')

        return description if description else "prompt"

    def get_output_filename(
        self,
        image_stem: str,
        config: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """Generate enhanced filename with model, prompt info, and date.

        Format: {image}-{Model_Name}-{prompt_shorthand}-p{slot}-YYYY-MM-DD.mp4

        Args:
            image_stem: Image filename without extension (e.g., 'selfie')
            config: Config dict containing prompt_titles and saved_prompts
            timestamp: Generation start time (defaults to now)

        Returns:
            Filename like: Selfie-Kling_V2.5_Turbo_Pro-Left_Right_1-2-3-4-5-6-p3-2026-01-17.mp4

        Examples:
            With prompt shorthand:
                "Selfie-Kling_V2.5_Turbo_Pro-Left_Right_1-2-3-4-5-6-p3-2026-01-17.mp4"
            Without shorthand (fallback to prompt text extraction):
                "Portrait-Kling_V2.5_Turbo_Pro-Turn_head_right_slowly-p1-2026-01-17.mp4"
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Default config if not provided
        if config is None:
            config = {}
            logger.debug(" get_output_filename called with config=None, using empty dict")

        logger.debug(f" get_output_filename inputs:")
        logger.info(f"  image_stem: {image_stem}")
        logger.info(f"  config keys: {config.keys() if config else 'None'}")
        logger.info(f"  timestamp: {timestamp}")
        logger.info(f"  model_display_name: {self.model_display_name}")

        # 1. Model name: spaces to underscores
        model_name = self.model_display_name.replace(" ", "_")

        # 2. Prompt info: try shorthand first, fallback to description
        slot_str = str(self.prompt_slot)
        prompt_titles = config.get("prompt_titles", {})

        if slot_str in prompt_titles and prompt_titles[slot_str]:
            # Use shorthand from prompt_titles and sanitize it
            shorthand = prompt_titles[slot_str]
            # Replace spaces with underscores, remove special chars except _ and -
            prompt_part = ''.join(
                c if c.isalnum() or c in ('_', '-', ' ') else ''
                for c in shorthand
            ).replace(" ", "_")
        else:
            # Fallback: extract from prompt text
            saved_prompts = config.get("saved_prompts", {})
            prompt_text = saved_prompts.get(slot_str, "")
            if prompt_text:
                prompt_part = self.sanitize_prompt_description(prompt_text)
            else:
                prompt_part = "prompt"  # Ultimate fallback

        # 3. Date: YYYY-MM-DD format (ISO 8601 for international compatibility)
        date_str = timestamp.strftime("%Y-%m-%d")

        # 4. Build filename
        return f"{image_stem}-{model_name}-{prompt_part}-p{self.prompt_slot}-{date_str}.mp4"

    def _report_progress(self, message: str, level: str = "info"):
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(message, level)

    def upload_to_freeimage(self, image_path: str) -> Optional[str]:
        """Upload image to freeimage.host"""
        try:
            img = Image.open(image_path)

            # Resize if needed
            max_size = 1200
            if img.width > max_size or img.height > max_size:
                if self.verbose:
                    logger.info(f"Resizing from {img.width}x{img.height}")
                self._report_progress(
                    f"Resizing from {img.width}x{img.height}", "resize"
                )
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert to RGB
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(
                    img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
                )
                img = background

            # Compress to JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

            if self.verbose:
                logger.info(f"Uploading {Path(image_path).name} to freeimage.host...")
            self._report_progress(
                f"Uploading {Path(image_path).name} to freeimage.host...", "upload"
            )

            response = requests.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": self.freeimage_key,
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
                    if self.verbose:
                        logger.info(f"✓ Uploaded: {url}")
                    self._report_progress(f"✓ Uploaded: {url}", "upload")
                    return url

            logger.error(f"Upload failed: {response.status_code}")
            return None

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return None

    def check_duplicate_exists(
        self, image_path: str, output_folder: Optional[str] = None
    ) -> bool:
        """Check if video already exists in the target output folder"""
        try:
            char_name = Path(image_path).stem
            # Use provided output folder, or default to downloads folder
            target_folder = output_folder if output_folder else self.downloads_folder
            # Use new filename format with model and prompt slot
            output_filename = self.get_output_filename(char_name)
            output_path = Path(target_folder) / output_filename
            return output_path.exists()
        except Exception:
            return False

    def get_genx_image_files(
        self,
        folder_path: str,
        use_source_folder: bool = False,
        fallback_output_folder: Optional[str] = None,
    ) -> List[str]:
        """Get GenX images excluding duplicates

        Args:
            folder_path: Path to scan for images
            use_source_folder: If True, check for duplicates in source folder (image's parent)
            fallback_output_folder: Output folder to check for duplicates when use_source_folder=False
        """
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".webp",
            ".tiff",
            ".tif",
        }
        genx_images = []

        try:
            for file_path in Path(folder_path).iterdir():
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in image_extensions
                    and "genx" in file_path.name.lower()
                ):
                    # Determine output folder for duplicate check
                    if use_source_folder:
                        check_folder = str(file_path.parent)
                    else:
                        check_folder = fallback_output_folder

                    if not self.check_duplicate_exists(str(file_path), check_folder):
                        genx_images.append(str(file_path))
                    elif self.verbose:
                        logger.info(f"Skipping duplicate: {file_path.name}")
        except Exception as e:
            if self.verbose:
                logger.error(f"Error getting GenX files: {e}")

        return genx_images

    def create_kling_generation(
        self,
        character_image_path: str,
        output_folder: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        use_source_folder: bool = False,
        skip_duplicate_check: bool = False,
        duration: int = 10,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        seed: int = -1,
        camera_fixed: bool = False,
        generate_audio: bool = False,
        end_image_url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[str]:
        """Create Kling video via fal.ai

        Args:
            character_image_path: Path to source image
            output_folder: Fallback output folder (used when use_source_folder=False)
            custom_prompt: Custom generation prompt
            negative_prompt: Negative prompt for content to avoid (model-dependent)
            use_source_folder: If True, save video in same folder as source image
            skip_duplicate_check: If True, skip duplicate detection (for reprocessing)
            duration: Video duration in seconds (default 10, some models support 5 or 6)
            aspect_ratio: Aspect ratio string (21:9, 16:9, 4:3, 1:1, 3:4, 9:16)
            resolution: Resolution string (480p, 720p)
            seed: Random seed (-1 for random)
            camera_fixed: Whether camera should be fixed/stationary
            generate_audio: Whether to generate audio
            end_image_url: Optional last frame image URL for interpolation
            config: Config dict containing prompt_titles and saved_prompts (for enhanced filenames)
            timestamp: Generation start time for consistent filenames (defaults to now)
        """
        try:
            # Determine actual output folder
            if use_source_folder:
                actual_output_folder = str(Path(character_image_path).parent)
            elif output_folder is not None:
                actual_output_folder = output_folder
            else:
                actual_output_folder = self.downloads_folder

            if not skip_duplicate_check and self.check_duplicate_exists(
                character_image_path, actual_output_folder
            ):
                if self.verbose:
                    logger.info(
                        f"Skipping {Path(character_image_path).name} - already exists"
                    )
                return None

            # Upload image
            image_url = self.upload_to_freeimage(character_image_path)
            if not image_url:
                logger.error("Failed to upload image")
                return None

            # Prepare prompt
            prompt = custom_prompt if custom_prompt else self.default_prompt

            # Truncate prompt if it exceeds API limit (2500 characters)
            MAX_PROMPT_LENGTH = 2500
            if len(prompt) > MAX_PROMPT_LENGTH:
                original_length = len(prompt)
                prompt = prompt[:MAX_PROMPT_LENGTH]
                if self.verbose:
                    logger.warning(
                        f"⚠ Prompt truncated from {original_length} to {MAX_PROMPT_LENGTH} characters (API limit)"
                    )
                self._report_progress(
                    f"⚠ Prompt truncated to {MAX_PROMPT_LENGTH} chars", "warning"
                )

            # fal.ai API request
            headers = {
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            }

            # Status check headers (no Content-Type for GET requests)
            status_headers = {"Authorization": f"Key {self.api_key}"}

            # Build full payload with ALL possible parameters
            payload_full: Dict[str, Any] = {
                "image_url": image_url,
                "prompt": prompt,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
            }

            # Add optional parameters if they differ from defaults or are explicitly set
            if resolution:
                payload_full["resolution"] = resolution

            if seed >= 0:
                payload_full["seed"] = seed

            if camera_fixed:
                payload_full["camera_fixed"] = True

            if generate_audio:
                payload_full["generate_audio"] = True

            if end_image_url:
                payload_full["end_image_url"] = end_image_url

            if negative_prompt:
                payload_full["negative_prompt"] = negative_prompt

            # Validate and filter parameters based on model schema (dynamic detection)
            payload = self.schema_manager.validate_parameters(
                self.model_endpoint,
                payload_full
            )

            if self.verbose:
                # Show which parameters were filtered out
                removed = set(payload_full.keys()) - set(payload.keys())
                if removed:
                    logger.info(f"Filtered unsupported parameters: {removed}")
                logger.info(f"Sending parameters: {list(payload.keys())}")

            if self.verbose:
                logger.info(f"Creating {self.model_display_name} video via fal.ai...")
                logger.info(f"Image: {Path(character_image_path).name}")
                logger.info(f"Duration: {duration} seconds")
                logger.info(f"Endpoint: {self.base_url}")

            # Submit request with retry logic
            max_submit_retries = 3
            request_id = None
            status_url = None

            for submit_attempt in range(max_submit_retries):
                try:
                    response = requests.post(
                        self.base_url, headers=headers, json=payload, timeout=30
                    )

                    if response.status_code == 429:
                        logger.warning(
                            f"⚠ Rate limited - waiting before retry ({submit_attempt + 1}/{max_submit_retries})"
                        )
                        time.sleep(30)
                        continue

                    elif response.status_code == 503:
                        logger.warning(
                            f"⚠ Service unavailable - retrying ({submit_attempt + 1}/{max_submit_retries})"
                        )
                        time.sleep(10)
                        continue

                    elif response.status_code == 402:
                        logger.error(
                            "💳 Payment required - insufficient credits in your fal.ai account"
                        )
                        return None

                    elif response.status_code != 200:
                        logger.error(f"❌ Request failed: {response.status_code}")
                        logger.error(f"Response: {response.text}")
                        if submit_attempt < max_submit_retries - 1:
                            logger.info(
                                f"Retrying... ({submit_attempt + 1}/{max_submit_retries})"
                            )
                            time.sleep(5)
                            continue
                        return None

                    result = response.json()
                    request_id = result.get("request_id")
                    status_url = result.get(
                        "status_url"
                    )  # Get the status URL from response

                    if not request_id or not status_url:
                        logger.error("✗ No request ID or status URL returned")
                        if submit_attempt < max_submit_retries - 1:
                            time.sleep(5)
                            continue
                        return None

                    # Success!
                    break

                except requests.exceptions.Timeout:
                    logger.warning(
                        f"⚠ Request timeout ({submit_attempt + 1}/{max_submit_retries})"
                    )
                    if submit_attempt < max_submit_retries - 1:
                        time.sleep(10)
                        continue
                    logger.error("✗ Failed to submit request after timeouts")
                    return None

                except requests.exceptions.ConnectionError as e:
                    logger.warning(
                        f"⚠ Connection error: {e} ({submit_attempt + 1}/{max_submit_retries})"
                    )
                    if submit_attempt < max_submit_retries - 1:
                        time.sleep(10)
                        continue
                    logger.error("✗ Failed to submit request due to connection errors")
                    return None

                except Exception as e:
                    logger.error(f"✗ Unexpected error during submission: {e}")
                    if submit_attempt < max_submit_retries - 1:
                        time.sleep(5)
                        continue
                    return None

            if not request_id:
                logger.error("✗ Failed to get request ID after all retries")
                return None

            if not status_url:
                logger.error("✗ Failed to get status URL after all retries")
                return None

            if self.verbose:
                logger.info(f"✓ Task created: {request_id}")
                logger.info("Waiting for video generation...")
            self._report_progress(f"✓ Task created: {request_id}", "task")
            self._report_progress("Waiting for video generation...", "progress")

            # Poll for completion with exponential backoff
            # Use the status_url provided by fal.ai (already authenticated)
            max_attempts = 240  # 20 minutes total (increased from 15)
            attempt = 0
            consecutive_errors = 0
            max_consecutive_errors = 10

            # Exponential backoff settings
            base_delay = 5
            max_delay = 30

            logger.debug(f" Starting polling loop. Max attempts: {max_attempts}, status_url: {status_url}")

            while attempt < max_attempts:
                # Calculate delay with exponential backoff
                if attempt < 24:  # First 2 minutes: 5 second polls
                    delay = base_delay
                elif attempt < 60:  # Next 3 minutes: 10 second polls
                    delay = 10
                else:  # After 5 minutes: 15 second polls
                    delay = 15

                time.sleep(delay)
                attempt += 1

                logger.debug(f" Polling attempt {attempt}/{max_attempts}, delay: {delay}s")

                # Show progress every minute
                if attempt % (60 // base_delay) == 0:
                    elapsed_mins = (attempt * base_delay) // 60
                    if self.verbose:
                        logger.info(
                            f"⏳ Still waiting... {elapsed_mins} min elapsed (attempt {attempt}/{max_attempts})"
                        )
                    self._report_progress(
                        f"⏳ Still waiting... {elapsed_mins} min elapsed", "progress"
                    )

                try:
                    # fal.ai status endpoint requires Authorization header
                    status_response = requests.get(
                        status_url, headers=status_headers, timeout=30
                    )

                    # Handle different HTTP status codes
                    if status_response.status_code == 404:
                        logger.error(
                            f"✗ Job not found (404) - request may have expired"
                        )
                        return None
                    elif status_response.status_code == 429:
                        if self.verbose:
                            logger.warning(
                                "⚠ Rate limited - waiting longer before retry"
                            )
                        time.sleep(30)
                        continue
                    elif status_response.status_code == 503:
                        if self.verbose:
                            logger.warning(
                                "⚠ Service unavailable - fal.ai may be overloaded"
                            )
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(
                                f"✗ Too many service errors ({consecutive_errors}) - giving up"
                            )
                            return None
                        time.sleep(10)
                        continue
                    elif status_response.status_code not in [200, 202]:
                        if self.verbose:
                            logger.warning(
                                f"⚠ Unexpected status code: {status_response.status_code}"
                            )
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(
                                f"✗ Too many errors ({consecutive_errors}) - giving up"
                            )
                            return None
                        continue

                    # Reset error counter on success
                    consecutive_errors = 0

                    status_result = status_response.json()
                    status = status_result.get("status")

                    # Log queue position if available
                    queue_position = status_result.get("queue_position")
                    if queue_position and self.verbose and attempt % 6 == 0:
                        logger.info(f"📊 Queue position: {queue_position}")

                    if status == "IN_QUEUE":
                        if self.verbose and attempt % 12 == 0:
                            logger.info("⏳ Job is in queue, waiting...")
                        continue

                    elif status == "IN_PROGRESS":
                        if self.verbose and attempt % 12 == 0:
                            logger.info("🎬 Video is being generated...")
                        continue

                    elif status == "COMPLETED":
                        # Debug: log the full response to see structure
                        logger.debug(" Status: COMPLETED")
                        logger.debug(f" Full response keys: {list(status_result.keys())}")
                        logger.debug(f" Full response: {status_result}")

                        # Try multiple possible response structures
                        video_url = None

                        # Structure 1: output.video.url
                        if "output" in status_result:
                            logger.debug(" Trying Structure 1: output.video.url")
                            output_data = status_result.get("output", {})
                            logger.debug(f" output keys: {list(output_data.keys()) if isinstance(output_data, dict) else 'not a dict'}")
                            video_url = output_data.get("video", {}).get("url")
                            if video_url:
                                logger.debug(f" Found video URL in Structure 1: {video_url}")
                            else:
                                logger.debug(" No video URL in Structure 1")

                        # Structure 2: video.url
                        if not video_url and "video" in status_result:
                            logger.debug(" Trying Structure 2: video.url")
                            video_data = status_result.get("video", {})
                            logger.debug(f" video keys: {list(video_data.keys()) if isinstance(video_data, dict) else 'not a dict'}")
                            video_url = video_data.get("url")
                            if video_url:
                                logger.debug(f" Found video URL in Structure 2: {video_url}")
                            else:
                                logger.debug(" No video URL in Structure 2")

                        # Structure 3: data.video.url
                        if not video_url and "data" in status_result:
                            logger.debug(" Trying Structure 3: data.video.url")
                            data_obj = status_result.get("data", {})
                            logger.debug(f" data keys: {list(data_obj.keys()) if isinstance(data_obj, dict) else 'not a dict'}")
                            video_url = data_obj.get("video", {}).get("url")
                            if video_url:
                                logger.debug(f" Found video URL in Structure 3: {video_url}")
                            else:
                                logger.debug(" No video URL in Structure 3")

                        # Structure 4: response_url might contain the result
                        if not video_url and "response_url" in status_result:
                            response_url = status_result.get("response_url")
                            if self.verbose:
                                logger.info(
                                    f"Fetching result from response_url: {response_url}"
                                )
                            try:
                                logger.debug(f" Fetching from response_url with headers: {status_headers}")
                                result_response = requests.get(
                                    response_url, headers=status_headers, timeout=30
                                )
                                logger.debug(f" Response status code: {result_response.status_code}")
                                logger.debug(f" Response text (first 1000 chars): {result_response.text[:1000]}")
                                if result_response.status_code == 200:
                                    result_data = result_response.json()
                                    logger.debug(f" Parsed JSON successfully")
                                    if self.verbose:
                                        logger.info(
                                            f"DEBUG - Result data keys: {list(result_data.keys())}"
                                        )
                                        logger.info(
                                            f"DEBUG - Result data: {result_data}"
                                        )

                                    # Check for errors in result data (API validation errors)
                                    if "error" in result_data:
                                        logger.error(
                                            f"❌ API Error: {result_data['error']}"
                                        )
                                        return None
                                    if "detail" in result_data:
                                        # Parse validation errors like duration invalid
                                        detail = result_data["detail"]
                                        if isinstance(detail, list):
                                            for err in detail:
                                                msg = err.get("msg", str(err))
                                                loc = err.get("loc", [])
                                                logger.error(
                                                    f"❌ Validation Error: {msg} (field: {loc})"
                                                )
                                        else:
                                            logger.error(f"❌ API Detail: {detail}")
                                        return None

                                    # Try all structures in result_data
                                    logger.debug(" Extracting video URL from result_data")
                                    video_url = result_data.get("video", {}).get("url")
                                    if video_url:
                                        logger.debug(f" Found video URL in result_data.video.url: {video_url}")

                                    if not video_url:
                                        video_url = (
                                            result_data.get("output", {})
                                            .get("video", {})
                                            .get("url")
                                        )
                                        if video_url:
                                            logger.debug(f" Found video URL in result_data.output.video.url: {video_url}")

                                    if not video_url:
                                        video_url = (
                                            result_data.get("data", {})
                                            .get("video", {})
                                            .get("url")
                                        )
                                        if video_url:
                                            logger.debug(f" Found video URL in result_data.data.video.url: {video_url}")
                                else:
                                    logger.debug(f" Non-200 status from response_url: {result_response.status_code}")
                                    logger.debug(f" Response text: {result_response.text[:1000]}")

                            except Exception as e:
                                if self.verbose:
                                    logger.warning(
                                        f"Failed to fetch from response_url: {e}"
                                    )

                        if not video_url:
                            logger.debug("No video URL found after checking all structures")
                            logger.debug(f" status_result keys: {list(status_result.keys())}")
                            logger.debug(f" status_result: {status_result}")
                            logger.error("✗ No video URL in response")
                            logger.error("✗ Checked structures: output.video.url, video.url, data.video.url, response_url")
                            return None

                        if self.verbose:
                            logger.info(f"✓ Video ready: {video_url}")
                        self._report_progress(
                            f"✓ Video ready - downloading...", "download"
                        )

                        # Download video with retry logic
                        max_download_retries = 3
                        for download_attempt in range(max_download_retries):
                            try:
                                video_response = requests.get(video_url, timeout=120)
                                if video_response.status_code != 200:
                                    if download_attempt < max_download_retries - 1:
                                        logger.warning(
                                            f"⚠ Download failed (attempt {download_attempt + 1}/{max_download_retries})"
                                        )
                                        time.sleep(5)
                                        continue
                                    else:
                                        logger.error(
                                            f"✗ Failed to download after {max_download_retries} attempts: {video_response.status_code}"
                                        )
                                        return None

                                # Save video with enhanced filename (model, prompt, date)
                                char_name = Path(character_image_path).stem

                                # DEBUG: Log parameters before filename generation
                                logger.debug(f" About to generate filename:")
                                logger.info(f"  char_name: {char_name}")
                                logger.info(f"  config type: {type(config)}, value: {config}")
                                logger.info(f"  timestamp type: {type(timestamp)}, value: {timestamp}")
                                logger.info(f"  model_display_name: {self.model_display_name}")
                                logger.info(f"  prompt_slot: {self.prompt_slot}")

                                try:
                                    output_filename = self.get_output_filename(
                                        char_name, config, timestamp
                                    )
                                    logger.debug(f" Generated filename: {output_filename}")
                                except Exception as e:
                                    logger.error(f"✗ Filename generation failed: {e}")
                                    logger.error(f"✗ Traceback:\n{traceback.format_exc()}")
                                    raise
                                output_path = (
                                    Path(actual_output_folder) / output_filename
                                )

                                with open(output_path, "wb") as f:
                                    f.write(video_response.content)

                                file_size = output_path.stat().st_size / (1024 * 1024)
                                total_time = attempt * base_delay
                                if self.verbose:
                                    logger.info(f"✓ Video saved: {output_path}")
                                    logger.info(f"✓ File size: {file_size:.2f} MB")
                                    logger.info(
                                        f"✓ Total generation time: {total_time // 60}m {total_time % 60}s"
                                    )
                                self._report_progress(
                                    f"✓ File size: {file_size:.2f} MB", "download"
                                )
                                self._report_progress(
                                    f"✓ Total generation time: {total_time // 60}m {total_time % 60}s",
                                    "success",
                                )

                                return str(output_path)

                            except Exception as download_error:
                                if download_attempt < max_download_retries - 1:
                                    logger.warning(
                                        f"⚠ Download error: {download_error} (retry {download_attempt + 1}/{max_download_retries})"
                                    )
                                    time.sleep(5)
                                else:
                                    logger.error(
                                        f"✗ Download failed after {max_download_retries} attempts: {download_error}"
                                    )
                                    return None

                    elif status in ["FAILED", "ERROR"]:
                        error_msg = status_result.get("error", "Unknown error")
                        logger.error(f"✗ Generation failed: {error_msg}")

                        # Check if it's a retriable error
                        if (
                            "quota" in error_msg.lower()
                            or "credit" in error_msg.lower()
                        ):
                            logger.error(
                                "💳 Insufficient credits - please add more credits to your fal.ai account"
                            )
                        elif "timeout" in error_msg.lower():
                            logger.error(
                                "⏱️ Server timeout - fal.ai may be overloaded, try again later"
                            )

                        return None

                    elif status == "CANCELLED":
                        logger.error("✗ Job was cancelled")
                        return None

                except requests.exceptions.Timeout:
                    if self.verbose:
                        logger.warning(f"⚠ Request timeout (attempt {attempt})")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"✗ Too many timeouts - giving up")
                        return None
                    continue

                except requests.exceptions.ConnectionError:
                    if self.verbose:
                        logger.warning(f"⚠ Connection error - retrying")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"✗ Too many connection errors - giving up")
                        return None
                    time.sleep(10)
                    continue

                except Exception as e:
                    if self.verbose and attempt % 12 == 0:
                        logger.warning(f"⚠ Status check error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"✗ Too many errors - giving up")
                        return None
                    continue

            # Timeout reached
            logger.error(f"✗ Timeout after {max_attempts * base_delay // 60} minutes")
            logger.error("💡 Possible causes:")
            logger.error(
                "   - fal.ai servers are overloaded (try again during off-peak hours)"
            )
            logger.error("   - Job stuck in queue (check fal.ai dashboard)")
            logger.error("   - Network connectivity issues")
            return None

        except Exception as e:
            logger.error(f"✗ Error: {str(e)}")
            logger.error(f"✗ Full traceback:\n{traceback.format_exc()}")
            return None

    def process_all_images_concurrent(
        self,
        target_directory: str,
        output_directory: Optional[str] = None,
        max_workers: int = 5,
        custom_prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        use_source_folder: bool = False,
        duration: int = 10,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        seed: int = -1,
        camera_fixed: bool = False,
        generate_audio: bool = False,
    ):
        """Process all GenX images concurrently

        Args:
            target_directory: Input directory or file path
            output_directory: Fallback output directory (used when use_source_folder=False)
            max_workers: Maximum concurrent workers
            custom_prompt: Custom generation prompt
            negative_prompt: Negative prompt for content to avoid
            progress_callback: Progress callback function
            use_source_folder: If True, save each video alongside its source image
            duration: Video duration in seconds
            aspect_ratio: Aspect ratio string
            resolution: Resolution string (480p, 720p)
            seed: Random seed (-1 for random)
            camera_fixed: Whether camera should be fixed
            generate_audio: Whether to generate audio
        """
        if output_directory is None:
            output_directory = self.downloads_folder

        if self.verbose:
            logger.info(f"Scanning: {target_directory}")
            logger.info(f"Max workers: {max_workers}")
            if use_source_folder:
                logger.info("Output mode: Videos saved alongside source images")
            else:
                logger.info(f"Output folder: {output_directory}")

        # Collect all images
        all_images = []

        target_path = Path(target_directory)
        if target_path.is_file():
            # Single file mode - check for duplicate in appropriate location
            if use_source_folder:
                check_folder = str(target_path.parent)
            else:
                check_folder = output_directory
            if not self.check_duplicate_exists(str(target_path), check_folder):
                all_images.append(str(target_path))
            elif self.verbose:
                logger.info(f"Skipping duplicate: {target_path.name}")
        else:
            # Root directory
            genx_images = self.get_genx_image_files(
                target_directory, use_source_folder, output_directory
            )
            all_images.extend(genx_images)

            # Subdirectories
            try:
                for folder_path in Path(target_directory).iterdir():
                    if folder_path.is_dir():
                        genx_images = self.get_genx_image_files(
                            str(folder_path), use_source_folder, output_directory
                        )
                        all_images.extend(genx_images)
            except Exception as e:
                if self.verbose:
                    logger.error(f"Error: {e}")

        total_images = len(all_images)
        if total_images == 0:
            if self.verbose:
                logger.info("No GenX images found")
            return

        if self.verbose:
            logger.info(f"Found {total_images} GenX images")
            logger.info("Starting concurrent processing...")

        videos_created = 0
        videos_skipped = 0
        lock = threading.Lock()

        def process_image(image_path):
            nonlocal videos_created, videos_skipped

            image_name = Path(image_path).name

            if progress_callback:
                with lock:
                    progress_callback(
                        videos_created + videos_skipped,
                        total_images,
                        f"Generating: {image_name}",
                    )

            try:
                result = self.create_kling_generation(
                    character_image_path=image_path,
                    output_folder=output_directory,
                    custom_prompt=custom_prompt,
                    negative_prompt=negative_prompt,
                    use_source_folder=use_source_folder,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    seed=seed,
                    camera_fixed=camera_fixed,
                    generate_audio=generate_audio,
                )

                with lock:
                    if result:
                        videos_created += 1
                        if progress_callback:
                            progress_callback(
                                videos_created + videos_skipped,
                                total_images,
                                f"Completed: {image_name}",
                            )
                    else:
                        videos_skipped += 1
                        if progress_callback:
                            progress_callback(
                                videos_created + videos_skipped,
                                total_images,
                                f"Failed: {image_name}",
                            )

                return result
            except Exception as e:
                with lock:
                    videos_skipped += 1
                    if self.verbose:
                        logger.error(f"Error processing {image_name}: {e}")
                    if progress_callback:
                        progress_callback(
                            videos_created + videos_skipped,
                            total_images,
                            f"Failed: {image_name}",
                        )
                return None

        # Process concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_image, img): img for img in all_images}

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    if self.verbose:
                        logger.error(f"Unexpected error: {e}")

        # Summary
        if self.verbose:
            logger.info("\n" + "=" * 80)
            logger.info("PROCESSING COMPLETE")
            logger.info(f"Videos created: {videos_created}")
            logger.info(f"Videos skipped: {videos_skipped}")
            logger.info(f"Total processed: {videos_created + videos_skipped}")
            logger.info("=" * 80)
