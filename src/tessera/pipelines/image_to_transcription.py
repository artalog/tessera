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


log = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)

@dataclass(frozen=True)
class PhotoTranscription:
    image_path: str

    @staticmethod
    def from_jpg_path(image_path):
        if not image_path.endswith(".jpeg") and not image_path.endswith(".jpg"):
            raise ValueError("Photo must be in JPEG format")
        return PhotoTranscription(image_path)

    @property
    def image_base64(self):
        with open(self.image_path, "rb") as f:
            log.info(f"Reading image: {self.image_path}")
            image_bytes = f.read()
            # image_bytes = _resize_image(image_bytes)
            image_base64 = _encode_image(image_bytes)

        return image_base64

    @property
    def has_transcription(self):
        # Check if there's a response file

        p = self._last_response_path
        return p is not None and os.path.exists(p)

    @property
    def has_annotation(self):
        return os.path.exists(self._annotation_path)

    @property
    def transcription(self):
        t = None
        if self.has_transcription:
            log.info(f"Reading response: {self._last_response_path}")

            if self._last_response_path.endswith(".txt"):
                with open(self._last_response_path, "r") as f:
                    t = f.read()
            elif self._last_response_path.endswith(".json"):
                # read json file
                with open(self._last_response_path, "r") as f:
                    response = json.load(f)
                    t = response["choices"][0]["message"]["content"]
            else:
                raise ValueError("Unknown file type for transcription")
        return t

    @property
    def annotation(self):
        t = None
        if self.has_annotation:
            log.info(f"Reading annotation: {self._annotation_path}")
            with open(self._annotation_path, "r") as f:
                t = f.read()
        return t

    @property
    def _annotation_path(self):
        image_name, _ = os.path.splitext(self.image_path)
        image_name = image_name.replace("all_extracted_images", "annotated")
        return image_name + ".txt"


    @property
    def _last_response_path(self):
        image_name, _ = os.path.splitext(self.image_path)
        p = image_name.replace("all_extracted_images", "transcribed")

        if not os.path.exists(p):
            return None

        # list all .json paths in the directory sorted
        json_files = [f for f in os.listdir(p) if f.endswith(".json") or f.endswith(".txt")]
        if not json_files:
            return None

        # sort by timestamp in name
        json_files.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))

        return os.path.join(p, json_files[-1])


    def save_response(self, response):
        image_name, _ = os.path.splitext(self.image_path)
        image_name = image_name.replace("all_extracted_images", "transcribed")
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        response_path = image_name + "/response_" + current_timestamp + ".json"

        os.makedirs(os.path.dirname(response_path), exist_ok=True)

        with open(response_path, "w") as f:
            f.write(response)

    @property
    def assistant_message(self):
        return {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": self.transcription,
                },
            ],
        }

    @property
    def user_message(self):
        text = "Transcribe the following image"
        if self.has_annotation:
            text += " by using the following human transcription as base:\n{self.annotation}"

        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": text,
                },
                _image_to_content(self.image_base64),
            ],
        }

    @property
    def system_message(self):
        annotation = self.annotation

        if not annotation:
            raise ValueError("Annotation must be provided for system message")

        return {
            "role": "user",
            "content": [
                _image_to_content(self.image_base64),
                {
                    "type": "text",
                    "text": f"Example of the best manual transcription by a human of the image above:\n{annotation}",
                },
            ],
        }


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
                    _image_to_content(base64_image)
                    for base64_image in base64_images[x : x + max_images_per_message]
                ],
            ],
        }
        for x in range(0, len(base64_images), max_images_per_message)
    ]


client = OpenAI()


def _encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")


def _resize_image(image_bytes, max_size=1024):
    with Image.open(BytesIO(image_bytes)) as img:
        img.thumbnail((max_size, max_size), Image.LANCZOS)

        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG")
        # save the image to file for testing
        with open("resized_image.jpg", "wb") as f:
            f.write(output_buffer.getvalue())

        return output_buffer.getvalue()


def _image_to_content(base64_image):
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
    }


def _load_images(images_dir):
    images = []
    for image_path in sorted(os.listdir(images_dir)):
        if not image_path.endswith(".jpeg") and not image_path.endswith(".jpg"):
            continue

        image = PhotoTranscription.from_jpg_path(os.path.join(images_dir, image_path))
        images.append(image)

    return images


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
    system_images = _load_images(annotation_path)
    user_images = _load_images(archive_path)

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
