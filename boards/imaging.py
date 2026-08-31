import io
from pathlib import Path

from PIL import Image, ImageOps

from django.conf import settings
from django.core.files.base import ContentFile


# Pillow format -> thumbnail file extension.
_FORMAT_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "GIF": "gif",
    "WEBP": "webp",
}


def build_thumbnail(image_field):
    """
    Build a bounded thumbnail for an uploaded post image.

    Returns ``(ContentFile, filename, width, height)`` ready to hand to
    ``ImageField.save(...)``, or ``None`` when the source already fits within
    ``settings.THUMBNAIL_SIZE`` or cannot be processed. Animated GIFs are
    reduced to their first frame.
    """
    max_size = settings.THUMBNAIL_SIZE

    try:
        image_field.open("rb")
        data = image_field.read()
    finally:
        image_field.seek(0)

    try:
        with Image.open(io.BytesIO(data)) as img:
            out_format = img.format if img.format in _FORMAT_EXTENSIONS else "PNG"

            # Honour EXIF orientation before measuring/resizing.
            img = ImageOps.exif_transpose(img)

            if img.width <= max_size[0] and img.height <= max_size[1]:
                return None

            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            save_kwargs = {}

            if out_format == "JPEG":
                img = img.convert("RGB")
                save_kwargs.update(quality=85, optimize=True)
            elif out_format == "GIF":
                # A static first frame is enough for a thumbnail; PNG keeps it sharp.
                img = img.convert("RGBA")
                out_format = "PNG"
            elif out_format == "PNG":
                save_kwargs["optimize"] = True

            img.save(buffer, format=out_format, **save_kwargs)
            width, height = img.size
    except (OSError, ValueError):
        return None

    stem = Path(image_field.name).stem
    filename = f"{stem}_thumb.{_FORMAT_EXTENSIONS[out_format]}"

    return ContentFile(buffer.getvalue()), filename, width, height
