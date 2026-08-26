from django.utils import timezone

from .models import Board, Post, PostReference, Thread


class ThreadService:
    @staticmethod
    def create_thread(
        board,
        subject,
        poster_name,
        content,
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
        )

        PostService.parse_references(post)

        return thread

    @staticmethod
    def create_reply(
        thread,
        poster_name,
        content,
    ):
        if thread.locked:
            raise ValueError("Thread is locked.")

        post = Post.objects.create(
            thread=thread,
            poster_name=poster_name,
            content=content,
        )

        thread.bumped_at = timezone.now()
        thread.save(update_fields=["bumped_at"])

        PostService.parse_references(post)

        return post


class PostService:
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