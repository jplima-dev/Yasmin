/* InkSheet colresize.js — arraste a borda direita do cabeçalho da coluna; duplo clique ajusta ao conteúdo. Carregar DEPOIS de enhance.js. */
(() => {
const EDGE = 5, MIN = 30;
const edgeTh = e => {
  const th = e.target.closest?.('th[data-col]'); if (!th) return null;
  return e.clientX > th.getBoundingClientRect().right - EDGE ? th : null;
};
let drag = null;

viewport.addEventListener('mousemove', e => { if (!drag) viewport.style.cursor = edgeTh(e) ? 'col-resize' : ''; });

// captura no document: roda antes da seleção por cabeçalho do enhance.js
document.addEventListener('mousedown', e => {
  const th = edgeTh(e); if (!th) return;
  e.preventDefault(); e.stopPropagation();
  const c = +th.dataset.col, s = activeSheet(), cols = table.querySelector('colgroup').children;
  drag = { c, x: e.clientX, w: s.colWidths[c] || 96, col: cols[th.cellIndex] };
}, true);

document.addEventListener('mousemove', e => {
  if (!drag) return;
  drag.nw = Math.max(MIN, Math.round(drag.w + (e.clientX - drag.x) / zoom));
  drag.col.style.width = drag.nw + 'px';
});

document.addEventListener('mouseup', () => {
  if (!drag) return; const d = drag; drag = null; viewport.style.cursor = '';
  if (d.nw && d.nw !== d.w) setWidth(d.c, d.nw);
});

viewport.addEventListener('dblclick', e => {
  const th = edgeTh(e); if (!th) return; e.stopPropagation();
  const c = +th.dataset.col, s = activeSheet(); let max = 0, n = 0;
  for (const a of Object.keys(s.cells)) {
    const p = parseAddr(a); if (!p || p.c !== c) continue;
    const st = s.cells[a].style || {}; max = Math.max(max, cellDisplay(s, a).length * (st.bold ? 8 : 7) * ((st.fontSize || 12) / 12)); if (++n > 3000) break;
  }
  setWidth(c, Math.max(MIN, Math.min(600, Math.round(max + 20))));
}, true);

function setWidth(c, w) {
  pushHistory(); activeSheet().colWidths[c] = w; renderGrid(); scheduleSave();
}
})();
