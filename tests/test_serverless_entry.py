import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import app.handler as worker_module


def test_serverless_starts_before_loading_model_and_needs_no_api_token(monkeypatch):
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

    runpy.run_path(str(Path(__file__).parents[1] / "handler.py"), run_name="__main__")

    assert events == ["start"]
    assert registered["handler"]({"input": {"task_type": "bad"}}) == {"input": {"task_type": "bad"}}
    assert events == ["start", "load_model"]
