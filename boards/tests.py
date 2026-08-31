from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Board, Post, Thread


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


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_missing_page_uses_custom_404_template(self):
        response = self.client.get("/not-a-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "404: Page not found", status_code=404)
        self.assertContains(response, reverse("homepage"), status_code=404)
