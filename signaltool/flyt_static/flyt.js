import * as THREE from './vendor/three.module.min.js';

const LAG_SRC = { 'råvare': 'Handelsdata', 'selskap': 'Selskapsrapport' };
const TYPE_LAB = { selskap: 'Selskaper', råvare: 'Råvarer', land: 'Land', sluttbruk: 'Sluttbruk' };
const TONN = new Set(['tonn', 't', 'tonnes', 'metric tonnes', 'metriske tonn', 'mt']);
const MAX_NODES = 25;
const YAW_MAX = Math.PI / 6;      // ±30°
const PITCH_MIN = 0;
const PITCH_MAX = Math.PI / 9;    // 20°
const ZOOM_MIN = 0.6, ZOOM_MAX = 2;
const EMPTY = 'Kilden beskriver ikke dette';
const MISS_CHAIN = 'Mangler data for verdikjeden';

const meta = JSON.parse(document.getElementById('flyt-meta')?.textContent || '{}');
const DATA_BASE = meta.data_base || 'flyt';
const KURS_URL = meta.kurs_url || 'data.json';

const $ = (id) => document.getElementById(id);
const el = {
  app: $('flyt-app'), q: $('flyt-q'), list: $('flyt-q-list'),
  kart: $('flyt-kart'), liste: $('flyt-liste'), hvis: $('flyt-hvis'),
  status: $('flyt-status'), crumb: $('flyt-crumb'),
  desk: $('flyt-desk'), wrap: $('flyt-stage-wrap'), scene: $('flyt-scene'),
  labels: $('flyt-labels'), panel: $('flyt-panel'), pbody: $('flyt-panel-body'),
  pclose: $('flyt-panel-close'), listView: $('flyt-list'), hvisBox: $('flyt-hvis-box'),
  hvisTekst: $('flyt-hvis-tekst'), zin: $('flyt-zoom-in'), zout: $('flyt-zoom-out'),
  reset: $('flyt-reset'),
};

let noder = [], kanter = [], scenarioer = [];
let byId = new Map();
let kurs = {}; // ticker -> entry from data.json
let universe = meta.universe || [];
let fokus = null;
let mode = 'kart'; // kart | liste
let is3d = false;
let zoom = 1, yaw = 0, pitch = Math.PI / 18; // 10°
let start = { zoom: 1, yaw: 0, pitch: Math.PI / 18, fokus: null };
let path = new Set();
let dimExcept = null;
let scenario = null;
let crumb = [];
let vis = { nodes: [], edges: [] };
let three = null; // {renderer, scene, camera, frames}
let dragging = null;
let webgl = true;

function slug(t) {
  return String(t || '').replace(/[^A-Za-z0-9_-]/g, '_');
}
function tickerOf(n) {
  if (n?.ticker) return n.ticker;
  if (n?.type === 'selskap' && n?.id) return n.id;
  return null;
}
function isTonn(u) { return TONN.has(String(u || '').trim().toLowerCase()); }
function isPub(e) { return e && e.publisert === true; }
function pubKanter(list) { return (list || kanter).filter(isPub); }
function hasPublished(ticker) {
  const nid = noder.find((n) => tickerOf(n) === ticker)?.id;
  if (!nid) return false;
  const adj = new Map();
  for (const e of pubKanter()) {
    if (!adj.has(e.fra)) adj.set(e.fra, []);
    if (!adj.has(e.til)) adj.set(e.til, []);
    adj.get(e.fra).push(e.til);
    adj.get(e.til).push(e.fra);
  }
  const seen = new Set([nid]);
  let frontier = [nid];
  for (let hop = 0; hop < 2; hop++) {
    const nxt = [];
    for (const u of frontier) {
      for (const v of adj.get(u) || []) {
        if (!seen.has(v)) { seen.add(v); nxt.push(v); return true; }
      }
    }
    frontier = nxt;
  }
  return false;
}
function parseFokus() {
  const u = new URL(location.href);
  return u.searchParams.get('fokus');
}
function setFokusUrl(id, push = true) {
  const u = new URL(location.href);
  if (id) u.searchParams.set('fokus', id);
  else u.searchParams.delete('fokus');
  if (push) history.pushState({ fokus: id }, '', u);
  else history.replaceState({ fokus: id }, '', u);
}
async function loadJson(url) {
  const r = await fetch(url);
  if (!r.ok) return null;
  return r.json();
}
function arr(obj, key, alt) {
  if (!obj) return [];
  if (Array.isArray(obj)) return obj;
  return obj[key] || obj[alt] || [];
}

function coverageFrom(nodes, edges, uni) {
  const adj = new Map();
  for (const n of nodes) adj.set(n.id, []);
  for (const e of pubKanter(edges)) {
    if (!adj.has(e.fra) || !adj.has(e.til)) continue;
    adj.get(e.fra).push([e.til, e]);
    adj.get(e.til).push([e.fra, e]);
  }
  const tickerId = new Map();
  for (const n of nodes) {
    const t = tickerOf(n);
    if (t) tickerId.set(t, n.id);
  }
  const has = (ticker, lag) => {
    const nid = tickerId.get(ticker);
    if (!nid) return false;
    const seen = new Set([nid]);
    let frontier = [nid];
    for (let hop = 0; hop < 2; hop++) {
      const nxt = [];
      for (const u of frontier) {
        for (const [v, e] of adj.get(u) || []) {
          if (e.lag === lag && e.status === 'kilde') return true;
          if (!seen.has(v)) { seen.add(v); nxt.push(v); }
        }
      }
      frontier = nxt;
    }
    return false;
  };
  const raw = uni.filter((t) => has(t, 'råvare'));
  const sel = uni.filter((t) => has(t, 'selskap'));
  return { n: uni.length, råvare_n: raw.length, selskap_n: sel.length,
    statuslinje: `Råvaredata for ${raw.length} av ${uni.length} · Selskapsdata for ${sel.length} av ${uni.length}` };
}

