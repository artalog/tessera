import sys
import tessera.pipelines.pdf_to_images as pdf_to_images

if __name__ == '__main__':
    from hamilton import driver

    # Use the first command-line argument as the PDF directory if provided.
    directory = sys.argv[1] if len(sys.argv) > 1 else "/path/to/pdf_folder"

    d = (
        driver.Builder()
        .with_modules(pdf_to_images)
        .with_cache()
        .build()
    )
    
    
    # Execute the pipeline, retrieving the aggregated image paths.
    results = d.execute(['all_extracted_images'], overrides={'data_directory': directory})
