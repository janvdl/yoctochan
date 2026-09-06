// Client-side "You" highlighting. There's no account to hang this off of,
// so it works entirely from this browser's own memory: after a successful
// post, the server redirects back to the thread with a #post-<id>
// fragment; this script remembers that id (in localStorage, scoped to the
// thread) so this and later visits can mark that post — and any >>reference
// to it — as yours.
(function () {
    "use strict";

    function storageKey(threadId) {
        return "yocto.mine." + threadId;
    }

    function loadMine(threadId) {
        try {
            var raw = localStorage.getItem(storageKey(threadId));
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function saveMine(threadId, ids) {
        try {
            localStorage.setItem(storageKey(threadId), JSON.stringify(ids));
        } catch (e) {
            // Storage unavailable (private browsing, quota, ...) — the
            // highlighting just won't persist between page loads.
        }
    }

    function tagElement(target) {
        var tag = document.createElement("span");
        tag.className = "you-tag";
        tag.textContent = "(You)";
        target.appendChild(tag);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var threadId = document.body.getAttribute("data-thread-id");

        if (!threadId) {
            return;
        }

        var mine = loadMine(threadId);

        var match = /^#post-(\d+)$/.exec(window.location.hash);
        if (match) {
            var newId = parseInt(match[1], 10);
            if (mine.indexOf(newId) === -1) {
                mine.push(newId);
                saveMine(threadId, mine);
            }
        }

        if (!mine.length) {
            return;
        }

        var mineSet = {};
        mine.forEach(function (id) {
            mineSet[id] = true;
        });

        // Mark your own posts.
        mine.forEach(function (id) {
            var post = document.getElementById("post-" + id);
            var header = post && post.querySelector("header");

            if (header && !header.querySelector(".you-tag")) {
                post.classList.add("post-mine");
                tagElement(header);
            }
        });

        // Mark >>references (including "Replies:" backlinks) to your posts.
        document.querySelectorAll("a.post-reference").forEach(function (link) {
            var refMatch = /(\d+)/.exec(link.textContent);

            if (!refMatch || !mineSet[refMatch[0]]) {
                return;
            }

            var next = link.nextElementSibling;
            if (next && next.classList.contains("you-tag")) {
                return;
            }

            var tag = document.createElement("span");
            tag.className = "you-tag";
            tag.textContent = "(You)";
            link.insertAdjacentElement("afterend", tag);
        });
    });
})();
