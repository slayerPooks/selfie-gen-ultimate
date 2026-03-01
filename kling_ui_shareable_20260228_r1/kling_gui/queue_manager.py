"""
Queue Manager - Thread-safe queue for processing images with status tracking.
"""

import threading
import os
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, List
from pathlib import Path
from datetime import datetime

from path_utils import VALID_EXTENSIONS

logger = logging.getLogger(__name__)


def get_output_video_path(
    image_path: str,
    output_folder: str,
    generator,
    config: dict = None,
    timestamp: Optional[datetime] = None,
) -> Path:
    """Get the output video path: {stem}_{model_short}_{index}.mp4

    The index is determined by scanning output_folder for existing files so
    each call returns the next available path for this image+model combination.
    """
    image_name = Path(image_path).stem
    filename = generator.get_output_filename(image_name, output_folder)
    return Path(output_folder) / filename


def check_video_exists(
    image_path: str,
    output_folder: str,
    generator,
    config: dict = None,
) -> tuple[bool, Optional[str]]:
    """Check if any video already exists for this image+model combination.

    Matches pattern: {stem}_{model_short}_*.mp4  (and *_looped.mp4 variant).

    Returns:
        (exists: bool, found_path: str | None)
    """
    import glob

    image_name = Path(image_path).stem
    model_short = generator.get_model_short_name()
    prompt_slot = (config or {}).get("current_prompt_slot", getattr(generator, "prompt_slot", 1))
    try:
        prompt_slot = max(1, int(prompt_slot))
    except (TypeError, ValueError):
        prompt_slot = 1

    slot_prefix = f"{image_name}_{model_short}_p{prompt_slot}_"
    slot_matches = sorted(glob.glob(str(Path(output_folder) / f"{slot_prefix}*.mp4")))
    if slot_matches:
        return True, slot_matches[0]

    # Backward compatibility: legacy filenames without slot suffix map to slot 1.
    if prompt_slot == 1:
        legacy_prefix = f"{image_name}_{model_short}_"
        legacy_matches = sorted(glob.glob(str(Path(output_folder) / f"{legacy_prefix}*.mp4")))
        for path in legacy_matches:
            if f"_{model_short}_p" not in Path(path).stem:
                return True, path
    return False, None


# Model duration constraints (from fal.ai API documentation)
# Format: (pattern, allowed_durations, priority)
# Higher priority patterns are checked first to ensure more specific matches
MODEL_DURATION_CONSTRAINTS = [
    # Kling family - most specific patterns first
    ("kling-video/v2.1", [5, 10], 3),
    ("kling-video/v2.5", [5, 10], 3),
    ("kling-video/v2", [5, 10], 2),  # Catch-all for v2.x
    ("kling-video/v1", [5, 10], 2),
    ("kling-video/o1", [5, 10], 2),

    # Wan models - specific versions first
    ("wan/v2.6", [5, 10, 15], 3),  # v2.6 added 15-second support
    ("wan/v2.5", [5, 10], 3),
    ("wan-25-preview", [5, 10], 3),

    # Pixverse models - specific versions first
    ("pixverse/v5.5", [5, 8, 10], 3),
    ("pixverse/v5", [5, 8], 3),

    # Other models - alphabetically sorted
    ("haiper-video-v2", [4, 6], 2),
    ("hunyuan-video", [5, 10], 2),
    ("ltx-2", [5, 10], 2),
    ("minimax-video", [6], 2),
    ("ovi", [5, 10], 2),
    ("veo3", [5, 6, 7, 8], 2),
    ("vidu", [2, 3, 4, 5, 6, 7, 8], 2),  # Vidu Q2 supports 2-8 seconds
]


def validate_duration(model_endpoint: str, duration: int) -> None:
    """Validate duration against model-specific constraints.

    Uses priority-based pattern matching to ensure more specific model versions
    are matched before generic patterns (e.g., "kling-video/v2.5" before "kling-video/v2").

    Args:
        model_endpoint: Full model endpoint (e.g., "fal-ai/kling-video/v2.1/pro/image-to-video")
        duration: Requested duration in seconds

    Raises:
        ValueError: If duration is not valid for the model
    """
    if not isinstance(duration, int) or duration <= 0:
        raise ValueError(f"Duration must be a positive integer, got: {duration}")

    # Sort constraints by priority (highest first) for most specific matching
    sorted_constraints = sorted(MODEL_DURATION_CONSTRAINTS, key=lambda x: x[2], reverse=True)

    # Check against known constraints with priority-based matching
    for pattern, allowed_durations, _ in sorted_constraints:
        if pattern in model_endpoint:
            if duration not in allowed_durations:
                allowed_str = ', '.join(f"{d}s" for d in allowed_durations)
                model_name = model_endpoint.split('/')[-1] if '/' in model_endpoint else model_endpoint
                raise ValueError(
                    f"Duration {duration}s invalid for {model_name}. "
                    f"Allowed durations: {allowed_str}"
                )
            logger.debug(f"Duration {duration}s validated for pattern '{pattern}'")
            return  # Valid duration found

    # Unknown model - log warning but allow (graceful degradation)
    logger.warning(
        f"No duration constraints found for model '{model_endpoint}'. "
        f"Proceeding with duration {duration}s (may fail at API level if unsupported)."
    )


