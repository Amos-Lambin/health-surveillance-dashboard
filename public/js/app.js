'use strict';
const { SUPABASE_URL, SUPABASE_ANON_KEY } = window.APP_CONFIG;
const $ = (id) => document.getElementById(id);
const DAY = 86400000;
if (window.Chart) { Chart.defaults.animation = false; }

let token = null;
try { token = sessionStorage.getItem('token'); } catch (e) { /* storage blocked */ }
let state = null; // { profile, districts, diseases, rows }
let chart = null;
let chartBars = null;
let chartCtl = null;
let chartDist = null;
let chartInt = null;
let mapShapes = null;

/* ---------- pure helpers ---------- */
function weeksBetween(a, b) {
  return Math.round((new Date(b + 'T00:00:00Z') - new Date(a + 'T00:00:00Z')) / (7 * DAY));
}

function mondaysBetween(first, last) {
  const out = [];
  let t = new Date(first + 'T00:00:00Z').getTime();
  const end = new Date(last + 'T00:00:00Z').getTime();
  while (t <= end) { out.push(new Date(t).toISOString().slice(0, 10)); t += 7 * DAY; }
  return out;
}

// Sum rows per reported week for one disease and one district (or 'all').
function aggregate(rows, diseaseId, districtId) {
  const byWeek = new Map();
  for (const r of rows) {
    if (r.disease_id !== diseaseId) continue;
    if (districtId !== 'all' && r.district_id !== districtId) continue;
    const w = byWeek.get(r.week_start) || { week: r.week_start, cases: 0, recv: 0, exp: 0 };
    w.cases += r.cases; w.recv += r.reports_received; w.exp += r.reports_expected;
    byWeek.set(r.week_start, w);
  }
  return [...byWeek.values()].sort((a, b) => a.week.localeCompare(b.week));
}


function stats(values) {
  const n = values.length;
  if (n < 2) return null;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1));
  return { mean, sd, n };
}

/* ---------- network ---------- */
async function api(path) {
  const res = await fetch(SUPABASE_URL + path, {
    headers: { apikey: SUPABASE_ANON_KEY, Authorization: 'Bearer ' + token }
  });
  if (!res.ok) { const e = new Error('HTTP ' + res.status); e.status = res.status; throw e; }
  return res.json();
}

