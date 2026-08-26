from django import forms


class CreateThreadForm(forms.Form):
    subject = forms.CharField(
        max_length=200,
        required=False,
        label="Subject",
    )

    poster_name = forms.CharField(
        max_length=64,
        required=False,
        label="Name",
    )

    content = forms.CharField(
        max_length=10_000,
        widget=forms.Textarea,
        label="Message",
    )

class CreatePostForm(forms.Form):
    poster_name = forms.CharField(
        max_length=64,
        required=False,
        label="Name",
    )

    content = forms.CharField(
        max_length=10_000,
        widget=forms.Textarea,
        label="Message",
    )