/* Open every external link (SEC EDGAR etc.) in a new tab, including links
   added later by page scripts. */
(function () {
  "use strict";
  function fix(root) {
    var links = (root.querySelectorAll ? root.querySelectorAll('a[href^="http"]') : []);
    for (var i = 0; i < links.length; i++) {
      links[i].target = "_blank";
      links[i].rel = "noopener";
    }
    if (root.matches && root.matches('a[href^="http"]')) { root.target = "_blank"; root.rel = "noopener"; }
  }
  fix(document);
  new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      m.addedNodes.forEach(function (n) { if (n.nodeType === 1) fix(n); });
    });
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