async function signIn(email, password) {
  const res = await fetch(SUPABASE_URL + '/auth/v1/token?grant_type=password', {
    method: 'POST',
    headers: { apikey: SUPABASE_ANON_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  if (!res.ok) throw new Error('Sign-in failed. Check your email and password.');
  token = (await res.json()).access_token;
  try { sessionStorage.setItem('token', token); } catch (e) { /* ignore */ }
}

/* ---------- views ---------- */
function showLogin(msg) {
  $('app-view').hidden = true; $('userbar').hidden = true; $('login-view').hidden = false;
  $('login-error').textContent = msg || ''; $('status').textContent = '';
}

function signOut() {
  token = null; state = null;
  try { sessionStorage.removeItem('token'); } catch (e) { /* ignore */ }
  $('password').value = '';
  showLogin('');
}

function fill(select, items) {
  select.replaceChildren(...items.map(([value, label]) => {
    const o = document.createElement('option'); o.value = value; o.textContent = label; return o;
  }));
}

async function init() {
  $('status').textContent = 'Loading data...';
  try {
    const [profiles, districts, diseases, rows, interest] = await Promise.all([
      api('/rest/v1/profiles?select=full_name,role,district_id'),
      api('/rest/v1/districts?select=id,name,dhis2_uid&order=name'),
      api('/rest/v1/diseases?select=id,name,icd10&order=name'),
      api('/rest/v1/weekly_cases_flagged?select=district_id,disease_id,week_start,cases,reports_received,reports_expected,low_count&order=week_start&limit=5000'),
      api('/rest/v1/web_interest?select=term,week_start,views&order=week_start&limit=3000')
    ]);
    if (!profiles.length) { showLogin('Your account has no role assigned. Ask an administrator.'); return; }
    state = { profile: profiles[0], districts, diseases, rows, interest };
  } catch (e) {
    if (e.status === 401) { signOut(); showLogin('Your session has expired. Please sign in again.'); return; }
    $('status').textContent = 'Could not load data (' + e.message + '). Try again later.';
    return;
  }
  const p = state.profile;
  const isOfficer = p.role === 'district_officer';
  $('whoami').textContent = (p.full_name || 'User') + ' (' + (isOfficer ? 'district officer' : 'national manager') + ')';
  fill($('disease'), state.diseases.map((d) => [d.id, d.name + ' (ICD-10 ' + d.icd10 + ')']));
  fill($('district'), (isOfficer ? [] : [['all', 'All districts (national)']])
    .concat(state.districts.map((d) => [d.id, d.name])));
  $('login-view').hidden = true; $('app-view').hidden = false; $('userbar').hidden = false;
  $('status').textContent = '';
  render();
}

function render() {
  const diseaseId = Number($('disease').value);
  const dv = $('district').value;
  const districtId = dv === 'all' ? 'all' : Number(dv);
  const diseaseName = state.diseases.find((d) => d.id === diseaseId).name;
  const districtName = districtId === 'all' ? 'all districts'
    : state.districts.find((d) => d.id === districtId).name;
  const series = aggregate(state.rows, diseaseId, districtId);
  $('trend-h').textContent = 'Weekly cases: ' + diseaseName + ', ' + districtName;

  if (!series.length) {
    ['kpi-cases', 'kpi-change', 'kpi-complete'].forEach((id) => { $(id).textContent = '-'; });
    $('kpi-week').textContent = 'No data for this selection.';
    $('caution').hidden = true;
    if (chart) { chart.destroy(); chart = null; }
    $('trend-table').tBodies[0].replaceChildren();
    clearExtras();
    return;
  }

  const latest = series[series.length - 1];
  const prev = series.length > 1 ? series[series.length - 2] : null;
  $('kpi-week').textContent = 'Week starting ' + latest.week + ' (' + series.length + ' reported weeks in total)';
  $('kpi-cases').textContent = latest.cases.toLocaleString();
  if (prev) {
    const gap = weeksBetween(prev.week, latest.week);
    $('kpi-change-lbl').textContent = 'Change vs previous reported week (' + gap + (gap === 1 ? ' week' : ' weeks') + ' earlier)';
    $('kpi-change').textContent = prev.cases === 0 ? 'n/a'
      : (latest.cases >= prev.cases ? '+' : '') + Math.round((100 * (latest.cases - prev.cases)) / prev.cases) + '%';
  } else {
    $('kpi-change-lbl').textContent = 'Change vs previous reported week';
    $('kpi-change').textContent = 'n/a';
  }
  $('kpi-complete').textContent = Math.round((100 * latest.recv) / latest.exp) + '%';
  $('kpi-complete-lbl').textContent = 'Reports received (' + latest.recv + ' of ' + latest.exp + ' expected)';
  $('caution').hidden = latest.cases >= 5;

  const labels = mondaysBetween(series[0].week, latest.week);
  const lookup = new Map(series.map((s) => [s.week, s.cases]));
  if (chart) chart.destroy();
  chart = new Chart($('trend'), {
    type: 'line',
    data: { labels, datasets: [{ label: 'Cases', data: labels.map((l) => (lookup.has(l) ? lookup.get(l) : null)),
      borderColor: '#0072b2', backgroundColor: '#0072b2', pointStyle: 'rectRot', pointRadius: 6,
      spanGaps: false, tension: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Cases per week' } },
        x: { ticks: { maxTicksLimit: 8, autoSkip: true }, title: { display: true, text: 'Week starting' } }
      },
      plugins: { legend: { display: false } }
    }
  });
  $('trend').setAttribute('aria-label', 'Line chart of weekly ' + diseaseName + ' cases in ' + districtName +
    '. ' + series.length + ' reported weeks. Latest week starting ' + latest.week + ': ' + latest.cases + ' cases.');

  $('trend-table').tBodies[0].replaceChildren(...series.map((s) => {
    const tr = document.createElement('tr');
    [s.week, s.cases, s.recv + ' / ' + s.exp].forEach((v) => {
      const td = document.createElement('td'); td.textContent = v; tr.appendChild(td);
    });
    return tr;
  }));
  setTimeout(() => renderExtras(diseaseId, districtId, districtName, series), 0);
}


function clearExtras() {
  [chartBars, chartCtl, chartDist, chartInt].forEach((c) => { if (c) c.destroy(); });
  chartBars = null; chartCtl = null; chartDist = null; chartInt = null;
  $('map').replaceChildren(); $('legend').replaceChildren(); $('map-caption').textContent = '';
  $('dist-section').hidden = true;
  $('alert-status').textContent = '';
}

function renderExtras(diseaseId, districtId, districtName, series) {
  const latest = series[series.length - 1];
  renderMap(diseaseId, districtId, latest.week);
  setTimeout(() => renderInterest(state.diseases.find((d) => d.id === diseaseId).name), 0);

  // District comparison: only for the national view.
  const distSec = $('dist-section');
  if (chartDist) { chartDist.destroy(); chartDist = null; }
  distSec.hidden = districtId !== 'all';
  if (districtId === 'all') {
    const totals = new Map();
    state.rows.forEach((r) => {
      if (r.disease_id === diseaseId && r.week_start === latest.week) {
        totals.set(r.district_id, (totals.get(r.district_id) || 0) + r.cases);
      }
    });
    const list = state.districts.filter((d) => totals.has(d.id))
      .map((d) => [d.name, totals.get(d.id)]).sort((a, b) => b[1] - a[1]);
    const dName = state.diseases.find((d) => d.id === diseaseId).name;
    $('dist-h').textContent = 'Cases by district: ' + dName + ', week starting ' + latest.week;
    chartDist = new Chart($('dist'), {
      type: 'bar',
      data: { labels: list.map((i) => i[0] + (i[1] < 5 ? ' *' : '')),
        datasets: [{ label: 'Cases', data: list.map((i) => i[1]), backgroundColor: '#0072b2' }] },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        scales: { x: { beginAtZero: true, title: { display: true, text: 'Cases in the week' } } },
        plugins: { legend: { display: false } } }
    });
    $('dist').setAttribute('aria-label', 'Bar chart of ' + dName + ' cases by district for week starting ' +
      latest.week + '. ' + list.map((i) => i[0] + ' ' + i[1]).join(', ') + '.');
  }

  setTimeout(() => {
  // Comparison bar chart: every disease, same latest week, same district selection.
  const items = state.diseases.map((d) => {
    const w = aggregate(state.rows, d.id, districtId).find((x) => x.week === latest.week);
    return [d.name, w ? w.cases : null];
  });
  $('bars-h').textContent = 'Cases by disease, week starting ' + latest.week + ': ' + districtName;
  if (chartBars) chartBars.destroy();
  chartBars = new Chart($('bars'), {
    type: 'bar',
    data: { labels: items.map((i) => i[0]), datasets: [{ label: 'Cases', data: items.map((i) => i[1]),
      backgroundColor: ['#0072b2', '#d55e00', '#009e73', '#cc79a7'] }] },
    options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: { x: { beginAtZero: true, title: { display: true, text: 'Cases in the week' } } },
      plugins: { legend: { display: false } } }
  });
  $('bars').setAttribute('aria-label', 'Bar chart of cases by disease for week starting ' + latest.week + ' in ' +
    districtName + ': ' + items.map((i) => i[0] + ' ' + (i[1] === null ? 'no data' : i[1])).join(', ') + '.');
  }, 0);

  setTimeout(() => {
  // Control chart: baseline is every reported week before the latest.
  const st = series.length - 1 >= 8 ? stats(series.slice(0, -1).map((s) => s.cases)) : null;
  const status = $('alert-status');
  if (chartCtl) { chartCtl.destroy(); chartCtl = null; }
  if (!st) {
    status.classList.remove('caution');
    status.textContent = 'Not enough earlier reported weeks to set a threshold (at least 8 needed).';
    return;
  }
  const ucl = st.mean + 2 * st.sd;
  const above = latest.cases > ucl;
  status.classList.toggle('caution', above);
  status.textContent = 'Latest week (starting ' + latest.week + '): ' + latest.cases + ' cases, ' +
    (above ? 'ABOVE' : 'within') + ' the threshold of ' + Math.round(ucl) + ' (average ' + Math.round(st.mean) +
    ' of ' + st.n + ' earlier reported weeks, plus 2 standard deviations).';

  const labels = mondaysBetween(series[0].week, latest.week);
  const lookup = new Map(series.map((s) => [s.week, s.cases]));
  const vals = labels.map((l) => (lookup.has(l) ? lookup.get(l) : null));
  chartCtl = new Chart($('control'), {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Cases', data: vals, borderColor: '#0072b2', spanGaps: false, tension: 0, pointRadius: 6,
        pointStyle: vals.map((v) => (v !== null && v > ucl ? 'triangle' : 'rectRot')),
        pointBackgroundColor: vals.map((v) => (v !== null && v > ucl ? '#d55e00' : '#0072b2')),
        pointBorderColor: vals.map((v) => (v !== null && v > ucl ? '#d55e00' : '#0072b2')) },
      { label: 'Average of earlier weeks', data: labels.map(() => st.mean), borderColor: '#009e73',
        borderDash: [6, 4], pointRadius: 0 },
      { label: 'Threshold (average + 2 SD)', data: labels.map(() => ucl), borderColor: '#d55e00',
        borderDash: [2, 3], pointRadius: 0 }
    ] },
    options: { responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, title: { display: true, text: 'Cases per week' } },
        x: { ticks: { maxTicksLimit: 8, autoSkip: true }, title: { display: true, text: 'Week starting' } } },
      plugins: { legend: { display: true } } }
  });
  $('control').setAttribute('aria-label', 'Control chart for ' + districtName + '. ' + status.textContent);
  }, 0);
}

