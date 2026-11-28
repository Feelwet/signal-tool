import * as THREE from './vendor/three.module.min.js';

const LAG_SRC = { 'råvare': 'Handelsdata', 'selskap': 'Selskapsrapport' };
const TYPE_LAB = { selskap: 'Selskaper', ticker: 'Selskaper', råvare: 'Råvarer', vare: 'Råvarer', land: 'Land', sluttbruk: 'Sluttbruk', verk: 'Verk og anlegg', anlegg: 'Verk og anlegg', energi: 'Råvarer' };
const MAX_LAND_PER_LAG = 6;
const MAX_SELSKAP_OVERSIKT = 8;
const TONN = new Set(['tonn', 't', 'tonnes', 'metric tonnes', 'metriske tonn', 'mt']);
const MAX_NODES = 40;
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
  reset: $('flyt-reset'), handle: $('flyt-sheet-handle'), chips: $('flyt-hvis-chips'),
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
let verkOpen = false;
let three = null; // {renderer, scene, camera, frames}
let dragging = null;
let webgl = true;
let listFilter = null;
let aggregatOnly = false;
let listIndex = [];
let oversiktPack = null;
let fokusFiler = {};
let gicsNames = [];

function slug(t) {
  return String(t || '').replace(/[^A-Za-z0-9_-]/g, '_');
}
function canonType(typ) {
  if (typ === 'anlegg') return 'verk';
  if (typ === 'ticker') return 'selskap';
  if (typ === 'vare') return 'råvare';
  return typ;
}
function isVare(n) { return n && canonType(n.type) === 'råvare'; }
let overviewPackGap = 44;
function isMobile() { return matchMedia('(max-width:900px)').matches; }
function isWide() { return matchMedia('(min-width:901px)').matches; }
function inUniverse(ticker) { return !!(ticker && universe.includes(ticker)); }
function tickerPageHref(ticker) {
  return inUniverse(ticker) ? `ticker/${slug(ticker)}.html` : null;
}
function yearInText(s) {
  const m = String(s || '').match(/\b((?:19|20)\d{2})\b/);
  return m ? m[1] : null;
}
function kildeKort(row) {
  const kilde = String(row?.kilde || '').trim();
  const y = yearOf(row) ?? yearInText(kilde);
  const side = row?.side ? `, s. ${row.side}` : '';
  if (/årsrapport/i.test(kilde)) {
    return (y != null && y !== '' ? `Årsrapport ${y}` : 'Årsrapport') + side;
  }
  if (kilde) {
    return kilde + side;
  }
  if (y != null && y !== '') return `Årsrapport ${y}` + side;
  return side ? side.replace(/^, /, '') : 'Kilde';
}
function srcText(row) {
  const lag = LAG_SRC[row?.lag] || 'Kilde';
  const kilde = String(row?.kilde || '').trim();
  const y = yearOf(row);
  const bits = [lag];
  if (kilde) bits.push(kilde);
  else if (y != null && y !== '' && !kilde) bits.push(String(y));
  let text = bits.join(' · ');
  if (row?.side) text += (text ? ', ' : '') + 's. ' + row.side;
  if (row?.hs_kode) text += ' · HS ' + row.hs_kode;
  // FLAG 5: SSB-tall er Norges egen rapportering; partnertall er ikke hentet.
  if (/SSB/.test(kilde) && !/kun norsk rapportering/.test(text)) text += ' · kun norsk rapportering';
  return text;
}

function tickerOf(n) {
  if (n?.ticker) return n.ticker;
  const nid = String(n?.id || '');
  if (nid.startsWith('ticker:') && nid.slice(7)) return nid.slice(7);
  if ((n?.type === 'selskap' || n?.type === 'ticker') && nid) return nid;
  return null;
}
function yearOf(row) {
  const v = (row?.år != null && row.år !== '') ? row.år : row?.ar;
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : v;
}
function isVerk(n) { return n && (n.type === 'verk' || n.type === 'anlegg'); }
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

function nodeTall(node) {
  if (node?.status === 'kontekst') return [];
  if (Array.isArray(node?.tall) && node.tall.length) return node.tall.filter((r) => r && typeof r === 'object');
  if (node && ((node.verdi != null && node.verdi !== '') || node.tekst)) return [node];
  return [];
}
function landTonn(node, edges) {
  const y0 = yearOf(node);
  if (node?.verdi != null && node.verdi !== '' && isTonn(node.enhet) && y0 != null) {
    const y = Number(y0), v = Number(node.verdi);
    if (Number.isFinite(y) && Number.isFinite(v)) return { year: y, val: v };
  }
  const list = (edges || pubKanter()).filter(isPub);
  const nid = node?.id;
  const byYear = new Map();
  for (const e of list) {
    if (e.status !== 'kilde' || e.verdi == null || e.verdi === '' || !isTonn(e.enhet)) continue;
    if (e.fra !== nid && e.til !== nid) continue;
    const y = yearOf(e);
    if (y == null) continue;
    const v = Number(e.verdi);
    if (!Number.isFinite(v)) continue;
    byYear.set(y, (byYear.get(y) || 0) + v);
  }
  if (!byYear.size) return null;
  let year = 0, val = -1;
  for (const [y, v] of byYear) {
    if (v > val || (v === val && y > year)) { val = v; year = y; }
  }
  return { year, val };
}
function landForLag(nodes, edges) {
  const lands = nodes.filter((n) => n.type === 'land');
  const measured = [], unmeasured = [];
  for (const n of lands) {
    const t = landTonn(n, edges);
    if (t) measured.push({ n, ...t });
    else unmeasured.push(n);
  }
  if (!measured.length) return { visible: [], andre: unmeasured };
  const years = new Map();
  for (const m of measured) years.set(m.year, (years.get(m.year) || 0) + 1);
  let maxn = 0, year = 0;
  for (const [y, c] of years) {
    if (c > maxn || (c === maxn && y > year)) { maxn = c; year = y; }
  }
  const ranked = measured.filter((m) => m.year === year).sort((a, b) => b.val - a.val);
  const otherYear = measured.filter((m) => m.year !== year).map((m) => m.n);
  return {
    visible: ranked.slice(0, MAX_LAND_PER_LAG).map((m) => m.n),
    andre: ranked.slice(MAX_LAND_PER_LAG).map((m) => m.n).concat(otherYear, unmeasured),
  };
}
function verkFor(companyId) {
  const linked = new Set();
  for (const e of pubKanter()) {
    if (e.fra === companyId) linked.add(e.til);
    else if (e.til === companyId) linked.add(e.fra);
  }
  let out = noder.filter((n) => isVerk(n) && linked.has(n.id));
  const focus = byId.get(companyId);
  const mat = focus?.materiale;
  if (mat) {
    const seen = new Set(out.map((n) => n.id));
    for (const n of noder) {
      if (isVerk(n) && n.materiale === mat && !seen.has(n.id)) { out.push(n); seen.add(n.id); }
    }
  }
  return out;
}
function plantLand(n) {
  if (n.land) return n.land;
  for (const e of pubKanter()) {
    const other = e.fra === n.id ? e.til : (e.til === n.id ? e.fra : null);
    const o = other && byId.get(other);
    if (o && o.type === 'land') return o.navn;
  }
  const t = n.hva_det_er || n.merknad || '';
  const m = t.match(/\bi\s+([^.,]+)/i);
  if (m) {
    const bit = m[1];
    const parts = bit.split(',').map((s) => s.trim());
    return parts[parts.length - 1];
  }
  return '';
}
function verkLabel(verks) {
  return 'Verk (' + verks.length + ')';
}
function packVisible(rawNodes, edges, focus) {
  const focusId = focus?.id;
  const fromNb = rawNodes.filter((n) => isVerk(n));
  const verks = focusId ? verkFor(focusId) : fromNb;
  let nodes = rawNodes.filter((n) => !isVerk(n));
  if (verks.length && focusId) {
    nodes.push({
      id: 'verk:' + focusId,
      type: 'verkgruppe',
      navn: verkLabel(verks),
      hva_det_er: 'Samlenode for verk og anlegg.',
      verk: verks,
      lag: 'selskap',
      status: 'kilde',
    });
    if (verkOpen) nodes = nodes.concat(verks);
  }
  const byHop = [[], [], []];
  const rest = [];
  for (const n of nodes) {
    if (n.type === 'land' && focusId) {
      const h = Math.min(hopOf(n.id, focusId), 2);
      byHop[h].push(n);
    } else rest.push(n);
  }
  nodes = rest;
  byHop.forEach((lands, hop) => {
    if (!lands.length) return;
    const { visible, andre } = landForLag(lands, edges);
    nodes.push(...visible);
    if (andre.length) {
      nodes.push({
        id: 'andre:' + hop,
        type: 'andre',
        navn: '+' + andre.length + ' andre',
        hva_det_er: 'Land utenfor de seks med mest tonn samme år, og land uten tonn.',
        medlemmer: andre,
        lag: 'råvare',
        status: 'kilde',
      });
    }
  });
  const keep = new Set(nodes.map((n) => n.id));
  const clusterId = focusId ? 'verk:' + focusId : null;
  const packedEdges = [];
  for (const e of edges) {
    const mapEnd = (id) => {
      const n = byId.get(id);
      if (isVerk(n) && clusterId) {
        if (verkOpen && keep.has(id)) return id;
        return clusterId;
      }
      if (n?.type === 'land' && !keep.has(id) && focusId) return 'andre:' + Math.min(hopOf(id, focusId), 2);
      return id;
    };
    const fra = mapEnd(e.fra), til = mapEnd(e.til);
    if (keep.has(fra) && keep.has(til) && fra !== til) packedEdges.push({ ...e, fra, til });
  }
  return { nodes, edges: packedEdges };
}
function isMekanisme(setning, url) {
  const s = String(setning || '').trim();
  const u = String(url || '').trim();
  const low = s.toLowerCase();
  return !!(s && u && low !== 'kilden beskriver ikke dette' && low !== 'mangler data');
}
function scenarioHasChip(s) {
  if ((s?.tekst || []).some((t) => isMekanisme(t.setning, t.kilde_url))) return true;
  return isMekanisme(s?.setning, s?.kilde_url);
}
function scenarioGroup(idOrName) {
  const seed = scenarioer.find((x) => x.id === idOrName) || scenarioer.find((x) => x.navn === idOrName);
  if (!seed) return [];
  return scenarioer.filter((x) => x.navn === seed.navn);
}
function fillChips() {
  const box = document.getElementById('flyt-hvis-chips') || document.querySelector('.flyt-hvis-chips');
  if (!box) return;
  box.innerHTML = '';
  const seen = new Set();
  for (const s of scenarioer) {
    if (!s.navn || seen.has(s.navn)) continue;
    const group = scenarioer.filter((x) => x.navn === s.navn);
    if (!group.some(scenarioHasChip)) continue;
    seen.add(s.navn);
    const sid = (group.find(scenarioHasChip) || s).id;
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'flyt-chip';
    b.dataset.scenario = sid;
    b.setAttribute('aria-pressed', 'false');
    b.textContent = s.navn;
    b.addEventListener('click', () => {
      if (scenario?.navn === s.navn) applyScenario(null);
      else applyScenario(sid);
    });
    box.appendChild(b);
  }
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
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    const txt = await r.text();
    if (!txt) return null;
    return JSON.parse(txt);
  } catch {
    return null;
  }
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

