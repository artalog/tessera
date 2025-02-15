import os
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

# ------------------------------
# CONFIGURATION
# ------------------------------

# Path to the service account JSON file
SERVICE_ACCOUNT_FILE = "credentials.json"

# Path to the local Git repo (root) that we want to scan for .txt files
LOCAL_REPO_PATH = "./data/Archivos_Scan_RBML/Archives"

# JSON file to store ID mappings (checked into your Git repo for history)
MAPPING_JSON_PATH = os.path.join(LOCAL_REPO_PATH, "drive_map.json")

DRIVE_PARENT_FOLDER_ID = "1eHiqnzJHjiB65_Vaz9CgmvYH_oyatwmC"


# ------------------------------
# MAIN LOGIC
# ------------------------------


def load_mapping():
    """
    Load the local JSON that stores folder/file IDs.
    Create a new empty structure if the file doesn't exist.
    """
    if os.path.exists(MAPPING_JSON_PATH):
        with open(MAPPING_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "folders": {},  # maps local folder path -> drive folder ID
            "files": {},  # maps local file path -> drive file (Doc) ID
        }


def save_mapping(mapping):
    """
    Save the updated mapping JSON to disk.
    """
    with open(MAPPING_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)


def create_folder_if_not_exists(drive_service, mapping, local_folder_path):
    """
    Ensure a matching folder in Drive exists for `local_folder_path`.
    Returns the drive folder ID.

    `local_folder_path` is a path *relative* to LOCAL_REPO_PATH, e.g. "" for top,
    "subfolder", "subfolder/nested", etc.
    """
    # If we already have a folder ID in the mapping, just return it
    if local_folder_path in mapping["folders"]:
        return mapping["folders"][local_folder_path]

    # We need to create a new folder in Drive
    folder_name = (
        os.path.basename(local_folder_path) if local_folder_path else LOCAL_REPO_PATH
    )
    if folder_name == LOCAL_REPO_PATH:
        # If local_folder_path == "", we can name it something like the repo root name
        folder_name = os.path.basename(os.path.abspath(LOCAL_REPO_PATH))

    # If there's a parent folder in the local structure, find its Drive ID for nesting
    parent_id = DRIVE_PARENT_FOLDER_ID

    if local_folder_path:
        # e.g. "some/subfolder" -> parent is "some"
        parent_local = os.path.dirname(local_folder_path)
        if parent_local:  # if not empty
            parent_id = create_folder_if_not_exists(
                drive_service, mapping, parent_local
            )
        else:
            # There's only one level, so the parent is DRIVE_PARENT_FOLDER_ID
            parent_id = DRIVE_PARENT_FOLDER_ID

    # Create the folder in Drive
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        folder_metadata["parents"] = [parent_id]

    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    folder_id = folder["id"]

    # Store in mapping
    mapping["folders"][local_folder_path] = folder_id
    save_mapping(mapping)  # Save immediately so partial progress is persisted
    return folder_id


def create_doc_if_not_exists(drive_service, mapping, local_file_path, text_content):
    """
    Create a new Google Doc with the contents of text_content if not already in mapping.
    Returns the doc ID.
    """
    if local_file_path in mapping["files"]:
        return mapping["files"][local_file_path]

    # Example doc name: filename without extension
    doc_name = os.path.splitext(os.path.basename(local_file_path))[0]

    # Find or create the folder in Drive for this file's directory
    parent_local_folder = os.path.dirname(local_file_path)
    folder_id = None
    if parent_local_folder:
        folder_id = create_folder_if_not_exists(
            drive_service, mapping, parent_local_folder
        )
    else:
        # The file is at the root of the repo
        folder_id = DRIVE_PARENT_FOLDER_ID

    # Build the metadata for a Google Doc
    file_metadata = {
        "name": doc_name,  # Document title
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    # The media body is our plain text
    media_body = MediaInMemoryUpload(
        text_content.encode("utf-8"), mimetype="text/plain", resumable=False
    )

    # Create the file
    new_file = (
        drive_service.files()
        .create(body=file_metadata, media_body=media_body, fields="id")
        .execute()
    )

    doc_id = new_file["id"]
    mapping["files"][local_file_path] = doc_id
    save_mapping(mapping)

    return doc_id


def main():
    # 1. Auth for Drive
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build("drive", "v3", credentials=creds)

    # 2. Load or create our mapping JSON
    mapping = load_mapping()

    # 3. Recursively walk LOCAL_REPO_PATH
    for root, dirs, files in os.walk(LOCAL_REPO_PATH):
        # Convert absolute path to path relative to LOCAL_REPO_PATH
        relative_dir = os.path.relpath(root, start=LOCAL_REPO_PATH)
        # If relative_dir is ".", treat it as ""
        if relative_dir == ".":
            relative_dir = ""

        for filename in files:
            if filename.lower().endswith(".txt"):
                local_file_path = os.path.join(relative_dir, filename)
                abs_file_path = os.path.join(root, filename)

                # Read the .txt content
                with open(abs_file_path, "r", encoding="utf-8") as f:
                    text_content = f.read()

                # Create or skip if doc already in mapping
                doc_id = create_doc_if_not_exists(
                    drive_service, mapping, local_file_path, text_content
                )
                print(f"[OK] {local_file_path} -> Doc ID: {doc_id}")

    print("Done. All .txt files processed.")


if __name__ == "__main__":
    main()
