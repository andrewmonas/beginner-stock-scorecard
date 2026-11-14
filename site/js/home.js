(async function () {
  const strongEl = document.getElementById("strong");
  try {
    const latest = await getJSON("data/latest.json");
    showDataNotes(latest);
    const by = Object.fromEntries(latest.stocks.map(s => [s.ticker, s]));
    const c = latest.counts;
    document.getElementById("stats").innerHTML = [
      ["Looks strong", c["Looks strong"]], ["Mixed", c["Mixed"]], ["Looks weak", c["Looks weak"]],
      ["Tickers scored", latest.stocks.length],
    ].map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");

    const strong = latest.top_strong.map(t => by[t]);
    strongEl.innerHTML = strong.length
      ? strong.map(stockCard).join("")
      : `<p class="muted">No stock scores 70 or more today. That happens in weak markets.</p>`;
    if (strong.length && strong.length < 10) {
      strongEl.insertAdjacentHTML("afterend", `<p class="muted small">Only ${strong.length} stocks reach “Looks strong” today.</p>`);
    }
    document.getElementById("steady").innerHTML = latest.top_steady.map(t => stockCard(by[t])).join("");
  } catch (e) {
    showError(strongEl, e);
  }
})();
