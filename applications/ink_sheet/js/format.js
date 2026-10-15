/* InkSheet format.js — congelar painéis (menu Visualizar) e bordas (seletor na barra de ferramentas).
   Carregar DEPOIS de rules.js. Estado: sheet.frzR / sheet.frzC e style.border = {t,r,b,l}. */
(() => {
const FULL = 1048576;
const active = () => (selection.end.r >= FULL - 1 || selection.end.c >= 16383) ? selection.start : selection.end;

/* ---- congelar painéis ---- */
function freeze(rows, cols, msg) {
  const s = activeSheet(); pushHistory(); s.frzR = rows; s.frzC = cols; afterDataChange(); flashStatus(msg);
}
function freezeHere() {
  const p = active(); if (!p.r && !p.c) { flashStatus('Selecione uma célula abaixo/à direita do que deve ficar fixo'); return; }
  freeze(p.r, p.c, `Congelado: ${p.r} linha(s) e ${p.c} coluna(s)`);
}

/* ---- bordas ---- */
const LINE = '1px solid var(--text)';
function applyBorder(mode) {
  const s = activeSheet(), x = normalizeRange(); pushHistory();
  for (let r = x.r1; r <= x.r2; r++) for (let c = x.c1; c <= x.c2; c++) {
    const a = addr(r, c), cell = s.cells[a] ||= { raw: '', style: {} }, st = cell.style ||= {};
    if (mode === 'none') { delete st.border; }
    else {
      const e = { t: r === x.r1, b: r === x.r2, l: c === x.c1, r: c === x.c2 };
      const add = mode === 'all' ? { t: 1, r: 1, b: 1, l: 1 } : mode === 'outline' ? { t: e.t, r: e.r, b: e.b, l: e.l } : mode === 'top' ? { t: e.t } : mode === 'bottom' ? { b: e.b } : mode === 'left' ? { l: e.l } : { r: e.r };
      const b = { ...(st.border || {}) }; for (const k in add) if (add[k]) b[k] = 1;
      if (Object.keys(b).length) st.border = b;
    }
    if (cell.raw === '' && !Object.keys(st).length) delete s.cells[a];
  }
  afterDataChange();
}
const prev = InkHooks.cell;
InkHooks.cell = (td, s, a) => {
  prev?.(td, s, a); const b = s.cells[a]?.style?.border; if (!b) return;
  if (b.t) td.style.borderTop = LINE; if (b.r) td.style.borderRight = LINE; if (b.b) td.style.borderBottom = LINE; if (b.l) td.style.borderLeft = LINE;
};

/* ---- interface ---- */
const lab = document.createElement('label'); lab.className = 'control';
lab.innerHTML = '<span>Bordas</span><select id="borderSelect"><option value="">Escolher…</option><option value="all">Todas</option><option value="outline">Contorno</option><option value="top">Superior</option><option value="bottom">Inferior</option><option value="left">Esquerda</option><option value="right">Direita</option><option value="none">Nenhuma</option></select>';
lab.querySelector('select').onchange = e => { const m = e.target.value; e.target.selectedIndex = 0; if (m) applyBorder(m); };
($('#clearFormatButton').closest('.toolbar-group') || $('#clearFormatButton')).before(lab);

let anchor = $('#menuGridlines');
for (const [txt, fn] of [['Congelar painéis aqui', freezeHere], ['Congelar linha superior', () => freeze(1, activeSheet().frzC || 0, 'Linha superior congelada')], ['Congelar primeira coluna', () => freeze(activeSheet().frzR || 0, 1, 'Primeira coluna congelada')], ['Descongelar painéis', () => freeze(0, 0, 'Painéis descongelados')]]) {
  const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.onclick = fn; anchor.after(b); anchor = b;
}
})();
