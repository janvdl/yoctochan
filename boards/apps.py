from django.apps import AppConfig


class BoardsConfig(AppConfig):
    name = 'boards'

    def ready(self):
        # Registers HEIC/HEIF support with Pillow, so an upload straight off
        # an iPhone can be opened at all (see boards/imaging.py's
        # convert_to_supported_format, which turns it into a JPEG).
        import pillow_heif

        pillow_heif.register_heif_opener()
