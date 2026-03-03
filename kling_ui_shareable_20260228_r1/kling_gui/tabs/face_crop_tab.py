"""Face Crop Tab — Extract passport-style 3:4 face crops from ID card photos."""

import os
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog
import threading
from pathlib import Path
from typing import Callable, Optional

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession
from path_utils import get_gen_images_folder

# Optional heavy dependencies — tab degrades gracefully if missing
try:
    import cv2
    import numpy as np
    from retinaface import RetinaFace

    HAS_FACE_DEPS = True
except ImportError:
    HAS_FACE_DEPS = False

# PIL for canvas thumbnails
try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


_DEFAULT_POLISH_PROMPT = (
    "Carefully remove all text, numbers, watermarks, seals, and document artifacts "
    "from the image. Clean up the background to make it seamless. "
    "CRITICAL: Do NOT alter the person's face, facial features, hair, expression, "
    "or clothing in any way. Keep the original photo quality, lighting, and realism "
    "exactly the same. Do not beautify or change the identity."
)


class FaceCropTab(tk.Frame):
    """Tab 0: Detect face in ID card photo and produce a 3:4 passport crop."""

    def __init__(
        self,
        parent,
        image_session: ImageSession,
        config: dict,
        config_getter: Callable[[], dict],
        log_callback: Callable[[str, str], None],
        notebook_switcher: Optional[Callable[[], None]] = None,
        notebook_switcher_prep: Optional[Callable[[], None]] = None,
        notebook_switcher_selfie: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.config = config
        self.get_config = config_getter
        self.log = log_callback
        # Legacy single-switcher kept for backward compat
        self._notebook_switcher = notebook_switcher
        self._notebook_switcher_prep = notebook_switcher_prep or notebook_switcher
        self._notebook_switcher_selfie = notebook_switcher_selfie

        # Detection state
        self._source_path: Optional[str] = None
        self._original_path: Optional[str] = None  # user-selected path, pre-EXIF correction
        self._cv2_img = None  # numpy array (BGR)
        self._face_box = None  # (fx, fy, fw, fh)
        self._crop_result = None  # numpy array of current crop
        self._busy = False

        # Tk variables
        self._multiplier_var = tk.DoubleVar(
            value=config.get("face_crop_multiplier", 1.9)
        )
        self._auto_switch_var = tk.BooleanVar(
            value=config.get("face_crop_auto_switch", True)
        )

        # Polish state
        self._polish_counter = 0
        self._polish_busy = False
        self._polish_provider_var = tk.StringVar(
            value=config.get("face_crop_polish_provider", "BFL (Kontext Pro)")
        )

        # PhotoImage references (prevent GC)
        self._source_photo = None
        self._crop_photo = None

        self._build_ui()

    # ── UI Construction ─────────────────────────────────────────────

    def _build_ui(self):
        # Dependency warning
        if not HAS_FACE_DEPS:
            warn = tk.Label(
                self,
                text="Missing dependencies: pip install opencv-python-headless numpy retinaface",
                bg=COLORS["bg_panel"],
                fg=COLORS["warning"],
                font=(FONT_FAMILY, 10, "bold"),
                anchor="w",
            )
            warn.pack(fill=tk.X, padx=8, pady=(8, 0))

        # ── Source & Detection ──────────────────────────────────────
        source_frame = tk.LabelFrame(
            self,
            text=" Source & Detection ",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 10, "bold"),
            bd=1,
            relief="groove",
        )
        source_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        # Browse row
        browse_row = tk.Frame(source_frame, bg=COLORS["bg_panel"])
        browse_row.pack(fill=tk.X, padx=6, pady=(6, 2))

        self._path_var = tk.StringVar()
        path_entry = tk.Entry(
            browse_row,
            textvariable=self._path_var,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            insertbackground=COLORS["text_light"],
            relief="flat",
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        browse_btn = tk.Button(
            browse_row,
            text="Browse",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            relief="flat",
            cursor="hand2",
            command=self._browse_image,
        )
        browse_btn.pack(side=tk.LEFT, padx=(6, 0))

        use_carousel_btn = tk.Button(
            browse_row,
            text="Use Carousel Image",
            bg=COLORS["accent_blue"],
            fg="white",
            font=(FONT_FAMILY, 9),
            relief="flat",
            cursor="hand2",
            command=self._use_carousel_image,
        )
        use_carousel_btn.pack(side=tk.LEFT, padx=(6, 0))

        # Detect row
        detect_row = tk.Frame(source_frame, bg=COLORS["bg_panel"])
        detect_row.pack(fill=tk.X, padx=6, pady=(2, 2))

        self._detect_btn = tk.Button(
            detect_row,
            text="Detect Face",
            bg=COLORS["btn_green"],
            fg="white",
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._detect_face,
            state=tk.DISABLED if not HAS_FACE_DEPS else tk.NORMAL,
        )
        self._detect_btn.pack(side=tk.LEFT)

        self._status_label = tk.Label(
            detect_row,
            text="No image loaded",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            font=(FONT_FAMILY, 9),
            anchor="w",
        )
        self._status_label.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        # Slider row
        slider_row = tk.Frame(source_frame, bg=COLORS["bg_panel"])
        slider_row.pack(fill=tk.X, padx=6, pady=(2, 6))

        tk.Label(
            slider_row,
            text="Crop Multiplier:",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT)

        tk.Button(
            slider_row,
            text="-",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            cursor="hand2",
            width=2,
            command=lambda: self._adjust_multiplier(-0.1),
        ).pack(side=tk.LEFT, padx=(6, 0))

        self._slider = tk.Scale(
            slider_row,
            from_=1.0,
            to=3.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=self._multiplier_var,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            troughcolor=COLORS["bg_input"],
            highlightthickness=0,
            font=(FONT_FAMILY, 9),
            length=200,
            command=self._on_slider_changed,
        )
        self._slider.pack(side=tk.LEFT, padx=(2, 2), fill=tk.X, expand=True)

        tk.Button(
            slider_row,
            text="+",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            cursor="hand2",
            width=2,
            command=lambda: self._adjust_multiplier(0.1),
        ).pack(side=tk.LEFT)

        # ── Preview ─────────────────────────────────────────────────
        preview_frame = tk.LabelFrame(
            self,
            text=" Preview ",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 10, "bold"),
            bd=1,
            relief="groove",
        )
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        canvas_container = tk.Frame(preview_frame, bg=COLORS["bg_panel"])
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left: source with face box overlay
        left_frame = tk.Frame(canvas_container, bg=COLORS["bg_panel"])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(
            left_frame,
            text="Source",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            font=(FONT_FAMILY, 8),
        ).pack()
        self._source_canvas = tk.Canvas(
            left_frame, bg=COLORS["bg_input"], highlightthickness=0
        )
        self._source_canvas.pack(fill=tk.BOTH, expand=True)

        # Separator
        tk.Frame(canvas_container, bg=COLORS["border"], width=2).pack(
            side=tk.LEFT, fill=tk.Y, padx=4
        )

        # Right: crop result
        right_frame = tk.Frame(canvas_container, bg=COLORS["bg_panel"])
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(
            right_frame,
            text="Crop Result",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            font=(FONT_FAMILY, 8),
        ).pack()
        self._crop_canvas = tk.Canvas(
            right_frame, bg=COLORS["bg_input"], highlightthickness=0
        )
        self._crop_canvas.pack(fill=tk.BOTH, expand=True)

        # ── Polish Frame ──────────────────────────────────────────────
        polish_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        polish_frame.pack(fill=tk.X, padx=8, pady=(2, 2))

        self._polish_btn = tk.Button(
            polish_frame,
            text="Polish Crop",
            bg=COLORS["accent_blue"],
            fg="white",
            disabledforeground="#C8C8C8",
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._polish_crop,
            state=tk.DISABLED,
        )
        self._polish_btn.pack(side=tk.LEFT)

        tk.Label(
            polish_frame,
            text="Provider:",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT, padx=(12, 4))

        self._polish_provider_combo = ttk.Combobox(
            polish_frame,
            textvariable=self._polish_provider_var,
            values=["BFL (Kontext Pro)", "fal.ai (FLUX.2 Edit)"],
            state="readonly",
            width=20,
        )
        self._polish_provider_combo.pack(side=tk.LEFT)

        edit_prompt_btn = tk.Button(
            polish_frame,
            text="Edit Prompt",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            relief="flat",
            cursor="hand2",
            command=self._open_polish_prompt_editor,
        )
        edit_prompt_btn.pack(side=tk.LEFT, padx=(10, 0))

        self._polish_status = tk.Label(
            polish_frame,
            text="",
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            font=(FONT_FAMILY, 9),
            anchor="w",
        )
        self._polish_status.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        # ── Send Frame ──────────────────────────────────────────────
        send_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        send_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        self._auto_switch_cb = tk.Checkbutton(
            send_frame,
            text="Auto-switch after send",
            variable=self._auto_switch_var,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_input"],
            activebackground=COLORS["bg_panel"],
            activeforeground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        )
        self._auto_switch_cb.pack(side=tk.LEFT)

        # Two destination buttons — pack right-to-left so Phase 2 is rightmost
        self._send_selfie_btn = tk.Button(
            send_frame,
            text="Send to 2 (Generate Selfie)",
            bg=COLORS["btn_green"],
            fg="white",
            disabledforeground="#C8C8C8",
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._send_to_selfie,
            state=tk.DISABLED,
        )
        self._send_selfie_btn.pack(side=tk.RIGHT, padx=(4, 0))

        self._send_prep_btn = tk.Button(
            send_frame,
            text="Send to 1 (AI Analysis)",
            bg="#4A7A8C",
            fg="white",
            disabledforeground="#C8C8C8",
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._send_to_prep,
            state=tk.DISABLED,
        )
        self._send_prep_btn.pack(side=tk.RIGHT)

    # ── Browse ──────────────────────────────────────────────────────

    def _browse_image(self):
        ftypes = [("Images", " ".join(f"*{e}" for e in VALID_EXTENSIONS))]
        path = filedialog.askopenfilename(
            title="Select ID card / passport photo",
            filetypes=ftypes,
        )
        if not path:
            return
        self._path_var.set(path)
        self._load_source(path)

    def _use_carousel_image(self):
        """Load the active carousel image as the face detection source."""
        path = self.image_session.active_image_path
        if not path:
            self._status_label.config(text="No image in carousel", fg=COLORS["warning"])
            return
        self._path_var.set(path)
        self._load_source(path)

    def _load_source(self, path: str):
        if not HAS_PIL:
            self._status_label.config(text="Pillow not installed", fg=COLORS["error"])
            return
        if not os.path.isfile(path):
            self._status_label.config(text="File not found", fg=COLORS["error"])
            return

        self._source_path = path
        self._original_path = path
        self._face_box = None
        self._crop_result = None
        self._polish_counter = 0
        self._send_prep_btn.config(state=tk.DISABLED)
        self._send_selfie_btn.config(state=tk.DISABLED)
        self._update_polish_btn_state()

        # Load with PIL, fix EXIF rotation, save corrected temp for cv2/RetinaFace
        try:
            pil_img = Image.open(path)
            pil_img = ImageOps.exif_transpose(pil_img)

            # Save orientation-corrected image so cv2.imread and RetinaFace
            # see the same upright pixels as the Tkinter preview.
            corrected_path = os.path.join(
                tempfile.gettempdir(), f"kling_facecrop_{os.path.basename(path)}"
            )
            save_img = pil_img.convert("RGB") if pil_img.mode not in ("RGB", "L") else pil_img
            save_img.save(corrected_path, format="JPEG", quality=95)
            self._source_path = corrected_path

            pil_img.thumbnail((400, 400))
            self._source_pil = pil_img.copy()
            self._show_on_canvas(self._source_canvas, pil_img)
            self._crop_canvas.delete("all")
            self._status_label.config(
                text=f"Loaded ({pil_img.width}x{pil_img.height} preview)",
                fg=COLORS["text_light"],
            )
            self.log(f"Face Crop: loaded {os.path.basename(path)}", "info")
        except Exception as exc:
            self._status_label.config(text=f"Load error: {exc}", fg=COLORS["error"])

    # ── Detection ───────────────────────────────────────────────────

    def _detect_face(self):
        if self._busy or not self._source_path:
            return
        if not HAS_FACE_DEPS:
            self._status_label.config(
                text="Dependencies missing", fg=COLORS["error"]
            )
            return

        self._busy = True
        self._detect_btn.config(state=tk.DISABLED, text="Detecting...")
        self._status_label.config(text="Running RetinaFace...", fg=COLORS["progress"])
        self.log("Face Crop: running RetinaFace detection...", "info")

        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _detect_worker(self):
        try:
            source = self._source_path
            if not source:
                self._after_detect(None, None, "No source image loaded")
                return

            img = cv2.imread(source)
            if img is None:
                self._after_detect(None, None, "Could not read image with OpenCV")
                return

            faces = RetinaFace.detect_faces(source)
            if not faces or len(faces) == 0:
                self._after_detect(img, None, "No face detected")
                return

            # Pick largest face
            best_key: Optional[str] = None
            best_area = 0
            for key, data in faces.items():
                area = data["facial_area"]
                w = area[2] - area[0]
                h = area[3] - area[1]
                if w * h > best_area:
                    best_area = w * h
                    best_key = key

            if best_key is None:
                self._after_detect(img, None, "No face detected")
                return

            fa = faces[best_key]["facial_area"]
            fx, fy = fa[0], fa[1]
            fw, fh = fa[2] - fa[0], fa[3] - fa[1]
            self._after_detect(img, (fx, fy, fw, fh), None)

        except Exception as exc:
            self._after_detect(None, None, str(exc))

    def _after_detect(self, cv2_img, face_box, error):
        def _update():
            self._busy = False
            self._detect_btn.config(state=tk.NORMAL, text="Detect Face")

            if error:
                self._status_label.config(text=error, fg=COLORS["error"])
                self.log(f"Face Crop: {error}", "error")
                self._update_polish_btn_state()
                return

            self._cv2_img = cv2_img
            self._face_box = face_box

            if face_box:
                fx, fy, fw, fh = face_box
                self._status_label.config(
                    text=f"Face found: {fw}x{fh} at ({fx},{fy})",
                    fg=COLORS["success"],
                )
                self.log(
                    f"Face Crop: detected face {fw}x{fh} at ({fx},{fy})", "success"
                )
                self._draw_source_with_box()
                self._update_crop_preview()
                self._send_prep_btn.config(state=tk.NORMAL)
                self._send_selfie_btn.config(state=tk.NORMAL)
            else:
                self._status_label.config(text="No face detected", fg=COLORS["error"])
                self.log("Face Crop: no face detected in image", "warning")

            self._update_polish_btn_state()

        self.after(0, _update)

    # ── Crop Math (from validated test_crop.py) ─────────────────────

    def _compute_crop(self):
        """Return (x_start, y_start, x_end, y_end) for the current multiplier."""
        if self._cv2_img is None or self._face_box is None:
            return None
        fx, fy, fw, fh = self._face_box
        h_img, w_img = self._cv2_img.shape[:2]
        mult = self._multiplier_var.get()

        face_center_x = fx + (fw // 2)
        target_w = int(fw * mult)
        target_h = int(target_w * 1.333)  # 3:4 ratio
        top_margin = int(fh * 0.6)

        x_start = face_center_x - (target_w // 2)
        y_start = fy - top_margin
        x_end = x_start + target_w
        y_end = y_start + target_h

        # Boundary shifting
        if x_start < 0:
            x_end -= x_start
            x_start = 0
        if x_end > w_img:
            x_start -= x_end - w_img
            x_end = w_img
        if y_start < 0:
            y_end -= y_start
            y_start = 0
        if y_end > h_img:
            y_start -= y_end - h_img
            y_end = h_img

        # Final clamp
        x_start = max(0, x_start)
        y_start = max(0, y_start)
        x_end = min(w_img, x_end)
        y_end = min(h_img, y_end)

        return x_start, y_start, x_end, y_end

    # ── Canvas Drawing ──────────────────────────────────────────────

    def _show_on_canvas(self, canvas: tk.Canvas, pil_img: "Image.Image"):
        """Fit a PIL image into a canvas, centered."""
        canvas.update_idletasks()
        cw = max(canvas.winfo_width(), 100)
        ch = max(canvas.winfo_height(), 100)

        img = pil_img.copy()
        img.thumbnail((cw, ch))
        photo = ImageTk.PhotoImage(img)

        canvas.delete("all")
        canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")

        # Return photo ref to prevent GC
        return photo

    def _draw_source_with_box(self):
        """Redraw source image with a face bounding box overlay."""
        if not HAS_PIL or self._source_path is None:
            return
        try:
            pil_img = Image.open(self._source_path).copy()
            if self._face_box:
                fx, fy, fw, fh = self._face_box
                draw = ImageDraw.Draw(pil_img)
                draw.rectangle(
                    [fx, fy, fx + fw, fy + fh], outline="#00FF88", width=3
                )
            pil_img.thumbnail((400, 400))
            self._source_photo = self._show_on_canvas(self._source_canvas, pil_img)
        except Exception:
            pass

    def _update_crop_preview(self):
        """Recompute crop from cached data and show on crop canvas."""
        if not HAS_PIL or self._cv2_img is None:
            return
        coords = self._compute_crop()
        if coords is None:
            return
        x1, y1, x2, y2 = coords
        crop_bgr = self._cv2_img[y1:y2, x1:x2]
        if crop_bgr.size == 0:
            return

        self._crop_result = crop_bgr
        # Convert BGR → RGB → PIL
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil_crop = Image.fromarray(crop_rgb)
        pil_crop.thumbnail((400, 400))
        self._crop_photo = self._show_on_canvas(self._crop_canvas, pil_crop)

    # ── Slider Callback ─────────────────────────────────────────────

    def _on_slider_changed(self, _value=None):
        if self._face_box is not None:
            self._update_crop_preview()

    def _adjust_multiplier(self, delta: float):
        val = round(self._multiplier_var.get() + delta, 1)
        val = max(1.0, min(3.0, val))
        self._multiplier_var.set(val)
        self._on_slider_changed()

    # ── Send crop to next phase ─────────────────────────────────────

    def _save_crop(self) -> Optional[Path]:
        """Save current crop to disk and add to session. Returns path or None."""
        if self._crop_result is None or self._source_path is None:
            return None

        # Use original user-selected path (not the EXIF-corrected temp copy)
        origin = Path(self._original_path or self._source_path)
        gen_dir = Path(get_gen_images_folder(str(origin)))
        gen_dir.mkdir(parents=True, exist_ok=True)

        # Collision-safe naming
        out_path = gen_dir / f"{origin.stem}_crop.jpg"
        counter = 2
        while out_path.exists():
            out_path = gen_dir / f"{origin.stem}_crop_{counter}.jpg"
            counter += 1

        try:
            cv2.imwrite(str(out_path), self._crop_result)
        except Exception:
            out_path = Path(tempfile.gettempdir()) / f"{origin.stem}_crop.jpg"
            cv2.imwrite(str(out_path), self._crop_result)

        self.log(
            f"Face Crop: saved {out_path.name} "
            f"({self._crop_result.shape[1]}x{self._crop_result.shape[0]})",
            "success",
        )
        self.image_session.add_image(str(out_path), "input", label=out_path.name)
        return out_path

    def _send_to_prep(self):
        if self._save_crop() is None:
            return
        if self._auto_switch_var.get() and self._notebook_switcher_prep:
            self._notebook_switcher_prep()

    def _send_to_selfie(self):
        if self._save_crop() is None:
            return
        if self._auto_switch_var.get() and self._notebook_switcher_selfie:
            self._notebook_switcher_selfie()

    # ── Polish Crop ─────────────────────────────────────────────────

    def _update_polish_btn_state(self):
        """Enable polish button only when a crop exists and we're not busy."""
        if self._crop_result is not None and not self._busy and not self._polish_busy:
            self._polish_btn.config(state=tk.NORMAL)
        else:
            self._polish_btn.config(state=tk.DISABLED)

    def _polish_crop(self):
        """Save the crop, then polish it in a background thread."""
        if self._crop_result is None or self._polish_busy:
            return

        crop_path = self._save_crop()
        if crop_path is None:
            return

        self._polish_busy = True
        self._polish_btn.config(state=tk.DISABLED, text="Polishing...")

        provider_label = self._polish_provider_var.get()
        provider = "bfl" if "BFL" in provider_label else "fal"
        self._polish_status.config(
            text=f"Running {provider_label}...", fg=COLORS["progress"]
        )

        prompt = self.get_config().get("face_crop_polish_prompt", _DEFAULT_POLISH_PROMPT)

        self._polish_counter += 1
        output_path = str(crop_path.parent / f"{crop_path.stem}_polished_{self._polish_counter}.png")

        def _worker():
            from crop_polisher import CropPolisher

            cfg = self.get_config()
            polisher = CropPolisher(
                falai_api_key=cfg.get("falai_api_key", ""),
                bfl_api_key=cfg.get("bfl_api_key", ""),
                freeimage_key=cfg.get("freeimage_api_key", ""),
            )
            polisher.set_progress_callback(
                lambda msg, lvl: self.log(f"Polish: {msg}", lvl)
            )

            result = polisher.polish(
                image_path=str(crop_path),
                output_path=output_path,
                provider=provider,
                prompt=prompt,
            )
            if result:
                self.after(0, lambda: self._on_polish_done(result))
            else:
                self.after(0, lambda: self._on_polish_error("Polish failed (see log)"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_polish_done(self, result_path: str):
        """Handle successful polish: update crop canvas and carousel."""
        self._polish_busy = False
        self._polish_btn.config(text="Polish Crop")
        self._update_polish_btn_state()

        basename = os.path.basename(result_path)
        self._polish_status.config(text=f"Done: {basename}", fg=COLORS["success"])
        self.log(f"Polish: saved {basename}", "success")

        # Update crop preview with polished image
        try:
            if HAS_PIL:
                pil_img = Image.open(result_path)
                pil_img.thumbnail((400, 400))
                self._crop_photo = self._show_on_canvas(self._crop_canvas, pil_img)

            # Update _crop_result to the polished numpy array
            if HAS_FACE_DEPS:
                polished_bgr = cv2.imread(result_path)
                if polished_bgr is not None:
                    self._crop_result = polished_bgr

            # Add polished image to carousel
            self.image_session.add_image(result_path, "input", label=basename)
        except Exception as exc:
            self.log(f"Polish: preview update error: {exc}", "warning")

    def _on_polish_error(self, error: str):
        """Handle polish failure."""
        self._polish_busy = False
        self._polish_btn.config(text="Polish Crop")
        self._update_polish_btn_state()
        self._polish_status.config(text=error, fg=COLORS["error"])

    def _open_polish_prompt_editor(self):
        """Open a modal dialog to view/edit the polish prompt."""
        dialog = tk.Toplevel(self)
        dialog.title("Polish Prompt")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(bg=COLORS["bg_main"])
        dialog.geometry("520x340")
        dialog.resizable(True, True)

        tk.Label(
            dialog,
            text="Instruction prompt sent to the AI editor:",
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 10),
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(12, 4))

        text_widget = tk.Text(
            dialog,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 10),
            wrap=tk.WORD,
            height=10,
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        current_prompt = self.get_config().get(
            "face_crop_polish_prompt", _DEFAULT_POLISH_PROMPT
        )
        text_widget.insert("1.0", current_prompt)

        btn_frame = tk.Frame(dialog, bg=COLORS["bg_main"])
        btn_frame.pack(fill=tk.X, padx=12, pady=(4, 12))

        def _reset():
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", _DEFAULT_POLISH_PROMPT)

        def _save():
            new_prompt = text_widget.get("1.0", tk.END).strip()
            self.config["face_crop_polish_prompt"] = new_prompt
            dialog.destroy()

        tk.Button(
            btn_frame,
            text="Reset to Default",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            relief="flat",
            cursor="hand2",
            command=_reset,
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Cancel",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            relief="flat",
            cursor="hand2",
            command=dialog.destroy,
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_frame,
            text="Save",
            bg=COLORS["accent_blue"],
            fg="white",
            font=(FONT_FAMILY, 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=_save,
        ).pack(side=tk.RIGHT)

    # ── Config Persistence ──────────────────────────────────────────

    def get_config_updates(self) -> dict:
        updates = {
            "face_crop_multiplier": self._multiplier_var.get(),
            "face_crop_auto_switch": self._auto_switch_var.get(),
            "face_crop_polish_provider": self._polish_provider_var.get(),
        }
        # Only persist polish prompt if it was explicitly set (not just default)
        if "face_crop_polish_prompt" in self.config:
            updates["face_crop_polish_prompt"] = self.config["face_crop_polish_prompt"]
        return updates
