"""Moderator-facing views: the dashboard and the content-action endpoints."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import ModAction, Post, Thread
from .moderation import can_moderate, log_action, moderator_required


def _safe_next(request, fallback):
    """Return a caller-supplied ``next`` URL if it is a safe local path."""
    candidate = request.POST.get("next") or request.GET.get("next")

    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate

    return fallback


def _require_board(request, board):
    if not can_moderate(request.user, board):
        raise PermissionDenied


@moderator_required
def dashboard(request):
    actions = (
        ModAction.objects.select_related(
            "moderator", "board", "target_thread", "target_post"
        )[:50]
    )

    return render(
        request,
        "mod/dashboard.html",
        {"actions": actions},
    )


@require_POST
@moderator_required
def post_action(request, post_id, action):
    post = get_object_or_404(
        Post.objects.select_related("thread__board"),
        id=post_id,
    )
    board = post.thread.board
    _require_board(request, board)

    if action == "delete":
        post.set_deleted(True, by=request.user)
        kind = ModAction.Kind.DELETE_POST
    elif action == "restore":
        post.set_deleted(False, by=request.user)
        kind = ModAction.Kind.RESTORE_POST
    else:
        raise PermissionDenied

    log_action(
        moderator=request.user,
        kind=kind,
        board=board,
        thread=post.thread,
        post=post,
    )
    messages.success(request, f"Post No.{post.id}: {action}.")

    fallback = reverse("thread", args=[board.slug, post.thread_id])
    return redirect(_safe_next(request, fallback))


@require_POST
@moderator_required
def thread_action(request, thread_id, action):
    thread = get_object_or_404(
        Thread.objects.select_related("board"),
        id=thread_id,
    )
    board = thread.board
    _require_board(request, board)

    kinds = {
        "delete": ModAction.Kind.DELETE_THREAD,
        "restore": ModAction.Kind.RESTORE_THREAD,
        "lock": ModAction.Kind.LOCK,
        "unlock": ModAction.Kind.UNLOCK,
        "sticky": ModAction.Kind.STICKY,
        "unsticky": ModAction.Kind.UNSTICKY,
    }

    if action == "delete":
        thread.set_deleted(True, by=request.user)
    elif action == "restore":
        thread.set_deleted(False, by=request.user)
    elif action in ("lock", "unlock"):
        thread.locked = action == "lock"
        thread.save(update_fields=["locked"])
    elif action in ("sticky", "unsticky"):
        thread.pinned = action == "sticky"
        thread.save(update_fields=["pinned"])
    else:
        raise PermissionDenied

    log_action(
        moderator=request.user,
        kind=kinds[action],
        board=board,
        thread=thread,
    )
    messages.success(request, f"Thread #{thread.id}: {action}.")

    if action == "delete":
        fallback = reverse("board", args=[board.slug])
    else:
        fallback = reverse("thread", args=[board.slug, thread.id])

    return redirect(_safe_next(request, fallback))
