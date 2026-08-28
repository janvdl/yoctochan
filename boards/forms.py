from django import forms


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
        required=True,
        label="Message",
        strip=True,
        widget=forms.Textarea,
    )

    def clean_content(self):
        content = self.cleaned_data["content"]

        if not content.strip():
            raise forms.ValidationError(
                "Message cannot be empty."
            )

        return content


class CreatePostForm(forms.Form):
    poster_name = forms.CharField(
        max_length=64,
        required=False,
        label="Name",
        strip=True,
    )

    content = forms.CharField(
        max_length=4_000,
        required=True,
        label="Message",
        strip=True,
        widget=forms.Textarea,
    )

    def clean_content(self):
        content = self.cleaned_data["content"]

        if not content.strip():
            raise forms.ValidationError(
                "Message cannot be empty."
            )

        return content