from django.urls import path

from . import views


urlpatterns = [
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
]