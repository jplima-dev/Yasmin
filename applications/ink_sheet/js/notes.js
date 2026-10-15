/* InkSheet notes.js — notas (comentários) e hyperlinks em células. Carregar DEPOIS de rules.js e format.js.
   Estado: cell.note (texto) e cell.link (URL). Também reconhece texto "https://…"/"www.…" e =HYPERLINK("url";"texto"). */
(() => {
const css = document.createElement('style');
css.textContent = `.sheet-table td.has-note::after{content:"";position:absolute;top:0;right:0;border-style:solid;border-width:0 8px 8px 0;border-color:transparent #d93025 transparent transparent;pointer-events:none}
.sheet-table td.has-link{color:var(--link,#0b5fcc);text-decoration:underline}body.dark .sheet-table td.has-link{--link:#7db3ff}
#noteTip{position:fixed;z-index:1500;max-width:280px;padding:9px 11px;border:1px solid #d9c66a;border-radius:8px;background:#fff8d6;color:#3b3200;font:12px/1.4 Arial,sans-serif;white-space:pre-wrap;box-shadow:0 8px 24px rgba(0,0,0,.18);pointer-events:none}`;
document.head.append(css);

/* só http, https e mailto (bloqueia javascript:, data: etc.) */
const safe = u => { try { const x = new URL(/^[a-z][a-z0-9+.-]*:/i.test(u) ? u : 'https://' + u); return ['http:', 'https:', 'mailto:'].includes(x.protocol) ? x.href : null; } catch { return null; } };
function urlOf(s, a) {
  const c = s.cells[a]; if (!c) return null; if (c.link) return safe(c.link);
  const r = typeof c.raw === 'string' ? c.raw.trim() : '', m = /^=\s*(?:HYPERLINK|HIPERLINK)\(\s*"([^"]+)"/i.exec(r);
  if (m) return safe(m[1]); return /^(https?:\/\/|www\.)\S+$/i.test(r) ? safe(r) : null;
}
window.InkLinks = { urlOf, safe };

const prev = InkHooks.cell;
InkHooks.cell = (td, s, a) => {
  prev?.(td, s, a); const c = s.cells[a]; if (!c) return;
  const u = urlOf(s, a);
  if (u) { td.classList.add('has-link'); td.title = `${u}\n(Ctrl+clique para abrir)`; }
  if (c.note) { td.classList.add('has-note'); td.dataset.note = c.note; td.removeAttribute('title'); }
};

/* tooltip da nota ao passar o mouse */
const tip = document.createElement('div'); tip.id = 'noteTip'; tip.hidden = true; document.body.append(tip);
viewport.addEventListener('mouseover', e => {
  const td = e.target.closest?.('td.has-note'); if (!td) { tip.hidden = true; return; }
  const r = td.getBoundingClientRect(); tip.textContent = td.dataset.note; tip.hidden = false;
  tip.style.left = Math.min(r.right + 6, innerWidth - 300) + 'px'; tip.style.top = Math.min(r.top, innerHeight - tip.offsetHeight - 10) + 'px';
});
viewport.addEventListener('mouseleave', () => { tip.hidden = true; });
viewport.addEventListener('scroll', () => { tip.hidden = true; });

/* Ctrl+clique abre o link */
viewport.addEventListener('click', e => {
  if (!(e.ctrlKey || e.metaKey)) return; const td = e.target.closest?.('td.has-link'); if (!td) return;
  const u = urlOf(activeSheet(), td.dataset.addr); if (u) { e.preventDefault(); e.stopPropagation(); window.open(u, '_blank', 'noopener'); }
}, true);

/* ---- comandos ---- */
const cur = () => { const a = selectedAddr(); return { a, s: activeSheet() }; };
const tidy = (s, a) => { const c = s.cells[a]; if (c && c.raw === '' && !c.note && !c.link && !Object.keys(c.style || {}).length) delete s.cells[a]; };
function editNote() {
  const { a, s } = cur();
  InkDialog(`Nota — ${a}`, [{ k: 'text', label: 'Texto da nota (deixe vazio para remover)', type: 'textarea', value: s.cells[a]?.note || '' }], v => {
    pushHistory(); const c = s.cells[a] ||= { raw: '', style: {} };
    if (v.text.trim()) c.note = v.text; else delete c.note; tidy(s, a); afterDataChange();
  });
}
function removeNote() { const { a, s } = cur(); if (!s.cells[a]?.note) { flashStatus('Esta célula não tem nota'); return; } pushHistory(); delete s.cells[a].note; tidy(s, a); afterDataChange(); }
function editLink() {
  const { a, s } = cur(), c0 = s.cells[a];
  InkDialog(`Link — ${a}`, [
    { k: 'url', label: 'Endereço (http, https ou mailto)', value: c0?.link || urlOf(s, a) || '' },
    { k: 'text', label: 'Texto a exibir (opcional)', value: '' },
  ], v => {
    const u = safe(v.url.trim()); if (!u) { alert('Endereço inválido. Use http://, https:// ou mailto:'); return; }
    pushHistory(); const c = s.cells[a] ||= { raw: '', style: {} }; c.link = u;
    if (v.text.trim()) c.raw = v.text.trim(); else if (c.raw === '') c.raw = u;
    afterDataChange();
  });
}
function removeLink() {
  const { a, s } = cur(), c = s.cells[a];
  if (!c || !urlOf(s, a)) { flashStatus('Esta célula não tem link'); return; }
  pushHistory(); delete c.link; if (typeof c.raw === 'string' && /^(https?:\/\/|www\.)\S+$/i.test(c.raw.trim())) c.raw = ''; tidy(s, a); afterDataChange();
}

let anchor = $('#menuChart');
for (const [txt, fn] of [['Inserir/editar nota…', editNote], ['Remover nota', removeNote], ['Inserir/editar link…', editLink], ['Remover link', removeLink]]) {
  const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.onclick = fn; anchor.after(b); anchor = b;
}
})();
