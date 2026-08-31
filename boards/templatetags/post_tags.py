import re

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def render_post(post):
    content = post.content

    # Escape user-provided content first.
    content = escape(content)

    # Get the posts this post references.
    references = (
        post.references
        .all()
    )

    referenced_posts = {
        reference.target_id: reference.target
        for reference in references
    }

    def replace_reference(match):
        post_id = int(match.group(1))
        target_post = referenced_posts.get(post_id)

        if target_post is None:
            return match.group(0)

        url = (
            reverse(
                "thread",
                kwargs={
                    "board_slug": target_post.thread.board.slug,
                    "thread_id": target_post.thread.id,
                }
            )
            + f"#post-{target_post.id}"
        )

        return (
            f'<a href="{url}" '
            f'class="post-reference">'
            f'&gt;&gt;{post_id}'
            f'</a>'
        )

    # Post references.
    content = re.sub(
        r"&gt;&gt;(\d+)",
        replace_reference,
        content,
    )

    # URLs.
    url_pattern = re.compile(
        r"(https?://[^\s<]+)"
    )

    def replace_url(match):
        url = match.group(1)

        return (
            f'<a href="{url}" '
            f'rel="nofollow noopener noreferrer" '
            f'target="_blank">'
            f'{url}'
            f'</a>'
        )

    content = url_pattern.sub(
        replace_url,
        content,
    )

    # Greentext.
    lines = content.split("\n")
    rendered_lines = []

    for line in lines:
        if line.startswith("&gt;") and not line.startswith("&gt;&gt;"):
            line = (
                '<span class="greentext">'
                + line
                + "</span>"
            )

        rendered_lines.append(line)

    content = "<br>".join(rendered_lines)

    return mark_safe(content)
