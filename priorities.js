(function () {
  "use strict";

  const state = { tier: "all", ready: "all", groups: [], stats: null };

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (v == null || v === false) return;
        if (k === "class") node.className = v;
        else if (k === "html") node.innerHTML = v;
        else if (k === "text") node.textContent = v;
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? "" : v);
      });
    }
    (children || []).forEach((c) => { if (c) node.appendChild(c); });
    return node;
  }

  function ideaVisible(idea) {
    if (state.tier !== "all" && idea.tier !== state.tier) return false;
    if (state.ready === "ready" && !idea.ready) return false;
    if (state.ready === "awaiting" && idea.ready) return false;
    return true;
  }

  function sourceBlock(idea) {
    const wrap = el("dd");
    if (idea.sources && idea.sources.length) {
      const ul = el("ul", { class: "source-list" });
      idea.sources.forEach((s) => {
        ul.appendChild(el("li", {}, [
          el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer", text: s.label }),
        ]));
      });
      wrap.appendChild(ul);
    }
    if (idea.source_note) wrap.appendChild(el("p", { class: "source-note", text: idea.source_note }));
    if (!idea.sources?.length && !idea.source_note) {
      wrap.appendChild(el("p", { class: "source-note", text: "No direct source URL in the approved priorities document." }));
    }
    return wrap;
  }

  function renderIdea(idea) {
    const card = el("article", {
      class: "card idea-card " + (idea.ready ? "ready" : "awaiting"),
      id: idea.id,
    }, [
      el("div", { class: "card-top" }, [
        el("span", { class: "chip " + (idea.tier === "P1" ? "tier-p1" : idea.tier === "P2" ? "tier-p2" : "tier-p3"), text: idea.tier }),
        el("span", { class: "chip " + (idea.ready ? "ready-yes" : "ready-no"), text: idea.readiness }),
        el("span", { class: "chip", text: idea.id }),
      ]),
      el("h3", { text: idea.title }),
      el("dl", { class: "dl" }, [
        el("dt", { text: "The issue" }),
        el("dd", { text: idea.issue }),
        el("dt", { text: "Why it matters" }),
        el("dd", { text: idea.why }),
        el("dt", { text: "Source" }),
        sourceBlock(idea),
        el("dt", { text: "How the database helps" }),
        el("dd", { text: idea.db }),
      ]),
    ]);
    if (idea.needs) {
      card.querySelector("dl").appendChild(el("dt", { text: "Waiting on" }));
      card.querySelector("dl").appendChild(el("dd", { text: idea.needs }));
    }
    return card;
  }

  function renderList() {
    const root = document.getElementById("priorityList");
    const counts = document.getElementById("priorityCounts");
    root.innerHTML = "";
    let shown = 0;
    let ready = 0;
    let awaiting = 0;
    state.groups.forEach((group) => {
      const ideas = group.ideas.filter(ideaVisible);
      if (!ideas.length) return;
      shown += ideas.length;
      ideas.forEach((i) => { if (i.ready) ready += 1; else awaiting += 1; });
      const section = el("section", { class: "issue-group", "aria-labelledby": "g-" + group.id }, [
        el("h2", { id: "g-" + group.id, text: group.title }),
        el("p", { class: "issue-blurb", text: group.blurb }),
        el("div", { class: "idea-grid" }, ideas.map(renderIdea)),
      ]);
      root.appendChild(section);
    });
    if (!shown) {
      root.appendChild(el("p", { class: "empty", text: "No priorities match this filter." }));
    }
    counts.textContent = "Showing " + shown + " of 39 ideas (" + ready + " ready now, " + awaiting + " awaiting data).";
  }

  function setFilter(kind, value) {
    state[kind] = value;
    document.querySelectorAll("#filterBar [data-kind='" + kind + "']").forEach((btn) => {
      btn.setAttribute("aria-pressed", btn.getAttribute("data-value") === value ? "true" : "false");
    });
    renderList();
  }

  function renderFilters() {
    const bar = document.getElementById("filterBar");
    const groups = [
      { kind: "tier", options: [["all", "All tiers"], ["P1", "First priority"], ["P2", "Second priority"], ["P3", "Later"]] },
      { kind: "ready", options: [["all", "All readiness"], ["ready", "Ready now"], ["awaiting", "Awaiting data"]] },
    ];
    groups.forEach((g, idx) => {
      if (idx) bar.appendChild(el("span", { class: "sr-only", text: "and" }));
      g.options.forEach(([value, label]) => {
        const pressed = state[g.kind] === value;
        bar.appendChild(el("button", {
          type: "button",
          class: "chip-btn",
          "data-kind": g.kind,
          "data-value": value,
          "aria-pressed": pressed ? "true" : "false",
          text: label,
          onclick: () => setFilter(g.kind, value),
        }));
      });
    });
  }

  function yesNo(v) {
    const td = el("td", { class: v ? "yes" : "no", text: v ? "Yes" : "No" });
    return td;
  }

  function barChart(rows, max) {
    const wrap = el("div");
    rows.forEach(([label, n, muted]) => {
      const pct = max ? Math.max(2, Math.round((n / max) * 100)) : 0;
      wrap.appendChild(el("div", { class: "bar-row" }, [
        el("div", { text: String(label) + (String(label).match(/^\d+$/) ? " days" : "") }),
        el("div", { class: "bar-track" }, [
          el("div", { class: "bar-fill" + (muted ? " muted" : ""), style: "width:" + pct + "%" }),
        ]),
        el("div", { text: String(n) }),
      ]));
    });
    return wrap;
  }

  function renderDemos(stats) {
    const root = document.getElementById("demoRoot");
    root.innerHTML = "";
    const meta = stats.sample_meta || {};
    root.appendChild(el("p", { class: "tiny", text:
      "Public sample snapshot: " + (meta.snapshot_date_america_chicago || "n/a") +
      ". " + (stats.current_rule_count || 0) + " current rules across " +
      ((meta.fund_families_in_sample || []).join(", ") || "the sample families") +
      ". " + (meta.coverage_note || "")
    }));

    // 1. Appendix I
    const s1 = el("div", { class: "guide-block" }, [
      el("h3", { text: "1. Notice 21-07 Appendix I coverage (S001)" }),
      el("p", { text: "Does each family in the sample currently show the main Appendix I discount types? Householding is detected from public prospectus phrasing, not from a separate category field." }),
    ]);
    const t1 = el("table", { class: "matrix" });
    t1.appendChild(el("thead", {}, [el("tr", {}, ["Family", "Breakpoints", "Rights of accumulation", "Letter of intent", "Householding language", "Named intermediaries"].map((h) => el("th", { text: h })))]));
    const tb1 = el("tbody");
    (stats.appendix_i_coverage || []).forEach((row) => {
      tb1.appendChild(el("tr", {}, [
        el("td", { text: row.fund_family }),
        yesNo(row.has_breakpoint),
        yesNo(row.has_roa),
        yesNo(row.has_loi),
        yesNo(row.household_rows > 0),
        el("td", { text: String(row.named_intermediaries) }),
      ]));
    });
    t1.appendChild(tb1);
    s1.appendChild(t1);
    s1.appendChild(el("p", { class: "tiny", text: "Source: FINRA Regulatory Notice 21-07, Appendix I. This is a coverage checklist, not a finding that a family is missing a legally required type." }));
    root.appendChild(s1);

    // 2. NTM 02-85
    const s2 = el("div", { class: "guide-block" }, [
      el("h3", { text: "2. Notice to Members 02-85 vigilance checklist (S029)" }),
      el("p", { text: "A family-level yes/no list of whether letters of intent, rights of accumulation, reinstatement, and named intermediaries appear in the current sample, as a public-prospectus half of the 02-85 review." }),
    ]);
    const t2 = el("table", { class: "matrix" });
    t2.appendChild(el("thead", {}, [el("tr", {}, ["Family", "Letter of intent", "Rights of accumulation", "Reinstatement", "Named intermediaries", "Current rules"].map((h) => el("th", { text: h })))]));
    const tb2 = el("tbody");
    (stats.ntm_0285_checklist || []).forEach((row) => {
      tb2.appendChild(el("tr", {}, [
        el("td", { text: row.fund_family }),
        yesNo(row.loa),
        yesNo(row.roa),
        yesNo(row.reinstatement),
        el("td", { class: row.named_intermediaries ? "yes" : "no", text: row.named_intermediaries ? "Yes (" + row.named_intermediary_count + ")" : "No" }),
        el("td", { text: String(row.current_rules) }),
      ]));
    });
    t2.appendChild(tb2);
    s2.appendChild(t2);
    s2.appendChild(el("p", { class: "tiny", text: "Source: Notice to Members 02-85. In this sample, all three families currently show all four checklist items." }));
    root.appendChild(s2);

    // 3. RoR histogram
    const ror = stats.ror_histogram || {};
    const windows = Object.entries(ror.windows || {});
    const maxW = windows.reduce((m, [, n]) => Math.max(m, n), 0);
    const s3 = el("div", { class: "guide-block" }, [
      el("h3", { text: "3. Rights of Reinstatement window histogram (S002)" }),
      el("p", { text: "FINRA found firms hard-coding a single reinstatement period while prospectuses vary. In this public sample, " + (ror.current_reinstatement_rows || 0) + " current rules mention reinstatement. Parsed windows:" }),
    ]);
    s3.appendChild(barChart(windows.map(([k, n]) => [k, n, k === "unparsed"]), maxW));
    s3.appendChild(el("p", { class: "tiny", text: ror.note || "" }));
    s3.appendChild(el("p", { class: "tiny", text: "Sources: FINRA Notice 21-07 and the Rights of Reinstatement targeted exam letter. Many sample rows mention reinstatement without a clear day count." }));
    root.appendChild(s3);

    // 4. LOI 13-month
    const loi = stats.loi_13_month || {};
    const s4 = el("div", { class: "guide-block" }, [
      el("h3", { text: "4. Letter-of-intent 13-month confirmer (S041)" }),
      el("div", { class: "demo-grid" }, [
        el("div", { class: "demo-stat" }, [
          el("div", { class: "k", text: "Current LOI rules in the sample" }),
          el("div", { class: "v", text: String(loi.current_loi_rows || 0) }),
        ]),
        el("div", { class: "demo-stat" }, [
          el("div", { class: "k", text: "Cite a 13-month term" }),
          el("div", { class: "v", text: String(loi.cite_13_month || 0) }),
        ]),
        el("div", { class: "demo-stat" }, [
          el("div", { class: "k", text: "Do not cite 13 months" }),
          el("div", { class: "v", text: String(loi.do_not_cite_13_month || 0) }),
          el("div", { class: "s", text: "These need a reviewer to read the official filing, not a default 13-month clock." }),
        ]),
      ]),
    ]);
    if ((loi.nonstandard_examples || []).length) {
      const ul = el("ul", { class: "example-list" });
      loi.nonstandard_examples.forEach((ex) => {
        ul.appendChild(el("li", {}, [
          el("span", { text: (ex.fund_family || "") + " · " + (ex.form_type || "") + " " + (ex.filing_date || "") + " · " }),
          el("code", { text: ex.accession || "" }),
          el("span", { text: ex.tickers && ex.tickers.length ? " · " + ex.tickers.join(", ") : "" }),
        ]));
      });
      s4.appendChild(el("p", { class: "tiny", text: "Examples of current letter-of-intent rules in the sample that do not mention a 13-month term (public filing identifiers only):" }));
      s4.appendChild(ul);
    }
    s4.appendChild(el("p", { class: "tiny", text: "Why it matters: Breakpoints FAQ #4 (usually a 13-month commitment). The approved priorities write-up had no direct source URL for this idea." }));
    root.appendChild(s4);

    // 5. Intermediary density
    const app = stats.intermediary_appendix || {};
    const hist = Object.entries(app.length_histogram || {}).map(([k, n]) => [k + " names", n, false]);
    const maxA = hist.reduce((m, [, n]) => Math.max(m, n), 0);
    const s5 = el("div", { class: "guide-block" }, [
      el("h3", { text: "5. Intermediary Appendix A density (S004, S063)" }),
      el("p", { text: "IM Guidance 2016-06 says intermediary-specific sales-load variations must identify each intermediary. " + (app.accessions_with_named_intermediary || 0) + " filings in the current sample name at least one intermediary. How many names appear on those filings:" }),
    ]);
    s5.appendChild(barChart(hist, maxA));
    if ((app.top_appendices || []).length) {
      const ul = el("ul", { class: "example-list" });
      app.top_appendices.forEach((ex) => {
        ul.appendChild(el("li", {}, [
          el("span", { text: (ex.fund_family || "") + " · " + (ex.form_type || "") + " " + (ex.filing_date || "") + " · " }),
          el("code", { text: ex.accession || "" }),
          el("span", { text: " · " + ex.n_intermediaries + " named intermediaries" }),
        ]));
      });
      s5.appendChild(el("p", { class: "tiny", text: "Densest current filings in the sample (public Accession Numbers):" }));
      s5.appendChild(ul);
    }
    s5.appendChild(el("p", { class: "tiny", text: "Source: IM Guidance Update 2016-06. Named-intermediary values can include parse noise and should be reviewed before operations use them." }));
    root.appendChild(s5);

    // supporting phrase counts
    const phrases = stats.householding_phrase_counts || {};
    const s6 = el("div", { class: "guide-block" }, [
      el("h3", { text: "Supporting illustration: householding and related-account phrases (S016, S040)" }),
      el("p", { text: "Counts of current sample rules whose public text mentions common Item 7(a) / FAQ #2 aggregation phrases. This is a phrase bank seed, not customer data." }),
    ]);
    const t6 = el("table", { class: "matrix" });
    t6.appendChild(el("thead", {}, [el("tr", {}, [el("th", { text: "Phrase" }), el("th", { text: "Current sample rules" })])]));
    const tb6 = el("tbody");
    Object.entries(phrases).forEach(([k, n]) => {
      tb6.appendChild(el("tr", {}, [el("td", { text: k }), el("td", { text: String(n) })]));
    });
    t6.appendChild(tb6);
    s6.appendChild(t6);
    root.appendChild(s6);
  }

  Promise.all([
    fetch("priorities_ideas.json").then((r) => { if (!r.ok) throw new Error("ideas " + r.status); return r.json(); }),
    fetch("priorities_demo_stats.json").then((r) => { if (!r.ok) throw new Error("stats " + r.status); return r.json(); }),
  ]).then(([ideas, stats]) => {
    state.groups = ideas.groups || [];
    state.stats = stats;
    renderFilters();
    renderList();
    renderDemos(stats);
  }).catch((err) => {
    const counts = document.getElementById("priorityCounts");
    const demo = document.getElementById("demoRoot");
    if (counts) counts.textContent = "Could not load the priorities list. Serve this folder over HTTP (not as a file:// page).";
    if (demo) {
      demo.innerHTML = "";
      demo.appendChild(el("p", { class: "notice error", text: "Could not load sample illustrations: " + err.message }));
    }
  });
})();
