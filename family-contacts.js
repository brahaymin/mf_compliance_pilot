(function () {
  "use strict";

  var ASSET_VERSION = (document.documentElement.getAttribute("data-asset-version") || "1").replace(/[^\w.-]/g, "");
  var DATA_URL = "family_contacts.json?v=" + ASSET_VERSION;
  var SEC_URL_RE = /^https:\/\/(?:www\.)?sec\.gov\//i;
  var SITE_RE = /^https:\/\/(?:www\.)?(?:fidelity\.com|401k\.com|institutional\.fidelity\.com|guggenheiminvestments\.com|naafunds\.com)(?:\/)?$/i;
  var PHONE_RE = /^1-\d{3}-\d{3}-\d{4}$/;

  var els = {
    status: document.getElementById("status"),
    results: document.getElementById("family-contacts"),
    jump: document.getElementById("family-jump"),
  };

  function text(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  function familySlug(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
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

  function safeSiteUrl(url) {
    if (!url || typeof url !== "string") return null;
    try {
      var u = new URL(url.trim());
      if (u.protocol !== "https:") return null;
      if (!SITE_RE.test(u.origin + (u.pathname === "/" ? "/" : ""))) {
        // Allow exact origin match after normalization
        var host = u.hostname.replace(/^www\./, "");
        var allowed = {
          "fidelity.com": true,
          "401k.com": true,
          "institutional.fidelity.com": true,
          "guggenheiminvestments.com": true,
          "naafunds.com": true
        };
        if (!allowed[host] && !allowed[u.hostname]) return null;
      }
      if (u.pathname && u.pathname !== "/") return u.origin;
      return u.toString();
    } catch (e) {
      return null;
    }
  }

  function telHref(value) {
    if (!PHONE_RE.test(value)) return null;
    return "tel:+" + value.replace(/-/g, "");
  }

  function setStatus(kind, message) {
    if (!els.status) return;
    els.status.className = "notice " + kind;
    els.status.textContent = message;
    els.status.hidden = !message;
  }

  function renderSource(entry) {
    var src = document.createElement("span");
    src.className = "contact-source";
    var label = (entry.form_type || "485BPOS") + " · " + (entry.filing_date || "") + " · " + (entry.accession || "");
    var href = safeSecUrl(entry.edgar_url);
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      text(a, label);
      src.appendChild(document.createTextNode("Source: "));
      src.appendChild(a);
    } else {
      text(src, "Source: " + label);
    }
    return src;
  }

  function renderValue(entry) {
    var wrap = document.createElement("div");
    wrap.className = "contact-value";
    var val = entry.value || "";
    var href = null;
    if (entry.type === "phone") href = telHref(val);
    else if (entry.type === "website") href = safeSiteUrl(val);
    else if (entry.type === "email") href = null; // only render if we ever add institutional inboxes; no mailto for now unless family domain
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      if (entry.type === "website") {
        a.rel = "noopener noreferrer";
        a.target = "_blank";
      }
      text(a, val);
      wrap.appendChild(a);
    } else {
      text(wrap, val);
    }
    wrap.appendChild(renderSource(entry));
    return wrap;
  }

  function renderFamily(card) {
    var article = document.createElement("article");
    article.className = "card family-card";
    article.id = familySlug(card.fund_family);

    var h2 = document.createElement("h2");
    h2.className = "card-title";
    text(h2, card.fund_family);
    article.appendChild(h2);

    var meta = document.createElement("p");
    meta.className = "family-meta";
    var n = 0;
    (card.groups || []).forEach(function (g) { n += (g.entries || []).length; });
    text(meta, n + " contact" + (n === 1 ? "" : "s") +
      (card.latest_current_485bpos ? " · latest current 485BPOS " + card.latest_current_485bpos : ""));
    article.appendChild(meta);

    (card.groups || []).forEach(function (group) {
      var section = document.createElement("div");
      section.className = "contact-group";
      var h3 = document.createElement("h3");
      text(h3, group.purpose);
      section.appendChild(h3);
      var ul = document.createElement("ul");
      ul.className = "contact-list";
      (group.entries || []).forEach(function (entry) {
        var li = document.createElement("li");
        var lab = document.createElement("div");
        lab.className = "contact-label";
        text(lab, entry.label || entry.type);
        li.appendChild(lab);
        li.appendChild(renderValue(entry));
        ul.appendChild(li);
      });
      section.appendChild(ul);
      article.appendChild(section);
    });
    return article;
  }

  function render(data) {
    els.results.innerHTML = "";
    els.jump.innerHTML = "";
    var families = (data && data.families) || [];
    if (!families.length) {
      setStatus("info", "No family contacts in this sample.");
      return;
    }
    families.forEach(function (card) {
      var a = document.createElement("a");
      a.href = "#" + familySlug(card.fund_family);
      text(a, card.fund_family);
      els.jump.appendChild(a);
      els.results.appendChild(renderFamily(card));
    });
    var note = (data.meta && data.meta.note) || "Contact details as published in fund prospectus filings; not legal advice.";
    var snap = data.meta && data.meta.snapshot_date_america_chicago;
    setStatus("info", note + (snap ? " Snapshot: " + snap + "." : ""));
    if (location.hash) {
      var target = document.getElementById(location.hash.slice(1));
      if (target && target.scrollIntoView) target.scrollIntoView();
    }
  }

  fetch(DATA_URL, { credentials: "same-origin" })
    .then(function (res) {
      if (!res.ok) throw new Error("Could not load family contacts (" + res.status + ")");
      return res.json();
    })
    .then(render)
    .catch(function (err) {
      setStatus("error", err.message || "Could not load family contacts.");
    });
})();
