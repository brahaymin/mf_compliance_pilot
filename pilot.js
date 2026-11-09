(function () {
  "use strict";

  var STRUCTURED_URL = "structured_rules_sample.json";
  var LEGACY_URL = "sample_rules.json";
  var SEC_URL_RE = /^https:\/\/(?:www\.)?sec\.gov\//i;

  var CATEGORY_LABELS = {
    sales_charge_waiver: "Sales charge waiver",
    roa: "ROA",
    loi: "LOI",
    breakpoint_schedule: "Breakpoint schedule",
    waiver_limitation: "Waiver limitation",
  };

  var WAIVER_TYPE_LABELS = {
    front_end: "Front-end",
    cdsc: "CDSC",
    intermediary_front_end: "Intermediary front-end",
    intermediary_cdsc: "Intermediary CDSC",
    intermediary_discount: "Intermediary discount",
  };

  var state = {
    mode: "structured", // structured | legacy
    structured: { rules: [], meta: null },
    legacy: { rules: [], meta: null, loaded: false, loading: false, error: null },
    query: "",
    category: "",
    waiverType: "",
    intermediary: "",
  };

  var els = {
    status: document.getElementById("status"),
    metaBar: document.getElementById("metaBar"),
    results: document.getElementById("results"),
    count: document.getElementById("resultCount"),
    search: document.getElementById("searchInput"),
    clear: document.getElementById("clearBtn"),
    form: document.getElementById("searchForm"),
    snapshot: document.getElementById("snapshotInfo"),
    structuredFilters: document.getElementById("structuredFilters"),
    categoryChips: document.getElementById("categoryChips"),
    waiverTypeFilter: document.getElementById("waiverTypeFilter"),
    intermediaryFilter: document.getElementById("intermediaryFilter"),
    tabStructured: document.getElementById("tabStructured"),
    tabLegacy: document.getElementById("tabLegacy"),
  };

  function setStatus(kind, message) {
    if (!els.status) return;
    els.status.className = "notice " + kind;
    els.status.textContent = message;
    els.status.hidden = !message;
  }

  function text(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  function safeSecUrl(url) {
    if (!url || typeof url !== "string") return null;
    var trimmed = url.trim();
    if (!SEC_URL_RE.test(trimmed)) return null;
    try {
      var u = new URL(trimmed);
      if (u.protocol !== "https:") return null;
      if (u.hostname !== "www.sec.gov" && u.hostname !== "sec.gov") return null;
      return u.toString();
    } catch (e) {
      return null;
    }
  }

  function normalize(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function appendHighlighted(container, value, q) {
    var raw = value == null ? "" : String(value);
    if (!q) {
      container.appendChild(document.createTextNode(raw));
      return;
    }
    var re;
    try {
      re = new RegExp(escapeRegExp(q), "ig");
    } catch (e) {
      container.appendChild(document.createTextNode(raw));
      return;
    }
    var last = 0;
    var match;
    while ((match = re.exec(raw)) !== null) {
      if (match.index > last) {
        container.appendChild(document.createTextNode(raw.slice(last, match.index)));
      }
      var mark = document.createElement("mark");
      mark.className = "mark";
      mark.textContent = match[0];
      container.appendChild(mark);
      last = match.index + match[0].length;
      if (match[0].length === 0) re.lastIndex += 1;
    }
    if (last < raw.length) {
      container.appendChild(document.createTextNode(raw.slice(last)));
    }
  }

  function categoryLabel(cat) {
    return CATEGORY_LABELS[cat] || cat || "Rule";
  }

  function waiverLabel(wt) {
    return WAIVER_TYPE_LABELS[wt] || wt || "";
  }

  function matchesStructured(rule, q) {
    if (!q) return true;
    var hay = [
      rule.fund_family,
      rule.description,
      rule.condition_text,
      rule.source_snippet,
      rule.form_type,
      rule.accession,
      rule.source,
      rule.waiver_type,
      rule.intermediary,
      rule.notes,
      categoryLabel(rule.category),
      (rule.tickers || []).join(" "),
    ]
      .map(normalize)
      .join("\n");
    return hay.indexOf(q) !== -1;
  }

  function matchesLegacy(rule, q) {
    if (!q) return true;
    var hay = [
      rule.ticker,
      rule.family,
      rule.fund_name,
      rule.description,
      rule.source_snippet,
      rule.form_type,
      rule.accession,
    ]
      .map(normalize)
      .join("\n");
    return hay.indexOf(q) !== -1;
  }

  function filteredStructured() {
    var q = normalize(state.query);
    return state.structured.rules.filter(function (rule) {
      if (state.category && rule.category !== state.category) return false;
      if (state.waiverType && (rule.waiver_type || "") !== state.waiverType) return false;
      if (state.intermediary && (rule.intermediary || "") !== state.intermediary) return false;
      return matchesStructured(rule, q);
    });
  }

  function filteredLegacy() {
    var q = normalize(state.query);
    return state.legacy.rules.filter(function (rule) {
      return matchesLegacy(rule, q);
    });
  }

  function renderMeta() {
    if (!els.metaBar) return;
    els.metaBar.innerHTML = "";
    var meta = state.mode === "structured" ? state.structured.meta : state.legacy.meta;
    var rules = state.mode === "structured" ? state.structured.rules : state.legacy.rules;
    if (!meta) return;
    var bits;
    if (state.mode === "structured") {
      bits = [
        ["Entries", String(meta.sample_entry_count || rules.length)],
        ["Tickers", String(meta.distinct_tickers_in_sample || "—")],
        ["Filings", String(meta.distinct_accessions_in_sample || "—")],
        ["Family", "Guggenheim"],
        ["Snapshot", meta.snapshot_date_america_chicago || "—"],
      ];
    } else {
      bits = [
        ["Sample rules", String(meta.sample_count || rules.length)],
        ["Tickers", String(meta.distinct_tickers_in_sample || "—")],
        ["Funds", String(meta.distinct_fund_names_in_sample || "—")],
        ["Snapshot", meta.snapshot_date_america_chicago || "—"],
      ];
    }
    bits.forEach(function (pair) {
      var span = document.createElement("span");
      var strong = document.createElement("strong");
      text(strong, pair[0] + ": ");
      span.appendChild(strong);
      span.appendChild(document.createTextNode(pair[1]));
      els.metaBar.appendChild(span);
    });
    if (els.snapshot) {
      var note =
        (meta.coverage_note || "") +
        " " +
        (meta.fund_family_coverage || meta.family_note || "") +
        " " +
        (meta.selection_note || "");
      text(els.snapshot, note.trim());
    }
  }

  function fillFilterOptions() {
    var waiverTypes = {};
    var intermediaries = {};
    state.structured.rules.forEach(function (r) {
      if (r.waiver_type) waiverTypes[r.waiver_type] = true;
      if (r.intermediary) intermediaries[r.intermediary] = true;
    });
    if (els.waiverTypeFilter) {
      var current = els.waiverTypeFilter.value;
      els.waiverTypeFilter.innerHTML = "";
      var optAll = document.createElement("option");
      optAll.value = "";
      text(optAll, "All waiver types");
      els.waiverTypeFilter.appendChild(optAll);
      Object.keys(waiverTypes)
        .sort()
        .forEach(function (wt) {
          var opt = document.createElement("option");
          opt.value = wt;
          text(opt, waiverLabel(wt));
          els.waiverTypeFilter.appendChild(opt);
        });
      els.waiverTypeFilter.value = current;
    }
    if (els.intermediaryFilter) {
      var curI = els.intermediaryFilter.value;
      els.intermediaryFilter.innerHTML = "";
      var allI = document.createElement("option");
      allI.value = "";
      text(allI, "All intermediaries");
      els.intermediaryFilter.appendChild(allI);
      Object.keys(intermediaries)
        .sort(function (a, b) {
          return a.localeCompare(b);
        })
        .forEach(function (name) {
          var opt = document.createElement("option");
          opt.value = name;
          text(opt, name);
          els.intermediaryFilter.appendChild(opt);
        });
      els.intermediaryFilter.value = curI;
    }
    if (els.categoryChips) {
      els.categoryChips.innerHTML = "";
      var cats = [""].concat(
        Object.keys(CATEGORY_LABELS).filter(function (c) {
          return state.structured.rules.some(function (r) {
            return r.category === c;
          });
        })
      );
      cats.forEach(function (cat) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chip-btn";
        btn.setAttribute("aria-pressed", state.category === cat ? "true" : "false");
        text(btn, cat ? categoryLabel(cat) : "All categories");
        btn.addEventListener("click", function () {
          state.category = cat;
          Array.prototype.forEach.call(els.categoryChips.querySelectorAll(".chip-btn"), function (b) {
            b.setAttribute("aria-pressed", "false");
          });
          btn.setAttribute("aria-pressed", "true");
          render();
        });
        els.categoryChips.appendChild(btn);
      });
    }
  }

  function renderTier(tiers) {
    if (!tiers || !tiers.length) return null;
    var wrap = document.createElement("div");
    wrap.className = "tier-wrap";
    var table = document.createElement("table");
    table.className = "tier-table";
    table.setAttribute("aria-label", "Breakpoint tiers");
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    ["Amount", "Offering price", "Net amount invested", "Dealer allowance"].forEach(function (h) {
      var th = document.createElement("th");
      text(th, h);
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    tiers.forEach(function (t) {
      var tr = document.createElement("tr");
      [t.amount, t.pct_offering_price, t.pct_net_amount_invested, t.dealer_allowance].forEach(function (v) {
        var td = document.createElement("td");
        text(td, v || "—");
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function renderStructuredCard(rule, q) {
    var card = document.createElement("article");
    card.className = "card";
    card.setAttribute("aria-label", categoryLabel(rule.category) + " rule");

    var top = document.createElement("div");
    top.className = "card-top";

    var cat = document.createElement("span");
    cat.className = "chip cat-" + (rule.category || "");
    text(cat, categoryLabel(rule.category));
    top.appendChild(cat);

    if (rule.waiver_type) {
      var wt = document.createElement("span");
      wt.className = "chip";
      text(wt, waiverLabel(rule.waiver_type));
      top.appendChild(wt);
    }
    if (rule.form_type) {
      var form = document.createElement("span");
      form.className = "chip";
      text(form, rule.form_type);
      top.appendChild(form);
    }
    if (rule.filing_date) {
      var date = document.createElement("span");
      date.className = "chip";
      text(date, rule.filing_date);
      top.appendChild(date);
    }
    if (rule.source) {
      var src = document.createElement("span");
      src.className = "chip";
      text(src, rule.source);
      top.appendChild(src);
    }
    if (rule.fund_family) {
      var fam = document.createElement("span");
      fam.className = "chip";
      text(fam, rule.fund_family);
      top.appendChild(fam);
    }
    card.appendChild(top);

    if (rule.tickers && rule.tickers.length) {
      var tickers = document.createElement("div");
      tickers.className = "tickers";
      text(tickers, rule.tickers.join(", "));
      card.appendChild(tickers);
    }

    var title = document.createElement("h2");
    title.className = "card-title";
    appendHighlighted(title, rule.description || categoryLabel(rule.category), q);
    card.appendChild(title);

    if (rule.intermediary) {
      var inter = document.createElement("p");
      inter.className = "desc";
      var strong = document.createElement("strong");
      text(strong, "Intermediary: ");
      inter.appendChild(strong);
      appendHighlighted(inter, rule.intermediary, q);
      card.appendChild(inter);
    }

    if (rule.condition_text) {
      var condLabel = document.createElement("p");
      condLabel.className = "desc";
      text(condLabel, "Condition");
      card.appendChild(condLabel);
      var cond = document.createElement("p");
      cond.className = "condition";
      appendHighlighted(cond, rule.condition_text, q);
      card.appendChild(cond);
    }

    var tiers = renderTier(rule.breakpoint_tiers);
    if (tiers) card.appendChild(tiers);

    if (rule.source_snippet) {
      var snip = document.createElement("blockquote");
      snip.className = "snippet";
      appendHighlighted(snip, rule.source_snippet, q);
      card.appendChild(snip);
    }

    var foot = document.createElement("div");
    foot.className = "card-foot";
    if (rule.accession) {
      var acc = document.createElement("span");
      text(acc, "Accession " + rule.accession);
      foot.appendChild(acc);
    }
    var href = safeSecUrl(rule.edgar_url);
    if (href) {
      var link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      text(link, "View SEC filing");
      foot.appendChild(link);
    }
    card.appendChild(foot);
    return card;
  }

  function renderLegacyCard(rule, q) {
    var card = document.createElement("article");
    card.className = "card";
    card.setAttribute("aria-label", (rule.ticker || "Rule") + " waiver excerpt");

    var top = document.createElement("div");
    top.className = "card-top";
    var ticker = document.createElement("span");
    ticker.className = "ticker";
    text(ticker, rule.ticker || "—");
    top.appendChild(ticker);
    if (rule.form_type) {
      var form = document.createElement("span");
      form.className = "chip";
      text(form, rule.form_type);
      top.appendChild(form);
    }
    if (rule.filing_date) {
      var date = document.createElement("span");
      date.className = "chip";
      text(date, rule.filing_date);
      top.appendChild(date);
    }
    card.appendChild(top);

    var name = document.createElement("h2");
    name.className = "fund-name";
    appendHighlighted(name, rule.fund_name || "Fund name unavailable", q);
    card.appendChild(name);

    var desc = document.createElement("p");
    desc.className = "desc";
    appendHighlighted(desc, rule.description || "Waiver language", q);
    card.appendChild(desc);

    var snip = document.createElement("blockquote");
    snip.className = "snippet";
    appendHighlighted(snip, rule.source_snippet || "", q);
    card.appendChild(snip);

    var foot = document.createElement("div");
    foot.className = "card-foot";
    if (rule.accession) {
      var acc = document.createElement("span");
      text(acc, "Accession " + rule.accession);
      foot.appendChild(acc);
    }
    var href = safeSecUrl(rule.edgar_url);
    if (href) {
      var link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      text(link, "View SEC filing");
      foot.appendChild(link);
    }
    card.appendChild(foot);
    return card;
  }

  function render() {
    var q = normalize(state.query);
    var matched =
      state.mode === "structured" ? filteredStructured() : filteredLegacy();
    var total =
      state.mode === "structured"
        ? state.structured.rules.length
        : state.legacy.rules.length;
    text(els.count, matched.length + " of " + total + " sample " + (state.mode === "structured" ? "entries" : "rules"));
    els.results.innerHTML = "";

    if (!matched.length) {
      var empty = document.createElement("div");
      empty.className = "empty panel";
      text(
        empty,
        q || state.category || state.waiverType || state.intermediary
          ? "No rules matched the current search/filters. Try another ticker, category, or keyword."
          : "No rules available in this sample."
      );
      els.results.appendChild(empty);
      return;
    }

    var frag = document.createDocumentFragment();
    matched.forEach(function (rule) {
      frag.appendChild(
        state.mode === "structured" ? renderStructuredCard(rule, q) : renderLegacyCard(rule, q)
      );
    });
    els.results.appendChild(frag);
  }

  function setMode(mode) {
    state.mode = mode;
    if (els.tabStructured) els.tabStructured.setAttribute("aria-selected", mode === "structured" ? "true" : "false");
    if (els.tabLegacy) els.tabLegacy.setAttribute("aria-selected", mode === "legacy" ? "true" : "false");
    if (els.structuredFilters) els.structuredFilters.hidden = mode !== "structured";
    if (mode === "legacy") {
      ensureLegacyLoaded().then(function () {
        renderMeta();
        render();
      });
    } else {
      setStatus(
        "warn",
        "Pilot demo only — static structured sample (Guggenheim). Automated extraction is unreviewed; not legal advice."
      );
      renderMeta();
      render();
    }
  }

  function ensureLegacyLoaded() {
    if (state.legacy.loaded) {
      setStatus(
        "warn",
        "Legacy regex snippets sample — broader families, less structured. Automated and unreviewed; not legal advice."
      );
      return Promise.resolve();
    }
    if (state.legacy.loading) return state.legacy.loading;
    setStatus("info", "Loading legacy sample…");
    state.legacy.loading = fetch(LEGACY_URL, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("Could not load " + LEGACY_URL);
        return res.json();
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.rules)) throw new Error("Legacy sample invalid");
        state.legacy.meta = data.meta || {};
        state.legacy.rules = data.rules || [];
        state.legacy.loaded = true;
        setStatus(
          "warn",
          "Legacy regex snippets sample — broader families, less structured. Automated and unreviewed; not legal advice."
        );
      })
      .catch(function (err) {
        state.legacy.error = String(err && err.message ? err.message : err);
        setStatus("error", "Failed to load legacy sample_rules.json.");
        console.error(err);
      })
      .finally(function () {
        state.legacy.loading = null;
      });
    return state.legacy.loading;
  }

  function onSearchSubmit(event) {
    if (event) event.preventDefault();
    state.query = els.search.value || "";
    render();
  }

  function onClear() {
    els.search.value = "";
    state.query = "";
    state.category = "";
    state.waiverType = "";
    state.intermediary = "";
    if (els.waiverTypeFilter) els.waiverTypeFilter.value = "";
    if (els.intermediaryFilter) els.intermediaryFilter.value = "";
    fillFilterOptions();
    els.search.focus();
    render();
  }

  function init() {
    if (els.form) els.form.addEventListener("submit", onSearchSubmit);
    if (els.clear) els.clear.addEventListener("click", onClear);
    if (els.search) {
      var timer = null;
      els.search.addEventListener("input", function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
          state.query = els.search.value || "";
          render();
        }, 120);
      });
    }
    if (els.waiverTypeFilter) {
      els.waiverTypeFilter.addEventListener("change", function () {
        state.waiverType = els.waiverTypeFilter.value || "";
        render();
      });
    }
    if (els.intermediaryFilter) {
      els.intermediaryFilter.addEventListener("change", function () {
        state.intermediary = els.intermediaryFilter.value || "";
        render();
      });
    }
    if (els.tabStructured) els.tabStructured.addEventListener("click", function () { setMode("structured"); });
    if (els.tabLegacy) els.tabLegacy.addEventListener("click", function () { setMode("legacy"); });

    setStatus("info", "Loading structured sample…");
    fetch(STRUCTURED_URL, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("Could not load " + STRUCTURED_URL + " (" + res.status + ").");
        return res.json();
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.rules)) throw new Error("Structured sample missing rules array.");
        if (data.meta && data.meta.schema && data.meta.schema !== "structured_rules_v1") {
          console.warn("Unexpected schema", data.meta.schema);
        }
        state.structured.meta = data.meta || {};
        state.structured.rules = data.rules || [];
        fillFilterOptions();
        setMode("structured");
      })
      .catch(function (err) {
        setStatus(
          "error",
          "Failed to load structured_rules_sample.json. Serve the docs/ folder over HTTP (GitHub Pages or a local static server)."
        );
        text(els.count, "0 entries loaded");
        console.error(err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
