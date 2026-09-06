from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery, Window
from django.db.models.functions import RowNumber

from .forms import CreateThreadForm, CreatePostForm, ReportForm
from .moderation import active_ban_for, can_moderate, get_client_ip
from .models import Board, Post, PostReference, Report, Thread
from .services import PostService, RateLimitService, SpamService, ThreadService


def _ban_response(request, board):
    """Render the 'you are banned' page if the client is banned, else None."""
    ban = active_ban_for(get_client_ip(request), board)

    if ban is None:
        return None

    return render(request, "boards/banned.html", {"ban": ban}, status=403)


def bad_request(request, exception=None):
    return render(request, "400.html", status=400)


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)


def homepage(request):
    boards = Board.objects.filter(is_active=True)

    return render(
        request,
        "boards/homepage.html",
        {"boards": boards},
    )


def board(request, board_slug):
    board = get_object_or_404(
        Board,
        slug=board_slug,
        is_active=True,
    )

    threads = (
        board.threads
        .filter(deleted=False, archived=False)
        .annotate(
            post_count=Count(
                "posts",
                filter=Q(posts__deleted=False),
            )
        )
        .order_by("-pinned", "-bumped_at")
    )

    paginator = Paginator(
        threads,
        board.threads_per_page,
    )

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    page_threads = list(page_obj)
    thread_ids = [thread.id for thread in page_threads]

    for thread in page_threads:
        thread.catalogue_display_posts = []
        thread.has_more_catalogue_posts = (
            thread.post_count > board.catalogue_replies + 1
        )

    if thread_ids:
        catalogue_posts = (
            Post.objects.filter(
                thread_id__in=thread_ids,
                deleted=False,
            )
            .annotate(
                oldest_position=Window(
                    expression=RowNumber(),
                    partition_by=[F("thread_id")],
                    order_by=[F("created_at").asc(), F("id").asc()],
                ),
                newest_position=Window(
                    expression=RowNumber(),
                    partition_by=[F("thread_id")],
                    order_by=[F("created_at").desc(), F("id").desc()],
                ),
            )
            .filter(
                Q(oldest_position=1)
                | Q(newest_position__lte=board.catalogue_replies)
            )
            .prefetch_related(
                Prefetch(
                    "references",
                    queryset=PostReference.objects.select_related(
                        "target__thread__board"
                    ),
                )
            )
            .order_by("thread_id", "created_at", "id")
        )

        posts_by_thread = defaultdict(list)
        for post in catalogue_posts:
            posts_by_thread[post.thread_id].append(post)

        for thread in page_threads:
            posts = posts_by_thread[thread.id]

            if not posts:
                continue

            op = next(
                post
                for post in posts
                if post.oldest_position == 1
            )

            replies = [post for post in posts if post.id != op.id]

            # Posts are ordered chronologically, so replies render oldest first.
            thread.catalogue_display_posts = [op] + replies

    return render(
        request,
        "boards/board.html",
        {
            "board": board,
            "page_obj": page_obj,
            "can_moderate": can_moderate(request.user, board),
        },
    )


def search(request, board_slug):
    board = get_object_or_404(
        Board,
        slug=board_slug,
        is_active=True,
    )

    query = request.GET.get("q", "").strip()
    query_too_short = bool(query) and len(query) < settings.SEARCH_MIN_QUERY_LENGTH
    has_searched = bool(query) and not query_too_short
    page_obj = None

    if has_searched:
        # A subject match should surface the thread's OP, not every one of
        # its replies (a reply's own content still matches independently,
        # via the other half of the OR below).
        first_post_id = (
            Post.objects.filter(thread=OuterRef("thread"))
            .order_by("created_at", "id")
            .values("id")[:1]
        )

        results = (
            Post.objects.filter(
                thread__board=board,
                deleted=False,
                thread__deleted=False,
            )
            .filter(
                Q(content__icontains=query)
                | Q(thread__subject__icontains=query, id=Subquery(first_post_id))
            )
            .select_related("thread")
            .prefetch_related(
                Prefetch(
                    "references",
                    queryset=PostReference.objects.select_related(
                        "target__thread__board"
                    ),
                )
            )
            .order_by("-created_at")
        )

        paginator = Paginator(results, settings.SEARCH_RESULTS_PER_PAGE)
        page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "boards/search.html",
        {
            "board": board,
            "query": query,
            "query_too_short": query_too_short,
            "has_searched": has_searched,
            "min_query_length": settings.SEARCH_MIN_QUERY_LENGTH,
            "page_obj": page_obj,
        },
    )


def thread(request, board_slug, thread_id):
    thread = get_object_or_404(
        Thread.objects.select_related("board"),
        id=thread_id,
        board__slug=board_slug,
    )

    moderating = can_moderate(request.user, thread.board)

    if thread.deleted and not moderating:
        raise Http404

    posts = thread.posts.prefetch_related(
        Prefetch(
            "references",
            queryset=PostReference.objects.select_related("target__thread__board"),
        ),
        Prefetch(
            "referenced_by",
            queryset=PostReference.objects.select_related("source__thread__board"),
        ),
    )
    if not moderating:
        posts = posts.filter(deleted=False)

    posts = list(posts)

    return render(
        request,
        "boards/thread.html",
        {
            "thread": thread,
            "posts": posts,
            "post_count": len(posts),
            "can_moderate": moderating,
            "show_backlinks": True,
        },
    )