/* ---------- map (plain SVG, no map library, no external tiles) ---------- */
function eachRing(geometry, fn) {
  const polys = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  polys.forEach((p) => p.forEach(fn));
}

async function getMapShapes() {
  if (mapShapes) return mapShapes;
  const res = await fetch('data/districts.geojson');
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const g = await res.json();
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  g.features.forEach((f) => eachRing(f.geometry, (ring) => ring.forEach(([x, y]) => {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  })));
  const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
  const W = 600, scale = W / ((maxX - minX) * k), H = Math.ceil((maxY - minY) * scale);
  const px = (x) => ((x - minX) * k * scale).toFixed(1);
  const py = (y) => ((maxY - y) * scale).toFixed(1);
  const shapes = g.features.map((f) => {
    let d = '';
    eachRing(f.geometry, (ring) => { d += 'M' + ring.map(([x, y]) => px(x) + ' ' + py(y)).join('L') + 'Z'; });
    return { uid: f.properties.uid, name: f.properties.name, d };
  });
  mapShapes = { shapes, W, H };
  return mapShapes;
}

function selectDistrict(d) {
  if (!d) return;
  const opt = [...$('district').options].find((o) => Number(o.value) === d.id);
  if (!opt) return;
  $('district').value = opt.value;
  render();
}

