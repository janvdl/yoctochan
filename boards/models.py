from django.db import models


class Board(models.Model):
    slug = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    bump_limit = models.PositiveIntegerField(
        default=300,
    )

    threads_per_page = models.PositiveIntegerField(
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

    class Meta:
        ordering = ["-pinned", "-bumped_at"]

    def can_bump(self):
        return self.posts.count() < self.board.bump_limit

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

    created_at = models.DateTimeField(auto_now_add=True)

    deleted = models.BooleanField(default=False)

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
