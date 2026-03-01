"""Image session state for the carousel — tracks images through the pipeline."""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)


_VALID_SOURCE_TYPES = {"input", "selfie", "outpaint"}


@dataclass
class ImageEntry:
    """A single image in the session.

    Attributes:
        path: Absolute path to the image file.
        source_type: One of "input", "selfie", "outpaint".
        label: Display label (auto-generated if empty).
    """

    path: str
    source_type: str  # "input", "selfie", "outpaint"
    label: str = ""

    def __post_init__(self):
        # Normalize to absolute path
        self.path = os.path.abspath(self.path)
        # Validate source_type
        if self.source_type not in _VALID_SOURCE_TYPES:
            logger.warning(
                "Unknown source_type %r, defaulting to 'input'", self.source_type
            )
            self.source_type = "input"
        if not self.label:
            self.label = f"{self.source_type}: {os.path.basename(self.path)}"

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.path)


class ImageSession:
    """Manages a session of images flowing through the pipeline.

    Supports navigation (prev/next), adding images from each processing step,
    and a change callback for UI updates whenever state changes.
    """

    def __init__(self):
        self._images: List[ImageEntry] = []
        self._current_index: int = -1
        self._on_change: Optional[Callable[[], None]] = None

    def set_on_change(self, callback: Callable[[], None]):
        """Set callback fired whenever the session state changes."""
        self._on_change = callback

    def _notify(self):
        if self._on_change:
            try:
                self._on_change()
            except Exception as e:
                logger.error("ImageSession on_change callback error: %s", e)

    def add_image(
        self,
        path: str,
        source_type: str,
        label: str = "",
        make_active: bool = True,
    ) -> ImageEntry:
        """Add an image to the session.

        Args:
            path: Absolute path to the image file
            source_type: One of "input", "selfie", "outpaint"
            label: Optional display label (auto-generated if empty)
            make_active: If True, navigate to this image immediately

        Returns:
            The created ImageEntry.
        """
        entry = ImageEntry(path=path, source_type=source_type, label=label)
        self._images.append(entry)
        if make_active:
            self._current_index = len(self._images) - 1
        self._notify()
        return entry

    def navigate(self, delta: int) -> bool:
        """Navigate by delta positions (e.g. +1 or -1).

        Returns True if the position changed.
        """
        if not self._images:
            return False
        new_index = self._current_index + delta
        if 0 <= new_index < len(self._images):
            self._current_index = new_index
            self._notify()
            return True
        return False

    def navigate_to(self, index: int) -> bool:
        """Navigate to an absolute index.

        Returns True if the position changed.
        """
        if 0 <= index < len(self._images):
            if self._current_index != index:
                self._current_index = index
                self._notify()
            return True
        return False

    @property
    def active_entry(self) -> Optional[ImageEntry]:
        """Get the currently active image entry."""
        if 0 <= self._current_index < len(self._images):
            return self._images[self._current_index]
        return None

    @property
    def active_image_path(self) -> Optional[str]:
        """Get the path of the currently active image."""
        entry = self.active_entry
        return entry.path if entry else None

    @property
    def count(self) -> int:
        """Total number of images in the session."""
        return len(self._images)

    @property
    def current_index(self) -> int:
        """Zero-based index of the active image (-1 if empty)."""
        return self._current_index

    @property
    def images(self) -> List[ImageEntry]:
        """Return a shallow copy of the image list."""
        return list(self._images)

    def clear(self):
        """Remove all images from the session."""
        self._images.clear()
        self._current_index = -1
        self._notify()

    def remove_current(self) -> bool:
        """Remove the currently active image.

        Returns True if an image was removed.
        """
        if not self._images or self._current_index < 0:
            return False
        self._images.pop(self._current_index)
        # Clamp index to valid range
        if self._current_index >= len(self._images):
            self._current_index = len(self._images) - 1
        self._notify()
        return True
