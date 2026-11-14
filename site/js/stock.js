(async function () {
  const main = document.getElementById("main");
  const ticker = (new URLSearchParams(location.search).get("t") || "SPY").toUpperCase();
  let s, latest;
  try {
    [s, latest] = await Promise.all([getJSON(`data/stocks/${encodeURIComponent(ticker)}.json`), getJSON("data/latest.json")]);
  } catch (e) {
    main.innerHTML = `<h1>${esc(ticker)}</h1>`;
    main.insertAdjacentHTML("beforeend", `<div class="callout warn">We don't score “${esc(ticker)}”. Only large,
      established companies and major index funds are included. <a href="explore.html">See the full list</a>.</div>`);
    return;
  }
  showDataNotes(latest);
  document.title = `${s.ticker} (${s.name}) · Beginner Stock Scorecard`;
  const d = s.details, w = s.weights_used;
  const t = d.trend.metrics, m = d.momentum.metrics, st = d.steadiness.metrics;
  const above = x => (x >= 0 ? "above" : "below");
  const medVol = latest.median_volatility;

  const parts = [
    {
      key: "trend", title: "Trend",
      what: `The price is <strong>${fmt.pct(Math.abs(t.vs50))} ${above(t.vs50)}</strong> its 50-day average
        (${fmt.money(t.sma50)}) and <strong>${fmt.pct(Math.abs(t.vs200))} ${above(t.vs200)}</strong> its 200-day average
        (${fmt.money(t.sma200)}). The 50-day average is ${fmt.pct(Math.abs(t.sma50_vs_200))} ${above(t.sma50_vs_200)} the 200-day.`,
      meaning: `A moving average is the average closing price over the last 50 or 200 trading days. It smooths out
        day-to-day noise. Trading above these averages means the price has been rising lately; below means falling.`,
    },
    {
      key: "momentum", title: "Momentum",
      what: `Return over 3 months: <strong>${fmt.signed(m.ret_3m)}</strong> (S&amp;P 500: ${fmt.signed(m.bench_3m)}).
        6 months: <strong>${fmt.signed(m.ret_6m)}</strong> (S&amp;P 500: ${fmt.signed(m.bench_6m)}).
        12 months: <strong>${fmt.signed(m.ret_12m)}</strong> (S&amp;P 500: ${fmt.signed(m.bench_12m)}).`,
      meaning: `Momentum compares this stock with the overall market. Beating the S&amp;P 500 scores above 50, trailing
        it scores below 50. Past winners sometimes keep going for a while, but often they don't.`,
    },
    {
      key: "steadiness", title: "Steadiness",
      what: `Its daily ups and downs add up to a volatility of <strong>${fmt.pct(st.volatility)}</strong> a year
        (the typical stock here: ${fmt.pct(medVol)}). Its biggest drop from a high in the past year was
        <strong>${fmt.pct(st.max_drawdown)}</strong>.`,
      meaning: `Volatility measures how much the price jumps around. A drawdown is how far it fell from its highest point.
        Calmer stocks score higher here. This is the “likely to stay even” part, but calm periods can end suddenly.`,
    },
    {
      key: "smart", title: "Smart money",
      what: s.parts.smart == null
        ? (s.type === "etf" ? "Not used for index funds." : `Not used today. ${esc(latest.smart_money.note)}`)
        : `Over the last 90 days, insiders and members of Congress reported a net of
           <strong>${d.smart.metrics.net_trades >= 0 ? "+" : ""}${d.smart.metrics.net_trades}</strong> purchases minus sales.`,
      meaning: `Company insiders (executives and directors) and members of Congress must publicly report their trades.
        More purchases than sales scores above 50. They can be wrong too, and reports arrive with a delay.`,
    },
  ];

  main.innerHTML = `
    <p class="small"><a href="explore.html">← All stocks</a></p>
    <div class="card-top">
      <div>
        <h1 style="margin-bottom:4px">${esc(s.name)} <span class="muted">(${esc(s.ticker)})</span></h1>
        <div class="pill-row">${badge(s.label)} <span class="muted small">${esc(s.sector)} · last close ${fmt.money(s.price)}</span></div>
      </div>
      <div class="score-num" style="font-size:2.8rem">${s.score}<small>/100</small></div>
    </div>
    <p class="lede" style="margin-top:14px">${esc(s.reason)}</p>
    <p class="muted small" data-asof></p>

    <h2>Price and moving averages (past year)</h2>
    <div class="chart-box">
      <div class="legend"><span><i style="background:var(--s1)"></i>Closing price</span>
        <span><i style="background:var(--s2)"></i>50-day average</span>
        <span><i style="background:var(--s3)"></i>200-day average</span></div>
      <div style="position:relative;height:320px"><canvas id="price" aria-label="Price chart with 50 and 200 day averages" role="img"></canvas></div>
    </div>

    <div class="two-col">
      <section>
        <h2>Score breakdown</h2>
        ${parts.map(p => {
          const v = s.parts[p.key];
          const weight = w[p.key] != null ? `${Math.round(w[p.key] * 1000) / 10}% of the score` : "not counted";
          return `<div class="part">
            <div class="part-head"><span>${p.title} <span class="muted small">(${weight})</span></span>
              <span>${v == null ? "n/a" : Math.round(v) + "/100"}</span></div>
            <div class="bar" role="img" aria-label="${p.title} ${v == null ? "not available" : Math.round(v) + " out of 100"}">
              <span style="width:${v == null ? 0 : v}%"></span></div>
            <p>${p.what}</p>
            <p class="muted small">${p.meaning}</p>
          </div>`;
        }).join("")}
        <p class="small muted">Total = weighted average of the parts above. <a href="how-it-works.html">Full method</a>.</p>
      </section>
      <section>
        <h2>Score over the last 30 trading days</h2>
        <div class="chart-box">
          <div style="position:relative;height:260px"><canvas id="history" aria-label="Score history chart" role="img"></canvas></div>
        </div>
        <p class="small muted">Recalculated from past prices for each day, using the same method.
          Dashed lines mark the 70 (“Looks strong”) and 40 (“Looks weak” below this) thresholds.</p>
      </section>
    </div>`;
  showDataNotes({ ...latest, demo: false });

  chartTheme();
  const c = s.chart;
  new Chart(document.getElementById("price"), {
    type: "line",
    data: {
      labels: c.dates,
      datasets: [
        { label: "Closing price", data: c.close, borderColor: cssVar("--s1"), borderWidth: 2, pointRadius: 0 },
        { label: "50-day average", data: c.sma50, borderColor: cssVar("--s2"), borderWidth: 2, pointRadius: 0 },
        { label: "200-day average", data: c.sma200, borderColor: cssVar("--s3"), borderWidth: 2, pointRadius: 0 },
      ],
    },
    options: {
      maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      scales: { x: { ticks: { maxTicksLimit: 6, maxRotation: 0 }, grid: { display: false } },
                y: { ticks: { callback: v => "$" + v } } },
      plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmt.money(ctx.parsed.y)}` } } },
    },
  });

  const threshold = (y, color) => ({ type: "line", data: s.history.map(() => y), borderColor: color, borderWidth: 1,
    borderDash: [5, 4], pointRadius: 0, tooltip: { enabled: false } });
  new Chart(document.getElementById("history"), {
    type: "line",
    data: {
      labels: s.history.map(h => h.date),
      datasets: [
        { label: "Score", data: s.history.map(h => h.score), borderColor: cssVar("--s1"), borderWidth: 2,
          pointRadius: 0, pointHoverRadius: 5 },
        { ...threshold(70, cssVar("--muted")), label: "70" },
        { ...threshold(40, cssVar("--muted")), label: "40" },
      ],
    },
    options: {
      maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      scales: { y: { min: 0, max: 100, ticks: { stepSize: 20 } },
                x: { ticks: { maxTicksLimit: 5, maxRotation: 0 }, grid: { display: false } } },
      plugins: { tooltip: { filter: i => i.datasetIndex === 0,
                            callbacks: { label: ctx => `Score: ${Math.round(ctx.parsed.y)}` } } },
    },
  });
})();
