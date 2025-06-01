import os
import logging
from openai import OpenAI

from tessera.lake_client.files import Asset

from tessera.pipelines.common import load_images, image_to_content

annotated_asset = Asset("Archivos_Scan_RBML/annotated")
images_asset = Asset("Archivos_Scan_RBML/all_extracted_images")

log = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def _images_to_messages(base64_images, max_images_per_message=4):
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Transcribe the following image",
                },
                *[
                    image_to_content(base64_image)
                    for base64_image in base64_images[x : x + max_images_per_message]
                ],
            ],
        }
        for x in range(0, len(base64_images), max_images_per_message)
    ]


def _make_system_messages(images):
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": """You are an expert Spanish colonial era archivist of documents from 1772 in Puebla, Mexico. The documents are marriage dispensations for the racialized communities of New Spain. The documents were handwritten by notaries and archbishops. You are also an expert in reading cursive and able to spot similar characters.

Here are instructions for transcribing the photos of documents:
- A user will provide you with photos of the documents. You will transcribe the photos into text.
- Cross-reference Spanish dictionaries and historical documents to ensure accuracy of words.
- Transcribe exactly as written, preserve all spellings.
- Use human transcriptions as examples to guide transcribing.
- If uncertain, use '[...]'

The user will provide the best human-transcribed pages of documents from the same archive that should be used as examples to transcribe newly provided photos:""",
                },
            ],
        }
    ]

    messages += [image.system_message for image in images]
    return messages


def _request(messages):
    client = OpenAI()
    return client.responses.create(
        model="gpt-4.1",
        input=messages,
    )


MAX_PHOTOS_PER_CONVERSATION = 4

out_asset = Asset("Archivos_Scan_RBML/gdrive")

def _transcribe_images(system_images, user_images):
    user_messages = []
    last_image = None
    for image in user_images:
        user_messages.append(image.user_message)
        if image.has_transcription:
            log.info(
                f"Skipping image: {image.image_path} because it has been transcribed"
            )
            user_messages.append(image.assistant_message)
        else:
            last_image = image
            break

    if not last_image:
        return None, None

    log.info(f"Transcribing image: {last_image.image_path}")
    messages = _make_system_messages(system_images)
    response = _request(
        messages + user_messages[len(user_messages) - MAX_PHOTOS_PER_CONVERSATION :]
    )

    return response, last_image


gdrive_asset = Asset("Archivos_Scan_RBML/gdrive")

def all_transcribed_archives(annotated_asset: str, images_asset: str, archive_folder: str) -> list[str]:
    metadata_path = os.path.join(archive_folder, "directory.json")
    if gdrive_asset.exists(metadata_path):
        log.info("GDrive metadata found, skipping transcription.")
        return []


    system_images = load_images(archive_folder, Asset(annotated_asset))
    user_images = load_images(archive_folder, Asset(images_asset))

    log.info(f"Transcribing {len(user_images)} images from {archive_folder}")

    out = []
    while True:
        response, image = _transcribe_images(system_images, user_images)
        if response is None:
            log.info("No more images to transcribe.")
            break

        json_response = response.model_dump_json()
        out_path = image.save_response(json_response)
        out.append(out_path)

        transcription_text = response.output[0].content[0].text
        log.info(transcription_text)

    return out
