import os
import sys
import fitz  # PyMuPDF


def data_directory() -> str:
    """
    Returns the path to the folder containing your PDFs.
    This default value can be overridden via the additional_namespace.
    """
    return "/path/to/pdf_folder"  # Default path if not provided via command-line.

def pdf_files(data_directory: str) -> list:
    """
    Scans the provided directory and returns a list of PDF file paths.
    """
    return [
        os.path.join(data_directory + "/pdf", f)
        for f in os.listdir(data_directory + "/pdf")
        if f.lower().endswith('.pdf')
    ]

def extract_images(data_directory: str, pdf_file: str) -> list:
    """
    Given a PDF file path, extracts all images embedded in the PDF.
    
    - If an output folder (named after the PDF without the .pdf extension) exists,
      extraction is skipped and the existing files are returned.
    - Otherwise, creates the folder, extracts images, saves them, and returns their paths.
    """
    output_folder = os.path.splitext(pdf_file)[0]
    output_folder = os.path.join(data_directory, "all_extracted_images", os.path.basename(output_folder))

    if os.path.exists(output_folder):
        print(f"Skipping extraction for {pdf_file} because {output_folder} already exists.")
        return [os.path.join(output_folder, f)
                for f in os.listdir(output_folder)
                if os.path.isfile(os.path.join(output_folder, f))]
    
    doc = fitz.open(pdf_file)
    os.makedirs(output_folder)
    extracted_paths = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        image_list = page.get_images(full=True)
        for image_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_filename = os.path.join(
                output_folder,
                f"page_{page_index + 1:03d}_img_{image_index + 1:03d}.{image_ext}",
            )
            with open(image_filename, "wb") as image_file:
                image_file.write(image_bytes)
            extracted_paths.append(image_filename)
    return extracted_paths

def all_extracted_images(data_directory: str, pdf_files: list) -> dict:
    """
    Iterates over all PDFs, extracts images from each (or skips if already done),
    and aggregates all extracted image file paths.
    """
    all_images = dict()
    for pdf_file in pdf_files:
        all_images[pdf_file] = extract_images(data_directory, pdf_file)
    return all_images