def get_duration_options_for_model(model_endpoint: str) -> list:
    """Get available duration options for a given model.
    
    Args:
        model_endpoint: Full model endpoint
        
    Returns:
        List of allowed duration values in seconds, or [5, 10] if unknown
    """
    # Sort constraints by priority for most specific matching
    sorted_constraints = sorted(MODEL_DURATION_CONSTRAINTS, key=lambda x: x[2], reverse=True)
    
    for pattern, allowed_durations, _ in sorted_constraints:
        if pattern in model_endpoint:
            return allowed_durations
    
    # Default for unknown models
    return [5, 10]


def get_next_available_path(
    image_path: str,
    output_folder: str,
    generator,
    config: dict = None,
    timestamp: Optional[datetime] = None,
) -> Path:
    """Return the next available output path for this image+model combination.

    With the {stem}_{model_short}_{index}.mp4 naming scheme the index is already
    auto-incremented by get_output_video_path(), so this is a simple delegation.
    """
    return get_output_video_path(image_path, output_folder, generator, config, timestamp)


@dataclass
class QueueItem:
    """Represents a single queued image with status tracking."""

    path: str
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    error_message: Optional[str] = None
    output_path: Optional[str] = None

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def source_folder(self) -> str:
        return os.path.dirname(self.path)


