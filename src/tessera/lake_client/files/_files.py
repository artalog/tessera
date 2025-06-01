
from dataclasses import dataclass
import os
import io
from pathlib import Path

import boto3

STORAGE_OPTIONS = {
    "key": os.environ["OCI_ACCESS_KEY"],
    "secret": os.environ["OCI_SECRET_KEY"],
    "client_kwargs": {
        "endpoint_url": os.environ["OCI_OBJECT_STORAGE_ENDPOINT_URL"],
        "region_name": os.environ["OCI_REGION"],
    },
}


s3 = boto3.client(
    "s3", 
    aws_access_key_id=os.environ["OCI_ACCESS_KEY"],
    aws_secret_access_key=os.environ["OCI_SECRET_KEY"],
    region_name=os.environ["OCI_REGION"],
    endpoint_url=os.environ["OCI_OBJECT_STORAGE_ENDPOINT_URL"],
)


@dataclass
class AssetKey:
    _components: list[str]

    @staticmethod
    def from_string(key: str) -> "AssetKey":
        components = key.split("/")
        return AssetKey(components)


AssetKeyLike = AssetKey | str

def _asset_key_like_to_asset_key(key: AssetKeyLike) -> AssetKey:
    if isinstance(key, AssetKey):
        return key
    elif isinstance(key, str):
        return AssetKey.from_string(key)
    else:
        raise TypeError(f"Unsupported type for asset key: {type(key)}")


FILES_PREFIX = "files"

@dataclass
class Asset:
    key: AssetKeyLike


    def _s3_key(self, file_path: str | Path) -> str:
        if isinstance(file_path, Path):
            file_path = str(file_path)

        key = _asset_key_like_to_asset_key(self.key)
        file_path = file_path.lstrip("/")
        key = [FILES_PREFIX] + key._components + [file_path]

        out = "/".join(key)
        return out

    def abs_path(self, file_path: str | Path = "") -> str:
        bucket_name = os.environ["OCI_OBJECT_STORAGE_BUCKET_NAME"]
        return f"s3://{bucket_name}/{self._s3_key(file_path)}"

    def exists(self, file_path: str | Path) -> bool:
        key = self._s3_key(file_path)
        try:
            s3.head_object(
                Bucket=os.environ["OCI_OBJECT_STORAGE_BUCKET_NAME"],
                Key=key,
            )
            return True
        except s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise e


    def list_dir(self, file_path: str | Path = "") -> list[str]:
        paginator = s3.get_paginator("list_objects_v2")
        key_prefix = self._s3_key(file_path)
        if not key_prefix.endswith("/"):
            key_prefix += "/"

        pages = paginator.paginate(
            Bucket=os.environ["OCI_OBJECT_STORAGE_BUCKET_NAME"],
            Prefix=key_prefix,
            Delimiter="/",
        )

        file_list = []
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    file_list.append(obj["Key"])
            if "CommonPrefixes" in page:
                for prefix in page["CommonPrefixes"]:
                    file_list.append(prefix["Prefix"])



        file_list = [
            f.replace(key_prefix, "", 1) for f in file_list
        ]

        return file_list


    def read(self, file_path: str | Path) -> io.BytesIO:
        key = self._s3_key(file_path)
        data = io.BytesIO()
        s3.download_fileobj(
           Bucket=os.environ["OCI_OBJECT_STORAGE_BUCKET_NAME"],
           Key=key,
           Fileobj=data,
        )
        data.seek(0)
        return data


    def write(self, file_path: str | Path, data) -> None:
        key = self._s3_key(file_path)
        s3.upload_fileobj(
            Fileobj=data,
            Bucket=os.environ["OCI_OBJECT_STORAGE_BUCKET_NAME"],
            Key=key,
        )


