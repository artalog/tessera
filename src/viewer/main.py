import os
import streamlit as st
from pathlib import Path

st.set_page_config(layout="wide")



chisme_dir = Path("./data/Archivos_Scan_RBML/Chisme/")

# get directories under chime
chisme_dirs = [x.name for x in chisme_dir.iterdir() if x.is_dir()]

col_chisme, col_page = st.columns([0.7, 0.3])

selected_chisme = col_chisme.selectbox("Select a chisme", chisme_dirs)

# get number of files with prefix page_n of jpeg
n_pages = len(list(chisme_dir.glob(f"{selected_chisme}/page_*.jpeg")))


# select page via dropdown
selected_page = col_page.selectbox("Select a page", range(1, n_pages + 1))

col1, col2 = st.columns(2)


def format_page_name(page):
    return f"{page:03d}"

with col1:
    st.header("Scan")
    try:
        st.image(f"{chisme_dir}/{selected_chisme}/page_{selected_page:03d}_img_001.jpeg")
    except:
        st.warning("No image found")

with col2:
    st.header("Transcription")

    try:
        st.write(Path(f"{chisme_dir}/{selected_chisme}/page_{selected_page:03d}_img_001.txt").read_text())
    except:
        st.warning("No transcription found")
