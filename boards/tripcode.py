"""
Tripcodes: a classic imageboard convention that lets an otherwise-anonymous
poster prove they're the same person across posts, without an account.

Typing ``Name#password`` in the name field splits off everything after the
first ``#`` as a "password" and derives a short tripcode from it; the
tripcode is shown next to the name, but the password itself is never
recoverable from it. The same password always produces the same tripcode
*on this deployment* (it's salted with SECRET_KEY), so it can't be used to
correlate the same poster across different sites.
"""

import base64
import hashlib
import hmac

from django.conf import settings

TRIPCODE_LENGTH = 10


def compute_tripcode(password):
    """Derive a short, stable, non-reversible tripcode from a password."""
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        password.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    # Base64 gives mixed-case alnum output; fold its two non-alnum
    # characters and padding into plain letters rather than stripping them
    # (stripping would shorten some tripcodes and not others).
    encoded = base64.b64encode(digest).decode("ascii")
    encoded = encoded.replace("+", "A").replace("/", "B").replace("=", "")

    return encoded[:TRIPCODE_LENGTH]


def parse_poster_name(raw_name):
    """
    Split a raw name-field submission into ``(display_name, tripcode)``.

    ``Name#password`` computes a tripcode from everything after the first
    ``#`` and keeps ``Name`` (stripped) as the display name. With no ``#``,
    or a ``#`` with nothing after it, the input is kept as a literal name
    and no tripcode is produced.
    """
    name, sep, password = raw_name.partition("#")

    if not sep or not password:
        return raw_name.strip(), ""

    return name.strip(), compute_tripcode(password)
