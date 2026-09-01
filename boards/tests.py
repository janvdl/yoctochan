import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from PIL import Image

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Ban, Board, ModAction, Moderator, Post, Report, Thread
from .moderation import active_ban_for


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


class DuplicatePostTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")
        self.thread = Thread.objects.create(board=self.board)
        Post.objects.create(thread=self.thread, content="op")

    def reply(self, content):
        return self.client.post(
            reverse("create-reply", args=[self.board.slug, self.thread.id]),
            {"content": content},
        )

    def test_identical_reply_is_rejected(self):
        self.assertEqual(self.reply("same text").status_code, 302)

        response = self.reply("same text")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "duplicate of a recent post")
        self.assertEqual(self.thread.posts.count(), 2)

    def test_different_reply_is_allowed(self):
        self.assertEqual(self.reply("first").status_code, 302)
        self.assertEqual(self.reply("second").status_code, 302)
        self.assertEqual(self.thread.posts.count(), 3)

    def test_same_text_in_another_thread_is_allowed(self):
        self.assertEqual(self.reply("shared line").status_code, 302)

        other = Thread.objects.create(board=self.board)
        Post.objects.create(thread=other, content="op")

        response = self.client.post(
            reverse("create-reply", args=[self.board.slug, other.id]),
            {"content": "shared line"},
        )

        self.assertEqual(response.status_code, 302)

    @override_settings(DUPLICATE_POST_WINDOW_SECONDS=0)
    def test_duplicate_allowed_once_window_elapses(self):
        self.assertEqual(self.reply("later repost").status_code, 302)
        self.assertEqual(self.reply("later repost").status_code, 302)
        self.assertEqual(self.thread.posts.count(), 3)

    def test_identical_thread_is_rejected(self):
        first = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "brand new thread"},
        )
        self.assertEqual(first.status_code, 302)

        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "brand new thread"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "duplicate of a recent post")


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_missing_page_uses_custom_404_template(self):
        response = self.client.get("/not-a-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "404: Page not found", status_code=404)
        self.assertContains(response, reverse("homepage"), status_code=404)


class PosterIPTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")

    def test_thread_creation_records_remote_addr(self):
        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "hello"},
            REMOTE_ADDR="203.0.113.7",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Post.objects.get().poster_ip, "203.0.113.7")

    def test_reply_records_remote_addr(self):
        thread = Thread.objects.create(board=self.board)
        Post.objects.create(thread=thread, content="op")

        self.client.post(
            reverse("create-reply", args=[self.board.slug, thread.id]),
            {"content": "a reply"},
            REMOTE_ADDR="198.51.100.4",
        )

        self.assertEqual(thread.posts.latest("id").poster_ip, "198.51.100.4")

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_forwarded_for_used_when_trusted(self):
        self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "proxied"},
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="70.70.70.70, 10.0.0.1",
        )

        self.assertEqual(Post.objects.get().poster_ip, "10.0.0.1")

    def test_forwarded_for_ignored_by_default(self):
        self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "spoof attempt"},
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )

        self.assertEqual(Post.objects.get().poster_ip, "10.0.0.1")

    def test_ip_never_rendered_publicly(self):
        thread = Thread.objects.create(board=self.board)
        Post.objects.create(
            thread=thread, content="op", poster_ip="203.0.113.9"
        )

        response = self.client.get(
            reverse("thread", args=[self.board.slug, thread.id])
        )

        self.assertNotContains(response, "203.0.113.9")


class ReservedSlugTests(TestCase):
    def test_reserved_slug_rejected(self):
        board = Board(slug="mod", name="Not allowed")

        with self.assertRaises(ValidationError):
            board.full_clean()


class SoftDeletedThreadTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")
        self.thread = Thread.objects.create(board=self.board, subject="Doomed")
        Post.objects.create(thread=self.thread, content="op body")

    def test_deleted_thread_404s_for_public(self):
        self.thread.set_deleted(True)

        response = self.client.get(
            reverse("thread", args=[self.board.slug, self.thread.id])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Thread.objects.filter(pk=self.thread.pk).exists())

    def test_deleted_thread_absent_from_board_list(self):
        self.thread.set_deleted(True)

        response = self.client.get(reverse("board", args=[self.board.slug]))

        self.assertNotContains(response, "Doomed")
        self.assertNotContains(response, "op body")

    def test_deleted_post_hidden_on_thread_page(self):
        Post.objects.create(
            thread=self.thread, content="secret reply", deleted=True
        )

        response = self.client.get(
            reverse("thread", args=[self.board.slug, self.thread.id])
        )

        self.assertNotContains(response, "secret reply")


