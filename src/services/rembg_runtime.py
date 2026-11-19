"""Low-memory CPU ONNX options for the supported portrait-removal models."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rembg.sessions.base import BaseSession


def create_rembg_session(model_name: str) -> BaseSession:
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
