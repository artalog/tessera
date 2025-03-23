from datetime import datetime
from dataclasses import dataclass
import json
import os
import sys
import base64
import logging
from PIL import Image
from openai import OpenAI
from io import BytesIO


from tessera.pipelines.common import PhotoTranscription, load_images, image_to_content


log = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)



def _images_to_messages(base64_images, max_images_per_message=4):
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
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


client = OpenAI()


def _resize_image(image_bytes, max_size=1024):
    with Image.open(BytesIO(image_bytes)) as img:
        img.thumbnail((max_size, max_size), Image.LANCZOS)

        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG")
        # save the image to file for testing
        with open("resized_image.jpg", "wb") as f:
            f.write(output_buffer.getvalue())

        return output_buffer.getvalue()



def _make_system_messages(images):
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
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
    log.info(len(json.dumps(messages)))
    return client.chat.completions.create(
        model="gpt-4.5-preview",
        max_completion_tokens=16383,
        messages=messages,
    )


MAX_PHOTOS_PER_CONVERSATION = 4


def _transcribe_images(system_images, user_images):
    messages = _make_system_messages(system_images)

    user_messages = []
    last_image = None
    for image in user_images:
        user_messages.append(image.user_message)
        if image.has_transcription:
            log.info(f"Skipping image: {image.image_path} because it has been transcribed")
            user_messages.append(image.assistant_message)
        else:
            last_image = image
            break

    if not last_image:
        raise ValueError("All images have been transcribed")

    log.info(f"Transcribing image: {last_image.image_path}")
    response = _request(
        messages + user_messages[len(user_messages) - MAX_PHOTOS_PER_CONVERSATION :]
    )

    return response, last_image


def transcribe_archive(annotation_path: str, archive_path: str) -> None:
    system_images = load_images(annotation_path)
    user_images = load_images(archive_path)

    log.info(f"Transcribing archive: {archive_path}")

    while True:
        try:
            response, image = _transcribe_images(system_images, user_images)
        except ValueError as e:
            return

        json_response = response.model_dump_json()
        image.save_response(json_response)

        transcription_text = response.choices[0].message.content
        log.info(transcription_text)


def all_transcribed_archives(annotation_path: str, archive_paths: list) -> dict:
    for archive_path in archive_paths:
        transcribe_archive(annotation_path, archive_path)

    return archive_paths