function hasKildeData(ticker) {
  return hasPublished(ticker);
}

function neighbors(id, hops = 2) {
  const ids = new Set([id]);
  let fringe = [id];
  const edges = [];
  for (let h = 0; h < hops; h++) {
    const nxt = [];
    for (const u of fringe) {
      for (const e of pubKanter()) {
        let v = null;
        if (e.fra === u && !ids.has(e.til)) v = e.til;
        else if (e.til === u && !ids.has(e.fra)) v = e.fra;
        if (e.fra === u || e.til === u) edges.push(e);
        if (v) { ids.add(v); nxt.push(v); }
      }
    }
    fringe = nxt;
  }
  // include edges between kept nodes
  const ev = pubKanter().filter((e) => ids.has(e.fra) && ids.has(e.til));
  return { ids, edges: ev };
}

function tickersOn(nodeId) {
  const out = [];
  const seen = new Set();
  for (const e of pubKanter()) {
    const other = e.fra === nodeId ? e.til : e.til === nodeId ? e.fra : null;
    if (!other) continue;
    const n = byId.get(other);
    const t = tickerOf(n);
    if (!t || seen.has(t)) continue;
    seen.add(t);
    const andel = (e.status === 'kilde' && e.enhet && String(e.enhet).includes('%')) ? e : null;
    // andel may also be on the company node or a dedicated field
    const share = (e.status === 'kilde' && e.verdi != null && /%|andel/i.test(String(e.enhet || ''))) ? e : null;
    out.push({ ticker: t, node: n, edge: e, share });
  }
  for (const n of noder) {
    const t = tickerOf(n);
    if (t && n.id !== nodeId) {
      const nb = neighbors(n.id, 2);
      if (nb.ids.has(nodeId) && !seen.has(t)) {
        seen.add(t);
        out.push({ ticker: t, node: n, edge: null, share: null });
      }
    }
  }
  return out;
}

function overviewGraph() {
  const connected = new Set();
  for (const e of pubKanter()) { connected.add(e.fra); connected.add(e.til); }
  const mats = noder.filter((n) => (n.type === 'råvare' || n.type === 'sluttbruk') && connected.has(n.id));
  const lands = noder.filter((n) => n.type === 'land' && connected.has(n.id));
  const nodes = [...mats, ...lands];
  const counts = new Map();
  for (const n of nodes) {
    const ts = new Set(tickersOn(n.id).map((x) => x.ticker));
    counts.set(n.id, ts.size);
  }
  return { nodes, counts };
}

function visibleSet(focusId) {
  if (!focusId) {
    const ov = overviewGraph();
    let nodes = ov.nodes.slice();
    const hidden = Math.max(0, nodes.length - MAX_NODES);
    if (nodes.length > MAX_NODES) nodes = nodes.slice(0, MAX_NODES);
    return { nodes, edges: [], overview: true, counts: ov.counts, hidden };
  }
  const t = tickerOf(byId.get(focusId)) || (byId.has(focusId) ? null : focusId);
  const focusNode = byId.get(focusId) || noder.find((n) => tickerOf(n) === focusId);
  if (!focusNode) return { nodes: [], edges: [], overview: false, hidden: 0, missing: true };
  const tk = tickerOf(focusNode);
  if (tk && !hasKildeData(tk)) {
    return { nodes: [focusNode], edges: [], overview: false, hidden: 0, missingChain: true };
  }
  const nb = neighbors(focusNode.id, 2);
  let nodes = noder.filter((n) => nb.ids.has(n.id));
  const hidden = Math.max(0, nodes.length - MAX_NODES);
  if (nodes.length > MAX_NODES) {
    // keep focus + nearest
    const rest = nodes.filter((n) => n.id !== focusNode.id);
    nodes = [focusNode, ...rest.slice(0, MAX_NODES - 1)];
  }
  const keep = new Set(nodes.map((n) => n.id));
  const edges = nb.edges.filter((e) => keep.has(e.fra) && keep.has(e.til));
  return { nodes, edges, overview: false, hidden, focus: focusNode };
}

function hopOf(id, focusId) {
  if (!focusId || id === focusId) return 0;
  const nb1 = neighbors(focusId, 1);
  if (nb1.ids.has(id)) return 1;
  return 2;
}

function layout(visu) {
  const W = el.scene.clientWidth || 840;
  const H = el.scene.clientHeight || 600;
  const pos = new Map();
  if (visu.overview) {
    const mats = visu.nodes.filter((n) => n.type === 'råvare' || n.type === 'sluttbruk');
    const lands = visu.nodes.filter((n) => n.type === 'land');
    const cols = [mats, lands];
    cols.forEach((col, ci) => {
      const x = W * (ci === 0 ? 0.32 : 0.68);
      col.forEach((n, i) => {
        const y = H * ((i + 1) / (col.length + 1));
        pos.set(n.id, { x, y, z: 0, hop: ci });
      });
    });
    return pos;
  }
  const focusId = visu.focus?.id || fokus;
  const groups = [[], [], []];
  for (const n of visu.nodes) groups[hopOf(n.id, focusId)].push(n);
  groups.forEach((g, hop) => {
    const x = W * (0.18 + hop * 0.32);
    g.forEach((n, i) => {
      const y = H * ((i + 1) / (g.length + 1));
      pos.set(n.id, { x, y, z: (hop - 1) * 20, hop });
    });
  });
  return pos;
}

