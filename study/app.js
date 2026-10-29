(function () {
  var rail = document.getElementById("rail");
  var links = rail.querySelectorAll("a");
  var items = [];
  for (var i = 0; i < links.length; i++) {
    var el = document.getElementById(links[i].getAttribute("href").slice(1));
    if (el) items.push({ el: el, link: links[i] });
  }
  var current = null, locked = false, lockTimer = 0, ticking = false;
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function place(item) {
    var l = item.link;
    rail.style.setProperty("--ix", l.offsetLeft + "px");
    rail.style.setProperty("--iw", l.offsetWidth + "px");
    rail.style.setProperty("--iy", (l.offsetTop + l.offsetHeight - 10) + "px");
    rail.setAttribute("data-ready", "");
  }
  function setCurrent(item) {
    if (item === current) return;
    current = item;
    for (var k = 0; k < items.length; k++) {
      if (items[k] === item) items[k].link.setAttribute("aria-current", "true");
      else items[k].link.removeAttribute("aria-current");
    }
    if (!item) { rail.removeAttribute("data-ready"); return; }
    place(item);
    // On narrow screens, bring the current link to the middle of the bar, once per change
    if (window.innerWidth < 1000 && rail.scrollWidth > rail.clientWidth) {
      var left = item.link.offsetLeft - (rail.clientWidth - item.link.offsetWidth) / 2;
      rail.scrollTo({ left: Math.max(0, left), behavior: calm ? "auto" : "smooth" });
    }
  }
  function update() {
    ticking = false;
    if (locked) return;
    var line = window.innerHeight * 0.3, found = null;
    for (var j = 0; j < items.length; j++) {
      if (items[j].el.getBoundingClientRect().top <= line) found = items[j];
    }
    setCurrent(found);
  }
  function unlockSoon(ms) {
    clearTimeout(lockTimer);
    lockTimer = setTimeout(function () { locked = false; update(); }, ms);
  }
  window.addEventListener("scroll", function () {
    if (locked) unlockSoon(160);
    else if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  // A tap on a link goes straight to that link, without the indicator stopping at every section on the way
  for (var m = 0; m < items.length; m++) {
    (function (item) {
      item.link.addEventListener("click", function () { locked = true; setCurrent(item); unlockSoon(700); });
    })(items[m]);
  }
  window.addEventListener("resize", function () { if (current) place(current); });
  update();
})();