(function () {
  "use strict";

  var ASSET_VERSION = (document.documentElement.getAttribute("data-asset-version") || "1").replace(/[^\w.-]/g, "");
  var DATA_URL = "coverage_slices.json?v=" + ASSET_VERSION;

  var els = {
    status: document.getElementById("status"),
    results: document.getElementById("coverage"),
  };

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

  function fmt(n) {
    if (n == null || n === "") return "—";
    var num = Number(n);
    if (!isFinite(num)) return String(n);
    return num.toLocaleString("en-US");
  }

  function setStatus(kind, message) {
    if (!els.status) return;
    els.status.className = "notice " + kind;
    els.status.textContent = message;
    els.status.hidden = !message;
  }

  function table(headers, rows) {
    var wrap = el("div", { className: "coverage-table-wrap" });
    var t = el("table", { className: "coverage-table" });
    var thead = document.createElement("thead");
    var tr = document.createElement("tr");
    headers.forEach(function (h) {
      var th = el("th", { text: h.label });
      if (h.numeric) th.className = "num";
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var r = document.createElement("tr");
      headers.forEach(function (h) {
        var td = document.createElement("td");
        if (h.numeric) {
          td.className = "num";
          text(td, fmt(row[h.key]));
        } else {
          text(td, row[h.key] == null ? "—" : row[h.key]);
        }
        r.appendChild(td);
      });
      tbody.appendChild(r);
    });
    t.appendChild(tbody);
    wrap.appendChild(t);
    return wrap;
  }

  function card(title, bodyFn) {
    var article = el("article", { className: "card coverage-card" });
    article.appendChild(el("h2", { className: "card-title", text: title }));
    bodyFn(article);
    return article;
  }

  function render(data) {
    els.results.innerHTML = "";
    var meta = (data && data.meta) || {};
    var filings = (data && data.filings) || {};
    var rules = (data && data.structured_rules) || {};

    var intro = card("Snapshot", function (article) {
      var p = el("p", { className: "coverage-meta" });
      text(p, (filings.count != null ? fmt(filings.count) + " filings" : "Filings unavailable") +
        (filings.filing_date_min && filings.filing_date_max
          ? " dated " + filings.filing_date_min + " to " + filings.filing_date_max
          : "") +
        (rules.count != null ? " · " + fmt(rules.count) + " structured-rule rows" : "") +
        (data.funds && data.funds.count != null ? " · " + fmt(data.funds.count) + " funds" : "") +
        (data.share_classes && data.share_classes.count != null ? " · " + fmt(data.share_classes.count) + " share classes" : "") +
        ".");
      article.appendChild(p);
      if (meta.coverage_note) article.appendChild(el("p", { className: "coverage-meta", text: meta.coverage_note }));
    });
    els.results.appendChild(intro);

    els.results.appendChild(card("Filings by year", function (article) {
      article.appendChild(table(
        [{ label: "Year", key: "year" }, { label: "Filings", key: "count", numeric: true }],
        filings.by_year || []
      ));
    }));

    els.results.appendChild(card("Filings by form type", function (article) {
      article.appendChild(table(
        [{ label: "Form type", key: "form_type" }, { label: "Filings", key: "count", numeric: true }],
        filings.by_form_type || []
      ));
    }));

    els.results.appendChild(card("Structured rules by family and status", function (article) {
      article.appendChild(table(
        [
          { label: "Fund family", key: "fund_family" },
          { label: "Status", key: "status" },
          { label: "Rows", key: "count", numeric: true }
        ],
        rules.by_family_status || []
      ));
    }));

    els.results.appendChild(card("Current structured-rule coverage by family", function (article) {
      article.appendChild(table(
        [
          { label: "Fund family", key: "fund_family" },
          { label: "Current rows", key: "current_rows", numeric: true },
          { label: "Waivers", key: "waiver_rows", numeric: true },
          { label: "ROA", key: "roa_rows", numeric: true },
          { label: "LOI", key: "loi_rows", numeric: true },
          { label: "Breakpoints", key: "breakpoint_rows", numeric: true },
          { label: "Limitations", key: "limitation_rows", numeric: true },
          { label: "Household language", key: "household_rows", numeric: true },
          { label: "Named intermediaries", key: "named_intermediaries", numeric: true }
        ],
        rules.family_coverage_current || []
      ));
    }));

    var note = meta.privacy_note || "Aggregated public-filing counts only; not legal advice.";
    setStatus("info", note);
  }

  fetch(DATA_URL, { credentials: "same-origin" })
    .then(function (res) {
      if (!res.ok) throw new Error("Could not load coverage slices (" + res.status + ")");
      return res.json();
    })
    .then(render)
    .catch(function (err) {
      setStatus("error", err.message || "Could not load coverage slices.");
    });
})();
