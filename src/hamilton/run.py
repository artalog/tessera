import os
from tessera.pipelines import (
    pdf_to_images,
    image_to_transcription,
    upload_gdrive,
    archive_index_to_json,
)
from hamilton import driver

from tessera.lake_client.files import Asset

ASSET_PREFIX = "Archivos_Scan_RBML"

directory = (
    os.path.dirname(os.path.realpath(__file__)) + "/../../data/Archivos_Scan_RBML"
)


# tracker = adapters.HamiltonTracker(
#    project_id=1,
#    username="timoha",
#    dag_name="tessera_transcribe",
#    tags={"environment": "DEV", "team": "MY_TEAM", "version": "X"},
# )

d = (
    driver.Builder()
    .with_modules(pdf_to_images)
    .with_modules(image_to_transcription)
    .with_modules(upload_gdrive)
    .with_modules(archive_index_to_json)
    # .with_adapters(tracker)
    # .with_cache()
    .build()
)


# results = d.execute(
#     ["archive_index_to_json"],
#     inputs={
#         "asset": ASSET_PREFIX + "/archive_index",
#     },
# )


for archive in Asset("Archivos_Scan_RBML/all_extracted_images").list_dir():
    print(f"Processing archive: {archive}")
    results = d.execute(
        ["all_transcribed_archives"],
        inputs={
            "annotated_asset": "Archivos_Scan_RBML/annotated",
            "images_asset": "Archivos_Scan_RBML/all_extracted_images",
            "archive_folder": archive,
        },
    )
    results = d.execute(
        ["upload_archive_to_gdrive"],
        inputs={
            "archive_folder": archive,
        },
    )


# Execute the pipeline, retrieving the aggregated image paths.
# results = d.execute(["all_extracted_images"], overrides={"data_directory": directory})
# extracted_images = results["all_extracted_images"]
#
# common_directories = []
# for key, image_paths in extracted_images.items():
#     if len(image_paths) > 1:
#         common_directories.append(os.path.commonpath(image_paths))
#     else:
#         common_directories.append(os.path.dirname(image_paths[0]))
#
#
# annotation_path = directory + "/annotated/Folder 762"
#
# for common_directory in common_directories:
#     results = d.execute(
#         ["all_transcribed_archives"],
#         inputs={
#             "archive_paths": [common_directory],
#             "annotation_path": annotation_path,
#         },
#     )
#
#     results = d.execute(
#         ["upload_gdrive"],
#         inputs={
#             "image_folders": [common_directory],
#         },
#     )
