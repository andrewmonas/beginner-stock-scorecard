(async function () {
  let latest;
  try {
    latest = await getJSON("data/latest.json");
  } catch (e) {
    showError(document.getElementById("weights"), e);
    return;
  }
  showDataNotes(latest);
  const M = latest.method;
  const p = x => `${Math.round(x * 1000) / 10}%`;
  const on = latest.smart_money.enabled;

  document.getElementById("labels").innerHTML =
    `${badge("Looks strong")} for ${M.labels[0][0]} or more, ${badge("Mixed")} for ${M.labels[1][0]} to ${M.labels[0][0] - 1}, and ${badge("Looks weak")} below ${M.labels[1][0]}`;

  const rows = [["trend", "Trend"], ["momentum", "Momentum"], ["steadiness", "Steadiness"], ["smart", "Smart money"]];
  const used = latest.weights_used;
  document.getElementById("weights").innerHTML = `
    <div class="table-wrap"><table>
      <thead><tr><th>Part</th><th class="num">Standard weight</th><th class="num">Weight in use today</th></tr></thead>
      <tbody>${rows.map(([k, n]) => `<tr><td>${n}</td><td class="num">${p(M.weights[k])}</td>
        <td class="num">${used[k] != null ? p(used[k]) : "off"}</td></tr>`).join("")}</tbody>
    </table></div>
    <p class="small muted">${on ? "Smart money is switched on." : "Smart money is switched off, so its 20% is shared out across the other three parts in proportion to their weights."}
    Index funds never have smart-money data, so for them the other three parts are always reweighted the same way.</p>`;

  const ta = M.trend_anchors, tw = M.trend_subweights, mp = M.momentum_periods;
  document.getElementById("parts").innerHTML = `
    <h3>Trend (${p(M.weights.trend)})</h3>
    <p>A moving average is the average closing price over the last N trading days. It shows the general direction
      without the daily noise. Three checks are scored:</p>
    <ul>
      <li>Price vs its <strong>200-day</strong> average (${p(tw.vs200)} of this part): ${p(ta.vs200[0])} below scores 0, ${p(ta.vs200[1])} above scores 100.</li>
      <li>Price vs its <strong>50-day</strong> average (${p(tw.vs50)}): ${p(ta.vs50[0])} below scores 0, ${p(ta.vs50[1])} above scores 100.</li>
      <li>The <strong>50-day vs the 200-day</strong> average (${p(tw.sma50_vs_200)}): ${p(ta.sma50_vs_200[0])} below scores 0,
        ${p(ta.sma50_vs_200[1])} above scores 100. When the 50-day is above the 200-day, the medium-term trend is up.</li>
    </ul>
    <h3>Momentum (${p(M.weights.momentum)})</h3>
    <p>Compares the stock's return over the last 3, 6 and 12 months (${mp["3m"]}, ${mp["6m"]} and ${mp["12m"]} trading days)
      with the S&amp;P 500 (SPY) over the same time. For each period, trailing the market by ${p(-M.momentum_anchors[0])}
      or more scores 0, matching it scores 50, and beating it by ${p(M.momentum_anchors[1])} or more scores 100.
      The three periods are averaged.</p>
    <h3>Steadiness (${p(M.weights.steadiness)})</h3>
    <p>The “likely to stay even” part. Two measurements, averaged:</p>
    <ul>
      <li><strong>Volatility</strong>: how much the price moves day to day over the last ${M.vol_window} trading days, scaled
        to a yearly number. ${p(M.vol_anchors[0])} or more scores 0; ${p(M.vol_anchors[1])} or less scores 100.
        A broad index fund is typically around 15%.</li>
      <li><strong>Biggest drop</strong> (maximum drawdown): the largest fall from a high point to a later low over the last
        ${M.dd_window} trading days. A ${p(-M.dd_anchors[0])} drop scores 0; no drop scores 100.</li>
    </ul>
    <h3>Smart money (${p(M.weights.smart)}, optional)</h3>
    <p>Company insiders and members of Congress must publicly report their stock trades. Over the last ${M.smart_days}
      days, we count reported purchases minus reported sales. Zero scores a neutral 50, and each extra net purchase adds
      ${M.smart_points_per_trade} points (each net sale subtracts ${M.smart_points_per_trade}), capped at 0 and 100.
      Insider awards and option exercises are ignored.</p>`;

  document.getElementById("smart-status").textContent = `Current status: ${latest.smart_money.note}`;
})();
