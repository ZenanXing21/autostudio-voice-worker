import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.handler as worker_module


def test_serverless_starts_before_loading_model_and_needs_no_api_token(monkeypatch, capsys):
    events = []
    registered = {}

    class FakeWorker:
        def __init__(self):
            events.append("load_model")

        def handle(self, job):
            return {"input": job["input"]}

    def fake_start(config):
        events.append("start")
        registered.update(config)

    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setattr(worker_module, "Worker", FakeWorker)
    monkeypatch.setattr(worker_module, "_worker", None)
    monkeypatch.setitem(sys.modules, "runpod", SimpleNamespace(serverless=SimpleNamespace(start=fake_start)))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        __version__="2.7.1+cu126", version=SimpleNamespace(cuda="12.6"),
        cuda=SimpleNamespace(
            is_available=lambda: True, get_device_name=lambda index: "Test GPU",
            get_device_capability=lambda index: (8, 6),
            get_device_properties=lambda index: SimpleNamespace(total_memory=24 * 1024**3),
            synchronize=lambda: None,
        ),
        ones=lambda *args, **kwargs: SimpleNamespace(add_=lambda value: None),
    ))

    runpy.run_path(str(Path(__file__).parents[1] / "handler.py"), run_name="__main__")

    assert events == ["start"]
    output = capsys.readouterr().out
    assert "Test GPU" in output
    assert "sm_86" in output
    assert "24.0 GiB" in output
    assert registered["handler"]({"input": {"task_type": "bad"}}) == {"input": {"task_type": "bad"}}
    assert events == ["start", "load_model"]


@pytest.mark.parametrize("cuda_version,available", [(None, False), ("12.6", False)])
def test_serverless_exits_with_clear_cuda_error(monkeypatch, capsys, cuda_version, available):
    monkeypatch.setitem(sys.modules, "runpod", SimpleNamespace(serverless=SimpleNamespace(start=lambda config: pytest.fail("serverless started without CUDA"))))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        __version__="2.7.1+cu126" if cuda_version else "2.7.1+cpu",
        version=SimpleNamespace(cuda=cuda_version),
        cuda=SimpleNamespace(is_available=lambda: available),
    ))

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(Path(__file__).parents[1] / "handler.py"), run_name="__main__")

    assert exc.value.code == 1
    assert "CUDA self-check failed" in capsys.readouterr().err


def test_serverless_exits_if_gpu_cannot_run_cuda_kernel(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "runpod", SimpleNamespace(serverless=SimpleNamespace(start=lambda config: pytest.fail("serverless started with unusable GPU"))))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        __version__="2.7.1+cu126", version=SimpleNamespace(cuda="12.6"),
        cuda=SimpleNamespace(
            is_available=lambda: True, get_device_name=lambda index: "Unsupported GPU",
            get_device_capability=lambda index: (12, 0),
            get_device_properties=lambda index: SimpleNamespace(total_memory=24 * 1024**3),
        ),
        ones=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no kernel image is available")),
    ))

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(Path(__file__).parents[1] / "handler.py"), run_name="__main__")

    assert exc.value.code == 1
    assert "no kernel image is available" in capsys.readouterr().err
