from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


# URL prefixes that must never be shadowed by a board slug.
RESERVED_BOARD_SLUGS = frozenset({"admin", "mod", "static", "media", "report", "watcher"})


def validate_board_slug(value):
    if value.lower() in RESERVED_BOARD_SLUGS:
        raise ValidationError(
            "%(value)s is a reserved slug.",
            params={"value": value},
        )


class Board(models.Model):
    slug = models.SlugField(
        max_length=32,
        unique=True,
        validators=[validate_board_slug],
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    bump_limit = models.PositiveIntegerField(
        default=300,
    )

    threads_per_page = models.PositiveIntegerField(
        default=10,
    )

    # A board shows at most max_pages * threads_per_page active threads;
    # beyond that, the oldest (by bump order, excluding pinned) are
    # automatically archived to make room. See ThreadService.
    max_pages = models.PositiveIntegerField(
        default=10,
    )

    catalogue_replies = models.PositiveIntegerField(
        default=3,
    )

    allows_nsfw = models.BooleanField(default=False)
    allows_images = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return f"/{self.slug}/"

class Thread(models.Model):
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name="threads",
    )

    subject = models.CharField(
        max_length=150,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    bumped_at = models.DateTimeField(auto_now_add=True)

    locked = models.BooleanField(default=False)
    pinned = models.BooleanField(default=False)

    # Automatically set once the board has more active threads than its
    # max_pages * threads_per_page cap — frozen (no more replies) and
    # dropped from the board's active listing, but still directly
    # viewable. Never set on a pinned thread.
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-pinned", "-bumped_at"]
        indexes = [
            # Matches board()'s hot query: a board's non-deleted,
            # non-archived threads, newest-bumped (pinned) first.
            models.Index(fields=["board", "deleted", "archived", "pinned", "bumped_at"]),
        ]

    def can_bump(self):
        return self.posts.count() < self.board.bump_limit

    def set_deleted(self, deleted, *, by=None):
        self.deleted = deleted
        self.deleted_at = timezone.now() if deleted else None
        self.deleted_by = by if deleted else None
        self.save(update_fields=["deleted", "deleted_at", "deleted_by"])

    def __str__(self):
        return f"/{self.board.slug}/ - Thread {self.pk}"

class Post(models.Model):
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name="posts",
    )

    content = models.TextField(
        max_length=4_000,
    )

    poster_name = models.CharField(
        max_length=64,
        blank=True,
    )

    # Derived from a "Name#password" submission (see boards/tripcode.py).
    # Blank when the poster didn't supply a password.
    poster_tripcode = models.CharField(max_length=16, blank=True)

    # True for a reply posted with "sage": it doesn't bump the thread.
    # Meaningless (always False) on an OP.
    is_sage = models.BooleanField(default=False)

    # Captured server-side; never rendered publicly, mod/admin only.
    poster_ip = models.GenericIPAddressField(null=True, blank=True)

    image = models.ImageField(
        upload_to="posts/%Y/%m/%d/",
        blank=True,
        width_field="image_width",
        height_field="image_height",
        validators=[
            FileExtensionValidator(
                allowed_extensions=list(settings.ALLOWED_IMAGE_EXTENSIONS),
            ),
        ],
    )
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)

    # SHA-256 of the uploaded image's bytes, used to catch a reposted image
    # even if it's been renamed. Blank when the post has no image.
    image_hash = models.CharField(max_length=64, blank=True, db_index=True)

    thumbnail = models.ImageField(
        upload_to="posts/%Y/%m/%d/thumbs/",
        blank=True,
        width_field="thumbnail_width",
        height_field="thumbnail_height",
    )
    thumbnail_width = models.PositiveIntegerField(null=True, blank=True)
    thumbnail_height = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        indexes = [
            # RateLimitService checks every poster_ip against a recent-time
            # window on every single post/reply submission.
            models.Index(fields=["poster_ip", "created_at"]),
            # PostService's duplicate-content/-image checks scan a
            # thread's recent posts by time.
            models.Index(fields=["thread", "created_at"]),
        ]

    def set_deleted(self, deleted, *, by=None):
        self.deleted = deleted
        self.deleted_at = timezone.now() if deleted else None
        self.deleted_by = by if deleted else None
        self.save(update_fields=["deleted", "deleted_at", "deleted_by"])


class PostReference(models.Model):
    source = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="references",
    )

    target = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="referenced_by",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target"],
                name="unique_post_reference",
            ),
        ]

    def __str__(self):
        return f"{self.source_id} -> {self.target_id}"


class Moderator(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="moderator",
    )

    # No boards selected == a global moderator.
    boards = models.ManyToManyField(
        Board,
        blank=True,
        related_name="moderators",
    )

    can_manage_moderators = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_global(self):
        return not self.boards.exists()

    is_global.boolean = True

    def can_moderate(self, board):
        return self.is_global() or self.boards.filter(pk=board.pk).exists()

    def __str__(self):
        return f"Moderator: {self.user}"


class ModAction(models.Model):
    class Kind(models.TextChoices):
        DELETE_POST = "delete_post", "Delete post"
        RESTORE_POST = "restore_post", "Restore post"
        DELETE_THREAD = "delete_thread", "Delete thread"
        RESTORE_THREAD = "restore_thread", "Restore thread"
        LOCK = "lock", "Lock thread"
        UNLOCK = "unlock", "Unlock thread"
        STICKY = "sticky", "Sticky thread"
        UNSTICKY = "unsticky", "Unsticky thread"
        BAN = "ban", "Ban poster"
        UNBAN = "unban", "Lift ban"
        RESOLVE_REPORT = "resolve_report", "Resolve report"

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="mod_actions",
    )
    kind = models.CharField(
        max_length=32,
        choices=Kind.choices,
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_thread = models.ForeignKey(
        Thread,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_post = models.ForeignKey(
        Post,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} by {self.moderator} @ {self.created_at:%Y-%m-%d %H:%M}"


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam / advertising"
        ILLEGAL = "illegal", "Illegal content"
        RULES = "rules", "Breaks board rules"
        OTHER = "other", "Other"

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
    )
    detail = models.CharField(max_length=500, blank=True)
    reporter_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]

    def resolve(self, by=None):
        self.resolved_at = timezone.now()
        self.resolved_by = by
        self.save(update_fields=["resolved_at", "resolved_by"])

    def __str__(self):
        return f"Report on Post No.{self.post_id} ({self.get_reason_display()})"


class BanQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(lifted_at__isnull=True).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )


class Ban(models.Model):
    ip_address = models.GenericIPAddressField()

    # No board == a site-wide ban.
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bans",
    )

    reason = models.CharField(max_length=500)  # shown to the banned user
    note = models.TextField(blank=True)  # internal only

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # null == permanent

    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = BanQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # active_ban_for() runs this exact lookup on every single
            # thread/reply creation request (both GET and POST) — probably
            # the single hottest query in the app.
            models.Index(fields=["ip_address", "lifted_at"]),
        ]

    def is_active(self):
        return self.lifted_at is None and (
            self.expires_at is None or self.expires_at > timezone.now()
        )

    is_active.boolean = True

    def lift(self, by=None):
        self.lifted_at = timezone.now()
        self.lifted_by = by
        self.save(update_fields=["lifted_at", "lifted_by"])

    def __str__(self):
        scope = f"/{self.board.slug}/" if self.board_id else "all boards"
        return f"Ban {self.ip_address} from {scope}"
