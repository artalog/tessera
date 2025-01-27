import os
import json
from pathlib import Path

import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(layout="wide")

# ------------------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------------------
# 1. Path to your local "archive" directory containing subfolders and images
archive_dir = Path("./data/Archivos_Scan_RBML/Archives/")

# 2. Path to your drive_map.json (which maps .txt paths to Google Doc IDs)
DRIVE_MAP_PATH = archive_dir / Path("./drive_map.json")

def load_drive_map(json_path: Path):
    if not json_path.exists():
        raise FileNotFoundError(f"File not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_credentials():
    """Load service account info from Streamlit secrets and create credentials."""
    service_account_info = st.secrets["service_account"]
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return creds


def get_gdoc_html(doc_id: str) -> str:
    """
    Uses the Drive API to export the Doc as HTML, returning the HTML string.
    """
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    # Export the doc as HTML
    request = drive_service.files().export(fileId=doc_id, mimeType='text/html')
    html_content = request.execute()

    # It often returns bytes, so decode if needed
    if isinstance(html_content, bytes):
        html_content = html_content.decode('utf-8', errors='replace')

    return html_content 

CSS_OVERRIDE = """
<style>
/* Target the main Streamlit Markdown container */
div[data-testid="stMarkdownContainer"] * {
    color: inherit !important;
    background-color: inherit !important;
}
</style>
"""


def main():
    # Load the mapping of local .txt -> Google Doc IDs
    drive_map = load_drive_map(DRIVE_MAP_PATH)

    # Discover subdirectories under archive_dir
    archive_dirs = [x.name for x in archive_dir.iterdir() if x.is_dir()]

    # UI: Layout with two columns for selectboxes
    col_archive, col_page = st.columns([0.7, 0.3])

    # Select a "archive"
    selected_archive = col_archive.selectbox("Select an archive", archive_dirs)

    # Count the pages by scanning .jpeg files
    pattern = f"{selected_archive}/page_*.jpeg"
    n_pages = len(list(archive_dir.glob(pattern)))

    # Select the page
    selected_page = col_page.selectbox("Select a page", range(1, n_pages + 1))

    # Prepare columns for Scan (image) and Transcription (text)
    col1, col2 = st.columns(2)

    # Left column: Display the image
    with col1:
        st.header("Scan")
        try:
            image_path = archive_dir / selected_archive / f"page_{selected_page:03d}_img_001.jpeg"
            st.image(str(image_path))
        except Exception:
            st.warning("No image found")

    # Right column: Display the transcription from Google Docs
    with col2:
        st.header("Transcription")

        # Build the local .txt path key as stored in drive_map.json
        # Adjust if your drive_map keys differ.
        map_key = f"{selected_archive}/page_{selected_page:03d}_img_001.txt"

        if map_key not in drive_map["files"]:
            st.warning("No Google Doc mapping found for this page.")
        else:
            doc_id = drive_map["files"][map_key]

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

if __name__ == "__main__":
    main()

