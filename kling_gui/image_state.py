"""Image session state for the carousel — tracks images through the pipeline."""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Tuple

logger = logging.getLogger(__name__)


_VALID_SOURCE_TYPES = {"input", "selfie", "outpaint", "polish", "upscale"}


@dataclass
class ImageEntry:
    """A single image in the session.

    Attributes:
        path: Absolute path to the image file.
        source_type: One of "input", "selfie", "outpaint".
        label: Display label (auto-generated if empty).
        rotation: Rotation in degrees (0, 90, 180, 270) applied on top of EXIF correction.
        similarity: Face similarity score string, e.g. "72%" or "n/a". None for inputs.
    """

    path: str
    source_type: str  # "input", "selfie", "outpaint", "polish", "upscale"
    label: str = ""
    rotation: int = 0
    similarity: Optional[str] = None  # "72%" or None
    ops: dict = field(default_factory=dict)  # {"pol": 1, "ups": 2, "exp": 1}

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
        self._reference_index: int = -1
        self._similarity_ref_index: int = -1
        self._on_change_listeners: List[Callable] = []
        self._primary_listener: Optional[Callable] = None

    def set_on_change(self, callback: Callable[[], None]):
        """Set the primary on_change listener (replaces any previous set_on_change call).
        For additional listeners, use add_on_change() instead."""
        if self._primary_listener and self._primary_listener in self._on_change_listeners:
            self._on_change_listeners.remove(self._primary_listener)
        self._primary_listener = callback
        if callback and callback not in self._on_change_listeners:
            self._on_change_listeners.append(callback)

    def add_on_change(self, callback: Callable[[], None]):
        """Add an additional change listener."""
        if callback not in self._on_change_listeners:
            self._on_change_listeners.append(callback)

    def remove_on_change(self, callback: Callable[[], None]):
        """Remove a change listener."""
        if callback in self._on_change_listeners:
            self._on_change_listeners.remove(callback)

    def _notify(self):
        for cb in self._on_change_listeners[:]:  # copy to allow removal during iteration
            try:
                cb()
            except Exception as e:
                logger.error("ImageSession on_change listener error: %s", e)

    def add_image(
        self,
        path: str,
        source_type: str,
        label: str = "",
        make_active: bool = True,
        similarity: Optional[str] = None,
        ops: Optional[dict] = None,
    ) -> ImageEntry:
        """Add an image to the session.

        Args:
            path: Absolute path to the image file
            source_type: One of "input", "selfie", "outpaint", "polish", "upscale"
            label: Optional display label (auto-generated if empty)
            make_active: If True, navigate to this image immediately
            similarity: Face similarity score string, e.g. "72%" or None
            ops: Pipeline operations dict, e.g. {"pol": 1, "ups": 2}

        Returns:
            The created ImageEntry.
        """
        entry = ImageEntry(path=path, source_type=source_type, label=label,
                           similarity=similarity, ops=ops or {})
        self._images.append(entry)
        new_idx = len(self._images) - 1
        if entry.source_type == "input":
            self._reference_index = new_idx
        if make_active:
            self._current_index = new_idx
        self._notify()
        return entry

    def navigate(self, delta: int) -> bool:
        """Cycle through all images by *delta* (wraps around).

        Returns True if the position changed.
        """
        if not self._images:
            return False
        new_index = (self._current_index + delta) % len(self._images)
        if new_index != self._current_index:
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

    @property
    def reference_index(self) -> int:
        """Index of the currently selected reference (input) image, or -1."""
        return self._reference_index

    @property
    def reference_entry(self) -> Optional[ImageEntry]:
        """The currently selected reference (input) image entry."""
        if 0 <= self._reference_index < len(self._images):
            entry = self._images[self._reference_index]
            if entry.source_type == "input":
                return entry
        return None

    # ── Similarity reference (any image type) ─────────────────────

    @property
    def similarity_ref_index(self) -> int:
        """Index of the user-selected similarity reference image, or -1."""
        return self._similarity_ref_index

    @property
    def similarity_ref_entry(self) -> Optional[ImageEntry]:
        """The image chosen as the similarity reference (any source_type)."""
        if 0 <= self._similarity_ref_index < len(self._images):
            return self._images[self._similarity_ref_index]
        return None

    def set_similarity_ref(self, index: int) -> bool:
        """Set the similarity reference to any image by index. Pass -1 to clear."""
        if index == -1:
            self._similarity_ref_index = -1
            self._notify()
            return True
        if 0 <= index < len(self._images):
            self._similarity_ref_index = index
            self._notify()
            return True
        return False

    @property
    def input_images(self) -> List[Tuple[int, ImageEntry]]:
        """List of (global_index, entry) for all input images."""
        return [
            (i, e) for i, e in enumerate(self._images) if e.source_type == "input"
        ]

    @property
    def generated_images(self) -> List[Tuple[int, ImageEntry]]:
        """List of (global_index, entry) for all non-input images."""
        return [
            (i, e) for i, e in enumerate(self._images) if e.source_type != "input"
        ]

    def navigate_reference(self, delta: int) -> bool:
        """Navigate through input images only by delta (+1/-1).

        Clamps at boundaries (does not wrap). Updates _reference_index
        and notifies listeners. Returns True if the reference changed.
        """
        inputs = self.input_images
        if not inputs:
            return False
        # Find current position within inputs list
        current_pos = -1
        for pos, (idx, _entry) in enumerate(inputs):
            if idx == self._reference_index:
                current_pos = pos
                break
        if current_pos < 0:
            # Reference is unset — jump to first or last input directly
            new_pos = 0 if delta >= 0 else len(inputs) - 1
        else:
            new_pos = current_pos + delta
        if 0 <= new_pos < len(inputs):
            self._reference_index = inputs[new_pos][0]
            self._notify()
            return True
        return False

    def clear(self):
        """Remove all images from the session."""
        self._images.clear()
        self._current_index = -1
        self._reference_index = -1
        self._similarity_ref_index = -1
        self._notify()

    def remove_current(self) -> bool:
        """Remove the currently active image.

        Returns True if an image was removed.
        """
        if not self._images or self._current_index < 0:
            return False
        removed_index = self._current_index
        self._images.pop(self._current_index)
        # Clamp current index to valid range
        if self._current_index >= len(self._images):
            self._current_index = len(self._images) - 1
        # Fix reference index after removal
        if self._reference_index == removed_index:
            # The reference itself was removed — find another input
            inputs = self.input_images
            self._reference_index = inputs[0][0] if inputs else -1
        elif self._reference_index > removed_index:
            self._reference_index -= 1
        # Fix similarity ref index after removal
        if self._similarity_ref_index == removed_index:
            self._similarity_ref_index = -1
        elif self._similarity_ref_index > removed_index:
            self._similarity_ref_index -= 1
        self._notify()
        return True

    def to_dict(self) -> dict:
        """Serialize session state to a plain dict (for JSON persistence)."""
        return {
            "images": [
                {
                    "path": e.path,
                    "source_type": e.source_type,
                    "label": e.label,
                    "similarity": e.similarity,
                    "ops": e.ops if e.ops else {},
                }
                for e in self._images
            ],
            "current_index": self._current_index,
            "reference_index": self._reference_index,
            "similarity_ref_index": self._similarity_ref_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImageSession":
        """Restore a session from a serialized dict.

        Skips entries whose file no longer exists on disk.
        Returns a new ImageSession (listeners are NOT transferred).
        """
        session = cls()
        images_data = data.get("images", [])
        for img in images_data:
            path = img.get("path", "")
            if not os.path.isfile(path):
                logger.debug("Session restore: skipping missing file %s", path)
                continue
            entry = ImageEntry(
                path=path,
                source_type=img.get("source_type", "input"),
                label=img.get("label", ""),
                similarity=img.get("similarity"),
                ops=img.get("ops", {}),
            )
            session._images.append(entry)

        count = len(session._images)
        raw_cur = data.get("current_index", -1)
        raw_ref = data.get("reference_index", -1)
        session._current_index = raw_cur if 0 <= raw_cur < count else (count - 1 if count else -1)

        # Validate reference_index points to an actual input entry
        if 0 <= raw_ref < count and session._images[raw_ref].source_type == "input":
            session._reference_index = raw_ref
        else:
            # Fall back to first input entry
            inputs = session.input_images
            session._reference_index = inputs[0][0] if inputs else -1

        # Restore similarity reference (any image type)
        raw_sim_ref = data.get("similarity_ref_index", -1)
        session._similarity_ref_index = raw_sim_ref if 0 <= raw_sim_ref < count else -1

        return session