function yearTonnScale(edges) {
  const byYear = new Map();
  for (const e of edges) {
    if (e.status === 'mangler' || e.verdi == null || !isTonn(e.enhet) || e.år == null) continue;
    const y = String(e.år);
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y).push(e);
  }
  const w = new Map();
  for (const [, list] of byYear) {
    const max = Math.max(...list.map((e) => Number(e.verdi) || 0), 1);
    for (const e of list) {
      const t = 1.2 + 4.5 * ((Number(e.verdi) || 0) / max);
      w.set(e, t);
    }
  }
  return w;
}

function srcLine(row) {
  const head = LAG_SRC[row.lag] || 'Kilde';
  const bits = [head];
  if (row.kilde) bits.push(row.kilde);
  if (row.år) bits.push(String(row.år));
  if (row.hs_kode) bits.push('HS ' + row.hs_kode);
  const text = bits.join(' · ');
  if (row.kilde_url) {
    const a = document.createElement('a');
    a.href = row.kilde_url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = text;
    const p = document.createElement('p');
    p.className = 'flyt-src';
    p.appendChild(a);
    if (row.status === 'estimat') {
      const em = document.createElement('span');
      em.textContent = ' · Estimat' + (row.metode ? `: ${row.metode}` : '');
      p.appendChild(em);
    }
    return p;
  }
  const p = document.createElement('p');
  p.className = 'flyt-src';
  p.textContent = text;
  return p;
}

function fmtVal(row) {
  if (row.status === 'mangler' || row.verdi == null || row.verdi === '') return null;
  const v = row.verdi;
  const num = typeof v === 'number' ? v.toLocaleString('nb-NO') : String(v);
  return [num, row.enhet, row.år].filter((x) => x != null && x !== '').join(' ');
}

function updateStatus() {
  const cov = coverageFrom(noder, kanter, universe);
  el.status.textContent = cov.statuslinje;
}

function fillSearch() {
  el.list.innerHTML = '';
  const opts = [];
  const visible = new Set();
  for (const e of pubKanter()) { visible.add(e.fra); visible.add(e.til); }
  for (const n of noder) {
    const t = tickerOf(n);
    if (!visible.has(n.id) && !universe.includes(t)) continue;
    opts.push({ v: n.id, lab: n.navn + (t && t !== n.navn ? ` (${t})` : '') });
    if (t && t !== n.id) opts.push({ v: t, lab: t });
  }
  for (const t of universe) {
    if (!opts.some((o) => o.v === t)) opts.push({ v: t, lab: t });
  }
  const seen = new Set();
  for (const o of opts) {
    if (seen.has(o.v)) continue;
    seen.add(o.v);
    const op = document.createElement('option');
    op.value = o.v;
    op.label = o.lab;
    el.list.appendChild(op);
  }
}

function resolveFokus(q) {
  if (!q) return null;
  if (byId.has(q)) return q;
  const up = q.toUpperCase();
  for (const n of noder) {
    if (tickerOf(n)?.toUpperCase() === up) return n.id;
    if (n.navn.toLowerCase() === q.toLowerCase()) return n.id;
    if (n.id.toLowerCase() === q.toLowerCase()) return n.id;
  }
  return q; // ukjent ticker: vis selskapsnode-mangel
}

