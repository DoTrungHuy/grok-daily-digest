(function () {
  "use strict";
  var bar = document.querySelector(".filters");
  if (!bar) return;
  bar.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".fbtn");
    if (!btn) return;
    var f = btn.getAttribute("data-f");
    bar.querySelectorAll(".fbtn").forEach(function (b) {
      b.classList.toggle("on", b === btn);
    });
    document.querySelectorAll(".item").forEach(function (el) {
      var cat = el.getAttribute("data-cat") || "";
      el.classList.toggle("is-hidden", !(f === "*" || cat === f));
    });
  });
})();
