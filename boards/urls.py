from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.homepage,
        name="homepage",
    ),

    path(
        "<slug:board_slug>/",
        views.board,
        name="board",
    ),

    path(
        "<slug:board_slug>/thread/<int:thread_id>/",
        views.thread,
        name="thread",
    ),

    path(
        "<slug:board_slug>/thread/create/",
        views.create_thread,
        name="create-thread",
    ),

    path(
        "<slug:board_slug>/thread/<int:thread_id>/reply/",
        views.create_reply,
        name="create-reply",
    ),

    path(
        "report/<int:post_id>/",
        views.report_post,
        name="report-post",
    ),
]