function isSelskap(n) { return n && canonType(n.type) === 'selskap'; }
function isVerkNode(n) { return n && (n.type === 'verk' || n.type === 'anlegg'); }
function selskaperOn(landId) {
  const out = [];
  const seen = new Set();
  const sel = pubKanter().filter((e) => e.lag === 'selskap');
  const other = (e, id) => e.fra === id ? e.til : (e.til === id ? e.fra : null);
  const plants = [];
  for (const e of sel) {
    const o = other(e, landId);
    if (!o) continue;
    const n = byId.get(o);
    if (!n) continue;
    if (isSelskap(n) && !seen.has(n.id)) {
      seen.add(n.id);
      out.push({ id: n.id, ticker: tickerOf(n), node: n, edge: e });
    } else if (isVerkNode(n)) plants.push(n.id);
  }
  for (const pid of plants) {
    for (const e of sel) {
      const o = other(e, pid);
      if (!o) continue;
      const n = byId.get(o);
      if (n && isSelskap(n) && !seen.has(n.id)) {
        seen.add(n.id);
        out.push({ id: n.id, ticker: tickerOf(n), node: n, edge: e });
      }
    }
  }
  return out;
}

function selskaperPaaVare(vareId) {
  const sel = pubKanter().filter((e) => e.lag === 'selskap');
  const other = (e, id) => e.fra === id ? e.til : (e.til === id ? e.fra : null);
  const found = new Set();
  const plants = [];
  for (const e of sel) {
    const o = other(e, vareId);
    if (!o) continue;
    const n = byId.get(o);
    if (!n) continue;
    if (isSelskap(n)) found.add(n.id);
    else if (isVerkNode(n)) plants.push(n.id);
  }
  for (const pid of plants) {
    for (const e of sel) {
      const o = other(e, pid);
      const n = o && byId.get(o);
      if (n && isSelskap(n)) found.add(n.id);
    }
    // eier via verkFor / samme materiale
    for (const n of noder) {
      if (!isSelskap(n)) continue;
      const vset = new Set(verkFor(n.id).map((v) => v.id));
      if (vset.has(pid)) found.add(n.id);
    }
  }
  return [...found];
}
function pubEdgeCount(nid) {
  return pubKanter().filter((e) => e.fra === nid || e.til === nid).length;
}
function overviewSelskaper() {
  const connected = new Set();
  for (const e of pubKanter()) { connected.add(e.fra); connected.add(e.til); }
  const sels = noder.filter((n) => isSelskap(n) && connected.has(n.id));
  sels.sort((a, b) => (pubEdgeCount(b.id) - pubEdgeCount(a.id))
    || String(tickerOf(a) || a.navn || '').localeCompare(String(tickerOf(b) || b.navn || ''), 'nb'));
  return sels;
}
function capCol(items, max, id, filter, hva) {
  const vis = items.slice(0, max);
  const rest = items.slice(max);
  if (rest.length) {
    vis.push({
      id, type: 'andre', navn: '+' + rest.length + ' andre',
      hva_det_er: hva || 'Øvrige i kolonnen.',
      medlemmer: rest, filter, lag: filter === 'selskaper' ? 'selskap' : 'land', status: 'kontekst',
    });
  }
  return vis;
}
function overviewGraph() {
  const connected = new Set();
  for (const e of pubKanter()) { connected.add(e.fra); connected.add(e.til); }
  let mats = noder.filter((n) => isVare(n) && connected.has(n.id));
  const lands = noder.filter((n) => n.type === 'land' && connected.has(n.id));
  const counts = new Map();
  const deg = new Map();
  mats = mats.map((n, i) => ({ n, i, c: selskaperPaaVare(n.id).length }))
    .sort((a, b) => (b.c - a.c) || (a.i - b.i))
    .map((x) => x.n);
  for (const n of mats) {
    counts.set(n.id, selskaperPaaVare(n.id).length);
    deg.set(n.id, pubEdgeCount(n.id));
  }
  for (const n of lands) {
    counts.set(n.id, selskaperOn(n.id).length);
    deg.set(n.id, pubEdgeCount(n.id));
  }
  const withT = lands.filter((n) => (counts.get(n.id) || 0) > 0)
    .sort((a, b) => (counts.get(b.id) - counts.get(a.id))
      || (deg.get(b.id) - deg.get(a.id))
      || String(a.navn || '').localeCompare(String(b.navn || ''), 'nb'));
  const landVis = capCol(withT, MAX_LAND_PER_LAG, 'andre:oversikt', 'land',
    'Øvrige land, inkludert land uten selskaper.');
  // 0-selskaps-land i +n andre (de som ikke er i withT)
  const visLandIds = new Set(withT.slice(0, MAX_LAND_PER_LAG).map((n) => n.id));
  const zeroLands = lands.filter((n) => !visLandIds.has(n.id) && !withT.includes(n));
  // capCol already only took withT; add zero-count lands into andre:oversikt
  const andreNode = landVis.find((n) => n.type === 'andre');
  const leftover = lands.filter((n) => !visLandIds.has(n.id));
  if (andreNode) andreNode.medlemmer = leftover;
  else if (leftover.length) {
    landVis.push({
      id: 'andre:oversikt', type: 'andre', navn: '+' + leftover.length + ' andre',
      hva_det_er: 'Øvrige land, inkludert land uten selskaper.',
      medlemmer: leftover, filter: 'land', lag: 'land', status: 'kontekst',
    });
  }
  const sels = overviewSelskaper();
  const showSels = isWide();
  const selVis = showSels ? capCol(sels, MAX_SELSKAP_OVERSIKT, 'andre:selskaper', 'selskaper',
    'Øvrige selskaper med publisert kant.') : [];
  const vareVis = capCol(mats, MAX_LAND_PER_LAG, 'andre:varer', 'varer', 'Øvrige varer.');
  const nodes = [...vareVis, ...(showSels ? selVis : []), ...landVis.filter((n) => n.type !== 'andre' || leftover.length || (n.medlemmer || []).length)];
  // drop empty andre
  const clean = nodes.filter((n) => n.type !== 'andre' || (n.medlemmer && n.medlemmer.length));
  return {
    nodes: clean, counts,
    varerN: mats.length, heading: 'Varer (' + mats.length + ')',
    landN: lands.length, landHeading: 'Land (' + lands.length + ')',
    selskaperN: sels.length, selskaperHeading: showSels ? ('Selskaper (' + sels.length + ')') : '',
    showSelskaper: showSels,
  };
}

