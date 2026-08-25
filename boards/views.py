from django.shortcuts import get_object_or_404, render

from .models import Board, Thread


def board(request, board_slug):
    board = get_object_or_404(
        Board,
        slug=board_slug,
        is_active=True,
    )

    threads = (
        board.threads
        .filter(locked=False)
        .order_by("-pinned", "-bumped_at")
    )

    return render(
        request,
        "boards/board.html",
        {
            "board": board,
            "threads": threads,
        },
    )

def thread(request, board_slug, thread_id):
    thread = get_object_or_404(
        Thread.objects.select_related("board"),
        id=thread_id,
        board__slug=board_slug,
    )

    posts = thread.posts.filter(
        deleted=False,
    )

    return render(
        request,
        "boards/thread.html",
        {
            "thread": thread,
            "posts": posts,
        },
    )