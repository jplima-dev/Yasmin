/* InkSheet views.js — ocultar/exibir linhas e colunas, filtrar por valor. Carregar DEPOIS de enhance.js.
   Estado salvo em sheet.hidR / sheet.hidC (listas de índices) e sheet.filters ([{c, val, h}]). */
(() => {
const raw = () => { const a = selection.start, b = selection.end; return { r1: Math.min(a.r, b.r), r2: Math.max(a.r, b.r), c1: Math.min(a.c, b.c), c2: Math.max(a.c, b.c) }; };
const uniq = (list, add) => [...new Set([...(list || []), ...add])].sort((a, b) => a - b);
const span = (a, b, cap) => { const out = []; for (let i = a; i <= Math.min(b, a + cap); i++) out.push(i); return out; };

function hideRows() {
  const s = activeSheet(), x = raw(), u = usedRange(s), r2 = x.r2 - x.r1 > 50000 ? Math.min(x.r2, Math.max(u.r2, x.r1)) : x.r2;
  pushHistory(); s.hidR = uniq(s.hidR, span(x.r1, r2, 50000)); selection = { start: { r: r2 + 1, c: x.c1 }, end: { r: r2 + 1, c: x.c1 } };
  afterDataChange(); flashStatus(`${r2 - x.r1 + 1} linha(s) oculta(s)`);
}
function hideCols() {
  const s = activeSheet(), x = raw(), u = usedRange(s), c2 = x.c2 - x.c1 > 2000 ? Math.min(x.c2, Math.max(u.c2, x.c1)) : x.c2;
  pushHistory(); s.hidC = uniq(s.hidC, span(x.c1, c2, 2000)); selection = { start: { r: x.r1, c: c2 + 1 }, end: { r: x.r1, c: c2 + 1 } };
  afterDataChange(); flashStatus(`${c2 - x.c1 + 1} coluna(s) oculta(s)`);
}
function filterByValue() {
  const s = activeSheet(), p = selection.end.r >= MAXR - 1 || selection.end.c >= 16383 ? selection.start : selection.end;
  const has = r => { const k = s.cells[addr(r, p.c)]; return !!k && k.raw !== '' && k.raw != null; };
  let h = p.r; while (h > 0 && has(h - 1)) h--; // cabeçalho = topo do bloco contíguo da coluna
  if (!has(p.r) && !has(p.r - 1)) { flashStatus('Selecione uma célula de dados abaixo do cabeçalho'); return; }
  if (h === p.r) { flashStatus('Selecione uma célula abaixo do cabeçalho'); return; }
  pushHistory(); const val = String(cellDisplay(s, addr(p.r, p.c)));
  s.filters = [...(s.filters || []).filter(f => f.c !== p.c), { c: p.c, val, h }];
  afterDataChange(); flashStatus(`Filtrado: coluna ${colName(p.c)} = "${val}"`);
}
function clearFilters() { const s = activeSheet(); if (!s.filters?.length) { flashStatus('Nenhum filtro ativo'); return; } pushHistory(); s.filters = []; afterDataChange(); flashStatus('Filtros removidos'); }
function showAll() {
  const s = activeSheet(); if (!(s.hidR?.length || s.hidC?.length || s.filters?.length)) { flashStatus('Nada oculto'); return; }
  pushHistory(); s.hidR = []; s.hidC = []; s.filters = []; afterDataChange(); flashStatus('Tudo exibido');
}

const MAXR = 1048576;
let anchor = $('#menuSortDesc') || $('#menuRemoveDuplicates');
for (const [txt, fn] of [['Filtrar pelo valor da célula', filterByValue], ['Limpar filtros', clearFilters], ['Ocultar linhas', hideRows], ['Ocultar colunas', hideCols], ['Exibir tudo', showAll]]) {
  const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.onclick = fn; anchor.after(b); anchor = b;
}
})();
