(function () {
  "use strict";

  var ASSET_VERSION = (document.documentElement.getAttribute("data-asset-version") || "1").replace(/[^\w.-]/g, "");
  var DATA_URL = "names_policy80.json?v=" + ASSET_VERSION;
  var DISCLAIMER = "Pilot data, not legal advice";
  var SOURCE_LABEL = "SEC EDGAR public filings";

  var els = {
    status: document.getElementById("status"),
    results: document.getElementById("names"),
    meta: document.getElementById("names-meta"),
    search: document.getElementById("namesSearch"),
    form: document.getElementById("namesSearchForm"),
  };

  var allRows = [];

  function text(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  function el(tag, opts) {
    var node = document.createElement(tag);
    opts = opts || {};
    if (opts.className) node.className = opts.className;
    if (opts.text != null) text(node, opts.text);
    return node;
  }

  function setStatus(kind, message) {
    if (!els.status) return;
    els.status.className = "notice " + kind;
    els.status.textContent = message;
    els.status.hidden = !message;
  }

  function isSecUrl(url) {
    return typeof url === "string" && (
      url.indexOf("https://www.sec.gov/") === 0 ||
      url.indexOf("https://sec.gov/") === 0
    );
  }

  function formatGeneratedAt(value) {
    if (!value) return "—";
    var d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    try {
      return new Intl.DateTimeFormat("en-US", {
        timeZone: "America/Chicago",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short"
      }).format(d);
    } catch (e) {
      return String(value);
    }
  }

  function formatReviewScore(review) {
    if (!review || typeof review !== "object") return "—";
    var score = review.score_both_correct;
    if (typeof score !== "number") return "—";
    var label = String(score);
    if (review.n != null) label += " (" + review.n + "-row review)";
    return label;
  }

  function addMeta(term, value) {
    if (!els.meta) return;
    els.meta.appendChild(el("dt", { text: term }));
    els.meta.appendChild(el("dd", { text: value }));
  }

  function renderMeta(meta) {
    if (!els.meta) return;
    while (els.meta.firstChild) els.meta.removeChild(els.meta.firstChild);
    meta = meta || {};
    addMeta("Generated", formatGeneratedAt(meta.generated_at));
    addMeta("Source", SOURCE_LABEL);
    addMeta("Review score", formatReviewScore(meta.review_score));
  }

  function rowMatches(row, query) {
    if (!query) return true;
    var hay = [
      row.fund_name,
      row.series_id,
      row.filing_date,
      row.form,
      row.policy_sentence
    ].join(" ").toLowerCase();
    return hay.indexOf(query) !== -1;
  }


  function splitItems(value) {
    if (value == null || value === "") return [];
    return String(value).split(";").map(function (part) { return part.trim(); }).filter(Boolean);
  }

  function stackedCell(value, className) {
    var td = el("td", { className: className });
    var items = splitItems(value);
    if (!items.length) {
      text(td, "—");
      return td;
    }
    items.forEach(function (item) {
      td.appendChild(el("div", { className: "names-item", text: item }));
    });
    return td;
  }

  function filingLink(url) {
    if (!isSecUrl(url)) return el("span", { text: "—" });
    var a = el("a", { text: "View" });
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }

  function renderTable(rows, total) {
    while (els.results.firstChild) els.results.removeChild(els.results.firstChild);

    var article = el("article", { className: "card" });
    article.appendChild(el("h2", {
      className: "card-title",
      text: "Showing " + rows.length.toLocaleString("en-US") + " of " + total.toLocaleString("en-US") + " rows"
    }));

    var wrap = el("div", { className: "names-table-wrap" });
    var table = el("table", { className: "names-table" });
    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    [
      { label: "Fund name", className: "fund" },
      { label: "Series ID", className: "series" },
      { label: "Filing date", className: "date" },
      { label: "Form", className: "form" },
      { label: "Policy sentence", className: "policy" },
      { label: "EDGAR", className: "edgar" }
    ].forEach(function (h) {
      headRow.appendChild(el("th", { className: h.className, text: h.label }));
    });
    thead.appendChild(headRow);

    var colgroup = document.createElement("colgroup");
    ["fund", "series", "date", "form", "policy", "edgar"].forEach(function (name) {
      colgroup.appendChild(el("col", { className: name }));
    });
    table.appendChild(colgroup);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.appendChild(stackedCell(row.fund_name, "fund"));
      tr.appendChild(stackedCell(row.series_id, "series"));
      tr.appendChild(el("td", { className: "date", text: row.filing_date || "—" }));
      tr.appendChild(el("td", { className: "form", text: row.form || "—" }));
      tr.appendChild(el("td", { className: "policy", text: row.policy_sentence || "—" }));
      var linkCell = el("td", { className: "edgar" });
      linkCell.appendChild(filingLink(row.sec_filing_url));
      tr.appendChild(linkCell);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    article.appendChild(wrap);
    els.results.appendChild(article);
  }

  function applyFilter() {
    var query = (els.search && els.search.value || "").trim().toLowerCase();
    var filtered = allRows.filter(function (row) { return rowMatches(row, query); });
    renderTable(filtered, allRows.length);
    setStatus("info", DISCLAIMER);
  }

  function render(data) {
    allRows = (data && data.rows) || [];
    renderMeta(data && data.meta);
    applyFilter();
  }

  if (els.form) {
    els.form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      applyFilter();
    });
  }
  if (els.search) {
    els.search.addEventListener("input", applyFilter);
  }

  fetch(DATA_URL, { credentials: "same-origin" })
    .then(function (res) {
      if (!res.ok) throw new Error("Could not load names rule data (" + res.status + ")");
      return res.json();
    })
    .then(render)
    .catch(function (err) {
      setStatus("error", err.message || "Could not load names rule data.");
    });
})();
