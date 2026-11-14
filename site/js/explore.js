(async function () {
  const rowsEl = document.getElementById("rows");
  let latest;
  try {
    latest = await getJSON("data/latest.json");
  } catch (e) {
    showError(rowsEl.parentElement.parentElement, e);
    return;
  }
  showDataNotes(latest);

  const cols = [
    { key: "ticker", label: "Ticker", get: s => s.ticker },
    { key: "name", label: "Name", get: s => s.name },
    { key: "sector", label: "Sector", get: s => s.sector },
    { key: "score", label: "Score", get: s => s.score, num: true },
    { key: "label", label: "Label", get: s => ({ "Looks strong": 2, "Mixed": 1, "Looks weak": 0 })[s.label] },
    { key: "trend", label: "Trend", get: s => s.parts.trend, num: true },
    { key: "momentum", label: "Momentum", get: s => s.parts.momentum, num: true },
    { key: "steadiness", label: "Steadiness", get: s => s.parts.steadiness, num: true },
    { key: "volatility", label: "Volatility", get: s => s.volatility, num: true },
    { key: "ret_6m", label: "6-mo return", get: s => s.ret_6m, num: true },
  ];
  let sortKey = "score", dir = -1;

  const sectors = [...new Set(latest.stocks.map(s => s.sector))].sort();
  document.getElementById("sector").insertAdjacentHTML("beforeend",
    sectors.map(x => `<option>${esc(x)}</option>`).join(""));

  function head() {
    document.getElementById("head").innerHTML = cols.map(c => {
      const active = c.key === sortKey;
      const aria = active ? (dir === 1 ? "ascending" : "descending") : "none";
      return `<th class="${c.num ? "num" : ""}" aria-sort="${aria}"><button data-k="${c.key}">${c.label}${active ? (dir === 1 ? " ↑" : " ↓") : ""}</button></th>`;
    }).join("");
    document.querySelectorAll("#head button").forEach(b => b.addEventListener("click", () => {
      const k = b.dataset.k;
      if (k === sortKey) dir = -dir; else { sortKey = k; dir = cols.find(c => c.key === k).num || k === "label" ? -1 : 1; }
      render();
    }));
  }

  function render() {
    const q = document.getElementById("q").value.trim().toLowerCase();
    const lab = document.getElementById("label").value;
    const sec = document.getElementById("sector").value;
    const col = cols.find(c => c.key === sortKey);
    const list = latest.stocks
      .filter(s => (!q || s.ticker.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
        && (!lab || s.label === lab) && (!sec || s.sector === sec))
      .sort((a, b) => {
        const x = col.get(a), y = col.get(b);
        return (typeof x === "string" ? x.localeCompare(y) : (x ?? -1) - (y ?? -1)) * dir;
      });
    head();
    document.getElementById("count").textContent = `${list.length} of ${latest.stocks.length} shown`;
    const n = v => (v == null ? "n/a" : Math.round(v));
    rowsEl.innerHTML = list.map(s => `<tr>
        <td><a href="stock.html?t=${encodeURIComponent(s.ticker)}"><strong>${esc(s.ticker)}</strong></a></td>
        <td>${esc(s.name)}</td><td>${esc(s.sector)}</td>
        <td class="num"><strong>${s.score}</strong></td><td>${badge(s.label)}</td>
        <td class="num">${n(s.parts.trend)}</td><td class="num">${n(s.parts.momentum)}</td>
        <td class="num">${n(s.parts.steadiness)}</td>
        <td class="num">${fmt.pct(s.volatility, 0)}</td>
        <td class="num ${signClass(s.ret_6m)}">${fmt.signed(s.ret_6m)}</td>
      </tr>`).join("") || `<tr><td colspan="${cols.length}">No matches.</td></tr>`;
  }

  ["q", "label", "sector"].forEach(id => document.getElementById(id).addEventListener("input", render));
  render();
})();
