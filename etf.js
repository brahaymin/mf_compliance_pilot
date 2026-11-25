(function () {
  "use strict";
  var list = document.getElementById("etf"), status = document.getElementById("status"),
    meta = document.getElementById("etf-meta"), q = document.getElementById("etf-q"), cards = [];
  function el(tag, o, kids) {
    var n = document.createElement(tag); o = o || {};
    if (o.text != null) n.textContent = o.text;
    if (o.cls) n.className = o.cls;
    if (o.href) { n.href = o.href; n.target = "_blank"; n.rel = "noopener"; }
    (kids || []).forEach(function (k) { n.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return n;
  }
  function addMeta(t, v) { meta.appendChild(el("dt", { text: t })); meta.appendChild(el("dd", { text: v })); }
  function render(d) {
    var m = d.meta || {};
    addMeta("Status", m.label + "; fees " + m.fee_status);
    addMeta("Series", m.active_series + " active, " + m.closed_series + " closed, " + m.series + " total. " + m.status_rule);
    addMeta("Coverage", m.series + " fund series, " + m.etf_classes + " ETF classes, " + m.other_classes +
      " mutual fund classes, " + m.registrants + " registrants (SEC class list " + m.source_year + ")");
    addMeta("Prospectus links", m.links_verified + " verified against the fund's own tickers; " + m.links_flagged +
      " flagged for review and not linked");
    addMeta("Scope", m.scope);
    addMeta("Source", m.source + ". Outside SEC sources: " + m.outside_sources + ".");
    if (m.hidden_series) addMeta("Hidden series", m.hidden_series + " omitted. " + (m.hide_rule || "") + " Source: " + (m.hide_source || "v1 MF DB") + ".");
    d.rows.forEach(function (r) {
      var body = r.classes.map(function (c) {
        return el("tr", {}, [el("td", {}, [c.name, c.etf ? el("span", { cls: "etf-tag", text: "ETF" }) : ""]),
          el("td", { text: (c.ticker || "no ticker") + (c.active ? "" : " (closed, last seen " + c.last_year + ")") }), el("td", { cls: "num pending", text: "pending review" })]);
      });
      var t = el("table", { cls: "etf-classes" }, [el("thead", {}, [el("tr", {}, [el("th", { text: "Share class" }),
        el("th", { text: "Ticker" }), el("th", { cls: "num", text: "Expense ratio" })])]), el("tbody", {}, body)]);
      var f = r.filing, fl = f ? el("p", { cls: "sub filing" }, [el("strong", { text: "Latest prospectus: " }),
        el("a", { text: f.form + " " + f.accession, href: f.url }), " · filed " + f.date])
        : el("p", { cls: "sub filing" }, [el("strong", { text: "Latest prospectus: " }),
          r.link_status === "flagged" ? "link flagged for review (may not match this fund), not shown" : "not found in v1 data"]);
      var card = el("article", { cls: "fund-card" }, [el("h2", {}, [r.fund_name + " ", el("span", { cls: "status-badge " + r.status,
        text: r.status === "active" ? "Active" : "Closed (last seen " + r.last_seen + ")" })]), fl,
        el("p", { cls: "sub" }, ["Source: " + (r.source ? "v1 MF DB" : "not recorded") + " · Fund series: ", el("a", { text: r.series_id,
          href: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=" + r.series_id })]),
        el("div", { cls: "fee-table-wrap" }, [t])]);
      card.dataset.status = r.status;
      card.dataset.q = (r.fund_name + " " + r.series_id + " " + r.classes.map(function (c) { return c.ticker + " " + c.name; }).join(" ")).toLowerCase();
      cards.push(card); list.appendChild(card);
    });
    status.textContent = d.rows.length + " fund series. Expense ratios pending review. Check each item against the SEC filing.";
  }
  var sf = document.getElementById("etf-status");
  function apply() {
    var v = q.value.trim().toLowerCase(), st = sf.value, n = 0;
    cards.forEach(function (c) {
      c.hidden = !!(v && c.dataset.q.indexOf(v) < 0) || (st !== "all" && c.dataset.status !== st);
      if (!c.hidden) n++;
    });
    status.textContent = "Showing " + n + " of " + cards.length + " fund series. Expense ratios pending review. Check each item against the SEC filing.";
  }
  q.addEventListener("input", apply);
  sf.addEventListener("change", apply);
  fetch("etf_lineage.json?v=20261125-hide").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) { render(d); apply(); }).catch(function () { status.textContent = "Could not load the fund list."; status.className = "notice warn"; });
})();
