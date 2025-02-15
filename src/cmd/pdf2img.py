import os
import sys
import fitz  # PyMuPDF


def extract_images_from_pdf(pdf_path, output_folder):
    pdf_document = fitz.open(pdf_path)
    for page_number in range(len(pdf_document)):
        page = pdf_document[page_number]
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            with open(
                f"{output_folder}/page_{page_number + 1:03d}_img_{img_index + 1:03d}.{image_ext}",
                "wb",
            ) as img_file:
                img_file.write(image_bytes)


if __name__ == "__main__":
    # first argument is the path to the PDF file
    pdf_path = sys.argv[1]

    # use same folder as the PDF file name but without the extension
    output_folder = os.path.splitext(pdf_path)[0]
    os.makedirs(output_folder, exist_ok=True)

    extract_images_from_pdf(sys.argv[1], output_folder)
