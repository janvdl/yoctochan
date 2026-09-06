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


# Formats that carry EXIF the way a camera or phone would (GPS, make/model,
# timestamps, ...) and that Pillow can safely re-encode without losing
# anything but that metadata. GIF is deliberately excluded: it doesn't carry
# EXIF the same way, and re-encoding risks dropping animation frames.
_EXIF_BEARING_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


def strip_exif(image_field):
    """
    Re-encode an uploaded image without its EXIF metadata — GPS
    coordinates, camera make/model/serial, timestamps — a real
    deanonymisation risk on a board where every other identifying signal
    (poster IP, name) is already deliberately kept private or hidden.
    Orientation is baked into the pixels first so dropping the tag doesn't
    leave the image sideways.

    Returns ``ContentFile`` ready to replace the upload, or ``None`` when
    there's nothing to do: the format doesn't carry EXIF the way we handle
    here, there's no EXIF present, or the file can't be re-decoded (in
    which case validation elsewhere will have already rejected it).
    """
    try:
        image_field.open("rb")
        data = image_field.read()
    finally:
        image_field.seek(0)

    try:
        with Image.open(io.BytesIO(data)) as img:
            image_format = img.format

            if image_format not in _EXIF_BEARING_FORMATS or not img.getexif():
                return None

            img = ImageOps.exif_transpose(img)

            save_kwargs = {}
            if image_format == "JPEG":
                img = img.convert("RGB")
                save_kwargs.update(quality=95, optimize=True)
            elif image_format == "PNG":
                save_kwargs["optimize"] = True

            buffer = io.BytesIO()
            img.save(buffer, format=image_format, **save_kwargs)
    except (OSError, ValueError):
        return None

    return ContentFile(buffer.getvalue(), name=Path(image_field.name).name)


# Recognised-but-unsupported upload formats we convert rather than reject,
# and what to convert them into. Currently just HEIC/HEIF, the default
# photo format on modern iPhones — without this, every iPhone photo shot
# with default camera settings would bounce off "Unsupported image format".
_CONVERTIBLE_FORMATS = {"HEIF": "JPEG"}


def convert_to_supported_format(image_field):
    """
    Convert an upload in a recognised-but-unsupported format into one this
    app actually accepts (see ``_CONVERTIBLE_FORMATS``). Returns a
    replacement upload — with a genuine ``.image`` attribute set, the same
    way Django's own ``forms.ImageField`` sets one, so the caller's
    format/size validation can inspect it exactly like any other upload —
    or ``None`` when there's nothing to convert: the format is already
    supported, or it's not one this function knows how to handle (existing
    validation will reject it as before).
    """
    source = getattr(image_field, "image", None)
    target_format = _CONVERTIBLE_FORMATS.get(getattr(source, "format", None))

    if target_format is None:
        return None

    converted = source.convert("RGB")
    # Image.convert() returns a plain new image with no .format of its own
    # (it's not the file that was decoded) — set it explicitly so the
    # caller's format check (which reads image.image.format) sees the
    # format we're actually about to save, not None.
    converted.format = target_format

    buffer = io.BytesIO()
    converted.save(buffer, format=target_format, quality=92)

    extension = _FORMAT_EXTENSIONS[target_format]
    stem = Path(image_field.name).stem
    content = ContentFile(buffer.getvalue(), name=f"{stem}.{extension}")
    content.image = converted
    content.content_type = f"image/{extension}"

    return content
