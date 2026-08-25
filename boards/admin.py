from django.contrib import admin

from .models import Board, Post, Thread


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "name",
        "is_active",
        "created_at",
    )

    list_filter = ("is_active",)

    search_fields = (
        "slug",
        "name",
    )


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "board",
        "subject",
        "created_at",
        "bumped_at",
        "locked",
        "pinned",
    )

    list_filter = (
        "board",
        "locked",
        "pinned",
    )

    search_fields = (
        "subject",
    )


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "thread",
        "poster_name",
        "created_at",
        "deleted",
    )

    list_filter = (
        "deleted",
    )

    search_fields = (
        "content",
        "poster_name",
    )