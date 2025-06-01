from typing import Any
import os
import json
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from tessera.pipelines.common import load_images

# ------------------------------
# CONFIGURATION
# ------------------------------

# Path to the service account JSON file
SERVICE_ACCOUNT_FILE = "credentials.json"

# Path to the local Git repo (root) that we want to scan for .txt files
LOCAL_REPO_PATH = "./data/Archivos_Scan_RBML/gdrive"

DRIVE_PARENT_FOLDER_ID = "1eHiqnzJHjiB65_Vaz9CgmvYH_oyatwmC"


log = logging.getLogger(__name__)

_drive_service = None


def get_drive_service() -> Any:
    global _drive_service
    if _drive_service:
        return _drive_service

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


def create_folder(local_folder_path: str) -> dict:
    # We need to create a new folder in Drive
    folder_name = os.path.basename(local_folder_path)
    metadata_path = os.path.join(LOCAL_REPO_PATH, folder_name, "directory.json")

    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
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
        get_drive_service.files().create(body=folder_metadata, fields="id").execute()
    )
    folder_id = folder["id"]

    metadata = format_metadata(folder_name, folder_id, is_directory=True)

    # create directory metadata file
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


# get parent folder metadata from current path from directory.json
def get_parent_folder_metadata(local_file_path: str) -> dict | None:
    parent_folder_path = os.path.dirname(local_file_path)
    parent_metadata_path = os.path.join(parent_folder_path, "directory.json")

    if os.path.exists(parent_metadata_path):
        with open(parent_metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            return metadata

    return None


def create_doc(local_file_path: str, text_content: str) -> dict:
    doc_name = os.path.splitext(os.path.basename(local_file_path))[0]
    folder_name = os.path.basename(os.path.dirname(local_file_path))
    metadata_path = os.path.join(LOCAL_REPO_PATH, folder_name, f"{doc_name}.json")

    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            return metadata

    log.info(f"Uploading {doc_name} to Google Drive")

    folder_metadata = get_parent_folder_metadata(metadata_path)
    if not folder_metadata:
        raise ValueError(f"Could not find parent folder metadata for {local_file_path}")

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
        get_drive_service.files()
        .create(body=file_metadata, media_body=media_body, fields="id")
        .execute()
    )

    doc_id = new_file["id"]

    file_key = f"{folder_metadata['filename']}/{doc_name}"

    metadata = format_metadata(file_key, doc_id, is_directory=False)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def format_metadata(
    filename: str, transcription_google_drive_doc_id: str, is_directory: bool
) -> dict:
    return {
        "filename": filename,
        "is_directory": is_directory,
        "transcription_google_drive_doc_id": transcription_google_drive_doc_id,
    }


def upload_gdrive(image_folders: list[str]) -> list[dict]:
    # 1. Auth for Drive
    output = []
    for image_folder in image_folders:
        # check if directory metadta file exists at archive path
        out = create_folder(image_folder)
        output.append(out)

        # load images from archive path
        images = load_images(image_folder)
        for image in images:
            if not image.has_transcription:
                log.info(f"Skipping image without transcription: {image.image_path}")
                continue

            out = create_doc(image.image_path, image.transcription)
            output.append(out)

    return output