function visibleSet(focusId) {
  if (!focusId) {
    if (oversiktPack && oversiktPack.aggregat) {
      const counts = new Map(Object.entries(oversiktPack.counts || {}).map(([k, v]) => [k, Number(v)]));
      let nodes = (oversiktPack.noder || []).slice();
      const showS = isWide();
      if (!showS) {
        nodes = nodes.filter((n) => !isSelskap(n) && n.id !== 'andre:selskaper' && n.filter !== 'selskaper');
      }
      return {
        nodes, edges: [], overview: true, counts, hidden: 0,
        heading: oversiktPack.varer_label, varerN: oversiktPack.varer_n,
        landN: oversiktPack.land_n, landHeading: oversiktPack.land_label,
        selskaperN: oversiktPack.selskaper_n, selskaperHeading: showS ? oversiktPack.selskaper_label : '',
        showSelskaper: showS,
      };
    }
    const ov = overviewGraph();
    return { nodes: ov.nodes.slice(), edges: [], overview: true, counts: ov.counts, hidden: 0, heading: ov.heading, varerN: ov.varerN, landN: ov.landN, landHeading: ov.landHeading, selskaperN: ov.selskaperN, selskaperHeading: ov.selskaperHeading, showSelskaper: ov.showSelskaper };
  }
  const t = tickerOf(byId.get(focusId)) || (byId.has(focusId) ? null : focusId);
  const focusNode = byId.get(focusId) || noder.find((n) => tickerOf(n) === focusId);
  if (!focusNode) return { nodes: [], edges: [], overview: false, hidden: 0, missing: true };
  const tk = tickerOf(focusNode);
  if (tk && !hasKildeData(tk)) {
    return { nodes: [focusNode], edges: [], overview: false, hidden: 0, missingChain: true };
  }
  const nb = neighbors(focusNode.id, 2);
  const extra = [];
  for (const e of kanter) {
    if (e.status !== 'mangler') continue;
    let other = null;
    if (e.fra === focusNode.id) other = e.til;
    else if (e.til === focusNode.id) other = e.fra;
    if (other && !nb.ids.has(other) && byId.has(other)) extra.push(byId.get(other));
  }
  const nodes = noder.filter((n) => nb.ids.has(n.id)).concat(extra);
  const packed = packVisible(nodes, nb.edges, focusNode);
  packed.nodes = capFocusSides(packed.nodes, packed.edges, focusNode);
  const hidden = Math.max(0, packed.nodes.length - MAX_NODES);
  let pnodes = packed.nodes;
  if (pnodes.length > MAX_NODES) {
    const head = pnodes.filter((n) => n.id === focusNode.id || n.type === 'verkgruppe');
    const rest = pnodes.filter((n) => n.id !== focusNode.id && n.type !== 'verkgruppe');
    pnodes = [...head, ...rest.slice(0, Math.max(0, MAX_NODES - head.length))];
  }
  const keep = new Set(pnodes.map((n) => n.id));
  const edges = packed.edges.filter((e) => keep.has(e.fra) && keep.has(e.til));
  return { nodes: pnodes, edges, overview: false, hidden, focus: focusNode };
}


