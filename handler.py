import runpod

from app.handler import Worker


worker = Worker()
runpod.serverless.start({"handler": worker.handle})
