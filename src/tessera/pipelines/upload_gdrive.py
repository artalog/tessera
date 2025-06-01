import io
import os
import json
import logging
from typing import Any
from functools import cache

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from tessera.pipelines.common import load_images
from tessera.lake_client.files import Asset

# ------------------------------
# CONFIGURATION
# ------------------------------

# Path to the service account JSON file
SERVICE_ACCOUNT_FILE = "credentials.json"

# Path to the local Git repo (root) that we want to scan for .txt files

DRIVE_PARENT_FOLDER_ID = "1eHiqnzJHjiB65_Vaz9CgmvYH_oyatwmC"


log = logging.getLogger(__name__)

_drive_service = None


out_asset = Asset("Archivos_Scan_RBML/gdrive")

def get_drive_service() -> Any:
    global _drive_service
    if _drive_service:
        return _drive_service

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


# get parent folder metadata from current path from directory.json
@cache
def get_folder_metadata(folder_path: str) -> dict | None:
    metadata_path = os.path.join(folder_path, "directory.json")

    if out_asset.exists(metadata_path):
        metadata = json.load(out_asset.read(metadata_path))
        return metadata

    return None


def create_folder(folder_path: str) -> dict:
    folder_name = folder_path.strip("/")
    metadata_path = os.path.join(folder_name, "directory.json")

    metadata = get_folder_metadata(folder_path)
    if metadata:
        log.info(f"Folder metadata already exists for {folder_name}")
        return metadata

    # If there's a parent folder in the local structure, find its Drive ID for nesting
    parent_id = DRIVE_PARENT_FOLDER_ID

    # Create the folder in Drive
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        folder_metadata["parents"] = [parent_id]

    folder = (
        get_drive_service().files().create(body=folder_metadata, fields="id").execute()
    )
    folder_id = folder["id"]

    metadata = format_metadata(folder_name, folder_id, is_directory=True)

    out_asset.write(metadata_path, io.BytesIO(json.dumps(metadata, indent=2).encode('utf-8')))

    return metadata




def create_doc(file_path: str, text_content: str) -> dict:
    doc_name = os.path.splitext(os.path.basename(file_path))[0]
    folder_name = os.path.basename(os.path.dirname(file_path))

    metadata_path = os.path.join(folder_name, f"{doc_name}.json")

    if out_asset.exists(metadata_path):
        metadata = json.load(out_asset.read(metadata_path))
        return metadata

    log.info(f"Uploading {doc_name} to Google Drive")

    folder_metadata = get_folder_metadata(folder_name)
    if not folder_metadata:
        raise ValueError(f"Could not find parent folder metadata for {file_path}")

    # Build the metadata for a Google Doc
    file_metadata = {
        "name": doc_name,  # Document title
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_metadata["transcription_google_drive_doc_id"]],
    }

    # The media body is our plain text
    media_body = MediaInMemoryUpload(
        text_content.encode("utf-8"), mimetype="text/plain", resumable=False
    )

    # Create the file
    new_file = (
        get_drive_service().files()
        .create(body=file_metadata, media_body=media_body, fields="id")
        .execute()
    )

    doc_id = new_file["id"]

    file_key = f"{folder_metadata['filename']}/{doc_name}"

    metadata = format_metadata(file_key, doc_id, is_directory=False)
    out_asset.write(metadata_path, io.BytesIO(json.dumps(metadata, indent=2).encode('utf-8')))

    return metadata


def format_metadata(
    filename: str, transcription_google_drive_doc_id: str, is_directory: bool
) -> dict:
    return {
        "filename": filename,
        "is_directory": is_directory,
        "transcription_google_drive_doc_id": transcription_google_drive_doc_id,
    }

def upload_archive_to_gdrive(archive_folder: str) -> list[str]:
    # check if directory metadta file exists at archive path
    output = []
    out = create_folder(archive_folder)
    output.append(out)

    # load images from archive path
    images = load_images(archive_folder)
    for image in images:
        if not image.has_transcription:
            log.info(f"Skipping image without transcription: {image.image_path}")
            continue

        out = create_doc(image.image_path, image.transcription)
        output.append(out)
    return output
