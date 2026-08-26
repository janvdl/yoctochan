from django.shortcuts import get_object_or_404, redirect, render

from .forms import CreateThreadForm, CreatePostForm
from .models import Board, Thread, Post
from .services import ThreadService

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

def create_thread(request, board_slug):
    board = get_object_or_404(
        Board,
        slug=board_slug,
        is_active=True,
    )

    if request.method == "POST":
        form = CreateThreadForm(request.POST)

        if form.is_valid():
            thread = ThreadService.create_thread(
                board=board,
                subject=form.cleaned_data["subject"],
                poster_name=form.cleaned_data["poster_name"],
                content=form.cleaned_data["content"],
            )

            return redirect(
                "thread",
                board_slug=board.slug,
                thread_id=thread.id,
            )

    else:
        form = CreateThreadForm()

    return render(
        request,
        "boards/create_thread.html",
        {
            "board": board,
            "form": form,
        },
    )

def create_reply(request, board_slug, thread_id):
    thread = get_object_or_404(
        Thread,
        id=thread_id,
        board__slug=board_slug,
        board__is_active=True,
    )

    if thread.locked:
        return redirect(
            "thread",
            board_slug=board_slug,
            thread_id=thread.id,
        )

    if request.method == "POST":
        form = CreatePostForm(request.POST)

        if form.is_valid():
            ThreadService.create_reply(
                thread=thread,
                poster_name=form.cleaned_data["poster_name"],
                content=form.cleaned_data["content"],
            )

            return redirect(
                "thread",
                board_slug=board_slug,
                thread_id=thread.id,
            )

    else:
        form = CreatePostForm()

    return render(
        request,
        "boards/create_reply.html",
        {
            "thread": thread,
            "form": form,
        },
    )