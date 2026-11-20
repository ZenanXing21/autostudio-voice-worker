"""Download only public v2Pro inference assets to a persistent volume."""

import argparse
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download


def main():
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
    g2pw.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            parts = Path(entry.filename).parts
            if not parts or parts[0] != "G2PWModel" or any(part in {".", ".."} for part in parts):
                raise ValueError(f"unexpected G2PW archive path: {entry.filename}")
            target = g2pw.joinpath(*parts[1:])
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif len(parts) > 1:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("wb") as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
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
