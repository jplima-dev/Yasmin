/* InkSheet enhance.js — grade virtual, seleção, teclado, preencher, colar. Carregar DEPOIS de engine.js. */
(() => {
const { MAXR, MAXC, ERRS, shiftFormula, parseNum } = InkEngine;
const RH = 24, CW = 96, HW = 50, HH = 26;
const css = document.createElement('style');
css.textContent = `.sheet-table td.cell.frz{position:sticky}.sheet-table td.cell.frz:not(.range-selected){background:var(--surface)}.sheet-table{table-layout:fixed}.sheet-table td.cell{height:${RH}px;max-height:${RH}px;overflow:hidden;white-space:nowrap;position:relative;box-sizing:border-box}
.sheet-table th.row-header{height:${RH}px;box-sizing:border-box}.sheet-table thead th{height:${HH}px;box-sizing:border-box}.sheet-table .hsp,.sheet-table .vspacer td{padding:0;border:0}
.sheet-table td.err{color:#b42318}.sheet-table th.hdr-on{background:var(--selected,#dff3ee)}.sheet-table td.fill-preview{outline:1px dashed var(--primary,#0f766e);outline-offset:-1px}
.fill-handle{position:absolute;right:-4px;bottom:-4px;width:8px;height:8px;background:var(--primary,#0f766e);border:1px solid #fff;cursor:crosshair;z-index:5}`;
document.head.append(css);

window.InkHooks = {};
/* ---- linhas/colunas ocultas (manuais ou por filtro): a grade trabalha em posições "visuais" ---- */
let hv = 0; const hidCache = new WeakMap();
function hiddenInfo(s) {
  let h = hidCache.get(s); if (h && h.v === hv) return h;
  const rows = new Set(s.hidR || []), cols = new Set(s.hidC || []);
  if (s.filters?.length) { const u = usedRange(s); for (const f of s.filters) for (let r = f.h + 1; r <= u.r2; r++) { const d = String(cellDisplay(s, addr(r, f.c))).toLowerCase(); if (!rows.has(r) && (f.vals ? !f.vals.includes(d) : d !== String(f.val).toLowerCase())) rows.add(r); } }
  h = { v: hv, rows, cols, R: [...rows].sort((a, b) => a - b), C: [...cols].sort((a, b) => a - b) }; hidCache.set(s, h); return h;
}
window.InkHidden = { info: hiddenInfo };
const nVis = s => MAXR - hiddenInfo(s).R.length;
function vrow(s, r) { const R = hiddenInfo(s).R; let lo = 0, hi = R.length; while (lo < hi) { const m = (lo + hi) >> 1; if (R[m] < r) lo = m + 1; else hi = m; } return r - lo; }
function rowOfV(s, v) { let r = v; for (const h of hiddenInfo(s).R) { if (h <= r) r++; else break; } return r; }
const cw = (s, c) => s.colWidths[c] || CW;
function colLeft(s, c) { let x = c * CW; for (const k in s.colWidths) if (+k < c) x += s.colWidths[k] - CW; for (const k of hiddenInfo(s).C) if (k < c) x -= cw(s, k); return x; }
function colAtX(s, x) { let c = Math.max(0, Math.min(MAXC - 1, Math.floor(x / CW))); while (c > 0 && colLeft(s, c) > x) c--; while (c < MAXC - 1 && colLeft(s, c + 1) <= x) c++; return c; }
const isFull = () => selection.end.r >= MAXR - 1 || selection.end.c >= MAXC - 1;
const act = () => isFull() ? { r: selection.start.r, c: selection.start.c } : selection.end;

/* ---- seleção "inteligente": ranges enormes são limitados à área usada para operações ---- */
window.selectedAddr = () => { const p = act(); return addr(p.r, p.c); };
window.normalizeRange = () => {
  const a = selection.start, b = selection.end;
  let r1 = Math.min(a.r, b.r), r2 = Math.max(a.r, b.r), c1 = Math.min(a.c, b.c), c2 = Math.max(a.c, b.c);
  if ((r2 - r1 + 1) * (c2 - c1 + 1) > 20000) { const u = usedRange(activeSheet()); r2 = Math.max(r1, Math.min(r2, u.r2)); c2 = Math.max(c1, Math.min(c2, u.c2)); }
  return { r1, r2, c1, c2 };
};

/* ---- renderização virtual: só a janela visível existe no DOM ---- */
let last = { r0: 0, r1: -1, c0: 0, c1: -1 };
function vis() {
  const s = activeSheet(), z = zoom, t = viewport.scrollTop / z, l = viewport.scrollLeft / z;
  return { r0: Math.max(0, Math.floor(t / RH)), r1: Math.min(nVis(s) - 1, Math.ceil((t + viewport.clientHeight / z) / RH)), c0: colAtX(s, l), c1: colAtX(s, l + viewport.clientWidth / z) };
}
const needDraw = () => { const s = activeSheet(), v = vis(), k = frozenRows(s).length, FC = s.frzC || 0; return (v.r0 < last.r0 + 4 && last.r0 > k) || (v.r1 > last.r1 - 4 && last.r1 < nVis(s) - 1) || (v.c0 < last.c0 + 1 && last.c0 > FC) || (v.c1 > last.c1 - 1 && last.c1 < MAXC - 1); };
const el = (t, cls) => { const x = document.createElement(t); if (cls) x.className = cls; return x; };
function frozenRows(s) { const H = hiddenInfo(s), out = []; for (let r = 0; r < (s.frzR || 0) && r < 500; r++) if (!H.rows.has(r)) out.push(r); return out; }
function draw() {
  if (!state) return;
  const s = activeSheet(); s.rows = MAXR; s.cols = MAXC; InkHooks.begin?.();
  const H = hiddenInfo(s), nV = nVis(s), fr = frozenRows(s), k = fr.length, FC = Math.min(s.frzC || 0, 200), v = vis();
  const r0 = Math.max(k, v.r0 - 12), r1 = Math.min(nV - 1, v.r1 + 12), c0 = Math.max(FC, v.c0 - 4), c1 = Math.min(MAXC - 1, Math.max(c0, v.c1 + 4)); // r0/r1 em posições visuais
  last = { r0, r1, c0, c1 };
  const fz = [], wn = []; for (let c = 0; c < FC; c++) if (!H.cols.has(c)) fz.push(c); for (let c = c0; c <= c1; c++) if (!H.cols.has(c)) wn.push(c);
  const fcols = new Set((s.filters || []).map(f => f.c)), lw = colLeft(s, c0) - colLeft(s, FC), total = colLeft(s, MAXC), rw = total - colLeft(s, c1 + 1), n = fz.length + wn.length + 3 + (lw ? 1 : 0) + (rw ? 1 : 0);
  const fl = []; let x = HW; for (const c of fz) { fl.push(x); x += cw(s, c); }
  const cg = el('colgroup'), mk = w => { const c = el('col'); c.style.width = w + 'px'; cg.append(c); };
  mk(HW); fz.forEach(c => mk(cw(s, c))); if (lw) mk(lw); wn.forEach(c => mk(cw(s, c))); if (rw) mk(rw);
  const hth = (c, left) => { const th = el('th'); th.textContent = colName(c) + (fcols.has(c) ? ' ▾' : ''); th.dataset.col = c; if (left !== undefined) { th.style.left = left + 'px'; th.style.zIndex = 25; } return th; };
  const thead = el('thead'), hr = el('tr'); hr.append(el('th', 'corner'));
  fz.forEach((c, i) => hr.append(hth(c, fl[i]))); if (lw) hr.append(el('th')); wn.forEach(c => hr.append(hth(c))); if (rw) hr.append(el('th')); thead.append(hr);
  const mkRow = (r, ftop) => {
    const tr = el('tr'), rh = el('th', 'row-header'); rh.textContent = r + 1; rh.dataset.row = r;
    if (ftop !== undefined) { rh.style.top = ftop + 'px'; rh.style.zIndex = 26; } tr.append(rh);
    const mc = (c, left) => {
      const td = el('td', 'cell'), a = addr(r, c); td.dataset.r = r; td.dataset.c = c; td.dataset.addr = a;
      const cell = s.cells[a];
      if (cell) { const t = cellDisplay(s, a); td.textContent = t; if (ERRS.includes(t)) td.classList.add('err'); td.title = cell.raw || ''; applyCellStyle(td, cell.style || {}); }
      InkHooks.cell?.(td, s, a);
      if (ftop !== undefined || left !== undefined) { td.classList.add('frz'); if (ftop !== undefined) td.style.top = ftop + 'px'; if (left !== undefined) td.style.left = left + 'px'; td.style.zIndex = ftop !== undefined && left !== undefined ? 24 : ftop !== undefined ? 22 : 21; }
      return td;
    };
    fz.forEach((c, i) => tr.append(mc(c, fl[i]))); if (lw) tr.append(el('td', 'hsp')); wn.forEach(c => tr.append(mc(c))); if (rw) tr.append(el('td', 'hsp'));
    return tr;
  };
  const tb = el('tbody'), vs = h => { const tr = el('tr', 'vspacer'), td = el('td'); td.colSpan = n; td.style.height = h + 'px'; tr.append(td); return tr; };
  fr.forEach((r, i) => tb.append(mkRow(r, HH + i * RH)));
  if (r0 > k) tb.append(vs((r0 - k) * RH));
  let r = rowOfV(s, r0);
  for (let vr = r0; vr <= r1; vr++, r++) { while (H.rows.has(r)) r++; tb.append(mkRow(r)); }
  if (r1 < nV - 1) tb.append(vs((nV - 1 - r1) * RH));
  table.replaceChildren(cg, thead, tb); table.style.width = (HW + total) + 'px';
  table.classList.toggle('no-gridlines', !state.gridlines); applyZoom(); paintSel();
}

window.renderGrid = () => { InkEngine.clear(); hv++; draw(); };

function paintSel() {
  const a = selection.start, b = selection.end, r1 = Math.min(a.r, b.r), r2 = Math.max(a.r, b.r), c1 = Math.min(a.c, b.c), c2 = Math.max(a.c, b.c), p = act();
  table.querySelectorAll('.fill-handle').forEach(x => x.remove());
  table.querySelectorAll('td.cell').forEach(td => { const r = +td.dataset.r, c = +td.dataset.c; td.classList.toggle('range-selected', r >= r1 && r <= r2 && c >= c1 && c <= c2); td.classList.toggle('selected', r === p.r && c === p.c); });
  table.querySelectorAll('th[data-col]').forEach(th => th.classList.toggle('hdr-on', +th.dataset.col >= c1 && +th.dataset.col <= c2));
  table.querySelectorAll('th[data-row]').forEach(th => th.classList.toggle('hdr-on', +th.dataset.row >= r1 && +th.dataset.row <= r2));
  const end = table.querySelector(`td.cell[data-r="${r2}"][data-c="${c2}"]`); if (end && !isFull()) end.append(el('i', 'fill-handle'));
  InkHooks.sel?.(table.querySelector(`td.cell[data-r="${p.r}"][data-c="${p.c}"]`), activeSheet(), addr(p.r, p.c));
  updateFormulaBar(); updateSelectionStats(); updateFormatControls();
}
window.renderSelection = paintSel;

function reveal(r, c) {
  const s = activeSheet(), z = zoom, vr = vrow(s, r), k = frozenRows(s).length, FC = s.frzC || 0;
  let fw = 0; for (let i = 0; i < FC; i++) if (!hiddenInfo(s).cols.has(i)) fw += cw(s, i);
  const y = vr * RH * z, h = RH * z, x = colLeft(s, c) * z, w = cw(s, c) * z, fh = k * RH * z; fw *= z;
  if (vr >= k) { if (y - fh < viewport.scrollTop) viewport.scrollTop = y - fh; else if (y + h > viewport.scrollTop + viewport.clientHeight - HH * z) viewport.scrollTop = y + h - viewport.clientHeight + HH * z; }
  if (c >= FC) { if (x - fw < viewport.scrollLeft) viewport.scrollLeft = x - fw; else if (x + w > viewport.scrollLeft + viewport.clientWidth - HW * z) viewport.scrollLeft = x + w - viewport.clientWidth + HW * z; }
}
window.setSelection = (r, c, extend = false, scroll = true) => {
  r = Math.max(0, Math.min(MAXR - 1, r)); c = Math.max(0, Math.min(MAXC - 1, c));
  const H = hiddenInfo(activeSheet()), pr = selection.end.r, pc = selection.end.c; // pula linhas/colunas ocultas
  while (H.rows.has(r) && r > 0 && r < MAXR - 1) r += r >= pr ? 1 : -1;
  while (H.cols.has(c) && c > 0 && c < MAXC - 1) c += c >= pc ? 1 : -1;
  if (extend) selection.end = { r, c }; else selection = { start: { r, c }, end: { r, c } };
  if (scroll) reveal(r, c);
  needDraw() ? draw() : paintSel();
};
let raf = 0;
viewport.addEventListener('scroll', () => { if (raf) return; raf = requestAnimationFrame(() => { raf = 0; if (needDraw()) draw(); }); });
const _sz = window.setZoom; window.setZoom = n => { _sz(n); draw(); };
window.addRow = window.addColumn = () => flashStatus('A grade já é ilimitada');

/* ---- mouse: arrastar para selecionar, cabeçalhos, alça de preenchimento ---- */
let drag = false, fill = null;
viewport.addEventListener('mousedown', e => {
  const t = e.target;
  if (t.classList?.contains('fill-handle')) { e.preventDefault(); e.stopPropagation(); fill = { src: normalizeRange() }; return; }
  const th = t.closest?.('th');
  if (th) {
    e.preventDefault();
    if (th.classList.contains('corner')) selection = { start: { r: 0, c: 0 }, end: { r: MAXR - 1, c: MAXC - 1 } };
    else if (th.dataset.col !== undefined) { const c = +th.dataset.col; selection = { start: { r: 0, c: e.shiftKey ? selection.start.c : c }, end: { r: MAXR - 1, c } }; }
    else if (th.dataset.row !== undefined) { const r = +th.dataset.row; selection = { start: { r: e.shiftKey ? selection.start.r : r, c: 0 }, end: { r, c: MAXC - 1 } }; }
    paintSel(); return;
  }
  if (t.closest?.('.cell')) drag = true;
}, true);
document.addEventListener('mousemove', e => {
  if (!drag && !fill) return;
  const td = document.elementFromPoint(e.clientX, e.clientY)?.closest?.('.cell'); if (!td) return;
  const r = +td.dataset.r, c = +td.dataset.c;
  if (drag && e.buttons === 1) { if (selection.end.r !== r || selection.end.c !== c) { selection.end = { r, c }; paintSel(); } return; }
  if (fill) {
    const s = fill.src, dr = Math.max(0, r - s.r2), dc = Math.max(0, c - s.c2);
    fill.tr = dr >= dc && dr > 0 ? r : s.r2; fill.tc = dr < dc ? c : s.c2;
    table.querySelectorAll('td.fill-preview').forEach(x => x.classList.remove('fill-preview'));
    table.querySelectorAll('td.cell').forEach(x => { const rr = +x.dataset.r, cc = +x.dataset.c; if (rr >= s.r1 && rr <= fill.tr && cc >= s.c1 && cc <= fill.tc && !(rr <= s.r2 && cc <= s.c2)) x.classList.add('fill-preview'); });
  }
});
document.addEventListener('mouseup', () => {
  drag = false;
  if (fill) { const f = fill; fill = null; table.querySelectorAll('td.fill-preview').forEach(x => x.classList.remove('fill-preview')); if (f.tr !== undefined) fillRange(f.src, f.tr, f.tc); }
});

/* ---- preencher: séries numéricas, "Item 1, Item 2", fórmulas com referências relativas ---- */
function put(s, a, raw, style) {
  const st = { ...(style || {}) };
  if ((raw === '' || raw == null) && !Object.keys(st).length) delete s.cells[a]; else s.cells[a] = { raw: raw ?? '', style: st };
}
function fillRange(src, tr, tc) {
  const down = tr > src.r2, right = tc > src.c2; if (!down && !right) return;
  pushHistory(); const s = activeSheet();
  const n = down ? src.r2 - src.r1 + 1 : src.c2 - src.c1 + 1, lines = down ? src.c2 - src.c1 + 1 : src.r2 - src.r1 + 1, count = down ? tr - src.r2 : tc - src.c2;
  const at = (l, i) => down ? addr(src.r1 + i, src.c1 + l) : addr(src.r1 + l, src.c1 + i);
  for (let l = 0; l < lines; l++) {
    const cells = [...Array(n)].map((_, i) => s.cells[at(l, i)]), raws = cells.map(c => c?.raw ?? ''); let series = null;
    if (n > 1 && raws.every(r => typeof r === 'string' && !r.startsWith('=') && parseNum(r) !== null)) { const v = raws.map(parseNum), st = (v[n - 1] - v[0]) / (n - 1); series = k => Math.round((v[n - 1] + st * k) * 1e10) / 1e10; }
    else if (n === 1 && typeof raws[0] === 'string' && !raws[0].startsWith('=') && parseNum(raws[0]) === null) { const m = /^(.*?)(\d+)$/.exec(raws[0]); if (m) series = k => m[1] + (+m[2] + k); }
    for (let k = 1; k <= count; k++) {
      const i = (k - 1) % n, off = (down ? src.r2 : src.c2) + k - ((down ? src.r1 : src.c1) + i);
      let raw = raws[i];
      if (series) raw = String(series(k)); else if (typeof raw === 'string' && raw.startsWith('=')) raw = shiftFormula(raw, down ? off : 0, down ? 0 : off);
      put(s, down ? addr(src.r2 + k, src.c1 + l) : addr(src.r1 + l, src.c2 + k), raw, cells[i]?.style);
    }
  }
  selection = { start: { r: src.r1, c: src.c1 }, end: { r: down ? tr : src.r2, c: right ? tc : src.c2 } };
  afterDataChange();
}

/* ---- copiar/colar: preserva estilos, desloca fórmulas, funciona entre abas ---- */
let clip = null;
window.copySelection = async (cut = false) => {
  const x = normalizeRange(), s = activeSheet(), cells = [];
  for (let r = x.r1; r <= x.r2; r++) { const row = []; for (let c = x.c1; c <= x.c2; c++) { const k = s.cells[addr(r, c)]; row.push({ raw: k?.raw ?? '', style: { ...(k?.style || {}) } }); } cells.push(row); }
  const text = cells.map(row => row.map(c => String(c.raw)).join('\t')).join('\n');
  clip = { text, r: x.r1, c: x.c1, cells };
  try { await navigator.clipboard.writeText(text); } catch {}
  window.__sheetClipboard = text; if (cut) clearContents();
};
function tsv(t) {
  const rows = []; let row = [], f = '', q = false; t = t.replace(/\r/g, '');
  for (let i = 0; i < t.length; i++) {
    const ch = t[i];
    if (q) { if (ch === '"' && t[i + 1] === '"') { f += '"'; i++; } else if (ch === '"') q = false; else f += ch; }
    else if (ch === '"' && f === '') q = true; else if (ch === '\t') { row.push(f); f = ''; }
    else if (ch === '\n') { row.push(f); rows.push(row); row = []; f = ''; } else f += ch;
  }
  if (f !== '' || row.length) { row.push(f); rows.push(row); } return rows;
}
window.pasteText = text => {
  if (!text) return;
  const x = normalizeRange(), s = activeSheet(); pushHistory();
  if (clip && text === clip.text) {
    const dr = x.r1 - clip.r, dc = x.c1 - clip.c;
    clip.cells.forEach((row, i) => row.forEach((cl, j) => put(s, addr(x.r1 + i, x.c1 + j), typeof cl.raw === 'string' && cl.raw.startsWith('=') ? shiftFormula(cl.raw, dr, dc) : cl.raw, cl.style)));
  } else tsv(text).forEach((row, i) => row.forEach((v, j) => { const a = addr(x.r1 + i, x.c1 + j); put(s, a, v, s.cells[a]?.style); }));
  afterDataChange();
};

/* ---- teclado: Ctrl+setas, Home/End, PageUp/Down, Ctrl+A, Ctrl+D/R, Shift/Ctrl+Espaço ---- */
function jump(r, c, dr, dc) {
  const s = activeSheet(), u = usedRange(s), inb = (R, C) => R >= 0 && C >= 0 && R < MAXR && C < MAXC;
  const has = (R, C) => { const x = s.cells[addr(R, C)]; return !!x && x.raw !== '' && x.raw != null; };
  if (!inb(r + dr, c + dc)) return { r, c };
  const both = has(r, c) && has(r + dr, c + dc); let R = r + dr, C = c + dc;
  if (both) while (inb(R + dr, C + dc) && has(R + dr, C + dc)) { R += dr; C += dc; }
  else while (inb(R + dr, C + dc) && !has(R, C)) { R += dr; C += dc; if ((dr > 0 && R > u.r2) || (dc > 0 && C > u.c2)) { if (dr > 0) R = MAXR - 1; if (dc > 0) C = MAXC - 1; break; } }
  return { r: R, c: C };
}
document.addEventListener('keydown', e => {
  if (editing || e.target.matches?.('input,select,textarea')) return;
  const ctrl = e.ctrlKey || e.metaKey, k = e.key, a = selection.end, K = k.toLowerCase();
  const stop = () => { e.preventDefault(); e.stopImmediatePropagation(); };
  const arrows = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
  if (isFull() && !ctrl && (k.length === 1 || k === 'F2') && k !== ' ') { const p = act(); selection = { start: p, end: p }; paintSel(); }
  if (ctrl && arrows[k]) { stop(); const t = jump(a.r, a.c, ...arrows[k]); setSelection(t.r, t.c, e.shiftKey); return; }
  if (k === 'Home') { stop(); setSelection(ctrl ? 0 : a.r, 0, e.shiftKey); return; }
  if (k === 'End') { stop(); const s = activeSheet(), u = usedRange(s); let c = 0; if (!ctrl) for (const x of Object.keys(s.cells)) { const p = parseAddr(x); if (p && p.r === a.r && s.cells[x].raw !== '') c = Math.max(c, p.c); } ctrl ? setSelection(u.r2, u.c2, e.shiftKey) : setSelection(a.r, c, e.shiftKey); return; }
  if (k === 'PageDown' || k === 'PageUp') { stop(); const n = Math.max(1, Math.floor(viewport.clientHeight / zoom / RH) - 1); setSelection(a.r + (k === 'PageDown' ? n : -n), a.c, e.shiftKey); return; }
  if (ctrl && K === 'a') { stop(); selection = { start: { r: 0, c: 0 }, end: { r: MAXR - 1, c: MAXC - 1 } }; paintSel(); return; }
  if (k === ' ' && (ctrl || e.shiftKey)) { stop(); const p = act(); selection = ctrl ? { start: { r: 0, c: p.c }, end: { r: MAXR - 1, c: p.c } } : { start: { r: p.r, c: 0 }, end: { r: p.r, c: MAXC - 1 } }; paintSel(); return; }
  if (ctrl && (K === 'd' || K === 'r')) { stop(); const x = normalizeRange(); K === 'd' ? fillRange({ ...x, r2: x.r1 }, x.r2, x.c2) : fillRange({ ...x, c2: x.c1 }, x.r2, x.c2); }
}, true);

/* ---- digitar para editar: cursor no fim (o original selecionava o texto e a 2ª letra apagava a 1ª) ---- */
const _se = window.startEdit;
window.startEdit = (initial = null) => { _se(initial); if (initial !== null && editing) { const n = cellEditor.value.length; cellEditor.setSelectionRange(n, n); } };

/* ---- ordenar / remover duplicatas: usam o valor calculado e ajustam as fórmulas das linhas movidas ---- */
const readRows = (x, kc = x.c1) => { const s = activeSheet(), rows = []; for (let r = x.r1; r <= x.r2; r++) { const row = []; for (let c = x.c1; c <= x.c2; c++) row.push(clone(cellAt(addr(r, c)) || { raw: '', style: {} })); rows.push({ row, from: r, key: evaluateCell(s, addr(r, kc)) }); } return rows; };
const writeRows = (x, rows) => {
  const s = activeSheet();
  for (let r = x.r1; r <= x.r2; r++) for (let c = x.c1; c <= x.c2; c++) delete s.cells[addr(r, c)];
  rows.forEach((o, ri) => o.row.forEach((cell, ci) => {
    if (typeof cell.raw === 'string' && cell.raw.startsWith('=')) cell.raw = shiftFormula(cell.raw, x.r1 + ri - o.from, 0);
    if (cell.raw !== '' || Object.keys(cell.style || {}).length) s.cells[addr(x.r1 + ri, x.c1 + ci)] = cell;
  }));
};
window.sortSelection = (desc = false, kc) => {
  const x = normalizeRange(); if (x.r1 === x.r2) return; pushHistory();
  const rows = readRows(x, kc), blank = k => k === '' || k == null;
  rows.sort((a, b) => {
    if (blank(a.key) || blank(b.key)) return blank(a.key) - blank(b.key); // vazios sempre no fim
    const an = typeof a.key === 'number', bn = typeof b.key === 'number';
    const c = an && bn ? a.key - b.key : an !== bn ? (an ? -1 : 1) : String(a.key).localeCompare(String(b.key), 'pt-BR', { numeric: true });
    return desc ? -c : c;
  });
  writeRows(x, rows); afterDataChange();
};
window.removeDuplicates = () => {
  const x = normalizeRange(); if (x.r1 === x.r2) return; pushHistory();
  const s = activeSheet(), seen = new Set(), kept = [];
  for (const o of readRows(x)) {
    const k = JSON.stringify(o.row.map((_, ci) => String(evaluateCell(s, addr(o.from, x.c1 + ci))).toLowerCase()));
    if (!seen.has(k)) { seen.add(k); kept.push(o); }
  }
  writeRows(x, kept); afterDataChange();
};

/* ---- digitar "10%" ou "R$ 5,00" aplica o formato automaticamente ---- */
const _setRaw = window.setRaw;
window.setRaw = (sh, a, raw, style) => {
  _setRaw(sh, a, raw, style); const c = sh.cells[a];
  if (c && typeof raw === 'string' && !(c.style ||= {}).format) {
    const t = raw.trim();
    if (/^[-+]?[\d.,]+%$/.test(t)) c.style.format = 'percent'; else if (/^[-+]?\s*R\$\s*[\d.,]+$/.test(t)) c.style.format = 'currency';
  }
};

/* ---- recuperação: se o IndexedDB falhar, guarda cópia local ---- */
const _save = window.saveProject;
window.saveProject = async (show = true) => {
  try { await _save(show); localStorage.removeItem('inksheet-recovery'); }
  catch (err) {
    console.error(err);
    try { localStorage.setItem('inksheet-recovery', JSON.stringify({ projectId, at: Date.now(), state })); saveState.textContent = 'Falha ao salvar — cópia local criada'; }
    catch { saveState.textContent = 'Falha ao salvar! Baixe o .json'; }
  }
};

if (state) renderAll();
})();
