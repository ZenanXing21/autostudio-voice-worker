import zipfile

import pytest

from scripts.download_gpt_sovits_models import extract_g2pw


def test_extract_g2pw_accepts_versioned_archive_root(tmp_path):
    archive = tmp_path / "g2pw.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("G2PWModel_1.1/g2pW.onnx", b"model")
        output.writestr("G2PWModel_1.1/config.json", b"{}")
    destination = tmp_path / "G2PWModel"

    extract_g2pw(archive, destination)

    assert (destination / "g2pW.onnx").read_bytes() == b"model"
    assert (destination / "config.json").read_bytes() == b"{}"


def test_extract_g2pw_rejects_traversal(tmp_path):
    archive = tmp_path / "g2pw.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("G2PWModel/g2pW.onnx", b"model")
        output.writestr("G2PWModel/../outside.txt", b"bad")

    with pytest.raises(ValueError, match="unsafe"):
        extract_g2pw(archive, tmp_path / "G2PWModel")

    assert not (tmp_path / "outside.txt").exists()
