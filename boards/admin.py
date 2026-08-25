from django.contrib import admin

from .models import Board


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