/* ---------- panel ---------- */
function openPanel() {
  el.panel.hidden = false;
  if (matchMedia('(max-width:900px)').matches) {
    el.panel.classList.remove('sheet-90');
    el.panel.style.height = '50vh';
  }
}
function closePanel() {
  el.panel.hidden = true;
  el.pbody.innerHTML = '';
  el.panel.classList.remove('sheet-90');
}
function sec(title, body, id) {
  const d = document.createElement('section');
  d.className = 'flyt-sec';
  if (id) d.dataset.sec = id;
  const h = document.createElement('h3');
  h.textContent = title;
  d.appendChild(h);
  if (typeof body === 'string') {
    const p = document.createElement('p');
    p.textContent = body;
    d.appendChild(p);
  } else if (body) d.appendChild(body);
  return d;
}
function kursBlock(ticker) {
  const e = kurs[ticker];
  const wrap = document.createElement('div');
  wrap.className = 'flyt-kurs';
  if (!e) {
    const p = document.createElement('p');
    p.className = 'flyt-miss';
    p.textContent = 'Mangler kursdata';
    wrap.appendChild(p);
  } else {
    const st = e.stats || {};
    const rk = e._risk || {};
    const lv = rk.level;
    const risk = document.createElement('p');
    risk.innerHTML = lv ? `Risiko: <span class="rk">${esc(lv)}</span>` : 'Risiko: Ingen risikonivå';
    wrap.appendChild(risk);
    const flags = [].concat(e.flags || [], e.cat_flags || [], e._flag ? [e._flag] : []);
    if (flags.length) {
      const ul = document.createElement('ul');
      flags.flat().forEach((f) => {
        if (!f) return;
        const li = document.createElement('li');
        li.textContent = typeof f === 'string' ? f : (f.name || f.text || JSON.stringify(f));
        ul.appendChild(li);
      });
      const cap = document.createElement('p');
      cap.textContent = 'Røde flagg';
      wrap.appendChild(cap);
      wrap.appendChild(ul);
    }
    const k = document.createElement('p');
    k.appendChild(pctSpan('Kurs 5d', st.ret_5d));
    k.append(' · ');
    k.appendChild(pctSpan('20d', st.ret_20d));
    wrap.appendChild(k);
  }
  const a = document.createElement('a');
  a.href = `ticker/${slug(ticker)}.html`;
  a.textContent = 'Tickere';
  a.className = 'flyt-rel';
  wrap.appendChild(a);
  return wrap;
}
function pctSpan(lab, x) {
  const s = document.createElement('span');
  if (x == null) { s.textContent = `${lab}: –`; return s; }
  const cls = x > 0 ? 'up' : x < 0 ? 'down' : '';
  s.innerHTML = `${esc(lab)}: <span class="${cls}">${(x * 100).toFixed(1)} %</span>`;
  return s;
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderPanel(node) {
  el.pbody.innerHTML = '';
  if (!node) { closePanel(); return; }
  el.pbody.appendChild(sec('Hva det er', node.hva_det_er || node.navn, 'hva'));
  const tall = document.createElement('div');
  const fv = fmtVal(node);
  if (node.status === 'mangler') {
    const p = document.createElement('p');
    p.innerHTML = '<span class="badge">Mangler data</span>';
    if (node.grunn) p.append(' ' + node.grunn);
    tall.appendChild(p);
  } else if (fv) {
    const p = document.createElement('p');
    p.textContent = fv;
    if (node.status === 'estimat') {
      const b = document.createElement('span');
      b.className = 'badge';
      b.textContent = ' Estimat';
      p.appendChild(b);
    }
    tall.appendChild(p);
  } else {
    const p = document.createElement('p');
    p.className = 'flyt-miss';
    p.textContent = 'Mangler data';
    tall.appendChild(p);
  }
  tall.appendChild(srcLine(node));
  // edges into/out of node, each with source line
  for (const e of pubKanter().filter((x) => x.fra === node.id || x.til === node.id)) {
    if (e.status === 'mangler') continue;
    const ev = fmtVal(e);
    if (!ev) continue;
    const p = document.createElement('p');
    const other = byId.get(e.fra === node.id ? e.til : e.fra);
    p.textContent = `${other?.navn || (e.fra === node.id ? e.til : e.fra)}: ${ev}`;
    if (e.status === 'estimat') p.append(' (Estimat' + (e.metode ? ': ' + e.metode : '') + ')');
    if (e.avvik) p.append(' · avvik mellom kilder');
    tall.appendChild(p);
    tall.appendChild(srcLine(e));
  }
  el.pbody.appendChild(sec('Tall', tall, 'tall'));
  const tk = tickerOf(node);
  if (tk) el.pbody.appendChild(sec('Kurs', kursBlock(tk), 'kurs'));
  const rel = document.createElement('div');
  const nb = neighbors(node.id, 1);
  for (const n of noder.filter((x) => nb.ids.has(x.id) && x.id !== node.id)) {
    const a = document.createElement('a');
    a.className = 'flyt-rel';
    a.href = `flyt.html?fokus=${encodeURIComponent(tickerOf(n) || n.id)}`;
    a.textContent = n.navn;
    a.addEventListener('click', (ev) => { ev.preventDefault(); go(n.id, true); });
    rel.appendChild(a);
  }
  if (rel.childNodes.length) el.pbody.appendChild(sec('Relaterte noder', rel, 'relaterte'));
  if (node.type && node.type !== 'selskap') {
    const box = document.createElement('div');
    const list = tickersOn(node.id);
    if (!list.length) {
      const p = document.createElement('p');
      p.className = 'flyt-miss';
      p.textContent = 'Ingen tickere koblet hit';
      box.appendChild(p);
    }
    for (const row of list) {
      const a = document.createElement('a');
      a.className = 'flyt-tk';
      a.href = `flyt.html?fokus=${encodeURIComponent(row.ticker)}`;
      const left = document.createElement('span');
      left.textContent = row.ticker;
      a.appendChild(left);
      const right = document.createElement('span');
      if (row.share && row.share.status === 'kilde' && row.share.verdi != null) {
        right.textContent = fmtVal(row.share);
      } else {
        right.textContent = 'Mangler data';
        right.className = 'flyt-miss';
      }
      a.appendChild(right);
      a.addEventListener('click', (ev) => { ev.preventDefault(); go(row.node.id, true); });
      box.appendChild(a);
    }
    el.pbody.appendChild(sec('Tickere koblet hit', box, 'tickere-koblet'));
  }
  if (vis.missingChain) {
    const p = document.createElement('p');
    p.className = 'flyt-miss';
    p.textContent = MISS_CHAIN;
    el.pbody.appendChild(p);
  }
  openPanel();
}

/* ---------- path / crumb ---------- */
function markPath(id) {
  path = new Set([id]);
  const updown = neighbors(id, 8);
  // only nodes on some path — all neighbors in the visible 2-hop already; highlight incident
  for (const e of pubKanter()) {
    if (e.fra === id || e.til === id) { path.add(e.fra); path.add(e.til); }
  }
  // upstream/downstream along directed edges
  const down = [id], up = [id];
  const seenD = new Set([id]), seenU = new Set([id]);
  while (down.length) {
    const u = down.pop();
    for (const e of pubKanter()) if (e.fra === u && !seenD.has(e.til)) { seenD.add(e.til); path.add(e.til); down.push(e.til); }
  }
  while (up.length) {
    const u = up.pop();
    for (const e of pubKanter()) if (e.til === u && !seenU.has(e.fra)) { seenU.add(e.fra); path.add(e.fra); up.push(e.fra); }
  }
  dimExcept = path;
}

function renderCrumb() {
  el.crumb.innerHTML = '';
  if (!crumb.length) { el.crumb.hidden = true; return; }
  el.crumb.hidden = false;
  crumb.forEach((id, i) => {
    if (i) {
      const sep = document.createElement('span');
      sep.textContent = ' › ';
      sep.className = 'flyt-miss';
      el.crumb.appendChild(sep);
    }
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = byId.get(id)?.navn || id;
    b.addEventListener('click', () => {
      crumb = crumb.slice(0, i + 1);
      go(id, false);
    });
    el.crumb.appendChild(b);
  });
}

/* ---------- 2D / 3D ---------- */
function edgeKey(e) { return e.fra + '>' + e.til; }

function draw2D(visu, pos) {
  const W = el.scene.clientWidth, H = el.scene.clientHeight;
  const scale = yearTonnScale(visu.edges);
  const hit = new Set(scenario ? (scenario.kanter || []).map((k) => k.includes('>') ? k : '') : []);
  const hitN = new Set(scenario?.noder || []);
  let svg = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">`;
  for (const e of visu.edges) {
    if (e.status === 'mangler') continue;
    const a = pos.get(e.fra), b = pos.get(e.til);
    if (!a || !b) continue;
    const thick = scale.get(e) || 1.4;
    const cls = [
      e.status === 'estimat' ? 'est' : '',
      dimExcept && !dimExcept.has(e.fra) && !dimExcept.has(e.til) ? 'dim' : '',
      hit.has(edgeKey(e)) || (hitN.has(e.fra) && hitN.has(e.til)) ? 'hit' : '',
    ].filter(Boolean).join(' ');
    svg += `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke-width="${thick}" />`;
  }
  svg += '</svg>';
  el.scene.innerHTML = `<div class="flyt-2d">${svg}</div>`;
  placeLabels(visu, pos, hitN);
}

function placeLabels(visu, pos, hitN) {
  el.labels.innerHTML = '';
  const counts = visu.counts || new Map();
  for (const n of visu.nodes) {
    const p = pos.get(n.id);
    if (!p) continue;
    const d = document.createElement('div');
    d.className = 'flyt-lab';
    d.dataset.id = n.id;
    if (dimExcept && !dimExcept.has(n.id)) d.classList.add('dim');
    if (path.has(n.id)) d.classList.add('path');
    if (n.id === (visu.focus?.id || fokus)) d.classList.add('on');
    if (hitN?.has(n.id)) d.classList.add('hit');
    d.style.left = (p.x / (el.scene.clientWidth) * 100) + '%';
    d.style.top = (p.y / (el.scene.clientHeight) * 100) + '%';
    const nm = document.createElement('span');
    nm.className = 'n';
    nm.textContent = n.navn;
    d.appendChild(nm);
    const vv = document.createElement('span');
    vv.className = 'v';
    if (visu.overview && counts.has(n.id)) vv.textContent = `${counts.get(n.id)} tickere`;
    else {
      const fv = fmtVal(n);
      vv.textContent = fv || (n.år ? String(n.år) : '');
    }
    if (vv.textContent) d.appendChild(vv);
    if (n.status === 'estimat') {
      const b = document.createElement('span'); b.className = 'badge'; b.textContent = 'Estimat'; d.appendChild(b);
    }
    if (n.status === 'mangler') {
      const b = document.createElement('span'); b.className = 'badge'; b.textContent = 'Mangler data'; d.appendChild(b);
    }
    d.addEventListener('click', (ev) => { ev.stopPropagation(); onNode(n.id); });
    el.labels.appendChild(d);
  }
  if (visu.hidden) {
    const d = document.createElement('div');
    d.className = 'flyt-lab';
    d.style.left = '92%'; d.style.top = '92%';
    d.innerHTML = `<span class="n">+${visu.hidden} andre</span>`;
    d.addEventListener('click', () => showList(true));
    el.labels.appendChild(d);
  }
}

function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl') || c.getContext('experimental-webgl'));
  } catch { return false; }
}

