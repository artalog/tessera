from dataclasses import dataclass
import base64
import os
import json
from datetime import datetime
import logging


log = logging.getLogger(__name__)



def _encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

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
                image_to_content(self.image_base64),
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
                image_to_content(self.image_base64),
                {
                    "type": "text",
                    "text": f"Example of the best manual transcription by a human of the image above:\n{annotation}",
                },
            ],
        }



def load_images(images_dir):
    images = []
    for image_path in sorted(os.listdir(images_dir)):
        if not image_path.endswith(".jpeg") and not image_path.endswith(".jpg"):
            continue

        image = PhotoTranscription.from_jpg_path(os.path.join(images_dir, image_path))
        images.append(image)

    return images


def image_to_content(base64_image):
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
    }
