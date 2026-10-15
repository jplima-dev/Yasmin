/* InkSheet ximport.js — importa .xlsx (valores, fórmulas, estilos, larguras, várias abas). Carregar DEPOIS de xlsx.js. */
(() => {
const $$ = (el, n) => [...el.getElementsByTagNameNS('*', n)];
const attr = (el, n) => el?.getAttribute(n);
const dec = new TextDecoder();

async function unzip(buf) {
  const dv = new DataView(buf), u8 = new Uint8Array(buf); let e = u8.length - 22;
  while (e >= 0 && dv.getUint32(e, true) !== 0x06054b50) e--;
  if (e < 0) throw new Error('Arquivo .xlsx inválido');
  const n = dv.getUint16(e + 10, true); let p = dv.getUint32(e + 16, true); const files = {};
  for (let i = 0; i < n; i++) {
    const method = dv.getUint16(p + 10, true), csz = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
    const name = dec.decode(u8.subarray(p + 46, p + 46 + nl)); p += 46 + nl + el + cl;
    files[name] = async () => {
      const s = off + 30 + dv.getUint16(off + 26, true) + dv.getUint16(off + 28, true), data = u8.subarray(s, s + csz);
      if (method === 0) return dec.decode(data);
      if (method !== 8) throw new Error('Compressão não suportada');
      return dec.decode(await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer());
    };
  }
  return files;
}
const xml = s => new DOMParser().parseFromString(s, 'application/xml');
const toPt = v => String(v).replace('.', ',');
const color = c => { const v = attr(c, 'rgb'); return v && v.length === 8 ? '#' + v.slice(2).toLowerCase() : null; };

function fmtKind(id, codes) {
  if ([9, 10].includes(id)) return 'percent'; if ([14, 15, 16, 17, 22, 45, 46, 47].includes(id)) return 'date';
  if ([3, 4].includes(id)) return 'number'; if ([5, 6, 7, 8, 41, 42, 43, 44].includes(id)) return 'currency';
  const c = (codes[id] || '').replace(/"[^"]*"|\[[^\]]*\]/g, m => /R\$|\$|€|£/.test(m) ? '$' : '');
  if (!c || /^general$/i.test(c)) return null; if (/%/.test(c)) return 'percent'; if (/\$|€|£/.test(c)) return 'currency';
  if (/[dy]/i.test(c) && !/[#0]/.test(c)) return 'date'; if (/#,##0|0\.00|0,00/.test(c)) return 'number'; return null;
}
function readStyles(doc) {
  if (!doc) return () => ({});
  const codes = {}; $$(doc, 'numFmt').forEach(n => codes[+attr(n, 'numFmtId')] = attr(n, 'formatCode'));
  const borders = $$($$(doc, 'borders')[0] || doc, 'border'), fonts = $$($$(doc, 'fonts')[0] || doc, 'font'), fills = $$($$(doc, 'fills')[0] || doc, 'fill'), xfs = [...($$(doc, 'cellXfs')[0]?.children || [])], memo = [];
  return i => {
    if (memo[i]) return memo[i]; const xf = xfs[i], st = {}; memo[i] = st; if (!xf) return st;
    const f = fonts[+attr(xf, 'fontId')], fl = fills[+attr(xf, 'fillId')];
    if (f) {
      if ($$(f, 'b')[0]) st.bold = true; if ($$(f, 'i')[0]) st.italic = true; if ($$(f, 'u')[0]) st.underline = true;
      const sz = +attr($$(f, 'sz')[0], 'val'); if (sz && sz !== 11) st.fontSize = sz;
      const col = color($$(f, 'color')[0]); if (col && col !== '#000000') st.color = col;
    }
    const pf = fl && $$(fl, 'patternFill')[0];
    if (pf && attr(pf, 'patternType') === 'solid') { const c = color($$(pf, 'fgColor')[0]); if (c && c !== '#ffffff') st.fill = c; }
    const al = attr($$(xf, 'alignment')[0], 'horizontal'); if (['left', 'center', 'right'].includes(al)) st.align = al;
    const bo = borders[+attr(xf, 'borderId')]; if (bo) { const b = {}; for (const [q, n] of [['l', 'left'], ['r', 'right'], ['t', 'top'], ['b', 'bottom']]) if (attr($$(bo, n)[0], 'style')) b[q] = 1; if (Object.keys(b).length) st.border = b; }
    const k = fmtKind(+attr(xf, 'numFmtId'), codes); if (k) st.format = k;
    return st;
  };
}
const refCell = r => { const m = /^([A-Z]+)(\d+)$/.exec(r); return m ? { c: colIndex(m[1]), r: +m[2] - 1 } : null; };

async function readSheet(path, files, shared, styleOf) {
  const doc = xml(await files[path]()), cells = {}, colWidths = {}, shares = {}, hidR = [], hidC = [], pane = $$(doc, 'pane')[0], frz = pane && attr(pane, 'state') === 'frozen' ? { frzC: +(attr(pane, 'xSplit') || 0), frzR: +(attr(pane, 'ySplit') || 0) } : {};
  $$(doc, 'row').forEach(r => { if (attr(r, 'hidden') === '1') hidR.push(+attr(r, 'r') - 1); });
  $$(doc, 'col').forEach(c => { if (attr(c, 'hidden') === '1') for (let i = +attr(c, 'min'); i <= Math.min(+attr(c, 'max'), +attr(c, 'min') + 200); i++) hidC.push(i - 1); const w = Math.round(+attr(c, 'width') * 7); if (w && Math.abs(w - 96) > 2) for (let i = +attr(c, 'min'); i <= Math.min(+attr(c, 'max'), +attr(c, 'min') + 200); i++) colWidths[i - 1] = Math.max(30, w); });
  for (const c of $$(doc, 'c')) {
    const p = refCell(attr(c, 'r')); if (!p) continue;
    const t = attr(c, 't'), f = $$(c, 'f')[0], v = $$(c, 'v')[0]?.textContent ?? '', st = { ...styleOf(+(attr(c, 's') || 0)) };
    let raw = '';
    if (f) {
      let ft = f.textContent; const si = attr(f, 'si');
      if (attr(f, 't') === 'shared') { if (ft) shares[si] = { ft, p }; else if (shares[si]) ft = InkEngine.shiftFormula('=' + shares[si].ft, p.r - shares[si].p.r, p.c - shares[si].p.c).slice(1); }
      raw = ft ? '=' + ft : '';
    } else if (t === 's') raw = shared[+v] ?? '';
    else if (t === 'inlineStr') raw = $$(c, 't').map(x => x.textContent).join('');
    else if (t === 'b') raw = v === '1' ? '=TRUE' : '=FALSE';
    else if (t === 'str' || t === 'e') raw = v;
    else if (v !== '') raw = toPt(v);
    if (raw === '' && !Object.keys(st).length) continue;
    cells[addr(p.r, p.c)] = { raw, style: st };
  }
  const relPath = path.replace(/([^/]+)$/, '_rels/$1.rels'), rel = {};
  if (files[relPath]) $$(xml(await files[relPath]()), 'Relationship').forEach(r => rel[attr(r, 'Id')] = { t: attr(r, 'Type'), g: attr(r, 'Target') });
  const ent = a => cells[a] ||= { raw: '', style: {} };
  $$(doc, 'hyperlink').forEach(h => { const id = h.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id'); if (id && rel[id] && attr(h, 'ref')) { const a = attr(h, 'ref').split(':')[0], c = ent(a); c.link = rel[id].g; if (c.raw === '') c.raw = c.link; } });
  const cr = Object.values(rel).find(x => /\/comments$/.test(x.t));
  if (cr) { const cp = cr.g.startsWith('/') ? cr.g.slice(1) : 'xl/' + cr.g.replace(/^\.\.\//, ''); if (files[cp]) $$(xml(await files[cp]()), 'comment').forEach(c => { ent(attr(c, 'ref')).note = $$(c, 't').map(t => t.textContent).join(''); }); }
  const af = attr($$(doc, 'autoFilter')[0], 'ref'), tables = [];
  if (af) { const [p, q] = af.split(':').map(refCell); if (p && q && q.r > p.r) tables.push({ id: 't' + Date.now().toString(36), h: p.r, r2: q.r, c1: p.c, c2: q.c, band: false }); }
  return { cells, colWidths, hidR, hidC, tables, ...frz };
}

async function importXlsx(file) {
  const files = await unzip(await file.arrayBuffer());
  if (!files['xl/workbook.xml']) throw new Error('Não parece um arquivo .xlsx');
  const wb = xml(await files['xl/workbook.xml']()), rels = xml(await files['xl/_rels/workbook.xml.rels']()), target = {};
  $$(rels, 'Relationship').forEach(r => { const t = attr(r, 'Target'); target[attr(r, 'Id')] = t.startsWith('/') ? t.slice(1) : 'xl/' + t; });
  const shared = files['xl/sharedStrings.xml'] ? $$(xml(await files['xl/sharedStrings.xml']()), 'si').map(si => $$(si, 't').filter(t => t.parentNode.localName !== 'rPh').map(t => t.textContent).join('')) : [];
  const styleOf = readStyles(files['xl/styles.xml'] ? xml(await files['xl/styles.xml']()) : null), out = [];
  for (const s of $$(wb, 'sheet')) {
    const path = target[s.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id') || attr(s, 'r:id')];
    if (!path || !files[path]) continue;
    out.push({ name: attr(s, 'name'), ...(await readSheet(path, files, shared, styleOf)) });
  }
  if (!out.length) throw new Error('Nenhuma aba encontrada');
  pushHistory(); let first = null;
  for (const o of out) {
    let name = o.name, k = 1; while (state.sheets.some(s => s.name === name)) name = `${o.name} (${++k})`;
    const sh = { id: typeof nowId === 'function' ? nowId() : 's' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), name, rows: 60, cols: 26, cells: o.cells, colWidths: o.colWidths, rowHeights: {}, hidR: o.hidR, hidC: o.hidC, frzR: o.frzR || 0, frzC: o.frzC || 0, tables: o.tables || [] };
    state.sheets.push(sh); first = first || sh;
  }
  state.activeSheetId = first.id; selection = { start: { r: 0, c: 0 }, end: { r: 0, c: 0 } };
  renderAll(); scheduleSave(); flashStatus(`Importado: ${out.length} aba(s)`);
}

const input = document.createElement('input'); input.type = 'file'; input.accept = '.xlsx'; input.hidden = true; document.body.append(input);
input.onchange = async e => { const f = e.target.files[0]; e.target.value = ''; if (!f) return; try { await importXlsx(f); } catch (err) { console.error(err); alert('Não foi possível importar: ' + err.message); } };
const btn = document.createElement('button'); btn.type = 'button'; btn.textContent = 'Importar Excel (.xlsx)'; btn.onclick = () => input.click();
$('#menuImportCsv').after(btn);
window.InkImport = { importXlsx };
})();