function worldPos(p, W, H) {
  // map pixel layout to a shallow 3d volume
  const x = (p.x / W - 0.5) * 24;
  const y = (0.5 - p.y / H) * 16;
  const z = (p.z || 0) * 0.15;
  return new THREE.Vector3(x, y, z);
}

function ensure3D() {
  if (three) return three;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
  const group = new THREE.Group();
  scene.add(group);
  scene.add(new THREE.AmbientLight(0xffffff, 0.9));
  const dir = new THREE.DirectionalLight(0xffffff, 0.4);
  dir.position.set(2, 4, 3);
  scene.add(dir);
  el.scene.innerHTML = '';
  el.scene.appendChild(renderer.domElement);
  three = { renderer, scene, camera, group, nodes: new Map(), edges: [] };
  return three;
}

function setCamera(t) {
  const W = el.scene.clientWidth, H = el.scene.clientHeight;
  t.renderer.setSize(W, H, false);
  t.renderer.domElement.style.width = '100%';
  t.renderer.domElement.style.height = '100%';
  const aspect = W / Math.max(H, 1);
  const fr = 14 / zoom;
  t.camera.left = -fr * aspect;
  t.camera.right = fr * aspect;
  t.camera.top = fr;
  t.camera.bottom = -fr;
  t.camera.updateProjectionMatrix();
  const r = 28;
  const x = r * Math.sin(yaw) * Math.cos(pitch);
  const y = r * Math.sin(pitch) + 6;
  const z = r * Math.cos(yaw) * Math.cos(pitch);
  t.camera.position.set(x, y, z);
  t.camera.lookAt(0, 0, 0);
  t.camera.updateMatrixWorld();
}

