import shutil
import tempfile
from io import BytesIO

from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Board, Post, Thread


def make_upload(name="test.png", image_format="PNG", size=(400, 300)):
    buffer = BytesIO()
    Image.effect_noise(size, 40).convert("RGB").save(buffer, format=image_format)
    buffer.seek(0)

    return SimpleUploadedFile(
        name,
        buffer.read(),
        content_type=f"image/{image_format.lower()}",
    )


class HomepageTests(TestCase):
    def test_lists_active_boards_only(self):
        active_board = Board.objects.create(
            slug="test",
            name="Test Board",
            description="An active board.",
        )
        Board.objects.create(
            slug="hidden",
            name="Hidden Board",
            is_active=False,
        )

        response = self.client.get(reverse("homepage"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/test/ - Test Board")
        self.assertContains(response, "An active board.")
        self.assertNotContains(response, "Hidden Board")
        self.assertContains(response, reverse("board", args=[active_board.slug]))


class BoardSettingsTests(TestCase):
    def test_content_settings_have_safe_defaults(self):
        board = Board.objects.create(
            slug="test",
            name="Test Board",
        )

        self.assertFalse(board.allows_nsfw)
        self.assertTrue(board.allows_images)


class CatalogueTests(TestCase):
    def test_catalogue_shows_op_and_limited_recent_replies(self):
        board = Board.objects.create(
            slug="test",
            name="Test Board",
            catalogue_replies=2,
        )
        thread = Thread.objects.create(board=board)
        op = Post.objects.create(thread=thread, content="Original post")
        first_reply = Post.objects.create(thread=thread, content="First reply")
        second_reply = Post.objects.create(thread=thread, content="Second reply")
        third_reply = Post.objects.create(thread=thread, content="Third reply")
        Post.objects.create(
            thread=thread,
            content="Deleted reply",
            deleted=True,
        )

        response = self.client.get(reverse("board", args=[board.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, op.content)
        self.assertNotContains(response, first_reply.content)
        self.assertContains(response, second_reply.content)
        self.assertContains(response, third_reply.content)
        self.assertNotContains(response, "Deleted reply")
        self.assertEqual(response.context["page_obj"][0].post_count, 4)
        self.assertContains(response, "View full thread")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")

    def test_create_thread_with_image(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "look at this", "image": make_upload()},
        )

        self.assertEqual(response.status_code, 302)

        post = Post.objects.get()
        self.assertTrue(post.image.name.endswith(".png"))
        self.assertTrue(post.image.storage.exists(post.image.name))
        self.assertEqual((post.image_width, post.image_height), (400, 300))

        # A 400x300 upload exceeds the 250x250 box, so a thumbnail is built.
        self.assertTrue(post.thumbnail)
        self.assertTrue(post.thumbnail.storage.exists(post.thumbnail.name))
        self.assertLessEqual(post.thumbnail_width, 250)
        self.assertLessEqual(post.thumbnail_height, 250)
        self.assertLess(post.thumbnail.size, post.image.size)

        thread_response = self.client.get(response.url)
        self.assertContains(thread_response, "post-image")
        self.assertContains(thread_response, "expand.js")
        # The thumbnail is served inline; the full image is only the expand target.
        self.assertContains(thread_response, post.thumbnail.url)
        self.assertContains(thread_response, 'data-full-src="%s"' % post.image.url)

    def test_reply_with_image(self):
        thread = Thread.objects.create(board=self.board)
        Post.objects.create(thread=thread, content="op")

        response = self.client.post(
            reverse("create-reply", args=[self.board.slug, thread.id]),
            {"content": "reply", "image": make_upload(name="reply.gif", image_format="GIF")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(thread.posts.exclude(image="").count(), 1)

    def test_small_image_gets_no_thumbnail(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "tiny", "image": make_upload(size=(120, 90))},
        )

        self.assertEqual(response.status_code, 302)

        post = Post.objects.get()
        self.assertFalse(post.thumbnail)

        # The template falls back to the original image when there is no thumbnail.
        thread_response = self.client.get(response.url)
        self.assertContains(thread_response, post.image.url)
        self.assertNotContains(thread_response, "data-full-src")

    def test_gif_thumbnail_is_rasterised_to_png(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "gif", "image": make_upload(name="x.gif", image_format="GIF")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.objects.get().thumbnail.name.endswith(".png"))

    def test_accepts_webp(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "webp", "image": make_upload(name="x.webp", image_format="WEBP")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.objects.get().image.name.endswith(".webp"))

    def test_jpeg_thumbnail(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "jpg", "image": make_upload(name="x.jpg", image_format="JPEG")},
        )

        self.assertEqual(response.status_code, 302)

        post = Post.objects.get()
        self.assertTrue(post.thumbnail.name.endswith(".jpg"))
        self.assertLess(post.thumbnail.size, post.image.size)

    def test_rejects_unsupported_format(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "hi", "image": make_upload(name="x.bmp", image_format="BMP")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported image format")
        self.assertFalse(Post.objects.exists())

    def test_rejects_non_image(self):
        bogus = SimpleUploadedFile("x.png", b"not really an image", content_type="image/png")

        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "hi", "image": bogus},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.exists())

    @override_settings(MAX_IMAGE_SIZE=10)
    def test_rejects_oversized_image(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "hi", "image": make_upload()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "too large")
        self.assertFalse(Post.objects.exists())

    def test_board_without_images_rejects_upload(self):
        self.board.allows_images = False
        self.board.save()

        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "hi", "image": make_upload()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not allow images")
        self.assertFalse(Post.objects.exists())

    def test_create_thread_image_only_no_message(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "", "image": make_upload()},
        )

        self.assertEqual(response.status_code, 302)

        post = Post.objects.get()
        self.assertEqual(post.content, "")
        self.assertTrue(post.image.storage.exists(post.image.name))

    def test_reply_image_only_no_message(self):
        thread = Thread.objects.create(board=self.board)
        Post.objects.create(thread=thread, content="op")

        response = self.client.post(
            reverse("create-reply", args=[self.board.slug, thread.id]),
            {"content": "", "image": make_upload()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(thread.posts.exclude(image="").count(), 1)

    def test_create_thread_rejects_empty_without_image(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Message cannot be empty")
        self.assertFalse(Post.objects.exists())

    def test_reply_rejects_empty_without_image(self):
        thread = Thread.objects.create(board=self.board)
        Post.objects.create(thread=thread, content="op")

        response = self.client.post(
            reverse("create-reply", args=[self.board.slug, thread.id]),
            {"content": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Message cannot be empty")
        self.assertEqual(thread.posts.count(), 1)


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_missing_page_uses_custom_404_template(self):
        response = self.client.get("/not-a-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "404: Page not found", status_code=404)
        self.assertContains(response, reverse("homepage"), status_code=404)
