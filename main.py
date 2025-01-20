import pdfplumber

def extract_images_with_pdfplumber(pdf_path, output_folder):
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages):
            for img_index, img in enumerate(page.images):
                xref = img["object_id"]
                image = pdf.streams.get(xref)
                with open(f"{output_folder}/page_{page_number+1}_img_{img_index+1}.jpg", "wb") as img_file:
                    img_file.write(image)

extract_images_with_pdfplumber("example.pdf", "output_images")

