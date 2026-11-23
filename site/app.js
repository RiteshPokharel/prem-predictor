const SVG = "http://www.w3.org/2000/svg";
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function el(tag, attrs = {}, ...kids) {
  const node = tag.startsWith("svg:") ? document.createElementNS(SVG, tag.slice(4)) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "text") node.textContent = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids) if (kid != null && kid !== false) node.append(kid);
  return node;
}

const pct = p => Math.round(p * 100);
const day = s => new Date(`${s.slice(0, 10)}T12:00:00Z`);
const fmt = (s, opts) => day(s).toLocaleDateString("en-GB", { timeZone: "UTC", ...opts });
const signed = n => n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0";
const tick = () => el("svg:svg", { width: 16, height: 16, viewBox: "0 0 16 16", "aria-hidden": "true" },
  el("svg:path", { d: "M3 8.5l3 3 7-7", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }));
const cross = () => el("svg:svg", { width: 16, height: 16, viewBox: "0 0 16 16", "aria-hidden": "true" },
  el("svg:path", { d: "M4 4l8 8M12 4l-8 8", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round" }));

const tip = document.getElementById("tip");
function showTip(e, nodes) {
  tip.replaceChildren(...nodes);
  tip.style.opacity = 1;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + 14, y = e.clientY - h - 12;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y < 8) y = e.clientY + 16;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
const hideTip = () => { tip.style.opacity = 0; };

const pickOf = m => [["H", m.pH], ["D", m.pD], ["A", m.pA]].reduce((a, b) => b[1] > a[1] ? b : a)[0];

// whole-number percentages that always add up to 100 (largest remainder)
function wholePercents(ps) {
  const raw = ps.map(p => p * 100), out = raw.map(Math.floor);
  const order = raw.map((v, i) => [v - out[i], i]).sort((a, b) => b[0] - a[0]);
  const short = 100 - out.reduce((a, b) => a + b, 0);
  for (let k = 0; k < short; k++) out[order[k][1]] += 1;
  return out;
}

function cells(m, { result = null } = {}) {
  const pick = pickOf(m), whole = wholePercents([m.pH, m.pD, m.pA]);
  return [["H", "Home win"], ["D", "Draw"], ["A", "Away win"]].map(([key, name], i) => {
    const v = whole[i];
    const td = el("td", { class: `cell${key === pick ? " pick" : ""}`, "data-final": v, "aria-label": `${name} ${v}%${key === pick ? ", model's pick" : ""}` });
    if (key === pick) td.append(el("span", { class: "ink" }));
    td.append(el("span", { class: "n", text: v }), el("span", { class: "pc", text: "%" }));
    if (result === key) td.append(el("span", { class: "ring", title: "Result" }));
    return td;
  });
}

/* ---------- coupon ---------- */
let openMatch = null;           // the one fixture whose detail row is showing
const fixtureRows = new Map();  // fixture -> { row, toggle }
function renderCoupon() {
  const fx = DATA.fixtures, body = document.getElementById("coupon-body");
  const rounds = [...new Set(fx.map(m => m.round).filter(Boolean))].sort((a, b) => a - b);
  const main = rounds[rounds.length - 1];
  document.getElementById("coupon-title").textContent = main ? `Gameweek ${main}` : "This week";
  const zone = fx[0] && fx[0].kickoff.endsWith("+01:00") ? "BST" : "GMT";
  document.getElementById("coupon-sub").textContent = `Kick-offs in UK time (${zone}) · Select a match for details`;

  let lastDay = null, n = 0;
  for (const m of fx) {
    const d = m.kickoff.slice(0, 10);
    if (d !== lastDay) { body.append(el("tr", { class: "day" }, el("td", { colspan: 6, text: fmt(d, { weekday: "long", day: "numeric", month: "long" }) }))); lastDay = d; }
    n += 1;
    const ko = el("td", { class: "ko hide-sm" }, m.kickoff.slice(11, 16), m.odds ? null : el("span", { class: "dagger", title: "No bookmaker odds yet", text: "†" }),
      m.round && m.round !== main ? el("span", { style: "display:block;font-size:12px", text: `Gameweek ${m.round}` }) : null);
    const row = el("tr", { class: "fixture", tabindex: 0, "aria-expanded": "false" },
      el("td", { class: "no", text: n }), ko,
      el("td", { class: "match" }, m.home, el("span", { class: "v", text: "v" }), m.away,
        el("span", { class: "ko-sm", text: `${m.kickoff.slice(11, 16)}${m.odds ? "" : " †"}` }),
        el("span", { class: "pred" }, el("span", { class: "k", text: "Prediction" }),
          el("span", { text: { H: `${m.home} win`, D: "Draw", A: `${m.away} win` }[pickOf(m)] }))),
      ...cells(m));
    const detail = el("tr", { class: "detail", hidden: true }, el("td", { colspan: 6 }));
    const setOpen = open => {
      detail.hidden = !open;
      row.setAttribute("aria-expanded", String(open));
      if (open) renderMatchDetail(detail.firstChild, m);
    };
    const toggle = () => {
      const opening = detail.hidden;
      if (openMatch) openMatch.setOpen(false);
      openMatch = opening ? { m, row, setOpen } : null;
      if (opening) setOpen(true);
    };
    fixtureRows.set(m, { row, toggle });
    row.addEventListener("click", toggle);
    row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    body.append(row, detail);
  }
  if (fx.length) fixtureRows.get(fx[0]).toggle();
  const noOdds = fx.filter(m => !m.odds).length;
  document.getElementById("coupon-foot").textContent =
    "Filled box: the model's pick. Numbers are percentage chances and add up to 100." +
    (noOdds ? ` † Bookmaker odds aren't out yet for ${noOdds === fx.length ? "any" : noOdds} of these matches, so they use ratings and xG only.` : "");
  renderStub();
}

function teamRow(name) { return DATA.table.find(t => t.Team === name) || {}; }

function renderMatchDetail(td, m) {
  const h = teamRow(m.home), a = teamRow(m.away);
  const chart = el("div");
  const f = (label, hv, av) => [el("span", { text: label }), el("span", { class: "fig", text: hv }), el("span", { class: "fig", text: av })];
  td.replaceChildren(el("div", { class: "detail-grid" },
    chart,
    el("div", { class: "facts" },
      el("span"), el("span", { class: "hd", text: m.home }), el("span", { class: "hd", text: m.away }),
      ...f("Table position", h.Pos ?? "–", a.Pos ?? "–"),
      ...f("Points", h.Pts ?? "–", a.Pts ?? "–"),
      ...f("Rating", h.Elo ?? "–", a.Elo ?? "–"),
      ...f("xG created per game", h.xgf?.toFixed(2) ?? "–", a.xgf?.toFixed(2) ?? "–"),
      ...f("xG conceded per game", h.xga?.toFixed(2) ?? "–", a.xga?.toFixed(2) ?? "–"))));
  // the predicted winner's line is red; on a predicted draw neither is
  const pick = pickOf(m);
  lineChart(chart, [
    { name: m.home, color: pick === "H" ? "var(--red)" : "var(--ink)", pts: series(m.home, true), tag: pick === "H" ? "Predicted to win" : null },
    { name: m.away, color: pick === "A" ? "var(--red)" : "var(--ink)", pts: series(m.away, true), dash: "5 4", tag: pick === "A" ? "Predicted to win" : null },
  ], 180, { names: true, key: true });
}

function renderStub() {
  const stub = document.getElementById("stub"), rec = DATA.record;
  if (!rec.length) {
    stub.append(el("div", { class: "stub-head" }, el("h2", { text: "Last round" })),
      el("div", { class: "stub-section" }, el("p", { text: "Results appear here once this round's matches are played." })));
    return;
  }
  const lastDates = [...new Set(rec.map(r => r.date))].sort();
  const latestWeek = weekOf(lastDates[lastDates.length - 1]);
  const last = rec.filter(r => weekOf(r.date) === latestWeek);
  const hits = last.filter(r => r.correct).length;
  const drawLink = el("a", { class: "more", href: "#/how" }, "Read more in How it works",
    el("svg:svg", { viewBox: "0 0 16 16", "aria-hidden": "true" }, el("svg:path", { d: "m6 3 5 5-5 5", fill: "none", stroke: "currentColor", "stroke-width": 2 })));
  stub.append(
    el("div", { class: "stub-head" },
      el("h2", { text: "Last round" }),
      el("div", { class: "stub-score" }, el("span", { class: "fig", text: `${hits}/${last.length}` }), el("span", { text: "picks correct" }))),
    el("ul", { class: "stub-list" }, ...last.map(r => el("li", {},
      el("span", {}, `${r.home} `, el("span", { class: "fig", text: `${r.hg}–${r.ag}` }), ` ${r.away}`),
      el("span", { class: `verdict ${r.correct ? "hit" : "miss"}`, "aria-label": r.correct ? "Correct" : "Missed" }, r.correct ? tick() : cross())))),
    el("div", { class: "stub-section" },
      el("h3", { text: "How often the prediction is right" }),
      el("div", { class: "bench" },
        ...benchRow("Our predictions", 0.535, false),
        ...benchRow("Bookmakers' predictions", 0.536, true)),
      el("p", { text: "Tested on 1,240 past matches. Bookmakers: how often their favourite won the same matches." })),
    el("div", { class: "stub-section" },
      el("h3", { text: "Why a draw is never predicted" }),
      el("p", { class: "draw-why", text: "1 in 4 matches end in a draw, but a draw is never the most likely result." }),
      drawLink));
  drawLink.addEventListener("click", e => {
    e.preventDefault();
    show("how");
    document.getElementById("why-draw").scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
  });
}

function benchRow(label, v, dim) {
  return [el("span", { text: label }),
    el("span", { class: "track" }, el("span", { class: `fill${dim ? " dim" : ""}`, style: `width:${(v * 100).toFixed(1)}%` })),
    el("span", { class: "fig", text: `${(v * 100).toFixed(v * 1000 % 10 ? 1 : 0)}%` })];
}

function weekOf(d) {
  const t = day(d); t.setUTCDate(t.getUTCDate() - ((t.getUTCDay() + 6) % 7));
  return t.toISOString().slice(0, 10);
}

/* signature: figures flip into place like a departure board, then the pick is inked */
function flipIn(scope) {
  const tds = [...scope.querySelectorAll(".cell")];
  if (reduceMotion) return;
  tds.forEach((td, i) => {
    const n = td.querySelector(".n"), final = td.dataset.final, ink = td.querySelector(".ink");
    if (ink) { ink.style.clipPath = "inset(0 100% 0 0)"; td.classList.remove("pick"); }
    const row = Math.floor(i / 3), start = 120 + row * 55 + (i % 3) * 25, flips = 6 + (i % 3);
    for (let k = 0; k < flips; k++) {
      setTimeout(() => { n.textContent = String(10 + Math.floor(Math.random() * 80)); }, start + k * 45);
    }
    setTimeout(() => {
      n.textContent = final;
      if (ink) {
        td.classList.add("pick");
        ink.style.clipPath = "inset(0 0 0 0)";  // final state, even if the animation below never runs
        ink.animate([{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0 0 0)" }],
          { duration: 320, easing: "cubic-bezier(0.16, 1, 0.3, 1)", fill: "forwards" });
      }
    }, start + flips * 45);
  });
}

/* ---------- results ---------- */
// Results are shown one gameweek at a time (newest first), so the page never grows past one round.
let gwList = [], gwIdx = 0;
const gwKey = r => r.gw ?? `w${weekOf(r.date)}`;
function renderResults() {
  const rec = DATA.record, sub = document.getElementById("results-sub");
  if (!rec.length) { sub.textContent = "Nothing settled yet. Results appear after the first matches are played."; return; }
  sub.replaceChildren(el("span", { class: "ring-key", "aria-hidden": "true" }), "The circle shows what actually happened");
  const groups = new Map();
  for (const r of [...rec].sort((a, b) => a.date.localeCompare(b.date))) {
    if (!groups.has(gwKey(r))) groups.set(gwKey(r), []);
    groups.get(gwKey(r)).push(r);
  }
  gwList = [...groups.values()];
  gwIdx = gwList.length - 1;
  document.getElementById("gw-sheet").hidden = false;
  document.getElementById("gw-prev").addEventListener("click", () => showGameweek(gwIdx - 1));
  document.getElementById("gw-next").addEventListener("click", () => showGameweek(gwIdx + 1));
  showGameweek(gwIdx);
  renderWeekly();
}

function showGameweek(i) {
  gwIdx = Math.max(0, Math.min(gwList.length - 1, i));
  const rows = gwList[gwIdx], hits = rows.filter(r => r.correct).length;
  document.getElementById("gw-name").textContent = rows[0].gw != null ? `Gameweek ${rows[0].gw}` : `Week of ${fmt(weekOf(rows[0].date), { day: "numeric", month: "short" })}`;
  document.getElementById("gw-sub").textContent = `${hits} of ${rows.length} predictions correct`;
  document.getElementById("gw-prev").disabled = gwIdx === 0;
  document.getElementById("gw-next").disabled = gwIdx === gwList.length - 1;
  const byDay = {};
  for (const r of rows) (byDay[r.date] ??= []).push(r);
  document.getElementById("results-sheets").replaceChildren(...Object.keys(byDay).sort().reverse().map(d => {
    const dayRows = byDay[d], h = dayRows.filter(r => r.correct).length;
    return el("div", { class: "sheet" },
      el("div", { class: "sheet-head" }, el("h2", { text: fmt(d, { weekday: "long", day: "numeric", month: "long" }) }), el("p", { text: `${h} of ${dayRows.length} correct` })),
      el("table", { class: "coupon settled" },
        el("thead", {}, el("tr", {},
          el("th", { scope: "col", class: "left" , text: "Match" }), el("th", { scope: "col", text: "Score" }),
          el("th", { scope: "col" }, el("span", { class: "key", text: "1" }), "Home"),
          el("th", { scope: "col" }, el("span", { class: "key", text: "X" }), "Draw"),
          el("th", { scope: "col" }, el("span", { class: "key", text: "2" }), "Away"),
          el("th", { scope: "col", class: "hide-sm" }))),
        el("tbody", {}, ...dayRows.map(r => el("tr", {},
          el("td", { class: "match" }, r.home, el("span", { class: "v", text: "v" }), r.away),
          el("td", { class: "score", text: `${r.hg}–${r.ag}` }),
          ...cells(r, { result: { Home: "H", Draw: "D", Away: "A" }[r.result] }),
          el("td", { class: `verdict ${r.correct ? "hit" : "miss"}` }, r.correct ? tick() : cross(), r.correct ? "Correct" : "Missed"))))));
  }));
}

function renderWeekly() {
  const box = document.getElementById("results-weekly");
  const weeks = {};
  for (const r of DATA.record) (weeks[weekOf(r.date)] ??= []).push(r.correct);
  const rows = Object.entries(weeks).sort().map(([w, v]) => ({ w, rate: v.filter(Boolean).length / v.length, n: v.length }));
  if (rows.length < 2) { box.replaceChildren(); return; }
  const W = box.clientWidth - 40;
  if (W <= 0) return;
  const H = 170, m = { t: 10, r: 10, b: 24, l: 40 };
  const y = v => m.t + (1 - v) * (H - m.t - m.b);
  const svg = el("svg:svg", { width: W, height: H, role: "img", "aria-label": "Share of correct picks by week" });
  for (const v of [0, 0.5, 1]) svg.append(el("svg:line", { class: "grid", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }), el("svg:text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", text: `${v * 100}%` }));
  const step = (W - m.l - m.r) / rows.length, bw = Math.min(26, step * 0.55);
  rows.forEach((r, i) => {
    const cx = m.l + step * (i + 0.5);
    const bar = el("svg:rect", { x: cx - bw / 2, y: y(r.rate), width: bw, height: y(0) - y(r.rate), fill: "var(--red)" });
    bar.addEventListener("mousemove", e => showTip(e, [el("span", { class: "fig", text: `${Math.round(r.rate * 100)}%` }), ` week of ${fmt(r.w, { day: "numeric", month: "short" })}, ${r.n} matches`]));
    bar.addEventListener("mouseleave", hideTip);
    svg.append(bar, el("svg:text", { x: cx, y: H - 6, "text-anchor": "middle", text: fmt(r.w, { day: "numeric", month: "short" }) }));
  });
  svg.append(el("svg:line", { class: "base", x1: m.l, x2: W - m.r, y1: y(0.535), y2: y(0.535) }),
    el("svg:text", { x: W - m.r, y: y(0.535) - 6, "text-anchor": "end", text: "53.5% tested" }));
  box.replaceChildren(el("div", { class: "sheet", style: "margin-bottom:24px" },
    el("div", { class: "sheet-head" }, el("h2", { text: "Correct picks by week" })),
    el("div", { style: "padding:12px 20px 16px" }, svg)));
}

/* ---------- teams ---------- */
let selected = null;
const currentSeason = Object.values(DATA.ratings).flat().reduce((a, r) => r[1] > a ? r[1] : a, "");

function series(team, thisSeasonOnly = false) {
  return (DATA.ratings[team] || []).filter(r => !thisSeasonOnly || r[1] === currentSeason)
    .map(([d, season, elo]) => ({ d, t: day(d).getTime(), season, elo }));
}
function change(team, games = 5) {
  const s = series(team);
  return s.length < 2 ? 0 : Math.round(s[s.length - 1].elo - s[Math.max(0, s.length - 1 - games)].elo);
}

function niceTicks(lo, hi, count) {
  const raw = (hi - lo) / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map(s => s * mag).find(s => s >= raw);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

function lineChart(box, lines, H = 220, { names = false, key = false } = {}) {
  const W = box.clientWidth;
  if (!W) return;
  lines = lines.filter(l => l.pts.length);
  if (!lines.length) return;
  const endText = (l, p) => names ? `${l.name} ${Math.round(p.elo)}` : String(Math.round(p.elo));
  const longest = Math.max(...lines.map(l => endText(l, l.pts[l.pts.length - 1]).length));
  const keyH = key ? 24 : 0;  // room above the plot for the home/away key
  H += keyH;
  const m = { t: 10 + keyH, r: 16 + longest * 7.5, b: 26, l: 46 };
  const all = lines.flatMap(l => l.pts);
  const t0 = Math.min(...all.map(p => p.t)), t1 = Math.max(...all.map(p => p.t));
  const lo = Math.min(1500, ...all.map(p => p.elo)) - 12, hi = Math.max(1500, ...all.map(p => p.elo)) + 12;
  const x = t => m.l + (t - t0) / (t1 - t0 || 1) * (W - m.l - m.r);
  const y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
  const svg = el("svg:svg", { width: W, height: H, role: "img", "aria-label": `Rating over time: ${lines.map(l => l.name).join(" and ")}` });
  for (const v of niceTicks(lo, hi, 4)) svg.append(el("svg:line", { class: "grid", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }), el("svg:text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", text: v }));
  const months = (t1 - t0) / 864e5 > 200 ? 2 : 1, s = new Date(t0);
  for (let d = new Date(Date.UTC(s.getUTCFullYear(), s.getUTCMonth() + 1, 1)); d.getTime() <= t1; d.setUTCMonth(d.getUTCMonth() + months)) {
    svg.append(el("svg:text", { x: x(d.getTime()), y: H - 4, "text-anchor": "middle", text: d.toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" }) }));
  }
  svg.append(el("svg:line", { class: "base", x1: m.l, x2: W - m.r, y1: y(1500), y2: y(1500) }));
  if (key) {
    const ky = 12, kx = m.l;
    svg.append(
      el("svg:line", { x1: kx, x2: kx + 18, y1: ky - 4, y2: ky - 4, stroke: "var(--ink)", "stroke-width": 2 }),
      el("svg:text", { class: "key", x: kx + 24, y: ky, text: "Home" }),
      el("svg:line", { x1: kx + 70, x2: kx + 88, y1: ky - 4, y2: ky - 4, stroke: "var(--ink)", "stroke-width": 2, "stroke-dasharray": "5 4" }),
      el("svg:text", { class: "key", x: kx + 94, y: ky, text: "Away" }));
  }
  for (const l of lines) {
    for (const season of new Set(l.pts.map(p => p.season))) {
      const seg = l.pts.filter(p => p.season === season);
      svg.append(el("svg:path", { d: seg.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.elo).toFixed(1)}`).join(""),
        fill: "none", stroke: l.color, "stroke-width": 2, "stroke-dasharray": l.dash || null, "stroke-linejoin": "round" }));
    }
  }
  const ends = lines.map(l => ({ l, p: l.pts[l.pts.length - 1] })).map(o => ({ ...o, yy: y(o.p.elo) })).sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < ends.length; i++) {
    const gap = ends[i - 1].l.tag ? 30 : 14;  // a tagged label takes two lines
    if (ends[i].yy - ends[i - 1].yy < gap) ends[i].yy = ends[i - 1].yy + gap;
  }
  for (const { l, p, yy } of ends) {
    svg.append(el("svg:circle", { cx: x(p.t), cy: y(p.elo), r: 3.5, fill: l.color }),
      el("svg:text", { class: "lbl", x: W - m.r + 8, y: yy + 4, text: endText(l, p), style: names ? `fill:${l.color}` : null }));
    if (l.tag) svg.append(el("svg:text", { class: "tag", x: W - m.r + 8, y: yy + 19, text: l.tag }));
  }
  const cross = el("svg:line", { stroke: "var(--muted)", y1: m.t, y2: H - m.b, visibility: "hidden" });
  const hit = el("svg:rect", { x: m.l, y: 0, width: Math.max(0, W - m.l - m.r), height: H, fill: "transparent" });
  const nearest = (pts, mx) => pts.reduce((a, b) => Math.abs(x(b.t) - mx) < Math.abs(x(a.t) - mx) ? b : a);
  hit.addEventListener("mousemove", e => {
    const mx = e.clientX - svg.getBoundingClientRect().left;
    const near = lines.map(l => nearest(l.pts, mx)), ref = nearest(near, mx);
    cross.setAttribute("x1", x(ref.t)); cross.setAttribute("x2", x(ref.t)); cross.setAttribute("visibility", "visible");
    showTip(e, [fmt(ref.d, { day: "numeric", month: "short", year: "numeric" }), ...lines.flatMap((l, i) => [el("br"), `${l.name} `, el("span", { class: "fig", text: Math.round(near[i].elo) })])]);
  });
  hit.addEventListener("mouseleave", () => { hideTip(); cross.setAttribute("visibility", "hidden"); });
  svg.append(cross, hit);
  box.replaceChildren(svg);
}

function renderTable() {
  document.getElementById("table-body").replaceChildren(...DATA.table.map(t => {
    const c = change(t.Team);
    const row = el("tr", { class: t.Team === selected ? "on" : "", tabindex: 0, "aria-selected": String(t.Team === selected) },
      el("td", { class: "pos", text: t.Pos }), el("td", { class: "t", text: t.Team }),
      el("td", {}, el("span", { class: "fig", text: t.P })),
      el("td", {}, el("span", { class: "fig", text: signed(t.GD) })),
      el("td", {}, el("span", { class: "fig", style: "font-weight:700", text: t.Pts })),
      el("td", {}, el("span", { class: "fig", text: t.Elo })),
      el("td", {}, el("span", { class: "fig", text: signed(c) })));
    row.addEventListener("click", () => { select(t.Team); revealPanel(); });
    row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(t.Team); revealPanel(); } });
    return row;
  }));
}

function renderTeamPanel() {
  const t = teamRow(selected), c = change(selected), chart = el("div", { style: "margin-top:14px" });
  const rank = [...DATA.table].sort((a, b) => b.Elo - a.Elo).findIndex(r => r.Team === selected) + 1;
  document.getElementById("team-name").textContent = t.Team;
  document.getElementById("team-sub").textContent = `${ordinal(t.Pos)} in the table · ${ordinal(rank)} by rating`;
  const next = DATA.fixtures.find(f => f.home === selected || f.away === selected);
  let nextEl = null;
  if (next) {
    const home = next.home === selected;
    nextEl = el("button", { class: "next-match", type: "button" },
      el("span", { class: "k", text: "Next match" }),
      el("span", { class: "opp" }, `${fmt(next.kickoff, { weekday: "short", day: "numeric", month: "short" })} ${next.kickoff.slice(11, 16)} · `,
        el("strong", { text: `v ${home ? next.away : next.home}` }), el("span", { class: "ha", text: home ? "Home" : "Away" })),
      el("span", { class: "go" }, "See match", el("svg:svg", { viewBox: "0 0 16 16", "aria-hidden": "true" },
        el("svg:path", { d: "m6 3 5 5-5 5", fill: "none", stroke: "currentColor", "stroke-width": 2 }))));
    nextEl.addEventListener("click", () => openFixture(next));
  }
  document.getElementById("team-body").replaceChildren(
    nextEl,
    el("div", { class: "team-top" },
      el("div", { class: "team-figs" },
        el("div", {}, "Rating", el("span", { class: "fig", text: t.Elo })),
        el("div", {}, "Last 5 games", el("span", { class: "fig", text: signed(c) })),
        el("div", {}, "xG created / conceded", el("span", { class: "fig", text: t.xgf != null ? `${t.xgf.toFixed(2)} / ${t.xga.toFixed(2)}` : "–" })))),
    chart);
  lineChart(chart, [{ name: t.Team, color: "var(--red)", pts: series(selected) }], 220);
}

const ordinal = n => n + ({ 1: "st", 2: "nd", 3: "rd" }[(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10] || "th");

function renderXg() {
  const box = document.getElementById("xg-chart"), W = box.clientWidth;
  if (!W) return;
  const teams = DATA.table.filter(t => t.xgf != null && t.xga != null);
  const H = W < 560 ? Math.round(W * 1.2) : Math.min(460, Math.max(340, W * 0.7)), m = { t: 12, r: 12, b: 82, l: 92 };
  const xs = teams.map(t => t.xgf), ys = teams.map(t => t.xga);
  const xlo = Math.min(...xs) - 0.1, xhi = Math.max(...xs) + 0.1, ylo = Math.min(...ys) - 0.1, yhi = Math.max(...ys) + 0.1;
  const x = v => m.l + (v - xlo) / (xhi - xlo) * (W - m.l - m.r);
  const y = v => m.t + (v - ylo) / (yhi - ylo) * (H - m.t - m.b);
  const svg = el("svg:svg", { width: W, height: H, role: "img", "aria-label": "xG created against xG conceded per game, per team" });
  for (const v of niceTicks(xlo, xhi, 6)) svg.append(el("svg:line", { class: "grid", x1: x(v), x2: x(v), y1: m.t, y2: H - m.b }), el("svg:text", { x: x(v), y: H - m.b + 20, "text-anchor": "middle", text: v.toFixed(1) }));
  for (const v of niceTicks(ylo, yhi, 5)) svg.append(el("svg:line", { class: "grid", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }), el("svg:text", { x: m.l - 10, y: y(v) + 4, "text-anchor": "end", text: v.toFixed(1) }));
  const cx = (m.l + W - m.r) / 2, cy = -(m.t + H - m.b) / 2;
  svg.append(
    el("svg:text", { class: "axis", x: cx, y: H - 30, "text-anchor": "middle", text: "Attack →" }),
    el("svg:text", { class: "axis-sub", x: cx, y: H - 8, "text-anchor": "middle", text: "More chances created (xG per game)" }),
    el("svg:text", { class: "axis", x: cy, y: 22, transform: "rotate(-90)", "text-anchor": "middle", text: "Defence →" }),
    el("svg:text", { class: "axis-sub", x: cy, y: 44, transform: "rotate(-90)", "text-anchor": "middle", text: "Fewer chances conceded (xG per game)" }));
  const pts = teams.map(t => ({ t, x: x(t.xgf), y: y(t.xga) }));
  for (const p of pts) {
    const on = p.t.Team === selected;
    const dot = el("svg:circle", { cx: p.x, cy: p.y, r: on ? 7 : 5, fill: on ? "var(--red)" : "var(--sheet)", stroke: on ? "var(--red)" : "var(--ink-2)", "stroke-width": on ? 2 : 1.5, style: "cursor:pointer" });
    dot.addEventListener("mousemove", e => showTip(e, [el("strong", { text: p.t.Team }), el("br"), `xG created ${p.t.xgf.toFixed(2)} · conceded ${p.t.xga.toFixed(2)}`]));
    dot.addEventListener("mouseleave", hideTip);
    dot.addEventListener("click", () => select(p.t.Team));
    svg.append(dot);
  }
  box.replaceChildren(svg);
  const placed = [], over = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  // label the most crowded dots first, while there is still room next to them
  const crowd = p => pts.filter(q => q !== p && Math.hypot(q.x - p.x, q.y - p.y) < 60).length;
  const order = [...pts].sort((a, b) => (b.t.Team === selected) - (a.t.Team === selected) || crowd(b) - crowd(a) || a.t.Team.localeCompare(b.t.Team));
  for (const p of order) {
    const on = p.t.Team === selected;
    const label = el("svg:text", { class: "lbl", text: p.t.Team, style: on ? "fill:var(--red);font-weight:700" : null });
    svg.append(label);
    const w = label.getComputedTextLength(), h = 15;
    const spots = [];
    for (const r of [8, 12, 18]) {
      spots.push([p.x + r, p.y - h / 2, "start", r], [p.x - r - w, p.y - h / 2, "end", r],
        [p.x - w / 2, p.y - r - h, "middle", r], [p.x - w / 2, p.y + r, "middle", r],
        [p.x + r * 0.7, p.y - r * 0.7 - h, "start", r], [p.x + r * 0.7, p.y + r * 0.7, "start", r],
        [p.x - r * 0.7 - w, p.y - r * 0.7 - h, "end", r], [p.x - r * 0.7 - w, p.y + r * 0.7, "end", r]);
    }
    const fits = ([sx, sy]) => {
      const b = { x: sx, y: sy, w, h };
      return sx >= m.l && sx + w <= W - m.r && sy >= 0 && sy + h <= H - m.b
        && !pts.some(q => over(b, { x: q.x - 7, y: q.y - 7, w: 14, h: 14 })) && !placed.some(o => over(b, { x: o.x - 6, y: o.y - 1, w: o.w + 12, h: o.h + 2 }));
    };
    const inside = ([x0, y0]) => x0 >= m.l && x0 + w <= W - m.r && y0 >= 0 && y0 + h <= H - m.b;
    const clearOfLabels = s => inside(s) && !placed.some(o => over({ x: s[0], y: s[1], w, h }, o));
    const [sx, sy, anchor] = spots.find(fits) || spots.find(clearOfLabels) || spots.find(([x0, y0]) => x0 >= m.l && x0 + w <= W - m.r && y0 >= 0) || spots[0];
    placed.push({ x: sx, y: sy, w, h });
    label.setAttribute("x", anchor === "start" ? sx : anchor === "end" ? sx + w : sx + w / 2);
    label.setAttribute("y", sy + h - 3);
    label.setAttribute("text-anchor", anchor);
  }
}

function select(team) {
  selected = team;
  renderTable(); renderTeamPanel(); renderXg();
}

// On one-column layouts the table sits below the panel, so bring the panel back into view.
function revealPanel() {
  const panel = document.getElementById("team-panel");
  if (panel.getBoundingClientRect().top < 0) panel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
}

function openFixture(m) {
  show("coupon");
  const f = fixtureRows.get(m);
  if (openMatch?.m !== m) f.toggle();
  f.row.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
  f.row.focus({ preventScroll: true });
}

function stepTeam(d) {
  const i = DATA.table.findIndex(t => t.Team === selected), n = DATA.table.length;
  select(DATA.table[(i + d + n) % n].Team);
}

document.getElementById("team-prev").addEventListener("click", () => stepTeam(-1));
document.getElementById("team-next").addEventListener("click", () => stepTeam(1));

/* ---------- how it works ---------- */
const TESTED = [
  ["Always home", 43.1, 1.074], ["Elo only", 52.2, 0.985], ["Elo + form", 52.4, 0.981],
  ["Elo + form + odds", 52.5, 0.972], ["This model", 53.5, 0.971], ["Bookmakers", 53.6, 0.969],
];
function dotPlot(box, col, lo, hi, step, fmtv) {
  const W = box.clientWidth;
  if (!W) return;
  const rowH = 26, m = { t: 6, r: 44, b: 22, l: 118 }, H = m.t + m.b + rowH * TESTED.length;
  const x = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r);
  const svg = el("svg:svg", { width: W, height: H, role: "img", "aria-label": box.previousElementSibling.textContent });
  for (let v = lo; v <= hi + 1e-9; v += step) {
    svg.append(el("svg:line", { class: "grid", x1: x(v), x2: x(v), y1: m.t, y2: H - m.b }),
      el("svg:text", { x: x(v), y: H - 6, "text-anchor": "middle", text: fmtv(v) }));
  }
  TESTED.forEach((r, i) => {
    const yy = m.t + rowH * (i + 0.5), v = r[col];
    const color = r[0] === "This model" ? "var(--red)" : r[0] === "Bookmakers" ? "var(--ink)" : "var(--muted)";
    const strong = color !== "var(--muted)";
    svg.append(el("svg:text", { x: m.l - 10, y: yy + 4, "text-anchor": "end", class: strong ? "lbl" : null, text: r[0] }),
      el("svg:line", { x1: x(lo), x2: x(v), y1: yy, y2: yy, stroke: color, "stroke-opacity": strong ? 0.5 : 0.35 }),
      el("svg:circle", { cx: x(v), cy: yy, r: strong ? 5.5 : 4.5, fill: color }),
      el("svg:text", { x: x(v) + 10, y: yy + 4, class: strong ? "lbl" : null, text: col === 1 ? `${v}%` : v.toFixed(3) }));
  });
  box.replaceChildren(svg);
}
function renderModelCharts() {
  dotPlot(document.getElementById("model-chart-acc"), 1, 40, 56, 4, v => `${v}%`);
  dotPlot(document.getElementById("model-chart-ll"), 2, 0.96, 1.08, 0.04, v => v.toFixed(2));
}

/* ---------- page ---------- */
const tabs = [...document.querySelectorAll(".tab")];
let nudged = false;  // hint once that the arrows switch team
function show(id, focus = false) {
  for (const t of tabs) {
    const on = t.getAttribute("aria-controls") === id;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    if (on && focus) t.focus();
  }
  if (id === "teams") {
    renderTeamPanel(); renderXg();
    if (!nudged) {
      nudged = true;
      document.querySelector(".switch-hint").classList.add("draw");
      document.getElementById("team-next").classList.add("nudge");
    }
  }
  if (id === "results") renderWeekly();
  if (id === "how") renderModelCharts();
  history.replaceState(null, "", id === "coupon" ? location.pathname : "#/" + id);
  scrollTo(0, 0);
}
document.getElementById("home-link").addEventListener("click", e => { e.preventDefault(); show("coupon"); });
tabs.forEach((t, i) => {
  t.addEventListener("click", () => show(t.getAttribute("aria-controls")));
  t.addEventListener("keydown", e => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (d) show(tabs[(i + d + tabs.length) % tabs.length].getAttribute("aria-controls"), true);
  });
});

// Updates run on Tuesday 06:00 and Friday 08:00 UK time (.github/workflows/weekly-predictions.yml).
function nextUpdate() {
  const now = new Date(), d = new Date(now);
  for (let i = 0; i < 8; i++, d.setDate(d.getDate() + 1)) {
    const wd = d.getDay();
    if ((wd === 2 || wd === 5) && (i > 0 || now.getHours() < (wd === 2 ? 6 : 8))) return i === 0 ? "Today" : d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  }
}
const upd = (k, v) => el("div", { class: "upd" }, el("span", { class: "k", text: k }), el("span", { class: "v", text: v }));
document.getElementById("stamp").replaceChildren(
  upd("Results to", fmt(DATA.updated, { day: "numeric", month: "short" })),
  upd("Next auto-update", nextUpdate()));
selected = DATA.table[0].Team;
renderCoupon();
renderResults();
renderTable();
flipIn(document.getElementById("coupon-body"));
// Tab links look like #/teams (not #teams, which would make the browser jump past the header).
if (tabs.some(t => "#/" + t.getAttribute("aria-controls") === location.hash)) show(location.hash.slice(2));
document.fonts.ready.then(() => { if (!document.getElementById("teams").hidden) renderXg(); });

let resizeTimer;
addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (!document.getElementById("teams").hidden) { renderTeamPanel(); renderXg(); }
    if (!document.getElementById("results").hidden) renderWeekly();
    if (!document.getElementById("how").hidden) renderModelCharts();
    if (!document.getElementById("coupon").hidden && openMatch) openMatch.setOpen(true);
  }, 150);
});