class QueueManager:
    """Thread-safe queue manager for image processing."""

    MAX_QUEUE_SIZE = 50

    def __init__(
        self,
        generator,
        config_getter: Callable[[], dict],
        log_callback: Callable[[str, str], None],
        queue_update_callback: Callable[[], None],
        processing_complete_callback: Optional[Callable[[QueueItem], None]] = None,
    ):
        """
        Initialize the queue manager.

        Args:
            generator: FalAIKlingGenerator instance
            config_getter: Function that returns current config dict
            log_callback: Function(message, level) for logging
            queue_update_callback: Function called when queue changes
            processing_complete_callback: Function called when an item finishes
        """
        self.items: List[QueueItem] = []
        self.lock = threading.Lock()
        self.generator = generator
        self.get_config = config_getter
        self.log = log_callback
        self.update_queue_display = queue_update_callback
        self.on_processing_complete = processing_complete_callback

        self.is_paused = False
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
        self._stop_flag = False

    def log_verbose(self, message: str, level: str = "info"):
        """Log a message only if verbose mode is enabled."""
        config = self.get_config()
        if config.get("verbose_gui_mode", False):
            self.log(message, level)

    def validate_file(self, file_path: str) -> tuple:
        """
        Validate a file for processing.

        Returns:
            (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in VALID_EXTENSIONS:
            return False, f"Unsupported format: {ext}"

        # Check if already in queue
        with self.lock:
            for item in self.items:
                if item.path == file_path and item.status in ("pending", "processing"):
                    return False, "Already in queue"

        return True, ""

    def add_to_queue(self, file_path: str) -> tuple:
        """
        Add a file to the processing queue.

        Returns:
            (success, message)
        """
        # Validate file
        is_valid, error = self.validate_file(file_path)
        if not is_valid:
            return False, error

        with self.lock:
            # Check queue limit
            pending_count = sum(
                1 for item in self.items if item.status in ("pending", "processing")
            )
            if pending_count >= self.MAX_QUEUE_SIZE:
                return False, f"Queue full ({self.MAX_QUEUE_SIZE} items max)"

            # Add to queue
            item = QueueItem(path=file_path)
            self.items.append(item)

        self.update_queue_display()
        self.log(f"Added to queue: {os.path.basename(file_path)}", "info")

        # Start processing if not already running
        if not self.is_running and not self.is_paused:
            self.start_processing()

        return True, "Added to queue"

    def start_processing(self):
        """Start the worker thread to process queue items."""
        if self.is_running:
            return

        self._stop_flag = False
        self.is_running = True
        self.is_paused = False
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        self.log("Processing started", "info")

    def pause_processing(self):
        """Pause processing after current item completes."""
        self.is_paused = True
        self.log("Processing paused", "warning")

    def resume_processing(self):
        """Resume processing."""
        self.is_paused = False
        if not self.is_running:
            self.start_processing()
        else:
            self.log("Processing resumed", "info")

    def stop_processing(self):
        """Stop processing completely."""
        self._stop_flag = True
        self.is_paused = True

    def retry_failed(self):
        """Re-queue all failed items."""
        count = 0
        with self.lock:
            for item in self.items:
                if item.status == "failed":
                    item.status = "pending"
                    item.error_message = None
                    count += 1

        if count > 0:
            self.update_queue_display()
            self.log(f"Retrying {count} failed item(s)", "info")
            if not self.is_running and not self.is_paused:
                self.start_processing()
        return count

    def clear_queue(self):
        """Remove all pending and failed items from queue."""
        with self.lock:
            self.items = [
                item
                for item in self.items
                if item.status in ("processing", "completed")
            ]
        self.update_queue_display()
        self.log("Queue cleared", "info")

    def remove_item(self, index: int):
        """Remove a specific item by index."""
        with self.lock:
            if 0 <= index < len(self.items):
                item = self.items[index]
                if item.status not in ("processing",):
                    self.items.pop(index)
                    self.update_queue_display()
                    return True
        return False

    def get_items(self) -> List[QueueItem]:
        """Get a copy of all queue items."""
        with self.lock:
            return list(self.items)

    def get_pending_count(self) -> int:
        """Get count of pending items."""
        with self.lock:
            return sum(1 for item in self.items if item.status == "pending")

    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self.lock:
            return {
                "pending": sum(1 for item in self.items if item.status == "pending"),
                "processing": sum(
                    1 for item in self.items if item.status == "processing"
                ),
                "completed": sum(
                    1 for item in self.items if item.status == "completed"
                ),
                "failed": sum(1 for item in self.items if item.status == "failed"),
                "total": len(self.items),
            }

    def _get_next_pending(self) -> Optional[QueueItem]:
        """Get next pending item and mark it as processing."""
        with self.lock:
            for item in self.items:
                if item.status == "pending":
                    item.status = "processing"
                    return item
        return None

    def _process_queue(self):
        """Worker thread that processes queue items."""
        while not self._stop_flag:
            # Check if paused
            if self.is_paused:
                self.is_running = False
                return

            # Get next item
            item = self._get_next_pending()
            if item is None:
                # No more items to process
                self.is_running = False
                self.log("Queue processing complete", "success")
                return

            self.update_queue_display()
            self.log(f"Processing: {item.filename}", "info")

            try:
                # Capture timestamp at start of processing (for consistent filenames)
                generation_timestamp = datetime.now()

                # Get current config
                config = self.get_config()
                use_source_folder = config.get("use_source_folder", True)
                output_folder = config.get("output_folder", "")
                prompt = self._get_current_prompt(config)
                negative_prompt = self._get_current_negative_prompt(config)
                allow_reprocess = config.get("allow_reprocess", False)
                reprocess_mode = config.get("reprocess_mode", "increment")
                video_duration = config.get("video_duration", 10)
                model_endpoint = config.get("current_model", "")
                prompt_slot = config.get("current_prompt_slot", 1)

                # Advanced video settings
                aspect_ratio = config.get("aspect_ratio", "9:16")
                resolution = config.get("resolution", "720p")
                seed = config.get("seed", -1)
                camera_fixed = config.get("camera_fixed", False)
                generate_audio = config.get("generate_audio", False)

                # Update generator's prompt slot for filename generation
                self.generator.update_prompt_slot(prompt_slot)

                # Validate duration before making API request
                try:
                    validate_duration(model_endpoint, video_duration)
                except ValueError as e:
                    item.status = "failed"
                    item.error_message = str(e)
                    self.log(f"Invalid duration: {e}", "error")
                    self.update_queue_display()
                    if self.on_processing_complete:
                        self.on_processing_complete(item)
                    continue

                # Verbose: Show configuration being used
                self.log_verbose(f"  Model: {self.generator.model_display_name}", "api")
                self.log_verbose(
                    f"  Duration: {config.get('video_duration', 10)}s", "debug"
                )
                if prompt:
                    prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
                    self.log_verbose(f"  Prompt: {prompt_preview}", "debug")

                # Determine output folder
                if use_source_folder:
                    actual_output = item.source_folder
                    self.log_verbose(f"  Output: source folder", "debug")
                elif not output_folder or not os.path.isdir(output_folder):
                    # Custom folder selected but not set or invalid - use source folder
                    actual_output = item.source_folder
                    self.log(
                        f"No valid output folder set - saving to source folder",
                        "warning",
                    )
                else:
                    actual_output = output_folder
                    self.log_verbose(f"  Output: {actual_output}", "debug")

                # Check if video already exists (with current model and prompt slot)
                video_exists, found_video_path = check_video_exists(
                    item.path, actual_output, self.generator, config
                )
                custom_output_path = None

                if video_exists:
                    if not allow_reprocess:
                        # Reprocessing disabled - fail with clear message
                        # Use the actual found filename instead of generating a new one
                        existing_path = Path(found_video_path) if found_video_path else get_output_video_path(
                            item.path, actual_output, self.generator, config, generation_timestamp
                        )
                        item.status = "failed"
                        item.error_message = f"Video already exists: {existing_path.name}. Enable 'Allow reprocessing' to regenerate."
                        self.log(
                            f"Skipped: {item.filename} - video already exists",
                            "warning",
                        )
                        self.log(f"  Existing: {existing_path}", "info")
                        self.log(f"  Enable 'Allow reprocessing' to regenerate", "info")
                        self.update_queue_display()
                        if self.on_processing_complete:
                            self.on_processing_complete(item)
                        continue

                    elif reprocess_mode == "overwrite":
                        # Overwrite mode - delete existing file and looped variant
                        existing_path = (
                            Path(found_video_path)
                            if found_video_path
                            else get_output_video_path(
                                item.path, actual_output, self.generator, config, generation_timestamp
                            )
                        )
                        looped_path = existing_path.with_name(
                            f"{existing_path.stem}_looped{existing_path.suffix}"
                        )
                        try:
                            existing_path.unlink()
                            if looped_path.exists():
                                looped_path.unlink()
                            self.log(
                                f"Deleted existing: {existing_path.name} (+ looped variant)",
                                "warning",
                            )
                        except Exception as e:
                            self.log(f"Could not delete existing file: {e}", "error")
                            item.status = "failed"
                            item.error_message = f"Could not delete existing file: {e}"
                            self.update_queue_display()
                            if self.on_processing_complete:
                                self.on_processing_complete(item)
                            continue

                        # Keep overwrite target stable even if generator picks a new indexed filename.
                        custom_output_path = str(existing_path)

                    elif reprocess_mode == "increment":
                        # Increment mode - find next available filename
                        try:
                            next_path = get_next_available_path(
                                item.path, actual_output, self.generator, config, generation_timestamp
                            )
                            custom_output_path = str(next_path)
                            self.log(
                                f"Will save as: {next_path.name} (incremented)", "info"
                            )
                        except ValueError as e:
                            item.status = "failed"
                            item.error_message = str(e)
                            self.log(f"Error: {e}", "error")
                            self.update_queue_display()
                            if self.on_processing_complete:
                                self.on_processing_complete(item)
                            continue

                # Process the image
                # Skip duplicate check if we've already handled it (overwrite mode deleted file,
                # increment mode uses custom path)
                skip_check = video_exists and reprocess_mode == "overwrite"
                result = self._generate_video(
                    item,
                    actual_output,
                    prompt,
                    negative_prompt,
                    use_source_folder,
                    custom_output_path,
                    skip_duplicate_check=skip_check,
                    video_duration=video_duration,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    seed=seed,
                    camera_fixed=camera_fixed,
                    generate_audio=generate_audio,
                    generation_timestamp=generation_timestamp,
                )

                if result:
                    item.status = "completed"
                    item.output_path = result
                    self.log(f"Completed: {item.filename}", "success")
                    self.log(f"Saved to: {result}", "info")

                    # Check if loop video is enabled
                    if config.get("loop_videos", False):
                        self._loop_video(result, item)
                else:
                    item.status = "failed"
                    item.error_message = "Generation failed"
                    self.log(f"Failed: {item.filename}", "error")

            except Exception as e:
                item.status = "failed"
                item.error_message = str(e)
                self.log(f"Error processing {item.filename}: {e}", "error")

            self.update_queue_display()

            if self.on_processing_complete:
                self.on_processing_complete(item)

        self.is_running = False

    def _generate_video(
        self,
        item: QueueItem,
        output_folder: str,
        prompt: str,
        negative_prompt: str,
        use_source_folder: bool,
        custom_output_path: Optional[str] = None,
        skip_duplicate_check: bool = False,
        video_duration: int = 10,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        seed: int = -1,
        camera_fixed: bool = False,
        generate_audio: bool = False,
        generation_timestamp: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Generate video using the generator.

        Args:
            item: Queue item being processed
            output_folder: Output folder path
            prompt: Generation prompt
            negative_prompt: Negative prompt (optional, model-dependent)
            use_source_folder: Whether to save to source folder
            custom_output_path: Optional custom output path (for increment mode)
            skip_duplicate_check: Whether to skip duplicate detection
            video_duration: Video duration in seconds (default: 10)
            aspect_ratio: Video aspect ratio (default: 9:16)
            resolution: Video resolution (default: 720p)
            seed: Random seed, -1 for random (default: -1)
            camera_fixed: Lock camera movement (default: False)
            generate_audio: Generate audio track (default: False)
            generation_timestamp: Generation start time for consistent filenames (default: None)

        Returns:
            Output path on success, None on failure
        """
        # Respect model capability: if not supported, drop negative_prompt
        supports_negative = (
            self.get_config()
            .get("model_capabilities", {})
            .get(self.generator.model_endpoint, False)
        )
        neg_for_payload = negative_prompt if supports_negative else None

        # Set up verbose callback for generator progress
        def progress_callback(message: str, level: str = "info"):
            self.log_verbose(message, level)

        # Attach callback to generator if verbose mode
        config = self.get_config()
        if config.get("verbose_gui_mode", False):
            self.generator.set_progress_callback(progress_callback)
        else:
            self.generator.set_progress_callback(None)

        # For increment mode, we need to handle the output path ourselves
        if custom_output_path:
            # Generate with skip_duplicate_check since we've already handled it
            result = self.generator.create_kling_generation(
                character_image_path=item.path,
                output_folder=output_folder,
                custom_prompt=prompt,
                negative_prompt=neg_for_payload,
                use_source_folder=use_source_folder,
                skip_duplicate_check=True,  # We've already handled duplicate check
                duration=video_duration,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                seed=seed,
                camera_fixed=camera_fixed,
                generate_audio=generate_audio,
                config=config,
                timestamp=generation_timestamp,
            )

            if result and custom_output_path != result:
                # Rename to custom path (incremented filename)
                try:
                    import shutil

                    shutil.move(result, custom_output_path)
                    return custom_output_path
                except Exception as e:
                    self.log(f"Could not rename output: {e}", "warning")
                    return result  # Return original path if rename fails

            return result
        else:
            # Normal generation
            return self.generator.create_kling_generation(
                character_image_path=item.path,
                output_folder=output_folder,
                custom_prompt=prompt,
                negative_prompt=neg_for_payload,
                use_source_folder=use_source_folder,
                skip_duplicate_check=skip_duplicate_check,
                duration=video_duration,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                seed=seed,
                camera_fixed=camera_fixed,
                generate_audio=generate_audio,
                config=config,
                timestamp=generation_timestamp,
            )

    def _loop_video(self, video_path: str, item: QueueItem):
        """
        Create a looped version of the generated video.

        Args:
            video_path: Path to the generated video
            item: Queue item being processed
        """
        try:
            from .video_looper import create_looped_video

            self.log(f"Creating looped video...", "info")

            # Create looped version (adds _looped suffix)
            looped_path = create_looped_video(
                input_path=video_path,
                suffix="_looped",
                overwrite=True,
                log_callback=self.log,
            )

            if looped_path:
                self.log(
                    f"Looped video saved: {os.path.basename(looped_path)}", "success"
                )
            else:
                self.log(f"Failed to create looped video", "warning")

        except ImportError:
            self.log("Video looper module not available", "warning")
        except Exception as e:
            self.log(f"Error creating looped video: {e}", "warning")

    def _get_current_prompt(self, config: dict) -> str:
        """Get the current prompt from config."""
        slot = config.get("current_prompt_slot", 1)
        saved_prompts = config.get("saved_prompts", {})
        return saved_prompts.get(str(slot), "") or ""

    def _get_current_negative_prompt(self, config: dict) -> str:
        """Get current negative prompt from config."""
        slot = config.get("current_prompt_slot", 1)
        saved = config.get("negative_prompts", {})
        return saved.get(str(slot), "") or ""
