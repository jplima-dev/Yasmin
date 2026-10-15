/* InkSheet tables.js — tabelas estruturadas e filtros com lista de valores (menu Dados).
   Estado: sheet.tables = [{id, h (linha do cabeçalho), r2, c1, c2, band}] e sheet.filters = [{c, h, vals:[…minúsculas]}].
   Carregar DEPOIS de notes.js. */
(() => {
const css = document.createElement('style');
css.textContent = `.sheet-table td.tb-head:not(.range-selected){background:var(--primary);color:#fff;font-weight:700}
.sheet-table td.tb-band:not(.range-selected){background:var(--mint)}.sheet-table td.cell.frz.tb-band:not(.range-selected){background:var(--mint)}.sheet-table td.cell.frz.tb-head:not(.range-selected){background:var(--primary)}
.flt-btn{position:absolute;right:3px;top:50%;transform:translateY(-50%);width:15px;height:15px;line-height:13px;text-align:center;font-size:9px;font-style:normal;background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:3px;cursor:pointer;z-index:4}
.flt-btn.on{background:var(--accent);color:#fff;border-color:var(--accent)}
#fltMenu{position:fixed;z-index:1600;width:250px;padding:10px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--text);box-shadow:0 18px 44px rgba(0,0,0,.22);font:12px Arial,sans-serif;display:grid;gap:8px}
#fltMenu button{padding:7px 10px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--text);cursor:pointer;text-align:left;font:inherit}
#fltMenu input[type=search]{height:30px;padding:0 8px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--text)}
#fltMenu .fl-list{max-height:190px;overflow:auto;border:1px solid var(--line);border-radius:7px;padding:4px}#fltMenu label{display:flex;gap:7px;align-items:center;padding:3px 4px;cursor:pointer}
#fltMenu .fl-bar{display:flex;gap:6px;justify-content:flex-end}#fltMenu .fl-ok{background:var(--primary);color:#fff;border-color:var(--primary)}`;
document.head.append(css);

const uid = () => 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
const act = () => (selection.end.r >= 1048575 || selection.end.c >= 16383) ? selection.start : selection.end;
const has = (s, r, c) => { const k = s.cells[addr(r, c)]; return !!k && k.raw !== '' && k.raw != null; };

/* ---- renderização: cabeçalho com botão ▾ e linhas alternadas ---- */
const prev = InkHooks.cell;
InkHooks.cell = (td, s, a) => {
  prev?.(td, s, a); if (!s.tables?.length) return; const r = +td.dataset.r, c = +td.dataset.c;
  for (const t of s.tables) {
    if (c < t.c1 || c > t.c2 || r < t.h || r > t.r2) continue;
    if (r === t.h) {
      if (t.band && !s.cells[a]?.style?.fill) td.classList.add('tb-head'); td.style.paddingRight = '22px'; // fundo próprio do usuário tem prioridade
      const on = (s.filters || []).some(f => f.c === c && f.h === t.h), b = document.createElement('i');
      b.className = 'flt-btn' + (on ? ' on' : ''); b.dataset.c = c; b.dataset.t = t.id; b.textContent = on ? '⏷' : '▾'; td.append(b);
    } else if (t.band && (r - t.h) % 2 === 0 && !s.cells[a]?.style?.fill) td.classList.add('tb-band');
  }
};

/* ---- criar / remover ---- */
function regionAt(s) {
  const x = selection, multi = x.start.r !== x.end.r || x.start.c !== x.end.c;
  if (multi && x.end.r < 1048575 && x.end.c < 16383) { const r1 = Math.min(x.start.r, x.end.r), r2 = Math.max(x.start.r, x.end.r), c1 = Math.min(x.start.c, x.end.c), c2 = Math.max(x.start.c, x.end.c); return r2 > r1 ? { h: r1, r2, c1, c2 } : null; }
  const p = act(); let h = p.r; while (h > 0 && has(s, h - 1, p.c)) h--;
  if (!has(s, h, p.c)) return null;
  let c1 = p.c, c2 = p.c; while (c1 > 0 && has(s, h, c1 - 1)) c1--; while (has(s, h, c2 + 1)) c2++;
  let r2 = h; const any = r => { for (let c = c1; c <= c2; c++) if (has(s, r, c)) return true; return false; };
  while (r2 - h < 100000 && any(r2 + 1)) r2++;
  return r2 > h ? { h, r2, c1, c2 } : null;
}
function make(band) {
  const s = activeSheet(), g = regionAt(s); if (!g) { flashStatus('Selecione uma célula dentro dos dados (cabeçalho + ao menos 1 linha)'); return; }
  pushHistory(); s.tables = (s.tables || []).filter(t => !(t.h <= g.r2 && t.r2 >= g.h && t.c1 <= g.c2 && t.c2 >= g.c1));
  s.tables.push({ id: uid(), ...g, band }); afterDataChange(); flashStatus(`Tabela ${addr(g.h, g.c1)}:${addr(g.r2, g.c2)}`);
}
function remove() {
  const s = activeSheet(), p = act(), t = (s.tables || []).find(t => p.r >= t.h && p.r <= t.r2 && p.c >= t.c1 && p.c <= t.c2);
  if (!t) { flashStatus('A célula selecionada não está em uma tabela'); return; }
  pushHistory(); s.tables = s.tables.filter(x => x !== t); s.filters = (s.filters || []).filter(f => f.h !== t.h); afterDataChange();
}

/* ---- auto-expansão: digitar logo abaixo (ou ao lado do cabeçalho) amplia a tabela ---- */
const _sr = window.setRaw;
window.setRaw = (sh, a, raw, style) => {
  _sr(sh, a, raw, style); if (!sh.tables?.length || raw === '' || raw == null) return; const p = parseAddr(a);
  for (const t of sh.tables) {
    if (p.c >= t.c1 && p.c <= t.c2 && p.r === t.r2 + 1) t.r2++;
    else if (p.r === t.h && p.c === t.c2 + 1) t.c2++;
  }
};

/* ---- menu do filtro ---- */
let menu = null;
const closeMenu = () => { menu?.remove(); menu = null; };
function openMenu(btn) {
  closeMenu(); const s = activeSheet(), t = s.tables.find(x => x.id === btn.dataset.t), c = +btn.dataset.c; if (!t) return;
  const vals = new Map();
  for (let r = t.h + 1; r <= t.r2 && vals.size < 1000; r++) { const d = String(cellDisplay(s, addr(r, c))), k = d.toLowerCase(); if (!vals.has(k)) vals.set(k, d); }
  const list = [...vals].sort((a, b) => a[1].localeCompare(b[1], 'pt-BR', { numeric: true }));
  const f = (s.filters || []).find(x => x.c === c && x.h === t.h), allowed = f ? new Set(f.vals || [String(f.val).toLowerCase()]) : null;
  menu = document.createElement('div'); menu.id = 'fltMenu';
  const mkBtn = (txt, fn, cls) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; if (cls) b.className = cls; b.onclick = fn; return b; };
  const sortBy = desc => { closeMenu(); selection = { start: { r: t.h + 1, c: t.c1 }, end: { r: t.r2, c: t.c2 } }; sortSelection(desc, c); };
  const search = document.createElement('input'); search.type = 'search'; search.placeholder = 'Buscar valor…';
  const box = document.createElement('div'); box.className = 'fl-list'; const checks = [];
  const row = (label, key, checked) => { const l = document.createElement('label'), i = document.createElement('input'); i.type = 'checkbox'; i.checked = checked; l.append(i, label === '' ? '(vazias)' : label); box.append(l); checks.push({ key, i, l, label: label.toLowerCase() }); return i; };
  const all = row('(Selecionar tudo)', null, !allowed || list.every(([k]) => allowed.has(k)));
  list.forEach(([k, d]) => row(d, k, !allowed || allowed.has(k)));
  all.onchange = () => checks.forEach(x => { if (x.key !== null && x.l.style.display !== 'none') x.i.checked = all.checked; });
  search.oninput = () => { const q = search.value.toLowerCase(); checks.forEach(x => { if (x.key !== null) x.l.style.display = x.label.includes(q) ? '' : 'none'; }); };
  const apply = () => {
    const on = checks.filter(x => x.key !== null && x.i.checked).map(x => x.key); closeMenu(); pushHistory();
    s.filters = (s.filters || []).filter(x => !(x.c === c && x.h === t.h)); if (on.length < list.length) s.filters.push({ c, h: t.h, vals: on });
    afterDataChange();
  };
  const bar = document.createElement('div'); bar.className = 'fl-bar';
  bar.append(mkBtn('Limpar', () => { closeMenu(); pushHistory(); s.filters = (s.filters || []).filter(x => !(x.c === c && x.h === t.h)); afterDataChange(); }), mkBtn('Cancelar', closeMenu), mkBtn('OK', apply, 'fl-ok'));
  menu.append(mkBtn('↑  Classificar A → Z', () => sortBy(false)), mkBtn('↓  Classificar Z → A', () => sortBy(true)), search, box, bar);
  document.body.append(menu); const r = btn.getBoundingClientRect();
  menu.style.left = Math.max(8, Math.min(r.left - 200, innerWidth - 262)) + 'px'; menu.style.top = Math.min(r.bottom + 4, innerHeight - menu.offsetHeight - 8) + 'px'; search.focus();
}
viewport.addEventListener('mousedown', e => { if (e.target.classList?.contains('flt-btn')) { e.preventDefault(); e.stopPropagation(); openMenu(e.target); } }, true);
document.addEventListener('mousedown', e => { if (menu && !menu.contains(e.target) && !e.target.classList?.contains('flt-btn')) closeMenu(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && menu) closeMenu(); }, true);
viewport.addEventListener('scroll', closeMenu);

let anchor = $('#menuRemoveDuplicates');
for (const [txt, fn] of [['Formatar como tabela', () => make(true)], ['Ativar filtros no cabeçalho', () => make(false)], ['Remover tabela/filtros', remove]]) {
  const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.onclick = fn; anchor.after(b); anchor = b;
}
})();