function sideOf(n, focus, edges) {
  if (!n || !focus) return 'mid';
  if (n.id === focus.id || n.type === 'verkgruppe' || isVerk(n)) return 'mid';
  const toF = edges.some((e) => e.til === focus.id && e.fra === n.id);
  const fromF = edges.some((e) => e.fra === focus.id && e.til === n.id);
  if (toF && !fromF) return 'up';
  if (fromF && !toF) return 'down';
  if (n.type === 'land' || n.type === 'andre' || n.id === 'andre:0' || (n.id || '').startsWith('andre:')) return 'down';
  if (isSelskap(n) && isVare(focus)) return 'up';
  if (isVare(n) && isSelskap(focus)) return fromF || !toF ? 'down' : 'up';
  return toF ? 'up' : 'down';
}
function capFocusSides(nodes, edges, focus) {
  if (!focus) return nodes;
  const flat = [];
  for (const n of nodes) {
    if (n.type === 'andre' && Array.isArray(n.medlemmer) && n.medlemmer.length) {
      for (const m of n.medlemmer) flat.push(m);
    } else flat.push(n);
  }
  nodes = flat;
  const mid = [], up = [], down = [];
  for (const n of nodes) {
    const s = sideOf(n, focus, edges);
    if (s === 'up') up.push(n);
    else if (s === 'down') down.push(n);
    else mid.push(n);
  }
  function cap(side, key) {
    const vis = side.slice(0, MAX_LAND_PER_LAG);
    const rest = side.slice(MAX_LAND_PER_LAG);
    if (rest.length) {
      vis.push({
        id: 'andre:' + key,
        type: 'andre',
        navn: '+' + rest.length + ' andre',
        hva_det_er: 'Øvrige noder på denne siden.',
        medlemmer: rest,
        filter: isSelskap(rest[0]) ? 'selskaper' : (isVare(rest[0]) ? 'varer' : 'land'),
        lag: 'råvare',
        status: 'kontekst',
      });
    }
    return vis;
  }
  let out = cap(up, 'opp').concat(mid).concat(cap(down, 'ned'));
  if (isMobile() && out.length > 14) {
    // maks 14 etiketter ved 390: slipp verkgruppe først
    out = out.filter((n) => n.type !== 'verkgruppe' && !isVerk(n));
    if (out.length > 14) {
      const focusN = out.filter((n) => n.id === focus.id);
      const rest = out.filter((n) => n.id !== focus.id);
      out = focusN.concat(rest.slice(0, 13));
    }
  }
  return out;
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
    const isAndre = (n, f) => n.type === 'andre' && (n.filter || (n.id || '').split(':')[1]) === f;
    const mats = visu.nodes.filter((n) => isVare(n) || isAndre(n, 'varer'));
    const sels = visu.nodes.filter((n) => visu.showSelskaper && (isSelskap(n) || isAndre(n, 'selskaper')));
    const lands = visu.nodes.filter((n) => n.type === 'land' || isAndre(n, 'land') || (n.type === 'andre' && n.id === 'andre:oversikt'));
    // Zoom 16/16 øverst til venstre; hold venstre kolonne unna zoom-stacken.
    const zoomW = 120;
    const gap = 44;
    overviewPackGap = 44;
    const packFit = (col, x, startY, labH) => {
      const n = col.length;
      if (!n) return;
      const avail = Math.max(labH, H - startY - 8);
      let usedGap = gap;
      if (n > 1 && n * labH + (n - 1) * gap > avail) {
        usedGap = Math.max(4, (avail - n * labH) / (n - 1));
      }
      overviewPackGap = Math.min(overviewPackGap, usedGap);
      col.forEach((node, i) => {
        const y = startY + labH / 2 + i * (labH + usedGap);
        pos.set(node.id, { x, y, z: 0, hop: x > W / 2 ? 1 : 0, labH });
      });
    };
    const zoomEl = document.querySelector('.flyt-zoom');
    const sceneBox = el.scene.getBoundingClientRect();
    const zoomRight = zoomEl && sceneBox.width
      ? Math.max(0, zoomEl.getBoundingClientRect().right - sceneBox.left)
      : 16 + zoomW;
    const three = !!(visu.showSelskaper && isWide());
    const headY = 16 + 9;
    const colStart = 16 + 18 + 8;
    const vareH = W < 500 ? 68 : 50;
    const landH = W < 500 ? 68 : 50;
    const selH = 44;
    let xL, xM, xR;
    if (three) {
      const span = Math.max(80, W - zoomRight - 24);
      xL = zoomRight + 24 + span * 0.12;
      xM = zoomRight + 24 + span * 0.50;
      xR = zoomRight + 24 + span * 0.82;
    } else {
      const narrow = W < 500;
      xL = narrow ? zoomRight + (W - zoomRight) * 0.28 : Math.max(W * 0.32, zoomRight + 70);
      xR = narrow ? zoomRight + (W - zoomRight) * 0.78 : W * 0.72;
    }
    pos.set('__varer_h', { x: xL, y: headY, z: 0, hop: 0, heading: visu.heading || ('Varer (' + visu.varerN + ')') });
    if (three) pos.set('__selskaper_h', { x: xM, y: headY, z: 0, hop: 0, heading: visu.selskaperHeading || ('Selskaper (' + (visu.selskaperN || sels.filter(isSelskap).length) + ')') });
    pos.set('__land_h', { x: xR, y: headY, z: 0, hop: 1, heading: visu.landHeading || ('Land (' + (visu.landN != null ? visu.landN : lands.filter((n) => n.type === 'land').length) + ')') });
    packFit(mats, xL, colStart, vareH);
    if (three) packFit(sels, xM, colStart, selH);
    packFit(lands, xR, colStart, landH);
    return pos;
  }
  const focusId = visu.focus?.id || fokus;
  const focusN = visu.focus || byId.get(focusId);
  const groups = [[], [], []];
  for (const n of visu.nodes) {
    if (n.type === 'verkgruppe' || isVerk(n)) continue;
    const s = sideOf(n, focusN, visu.edges || []);
    const hop = s === 'up' ? 0 : (s === 'down' ? 2 : 1);
    groups[hop].push(n);
  }
  // Sørg for at fokus ligger i midten også om sideOf ga noe annet
  groups[0] = groups[0].filter((n) => n.id !== focusId);
  groups[2] = groups[2].filter((n) => n.id !== focusId);
  if (focusN && visu.nodes.some((n) => n.id === focusId)) {
    groups[1] = [focusN, ...groups[1].filter((n) => n.id !== focusId)];
  }
  const packFocusCol = (g, x, hop) => {
    if (!g.length) return;
    const estH = (n) => {
      const name = String(n.navn || '');
      const hasVal = !!fmtSceneVal(n);
      const lines = Math.max(1, Math.ceil(name.length / (W < 500 ? 12 : 16)));
      return Math.max(44, 8 + lines * 16 + (hasVal ? 16 : 0));
    };
    let items = g.slice();
    const startY = 8;
    const avail = Math.max(44, H - startY - 8);
    const gap0 = 8;
    const fits = (arr) => {
      const hs = arr.map(estH);
      return hs.reduce((a, b) => a + b, 0) + gap0 * Math.max(0, arr.length - 1) <= avail;
    };
    while (items.length > 1 && !fits(items)) {
      const keep = items.filter((n) => n.type !== 'andre');
      const drop = keep.pop();
      let andre = items.find((n) => n.type === 'andre') || visu.nodes.find((n) => n.type === 'andre' && (n.id === 'andre:ned' || n.id === 'andre:opp' || n.id === 'andre:' + hop));
      const rest = (andre && andre.medlemmer ? andre.medlemmer.slice() : []);
      if (drop) rest.unshift(drop);
      items = keep;
      if (rest.length) {
        if (!andre) {
          andre = {
            id: 'andre:' + (hop === 0 ? 'opp' : 'ned'),
            type: 'andre', lag: 'råvare', status: 'kontekst', filter: 'land',
            hva_det_er: 'Øvrige noder på denne siden.',
          };
          visu.nodes.push(andre);
        }
        andre.medlemmer = rest;
        andre.navn = '+' + rest.length + ' andre';
        items.push(andre);
      }
    }
    const hs = items.map(estH);
    let usedGap = gap0;
    const sumH = hs.reduce((a, b) => a + b, 0);
    if (items.length > 1 && sumH + usedGap * (items.length - 1) > avail) {
      usedGap = Math.max(4, (avail - sumH) / (items.length - 1));
    }
    let y = startY;
    items.forEach((n, i) => {
      const h = hs[i];
      pos.set(n.id, { x, y: y + h / 2, z: (hop - 1) * 20, hop });
      y += h + usedGap;
    });
  };
  groups.forEach((g, hop) => {
    const x = W * (0.18 + hop * 0.32);
    packFocusCol(g, x, hop);
  });
  const cluster = visu.nodes.find((n) => n.type === 'verkgruppe');
  const plants = visu.nodes.filter((n) => isVerk(n));
  if (cluster) {
    const nhy = pos.get(focusId) || { x: W * 0.18, y: H * 0.5 };
    const cx = nhy.x + W * 0.14;
    const cy = nhy.y;
    pos.set(cluster.id, { x: cx, y: cy, z: 0, hop: 0 });
    if (verkOpen && plants.length) {
      plants.forEach((p, i) => {
        const ang = (Math.PI / 2) * ((i + 0.5) / plants.length - 0.5);
        pos.set(p.id, { x: cx + Math.cos(ang) * (W * 0.08), y: cy + Math.sin(ang) * (H * 0.42), z: 0, hop: 0 });
      });
    }
  }
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
  const text = srcText(row);
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
  const y = yearOf(row);
  return [num, row.enhet, y].filter((x) => x != null && x !== '').join(' ');
}
function roundTonnHalfUp(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return n;
  return Math.floor(n + 0.5);
}
function tickerCountLabel(n) {
  const k = Number(n) || 0;
  return k === 1 ? '1 ticker' : `${k} tickere`;
}
function selskapCountLabel(n) {
  const k = Number(n) || 0;
  return k === 1 ? '1 selskap' : `${k} selskaper`;
}
function fmtSceneVal(row) {
  if (row.status === 'mangler' || row.verdi == null || row.verdi === '') return null;
  const v = row.verdi;
  let num;
  if (typeof v === 'number' && isTonn(row.enhet) && v > 0 && v < 1) {
    // FLAG 2: verdi lagres med desimaler; scenen viser «under 1 tonn» under 1 tonn.
    num = 'under 1';
  } else if (typeof v === 'number' && isTonn(row.enhet)) {
    num = roundTonnHalfUp(v).toLocaleString('nb-NO');
  } else if (typeof v === 'number') {
    num = v.toLocaleString('nb-NO');
  } else {
    num = String(v);
  }
  const y = yearOf(row);
  return [num, row.enhet, y].filter((x) => x != null && x !== '').join(' ');
}

function sizeScene() {
  if (!el.wrap) return;
  if (isMobile()) {
    const top = el.wrap.getBoundingClientRect().top;
    document.body.style.setProperty('--flyt-scene-top', `${top}px`);
  } else {
    document.body.style.removeProperty('--flyt-scene-top');
  }
}
function updateStatus() {
  const cov = meta.coverage;
  const k = cov && cov.k != null ? Number(cov.k) : 0;
  if (cov && cov.beregnet && cov.statuslinje && k >= 1) {
    el.status.hidden = false;
    el.status.textContent = cov.statuslinje;
  } else {
    el.status.hidden = true;
    el.status.textContent = '';
  }
}

