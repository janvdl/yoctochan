from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Board


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


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_missing_page_uses_custom_404_template(self):
        response = self.client.get("/not-a-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "404: Page not found", status_code=404)
        self.assertContains(response, reverse("homepage"), status_code=404)
