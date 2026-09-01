from django.contrib import admin

from .models import (
    Ban,
    Board,
    ModAction,
    Moderator,
    Post,
    PostReference,
    Report,
    Thread,
)


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "name",
        "is_active",
        "allows_nsfw",
        "allows_images",
        "created_at",
    )

    list_filter = (
        "is_active",
        "allows_nsfw",
        "allows_images",
    )

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
        "deleted",
    )

    list_filter = (
        "board",
        "locked",
        "pinned",
        "deleted",
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
        "poster_ip",
        "image",
        "thumbnail",
        "created_at",
        "deleted",
    )

    readonly_fields = (
        "image_width",
        "image_height",
        "image_hash",
        "thumbnail",
        "thumbnail_width",
        "thumbnail_height",
        "deleted_at",
    )

    list_filter = (
        "deleted",
    )

    search_fields = (
        "content",
        "poster_name",
        "poster_ip",
    )

@admin.register(PostReference)
class PostReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "target",
    )

    search_fields = (
        "source__content",
        "target__content",
    )


@admin.register(Moderator)
class ModeratorAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_global",
        "can_manage_moderators",
        "created_at",
    )

    list_filter = (
        "can_manage_moderators",
    )

    search_fields = (
        "user__username",
    )

    filter_horizontal = (
        "boards",
    )


@admin.register(ModAction)
class ModActionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "moderator",
        "kind",
        "board",
        "target_thread",
        "target_post",
    )

    list_filter = (
        "kind",
        "board",
    )

    search_fields = (
        "moderator__username",
        "note",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "post",
        "reason",
        "reporter_ip",
        "resolved_at",
        "resolved_by",
    )

    list_filter = (
        "reason",
        "resolved_at",
    )

    search_fields = (
        "detail",
        "reporter_ip",
    )

    readonly_fields = (
        "post",
        "reason",
        "detail",
        "reporter_ip",
        "created_at",
    )


@admin.register(Ban)
class BanAdmin(admin.ModelAdmin):
    list_display = (
        "ip_address",
        "board",
        "is_active",
        "created_at",
        "expires_at",
        "lifted_at",
        "created_by",
    )

    list_filter = (
        "board",
        "created_at",
    )

    search_fields = (
        "ip_address",
        "reason",
        "note",
    )

    readonly_fields = (
        "created_at",
    )
