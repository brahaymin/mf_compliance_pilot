(function () {
  "use strict";
  var els = {
    status: document.getElementById("status"),
    list: document.getElementById("fees"),
    meta: document.getElementById("fees-meta")
  };
  function el(tag, opts, kids) {
    var n = document.createElement(tag);
    opts = opts || {};
    if (opts.text != null) n.textContent = opts.text;
    if (opts.cls) n.className = opts.cls;
    if (opts.href) { n.href = opts.href; n.rel = "noopener"; }
    (kids || []).forEach(function (k) { n.appendChild(k); });
    return n;
  }
  function pct(v) { return (typeof v === "number" ? v.toFixed(2) : "—") + "%"; }
  function addMeta(t, v) {
    els.meta.appendChild(el("dt", { text: t }));
    els.meta.appendChild(el("dd", { text: v }));
  }
  function seriesUrl(id) {
    return "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=" + encodeURIComponent(id);
  }
  function render(data) {
    var meta = data.meta || {}, rows = data.rows || [];
    addMeta("Status", meta.label || "supervised pilot");
    addMeta("Confirmed changes", String(meta.row_count) + " across " + meta.fund_count + " funds");
    if (meta.known_limitation) addMeta("Known limitation", meta.known_limitation);
    var groups = {}, order = [];
    rows.forEach(function (r) {
      var k = r.series_id + "|" + r.filing_accession_new;
      if (!groups[k]) { groups[k] = []; order.push(k); }
      groups[k].push(r);
    });
    order.forEach(function (k) {
      var g = groups[k], r0 = g[0];
      var head = el("tr", {}, [el("th", { text: "Line" }), el("th", { text: "Prior", cls: "num" }),
        el("th", { text: "New", cls: "num" }), el("th", { text: "Change", cls: "num" })]);
      var body = g.map(function (r) {
        var d = r["new"] - r.old;
        return el("tr", {}, [el("td", { text: r.field_label }), el("td", { text: pct(r.old), cls: "num" }),
          el("td", { text: pct(r["new"]), cls: "num" }),
          el("td", { text: (d > 0 ? "+" : "") + d.toFixed(2) + " pts", cls: "num delta " + (d > 0 ? "up" : "down") })]);
      });
      var table = el("table", { cls: "fee-table" }, [el("thead", {}, [head]), el("tbody", {}, body)]);
      var sub = el("p", { cls: "sub" }, [
        document.createTextNode("Series "),
        el("a", { text: r0.series_id, href: seriesUrl(r0.series_id) }),
        document.createTextNode(" · new filing " + r0.filing_date_new + " (" + r0.filing_accession_new +
          ") vs prior " + r0.filing_date_prior + " (" + r0.filing_accession_prior + ")")
      ]);
      els.list.appendChild(el("article", { cls: "fund-card" }, [el("h2", { text: r0.fund_name }), sub,
        el("div", { cls: "fee-table-wrap" }, [table])]));
    });
    els.status.textContent = rows.length + " confirmed changes. Check each against the SEC filing.";
  }
  fetch("fee_changes.json?v=20261125-launch")
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(render)
    .catch(function () { els.status.textContent = "Could not load fee changes."; els.status.className = "notice warn"; });
})();
