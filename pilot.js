(function () {
  "use strict";

  var DATA_URL = "sample_rules.json";
  var SEC_URL_RE = /^https:\/\/(?:www\.)?sec\.gov\//i;
  var state = {
    rules: [],
    meta: null,
    query: "",
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

  function matches(rule, q) {
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
      if (match[0].length === 0) {
        re.lastIndex += 1;
      }
    }
    if (last < raw.length) {
      container.appendChild(document.createTextNode(raw.slice(last)));
    }
  }

  function renderMeta() {
    if (!state.meta || !els.metaBar) return;
    var m = state.meta;
    els.metaBar.innerHTML = "";
    var bits = [
      ["Sample rules", String(m.sample_count || state.rules.length)],
      ["Tickers", String(m.distinct_tickers_in_sample || "—")],
      ["Funds", String(m.distinct_fund_names_in_sample || "—")],
      ["Snapshot", m.snapshot_date_america_chicago || "—"],
    ];
    bits.forEach(function (pair) {
      var span = document.createElement("span");
      var strong = document.createElement("strong");
      text(strong, pair[0] + ": ");
      span.appendChild(strong);
      span.appendChild(document.createTextNode(pair[1]));
      els.metaBar.appendChild(span);
    });
    if (els.snapshot) {
      var note = (m.coverage_note || "") + " " + (m.family_note || "");
      text(els.snapshot, note.trim());
    }
  }

  function render() {
    var q = normalize(state.query);
    var matched = state.rules.filter(function (r) {
      return matches(r, q);
    });
    text(els.count, matched.length + " of " + state.rules.length + " sample rules");
    els.results.innerHTML = "";

    if (!matched.length) {
      var empty = document.createElement("div");
      empty.className = "empty panel";
      text(
        empty,
        q
          ? 'No rules matched "' + state.query + '". Try a ticker, fund name fragment, or keyword like "CDSC" or "breakpoint".'
          : "No rules available in this sample."
      );
      els.results.appendChild(empty);
      return;
    }

    var frag = document.createDocumentFragment();
    matched.forEach(function (rule) {
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
      if (rule.family) {
        var fam = document.createElement("span");
        fam.className = "chip";
        text(fam, rule.family);
        top.appendChild(fam);
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
      frag.appendChild(card);
    });
    els.results.appendChild(frag);
  }

  function onSearchSubmit(event) {
    if (event) event.preventDefault();
    state.query = els.search.value || "";
    render();
  }

  function onClear() {
    els.search.value = "";
    state.query = "";
    els.search.focus();
    render();
  }

  function validatePayload(data) {
    if (!data || typeof data !== "object") throw new Error("Sample file is not an object.");
    if (!Array.isArray(data.rules)) throw new Error("Sample file is missing a rules array.");
    return data;
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

    setStatus("info", "Loading sample rules…");
    fetch(DATA_URL, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("Could not load " + DATA_URL + " (" + res.status + ").");
        return res.json();
      })
      .then(function (data) {
        data = validatePayload(data);
        state.meta = data.meta || {};
        state.rules = data.rules || [];
        renderMeta();
        setStatus(
          "warn",
          "Pilot demo only — static sample, not the live library. Extracted text is automated and unreviewed; not legal advice."
        );
        render();
      })
      .catch(function (err) {
        setStatus(
          "error",
          "Failed to load sample data. If you opened this file directly from disk, serve the docs/ folder over HTTP (GitHub Pages or a local static server)."
        );
        text(els.count, "0 rules loaded");
        console.error(err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
