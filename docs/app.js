(function () {
  "use strict";
  document.documentElement.classList.add("js");

  var reveals = document.querySelectorAll(".reveal");
  document.querySelectorAll(".items-grid, .digest-grid").forEach(function (grid) {
    Array.prototype.forEach.call(grid.children, function (child, i) {
      if (child.classList && child.classList.contains("reveal")) {
        child.style.transitionDelay = Math.min(i * 60, 360) + "ms";
      }
    });
  });

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
      { rootMargin: "0px 0px -6% 0px", threshold: 0.06 }
    );
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-in"); });
  }

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
        card.classList.toggle("is-hidden", !(f === "*" || cat === f));
      });
    });
  }
})();
