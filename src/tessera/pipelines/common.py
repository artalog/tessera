from dataclasses import dataclass
import base64
from PIL import Image
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

def _encode_image(image_bytes: io.BytesIO) -> str:
    return base64.b64encode(image_bytes.getvalue()).decode("utf-8")


def _resize_image(image_bytes: io.BytesIO, max_size: int = 1800) -> io.BytesIO:
    with Image.open(image_bytes) as img:
        img.thumbnail((max_size,max_size), Image.LANCZOS)

        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG")
        return output_buffer

@dataclass
class PhotoTranscription:
    archive: str
    page: int

    @property
    def image_base64(self):
        image_path = self.image_path + ".jpeg"
        image_bytes = images_asset.read(image_path)
        image_bytes = _resize_image(image_bytes)
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
            p = self._last_response_path

            if p.endswith(".txt"):
                t = io.TextIOWrapper(transcribed_asset.read(p)).read()
            elif p.endswith(".json"):
                response = json.load(transcribed_asset.read(p))
                if "choices" in response:
                    t = response["choices"][0]["message"]["content"]
                if "output" in response:
                    t = response["output"][0]["content"][0]["text"]
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


    def save_response(self, response) -> str:
        image_name, _ = os.path.splitext(self.image_path)
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        response_path = image_name + "/response_" + current_timestamp + ".json"

        transcribed_asset.write(response_path, io.BytesIO(response.encode("utf-8")))
        return response_path


    @property
    def assistant_message(self):
        return {
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
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
                    "type": "input_text",
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
                    "type": "input_text",
                    "text": f"Example of the best manual transcription by a human of the image above:\n{annotation}",
                },
            ],
        }



def load_images(archive_name: str, asset: FileAsset = images_asset) -> list[PhotoTranscription]:
    images = []
    for image_path in sorted(asset.list_dir(archive_name)):
        # parse page number as int page_{self.page:03d}_img_001
        page_number = int(image_path.split("_")[1])

        image = PhotoTranscription(
            archive=archive_name.strip("/"),
            page=page_number,
        )
        images.append(image)

    return images


def image_to_content(base64_image):
    return {
        "type": "input_image",
        "image_url": f"data:image/jpeg;base64,{base64_image}",
    }
