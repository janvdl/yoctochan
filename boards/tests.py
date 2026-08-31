from django.test import TestCase
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
