// Client-side "thread watcher": lets a reader pin threads to a small
// persistent list that follows them across pages, showing new-reply
// counts. Posters have no accounts here, so the list itself lives entirely
// in this browser's localStorage; the one server round-trip
// (/watcher/status/) just refreshes reply counts for threads already on it.
(function () {
    "use strict";

    var STORAGE_KEY = "yocto.watched";

    function loadWatched() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function saveWatched(list) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
        } catch (e) {
            // Storage unavailable — the list just won't persist.
        }
    }

    function findIndex(list, threadId) {
        for (var i = 0; i < list.length; i++) {
            if (list[i].threadId === threadId) {
                return i;
            }
        }
        return -1;
    }

    function buildRow(entry) {
        var li = document.createElement("li");

        var link = document.createElement("a");
        link.href = "/" + entry.board + "/thread/" + entry.threadId + "/";
        link.textContent = "/" + entry.board + "/ " + entry.subject;
        li.appendChild(link);

        var unread = (entry.currentCount || entry.lastSeenCount) - entry.lastSeenCount;
        if (unread > 0) {
            var badge = document.createElement("span");
            badge.className = "thread-watcher-count";
            badge.textContent = unread + " new";
            li.appendChild(badge);
        }

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "thread-watcher-remove";
        remove.textContent = "×";
        remove.setAttribute(
            "aria-label",
            "Stop watching /" + entry.board + "/ thread " + entry.threadId
        );
        remove.addEventListener("click", function () {
            removeThread(entry.threadId);
        });
        li.appendChild(remove);

        return li;
    }

    function render() {
        var widget = document.getElementById("thread-watcher");

        if (!widget) {
            return;
        }

        var list = loadWatched();
        var listEl = widget.querySelector(".thread-watcher-list");
        listEl.innerHTML = "";
        widget.hidden = list.length === 0;

        list.forEach(function (entry) {
            listEl.appendChild(buildRow(entry));
        });
    }

    function removeThread(threadId) {
        saveWatched(
            loadWatched().filter(function (entry) {
                return entry.threadId !== threadId;
            })
        );

        render();
        syncToggleButton();
    }

    function syncToggleButton() {
        var button = document.getElementById("watch-thread-toggle");

        if (!button) {
            return;
        }

        var threadId = parseInt(button.getAttribute("data-thread-id"), 10);
        var watching = findIndex(loadWatched(), threadId) !== -1;

        button.textContent = watching ? "★ Watching" : "☆ Watch thread";
        button.classList.toggle("watching", watching);
    }

    function toggleWatch(button) {
        var threadId = parseInt(button.getAttribute("data-thread-id"), 10);
        var list = loadWatched();
        var index = findIndex(list, threadId);

        if (index === -1) {
            list.push({
                threadId: threadId,
                board: button.getAttribute("data-board"),
                subject: button.getAttribute("data-subject") || "(no subject)",
                lastSeenCount: parseInt(button.getAttribute("data-post-count"), 10) || 0,
            });
        } else {
            list.splice(index, 1);
        }

        saveWatched(list);
        syncToggleButton();
        render();
    }

    // Opening the thread page counts as reading it: bump its lastSeenCount
    // to the current total so it doesn't show as unread right after you
    // just looked at it.
    function markCurrentThreadRead(button) {
        var threadId = parseInt(button.getAttribute("data-thread-id"), 10);
        var postCount = parseInt(button.getAttribute("data-post-count"), 10) || 0;
        var list = loadWatched();
        var index = findIndex(list, threadId);

        if (index !== -1) {
            list[index].lastSeenCount = postCount;
            list[index].currentCount = postCount;
            saveWatched(list);
        }
    }

    function refreshCounts() {
        var list = loadWatched();

        if (!list.length || typeof fetch !== "function") {
            return;
        }

        var ids = list
            .map(function (entry) {
                return entry.threadId;
            })
            .join(",");

        fetch("/watcher/status/?ids=" + encodeURIComponent(ids))
            .then(function (response) {
                return response.ok ? response.json() : null;
            })
            .then(function (data) {
                if (!data) {
                    return;
                }

                var updated = loadWatched().filter(function (entry) {
                    var status = data.threads[entry.threadId];

                    if (!status || status.deleted) {
                        return false;
                    }

                    entry.currentCount = status.postCount;
                    return true;
                });

                saveWatched(updated);
                render();
            })
            .catch(function () {
                // Offline, or the endpoint failed — keep showing whatever
                // the widget last knew.
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var toggle = document.getElementById("watch-thread-toggle");

        if (toggle) {
            markCurrentThreadRead(toggle);
            syncToggleButton();
            toggle.addEventListener("click", function () {
                toggleWatch(toggle);
            });
        }

        render();
        refreshCounts();
    });
})();
