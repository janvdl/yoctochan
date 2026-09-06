from django import forms
from django.conf import settings
from django.template.defaultfilters import filesizeformat

from .imaging import convert_to_supported_format, strip_exif
from .moderation import BAN_DURATION_CHOICES
from .models import Report


def validate_post_image(image):
    """
    Validate an uploaded post image: enforce the file size limit and
    restrict to well-known raster formats. ``forms.ImageField`` has already
    confirmed the upload is a genuine, Pillow-readable image and attached the
    decoded image as ``image.image``.
    """
    if image.size > settings.MAX_IMAGE_SIZE:
        raise forms.ValidationError(
            "Image is too large (max %(limit)s)."
            % {"limit": filesizeformat(settings.MAX_IMAGE_SIZE)}
        )

    image_format = getattr(getattr(image, "image", None), "format", None)

    if image_format not in settings.ALLOWED_IMAGE_FORMATS:
        raise forms.ValidationError(
            "Unsupported image format. Allowed formats: JPG, PNG, GIF, WebP."
        )

    return image


def process_uploaded_image(image):
    """
    The full pipeline for a freshly-uploaded post image: convert a
    recognised-but-unsupported format (HEIC/HEIF) into one we accept,
    validate size and format, then strip EXIF metadata. Returns the image
    to actually save — which may not be the object passed in, if either
    step above replaced it — or raises ``ValidationError`` (via
    ``validate_post_image``) if it's still not acceptable.
    """
    converted = convert_to_supported_format(image)
    if converted is not None:
        image = converted

    validate_post_image(image)

    stripped = strip_exif(image)
    if stripped is not None:
        image = stripped

    return image


class CreateThreadForm(forms.Form):
    subject = forms.CharField(
        max_length=150,
        required=False,
        label="Subject",
        strip=True,
    )

    poster_name = forms.CharField(
        max_length=64,
        required=False,
        label="Name",
        strip=True,
        help_text="Add #password for a tripcode.",
    )

    content = forms.CharField(
        max_length=4_000,
        required=False,
        label="Message",
        strip=True,
        widget=forms.Textarea,
    )

    image = forms.ImageField(
        required=False,
        label="Image",
    )

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if image:
            image = process_uploaded_image(image)

        return image

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        image = cleaned_data.get("image")

        if not content and not image:
            self.add_error(
                "content",
                "Message cannot be empty unless an image is attached.",
            )

        return cleaned_data


class ReportForm(forms.Form):
    reason = forms.ChoiceField(
        choices=Report.Reason.choices,
        label="Reason",
    )

    detail = forms.CharField(
        max_length=500,
        required=False,
        label="Details (optional)",
        strip=True,
        widget=forms.Textarea,
    )


class BanForm(forms.Form):
    ip_address = forms.GenericIPAddressField(label="IP address")

    scope = forms.ChoiceField(label="Scope")

    reason = forms.CharField(
        max_length=500,
        label="Reason (shown to the user)",
        strip=True,
    )

    note = forms.CharField(
        max_length=2_000,
        required=False,
        label="Internal note",
        strip=True,
        widget=forms.Textarea,
    )

    duration = forms.ChoiceField(
        choices=BAN_DURATION_CHOICES,
        label="Duration",
    )

    delete_post = forms.BooleanField(
        required=False,
        label="Also delete the reported post",
    )

    def __init__(self, *args, scope_choices=None, from_post=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["scope"].choices = scope_choices or [("board", "This board only")]

        if not from_post:
            del self.fields["delete_post"]


class CreatePostForm(forms.Form):
    poster_name = forms.CharField(
        max_length=64,
        required=False,
        label="Name",
        strip=True,
        help_text="Add #password for a tripcode.",
    )

    content = forms.CharField(
        max_length=4_000,
        required=False,
        label="Message",
        strip=True,
        widget=forms.Textarea,
    )

    image = forms.ImageField(
        required=False,
        label="Image",
    )

    sage = forms.BooleanField(
        required=False,
        label="Sage (don't bump this thread)",
    )

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if image:
            image = process_uploaded_image(image)

        return image

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        image = cleaned_data.get("image")

        if not content and not image:
            self.add_error(
                "content",
                "Message cannot be empty unless an image is attached.",
            )

        return cleaned_data
