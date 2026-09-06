"""Moderator-facing views: the dashboard, content actions, reports and bans."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import BanForm
from .models import Ban, Board, ModAction, Post, PostReference, Report, Thread
from .moderation import (
    ban_duration_delta,
    can_moderate,
    get_moderator,
    log_action,
    moderatable_boards,
    moderator_required,
)


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


def _open_report_count(request):
    return Report.objects.filter(
        resolved_at__isnull=True,
        post__thread__board__in=moderatable_boards(request.user),
    ).count()


@moderator_required
def dashboard(request):
    # The template only ever shows target_thread_id/target_post_id (plain
    # columns, no join needed) — moderator and board are the only FKs it
    # actually dereferences.
    actions = ModAction.objects.select_related("moderator", "board")[:50]

    return render(
        request,
        "mod/dashboard.html",
        {
            "actions": actions,
            "open_reports": _open_report_count(request),
        },
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


# --- Reports -----------------------------------------------------------------


@moderator_required
def reports(request):
    show_all = request.GET.get("show") == "all"

    queryset = (
        Report.objects.select_related("post__thread__board", "resolved_by")
        .prefetch_related(
            # render_post (in the template) reads post.references for
            # each report's post; without this it's an extra query per row.
            Prefetch(
                "post__references",
                queryset=PostReference.objects.select_related(
                    "target__thread__board"
                ),
            )
        )
        .filter(post__thread__board__in=moderatable_boards(request.user))
    )

    if not show_all:
        queryset = queryset.filter(resolved_at__isnull=True)

    return render(
        request,
        "mod/reports.html",
        {
            "reports": queryset,
            "show_all": show_all,
        },
    )


@require_POST
@moderator_required
def report_resolve(request, report_id):
    report = get_object_or_404(
        Report.objects.select_related("post__thread__board"),
        id=report_id,
    )
    board = report.post.thread.board
    _require_board(request, board)

    if report.resolved_at is None:
        report.resolve(by=request.user)
        log_action(
            moderator=request.user,
            kind=ModAction.Kind.RESOLVE_REPORT,
            board=board,
            thread=report.post.thread,
            post=report.post,
        )
        messages.success(request, f"Report on No.{report.post_id} dismissed.")

    return redirect(_safe_next(request, reverse("mod-reports")))


# --- Bans -------------------------------------------------------------------


def _is_global_mod(user):
    moderator = get_moderator(user)
    return user.is_superuser or (moderator is not None and moderator.is_global())


@moderator_required
def bans(request):
    queryset = Ban.objects.select_related("board", "created_by", "lifted_by")

    if not _is_global_mod(request.user):
        queryset = queryset.filter(board__in=moderatable_boards(request.user))

    ban_list = sorted(queryset, key=lambda ban: (not ban.is_active(), -ban.id))

    return render(request, "mod/bans.html", {"bans": ban_list})


@moderator_required
def ban_create(request):
    post = None
    board = None

    post_id = request.GET.get("post") or request.POST.get("post")
    if post_id:
        post = get_object_or_404(
            Post.objects.select_related("thread__board"),
            id=post_id,
        )
        board = post.thread.board
    else:
        board_slug = request.GET.get("board") or request.POST.get("board")
        if board_slug:
            board = get_object_or_404(Board, slug=board_slug)

    allow_global = _is_global_mod(request.user)

    if board is not None:
        _require_board(request, board)
    elif not allow_global:
        raise Http404

    scope_choices = []
    if board is not None:
        scope_choices.append(("board", f"/{board.slug}/ only"))
    if allow_global:
        scope_choices.append(("global", "All boards (site-wide)"))

    form_kwargs = {
        "scope_choices": scope_choices,
        "from_post": post is not None,
    }

    if request.method == "POST":
        form = BanForm(request.POST, **form_kwargs)

        if form.is_valid():
            ban_board = None if form.cleaned_data["scope"] == "global" else board

            delta = ban_duration_delta(form.cleaned_data["duration"])
            expires_at = timezone.now() + delta if delta else None

            ban = Ban.objects.create(
                ip_address=form.cleaned_data["ip_address"],
                board=ban_board,
                reason=form.cleaned_data["reason"],
                note=form.cleaned_data["note"],
                created_by=request.user,
                expires_at=expires_at,
            )

            log_action(
                moderator=request.user,
                kind=ModAction.Kind.BAN,
                board=ban_board,
                thread=post.thread if post else None,
                post=post,
                note=f"{ban.ip_address} · {form.cleaned_data['duration']}",
            )

            if post and form.cleaned_data.get("delete_post"):
                post.set_deleted(True, by=request.user)
                log_action(
                    moderator=request.user,
                    kind=ModAction.Kind.DELETE_POST,
                    board=post.thread.board,
                    thread=post.thread,
                    post=post,
                )

            if post:
                for open_report in post.reports.filter(resolved_at__isnull=True):
                    open_report.resolve(by=request.user)

            messages.success(request, f"Banned {ban.ip_address}.")
            return redirect("mod-bans")
    else:
        initial = {}
        prefill_ip = request.GET.get("ip") or (post.poster_ip if post else None)
        if prefill_ip:
            initial["ip_address"] = prefill_ip
        form = BanForm(initial=initial, **form_kwargs)

    return render(
        request,
        "mod/ban_form.html",
        {"form": form, "post": post, "board": board},
    )


@require_POST
@moderator_required
def ban_lift(request, ban_id):
    ban = get_object_or_404(Ban.objects.select_related("board"), id=ban_id)

    if ban.board is not None:
        _require_board(request, ban.board)
    elif not _is_global_mod(request.user):
        raise PermissionDenied

    if ban.lifted_at is None:
        ban.lift(by=request.user)
        log_action(
            moderator=request.user,
            kind=ModAction.Kind.UNBAN,
            board=ban.board,
            note=str(ban.ip_address),
        )
        messages.success(request, f"Lifted ban on {ban.ip_address}.")

    return redirect(_safe_next(request, reverse("mod-bans")))
