(function () {
  "use strict";

  // Blur-in titles: split into words
  document.querySelectorAll("[data-blur]").forEach(function (el) {
    var text = el.textContent.trim();
    if (!text) return;
    el.setAttribute("aria-label", text);
    el.innerHTML = text
      .split(/(\s+)/)
      .map(function (part, i) {
        if (/^\s+$/.test(part)) return part;
        return (
          '<span class="blur-word" style="--d:' +
          i * 70 +
          'ms">' +
          part +
          "</span>"
        );
      })
      .join("");
  });

  // Stagger reveal delays for sibling cards
  document.querySelectorAll(".items-grid, .digest-grid").forEach(function (grid) {
    Array.prototype.forEach.call(grid.children, function (child, i) {
      if (child.classList && child.classList.contains("reveal")) {
        child.style.setProperty("--d", Math.min(i * 70, 420) + "ms");
      }
    });
  });

  var reveals = document.querySelectorAll(".reveal, [data-blur]");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    reveals.forEach(function (el) {
      io.observe(el);
    });
  } else {
    reveals.forEach(function (el) {
      el.classList.add("is-in");
    });
  }

  // Category filter
  var bar = document.querySelector(".filter-bar");
  if (bar) {
    bar.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".filter-btn");
      if (!btn) return;
      var f = btn.getAttribute("data-filter");
      bar.querySelectorAll(".filter-btn").forEach(function (b) {
        b.classList.toggle("is-on", b === btn);
      });
      document.querySelectorAll(".item-card").forEach(function (card) {
        var cat = card.getAttribute("data-category") || "";
        var show = f === "*" || cat === f;
        card.classList.toggle("is-hidden", !show);
      });
    });
  }
})();
