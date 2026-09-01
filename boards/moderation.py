"""Helpers for the moderation layer: client IP capture, permission checks,
and audit logging."""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import ModAction, Moderator


def get_client_ip(request):
    """
    Best-effort client IP for a request.

    Uses ``REMOTE_ADDR`` by default. When ``settings.TRUST_X_FORWARDED_FOR`` is
    true (i.e. the app sits behind a proxy that sets the header), the right-most
    ``X-Forwarded-For`` entry is used instead — that is the address the trusted
    proxy actually saw, and the only one a client cannot spoof.
    """
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()

    return request.META.get("REMOTE_ADDR") or None


def get_moderator(user):
    """
    The ``Moderator`` record for ``user``, or ``None`` if there isn't one.

    Superusers are global moderators whether or not they have a record, so
    callers must check ``user.is_superuser`` separately. The lookup is cached on
    the user instance for the request's lifetime.
    """
    if not user.is_authenticated:
        return None

    if not hasattr(user, "_cached_moderator"):
        try:
            user._cached_moderator = user.moderator
        except Moderator.DoesNotExist:
            user._cached_moderator = None

    return user._cached_moderator


def can_moderate(user, board):
    """Whether ``user`` may take moderation actions on ``board``."""
    if not user.is_authenticated or not user.is_staff:
        return False

    if user.is_superuser:
        return True

    moderator = get_moderator(user)
    return moderator is not None and moderator.can_moderate(board)


def moderator_required(view):
    """
    Gate a view behind moderator access: anonymous / non-staff users are sent to
    the login page; a staff user with no moderator standing gets a 403.
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated or not user.is_staff:
            return redirect_to_login(request.get_full_path())

        if not user.is_superuser and get_moderator(user) is None:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapped


def log_action(*, moderator, kind, board=None, thread=None, post=None, note=""):
    """Record a moderation action in the audit log."""
    return ModAction.objects.create(
        moderator=moderator,
        kind=kind,
        board=board,
        target_thread=thread,
        target_post=post,
        note=note,
    )
