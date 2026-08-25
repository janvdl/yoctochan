from django.shortcuts import get_object_or_404, render

from .models import Board


def board(request, board_slug):
    board = get_object_or_404(
        Board,
        slug=board_slug,
        is_active=True,
    )

    return render(
        request,
        "boards/board.html",
        {
            "board": board,
        },
    )