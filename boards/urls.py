from django.urls import path

from . import views


urlpatterns = [
    path(
        "<slug:board_slug>/",
        views.board,
        name="board",
    ),
]