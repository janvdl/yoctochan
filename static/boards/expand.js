// Classic imageboard behaviour: click a post thumbnail to expand it inline to
// the full-size image, click again to shrink back to the thumbnail. The full
// image is only fetched on the first expand, so threads stay light until a
// reader actually opens an image. Falls back to opening the image in a new tab
// when JavaScript is unavailable.
(function () {
    "use strict";

    function expand(image) {
        var full = image.getAttribute("data-full-src");

        if (full && image.getAttribute("src") !== full) {
            image.dataset.thumbSrc = image.getAttribute("src");
            image.dataset.thumbWidth = image.getAttribute("width") || "";
            image.dataset.thumbHeight = image.getAttribute("height") || "";
            image.setAttribute("src", full);
        }

        image.removeAttribute("width");
        image.removeAttribute("height");
        image.classList.add("expanded");
    }

    function collapse(image) {
        if (image.dataset.thumbSrc) {
            image.setAttribute("src", image.dataset.thumbSrc);
        }

        if (image.dataset.thumbWidth) {
            image.setAttribute("width", image.dataset.thumbWidth);
        }

        if (image.dataset.thumbHeight) {
            image.setAttribute("height", image.dataset.thumbHeight);
        }

        image.classList.remove("expanded");
    }

    document.addEventListener("click", function (event) {
        var link = event.target.closest(".post-image a");

        if (!link) {
            return;
        }

        var image = link.querySelector("img");

        if (!image) {
            return;
        }

        event.preventDefault();

        if (image.classList.contains("expanded")) {
            collapse(image);
        } else {
            expand(image);
        }
    });
})();
