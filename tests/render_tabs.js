"use strict";
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.resolve(__dirname, "..");

const TABS = [
  { name: "fees", html: "fees.html", script: "fees.js", selector: "#fees .fund-card" },
  { name: "etf", html: "etf.html", script: "etf.js", selector: "#etf .fund-card" },
  { name: "names", html: "index.html", script: "names.js", selector: "#names tbody tr, #names .name-row, #names article, #names li, #names .card" },
  { name: "rules", html: "rules.html", script: "pilot.js", selector: "#results article, #results .rule-card, #results .card, #results li, #results section" },
  { name: "priorities", html: "priorities.html", script: "priorities.js", selector: "#priorityList article, #priorityList .card, #priorityList li, #priorityList .idea" },
  { name: "family-contacts", html: "family-contacts.html", script: "family-contacts.js", selector: "#family-contacts article, #family-contacts .card, #family-contacts section, #family-contacts li" },
  { name: "coverage", html: "coverage.html", script: "coverage.js", selector: "#coverage table, #coverage article, #coverage .card, #coverage section, #coverage tbody tr" },
];

function localFetch(url) {
  const raw = String(url);
  const clean = raw.split("?")[0].replace(/^https?:\/\/[^/]+\//, "");
  const file = path.join(ROOT, path.basename(clean) === clean || clean.startsWith("/")
    ? path.basename(clean)
    : clean);
  const resolved = path.join(ROOT, path.basename(clean));
  if (!fs.existsSync(resolved)) {
    return Promise.resolve({
      ok: false,
      status: 404,
      json: async () => { throw new Error("HTTP 404 " + raw); },
      text: async () => "",
    });
  }
  const text = fs.readFileSync(resolved, "utf8");
  return Promise.resolve({
    ok: true,
    status: 200,
    json: async () => JSON.parse(text),
    text: async () => text,
  });
}

function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function runTab(tab) {
  const errors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (err) => errors.push(err));
  virtualConsole.on("error", (err) => errors.push(err));
  const html = fs.readFileSync(path.join(ROOT, tab.html), "utf8");
  const dom = new JSDOM(html, {
    url: "https://pilot.test/" + tab.html,
    runScripts: "outside-only",
    pretendToBeVisual: true,
    virtualConsole,
  });
  const { window } = dom;
  window.fetch = localFetch;
  window.addEventListener("error", (ev) => errors.push(ev.error || ev.message));
  window.addEventListener("unhandledrejection", (ev) => errors.push(ev.reason));
  const script = fs.readFileSync(path.join(ROOT, tab.script), "utf8");
  window.eval(script);
  if (window.document.readyState === "loading") {
    window.document.dispatchEvent(new window.Event("DOMContentLoaded"));
  }
  // Allow fetch()+render() promise chains (and their .catch) to settle.
  await wait(200);
  const bodyText = window.document.body.textContent || "";
  const status = (window.document.getElementById("status") ||
    window.document.getElementById("priorityCounts") ||
    { textContent: "" }).textContent || "";
  if (/Could not load/i.test(status) || /Could not load/i.test(bodyText) && window.document.querySelectorAll(tab.selector).length === 0) {
    errors.push(new Error(tab.name + " showed a load error: " + status));
  }
  const hits = window.document.querySelectorAll(tab.selector).length;
  if (hits < 1) {
    errors.push(new Error(tab.name + " rendered 0 nodes for " + tab.selector + "; status=" + JSON.stringify(status)));
  }
  if (tab.name === "etf") {
    const totals = window.document.querySelectorAll(".fee-total");
    if (totals.length !== 296) {
      errors.push(new Error("etf expected 296 fee totals, got " + totals.length));
    }
    let waiverExample = false;
    window.document.querySelectorAll("#etf .etf-classes tbody tr").forEach(function (tr) {
      if (tr.querySelector(".fee-total") && tr.querySelector(".fee-net") && tr.querySelector(".fee-waiver")) {
        waiverExample = true;
      }
    });
    if (!waiverExample) errors.push(new Error("etf missing a waiver example with Total, Net, and waiver amount"));
    const reasons = window.document.querySelectorAll(".fee-reason");
    if (reasons.length !== 6) {
      errors.push(new Error("etf expected 6 blank reasons, got " + reasons.length));
    }
    const reasonText = Array.prototype.map.call(reasons, function (n) { return (n.textContent || "").trim(); });
    ["not yet effective, no final prospectus", "older class, no usable fee table in filings"].forEach(function (r) {
      if (reasonText.indexOf(r) < 0) errors.push(new Error("etf missing blank reason: " + r));
    });
    window.document.querySelectorAll("td.blank").forEach(function (td) {
      if (/\d+(?:\.\d+)?\s*%/.test(td.textContent || "")) {
        errors.push(new Error("etf blank reason cell contains a fee number"));
      }
    });
    const disclosure = window.document.body.textContent || "";
    if (!/Read the full filing/i.test(disclosure)) {
      errors.push(new Error("etf missing read-the-full-filing disclosure"));
    }
    const filter = window.document.getElementById("etf-status");
    if (!filter || filter.value !== "active") {
      errors.push(new Error("etf Active filter is not the default"));
    }
    const shown = Array.prototype.filter.call(window.document.querySelectorAll("#etf .fund-card"), function (c) {
      return !c.hidden;
    });
    const closedShown = shown.filter(function (c) { return c.dataset.status === "closed"; });
    if (closedShown.length !== 0) {
      errors.push(new Error("etf default view shows closed series"));
    }
    if (shown.length !== 93) {
      errors.push(new Error("etf default Active view expected 93 series, got " + shown.length));
    }
    const totalLines = window.document.querySelectorAll(".fee-total-line");
    if (totalLines.length !== 296) {
      errors.push(new Error("etf expected 296 exact total lines, got " + totalLines.length));
    }
    let waiverLines = false;
    window.document.querySelectorAll("#etf .etf-classes tbody tr").forEach(function (tr) {
      if (tr.querySelector(".fee-waiver") && tr.querySelector(".fee-total-line") && tr.querySelector(".fee-net-line")) {
        waiverLines = true;
      }
    });
    if (!waiverLines) errors.push(new Error("etf waiver row missing both exact filing lines"));
    const notes = window.document.querySelectorAll(".fee-note");
    const noteText = Array.prototype.map.call(notes, function (n) { return (n.textContent || "").trim(); });
    const noWaiver = noteText.filter(function (s) { return s === "no waiver in filing"; }).length;
    if (noWaiver !== 233) {
      errors.push(new Error("etf expected 233 'no waiver in filing' notes, got " + noWaiver));
    }
    function rowByTicker(ticker) {
      return Array.prototype.find.call(window.document.querySelectorAll("#etf .etf-classes tbody tr"), function (tr) {
        const td = tr.querySelectorAll("td")[1];
        const t = ((td && td.textContent) || "").trim();
        return t === ticker || t.indexOf(ticker + " ") === 0;
      });
    }
    function assertFeeRow(ticker, total, net, wantsWaiver) {
      const tr = rowByTicker(ticker);
      if (!tr) { errors.push(new Error("etf missing row for " + ticker)); return; }
      const tot = tr.querySelector(".fee-total");
      const n = tr.querySelector(".fee-net");
      const w = tr.querySelector(".fee-waiver");
      const line = tr.querySelector(".fee-total-line");
      const a = tr.querySelector("a.fee-filing");
      if (!tot || (tot.textContent || "").trim() !== total) errors.push(new Error(ticker + " total: " + JSON.stringify(tot && tot.textContent)));
      if (!n || (n.textContent || "").trim() !== net) errors.push(new Error(ticker + " net: " + JSON.stringify(n && n.textContent)));
      if (wantsWaiver) {
        if (!w) errors.push(new Error(ticker + " missing waiver amount"));
      } else if (w) {
        errors.push(new Error(ticker + " unexpected waiver amount"));
      }
      if (!line || !(line.textContent || "").trim()) errors.push(new Error(ticker + " missing exact filing line"));
      const href = a && a.getAttribute("href") || "";
      if (href.indexOf("#:~:text=") < 0) errors.push(new Error(ticker + " missing class-specific highlight link"));
    }
    assertFeeRow("FLTMX", "0.39%", "0.37%", true);
    assertFeeRow("FSHBX", "0.30%", "0.30%", false);
    assertFeeRow("FRIFX", "0.65%", "0.65%", false);
    assertFeeRow("NUDG", "0.75%", "0.61%", true);
    const frifx = rowByTicker("FRIFX");
    const frifxHref = frifx && frifx.querySelector("a.fee-filing") && frifx.querySelector("a.fee-filing").getAttribute("href") || "";
    if (frifxHref.indexOf("000075451026000241") < 0) {
      errors.push(new Error("FRIFX href is not the stored fallback filing: " + JSON.stringify(frifxHref)));
    }
    let blankOk = 0;
    window.document.querySelectorAll("#etf .fund-card").forEach(function (card) {
      const q = card.dataset.q || "";
      if (q.indexOf("s000006325") < 0 && q.indexOf("s000006335") < 0) return;
      card.querySelectorAll(".etf-classes tbody tr").forEach(function (tr) {
        if (!tr.querySelector(".etf-tag")) return;
        const reason = tr.querySelector(".fee-reason");
        const txt = (reason && reason.textContent || "").trim();
        if (txt !== "not yet effective, no final prospectus") {
          errors.push(new Error("TCW ETF class missing not-yet-effective reason: " + JSON.stringify(txt)));
          return;
        }
        if (tr.querySelector(".fee-total") || tr.querySelector("a.fee-filing") || /\d+(?:\.\d+)?\s*%/.test(tr.textContent || "")) {
          errors.push(new Error("TCW ETF blank row has a fee number or link"));
          return;
        }
        blankOk += 1;
      });
    });
    if (blankOk !== 2) errors.push(new Error("etf expected 2 TCW not-yet-effective blank ETF rows, got " + blankOk));
    const metaText = (window.document.getElementById("etf-meta") && window.document.getElementById("etf-meta").textContent) || "";
    if (metaText.indexOf("295 of 297") < 0) {
      errors.push(new Error("etf meta missing active fee counts: " + JSON.stringify(metaText.slice(0, 400))));
    }
    // Sisters in one fee table may share a highlight; different exact lines must not.
    const fragLines = {};
    window.document.querySelectorAll("#etf a.fee-filing").forEach(function (a) {
      const href = a.getAttribute("href") || "";
      const m = href.match(/(\d{18})\/[^#]+(?:#:~:text=.+)$/);
      if (!m) return;
      const key = m[1] + " " + href.split("#")[1];
      const lineEl = a.closest("tr") && a.closest("tr").querySelector(".fee-total-line");
      const line = (lineEl && lineEl.textContent || "").trim();
      (fragLines[key] || (fragLines[key] = [])).push(line);
    });
    Object.keys(fragLines).forEach(function (key) {
      if (new Set(fragLines[key]).size !== 1) {
        errors.push(new Error("etf shared fragment has different filing lines: " + key));
      }
    });
    let fimuHref = null;
    const fimuRow = rowByTicker("FIMU");
    if (fimuRow && fimuRow.querySelector("a.fee-filing")) {
      fimuHref = fimuRow.querySelector("a.fee-filing").getAttribute("href") || "";
    }
    if (!fimuHref || fimuHref.indexOf("filing12344.htm") < 0 || fimuHref.indexOf("index.htm") >= 0) {
      errors.push(new Error("etf FIMU href is not the stored document: " + JSON.stringify(fimuHref)));
    }
    if (!fimuHref || fimuHref.indexOf("#:~:text=") < 0) {
      errors.push(new Error("etf FIMU href missing text fragment"));
    }
  }
  if (tab.name === "fees") {
    window.document.querySelectorAll("#fees .ticker").forEach(function (n) {
      var text = (n.textContent || "").trim();
      if (text === "no ticker") return;
      var label = n.querySelector(".ticker-source");
      var src = label && (label.textContent || "").trim();
      if (!src || (src !== "DB" && src !== "SEC")) {
        errors.push(new Error("fees ticker lacks source label: " + JSON.stringify(text)));
      }
    });
  }
  if (errors.length) {
    const msg = errors.map((e) => (e && e.stack) || String(e)).join("\n");
    throw new Error(tab.name + " failed:\n" + msg);
  }
  return hits;
}

(async () => {
  let failed = 0;
  for (const tab of TABS) {
    try {
      const n = await runTab(tab);
      console.log("PASS", tab.name, n, "nodes");
    } catch (err) {
      failed += 1;
      console.error("FAIL", tab.name, err && err.message ? err.message : err);
    }
  }
  if (failed) process.exit(1);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
