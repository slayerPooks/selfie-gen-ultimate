"""Standalone face similarity scoring using InsightFace (ArcFace).

Extracted from SelfieGenerator so outpaint and other tabs can reuse it.
"""

import os
import threading
from typing import Optional, Callable

# InsightFace singleton (ArcFace model is ~300 MB, load once)
_insightface_app = None
_insightface_init_lock = threading.Lock()
_insightface_infer_lock = threading.Lock()


def compute_face_similarity(
    source_path: str,
    target_path: str,
    report_cb: Optional[Callable[[str, str], None]] = None,
) -> Optional[int]:
    """Compute face similarity between two images using InsightFace (ArcFace).

    Uses RetinaFace detection + alignment + ArcFace embedding.

    Args:
        source_path: Path to the reference/source face image.
        target_path: Path to the generated/target face image.
        report_cb: Optional ``(msg, level) -> None`` callback for progress logs.

    Returns:
        Cosine similarity as 0-100 integer, or None if a face
        cannot be detected in either image.
    """
    global _insightface_app

    def _log(msg: str, level: str = "debug"):
        if report_cb:
            report_cb(f"Sim: {msg}", level)

    try:
        import insightface.app  # noqa: F811
        import numpy as np
        import cv2
    except ImportError as ie:
        _log(f"missing dependency: {ie}", "warning")
        return None

    # Validate paths exist before doing anything expensive
    ref_exists = os.path.isfile(source_path)
    tgt_exists = os.path.isfile(target_path)
    _log(f"ref exists={ref_exists} target exists={tgt_exists}", "debug")
    if not ref_exists or not tgt_exists:
        _log(f"file missing — ref={source_path!r} target={target_path!r}", "warning")
        return None

    try:
        # One-time model init (downloads ~300 MB to ~/.insightface/models/)
        with _insightface_init_lock:
            if _insightface_app is None:
                _log("loading ArcFace model (first run)...", "info")
                app = insightface.app.FaceAnalysis(name="buffalo_l")
                app.prepare(ctx_id=-1, det_size=(640, 640), providers=["CPUExecutionProvider"])
                _insightface_app = app
                _log("ArcFace model loaded", "info")

        analyser = _insightface_app
        assert analyser is not None  # guaranteed by init block above

        def _load_image(img_path: str):
            """Load image via PIL (Unicode-safe) and convert to BGR numpy array."""
            from PIL import Image, ImageOps
            pil_img = Image.open(img_path)
            pil_img = ImageOps.exif_transpose(pil_img)
            # Convert to RGB numpy, then BGR for InsightFace
            rgb = np.array(pil_img.convert("RGB"))
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            _log(f"loaded {os.path.basename(img_path)} shape={bgr.shape}", "debug")
            return bgr

        def _best_face(img_path: str, label: str):
            img = _load_image(img_path)
            if img is None:
                _log(f"image read failed for {label}: {img_path!r}", "warning")
                return None
            with _insightface_infer_lock:
                faces = analyser.get(img)
            n = len(faces) if faces else 0
            _log(f"{label}: {n} face(s) detected", "debug")
            if not faces:
                return None
            # Pick highest detection confidence when multiple faces found
            best = max(faces, key=lambda f: f.det_score)
            _log(f"{label}: best face score={best.det_score:.3f}", "debug")
            return best

        face1 = _best_face(source_path, "ref")
        face2 = _best_face(target_path, "target")

        if face1 is None or face2 is None:
            missing = []
            if face1 is None:
                missing.append("ref")
            if face2 is None:
                missing.append("target")
            _log(f"no face in {'+'.join(missing)} — cannot compute similarity", "warning")
            return None

        # Cosine similarity on L2-normalised ArcFace embeddings
        sim = float(np.dot(face1.normed_embedding, face2.normed_embedding))
        score = min(100, max(0, round(sim * 100)))
        _log(f"cosine={sim:.4f} → score={score}%", "debug")
        return score
    except Exception as exc:
        import traceback
        _log(f"failed: {type(exc).__name__}: {exc!r}", "warning")
        _log(traceback.format_exc(), "debug")
        return None
