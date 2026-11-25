"use strict";
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.resolve(__dirname, "..");

const TABS = [
  { name: "fees", html: "fees.html", script: "fees.js", selector: "#fees .fund-card" },
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
