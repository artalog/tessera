import os
import sys
import tessera.pipelines.pdf_to_images as pdf_to_images
import tessera.pipelines.image_to_transcription as image_to_transcription

from hamilton import driver
from hamilton_sdk import adapters

# Use the first command-line argument as the PDF directory if provided.
directory = "../../data/Archivos_Scan_RBML"

tracker = adapters.HamiltonTracker(
   project_id=1,
   username="timoha",
   dag_name="tessera_transcribe",
   tags={"environment": "DEV", "team": "MY_TEAM", "version": "X"},
)

d = (
    driver.Builder()
    .with_modules(pdf_to_images)
    .with_modules(image_to_transcription)
    .with_adapters(tracker)
    .with_cache()
    .build()
)


# Execute the pipeline, retrieving the aggregated image paths.
results = d.execute(['all_extracted_images'], overrides={'data_directory': directory})

# each value in results contain list of all images extracted (full paths), aggreage a list of common
# directories
common_directories = []
for image_paths in results.values():
    common_directories.append(os.path.commonpath(image_paths))



annotation_path = directory + '/annotated/Folder 762'

    


results = d.execute(['all_transcribed_archives'], inputs={
    'archive_paths': common_directories,
    'annotation_path': annotation_path
})