async function renderMap(diseaseId, districtId, week) {
  let m;
  try { m = await getMapShapes(); } catch (e) {
    $('map-caption').textContent = 'Map boundaries could not be loaded (' + e.message + ').';
    return;
  }
  const isOfficer = state.profile.role === 'district_officer';
  const byUid = new Map(state.districts.map((d) => [d.dhis2_uid, d]));
  const totals = new Map();
  state.rows.forEach((r) => {
    if (r.disease_id === diseaseId && r.week_start === week) {
      totals.set(r.district_id, (totals.get(r.district_id) || 0) + r.cases);
    }
  });
  // Managers: scale by the highest district this week. Officers only see one district,
  // so scale by that district's own highest weekly count.
  const max = isOfficer
    ? Math.max(1, ...state.rows.filter((r) => r.disease_id === diseaseId).map((r) => r.cases))
    : Math.max(1, ...totals.values());
  const step = max / 5;
  const COLORS = ['#fef0d9', '#fdcc8a', '#fc8d59', '#e34a33', '#b30000']; // light orange to dark red
  const GREY = '#c9d0d3';
  const NS = 'http://www.w3.org/2000/svg';
  const svg = $('map');
  svg.setAttribute('viewBox', '0 0 ' + m.W + ' ' + m.H);
  svg.replaceChildren();
  const selectedUid = districtId === 'all' ? null
    : (state.districts.find((d) => d.id === districtId) || {}).dhis2_uid;
  const ordered = m.shapes.slice().sort((a, b) => (a.uid === selectedUid) - (b.uid === selectedUid));
  let ownPath = null;
  // A copy of the hovered district drawn on top, enlarged with a shadow, so it "lifts" off the map.
  const hl = document.createElementNS(NS, 'path');
  hl.setAttribute('class', 'hl');
  hl.setAttribute('aria-hidden', 'true');
  hl.style.display = 'none';
  const lift = (p) => { hl.setAttribute('d', p.getAttribute('d')); hl.setAttribute('fill', p.getAttribute('fill')); hl.style.display = ''; };
  const drop = () => { hl.style.display = 'none'; };

  ordered.forEach((s) => {
    const d = byUid.get(s.uid);
    const v = d ? totals.get(d.id) : undefined;
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', s.d);
    if (isOfficer && !d) { // outside this officer's access: plain white context shape
      p.style.fill = 'var(--surface)';
      p.setAttribute('class', 'inert');
      p.setAttribute('aria-hidden', 'true');
      svg.appendChild(p);
      return;
    }
    const label = v === undefined ? s.name + ': no data'
      : s.name + ': ' + v + ' cases' + (v < 5 ? ' (fewer than 5, interpret with caution)' : '');
    p.setAttribute('fill', v === undefined ? GREY : COLORS[Math.min(4, Math.floor(v / step))]);
    p.setAttribute('tabindex', '0');
    p.setAttribute('role', 'button');
    p.setAttribute('aria-label', label + '. Select to filter.');
    if (v !== undefined && v < 5) p.style.strokeDasharray = '4 3';
    if (s.uid === selectedUid) { p.style.stroke = 'var(--ink)'; p.style.strokeWidth = '3'; }
    if (d) ownPath = ownPath || p;
    const t = document.createElementNS(NS, 'title'); t.textContent = label; p.appendChild(t);
    const say = () => { $('map-caption').textContent = label; lift(p); };
    p.addEventListener('mouseenter', say);
    p.addEventListener('focus', say);
    p.addEventListener('mouseleave', drop);
    p.addEventListener('blur', drop);
    p.addEventListener('click', () => selectDistrict(d));
    p.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectDistrict(d); }
    });
    svg.appendChild(p);
  });

  svg.appendChild(hl);
  if (isOfficer && ownPath) { // zoom to the officer's own district
    const bb = ownPath.getBBox();
    const pad = Math.max(bb.width, bb.height) * 0.08;
    svg.setAttribute('viewBox', [bb.x - pad, bb.y - pad, bb.width + 2 * pad, bb.height + 2 * pad].join(' '));
  }
  $('map-caption').textContent = 'Week starting ' + week + '. Hover or focus a district for its count.' +
    (isOfficer ? ' Colours are relative to this district\'s own highest weekly count.' : '');

  const items = COLORS.map((c, i) => [c, Math.round(i * step) + ' to ' + Math.round((i + 1) * step) + ' cases']);
  items.push(isOfficer ? ['var(--surface)', 'Other districts (outside your access)'] : [GREY, 'No data']);
  $('legend').replaceChildren(...items.map(([c, text]) => {
    const li = document.createElement('li');
    const sw = document.createElement('span'); sw.className = 'sw'; sw.style.background = c;
    li.append(sw, text);
    return li;
  }));
}

