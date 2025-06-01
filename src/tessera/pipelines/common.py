from dataclasses import dataclass
import base64
import os
import io
import json
from datetime import datetime
import logging

from tessera.lake_client.files import Asset as FileAsset

log = logging.getLogger(__name__)


transcribed_asset = FileAsset("Archivos_Scan_RBML/transcribed")
annotated_asset = FileAsset("Archivos_Scan_RBML/annotated")
images_asset = FileAsset("Archivos_Scan_RBML/all_extracted_images")

def _encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

@dataclass(frozen=True)
class PhotoTranscription:
    archive: str
    page: int

    @property
    def image_base64(self):
        log.info(f"Reading image: {self.image_path}")
        image_bytes = images_asset.read(self.image_path).getvalue()
        # image_bytes = _resize_image(image_bytes)
        image_base64 = _encode_image(image_bytes)

        return image_base64

    @property
    def has_transcription(self):
        # Check if there's a response file

        p = self._last_response_path
        return p is not None

    @property
    def has_annotation(self):
        return annotated_asset.exists(self._annotation_path)


    @property
    def transcription(self) -> str | None:
        t = None
        if self.has_transcription:
            log.info(f"Reading response: {self._last_response_path}")

            if self._last_response_path.endswith(".txt"):
                t = io.TextIOWrapper(transcribed_asset.read(self._last_response_path)).read()
            elif self._last_response_path.endswith(".json"):
                response = json.load(transcribed_asset.read(self._last_response_path))
                t = response["choices"][0]["message"]["content"]
            else:
                raise ValueError("Unknown file type for transcription")
        return t

    @property
    def image_path(self) -> str:
        return os.path.join(self.archive, f"page_{self.page:03d}_img_001")


    @property
    def annotation(self) -> str | None:
        t = None
        if self.has_annotation:
            log.info(f"Reading annotation: {self._annotation_path}")
            t = io.TextIOWrapper(annotated_asset.read(self._annotation_path)).read()
        return t

    @property
    def _annotation_path(self):
        image_name, _ = os.path.splitext(self.image_path)
        return image_name + ".txt"


    @property
    def _last_response_path(self) -> str | None:
        p = self.image_path

        responses = transcribed_asset.list_dir(p)
        responses = [f for f in responses if f.startswith("response_")]

        if len(responses) == 0:
            return None

        # sort by timestamp in name
        responses.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))

        return os.path.join(p, responses[-1])


    def save_response(self, response):
        image_name, _ = os.path.splitext(self.image_path)
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        response_path = image_name + "/response_" + current_timestamp + ".json"

        transcribed_asset.write(response_path, response)


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