def create_thread(request, board_slug):
    board = get_object_or_404(
        Board,
        slug=board_slug,
        is_active=True,
    )

    banned = _ban_response(request, board)
    if banned:
        return banned

    if request.method == "POST":
        form = CreateThreadForm(request.POST, request.FILES)
        poster_ip = get_client_ip(request)

        if form.is_valid():
            image = form.cleaned_data["image"]
            content = form.cleaned_data["content"]
            image_hash = PostService.hash_image(image)

            if image and not board.allows_images:
                form.add_error(None, "This board does not allow images.")
            elif RateLimitService.is_cooling_down(poster_ip):
                form.add_error(None, "You're posting too quickly. Please wait a moment.")
            elif RateLimitService.has_hit_thread_limit(poster_ip):
                form.add_error(
                    None,
                    "You've started too many threads recently. Please wait before starting another.",
                )
            elif SpamService.is_spam(content):
                form.add_error("content", "This looks like spam and can't be posted.")
            elif image and PostService.is_recent_duplicate_image(image_hash, board=board):
                form.add_error(None, "This image is a duplicate of a recent post.")
            elif PostService.is_recent_duplicate(content, board=board):
                form.add_error(
                    "content",
                    "This is a duplicate of a recent post.",
                )
            else:
                post = ThreadService.create_thread(
                    board=board,
                    subject=form.cleaned_data["subject"],
                    poster_name=form.cleaned_data["poster_name"],
                    content=form.cleaned_data["content"],
                    image=image,
                    image_hash=image_hash,
                    poster_ip=poster_ip,
                )

                return redirect(
                    reverse(
                        "thread",
                        kwargs={
                            "board_slug": board.slug,
                            "thread_id": post.thread_id,
                        },
                    )
                    + f"#post-{post.id}"
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
        Thread.objects.select_related("board"),
        id=thread_id,
        board__slug=board_slug,
        board__is_active=True,
    )

    banned = _ban_response(request, thread.board)
    if banned:
        return banned

    if thread.locked or thread.archived:
        return redirect(
            "thread",
            board_slug=board_slug,
            thread_id=thread.id,
        )

    if request.method == "POST":
        form = CreatePostForm(request.POST, request.FILES)
        poster_ip = get_client_ip(request)

        if form.is_valid():
            image = form.cleaned_data["image"]
            content = form.cleaned_data["content"]
            image_hash = PostService.hash_image(image)

            if image and not thread.board.allows_images:
                form.add_error(None, "This board does not allow images.")
            elif RateLimitService.is_cooling_down(poster_ip):
                form.add_error(None, "You're posting too quickly. Please wait a moment.")
            elif SpamService.is_spam(content):
                form.add_error("content", "This looks like spam and can't be posted.")
            elif image and PostService.is_recent_duplicate_image(image_hash, thread=thread):
                form.add_error(None, "This image is a duplicate of a recent post.")
            elif PostService.is_recent_duplicate(content, thread=thread):
                form.add_error(
                    "content",
                    "This is a duplicate of a recent post.",
                )
            else:
                post = ThreadService.create_reply(
                    thread=thread,
                    poster_name=form.cleaned_data["poster_name"],
                    content=form.cleaned_data["content"],
                    image=image,
                    image_hash=image_hash,
                    poster_ip=poster_ip,
                    sage=form.cleaned_data["sage"],
                )

                return redirect(
                    reverse(
                        "thread",
                        kwargs={
                            "board_slug": board_slug,
                            "thread_id": thread.id,
                        },
                    )
                    + f"#post-{post.id}"
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


def report_post(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("thread__board"),
        id=post_id,
        deleted=False,
    )

    thread_url = redirect(
        "thread",
        board_slug=post.thread.board.slug,
        thread_id=post.thread_id,
    )

    if request.method == "POST":
        form = ReportForm(request.POST)

        if form.is_valid():
            reporter_ip = get_client_ip(request)

            already_open = Report.objects.filter(
                post=post,
                reporter_ip=reporter_ip,
                resolved_at__isnull=True,
            ).exists()

            if not already_open:
                Report.objects.create(
                    post=post,
                    reason=form.cleaned_data["reason"],
                    detail=form.cleaned_data["detail"],
                    reporter_ip=reporter_ip,
                )

            messages.success(request, "Thanks — your report has been submitted.")
            return thread_url
    else:
        form = ReportForm()

    return render(
        request,
        "boards/report.html",
        {
            "post": post,
            "thread": post.thread,
            "form": form,
        },
    )


def watcher_status(request):
    """
    JSON status for the client-side thread watcher (static/boards/watcher.js).
    Given ``?ids=1,2,3``, reports each thread's current (non-deleted) post
    count plus its locked/deleted state — enough for the widget to show
    new-reply counts and drop threads that no longer exist, without any
    server-side notion of "who is watching what" (that lives in the
    visitor's own localStorage).
    """
    raw_ids = request.GET.get("ids", "")

    try:
        ids = {int(value) for value in raw_ids.split(",") if value.strip()}
    except ValueError:
        ids = set()

    # A generous cap — the widget realistically never watches this many.
    ids = list(ids)[:200]

    rows = Thread.objects.filter(id__in=ids).annotate(
        post_count=Count("posts", filter=Q(posts__deleted=False)),
    ).values("id", "board__slug", "post_count", "locked", "deleted")

    threads = {
        str(row["id"]): {
            "board": row["board__slug"],
            "postCount": row["post_count"],
            "locked": row["locked"],
            "deleted": row["deleted"],
        }
        for row in rows
    }

    return JsonResponse({"threads": threads})