/* ---------- public interest ---------- */
function renderInterest(diseaseName) {
  if (chartInt) { chartInt.destroy(); chartInt = null; }
  const pts = state.interest.filter((r) => r.term === diseaseName);
  if (!pts.length) {
    $('interest').setAttribute('aria-label', 'No pageview data for ' + diseaseName);
    return;
  }
  chartInt = new Chart($('interest'), {
    type: 'line',
    data: { labels: pts.map((p) => p.week_start), datasets: [{ label: 'Wikipedia pageviews',
      data: pts.map((p) => p.views), borderColor: '#cc79a7', backgroundColor: '#cc79a7',
      pointStyle: 'circle', pointRadius: 3, tension: 0 }] },
    options: { responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, title: { display: true, text: 'Views per week' } },
        x: { ticks: { maxTicksLimit: 8, autoSkip: true }, title: { display: true, text: 'Week starting' } } },
      plugins: { legend: { display: false } } }
  });
  const last = pts[pts.length - 1];
  $('interest').setAttribute('aria-label', 'Line chart of weekly English Wikipedia pageviews for ' + diseaseName +
    ' over ' + pts.length + ' weeks. Latest week starting ' + last.week_start + ': ' + last.views + ' views.');
}

/* ---------- CSV export (aggregated district-week counts only) ---------- */
function csvCell(v) {
  let t = v === null || v === undefined ? '' : String(v);
  if (typeof v === 'string' && /^[=+\-@\t\r]/.test(t)) t = "'" + t; // block spreadsheet formula injection
  return /[",\r\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
}

function exportCsv() {
  const diseaseId = Number($('disease').value);
  const dv = $('district').value;
  const disease = state.diseases.find((d) => d.id === diseaseId);
  const names = new Map(state.districts.map((d) => [d.id, d.name]));
  const rows = state.rows
    .filter((r) => r.disease_id === diseaseId && (dv === 'all' || r.district_id === Number(dv)))
    .sort((a, b) => (names.get(a.district_id) || '').localeCompare(names.get(b.district_id) || '')
      || a.week_start.localeCompare(b.week_start));
  const header = ['district', 'disease', 'icd10', 'week_start', 'cases', 'reports_received',
    'reports_expected', 'completeness_pct', 'fewer_than_5_cases'];
  const lines = [header.join(',')].concat(rows.map((r) => [
    names.get(r.district_id), disease.name, disease.icd10, r.week_start, r.cases,
    r.reports_received, r.reports_expected,
    Math.round((1000 * r.reports_received) / r.reports_expected) / 10, r.cases < 5 ? 'yes' : 'no'
  ].map(csvCell).join(',')));
  const blob = new Blob(['\ufeff' + lines.join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' });
  const label = dv === 'all' ? 'all-districts' : names.get(Number(dv));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = ('surveillance_' + disease.name + '_' + label + '.csv').toLowerCase().replace(/[^a-z0-9_.]+/g, '-');
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  $('status').textContent = rows.length + ' rows downloaded.';
}

/* ---------- wiring ---------- */
$('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('login-error').textContent = '';
  try {
    await signIn($('email').value.trim(), $('password').value);
    $('password').value = '';
    await init();
  } catch (err) {
    showLogin(err.message);
  }
});
$('signout').addEventListener('click', signOut);
$('export').addEventListener('click', exportCsv);
$('disease').addEventListener('change', render);
$('district').addEventListener('change', render);

if (token) init(); else showLogin('');
