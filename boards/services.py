from django.utils import timezone

from .imaging import build_thumbnail
from .models import Board, Post, PostReference, Thread


class ThreadService:
    @staticmethod
    def create_thread(
        board,
        subject,
        poster_name,
        content,
        image=None,
    ):
        thread = Thread.objects.create(
            board=board,
            subject=subject,
            bumped_at=timezone.now(),
        )

        post = Post.objects.create(
            thread=thread,
            poster_name=poster_name,
            content=content,
            image=image or "",
        )

        PostService.generate_thumbnail(post)
        PostService.parse_references(post)

        return thread

    @staticmethod
    def create_reply(
        thread,
        poster_name,
        content,
        image=None,
    ):
        if thread.locked:
            raise ValueError("Thread is locked.")

        post = Post.objects.create(
            thread=thread,
            poster_name=poster_name,
            content=content,
            image=image or "",
        )

        if thread.can_bump():
            thread.bumped_at = timezone.now()
            thread.save(update_fields=["bumped_at"])

        PostService.generate_thumbnail(post)
        PostService.parse_references(post)

        return post


class PostService:
    @staticmethod
    def generate_thumbnail(post):
        """
        Build and attach a bounded thumbnail for a post's image. No-op when the
        post has no image or the original already fits the thumbnail box.
        """
        if not post.image:
            return

        result = build_thumbnail(post.image)

        if result is None:
            return

        content, filename, width, height = result

        post.thumbnail.save(filename, content, save=False)
        post.thumbnail_width = width
        post.thumbnail_height = height
        post.save(
            update_fields=[
                "thumbnail",
                "thumbnail_width",
                "thumbnail_height",
            ]
        )

    @staticmethod
    def parse_references(post):
        """
        Find >>123 style references in a post and create
        PostReference records for valid posts.
        """
        import re

        post_ids = re.findall(
            r">>(\d+)",
            post.content,
        )

        if not post_ids:
            return

        post_ids = set(int(post_id) for post_id in post_ids)

        referenced_posts = Post.objects.filter(
            id__in=post_ids,
        )

        references = [
            PostReference(
                source=post,
                target=target,
            )
            for target in referenced_posts
            if target.id != post.id
        ]

        PostReference.objects.bulk_create(
            references,
            ignore_conflicts=True,
        )