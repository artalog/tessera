from enum import StrEnum
import json
import os
from pathlib import Path

import pandas as pd
import logging

import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

from tessera.pipelines.common import PhotoTranscription
from tessera.lake_client.files import Asset as FileAsset, STORAGE_OPTIONS


log = logging.getLogger(__name__)
st.set_page_config(layout="wide")


qs = st.query_params.to_dict()  # gets a dict of query parameters
if "archive" not in st.session_state:
    st.session_state.archive = int(qs.get("archive", 764))

if "page" not in st.session_state:
    st.session_state.page = int(qs.get("page", 1))


def update_archive_qs():
    st.query_params.archive = st.session_state.archive
    st.query_params.page = 1


def update_page_qs():
    st.query_params.page = st.session_state.page

@st.cache_resource
def get_credentials():
    """Load service account info from Streamlit secrets and create credentials."""
    service_account_info_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if not service_account_info_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT environment variable not set.")

    service_account_info = json.loads(service_account_info_json)
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return creds

archive_index_asset = FileAsset("Archivos_Scan_RBML/archive_index")
images_asset = FileAsset("Archivos_Scan_RBML/all_extracted_images")
gdrive_asset = FileAsset("Archivos_Scan_RBML/gdrive")

@st.cache_resource
def get_archive_index() -> pd.DataFrame:
    df = pd.read_json(archive_index_asset.abs_path("index.json"), lines=True, dtype=object, storage_options=STORAGE_OPTIONS)
    return df


@st.cache_resource
def get_archives() -> pd.DataFrame:
    archive_dirs = images_asset.list_dir()
    archive_dirs = [x.rstrip("/") for x in archive_dirs if x.endswith("/")]

    # Convert to dataframe
    archive_dirs_df = pd.DataFrame(archive_dirs, columns=["archive"])
    # Add "document_number" column by parsing "Folder 764" to "764" integer
    archive_dirs_df["document_number"] = (
        archive_dirs_df["archive"].str.extract(r"(\d+)").astype(int)
    )
    return archive_dirs_df


def get_gdoc_html(doc_id: str) -> str:
    """
    Uses the Drive API to export the Doc as HTML, returning the HTML string.
    """
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    # Export the doc as HTML
    request = drive_service.files().export(fileId=doc_id, mimeType="text/html")
    html_content = request.execute()

    # It often returns bytes, so decode if needed
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8", errors="replace")

    return html_content


def get_transcription_key(archive: str, page: int) -> str:
    return f"{archive}/page_{page:03d}_img_001"


CSS_OVERRIDE = """
<style>
/* Target the main Streamlit Markdown container */
div[data-testid="stMarkdownContainer"] * {
        color: inherit !important;
        background-color: inherit !important;
        }
</style>
"""


class Source(StrEnum):
    GOOGLE_DOCS = "Google Docs"
    CHAT_GPT = "Chat GPT"


def _get_image_path(archive: str, page: int) -> Path:
    return f"{archive}/page_{page:03d}_img_001.jpeg"


@st.cache_data
def get_page_numbers(archive: str) -> list[int]:
    page_files = images_asset.list_dir(archive)
    # Filter for files that match the pattern "page_*.jpeg"
    page_files = [f for f in page_files if f.startswith("page_") and f.endswith(".jpeg")]
    # Extract page numbers from file names
    page_numbers = [int(f.split("_")[1]) for f in page_files]
    page_numbers = list(range(1, max(page_numbers) + 1))
    return page_numbers

@st.cache_data
def get_google_doc_id(archive: str, page: int) -> str | None:
    map_key = get_transcription_key(archive, page)
    doc_meta = json.load(gdrive_asset.read(map_key + ".json"))
    return doc_meta.get("transcription_google_drive_doc_id")


def main():
    # Load the mapping of local .txt -> Google Doc IDs
    archives = get_archives()
    archive_index = get_archive_index()
    # merge on "document_number"
    archives = pd.merge(archives, archive_index, on="document_number", how="left")

    # UI: Layout with two columns for selectboxes
    col_archive, col_page = st.columns([0.7, 0.3])

    documents = archives["document_number"].tolist()

    def _archive_selectbox_format_func(document_number: int) -> str:
        # Format the archive name with its description
        archive_info = archives[archives["document_number"] == document_number].iloc[0]
        return f"{archive_info['document_number']} - {archive_info['description']}"

    # Select a "archive"
    selected_archive = col_archive.selectbox(
        "Select an archive",
        documents,
        key="archive",
        on_change=update_archive_qs,
        format_func=_archive_selectbox_format_func,
    )

    archive_info = archives[archives["document_number"] == selected_archive].iloc[0]
    selected_archive = archive_info["archive"]

    page_numbers = get_page_numbers(selected_archive)

    # Select the page
    selected_page = col_page.selectbox(
        "Select a page", page_numbers, key="page", on_change=update_page_qs
    )

    cols = {
        "document_number": "Document Number",
        "year": "Year",
        "author": "Author",
        "description": "Description",
        "pages": "Original Pages",
    }

    # make markdown print out Value -> Key
    markdown = "\n".join(f"- **{v}**: {archive_info[k]}" for k, v in cols.items())
    st.markdown(markdown)

    # Prepare columns for Scan (image) and Transcription (text)
    col1, col2 = st.columns(2)

    # Left column: Display the image
    with col1:
        st.header("Scan")
        try:
            st.image(images_asset.read(_get_image_path(selected_archive, selected_page)))
        except Exception:
            log.exception("Error loading image")
            st.warning("No image found")

    # Right column: Display the transcription from Google Docs
    with col2:
        st.header("Transcription")
        t_source = st.selectbox("Source", [e.value for e in Source])

        match t_source:
            case Source.CHAT_GPT:
                # read the .txt file and display the transcription
                image = PhotoTranscription(archive=selected_archive, page=selected_page)
                if not image.has_transcription:
                    st.warning("No transcription found for this page.")
                    return

                st.markdown(image.transcription)
            case Source.GOOGLE_DOCS:

                try:
                    doc_id = get_google_doc_id(selected_archive, selected_page)
                    if not doc_id:
                        raise RuntimeError("No Google Doc ID found for this page.")

                    # A small horizontal layout for Refresh & Edit
                    refresh_col, edit_col = st.columns([0.15, 0.85])

                    with st.spinner("Loading transcription..."):
                        # If user clicks "Refresh", re-fetch from the Docs API
                        if refresh_col.button("Refresh"):
                            st.session_state[f"doc_{doc_id}"] = get_gdoc_html(doc_id)

                        # Get or fetch the doc text from session_state to persist across re-renders
                        doc_key = f"doc_{doc_id}"
                        if doc_key not in st.session_state:
                            # First load
                            st.session_state[doc_key] = get_gdoc_html(doc_id)

                        # Show an edit icon that links to the Google Doc in a new tab
                        edit_url = f"https://docs.google.com/document/d/{doc_id}/edit"
                        edit_icon = "✎"
                        edit_html = f"""
                        <p style="text-align:right; margin-top: 10px;">
                            <a href="{edit_url}" target="_blank" style="text-decoration:none;font-size:16px;">
                                {edit_icon} Edit
                            </a>
                        </p>
                        """
                        edit_col.markdown(CSS_OVERRIDE, unsafe_allow_html=True)
                        edit_col.markdown(edit_html, unsafe_allow_html=True)

                        # Finally, display the doc text
                        st.markdown(st.session_state[doc_key], unsafe_allow_html=True)


                except Exception:
                    log.exception("Error loading transcription metadata")
                    st.warning(f"No Google Doc found for page {selected_page}.")



if __name__ == "__main__":
    main()
