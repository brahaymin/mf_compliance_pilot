(function () {
  "use strict";

  var ASSET_VERSION = (document.documentElement.getAttribute("data-asset-version") || "1").replace(/[^\w.-]/g, "");
  var ISSUE_MAP_URL = "issue_map.json?v=" + ASSET_VERSION;
  var RULES_URL = "structured_rules_sample.json?v=" + ASSET_VERSION;
  var SEC_URL_RE = /^https:\/\/(?:www\.)?sec\.gov\//i;
  var CATEGORY_LABELS = {
    sales_charge_waiver: "Sales charge waiver",
    roa: "ROA",
    loi: "LOI",
    breakpoint_schedule: "Breakpoint schedule",
    waiver_limitation: "Waiver limitation"
  };

  var state = {
    issues: [],
    rules: [],
    filings: {},
    chains: {},
    families: [],
    issueId: "",
    family: "",
    status: "current",
    query: "",
    matchIndex: {},
    openTimelines: false
  };

  var els = {
    pills: document.getElementById("issuePills"),
    select: document.getElementById("issueSelect"),
    blurb: document.getElementById("issueBlurb"),
    sources: document.getElementById("issueSources"),
    family: document.getElementById("familyFilter"),
    status: document.getElementById("statusFilter"),
    search: document.getElementById("searchInput"),
    count: document.getElementById("resultCount"),
    notice: document.getElementById("status"),
    results: document.getElementById("results")
  };

  function text(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  function setNotice(kind, message) {
    if (!els.notice) return;
    els.notice.className = "notice " + kind;
    els.notice.textContent = message;
    els.notice.hidden = !message;
  }

  function safeSecUrl(url) {
    if (!url || typeof url !== "string") return null;
    try {
      var u = new URL(url.trim());
      if (u.protocol !== "https:") return null;
      if (u.hostname !== "www.sec.gov" && u.hostname !== "sec.gov") return null;
      return u.toString();
    } catch (e) {
      return null;
    }
  }

  function filingInfo(accession) {
    var f = state.filings[accession];
    return f || null;
  }

  function secLink(url, label) {
    var href = safeSecUrl(url);
    if (!href) return document.createTextNode(label);
    var a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    text(a, label);
    return a;
  }

  function refLine(prefix, ref) {
    var p = document.createElement("p");
    var k = document.createElement("span");
    k.className = "chain-key";
    text(k, prefix + " ");
    p.appendChild(k);
    var f = filingInfo(ref.accession);
    var label = (ref.form_type || "") + " filed " + (ref.filing_date || "?");
    p.appendChild(secLink(f && f.edgar_url, label));
    p.appendChild(document.createTextNode(" (" + ref.accession + ")"));
    return p;
  }

  function renderChain(rule) {
    var box = document.createElement("div");
    box.className = "chain";
    box.setAttribute("aria-label", "Version history");
    var eff = document.createElement("p");
    var k = document.createElement("span");
    k.className = "chain-key";
    text(k, "Effective: ");
    eff.appendChild(k);
    eff.appendChild(
      document.createTextNode(
        (rule.effective_from || rule.filing_date || "unknown") +
          " → " +
          (rule.effective_to ? rule.effective_to : rule.status === "current" ? "present" : "unknown")
      )
    );
    box.appendChild(eff);
    if (rule.days_since_prior != null && rule.prior_filing_date) {
      var d = document.createElement("p");
      text(
        d,
        rule.days_since_prior + " days after prior filing (" + rule.prior_filing_date + ") of this rule"
      );
      box.appendChild(d);
    }
    if (rule.superseded_by) box.appendChild(refLine("Superseded by", rule.superseded_by));
    if (rule.amended_by) box.appendChild(refLine("Amended by", rule.amended_by));
    if (rule.amendment_note) {
      var n = document.createElement("p");
      text(n, rule.amendment_note);
      box.appendChild(n);
    }
    if (rule.chain_varies_by_ticker) {
      var v = document.createElement("p");
      text(v, "Version details shown for " + (rule.chain_shown_for || "first ticker") + "; other tickers may differ.");
      box.appendChild(v);
    }
    var chain = state.chains[rule.chain_id];
    if (chain && chain.length > 1) {
      var det = document.createElement("details");
      if (state.openTimelines) det.setAttribute("open", "");
      var sum = document.createElement("summary");
      text(sum, "Version timeline (" + chain.length + " filings)");
      det.appendChild(sum);
      var ol = document.createElement("ol");
      ol.className = "timeline";
      var sorted = chain.slice().sort(function (a, b) {
        var fa = filingInfo(a[0]) || {};
        var fb = filingInfo(b[0]) || {};
        var da = fa.filing_date || "";
        var db = fb.filing_date || "";
        if (da !== db) return da < db ? -1 : 1;
        return String(a[0]).localeCompare(String(b[0]));
      });
      sorted.forEach(function (item) {
        var acc = item[0];
        var st = item[1];
        var f = filingInfo(acc);
        var li = document.createElement("li");
        if (st === "current") li.className = "v-current";
        if (acc === rule.accession) li.className = (li.className ? li.className + " " : "") + "this-version";
        if (f && f.filing_date) {
          li.appendChild(secLink(f.edgar_url, f.filing_date + " · " + (f.form_type || "filing") + " · " + acc));
        } else {
          li.appendChild(document.createTextNode("Filing details not in sample (" + acc + ")"));
        }
        li.appendChild(
          document.createTextNode(
            " — " + (st === "current" ? "Current" : "Historical") + (acc === rule.accession ? " (this version)" : "")
          )
        );
        ol.appendChild(li);
      });
      det.appendChild(ol);
      box.appendChild(det);
    }
    return box;
  }

  function companyUrl(id) {
    if (!id || !/^[A-Z0-9]{6,10}$/i.test(String(id))) return null;
    return "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=" + encodeURIComponent(id) + "&owner=include&count=40";
  }

  function ruleText(r) {
    return [r.description, r.condition_text, r.source_snippet, r.intermediary].map(function (x) { return x || ""; }).join(" ");
  }

  function matchesClause(rule, clause) {
    if (clause.categories && clause.categories.indexOf(rule.category) === -1) return false;
    if (clause.waiver_types && clause.waiver_types.indexOf(rule.waiver_type) === -1) return false;
    if (clause.require_intermediary && !String(rule.intermediary || "").trim()) return false;
    if (clause.text_regex && !new RegExp(clause.text_regex, "i").test(ruleText(rule))) return false;
    return true;
  }

  function matchesIssue(rule, issue) {
    var clauses = issue.match || [];
    for (var i = 0; i < clauses.length; i++) {
      if (matchesClause(rule, clauses[i])) return true;
    }
    return false;
  }

  function currentIssue() {
    for (var i = 0; i < state.issues.length; i++) {
      if (state.issues[i].id === state.issueId) return state.issues[i];
    }
    return state.issues[0] || null;
  }

  function familyList() {
    var seen = {};
    var out = [];
    state.rules.forEach(function (r) {
      var f = r.fund_family;
      if (f && !seen[f]) {
        seen[f] = true;
        out.push(f);
      }
    });
    out.sort();
    return out;
  }

  function queryMatch(rule, q) {
    if (!q) return true;
    var blob = (
      (rule.description || "") + " " +
      (rule.condition_text || "") + " " +
      (rule.tickers || []).join(" ") + " " +
      (rule.fund_family || "") + " " +
      (rule.accession || "") + " " +
      (rule.ciks || []).join(" ") + " " +
      (rule.series_ids || []).join(" ") + " " +
      (rule.class_ids || []).join(" ") + " " +
      (rule.intermediary || "")
    ).toLowerCase();
    return blob.indexOf(q) !== -1;
  }

  function idLink(value, label) {
    var wrap = document.createElement("div");
    var dt = document.createElement("dt");
    text(dt, label);
    var dd = document.createElement("dd");
    var href = companyUrl(value);
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      text(a, value);
      dd.appendChild(a);
    } else {
      text(dd, value || "—");
    }
    wrap.appendChild(dt);
    wrap.appendChild(dd);
    return wrap;
  }

  function renderIdList(values, label, limit) {
    var frag = document.createDocumentFragment();
    var list = values || [];
    var shown = list.slice(0, limit || 4);
    shown.forEach(function (v) { frag.appendChild(idLink(v, label)); });
    if (list.length > shown.length) {
      var more = document.createElement("div");
      var dt = document.createElement("dt");
      text(dt, "");
      var dd = document.createElement("dd");
      dd.className = "more-ids";
      text(dd, "+" + (list.length - shown.length) + " more " + label.toLowerCase() + (list.length - shown.length === 1 ? "" : "s"));
      more.appendChild(dt);
      more.appendChild(dd);
      frag.appendChild(more);
    }
    if (!list.length) {
      frag.appendChild(idLink("", label));
    }
    return frag;
  }

  function renderGap(family, issue) {
    var card = document.createElement("article");
    card.className = "card gap-card";
    var badge = document.createElement("div");
    badge.className = "gap-badge";
    text(badge, "Coverage gap");
    card.appendChild(badge);
    var h = document.createElement("h2");
    h.className = "card-title";
    text(h, family);
    card.appendChild(h);
    var p = document.createElement("p");
    p.className = "desc";
    text(p, "No current rules in this sample map to “" + issue.title + "” for this family. That is a coverage gap for a first-priority issue.");
    card.appendChild(p);
    return card;
  }

  function renderRule(rule, issue) {
    var card = document.createElement("article");
    card.className = "card " + (rule.status === "current" ? "is-current" : "is-historical");
    var top = document.createElement("div");
    top.className = "card-top";
    var st = document.createElement("span");
    st.className = "status-badge " + (rule.status === "current" ? "status-badge--current" : "status-badge--historical");
    text(st, rule.status === "current" ? "Current" : "Historical");
    top.appendChild(st);
    var cat = document.createElement("span");
    cat.className = "chip cat-" + (rule.category || "");
    text(cat, CATEGORY_LABELS[rule.category] || rule.category || "");
    top.appendChild(cat);
    if (rule.form_type) {
      var form = document.createElement("span");
      form.className = "chip";
      text(form, rule.form_type);
      top.appendChild(form);
    }
    if (rule.filing_date) {
      var date = document.createElement("span");
      date.className = "chip";
      text(date, "Filed " + rule.filing_date);
      top.appendChild(date);
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
    text(title, rule.description || (CATEGORY_LABELS[rule.category] || "Rule"));
    card.appendChild(title);

    var ids = document.createElement("dl");
    ids.className = "ids";
    ids.appendChild(renderIdList(rule.ciks, "CIK", 3));
    ids.appendChild(renderIdList(rule.series_ids, "Series ID", 3));
    ids.appendChild(renderIdList(rule.class_ids, "Class ID", 3));
    card.appendChild(ids);

    card.appendChild(renderChain(rule));

    var foot = document.createElement("div");
    foot.className = "card-foot";
    var acc = document.createElement("span");
    var href = safeSecUrl(rule.edgar_url);
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      text(a, rule.accession || "SEC filing");
      acc.appendChild(document.createTextNode("Accession "));
      acc.appendChild(a);
    } else {
      text(acc, "Accession " + (rule.accession || "—"));
    }
    foot.appendChild(acc);
    card.appendChild(foot);

    if (issue.sources && issue.sources.length) {
      var src = document.createElement("p");
      src.className = "issue-source-line";
      src.appendChild(document.createTextNode("Issue source: "));
      issue.sources.slice(0, 2).forEach(function (s, i) {
        if (i) src.appendChild(document.createTextNode(" · "));
        if (s.url && /^https:\/\//.test(s.url)) {
          var sa = document.createElement("a");
          sa.href = s.url;
          sa.rel = "noopener noreferrer";
          sa.target = "_blank";
          text(sa, s.label || s.url);
          src.appendChild(sa);
        } else {
          src.appendChild(document.createTextNode(s.label || ""));
        }
      });
      card.appendChild(src);
    }
    return card;
  }

  function render() {
    var issue = currentIssue();
    els.results.innerHTML = "";
    if (!issue) {
      text(els.count, "No issues available.");
      return;
    }
    var q = (state.query || "").trim().toLowerCase();
    var matched = state.matchIndex[issue.id] || [];
    var families = state.family ? [state.family] : state.families.slice();
    var total = 0;
    var gaps = 0;
    var shownFamilies = 0;

    if (issue.tier === "P1" && state.status === "current" && !q) {
      var missing = families.filter(function (fam) {
        return !matched.some(function (r) { return r.status === "current" && r.fund_family === fam; });
      });
      if (missing.length && families.length) {
        var sum = document.createElement("p");
        sum.className = "notice error coverage-summary";
        text(sum, missing.length + " coverage gap" + (missing.length === 1 ? "" : "s") + " for this first-priority issue (no current rules in the sample).");
        els.results.appendChild(sum);
      } else if (families.length) {
        var ok = document.createElement("p");
        ok.className = "notice info coverage-summary";
        text(ok, "Every family in this view has at least one current rule for this first-priority issue.");
        els.results.appendChild(ok);
      }
    }

    families.forEach(function (fam) {
      var rows = matched.filter(function (r) {
        if (r.fund_family !== fam) return false;
        if (state.status && r.status !== state.status) return false;
        if (!queryMatch(r, q)) return false;
        return true;
      });
      var currentForFam = matched.filter(function (r) { return r.fund_family === fam && r.status === "current"; });
      var showGap = issue.tier === "P1" && state.status === "current" && !q && currentForFam.length === 0;
      if (!rows.length && !showGap) return;
      shownFamilies += 1;
      var block = document.createElement("section");
      block.className = "family-block";
      var h = document.createElement("h2");
      h.id = "family-" + fam.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      h.appendChild(document.createTextNode(fam + " "));
      var cnt = document.createElement("span");
      cnt.className = "family-count";
      text(cnt, showGap && !rows.length ? "coverage gap" : (rows.length + " rule" + (rows.length === 1 ? "" : "s")));
      h.appendChild(cnt);
      block.appendChild(h);
      if (showGap) {
        block.appendChild(renderGap(fam, issue));
        gaps += 1;
      }
      rows.forEach(function (r) {
        block.appendChild(renderRule(r, issue));
        total += 1;
      });
      els.results.appendChild(block);
    });

    var parts = [total + " rule" + (total === 1 ? "" : "s")];
    if (gaps) parts.push(gaps + " coverage gap" + (gaps === 1 ? "" : "s"));
    parts.push(issue.tier + " · " + issue.title);
    text(els.count, parts.join(" · "));
    setNotice("", "");
  }

  function renderIssuePicker() {
    els.pills.innerHTML = "";
    els.select.innerHTML = "";
    state.issues.forEach(function (issue, idx) {
      var pill = document.createElement("button");
      pill.type = "button";
      pill.className = "issue-pill";
      pill.setAttribute("role", "option");
      pill.setAttribute("aria-selected", issue.id === state.issueId ? "true" : "false");
      var tier = document.createElement("span");
      tier.className = "tier";
      text(tier, issue.tier);
      pill.appendChild(tier);
      pill.appendChild(document.createTextNode(issue.title));
      pill.addEventListener("click", function () { selectIssue(issue.id); });
      els.pills.appendChild(pill);
      var opt = document.createElement("option");
      opt.value = issue.id;
      text(opt, issue.tier + " — " + issue.title);
      if (issue.id === state.issueId) opt.selected = true;
      els.select.appendChild(opt);
    });
    var issue = currentIssue();
    text(els.blurb, issue ? issue.blurb : "");
    els.sources.innerHTML = "";
    if (issue && issue.sources) {
      issue.sources.forEach(function (s) {
        if (!s.url || !/^https:\/\//.test(s.url)) return;
        var a = document.createElement("a");
        a.href = s.url;
        a.rel = "noopener noreferrer";
        a.target = "_blank";
        text(a, s.label || s.url);
        els.sources.appendChild(a);
      });
    }
  }

  function selectIssue(id) {
    state.issueId = id;
    renderIssuePicker();
    render();
  }

  function populateFamilies() {
    state.families = familyList();
    var keep = els.family.value;
    els.family.innerHTML = "";
    var all = document.createElement("option");
    all.value = "";
    text(all, "All families");
    els.family.appendChild(all);
    state.families.forEach(function (f) {
      var o = document.createElement("option");
      o.value = f;
      text(o, f);
      els.family.appendChild(o);
    });
    if (keep && state.families.indexOf(keep) !== -1) els.family.value = keep;
  }

  function buildMatchIndex() {
    state.matchIndex = {};
    state.issues.forEach(function (issue) {
      state.matchIndex[issue.id] = state.rules.filter(function (r) { return matchesIssue(r, issue); });
    });
  }

  els.select.addEventListener("change", function () { selectIssue(els.select.value); });
  els.family.addEventListener("change", function () { state.family = els.family.value; render(); });
  els.status.addEventListener("change", function () { state.status = els.status.value; render(); });
  var searchTimer = null;
  els.search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      state.query = els.search.value;
      render();
    }, 150);
  });

  Promise.all([
    fetch(ISSUE_MAP_URL, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("Could not load issue map (" + r.status + ")");
      return r.json();
    }),
    fetch(RULES_URL, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("Could not load rule sample (" + r.status + ")");
      return r.json();
    })
  ]).then(function (pair) {
    var map = pair[0];
    var data = pair[1];
    var tierRank = { P1: 1, P2: 2, P3: 3 };
    state.issues = (map.issues || []).slice().sort(function (a, b) {
      return (tierRank[a.tier] || 9) - (tierRank[b.tier] || 9) || (a.sort_order || 0) - (b.sort_order || 0);
    });
    state.rules = data.rules || [];
    state.filings = data.filings || {};
    state.chains = data.chains || {};
    state.issueId = (state.issues[0] && state.issues[0].id) || "";
    try {
      var params = new URLSearchParams(location.search);
      var qIssue = params.get("issue");
      var qFam = params.get("family");
      var qStatus = params.get("status");
      var qText = params.get("q");
      if (qIssue && state.issues.some(function (i) { return i.id === qIssue; })) state.issueId = qIssue;
      if (qFam) state.family = qFam;
      if (qStatus === "current" || qStatus === "historical" || qStatus === "") state.status = qStatus;
      if (qText) {
        state.query = qText;
        if (els.search) els.search.value = qText;
      }
      if (params.get("timeline") === "open") state.openTimelines = true;
    } catch (e) {}
    buildMatchIndex();
    populateFamilies();
    if (state.family) els.family.value = state.family;
    els.status.value = state.status;
    renderIssuePicker();
    render();
  }).catch(function (err) {
    setNotice("error", err.message || "Could not load the issue view.");
  });
})();
