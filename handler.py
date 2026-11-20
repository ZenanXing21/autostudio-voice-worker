import runpod

from app.handler import handler


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
