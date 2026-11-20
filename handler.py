import runpod
import sys

from app.handler import handler


def check_cuda_runtime():
    import torch

    print(f"PyTorch: {torch.__version__}", flush=True)
    print(f"PyTorch CUDA runtime: {torch.version.cuda}", flush=True)
    if not torch.version.cuda:
        raise RuntimeError("CPU-only PyTorch was installed; rebuild with the official CUDA wheel")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable; check RunPod GPU assignment and NVIDIA driver compatibility")

    name = torch.cuda.get_device_name(0)
    major, minor = torch.cuda.get_device_capability(0)
    memory_gib = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU 0: {name} (sm_{major}{minor}, {memory_gib:.1f} GiB)", flush=True)
    probe = torch.ones(1, device="cuda:0")
    probe.add_(1)
    torch.cuda.synchronize()
    print("CUDA kernel self-check passed", flush=True)


if __name__ == "__main__":
    try:
        check_cuda_runtime()
    except Exception as exc:
        print(f"CUDA self-check failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
    runpod.serverless.start({"handler": handler})
