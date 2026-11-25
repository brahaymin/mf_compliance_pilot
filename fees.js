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
    if (opts.href) { n.href = opts.href; n.target = "_blank"; n.rel = "noopener"; }
    (kids || []).forEach(function (k) { n.appendChild(k); });
    return n;
  }
  var FRAG = "#:~:text=Annual%20Fund%20Operating%20Expenses";
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
    var counts = { all: rows.length, "Mutual fund": 0, ETF: 0 };
    rows.forEach(function (r) { counts[r.fund_type] = (counts[r.fund_type] || 0) + 1; });
    var countLine = el("p", { cls: "notice info", text: "" });
    countLine.id = "feesCount";
    var filter = el("select", {}, [["all", "All"], ["Mutual fund", "Mutual funds"], ["ETF", "ETFs"]].map(function (o) {
      var op = el("option", { text: o[1] }); op.value = o[0]; return op;
    }));
    filter.id = "feesFilter"; filter.value = "all";
    var label = el("label", { text: "Show: " }, [filter]);
    var search = el("input", {}); search.id = "feesSearch"; search.type = "search";
    search.placeholder = "Search fund name or ticker";
    search.addEventListener("input", function () { apply(); });
    els.list.parentNode.insertBefore(el("div", { cls: "fees-controls" }, [label, search, countLine]), els.list);
    function apply() {
      var shown = 0;
      Array.prototype.forEach.call(els.list.querySelectorAll(".fund-card"), function (c) {
        var q = search.value.trim().toLowerCase();
        var on = (filter.value === "all" || c.getAttribute("data-type") === filter.value) &&
          (!q || c.getAttribute("data-search").indexOf(q) !== -1);
        c.hidden = !on; if (on) shown += c.querySelectorAll("tbody tr").length;
      });
      countLine.textContent = counts.all + " fee changes: " + counts["Mutual fund"] + " mutual funds, " +
        counts.ETF + " ETFs. Showing " + shown + ".";
    }
    filter.addEventListener("change", apply);
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
        return el("tr", {}, [el("td", {}, [document.createTextNode(r.field_label + " "),
          el("span", { cls: "type-badge small", text: r.fund_type }), document.createTextNode(" "),
          el("span", { cls: "ticker small", text: r.ticker || "no ticker" })]), el("td", { text: pct(r.old), cls: "num" }),
          el("td", { text: pct(r["new"]), cls: "num" }),
          el("td", { text: (d > 0 ? "+" : "") + d.toFixed(2) + " pts", cls: "num delta " + (d > 0 ? "up" : "down") })]);
      });
      var table = el("table", { cls: "fee-table" }, [el("thead", {}, [head]), el("tbody", {}, body)]);
      function filingLine(label, acc, date, form, url, doc) {
        var kids = [el("strong", { text: label + ": " })];
        if (doc) kids.push(el("a", { text: (form || "Filing") + " document " + acc, href: doc + FRAG, cls: "doc-link" }));
        else if (url) kids.push(el("a", { text: (form || "Filing") + " " + acc, href: url }));
        else kids.push(document.createTextNode("not recorded"));
        if (doc && url) { kids.push(document.createTextNode(" ")); kids.push(el("a", { text: "(index)", href: url, cls: "index-link" })); }
        kids.push(document.createTextNode(" · filed " + (date || "not recorded") +
          " · form " + (form || "not recorded")));
        return el("p", { cls: "sub filing" }, kids);
      }
      var sub = el("div", {}, [
        filingLine("New fee appeared in", r0.filing_accession_new, r0.filing_date_new, r0.form_new, r0.filing_url_new, r0.doc_url_new),
        filingLine("Compared against prior", r0.filing_accession_prior, r0.filing_date_prior, r0.form_prior, r0.filing_url_prior, r0.doc_url_prior),
        el("p", { cls: "sub" }, [document.createTextNode("Fund series: "),
          el("a", { text: r0.series_id, href: seriesUrl(r0.series_id) })])
      ]);
      var card = el("article", { cls: "fund-card" }, [el("h2", {}, [document.createTextNode(r0.fund_name + " "),
        el("span", { cls: "type-badge", text: r0.fund_type }), document.createTextNode(" "),
        el("span", { cls: "ticker", text: (function (t) { return t.length ? t.filter(function (x, i) { return t.indexOf(x) === i; }).join(", ") : "no ticker"; })(g.map(function (r) { return r.ticker; }).filter(Boolean)) })]), sub,
        el("div", { cls: "fee-table-wrap" }, [table])]);
      card.setAttribute("data-type", r0.fund_type);
      var tickers = g.map(function (r) { return r.ticker; }).filter(Boolean);
      card.setAttribute("data-search", (r0.fund_name + " " + tickers.join(" ")).toLowerCase());
      els.list.appendChild(card);
    });
    apply();
    els.status.textContent = rows.length + " confirmed changes. Check each against the SEC filing.";
  }
  fetch("fee_changes.json?v=20261125-docs")
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(render)
    .catch(function () { els.status.textContent = "Could not load fee changes."; els.status.className = "notice warn"; });
})();
