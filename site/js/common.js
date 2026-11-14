/* Shared helpers for every page. */
const SITE_NAME = "Beginner Stock Scorecard";
const NAV = [
  ["index.html", "Home", "home"],
  ["explore.html", "All stocks", "explore"],
  ["track-record.html", "Track record", "track"],
  ["how-it-works.html", "How it works", "how"],
  ["guide.html", "Beginner guide", "guide"],
  ["disclaimer.html", "Disclaimer", "disclaimer"],
];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderChrome() {
  const page = document.body.dataset.page;
  const header = document.getElementById("site-header");
  header.className = "site-header";
  header.innerHTML = `<div class="wrap">
      <a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">S</span>${SITE_NAME}</a>
      <button class="nav-toggle" aria-expanded="false" aria-controls="nav">Menu</button>
      <nav class="nav" id="nav">${NAV.map(([href, label, key]) =>
        `<a href="${href}"${key === page ? ' class="active" aria-current="page"' : ""}>${label}</a>`).join("")}</nav>
    </div>`;
  const btn = header.querySelector(".nav-toggle");
  btn.addEventListener("click", () => {
    const nav = header.querySelector(".nav");
    btn.setAttribute("aria-expanded", nav.classList.toggle("open"));
  });
  document.getElementById("site-footer").innerHTML = `<div class="wrap">
      <p><strong>Educational information only, not financial advice.</strong> Scores are computed automatically from past
      price data and can be wrong. Nothing here is a recommendation for any person. See the <a href="disclaimer.html">full disclaimer</a>.</p>
      <p>Price data: Alpaca Markets (IEX feed). Built as a learning project. No accounts, no tracking, no payments.</p>
    </div>`;
}

async function getJSON(path) {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(`Could not load ${path} (${r.status})`);
  return r.json();
}

const fmt = {
  pct: (x, d = 1) => (x == null ? "n/a" : `${(x * 100).toFixed(d)}%`),
  signed: (x, d = 1) => (x == null ? "n/a" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(d)}%`),
  money: x => (x == null ? "n/a" : `$${Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`),
  int: x => (x == null ? "n/a" : Math.round(x).toString()),
  date: s => new Date(s + "T12:00:00").toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }),
};

function signClass(x) { return x == null ? "" : x >= 0 ? "pos" : "neg"; }

function labelClass(label) {
  return { "Looks strong": "strong", "Mixed": "mixed", "Looks weak": "weak" }[label] || "mixed";
}

function badge(label) {
  const icon = { strong: "▲", mixed: "●", weak: "▼" }[labelClass(label)];
  return `<span class="badge ${labelClass(label)}"><span aria-hidden="true">${icon}</span>${esc(label)}</span>`;
}

function sparkline(values) {
  if (!values || values.length < 2) return "";
  const w = 240, h = 44, pad = 3;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) =>
    `${(pad + (i / (values.length - 1)) * (w - 2 * pad)).toFixed(1)},${(h - pad - ((v - min) / span) * (h - 2 * pad)).toFixed(1)}`);
  const change = values[values.length - 1] / values[0] - 1;
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img"
      aria-label="Price over the last ${values.length} trading days: ${fmt.signed(change)}">
      <polyline fill="none" stroke="var(--s1)" stroke-width="2" vector-effect="non-scaling-stroke"
        stroke-linejoin="round" stroke-linecap="round" points="${pts.join(" ")}"/></svg>`;
}

function stockCard(s) {
  return `<a class="card" href="stock.html?t=${encodeURIComponent(s.ticker)}">
      <div class="card-top">
        <div><div class="ticker">${esc(s.ticker)}</div><div class="name">${esc(s.name)}</div></div>
        <div class="score-num">${s.score}<small>/100</small></div>
      </div>
      <div style="margin-top:8px">${badge(s.label)}</div>
      ${sparkline(s.spark)}
      <p class="reason">${esc(s.reason)}</p>
    </a>`;
}

function showDataNotes(latest) {
  if (latest.demo) {
    const b = document.createElement("div");
    b.className = "demo-banner";
    b.textContent = "PREVIEW WITH FAKE DEMO DATA: these are not real prices or real scores.";
    document.body.insertBefore(b, document.body.firstChild);
  }
  document.querySelectorAll("[data-asof]").forEach(el => {
    el.textContent = `Scores use closing prices from ${fmt.date(latest.asof)}. Updated automatically every weekday evening.`;
  });
}

function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function chartTheme() {
  if (!window.Chart) return;
  Chart.defaults.color = cssVar("--muted");
  Chart.defaults.borderColor = cssVar("--grid");
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.plugins.legend.display = false;   // we draw our own legend in HTML
  Chart.defaults.animation = false;
}

function showError(el, err) {
  el.innerHTML = `<div class="callout warn"><strong>Data not available yet.</strong> ${esc(err.message)}.
    The daily scoring job may not have run yet.</div>`;
}

document.addEventListener("DOMContentLoaded", renderChrome);
