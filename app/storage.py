from pathlib import Path


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
