def create_rembg_session(model_name: str):
    import onnxruntime as ort
    from rembg.sessions.u2net_human_seg import U2netHumanSegSession

    if model_name != U2netHumanSegSession.name():
        raise ValueError("This runtime profile supports only u2net_human_seg")

    options = ort.SessionOptions()
    # Return inference allocations instead of growing a retained CPU arena.
    # Memory-pattern planning and graph optimizations retain their defaults.
    options.enable_cpu_mem_arena = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1

    return U2netHumanSegSession(
        model_name, options, providers=["CPUExecutionProvider"]
    )
