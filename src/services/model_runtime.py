"""Own the shared inference models and their initialization."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rembg.sessions.base import BaseSession
    from ultralytics import YOLO

# Retain the existing OpenMP compatibility setting before native imports.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger(__name__)
MODEL_PATH = Path(__file__).resolve().parents[2] / "best.pt"
REMBG_MODEL_NAME = "modnet-portrait"

rembg_session: BaseSession | None = None
yolo_model: YOLO | None = None
yolo_lock = Lock()


def create_rembg_session(model_name: str) -> BaseSession:
    """Use low-memory CPU ONNX options without changing model precision."""
    import onnxruntime as ort
    from rembg.sessions.u2net_human_seg import U2netHumanSegSession

    from services.modnet_session import ModnetPortraitSession

    session_types = {
        ModnetPortraitSession.name(): ModnetPortraitSession,
        U2netHumanSegSession.name(): U2netHumanSegSession,
    }
    if model_name not in session_types:
        raise ValueError(f"Unsupported background-removal model: {model_name}")

    options = ort.SessionOptions()
    # Return inference allocations instead of growing a retained CPU arena.
    # Memory-pattern planning and graph optimizations retain their defaults.
    options.enable_cpu_mem_arena = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return session_types[model_name](
        model_name, options, providers=["CPUExecutionProvider"]
    )


def load_models() -> None:
    """Load once at startup; never publish a partially initialized model pair."""
    from ultralytics import YOLO

    global rembg_session, yolo_model
    if rembg_session is not None and yolo_model is not None:
        return

    logger.info("Loading photo-processing models")
    session = create_rembg_session(REMBG_MODEL_NAME)
    detector = YOLO(str(MODEL_PATH))
    rembg_session, yolo_model = session, detector
    logger.info("Photo-processing models loaded")


def get_detector() -> YOLO:
    if yolo_model is None:
        raise RuntimeError("Photo-processing models have not been loaded")
    return yolo_model


def get_background_session() -> BaseSession:
    if rembg_session is None:
        raise RuntimeError("Photo-processing models have not been loaded")
    return rembg_session