function draw3D(visu, pos) {
  const t = ensure3D();
  while (t.group.children.length) t.group.remove(t.group.children[0]);
  t.nodes.clear();
  const W = el.scene.clientWidth, H = el.scene.clientHeight;
  const scale = yearTonnScale(visu.edges);
  const hitN = new Set(scenario?.noder || []);
  const hitE = new Set((scenario?.kanter || []).map((k) => String(k)));
  const matN = new THREE.MeshLambertMaterial({ color: 0x8b949e });
  const matOn = new THREE.MeshLambertMaterial({ color: 0xc9d1d9 });
  const matHit = new THREE.MeshLambertMaterial({ color: 0x6cb6ff });
  for (const n of visu.nodes) {
    const p = pos.get(n.id);
    if (!p) continue;
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.45, 20, 16), hitN.has(n.id) ? matHit : (n.id === visu.focus?.id ? matOn : matN));
    mesh.position.copy(worldPos(p, W, H));
    mesh.userData.id = n.id;
    if (dimExcept && !dimExcept.has(n.id)) mesh.material = mesh.material.clone(), mesh.material.transparent = true, mesh.material.opacity = 0.3;
    t.group.add(mesh);
    t.nodes.set(n.id, mesh);
  }
  for (const e of visu.edges) {
    if (e.status === 'mangler') continue;
    const a = pos.get(e.fra), b = pos.get(e.til);
    if (!a || !b) continue;
    const pa = worldPos(a, W, H), pb = worldPos(b, W, H);
    const thick = (scale.get(e) || 1.4) * 0.035;
    const geo = new THREE.BufferGeometry().setFromPoints([pa, pb]);
    const dashed = e.status === 'estimat';
    const col = hitE.has(edgeKey(e)) ? 0x6cb6ff : 0x8b949e;
    let line;
    if (dashed) {
      const mat = new THREE.LineDashedMaterial({ color: col, dashSize: 0.35, gapSize: 0.22, transparent: true, opacity: dimExcept && !dimExcept.has(e.fra) && !dimExcept.has(e.til) ? 0.3 : 1 });
      line = new THREE.Line(geo, mat);
      line.computeLineDistances();
    } else {
      const mat = new THREE.LineBasicMaterial({ color: col, linewidth: thick, transparent: true, opacity: dimExcept && !dimExcept.has(e.fra) && !dimExcept.has(e.til) ? 0.3 : 1 });
      line = new THREE.Line(geo, mat);
    }
    t.group.add(line);
  }
  setCamera(t);
  t.renderer.render(t.scene, t.camera);
  // project labels
  placeLabelsProjected(visu, pos, hitN, t);
}

function placeLabelsProjected(visu, pos, hitN, t) {
  el.labels.innerHTML = '';
  const W = el.scene.clientWidth, H = el.scene.clientHeight;
  const counts = visu.counts || new Map();
  for (const n of visu.nodes) {
    const mesh = t.nodes.get(n.id);
    if (!mesh) continue;
    const v = mesh.position.clone().project(t.camera);
    const x = (v.x * 0.5 + 0.5) * W;
    const y = (-v.y * 0.5 + 0.5) * H;
    const d = document.createElement('div');
    d.className = 'flyt-lab';
    d.dataset.id = n.id;
    if (dimExcept && !dimExcept.has(n.id)) d.classList.add('dim');
    if (path.has(n.id)) d.classList.add('path');
    if (n.id === (visu.focus?.id || fokus)) d.classList.add('on');
    if (hitN?.has(n.id)) d.classList.add('hit');
    d.style.left = x + 'px';
    d.style.top = y + 'px';
    const nm = document.createElement('span');
    nm.className = 'n';
    nm.textContent = n.navn;
    d.appendChild(nm);
    const vv = document.createElement('span');
    vv.className = 'v';
    if (visu.overview && counts.has(n.id)) vv.textContent = `${counts.get(n.id)} tickere`;
    else {
      const fv = fmtVal(n);
      vv.textContent = fv || (n.år ? String(n.år) : '');
    }
    if (vv.textContent) d.appendChild(vv);
    if (n.status === 'estimat') { const b = document.createElement('span'); b.className = 'badge'; b.textContent = 'Estimat'; d.appendChild(b); }
    if (n.status === 'mangler') { const b = document.createElement('span'); b.className = 'badge'; b.textContent = 'Mangler data'; d.appendChild(b); }
    d.addEventListener('click', (ev) => { ev.stopPropagation(); onNode(n.id); });
    el.labels.appendChild(d);
  }
  if (visu.hidden) {
    const d = document.createElement('div');
    d.className = 'flyt-lab';
    d.style.left = '92%'; d.style.top = '92%';
    d.innerHTML = `<span class="n">+${visu.hidden} andre</span>`;
    d.addEventListener('click', () => showList(true));
    el.labels.appendChild(d);
  }
}

