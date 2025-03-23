import os
import sys
from tessera.pipelines import pdf_to_images, image_to_transcription, upload_gdrive
from hamilton import driver
from hamilton_sdk import adapters

directory = os.path.dirname(os.path.realpath(__file__)) + "/../../data/Archivos_Scan_RBML"


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
    .with_modules(upload_gdrive)
    .with_adapters(tracker)
    .with_cache()
    .build()
)


# Execute the pipeline, retrieving the aggregated image paths.
results = d.execute(['all_extracted_images'], overrides={'data_directory': directory})
extracted_images = results['all_extracted_images']

common_directories = []
for key, image_paths in extracted_images.items():
    common_directories.append(os.path.commonpath(image_paths))


annotation_path = directory + '/annotated/Folder 762'


results = d.execute(['all_transcribed_archives'], inputs={
    'archive_paths': common_directories,
    'annotation_path': annotation_path
})



results = d.execute(['upload_gdrive'], inputs={
    'image_folders': common_directories,
})
