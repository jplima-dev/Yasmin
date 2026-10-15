/* InkSheet rules.js — formatação condicional e validação de dados (lista suspensa, número, inteiro).
   Carregar DEPOIS de enhance.js. As regras ficam em sheet.cf e sheet.dv (salvas junto com o projeto). */
(() => {
const h = (t, css) => { const x = document.createElement(t); if (css) x.style.cssText = css; return x; };
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const selRange = () => { const a = selection.start, b = selection.end; return { r1: Math.min(a.r, b.r), r2: Math.max(a.r, b.r), c1: Math.min(a.c, b.c), c2: Math.max(a.c, b.c) }; };
const inR = (k, r, c) => r >= k.r1 && r <= k.r2 && c >= k.c1 && c <= k.c2;
const label = k => `${addr(k.r1, k.c1)}:${addr(k.r2, k.c2)}`;
const num = v => typeof v === 'number' ? v : (v === '' || v == null ? null : InkEngine.parseNum(v));

/* ---- diálogo genérico ---- */
function dialog(title, fields, ok) {
  const ov = h('div', 'position:fixed;inset:0;background:rgba(10,20,17,.4);z-index:2000;display:grid;place-items:center');
  const box = h('form', 'width:min(380px,92vw);padding:22px;border-radius:14px;background:var(--surface);color:var(--text);border:1px solid var(--line);box-shadow:0 24px 60px rgba(0,0,0,.25);display:grid;gap:12px;font-size:13px;max-height:90vh;overflow:auto');
  const t = h('strong', 'font:400 18px Georgia,serif'); t.textContent = title; box.append(t);
  const ctl = {}, rows = {};
  for (const f of fields) {
    const row = h('label', 'display:grid;gap:4px;color:var(--muted);font-size:11px'); row.append(f.label); let c;
    if (f.type === 'select') { c = h('select'); f.opts.forEach(([v, x]) => { const o = h('option'); o.value = v; o.textContent = x; c.append(o); }); }
    else if (f.type === 'textarea') c = h('textarea');
    else { c = h('input'); c.type = f.type || 'text'; }
    c.value = f.value ?? ''; c.style.cssText = 'height:34px;padding:0 8px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--text);font-size:13px' + (f.type === 'color' ? ';padding:2px' : '') + (f.type === 'textarea' ? ';height:110px;padding:8px;resize:vertical;font:13px Arial' : '');
    row.append(c); box.append(row); ctl[f.k] = c; rows[f.k] = row;
  }
  const sync = () => fields.forEach(f => { if (f.when) rows[f.k].style.display = f.when.in.includes(ctl[f.when.k].value) ? 'grid' : 'none'; });
  box.addEventListener('input', sync); sync();
  const bar = h('div', 'display:flex;gap:8px;justify-content:flex-end;margin-top:4px'), cancel = h('button'), go = h('button');
  cancel.type = 'button'; cancel.textContent = 'Cancelar'; go.textContent = 'Aplicar';
  cancel.style.cssText = 'padding:8px 14px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text);cursor:pointer';
  go.style.cssText = 'padding:8px 16px;border:0;border-radius:8px;background:var(--primary);color:#fff;cursor:pointer;font-weight:700';
  bar.append(cancel, go); box.append(bar); ov.append(box); document.body.append(ov);
  cancel.onclick = () => ov.remove(); ov.addEventListener('mousedown', e => { if (e.target === ov) ov.remove(); });
  ov.addEventListener('keydown', e => { if (e.key === 'Escape') ov.remove(); e.stopPropagation(); });
  box.onsubmit = e => { e.preventDefault(); const v = {}; fields.forEach(f => v[f.k] = ctl[f.k].value); ov.remove(); ok(v); };
  (Object.values(ctl)[0]).focus();
}

window.InkDialog = dialog;

/* ---- formatação condicional ---- */
let dups = new Map();
function test(k, v, s) {
  const op = k.op;
  if (op === 'empty') return v === '' || v == null;
  if (op === 'contains') return String(v ?? '').toLowerCase().includes(String(k.val).toLowerCase());
  if (op === 'dup') {
    if (v === '' || v == null) return false;
    if (!dups.has(k.id)) {
      const m = new Map(), u = usedRange(s);
      for (const a of Object.keys(s.cells)) { const p = parseAddr(a); if (!p || !inR({ r1: k.r1, r2: Math.min(k.r2, u.r2), c1: k.c1, c2: Math.min(k.c2, u.c2) }, p.r, p.c)) continue; const x = String(evaluateCell(s, a)).toLowerCase(); if (x !== '') m.set(x, (m.get(x) || 0) + 1); }
      dups.set(k.id, m);
    }
    return dups.get(k.id).get(String(v).toLowerCase()) > 1;
  }
  const x = num(v), y = num(k.val), z = num(k.val2);
  if (op === 'eq') return x !== null && y !== null ? x === y : String(v ?? '').toLowerCase() === String(k.val).toLowerCase();
  if (x === null || y === null) return false;
  if (op === 'gt') return x > y; if (op === 'lt') return x < y;
  if (op === 'between') return z !== null && x >= Math.min(y, z) && x <= Math.max(y, z);
  return false;
}
InkHooks.begin = () => { dups = new Map(); };
InkHooks.cell = (td, s, a) => {
  if (!s.cf?.length) return; const r = +td.dataset.r, c = +td.dataset.c; let v;
  for (const k of s.cf) {
    if (!inR(k, r, c)) continue; v ??= evaluateCell(s, a);
    if (test(k, v, s)) { if (k.fill) td.style.backgroundColor = k.fill; if (k.color) td.style.color = k.color; if (k.bold) td.style.fontWeight = '700'; }
  }
};
function addCF() {
  const rg = selRange();
  dialog(`Formatação condicional — ${label(rg)}`, [
    { k: 'op', label: 'Quando a célula for…', type: 'select', value: 'gt', opts: [['gt', 'Maior que'], ['lt', 'Menor que'], ['eq', 'Igual a'], ['between', 'Entre'], ['contains', 'Contém o texto'], ['empty', 'Vazia'], ['dup', 'Valor duplicado']] },
    { k: 'val', label: 'Valor', when: { k: 'op', in: ['gt', 'lt', 'eq', 'between', 'contains'] } },
    { k: 'val2', label: 'e', when: { k: 'op', in: ['between'] } },
    { k: 'fill', label: 'Cor de fundo', type: 'color', value: '#fde2dd' },
    { k: 'color', label: 'Cor do texto', type: 'color', value: '#9b2c1a' },
    { k: 'bold', label: 'Negrito', type: 'select', value: '', opts: [['', 'Não'], ['1', 'Sim']] },
  ], v => {
    pushHistory(); (activeSheet().cf ||= []).push({ id: uid(), ...rg, op: v.op, val: v.val, val2: v.val2, fill: v.fill, color: v.color, bold: !!v.bold });
    afterDataChange();
  });
}

/* ---- validação de dados ---- */
const dvAt = (s, r, c) => s.dv?.find(k => inR(k, r, c));
function check(k, raw) {
  const msg = k.msg || 'Valor inválido para esta célula.'; raw = String(raw ?? '').trim();
  if (raw === '' || raw.startsWith('=')) return null;
  if (k.type === 'list') return k.items.some(i => i.toLowerCase() === raw.toLowerCase()) ? null : msg;
  const n = InkEngine.parseNum(raw); if (n === null) return msg;
  if (k.type === 'integer' && !Number.isInteger(n)) return msg;
  const lo = num(k.min), hi = num(k.max);
  return (lo !== null && n < lo) || (hi !== null && n > hi) ? msg : null;
}
const _fe = window.finishEdit; let busy = false;
window.finishEdit = (commit = true) => {
  if (busy) return; // o blur disparado ao esconder o editor não pode confirmar a edição rejeitada
  if (commit && editing) {
    const p = selection.end, k = dvAt(activeSheet(), p.r, p.c), err = k && check(k, cellEditor.value);
    if (err) { busy = true; _fe(false); alert(err); busy = false; return; }
  }
  _fe(commit);
};
InkHooks.sel = (td, s, a) => {
  if (!td) return; const p = parseAddr(a), k = dvAt(s, p.r, p.c); if (!k || k.type !== 'list') return;
  const sel = h('select', 'position:absolute;right:0;top:0;width:18px;height:100%;opacity:.01;cursor:pointer;z-index:6'), arrow = h('i', 'position:absolute;right:3px;top:50%;transform:translateY(-50%);font-size:9px;font-style:normal;color:var(--muted);pointer-events:none');
  arrow.textContent = '▾'; k.items.forEach(i => { const o = h('option'); o.textContent = i; sel.append(o); }); sel.selectedIndex = -1;
  sel.onchange = () => { pushHistory(); setRaw(s, a, sel.value); afterDataChange(); };
  td.append(arrow, sel);
};
function addDV() {
  const rg = selRange();
  dialog(`Validação de dados — ${label(rg)}`, [
    { k: 'type', label: 'Permitir', type: 'select', value: 'list', opts: [['list', 'Lista suspensa'], ['number', 'Número decimal'], ['integer', 'Número inteiro']] },
    { k: 'items', label: 'Itens (separados por ;)', when: { k: 'type', in: ['list'] } },
    { k: 'min', label: 'Mínimo (opcional)', when: { k: 'type', in: ['number', 'integer'] } },
    { k: 'max', label: 'Máximo (opcional)', when: { k: 'type', in: ['number', 'integer'] } },
    { k: 'msg', label: 'Mensagem de erro', value: 'Valor inválido para esta célula.' },
  ], v => {
    const items = v.items.split(/[;\n]/).map(x => x.trim()).filter(Boolean);
    if (v.type === 'list' && !items.length) { alert('Informe ao menos um item.'); return; }
    pushHistory(); const s = activeSheet(); s.dv = (s.dv || []).filter(k => !(k.r1 <= rg.r2 && k.r2 >= rg.r1 && k.c1 <= rg.c2 && k.c2 >= rg.c1));
    s.dv.push({ id: uid(), ...rg, type: v.type, items, min: v.min, max: v.max, msg: v.msg }); afterDataChange();
  });
}
function clearRules() {
  const rg = selRange(), s = activeSheet(), hit = k => k.r1 <= rg.r2 && k.r2 >= rg.r1 && k.c1 <= rg.c2 && k.c2 >= rg.c1;
  const n = (s.cf || []).filter(hit).length + (s.dv || []).filter(hit).length;
  if (!n) { flashStatus('Nenhuma regra na seleção'); return; }
  pushHistory(); s.cf = (s.cf || []).filter(k => !hit(k)); s.dv = (s.dv || []).filter(k => !hit(k)); afterDataChange(); flashStatus(`${n} regra(s) removida(s)`);
}

/* ---- menu Dados ---- */
let anchor = $('#menuRemoveDuplicates');
for (const [txt, fn] of [['Formatação condicional…', addCF], ['Validação de dados…', addDV], ['Limpar regras da seleção', clearRules]]) {
  const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.onclick = fn; anchor.after(b); anchor = b;
}
})();
