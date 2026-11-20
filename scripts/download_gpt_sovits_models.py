"""Download only public v2Pro inference assets to a persistent volume."""

import argparse
import zipfile
from pathlib import Path, PurePosixPath

def extract_g2pw(archive_path: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        entries = [(entry, PurePosixPath(entry.filename).parts) for entry in archive.infolist()]
        models = [parts for _, parts in entries if parts and parts[-1] == "g2pW.onnx"]
        if len(models) != 1:
            raise ValueError("G2PW archive must contain exactly one g2pW.onnx")
        prefix = models[0][:-1]
        for entry, parts in entries:
            if not parts or any(part in {".", ".."} for part in parts):
                raise ValueError(f"unsafe G2PW archive path: {entry.filename}")
            if parts[:len(prefix)] != prefix:
                continue
            relative = parts[len(prefix):]
            if not relative:
                continue
            target = destination.joinpath(*relative)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("wb") as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)


def main():
    from huggingface_hub import hf_hub_download, snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, default=Path("/runpod-volume/gpt-sovits"))
    args = parser.parse_args()
    root = args.model_dir.resolve()
    pretrained = root / "pretrained_models"
    pretrained.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id="lj1995/GPT-SoVITS",
        allow_patterns=[
            "chinese-roberta-wwm-ext-large/*",
            "chinese-hubert-base/*",
            "sv/pretrained_eres2netv2w24s4ep4.ckpt",
        ],
        local_dir=pretrained,
    )
    archive_path = Path(hf_hub_download(
        repo_id="XXXXRT/GPT-SoVITS-Pretrained",
        filename="G2PWModel.zip",
        local_dir=root,
    ))
    g2pw = root / "G2PWModel"
    extract_g2pw(archive_path, g2pw)
    required = [
        pretrained / "chinese-roberta-wwm-ext-large",
        pretrained / "chinese-hubert-base",
        pretrained / "sv/pretrained_eres2netv2w24s4ep4.ckpt",
        g2pw / "g2pW.onnx",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("public GPT-SoVITS assets missing after download: " + ", ".join(missing))
    print(f"Public GPT-SoVITS assets ready in {root}")


if __name__ == "__main__":
    main()
