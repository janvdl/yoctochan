from django import forms
from django.conf import settings
from django.template.defaultfilters import filesizeformat


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
            validate_post_image(image)

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


class CreatePostForm(forms.Form):
    poster_name = forms.CharField(
        max_length=64,
        required=False,
        label="Name",
        strip=True,
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
            validate_post_image(image)

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
