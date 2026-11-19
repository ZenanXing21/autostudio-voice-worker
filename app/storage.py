from pathlib import Path
import shutil


class LocalStorage:
    """Keep outputs on the worker's filesystem; voices already live in DATA_DIR."""

    def __init__(self, settings):
        self.output_dir = settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def upload(self, path: Path, key: str, private: bool = False) -> str:
        if private:
            return str(path)
        parts = key.split("/")
        if len(parts) < 3 or parts[0] != "outputs" or any(part in {"", ".", ".."} or "\\" in part for part in parts):
            raise ValueError("invalid output storage key")
        destination = self.output_dir.joinpath(*parts[1:])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        return str(destination)


class Storage:
    def __init__(self, settings, client=None):
        self.settings = settings
        if client is None:
            import boto3
            client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url or None, region_name=settings.s3_region)
        self.client = client

    def upload(self, path: Path, key: str, private: bool = False) -> str:
        self.client.upload_file(str(path), self.settings.s3_bucket, key)
        if private:
            return key
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.settings.s3_bucket, "Key": key}, ExpiresIn=self.settings.presign_seconds)
