"""
Image Storage Service

Handles saving AI-generated images to local disk.
"""

import base64
import uuid
from pathlib import Path

from app.core.config import get_settings, BASE_DIR


def get_generated_image_dir() -> Path:
    """Return the absolute path to the generated images directory."""
    settings = get_settings()
    raw = Path(settings.GENERATED_IMAGE_DIR)
    if raw.is_absolute():
        return raw
    return (BASE_DIR / raw).resolve()


def ensure_generated_image_dir() -> Path:
    """Create the generated images directory if it does not exist."""
    image_dir = get_generated_image_dir()
    image_dir.mkdir(parents=True, exist_ok=True)
    return image_dir


def save_generated_image(b64_data: str, mime_type: str = "image/png") -> tuple[str, str]:
    """
    Decode a base64 image and save it to disk.

    Returns:
        (absolute_path_str, mime_type)
    """
    image_dir = ensure_generated_image_dir()

    extension = "png" if "png" in mime_type else "jpeg"
    filename = f"{uuid.uuid4().hex}_image.{extension}"
    image_path = image_dir / filename

    print("[image_storage] Saving generated image:", image_path)

    image_bytes = base64.b64decode(b64_data)
    image_path.write_bytes(image_bytes)

    print("[image_storage] Image saved successfully:", image_path)

    return str(image_path), mime_type
