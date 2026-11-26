(function () {
  "use strict";
  var list = document.getElementById("etf"), status = document.getElementById("status"),
    meta = document.getElementById("etf-meta"), q = document.getElementById("etf-q"), cards = [];
  function el(tag, o, kids) {
    var n = document.createElement(tag); o = o || {};
    if (o.text != null) n.textContent = o.text;
    if (o.cls) n.className = o.cls;
    if (o.href) { n.href = o.href; n.target = "_blank"; n.rel = "noopener"; }
    if (o.colspan) n.colSpan = o.colspan;
    (kids || []).forEach(function (k) { n.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return n;
  }
  function addMeta(t, v) { meta.appendChild(el("dt", { text: t })); meta.appendChild(el("dd", { text: v })); }
  function pct(v) { return (typeof v === "number" && isFinite(v) ? v.toFixed(2) : "—") + "%"; }
  function feeCells(c) {
    if (c && typeof c.expense_total === "number" && typeof c.expense_net === "number") {
      var waiver = (typeof c.waiver_amount === "number" && c.waiver_amount > 0)
        ? c.waiver_amount
        : Math.round((c.expense_total - c.expense_net) * 100) / 100;
      var totalKids = [el("span", { cls: "fee-total", text: pct(c.expense_total) })];
      if (c.total_line) {
        totalKids.push(el("span", { cls: "fee-line fee-total-line", text: c.total_line }));
      }
      var netKids = [el("span", { cls: "fee-net", text: pct(c.expense_net) })];
      if (waiver > 0) {
        netKids.push(" ");
        netKids.push(el("span", { cls: "fee-waiver", text: "Waiver " + pct(waiver) }));
      }
      if (c.net_line) {
        netKids.push(el("span", { cls: "fee-line fee-net-line", text: c.net_line }));
      } else {
        netKids.push(el("span", { cls: "fee-note", text: "no waiver in filing" }));
      }
      var srcKids = [];
      if (c.filing_url) {
        srcKids.push(el("a", { cls: "fee-filing", text: (c.form ? c.form + " " : "Filing ") + (c.accession || "document"), href: c.filing_url }));
        srcKids.push(" ");
      }
      srcKids.push(el("span", { cls: "fee-source", text: "source: v1 MF DB" + (c.accession ? " · " + c.accession : "") }));
      return [
        el("td", { cls: "num" }, totalKids),
        el("td", { cls: "num" }, netKids),
        el("td", { cls: "fee-src" }, srcKids)
      ];
    }
    if (c && c.reason) {
      return [el("td", { cls: "fees blank", colspan: 3 }, [el("span", { cls: "fee-reason", text: c.reason })])];
    }
    return [el("td", { cls: "num", text: "—" }), el("td", { cls: "num", text: "—" }), el("td", { text: "" })];
  }
  function render(d) {
    var m = d.meta || {};
    addMeta("Status", m.label + "; fees " + m.fee_status);
    addMeta("Series", m.active_series + " active, " + m.closed_series + " closed, " + m.series + " total. " + m.status_rule);
    addMeta("Coverage", m.series + " fund series, " + m.etf_classes + " ETF classes, " + m.other_classes +
      " mutual fund classes, " + m.registrants + " registrants (SEC class list " + m.source_year + ")");
    addMeta("Prospectus links", m.links_from_db + " from the v1 DB (series_primary_document); " + m.links_none +
      " with no filing in the DB");
    if (m.fees_published != null) {
      var activeFees = m.fees_published_active, activeBlank = m.fees_blank_active;
      var line = m.fees_published + " with Total and Net; " + (m.fees_blank || 0) +
        " with no usable fee table (reason shown).";
      if (activeFees != null) {
        line = activeFees + " of " + (activeFees + (activeBlank || 0)) +
          " active share classes with Total and Net; " + (activeBlank || 0) +
          " active ETF classes with no usable fee table (reason shown). " +
          m.fees_published + " published in all, including closed series.";
      }
      addMeta("Expense ratios", line + " Source: " + (m.fee_source || "v1 MF DB") + ".");
    }
    addMeta("Scope", m.scope);
    addMeta("Source", m.source + ". Outside SEC sources: " + m.outside_sources + ".");
    if (m.hidden_series) addMeta("Hidden series", m.hidden_series + " omitted. " + (m.hide_rule || "") + " Source: " + (m.hide_source || "v1 MF DB") + ".");
    (d.rows || []).forEach(function (r) {
      var body = (r.classes || []).map(function (c) {
        return el("tr", {}, [el("td", {}, [c.name, c.etf ? el("span", { cls: "etf-tag", text: "ETF" }) : ""]),
          el("td", { text: (c.ticker || "no ticker") + (c.active ? "" : " (closed, last seen " + c.last_year + ")") })].concat(feeCells(c)));
      });
      var t = el("table", { cls: "etf-classes" }, [el("thead", {}, [el("tr", {}, [el("th", { text: "Share class" }),
        el("th", { text: "Ticker" }), el("th", { cls: "num", text: "Total" }), el("th", { cls: "num", text: "Net" }),
        el("th", { text: "Fee filing" })])]), el("tbody", {}, body)]);
      var f = r.filing, fl = f ? el("p", { cls: "sub filing" }, [el("strong", { text: "Latest prospectus: " }),
        el("a", { text: f.form + " " + f.accession, href: f.url }), " · filed " + f.date + " · source: v1 MF DB"])
        : el("p", { cls: "sub filing" }, [el("strong", { text: "Latest prospectus: " }), "not found in v1 data"]);
      var card = el("article", { cls: "fund-card" }, [el("h2", {}, [r.fund_name + " ", el("span", { cls: "status-badge " + r.status,
        text: r.status === "active" ? "Active" : "Closed (last seen " + r.last_seen + ")" })]), fl,
        el("p", { cls: "sub" }, ["Source: " + (r.source ? "v1 MF DB" : "not recorded") + " · Fund series: ", el("a", { text: r.series_id,
          href: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=" + r.series_id })]),
        el("div", { cls: "fee-table-wrap" }, [t])]);
      card.dataset.status = r.status;
      card.dataset.q = (r.fund_name + " " + r.series_id + " " + (r.classes || []).map(function (c) { return (c.ticker || "") + " " + c.name; }).join(" ")).toLowerCase();
      cards.push(card); list.appendChild(card);
    });
    status.textContent = (d.rows || []).length + " fund series. Read the full filing. Check each item against the SEC filing.";
  }
  var sf = document.getElementById("etf-status");
  function apply() {
    var v = q.value.trim().toLowerCase(), st = sf.value, n = 0;
    cards.forEach(function (c) {
      c.hidden = !!(v && c.dataset.q.indexOf(v) < 0) || (st !== "all" && c.dataset.status !== st);
      if (!c.hidden) n++;
    });
    status.textContent = "Showing " + n + " of " + cards.length + " fund series. Read the full filing. Check each item against the SEC filing.";
  }
  q.addEventListener("input", apply);
  sf.addEventListener("change", apply);
  fetch("etf_lineage.json?v=20261126-allclass").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) { render(d); apply(); }).catch(function () { status.textContent = "Could not load the fund list."; status.className = "notice warn"; });
})();