class ModerationPermissionTests(TestCase):
    def setUp(self):
        self.board_a = Board.objects.create(slug="a", name="A")
        self.board_b = Board.objects.create(slug="b", name="B")
        self.thread_b = Thread.objects.create(board=self.board_b)
        Post.objects.create(thread=self.thread_b, content="op")

        self.superuser = User.objects.create_superuser("root", password="x")
        self.plain = User.objects.create_user("plain", password="x")
        self.scoped = User.objects.create_user(
            "scoped", password="x", is_staff=True
        )
        scoped_mod = Moderator.objects.create(user=self.scoped)
        scoped_mod.boards.add(self.board_a)

    def _lock_url(self):
        return reverse("mod-thread-action", args=[self.thread_b.id, "lock"])

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self._lock_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("mod-login"), response.url)

    def test_non_staff_user_forbidden(self):
        self.client.force_login(self.plain)

        response = self.client.post(self._lock_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("mod-login"), response.url)

    def test_scoped_mod_cannot_touch_other_board(self):
        self.client.force_login(self.scoped)

        response = self.client.post(self._lock_url())

        self.assertEqual(response.status_code, 403)
        self.thread_b.refresh_from_db()
        self.assertFalse(self.thread_b.locked)

    def test_superuser_can_lock(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self._lock_url(), {"next": "/b/"})

        self.assertEqual(response.status_code, 302)
        self.thread_b.refresh_from_db()
        self.assertTrue(self.thread_b.locked)

    def test_get_request_rejected(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self._lock_url())

        self.assertEqual(response.status_code, 405)


class ModerationActionTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")
        self.thread = Thread.objects.create(board=self.board)
        self.op = Post.objects.create(thread=self.thread, content="op")
        self.reply = Post.objects.create(thread=self.thread, content="a reply")

        self.mod = User.objects.create_user(
            "mod", password="x", is_staff=True
        )
        Moderator.objects.create(user=self.mod)  # global
        self.client.force_login(self.mod)

    def act_post(self, post, action):
        return self.client.post(
            reverse("mod-post-action", args=[post.id, action])
        )

    def act_thread(self, action):
        return self.client.post(
            reverse("mod-thread-action", args=[self.thread.id, action])
        )

    def test_delete_and_restore_post(self):
        self.act_post(self.reply, "delete")
        self.reply.refresh_from_db()
        self.assertTrue(self.reply.deleted)
        self.assertEqual(self.reply.deleted_by, self.mod)
        self.assertIsNotNone(self.reply.deleted_at)
        self.assertEqual(
            ModAction.objects.filter(kind="delete_post").count(), 1
        )

        self.act_post(self.reply, "restore")
        self.reply.refresh_from_db()
        self.assertFalse(self.reply.deleted)
        self.assertIsNone(self.reply.deleted_by)
        self.assertEqual(
            ModAction.objects.filter(kind="restore_post").count(), 1
        )

    def test_delete_and_restore_thread(self):
        self.act_thread("delete")
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.deleted)

        self.act_thread("restore")
        self.thread.refresh_from_db()
        self.assertFalse(self.thread.deleted)

        self.assertEqual(ModAction.objects.count(), 2)

    def test_lock_blocks_replies(self):
        self.act_thread("lock")
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.locked)

        self.client.logout()
        response = self.client.post(
            reverse("create-reply", args=[self.board.slug, self.thread.id]),
            {"content": "sneaky"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.thread.posts.count(), 2)

    def test_sticky_toggle(self):
        self.act_thread("sticky")
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.pinned)

        self.act_thread("unsticky")
        self.thread.refresh_from_db()
        self.assertFalse(self.thread.pinned)

    def test_unknown_action_rejected(self):
        response = self.act_thread("nuke")
        self.assertEqual(response.status_code, 403)

    def test_dashboard_lists_actions(self):
        self.act_thread("lock")

        response = self.client.get(reverse("mod-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lock thread")

    def test_moderator_sees_deleted_post_with_restore_control(self):
        self.reply.set_deleted(True, by=self.mod)

        response = self.client.get(
            reverse("thread", args=[self.board.slug, self.thread.id])
        )

        self.assertContains(response, "a reply")
        self.assertContains(response, "restore")


class ReportTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")
        self.thread = Thread.objects.create(board=self.board)
        self.post = Post.objects.create(thread=self.thread, content="op")

    def report_url(self):
        return reverse("report-post", args=[self.post.id])

    def test_anonymous_can_report(self):
        response = self.client.post(
            self.report_url(),
            {"reason": "spam", "detail": "buy pills"},
            REMOTE_ADDR="5.5.5.5",
        )

        self.assertEqual(response.status_code, 302)
        report = Report.objects.get()
        self.assertEqual(report.reason, "spam")
        self.assertEqual(report.reporter_ip, "5.5.5.5")
        self.assertIsNone(report.resolved_at)

    def test_duplicate_open_report_is_deduped(self):
        for _ in range(2):
            self.client.post(
                self.report_url(), {"reason": "spam"}, REMOTE_ADDR="5.5.5.5"
            )

        self.assertEqual(Report.objects.count(), 1)

    def test_new_report_allowed_after_previous_resolved(self):
        self.client.post(
            self.report_url(), {"reason": "spam"}, REMOTE_ADDR="5.5.5.5"
        )
        Report.objects.update(resolved_at=timezone.now())

        self.client.post(
            self.report_url(), {"reason": "rules"}, REMOTE_ADDR="5.5.5.5"
        )

        self.assertEqual(Report.objects.count(), 2)

    def test_invalid_reason_rerenders(self):
        response = self.client.post(self.report_url(), {"reason": "nonsense"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Report.objects.exists())

    def test_reporting_deleted_post_404s(self):
        self.post.set_deleted(True)

        self.assertEqual(self.client.get(self.report_url()).status_code, 404)


class ReportsQueueTests(TestCase):
    def setUp(self):
        self.board_a = Board.objects.create(slug="a", name="A")
        self.board_b = Board.objects.create(slug="bb", name="B")

        self.report_a = self._report(self.board_a)
        self.report_b = self._report(self.board_b)

        self.global_mod = User.objects.create_superuser("root", password="x")
        self.scoped = User.objects.create_user(
            "scoped", password="x", is_staff=True
        )
        Moderator.objects.create(user=self.scoped).boards.add(self.board_a)

    def _report(self, board):
        thread = Thread.objects.create(board=board)
        post = Post.objects.create(thread=thread, content="bad")
        return Report.objects.create(post=post, reason="spam")

    def test_global_mod_sees_all_reports(self):
        self.client.force_login(self.global_mod)

        response = self.client.get(reverse("mod-reports"))

        self.assertContains(response, "/a/ No.%d" % self.report_a.post_id)
        self.assertContains(response, "/bb/ No.%d" % self.report_b.post_id)

    def test_scoped_mod_sees_only_their_board(self):
        self.client.force_login(self.scoped)

        response = self.client.get(reverse("mod-reports"))

        self.assertContains(response, "/a/ No.%d" % self.report_a.post_id)
        self.assertNotContains(response, "/bb/ No.%d" % self.report_b.post_id)

    def test_resolve_marks_and_logs(self):
        self.client.force_login(self.global_mod)

        response = self.client.post(
            reverse("mod-report-resolve", args=[self.report_a.id])
        )

        self.assertEqual(response.status_code, 302)
        self.report_a.refresh_from_db()
        self.assertIsNotNone(self.report_a.resolved_at)
        self.assertEqual(self.report_a.resolved_by, self.global_mod)
        self.assertEqual(
            ModAction.objects.filter(kind="resolve_report").count(), 1
        )

    def test_scoped_mod_cannot_resolve_other_board(self):
        self.client.force_login(self.scoped)

        response = self.client.post(
            reverse("mod-report-resolve", args=[self.report_b.id])
        )

        self.assertEqual(response.status_code, 403)


class BanLookupTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")
        self.other = Board.objects.create(slug="o", name="Other")

    def test_global_ban_matches_any_board(self):
        Ban.objects.create(ip_address="1.1.1.1", reason="x")

        self.assertIsNotNone(active_ban_for("1.1.1.1", self.board))
        self.assertIsNotNone(active_ban_for("1.1.1.1", self.other))

    def test_board_ban_scoped(self):
        Ban.objects.create(ip_address="1.1.1.1", board=self.board, reason="x")

        self.assertIsNotNone(active_ban_for("1.1.1.1", self.board))
        self.assertIsNone(active_ban_for("1.1.1.1", self.other))

    def test_expired_and_lifted_bans_ignored(self):
        Ban.objects.create(
            ip_address="1.1.1.1",
            reason="x",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        Ban.objects.create(
            ip_address="1.1.1.1", reason="x", lifted_at=timezone.now()
        )

        self.assertIsNone(active_ban_for("1.1.1.1", self.board))

    def test_board_ban_preferred_over_global(self):
        Ban.objects.create(ip_address="1.1.1.1", reason="global one")
        Ban.objects.create(
            ip_address="1.1.1.1", board=self.board, reason="board one"
        )

        self.assertEqual(
            active_ban_for("1.1.1.1", self.board).reason, "board one"
        )

    def test_no_ip_returns_none(self):
        Ban.objects.create(ip_address="1.1.1.1", reason="x")

        self.assertIsNone(active_ban_for(None, self.board))


class BanEnforcementTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(slug="b", name="Board")
        self.other = Board.objects.create(slug="o", name="Other")
        self.thread = Thread.objects.create(board=self.board)
        Post.objects.create(thread=self.thread, content="op")

    def test_banned_ip_blocked_on_get_and_post(self):
        Ban.objects.create(ip_address="7.7.7.7", board=self.board, reason="no")

        get = self.client.get(
            reverse("create-thread", args=[self.board.slug]),
            REMOTE_ADDR="7.7.7.7",
        )
        self.assertEqual(get.status_code, 403)
        self.assertTemplateUsed(get, "boards/banned.html")

        post = self.client.post(
            reverse("create-reply", args=[self.board.slug, self.thread.id]),
            {"content": "hi"},
            REMOTE_ADDR="7.7.7.7",
        )
        self.assertEqual(post.status_code, 403)
        self.assertEqual(self.thread.posts.count(), 1)

    def test_board_ban_leaves_other_boards_open(self):
        Ban.objects.create(ip_address="7.7.7.7", board=self.board, reason="no")

        response = self.client.get(
            reverse("create-thread", args=[self.other.slug]),
            REMOTE_ADDR="7.7.7.7",
        )
        self.assertEqual(response.status_code, 200)

    def test_expired_ban_allows_posting(self):
        Ban.objects.create(
            ip_address="7.7.7.7",
            board=self.board,
            reason="no",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            reverse("create-thread", args=[self.board.slug]),
            {"content": "back again"},
            REMOTE_ADDR="7.7.7.7",
        )
        self.assertEqual(response.status_code, 302)


class BanCreateTests(TestCase):
    def setUp(self):
        self.board_a = Board.objects.create(slug="a", name="A")
        self.board_b = Board.objects.create(slug="bb", name="B")
        self.thread = Thread.objects.create(board=self.board_a)
        self.post = Post.objects.create(
            thread=self.thread, content="spam", poster_ip="8.8.8.8"
        )

        self.superuser = User.objects.create_superuser("root", password="x")
        self.scoped = User.objects.create_user(
            "scoped", password="x", is_staff=True
        )
        Moderator.objects.create(user=self.scoped).boards.add(self.board_a)

    def test_ban_from_post_computes_expiry_and_deletes(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("mod-ban-create"),
            {
                "post": self.post.id,
                "ip_address": "8.8.8.8",
                "scope": "board",
                "reason": "spamming",
                "note": "",
                "duration": "1w",
                "delete_post": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        ban = Ban.objects.get()
        self.assertEqual(ban.board, self.board_a)
        self.assertAlmostEqual(
            ban.expires_at,
            timezone.now() + timedelta(weeks=1),
            delta=timedelta(minutes=1),
        )

        self.post.refresh_from_db()
        self.assertTrue(self.post.deleted)
        self.assertEqual(
            set(ModAction.objects.values_list("kind", flat=True)),
            {"ban", "delete_post"},
        )

    def test_permanent_ban_has_no_expiry(self):
        self.client.force_login(self.superuser)

        self.client.post(
            reverse("mod-ban-create"),
            {
                "ip_address": "8.8.8.8",
                "board": self.board_a.slug,
                "scope": "board",
                "reason": "x",
                "duration": "perm",
            },
        )

        self.assertIsNone(Ban.objects.get().expires_at)

    def test_scoped_mod_cannot_create_global_ban(self):
        self.client.force_login(self.scoped)

        response = self.client.post(
            reverse("mod-ban-create"),
            {
                "post": self.post.id,
                "ip_address": "8.8.8.8",
                "scope": "global",
                "reason": "x",
                "duration": "1d",
            },
        )

        self.assertEqual(response.status_code, 200)  # form re-rendered
        self.assertFalse(Ban.objects.exists())

    def test_ban_resolves_open_reports_on_post(self):
        report = Report.objects.create(post=self.post, reason="spam")
        self.client.force_login(self.superuser)

        self.client.post(
            reverse("mod-ban-create"),
            {
                "post": self.post.id,
                "ip_address": "8.8.8.8",
                "scope": "board",
                "reason": "x",
                "duration": "1d",
            },
        )

        report.refresh_from_db()
        self.assertIsNotNone(report.resolved_at)

    def test_ban_lift(self):
        ban = Ban.objects.create(
            ip_address="8.8.8.8", board=self.board_a, reason="x"
        )
        self.client.force_login(self.superuser)

        response = self.client.post(reverse("mod-ban-lift", args=[ban.id]))

        self.assertEqual(response.status_code, 302)
        ban.refresh_from_db()
        self.assertIsNotNone(ban.lifted_at)
        self.assertEqual(ban.lifted_by, self.superuser)
        self.assertFalse(ban.is_active())
        self.assertEqual(ModAction.objects.filter(kind="unban").count(), 1)