function want3D() {
  return is3d && webgl && mode === 'kart' && (el.scene.clientWidth >= 700 || matchMedia('(min-width:901px)').matches);
}

function redraw() {
  vis = visibleSet(fokus);
  const pos = layout(vis);
  if (mode === 'liste') {
    el.wrap.hidden = false;
    // keep scene but list is shown
  }
  if (mode === 'kart') {
    el.listView.hidden = true;
    el.wrap.style.display = '';
    if (want3D()) draw3D(vis, pos);
    else {
      if (three) { three.renderer.dispose(); three = null; }
      draw2D(vis, pos);
    }
  }
  if (vis.missingChain && vis.focus) renderPanel(vis.focus);
}

function showList(force) {
  if (force) { mode = 'liste'; syncToggle(); }
  el.listView.hidden = false;
  el.wrap.style.display = 'none';
  closePanel();
  const groups = { selskap: [], råvare: [], land: [], sluttbruk: [] };
  const visN = vis.nodes.length ? vis.nodes : noder;
  for (const n of visN) (groups[n.type] || (groups.råvare)).push(n);
  el.listView.innerHTML = '';
  for (const [typ, rows] of Object.entries(groups)) {
    if (!rows.length) continue;
    const det = document.createElement('details');
    det.open = true;
    const sum = document.createElement('summary');
    sum.textContent = TYPE_LAB[typ] || typ;
    det.appendChild(sum);
    for (const n of rows) {
      const a = document.createElement('a');
      a.href = `flyt.html?fokus=${encodeURIComponent(tickerOf(n) || n.id)}`;
      a.textContent = n.navn + (fmtVal(n) ? ' · ' + fmtVal(n) : '');
      a.addEventListener('click', (ev) => { ev.preventDefault(); mode = 'kart'; syncToggle(); go(n.id, true); });
      det.appendChild(a);
    }
    el.listView.appendChild(det);
  }
}

function syncToggle() {
  const kartOn = mode === 'kart';
  el.kart.classList.toggle('on', kartOn);
  el.liste.classList.toggle('on', !kartOn);
  el.kart.setAttribute('aria-pressed', kartOn ? 'true' : 'false');
  el.liste.setAttribute('aria-pressed', kartOn ? 'false' : 'true');
  if (mode === 'liste') showList();
  else { el.listView.hidden = true; el.wrap.style.display = ''; redraw(); }
}

function onNode(id) {
  const n = byId.get(id);
  if (!n) return;
  if (crumb[crumb.length - 1] !== id) crumb.push(id);
  renderCrumb();
  markPath(id);
  renderPanel(n);
  if (tickerOf(n) || n.type) setFokusUrl(tickerOf(n) || n.id, true);
  fokus = n.id;
  redraw();
}

function go(id, push, fromUrl) {
  const resolved = resolveFokus(id);
  const node = byId.get(resolved) || noder.find((n) => tickerOf(n) === resolved);
  fokus = node ? node.id : resolved;
  if (!fromUrl) setFokusUrl(node ? (tickerOf(node) || node.id) : resolved, push);
  if (node) {
    if (!crumb.length || crumb[crumb.length - 1] !== node.id) crumb = [node.id];
    renderCrumb();
    markPath(node.id);
    renderPanel(node);
  } else {
    crumb = [];
    renderCrumb();
    dimExcept = null;
    path = new Set();
    // unknown ticker: synthetic missing company node
    const fake = { id: resolved, navn: resolved, type: 'selskap', ticker: resolved, lag: 'selskap', status: 'mangler', hva_det_er: 'Selskap i universet', grunn: MISS_CHAIN };
    vis = { nodes: [fake], edges: [], overview: false, hidden: 0, missingChain: true, focus: fake };
    renderPanel(fake);
  }
  redraw();
}

function resetView() {
  zoom = start.zoom;
  yaw = start.yaw;
  pitch = start.pitch;
  scenario = null;
  document.querySelectorAll('.flyt-chip').forEach((b) => b.setAttribute('aria-pressed', 'false'));
  const initial = start.fokus;
  crumb = initial ? [initial] : [];
  dimExcept = null;
  path = new Set();
  if (initial) go(initial, false, true);
  else {
    fokus = null;
    setFokusUrl(null, false);
    closePanel();
    renderCrumb();
    redraw();
  }
}

function applyScenario(id) {
  const s = scenarioer.find((x) => x.id === id) || null;
  scenario = s;
  document.querySelectorAll('.flyt-chip').forEach((b) => b.setAttribute('aria-pressed', b.dataset.scenario === id ? 'true' : 'false'));
  const box = el.hvisTekst;
  box.innerHTML = '';
  if (!s || !s.tekst || !s.tekst.length) {
    const p = document.createElement('p');
    p.className = 'flyt-hvis-s';
    p.textContent = EMPTY;
    box.appendChild(p);
  } else {
    for (const t of s.tekst) {
      const p = document.createElement('p');
      p.className = 'flyt-hvis-s';
      p.textContent = t.setning + ' ';
      if (t.kilde_url) {
        const a = document.createElement('a');
        a.href = t.kilde_url;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = t.side ? `Kilde, s. ${t.side}` : 'Kilde';
        p.appendChild(a);
      }
      box.appendChild(p);
    }
  }
  redraw();
}