function fillSearch() {
  el.list.innerHTML = '';
  const opts = [];
  const visible = new Set();
  for (const e of pubKanter()) { visible.add(e.fra); visible.add(e.til); }
  for (const n of noder) {
    const t = tickerOf(n);
    if (!visible.has(n.id) && n.status !== 'mangler' && !universe.includes(t)) continue;
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
  const href = tickerPageHref(ticker);
  const tickerPlain = () => {
    const s = document.createElement('span');
    s.className = 'flyt-tk-plain';
    s.textContent = ticker;
    return s;
  };
  if (!e) {
    const p = document.createElement('p');
    p.className = 'flyt-miss';
    p.textContent = 'Mangler kursdata';
    if (!href) {
      p.append(' ');
      p.appendChild(tickerPlain());
    }
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
  if (href) {
    const a = document.createElement('a');
    a.href = href;
    a.textContent = ticker;
    a.className = 'flyt-rel';
    wrap.appendChild(a);
  } else if (e) {
    wrap.appendChild(tickerPlain());
  }
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


// SPEC-tillegg: avvik >20 % mot partner gir to rader (44 px) + metodelinje 13/18.
// Scenetykkelse kommer alltid fra rapportørens tall.
function avvikInfo(r) {
  const p = r?.partner;
  if (!p || p.verdi == null || p.verdi === '' || r.verdi == null || r.verdi === '') return null;
  const a = Number(r.verdi), b = Number(p.verdi);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === 0) return null;
  const pct = Math.abs(b - a) / Math.abs(a) * 100;
  if (pct <= 20) return null;
  return { pct, partner: p };
}
function appendAvvik(container, r, node, info) {
  const wrap = document.createElement('div');
  wrap.className = 'flyt-tall-rad flyt-avvik';
  const rows = [
    [`Rapportør (${r.reporter_land || r.reporter || ''}):`, r],
    [`Partner (${info.partner.reporter_land || info.partner.land || ''}):`, { ...info.partner, enhet: info.partner.enhet || r.enhet, ar: info.partner.ar || r.ar }],
  ];
  for (const [lab, row] of rows) {
    const d = document.createElement('div');
    d.className = 'flyt-avvik-rad';
    const a = document.createElement('span'); a.textContent = lab;
    const b = document.createElement('span'); b.textContent = fmtVal(row) || 'Mangler data';
    d.append(a, b);
    wrap.appendChild(d);
  }
  const m = document.createElement('p');
  m.className = 'flyt-metode';
  m.textContent = 'Metode: ' + (r.metode || info.partner.metode || 'Mangler data');
  wrap.appendChild(m);
  wrap.appendChild(srcLine({ ...r, lag: r.lag || node.lag }));
  container.appendChild(wrap);
}

function appendTallRows(container, node) {
  if (node.status === 'kontekst') {
    const p = document.createElement('p');
    p.className = 'flyt-kontekst-tall';
    p.textContent = 'Noden har ingen egne tall.';
    container.appendChild(p);
    return;
  }
  const rows = nodeTall(node);
  if (!rows.length) {
    const p = document.createElement('p');
    p.className = 'flyt-miss';
    if (node.status === 'mangler') {
      const b = document.createElement('span');
      b.className = 'badge';
      b.textContent = 'Mangler data';
      p.appendChild(b);
      if (node.grunn) p.append(' ' + node.grunn);
    } else {
      p.textContent = 'Mangler data';
    }
    container.appendChild(p);
    if (node.kilde || node.kilde_url || node.status === 'mangler') container.appendChild(srcLine(node));
    return;
  }
  for (const r of rows) {
    const av = avvikInfo(r);
    if (av) { appendAvvik(container, r, node, av); continue; }
    const wrap = document.createElement('div');
    wrap.className = 'flyt-tall-rad';
    const p = document.createElement('p');
    p.textContent = r.tekst || fmtVal(r) || 'Mangler data';
    if (r.status === 'estimat') {
      const b = document.createElement('span');
      b.className = 'badge';
      b.textContent = ' Estimat';
      p.appendChild(b);
    }
    wrap.appendChild(p);
    wrap.appendChild(srcLine({ ...r, lag: r.lag || node.lag }));
    container.appendChild(wrap);
  }
}

function renderPanel(node, opts) {
  el.pbody.innerHTML = '';
  if (!node) { closePanel(); return; }
  el.pbody.appendChild(sec('Hva det er', node.hva_det_er || node.navn, 'hva'));
  const tall = document.createElement('div');
  appendTallRows(tall, node);
  if (node.type !== 'verkgruppe') el.pbody.appendChild(sec('Tall', tall, 'tall'));
  const flows = pubKanter().filter((x) => x.fra === node.id || x.til === node.id);
  if (node.status === 'kontekst' && flows.length) {
    const box = document.createElement('div');
    for (const e of flows) {
      const row = document.createElement('div');
      row.className = 'flyt-strom-rad';
      const other = byId.get(e.fra === node.id ? e.til : e.fra);
      const p = document.createElement('p');
      const ev = fmtVal(e);
      p.textContent = `${other?.navn || (e.fra === node.id ? e.til : e.fra)}: ${ev || 'Mangler data'}`;
      if (e.status === 'estimat') p.append(' (Estimat' + (e.metode ? ': ' + e.metode : '') + ')');
      row.appendChild(p);
      row.appendChild(srcLine(e));
      box.appendChild(row);
    }
    el.pbody.appendChild(sec('Strømmer koblet hit', box, 'strommer'));
  }
  if (node.type === 'verkgruppe') {
    const box = document.createElement('div');
    for (const v of node.verk || []) {
      const row = document.createElement('div');
      row.className = 'flyt-verk-rad';
      const a = document.createElement('span'); a.textContent = v.navn;
      const b = document.createElement('span'); b.textContent = plantLand(v) || v.land || '';
      const c = document.createElement('span'); c.textContent = fmtVal(v) || 'Mangler data';
      row.append(a, b, c);
      row.tabIndex = 0;
      row.addEventListener('click', () => { if (!verkOpen) { verkOpen = true; redraw(); } renderPanel(v); });
      box.appendChild(row);
    }
    el.pbody.appendChild(sec('Verk og anlegg', box, 'verk'));
  }
  if (node.type === 'andre') {
    const box = document.createElement('div');
    for (const m of node.medlemmer || []) {
      const row = document.createElement('div');
      row.className = 'flyt-verk-rad';
      const a = document.createElement('span'); a.textContent = m.navn;
      const c = document.createElement('span');
      c.textContent = landTonn(m) ? fmtVal(m) : 'uten tonn';
      row.append(a, c);
      row.tabIndex = 0;
      row.addEventListener('click', () => { go(m.id, true); });
      box.appendChild(row);
    }
    el.pbody.appendChild(sec('Andre land', box, 'andre'));
  }
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
  if (node.type && node.type !== 'selskap' && !isVare(node)) {
    const box = document.createElement('div');
    const isLand = node.type === 'land';
    const list = isLand ? selskaperOn(node.id) : tickersOn(node.id);
    if (isLand) {
      const cap = document.createElement('p');
      cap.textContent = selskapCountLabel(list.length);
      box.appendChild(cap);
    }
    if (!list.length && !isLand) {
      const p = document.createElement('p');
      p.className = 'flyt-miss';
      p.textContent = 'Mangler data';
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
  const shouldOpen = opts && Object.prototype.hasOwnProperty.call(opts, 'open') ? opts.open : true;
  if (shouldOpen) openPanel();
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
  for (const n of noder) {
    if (n.type === 'verk' && path.has(n.id)) {
      const cid = (n.id && path.has(id) ? 'verk:' + id : null);
      if (cid) path.add(cid);
      // also cluster for the linked company
      for (const e of pubKanter()) {
        if (e.fra === n.id) path.add('verk:' + e.til);
        if (e.til === n.id) path.add('verk:' + e.fra);
      }
    }
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


function boxesOverlap(a, b, gap) {
  return !(a.right + gap <= b.left || b.right + gap <= a.left || a.bottom + gap <= b.top || b.bottom + gap <= a.top);
}
function resolveOverlaps(visu) {
  const parent = el.labels.getBoundingClientRect();
  if (!parent.width || !parent.height) return;
  const labs = [...el.labels.querySelectorAll('.flyt-lab')];
  const heads = [...el.labels.querySelectorAll('.flyt-col-h')];
  const items = [...heads, ...labs];
  if (items.length < 2) return;
  const toBox = (d) => d.getBoundingClientRect();
  const focusId = visu.focus?.id || fokus;
  const hydro = labs.find((d) => d.dataset.id === focusId);
  const verk = labs.find((d) => (d.dataset.id || '').startsWith('verk:'));
  if (hydro && verk) {
    const a = toBox(hydro), b = toBox(verk);
    if (boxesOverlap(a, b, 4)) {
      const dx = (a.right + 8) - b.left;
      const cx = (b.left - parent.left) + b.width / 2 + Math.max(dx, 0);
      verk.style.left = (Math.min(parent.width - 8, cx) / parent.width * 100) + '%';
    }
  }
  const minGap = visu.overview ? overviewPackGap : 4;
  const isHead = (d) => d.classList.contains('flyt-col-h');
  const gapAB = (a, b) => (isHead(a) || isHead(b) ? 8 : minGap);
  const mid = parent.left + parent.width / 2;
  function colsByX(list) {
    const rows = list.map((d) => ({ d, x: toBox(d).left + toBox(d).width / 2 }));
    rows.sort((a, b) => a.x - b.x);
    const out = [];
    const thresh = 80;
    for (const r of rows) {
      const col = out.find((c) => Math.abs((c.reduce((s, i) => s + i.x, 0) / c.length) - r.x) < thresh);
      if (col) col.push(r);
      else out.push([r]);
    }
    return out.map((c) => c.map((i) => i.d));
  }
  const cols = visu.overview ? colsByX(items) : [
    items.filter((d) => toBox(d).left + toBox(d).width / 2 < mid),
    items.filter((d) => toBox(d).left + toBox(d).width / 2 >= mid),
  ];
  for (const col of cols) {
    col.sort((a, b) => toBox(a).top - toBox(b).top);
    for (let i = 1; i < col.length; i++) {
      const prev = toBox(col[i - 1]);
      const cur = toBox(col[i]);
      const needTop = prev.bottom + gapAB(col[i - 1], col[i]);
      if (cur.top < needTop - 0.5) {
        const dy = needTop - cur.top;
        const y = (cur.top - parent.top) + dy + cur.height / 2;
        col[i].style.top = (Math.min(parent.height - 8, Math.max(8, y)) / parent.height * 100) + '%';
      }
    }
  }
  if (visu.overview) {
    // Hold kolonne-x fast (EU-27 og øvrige land samme x). Bare vertikal justering.
    let oGuard = 0;
    while (oGuard++ < 10) {
      let moved = false;
      const boxes = items.map((d) => ({ d, b: toBox(d) }));
      for (let i = 0; i < boxes.length; i++) {
        for (let j = i + 1; j < boxes.length; j++) {
          const A = boxes[i], B = boxes[j];
          const g = gapAB(A.d, B.d);
          if (!boxesOverlap(A.b, B.b, 0) && !boxesOverlap(A.b, B.b, g)) continue;
          const lower = A.b.top >= B.b.top ? A : B;
          const upper = lower === A ? B : A;
          const dy = (upper.b.bottom + gapAB(upper.d, lower.d)) - lower.b.top;
          if (dy > 0) {
            const y = (lower.b.top - parent.top) + dy + lower.b.height / 2;
            lower.d.style.top = (Math.min(parent.height - 8, Math.max(8, y)) / parent.height * 100) + '%';
            moved = true;
          }
        }
      }
      if (!moved) break;
    }
    return;
  }
  let guard = 0;
  while (guard++ < 10) {
    let moved = false;
    const boxes = items.map((d) => ({ d, b: toBox(d) }));
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const A = boxes[i], B = boxes[j];
        if (!boxesOverlap(A.b, B.b, 0) && !boxesOverlap(A.b, B.b, minGap)) continue;
        if (boxesOverlap(A.b, B.b, 0)) {
          const right = A.b.left >= B.b.left ? A : B;
          const left = right === A ? B : A;
          const dx = (left.b.right + minGap) - right.b.left;
          if (dx > 0 && right.b.right + dx <= parent.right - 4) {
            const cx = (right.b.left - parent.left) + right.b.width / 2 + dx;
            right.d.style.left = (cx / parent.width * 100) + '%';
            moved = true;
          } else {
            const lower = A.b.top >= B.b.top ? A : B;
            const upper = lower === A ? B : A;
            const dy = (upper.b.bottom + minGap) - lower.b.top;
            if (dy > 0) {
              const y = (lower.b.top - parent.top) + dy + lower.b.height / 2;
              lower.d.style.top = (Math.min(parent.height - 8, y) / parent.height * 100) + '%';
              moved = true;
            }
          }
        } else if (boxesOverlap(A.b, B.b, minGap)) {
          const lower = A.b.top >= B.b.top ? A : B;
          const upper = lower === A ? B : A;
          const dy = (upper.b.bottom + minGap) - lower.b.top;
          if (dy > 0 && lower.b.bottom + dy <= parent.bottom - 4) {
            const y = (lower.b.top - parent.top) + dy + lower.b.height / 2;
            lower.d.style.top = (y / parent.height * 100) + '%';
            moved = true;
          }
        }
      }
    }
    if (!moved) break;
  }
}

function andreFilter(n) {
  if (!n || n.type !== 'andre') return null;
  if (n.filter) return n.filter;
  if (n.id === 'andre:oversikt') return 'land';
  if (n.id === 'andre:selskaper') return 'selskaper';
  if (n.id === 'andre:varer') return 'varer';
  return 'land';
}
function onAndreOrNode(n) {
  if (n && n.type === 'andre') {
    listFilter = andreFilter(n);
    showList(true);
    return;
  }
  onNode(n.id);
}
function fillLabel(d, n, visu, counts) {
  if (visu.overview && isSelskap(n)) {
    d.classList.add('selskap-rad');
    const tk = document.createElement('span');
    tk.className = 'n';
    tk.textContent = tickerOf(n) || n.navn || '';
    d.appendChild(tk);
    const nm = tickerOf(n) && n.navn && n.navn !== tickerOf(n) ? n.navn : '';
    if (nm) {
      const vv = document.createElement('span');
      vv.className = 'v';
      vv.textContent = nm;
      d.appendChild(vv);
    }
    return;
  }
  const nm = document.createElement('span');
  nm.className = 'n';
  nm.textContent = n.navn;
  d.appendChild(nm);
  const vv = document.createElement('span');
  vv.className = 'v';
  if (visu.overview) {
    if (n.type === 'land' && counts.has(n.id)) vv.textContent = selskapCountLabel(counts.get(n.id));
  } else {
    const fv = fmtSceneVal(n);
    vv.textContent = fv || (n.år ? String(n.år) : '');
  }
  if (vv.textContent) d.appendChild(vv);
  if (n.status === 'estimat') {
    const b = document.createElement('span'); b.className = 'badge'; b.textContent = 'Estimat'; d.appendChild(b);
  }
  if (n.status === 'mangler') {
    const b = document.createElement('span'); b.className = 'badge'; b.textContent = 'Mangler data'; d.appendChild(b);
  }
}

function placeOverviewHeading(pos) {
  for (const key of ['__varer_h', '__selskaper_h', '__land_h']) {
    const head = pos.get(key);
    if (!head || !head.heading) continue;
    const h = document.createElement('div');
    h.className = 'flyt-col-h';
    h.dataset.id = key;
    h.textContent = head.heading;
    h.style.left = (head.x / (el.scene.clientWidth) * 100) + '%';
    h.style.top = (head.y / (el.scene.clientHeight) * 100) + '%';
    el.labels.appendChild(h);
  }
}

function placeLabels(visu, pos, hitN) {
  el.labels.innerHTML = '';
  placeOverviewHeading(pos);
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
    fillLabel(d, n, visu, counts);
    d.addEventListener('click', (ev) => { ev.stopPropagation(); onAndreOrNode(n); });
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
  resolveOverlaps(visu);
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
  placeOverviewHeading(pos);
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
    fillLabel(d, n, visu, counts);
    d.addEventListener('click', (ev) => { ev.stopPropagation(); onAndreOrNode(n); });
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
  resolveOverlaps(visu);
}

function want3D() {
  return is3d && webgl && mode === 'kart' && (el.scene.clientWidth >= 700 || matchMedia('(min-width:901px)').matches);
}

function redraw() {
  sizeScene();
  vis = visibleSet(fokus);
  const pos = layout(vis);
  if (mode === 'liste') {
    el.wrap.hidden = false;
    // keep scene but list is shown
  }
  if (mode === 'kart') {
    el.listView.hidden = true;
    el.wrap.style.display = '';
    // Oversikten er to faste kolonner; 3D-projeksjon med pitch forskyver x/y og bryter R4.
    if (want3D() && !vis.overview) draw3D(vis, pos);
    else {
      if (three) { three.renderer.dispose(); three = null; }
      draw2D(vis, pos);
    }
  }
  if (vis.missingChain && vis.focus) renderPanel(vis.focus);
}

function showList(force) {
  if (force) { mode = 'liste'; syncToggle(); return; }
  if (three) { try { three.renderer.dispose(); } catch (e) {} three = null; el.scene.innerHTML = ''; }
  el.listView.hidden = false;
  el.wrap.style.display = 'none';
  closePanel();
  const names = (gicsNames && gicsNames.length) ? gicsNames : ['Energi','Råvarer','Industri','Syklisk forbruk','Defensivt forbruk','Helse','Finans','Teknologi','Kommunikasjon','Forsyning','Eiendom','Ukjent sektor'];
  el.listView.innerHTML = '';
  const filt = listFilter;
  function addRow(parent, opts) {
    const clickable = !!opts.clickable;
    const a = document.createElement(clickable ? 'a' : 'div');
    a.className = 'flyt-list-rad' + (opts.miss ? ' miss' : '');
    if (clickable) a.href = `flyt.html?fokus=${encodeURIComponent(opts.fokus)}`;
    const tk = document.createElement('span'); tk.className = 'tk'; tk.textContent = opts.ticker || '';
    const nm = document.createElement('span'); nm.className = 'nm'; nm.textContent = opts.navn || '';
    a.appendChild(tk); a.appendChild(nm);
    if (opts.miss) {
      const m = document.createElement('span'); m.className = 'miss-lab'; m.textContent = 'Mangler data'; a.appendChild(m);
    }
    if (clickable) {
      a.addEventListener('click', (ev) => {
        ev.preventDefault();
        listFilter = null;
        mode = 'kart';
        syncToggle();
        go(opts.fokus, true);
      });
    }
    parent.appendChild(a);
  }
  if (filt === 'land' || filt === 'varer' || filt === 'selskaper') {
    const h = document.createElement('h2');
    h.textContent = filt === 'land' ? 'Land' : (filt === 'varer' ? 'Varer' : 'Selskaper');
    el.listView.appendChild(h);
    let rows = [];
    if (filt === 'selskaper') {
      const fromOv = (oversiktPack && oversiktPack.selskaper) || overviewSelskaper().map((n) => ({ id: n.id, navn: n.navn, ticker: tickerOf(n) }));
      rows = fromOv;
    } else if (filt === 'varer') {
      rows = (vis.nodes || []).filter((n) => isVare(n)).map((n) => ({ id: n.id, navn: n.navn }));
      const andre = (vis.nodes || []).find((n) => n.id === 'andre:varer');
      if (andre) rows = rows.concat(andre.medlemmer || []);
      if (oversiktPack && oversiktPack.noder) {
        const seen = new Set(rows.map((r) => r.id));
        for (const n of oversiktPack.noder) {
          if (isVare(n) && !seen.has(n.id)) { rows.push(n); seen.add(n.id); }
        }
      }
    } else {
      const andre = (vis.nodes || []).find((n) => n.id === 'andre:oversikt');
      const visL = (vis.nodes || []).filter((n) => n.type === 'land');
      rows = visL.map((n) => ({ id: n.id, navn: n.navn })).concat(andre && andre.medlemmer ? andre.medlemmer : []);
    }
    const det = document.createElement('details');
    det.open = true;
    const sum = document.createElement('summary');
    sum.textContent = h.textContent + ' (' + rows.length + ')';
    det.appendChild(sum);
    for (const r of rows) {
      addRow(det, { ticker: r.ticker || '', navn: r.navn || r.id, fokus: r.ticker || r.id, clickable: true, miss: false });
    }
    el.listView.appendChild(det);
    return;
  }
  // Standard Liste: univers-tickere gruppert etter GICS. Uten publisert kant: grå, nederst, Mangler data.
  const items = (listIndex && listIndex.length) ? listIndex.slice() : (
    (meta.universe || []).map((t) => ({ ticker: t, navn: t, id: t, sektor: 'Ukjent sektor', publisert: hasPublished(t) }))
  );
  const buckets = {};
  for (const name of names) buckets[name] = [];
  if (!buckets['Ukjent sektor']) buckets['Ukjent sektor'] = [];
  for (const it of items) {
    let s = it.sektor || 'Ukjent sektor';
    if (!buckets[s]) s = 'Ukjent sektor';
    buckets[s].push(it);
  }
  for (const name of names) {
    const rows = buckets[name] || [];
    if (!rows.length) continue;
    const ok = rows.filter((r) => r.publisert);
    const miss = rows.filter((r) => !r.publisert);
    ok.sort((a, b) => String(a.ticker).localeCompare(String(b.ticker), 'nb'));
    miss.sort((a, b) => String(a.ticker).localeCompare(String(b.ticker), 'nb'));
    const det = document.createElement('details');
    det.open = true;
    const sum = document.createElement('summary');
    sum.textContent = name;
    det.appendChild(sum);
    for (const r of ok.concat(miss)) {
      addRow(det, {
        ticker: r.ticker, navn: r.navn && r.navn !== r.ticker ? r.navn : '',
        fokus: r.id || r.ticker, clickable: !!r.publisert, miss: !r.publisert,
      });
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
  const syn = (vis.nodes || []).find((x) => x.id === id);
  if (syn && syn.type === 'verkgruppe') {
    verkOpen = !verkOpen;
    if (crumb[crumb.length - 1] !== id) crumb.push(id);
    renderCrumb();
    redraw();
    renderPanel(syn);
    return;
  }
  if (syn && syn.type === 'andre') {
    listFilter = andreFilter(syn);
    showList(true);
    return;
  }
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
  const run = () => goAfterLoad(id, push, fromUrl);
  if (aggregatOnly) { loadFokusPack(id).then(run); return; }
  run();
}
function goAfterLoad(id, push, fromUrl) {
  const resolved = resolveFokus(id);
  const node = byId.get(resolved) || noder.find((n) => tickerOf(n) === resolved);
  fokus = node ? node.id : resolved;
  if (!fromUrl) setFokusUrl(node ? (tickerOf(node) || node.id) : resolved, push);
  const open = !(fromUrl && isMobile());
  if (node) {
    if (!crumb.length || crumb[crumb.length - 1] !== node.id) crumb = [node.id];
    renderCrumb();
    markPath(node.id);
    renderPanel(node, { open });
  } else {
    crumb = [];
    renderCrumb();
    dimExcept = null;
    path = new Set();
    // unknown ticker: synthetic missing company node
    const fake = { id: resolved, navn: resolved, type: 'selskap', ticker: resolved, lag: 'selskap', status: 'mangler', hva_det_er: 'Selskap i universet', grunn: MISS_CHAIN };
    vis = { nodes: [fake], edges: [], overview: false, hidden: 0, missingChain: true, focus: fake };
    renderPanel(fake, { open });
  }
  redraw();
}

function resetView() {
  zoom = start.zoom;
  yaw = start.yaw;
  pitch = start.pitch;
  scenario = null;
  verkOpen = false;
  document.querySelectorAll('.flyt-chip').forEach((b) => b.setAttribute('aria-pressed', 'false'));
  dimExcept = null;
  path = new Set();
  const initial = start.fokus;
  if (initial) {
    go(initial, false, true);
    closePanel();
  } else {
    crumb = [];
    fokus = null;
    setFokusUrl(null, false);
    closePanel();
    renderCrumb();
    redraw();
  }
}

function applyScenario(id) {
  const group = id ? scenarioGroup(id) : [];
  const sourced = group.filter(scenarioHasChip);
  const s = sourced[0] || null;
  scenario = s ? { ...s, navn: s.navn, id: s.id, noder: group.flatMap((x) => x.berorte_noder || x.noder || []), kanter: group.flatMap((x) => x.berorte_kanter || x.kanter || []) } : null;
  document.querySelectorAll('.flyt-chip').forEach((b) => {
    const g = scenarioGroup(b.dataset.scenario);
    const on = !!(s && g.some((x) => x.navn === s.navn));
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  const box = el.hvisTekst;
  box.innerHTML = '';
  const tallBox = document.getElementById('flyt-hvis-tall');
  if (tallBox) tallBox.innerHTML = '';
  if (s) {
    const sentences = [];
    for (const row of group) {
      if (Array.isArray(row.tekst)) {
        for (const trow of row.tekst) {
          if (isMekanisme(trow.setning, trow.kilde_url)) sentences.push({ ...trow });
        }
      } else if (isMekanisme(row.setning, row.kilde_url)) {
        sentences.push({ setning: row.setning, kilde_url: row.kilde_url, side: row.side, kilde: row.kilde, år: row.år, ar: row.ar, lag: row.lag });
      }
    }
    for (const trow of sentences) {
      const p = document.createElement('p');
      p.className = 'flyt-hvis-s';
      p.textContent = trow.setning + ' ';
      if (trow.kilde_url) {
        const a = document.createElement('a');
        a.href = trow.kilde_url;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = kildeKort(trow);
        p.appendChild(a);
      }
      box.appendChild(p);
    }
    if (tallBox) {
      const tallRows = [];
      let hasEmpty = false;
      let hasMangler = false;
      for (const row of group) {
        if (Array.isArray(row.tall) && row.tall.length) {
          for (const r of row.tall) tallRows.push(r);
        }
        const st = String(row.setning || '').trim();
        const low = st.toLowerCase();
        if (low === 'mangler data') {
          if (!hasMangler) {
            tallRows.push({ tekst: 'Mangler data', status: 'mangler', kilde: row.kilde, kilde_url: row.kilde_url, side: row.side });
            hasMangler = true;
          }
        } else if (low === 'kilden beskriver ikke dette') {
          hasEmpty = true;
        }
      }
      if (hasEmpty) tallRows.push({ tekst: EMPTY });
      if (!tallRows.length) {
        const p = document.createElement('p');
        p.className = 'flyt-hvis-tall-rad flyt-miss';
        p.textContent = EMPTY;
        tallBox.appendChild(p);
      } else {
        for (const r of tallRows) {
          const p = document.createElement('p');
          p.className = 'flyt-hvis-tall-rad';
          if (r.status === 'mangler' || String(r.tekst || '').toLowerCase() === 'mangler data') {
            const b = document.createElement('span');
            b.className = 'badge';
            b.textContent = 'Mangler data';
            p.appendChild(b);
          } else {
            p.textContent = r.tekst || r.setning || '';
          }
          if (r.kilde_url || r.kilde) {
            const a = document.createElement('a');
            if (r.kilde_url) { a.href = r.kilde_url; a.target = '_blank'; a.rel = 'noopener'; }
            a.textContent = ' ' + kildeKort(r);
            p.appendChild(a);
          }
          tallBox.appendChild(p);
        }
      }
    }
  }
  redraw();
}

function bind() {
  el.kart.addEventListener('click', () => { if (!webgl && !hasWebGL()) { mode = 'liste'; } else mode = 'kart'; syncToggle(); });
  el.liste.addEventListener('click', () => { listFilter = null; mode = 'liste'; syncToggle(); });
  el.hvis.addEventListener('click', () => {
    const on = el.hvisBox.hidden;
    el.hvisBox.hidden = !on;
    el.hvis.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (el.chips) el.chips.hidden = !on;
    if (on && isMobile()) closePanel();
    sizeScene();
    if (mode === 'kart') redraw();
  });
  window.addEventListener('resize', () => { sizeScene(); if (mode === 'kart') redraw(); });
  el.pclose.addEventListener('click', closePanel);
  el.zin.addEventListener('click', () => { zoom = Math.min(ZOOM_MAX, zoom + 0.2); redraw(); });
  el.zout.addEventListener('click', () => { zoom = Math.max(ZOOM_MIN, zoom - 0.2); redraw(); });
  el.reset.addEventListener('click', resetView);
  el.q.addEventListener('change', () => { const v = el.q.value.trim(); if (v) go(v, true); });
  el.q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const v = el.q.value.trim(); if (v) go(v, true); } });
  // bunnark: 44 px-håndtak, 90 % nås ved drag eller trykk
  function setSheet(pct) {
    if (pct >= 90) { el.panel.classList.add('sheet-90'); el.panel.style.height = '90vh'; }
    else { el.panel.classList.remove('sheet-90'); el.panel.style.height = '50vh'; }
  }
  let startY = null, startH = null, dragged = false;
  const handle = el.handle || el.panel;
  handle.addEventListener('pointerdown', (e) => {
    if (!isMobile() || el.panel.hidden) return;
    startY = e.clientY;
    startH = el.panel.getBoundingClientRect().height;
    dragged = false;
    handle.setPointerCapture(e.pointerId);
  });
  handle.addEventListener('pointermove', (e) => {
    if (startY == null) return;
    const dy = startY - e.clientY;
    if (Math.abs(dy) > 6) dragged = true;
    const vh = window.innerHeight;
    const h = Math.max(0.5 * vh, Math.min(0.9 * vh, startH + dy));
    el.panel.style.height = h + 'px';
    if (h >= 0.89 * vh) el.panel.classList.add('sheet-90');
    else el.panel.classList.remove('sheet-90');
  });
  handle.addEventListener('pointerup', () => {
    if (startY == null) return;
    const vh = window.innerHeight;
    const h = el.panel.getBoundingClientRect().height;
    const mid = (0.5 * vh + 0.9 * vh) / 2;
    if (dragged) setSheet(h >= mid ? 90 : 50);
    else setSheet(el.panel.classList.contains('sheet-90') && h >= mid ? 50 : 90);
    startY = startH = null;
    dragged = false;
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

function fokusSlug(id) {
  return String(id || '').replace(/[:/\\]/g, '-') + '.json';
}
async function loadFokusPack(id) {
  if (!id) return;
  const resolved = id;
  const rel = (fokusFiler && (fokusFiler[resolved] || fokusFiler[resolveFokus(resolved)])) || ('fokus/' + fokusSlug(resolveFokus(resolved) || resolved));
  const pack = await loadJson(`${DATA_BASE}/${rel}`);
  if (!pack) return;
  const nn = arr(pack, 'noder', 'nodes');
  const kk = arr(pack, 'kanter', 'edges');
  for (const n of nn) {
    if (!n || !n.id) continue;
    const prev = byId.get(n.id);
    if (!prev) noder.push(n);
    byId.set(n.id, n);
  }
  const have = new Set(kanter.map((e) => e.id || (e.fra + '>' + e.til)));
  for (const e of kk) {
    const k = e.id || (e.fra + '>' + e.til);
    if (!have.has(k)) { kanter.push(e); have.add(k); }
  }
}
async function init() {
  webgl = hasWebGL();
  is3d = webgl && matchMedia('(min-width:901px)').matches;
  const ov = await loadJson(`${DATA_BASE}/oversikt.json`);
  const D = await loadJson(KURS_URL);
  let S = await loadJson(`${DATA_BASE}/scenarios.json`);
  if (!S) S = await loadJson(`${DATA_BASE}/scenarioer.json`);
  if (ov && ov.aggregat) {
    aggregatOnly = true;
    oversiktPack = ov;
    const graf = ov.graf || ov;
    noder = arr(graf, 'noder', 'nodes');
    kanter = arr(graf, 'kanter', 'edges');
    // scene uses packed oversiktPack.noder; noder/kanter er publisert graf for tellinger
    listIndex = ov.liste || [];
    fokusFiler = ov.fokus_filer || {};
    gicsNames = ov.gics || [];
  } else {
    const [N, K] = await Promise.all([
      loadJson(`${DATA_BASE}/noder.json`),
      loadJson(`${DATA_BASE}/kanter.json`),
    ]);
    noder = arr(N, 'noder', 'nodes');
    kanter = arr(K, 'kanter', 'edges');
  }
  scenarioer = arr(S, 'scenarioer', 'scenarios');
  byId = new Map(noder.map((n) => [n.id, n]));
  if (D && Array.isArray(D.tickers)) {
    for (const e of D.tickers) kurs[e.ticker] = e;
  }
  universe = meta.universe || [];
  updateStatus();
  fillSearch();
  fillChips();
  bind();
  const qf = parseFokus();
  start = { zoom: 1, yaw: 0, pitch: is3d ? Math.PI / 18 : 0, fokus: qf ? resolveFokus(qf) : null };
  pitch = start.pitch;
  syncToggle();
  sizeScene();
  if (qf) go(qf, false, true);
  else redraw();
}

window.__flyt = { onNode, applyScenario, resetView, fillChips, selskaperOn, tickersOn, selskapCountLabel, tickerCountLabel,
  get vis() { return vis; }, get verkOpen() { return verkOpen; } };
init().catch((err) => {
  el.status.textContent = 'Kunne ikke laste flyt-data.';
  console.error(err);
});
