(async function () {
  const el = document.getElementById("content");
  let tr, latest;
  try {
    [tr, latest] = await Promise.all([getJSON("data/track_record.json"), getJSON("data/latest.json")]);
  } catch (e) {
    showError(el, e);
    return;
  }
  showDataNotes(latest);
  const names = { "1m": "1 month", "3m": "3 months", "6m": "6 months" };
  const horizons = Object.keys(tr.horizons);

  if (!tr.tracking_since) {
    el.innerHTML = `<div class="callout">Tracking hasn't started yet. The first daily snapshot is saved the first time
      the scoring job runs on real data.</div>`;
    return;
  }

  const firstResult = new Date(tr.tracking_since + "T12:00:00");
  firstResult.setDate(firstResult.getDate() + 31);
  const anyDone = horizons.some(h => tr.summary[h]);

  let html = `<p class="muted">Tracking since <strong>${fmt.date(tr.tracking_since)}</strong> ·
    ${tr.cohorts.length} daily snapshot${tr.cohorts.length === 1 ? "" : "s"} saved.</p>`;

  if (!anyDone) {
    html += `<div class="callout">Too early to judge. The first 1-month results will appear around
      <strong>${firstResult.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</strong>.
      Until then, there is no evidence either way. Be wary of any site that claims results without a record like this.</div>`;
  } else {
    html += `<div class="stats">` + horizons.map(h => {
      const s = tr.summary[h];
      if (!s) return `<div class="stat"><div class="k">After ${names[h]}</div><div class="v muted">Not yet</div>
        <div class="k">needs ${tr.horizons[h]} trading days of history</div></div>`;
      return `<div class="stat"><div class="k">After ${names[h]} (${s.cohorts} days measured)</div>
        <div class="v ${signClass(s.avg_excess)}">${fmt.signed(s.avg_excess)}</div>
        <div class="k">average difference vs S&amp;P 500<br>
          Group ${fmt.signed(s.avg_group)} · S&amp;P ${fmt.signed(s.avg_spy)}<br>
          Did better on ${fmt.pct(s.pct_beat, 0)} of days<br>
          Worst: <span class="neg">${fmt.signed(s.worst_excess)}</span> · Best: <span class="${signClass(s.best_excess)}">${fmt.signed(s.best_excess)}</span></div></div>`;
    }).join("") + `</div>`;

    const done1 = tr.cohorts.filter(c => c["1m"]).slice().reverse();
    if (done1.length >= 2) {
      html += `<h2>1-month difference vs S&amp;P 500, by snapshot day</h2>
        <div class="chart-box"><div class="legend">
          <span><i style="background:var(--s1)"></i>Group did better</span>
          <span><i style="background:var(--bad)"></i>Group did worse</span></div>
        <div style="position:relative;height:260px"><canvas id="excess" role="img"
          aria-label="Bar chart of the 1-month difference between the group and the S&P 500 for each day"></canvas></div></div>`;
    }
  }

  const cell = r => r
    ? `<td class="num">${fmt.signed(r.group)}</td><td class="num">${fmt.signed(r.spy)}</td>
       <td class="num ${signClass(r.excess)}"><strong>${fmt.signed(r.excess)}</strong></td>`
    : `<td class="num muted" colspan="3">not yet</td>`;
  html += `<h2>Every snapshot</h2><div class="table-wrap"><table>
    <thead><tr><th rowspan="2">Date</th><th rowspan="2" class="num">“Looks strong”</th>
      ${horizons.map(h => `<th colspan="3" class="num">${names[h]} later</th>`).join("")}</tr>
      <tr>${horizons.map(() => `<th class="num">Group</th><th class="num">S&amp;P</th><th class="num">Diff.</th>`).join("")}</tr></thead>
    <tbody>${tr.cohorts.map(c => `<tr><td>${fmt.date(c.date)}</td>
      <td class="num" title="${esc(c.tickers.join(", "))}">${c.count}</td>${horizons.map(h => cell(c[h])).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
  el.innerHTML = html;

  const canvas = document.getElementById("excess");
  if (canvas) {
    chartTheme();
    const done1 = tr.cohorts.filter(c => c["1m"]).slice().reverse();
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: done1.map(c => c.date),
        datasets: [{ data: done1.map(c => c["1m"].excess * 100),
          backgroundColor: done1.map(c => (c["1m"].excess >= 0 ? cssVar("--s1") : cssVar("--bad"))),
          borderRadius: 4, borderSkipped: "start" }],
      },
      options: {
        maintainAspectRatio: false,
        scales: { y: { ticks: { callback: v => v + "%" } }, x: { ticks: { maxTicksLimit: 8, maxRotation: 0 }, grid: { display: false } } },
        plugins: { tooltip: { callbacks: { label: ctx => `Difference: ${ctx.parsed.y >= 0 ? "+" : ""}${ctx.parsed.y.toFixed(1)}%` } } },
      },
    });
  }
})();