/* ---------- events ---------- */
function bind() {
  el.kart.addEventListener('click', () => { if (!webgl && !hasWebGL()) { mode = 'liste'; } else mode = 'kart'; syncToggle(); });
  el.liste.addEventListener('click', () => { mode = 'liste'; syncToggle(); });
  el.hvis.addEventListener('click', () => {
    const on = el.hvisBox.hidden;
    el.hvisBox.hidden = !on;
    el.hvis.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  el.pclose.addEventListener('click', closePanel);
  el.zin.addEventListener('click', () => { zoom = Math.min(ZOOM_MAX, zoom + 0.2); redraw(); });
  el.zout.addEventListener('click', () => { zoom = Math.max(ZOOM_MIN, zoom - 0.2); redraw(); });
  el.reset.addEventListener('click', resetView);
  el.q.addEventListener('change', () => { const v = el.q.value.trim(); if (v) go(v, true); });
  el.q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const v = el.q.value.trim(); if (v) go(v, true); } });
  document.querySelectorAll('.flyt-chip').forEach((b) => {
    b.addEventListener('click', () => {
      const id = b.dataset.scenario;
      if (scenario?.id === id) applyScenario(null);
      else applyScenario(id);
    });
  });
  // bottom sheet snap 50 / 90
  let startY = null, startH = null;
  el.panel.addEventListener('pointerdown', (e) => {
    if (!matchMedia('(max-width:900px)').matches) return;
    startY = e.clientY;
    startH = el.panel.getBoundingClientRect().height;
    el.panel.setPointerCapture(e.pointerId);
  });
  el.panel.addEventListener('pointerup', (e) => {
    if (startY == null) return;
    const dy = startY - e.clientY;
    const vh = window.innerHeight;
    let h = startH + dy;
    const mid = (0.5 * vh + 0.9 * vh) / 2;
    if (h >= mid) { el.panel.classList.add('sheet-90'); el.panel.style.height = '90vh'; }
    else { el.panel.classList.remove('sheet-90'); el.panel.style.height = '50vh'; }
    startY = startH = null;
  });
  // rotate / zoom on scene
  el.scene.addEventListener('pointerdown', (e) => {
    if (!want3D()) return;
    dragging = { x: e.clientX, y: e.clientY, yaw, pitch };
    el.scene.setPointerCapture(e.pointerId);
  });
  el.scene.addEventListener('pointermove', (e) => {
    if (!dragging || !want3D()) return;
    const dx = (e.clientX - dragging.x) / 180;
    const dy = (e.clientY - dragging.y) / 240;
    yaw = Math.max(-YAW_MAX, Math.min(YAW_MAX, dragging.yaw + dx));
    pitch = Math.max(PITCH_MIN, Math.min(PITCH_MAX, dragging.pitch + dy));
    if (three) { setCamera(three); three.renderer.render(three.scene, three.camera); placeLabelsProjected(vis, layout(vis), new Set(scenario?.noder || []), three); }
  });
  el.scene.addEventListener('pointerup', () => { dragging = null; });
  el.scene.addEventListener('wheel', (e) => {
    if (mode !== 'kart') return;
    e.preventDefault();
    zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom * (e.deltaY > 0 ? 0.92 : 1.08)));
    redraw();
  }, { passive: false });
  addEventListener('popstate', () => {
    const f = parseFokus();
    if (f) go(f, false, true);
    else { fokus = null; crumb = []; dimExcept = null; closePanel(); renderCrumb(); redraw(); }
  });
  addEventListener('resize', () => {
    const wide = matchMedia('(min-width:901px)').matches;
    if (wide && webgl) is3d = true;
    else is3d = false;
    redraw();
  });
}

async function init() {
  webgl = hasWebGL();
  is3d = webgl && matchMedia('(min-width:901px)').matches;
  if (!webgl) { mode = 'liste'; }
  const [N, K, S, D] = await Promise.all([
    loadJson(`${DATA_BASE}/noder.json`),
    loadJson(`${DATA_BASE}/kanter.json`),
    loadJson(`${DATA_BASE}/scenarioer.json`),
    loadJson(KURS_URL),
  ]);
  noder = arr(N, 'noder', 'nodes');
  kanter = arr(K, 'kanter', 'edges');
  scenarioer = arr(S, 'scenarioer', 'scenarios');
  byId = new Map(noder.map((n) => [n.id, n]));
  if (D && Array.isArray(D.tickers)) {
    for (const e of D.tickers) kurs[e.ticker] = e;
  }
  if (!universe.length && meta.n) universe = meta.universe || [];
  if (!universe.length) {
    // fallback: tickers present as company nodes (ikke hardkodet 61)
    universe = noder.map(tickerOf).filter(Boolean);
  }
  updateStatus();
  fillSearch();
  bind();
  const qf = parseFokus();
  start = { zoom: 1, yaw: 0, pitch: is3d ? Math.PI / 18 : 0, fokus: qf ? resolveFokus(qf) : null };
  pitch = start.pitch;
  syncToggle();
  if (qf) go(qf, false, true);
  else redraw();
}

init().catch((err) => {
  el.status.textContent = 'Kunne ikke laste flyt-data.';
  console.error(err);
});
