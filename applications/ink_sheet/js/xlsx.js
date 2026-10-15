/* InkSheet xlsx.js — exporta .xlsx real (fórmulas, estilos, larguras, várias abas). Carregar DEPOIS de enhance.js. */
(() => {
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
const EN = { SOMA: 'SUM', 'MÉDIA': 'AVERAGE', MEDIA: 'AVERAGE', 'MÍNIMO': 'MIN', MINIMO: 'MIN', 'MÁXIMO': 'MAX', MAXIMO: 'MAX', 'CONT.NÚM': 'COUNT', 'CONT.NUM': 'COUNT', 'CONT.VALORES': 'COUNTA', SE: 'IF', SEERRO: 'IFERROR', E: 'AND', OU: 'OR', 'NÃO': 'NOT', NAO: 'NOT', ARRED: 'ROUND', RESTO: 'MOD', 'POTÊNCIA': 'POWER', POTENCIA: 'POWER', RAIZ: 'SQRT', SOMASE: 'SUMIF', 'CONT.SE': 'COUNTIF', CORRESP: 'MATCH', 'ÍNDICE': 'INDEX', INDICE: 'INDEX', PROCV: 'VLOOKUP', PROCX: 'XLOOKUP', CONCATENAR: 'CONCATENATE', UNIRTEXTO: 'TEXTJOIN', 'NÚM.CARACT': 'LEN', 'NUM.CARACT': 'LEN', 'MAIÚSCULA': 'UPPER', MAIUSCULA: 'UPPER', 'MINÚSCULA': 'LOWER', MINUSCULA: 'LOWER', ARRUMAR: 'TRIM', ESQUERDA: 'LEFT', DIREITA: 'RIGHT', 'EXT.TEXTO': 'MID', SUBSTITUIR: 'SUBSTITUTE', HOJE: 'TODAY', AGORA: 'NOW', DATA: 'DATE', ANO: 'YEAR', 'MÊS': 'MONTH', MES: 'MONTH', DIA: 'DAY', SOMASES: 'SUMIFS', HIPERLINK: 'HYPERLINK', TEXTO: 'TEXT', SOMARPRODUTO: 'SUMPRODUCT', MED: 'MEDIAN', MAIOR: 'LARGE', MENOR: 'SMALL', MULT: 'PRODUCT', 'CONTAR.VAZIO': 'COUNTBLANK', 'ÉNÚM': 'ISNUMBER', ENUM: 'ISNUMBER', 'ÉTEXTO': 'ISTEXT', 'ÉCÉL.VAZIA': 'ISBLANK', 'ÉERRO': 'ISERROR', 'ARREDONDAR.PARA.CIMA': 'ROUNDUP', 'ARREDONDAR.PARA.BAIXO': 'ROUNDDOWN', TRUNCAR: 'TRUNC', PROCURAR: 'FIND', LOCALIZAR: 'SEARCH', 'PRI.MAIÚSCULA': 'PROPER', DIAS: 'DAYS', 'FIMMÊS': 'EOMONTH', ESCOLHER: 'CHOOSE', SES: 'IFS', 'CONT.SES': 'COUNTIFS', 'MÉDIASE': 'AVERAGEIF', 'MÉDIASES': 'AVERAGEIFS' };
function toEnglish(f) {
  const semi = f.includes(';');
  return f.slice(1).split(/("(?:[^"]|"")*")/).map((p, i) => i % 2 ? p : p
    .replace(/([A-Za-zÀ-ÿ_][\wÀ-ÿ.]*)\(/g, (m, n) => (EN[n.toUpperCase()] || n.toUpperCase()) + '(')
    .replace(/\bVERDADEIRO\b/gi, 'TRUE').replace(/\bFALSO\b/gi, 'FALSE')
    .replace(semi ? /(\d),(\d)/g : /$^/g, '$1.$2').replace(/;/g, ',')).join('');
}
const dateSerial = s => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s) || null; if (m) return Date.UTC(+m[1], +m[2] - 1, +m[3]) / 864e5 + 25569; const d = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s); return d ? Date.UTC(+d[3], +d[2] - 1, +d[1]) / 864e5 + 25569 : null; };
const col = n => colName(n);

/* ---- estilos ---- */
function makeStyles() {
  const fonts = ['<font><sz val="11"/><name val="Arial"/></font>'], fills = ['<fill><patternFill patternType="none"/></fill>', '<fill><patternFill patternType="gray125"/></fill>'];
  const borders = ['<border><left/><right/><top/><bottom/><diagonal/></border>'], xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'], map = new Map(), fmts = { currency: '"R$" #,##0.00', date: 'dd/mm/yyyy' };
  const ids = { currency: 164, date: 165, percent: 10, number: 4 };
  const rgb = h => 'FF' + String(h).replace('#', '').toUpperCase();
  const index = (arr, x) => { let i = arr.indexOf(x); if (i < 0) i = arr.push(x) - 1; return i; };
  function get(st) {
    st = st || {}; const key = JSON.stringify([st.bold, st.italic, st.underline, st.color, st.fill, st.fontSize, st.fontFamily, st.align, st.format, st.border]);
    if (key === '[null,null,null,null,null,null,null,null,null,null]') return 0;
    if (map.has(key)) return map.get(key);
    const font = `<font>${st.bold ? '<b/>' : ''}${st.italic ? '<i/>' : ''}${st.underline ? '<u/>' : ''}<sz val="${st.fontSize || 11}"/>${st.color ? `<color rgb="${rgb(st.color)}"/>` : ''}<name val="${esc(st.fontFamily || 'Arial')}"/></font>`;
    const fill = st.fill ? `<fill><patternFill patternType="solid"><fgColor rgb="${rgb(st.fill)}"/><bgColor indexed="64"/></patternFill></fill>` : null;
    const nf = ids[st.format] || 0, fi = index(fonts, font), fl = fill ? index(fills, fill) : 0;
    const sd = (k, n) => st.border?.[k] ? `<${n} style="thin"><color rgb="FF222222"/></${n}>` : `<${n}/>`, bi = st.border ? index(borders, `<border>${sd('l', 'left')}${sd('r', 'right')}${sd('t', 'top')}${sd('b', 'bottom')}<diagonal/></border>`) : 0;
    const xf = `<xf numFmtId="${nf}" fontId="${fi}" fillId="${fl}" borderId="${bi}" applyFont="1"${bi ? ' applyBorder="1"' : ''}${nf ? ' applyNumberFormat="1"' : ''}${fl ? ' applyFill="1"' : ''}${st.align ? ' applyAlignment="1"><alignment horizontal="' + st.align + '"/></xf>' : '/>'}`;
    const i = xfs.push(xf) - 1; map.set(key, i); return i;
  }
  const xml = () => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="2"><numFmt numFmtId="164" formatCode="${esc(fmts.currency)}"/><numFmt numFmtId="165" formatCode="${fmts.date}"/></numFmts><fonts count="${fonts.length}">${fonts.join('')}</fonts><fills count="${fills.length}">${fills.join('')}</fills><borders count="${borders.length}">${borders.join('')}</borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="${xfs.length}">${xfs.join('')}</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`;
  return { get, xml };
}

/* ---- planilha ---- */
function sheetXml(sh, styles, tail = '') {
  const rows = new Map();
  for (const a of Object.keys(sh.cells)) { const p = parseAddr(a); if (!p) continue; if (!rows.has(p.r)) rows.set(p.r, []); rows.get(p.r).push(p); }
  const H = window.InkHidden?.info(sh), ur = usedRange(sh); let data = '';
  if (H) for (const r of H.R) if (r <= ur.r2 && !rows.has(r)) rows.set(r, []);
  for (const r of [...rows.keys()].sort((x, y) => x - y)) {
    data += `<row r="${r + 1}"${H?.rows.has(r) ? ' hidden="1"' : ''}>`;
    for (const p of rows.get(r).sort((x, y) => x.c - y.c)) {
      const a = addr(p.r, p.c), cell = sh.cells[a], raw = cell.raw ?? '', st = { ...(cell.style || {}) }, isF = typeof raw === 'string' && raw.startsWith('=') && raw.length > 1;
      if (raw === '' && !Object.keys(st).length) continue;
      let v = InkEngine.evalCell(sh, a), t = '', body = '';
      if (typeof v === 'string' && dateSerial(v) !== null && (st.format === 'date' || isF)) { v = dateSerial(v); if (!st.format) st.format = 'date'; }
      if (raw === '') { data += `<c r="${a}" s="${styles.get(st)}"/>`; continue; }
      const f = isF ? `<f>${esc(toEnglish(raw))}</f>` : '';
      if (typeof v === 'number') body = `<v>${v}</v>`;
      else if (typeof v === 'boolean') { t = ' t="b"'; body = `<v>${+v}</v>`; }
      else if (InkEngine.ERRS.includes(v)) { t = ' t="e"'; body = `<v>${v}</v>`; }
      else if (isF) { t = ' t="str"'; body = `<v>${esc(v)}</v>`; }
      else { t = ' t="inlineStr"'; body = `<is><t xml:space="preserve">${esc(v)}</t></is>`; }
      data += `<c r="${a}" s="${styles.get(st)}"${t}>${f}${body}</c>`;
    }
    data += '</row>';
  }
  const ck = [...new Set([...Object.keys(sh.colWidths || {}).map(Number), ...(H?.C || []).filter(c => c <= ur.c2 + 50)])].sort((a, b) => a - b);
  const cols = ck.map(c => `<col min="${c + 1}" max="${c + 1}" width="${(((sh.colWidths || {})[c] || 96) / 7).toFixed(2)}" customWidth="1"${H?.cols.has(c) ? ' hidden="1"' : ''}/>`).join('');
  const fr = sh.frzR || 0, fc = sh.frzC || 0, pane = fr || fc ? `<sheetViews><sheetView workbookViewId="0"><pane${fc ? ` xSplit="${fc}"` : ''}${fr ? ` ySplit="${fr}"` : ''} topLeftCell="${addr(fr, fc)}" activePane="${fr && fc ? 'bottomRight' : fr ? 'bottomLeft' : 'topRight'}" state="frozen"/></sheetView></sheetViews>` : '';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">${pane}${cols ? `<cols>${cols}</cols>` : ''}<sheetData>${data}</sheetData>${tail}</worksheet>`;
}

const linkOf = (sh, a) => window.InkLinks?.urlOf(sh, a) || null;
function extras(sh, n) {
  const rels = [], files = [], types = []; let id = 0, hl = ''; const t0 = sh.tables?.[0]; let tail = t0 ? `<autoFilter ref="${addr(t0.h, t0.c1)}:${addr(t0.r2, t0.c2)}"/>` : '';
  for (const a of Object.keys(sh.cells)) { const u = linkOf(sh, a); if (u) { rels.push(`<Relationship Id="rId${++id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="${esc(u)}" TargetMode="External"/>`); hl += `<hyperlink ref="${a}" r:id="rId${id}"/>`; } }
  if (hl) tail += `<hyperlinks>${hl}</hyperlinks>`;
  const notes = Object.keys(sh.cells).filter(a => sh.cells[a].note);
  if (notes.length) {
    const vmlId = ++id, cmId = ++id;
    rels.push(`<Relationship Id="rId${vmlId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" Target="../drawings/vmlDrawing${n}.vml"/>`, `<Relationship Id="rId${cmId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments${n}.xml"/>`);
    tail += `<legacyDrawing r:id="rId${vmlId}"/>`;
    files.push([`xl/comments${n}.xml`, `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><authors><author>InkSheet</author></authors><commentList>${notes.map(a => `<comment ref="${a}" authorId="0"><text><r><t xml:space="preserve">${esc(sh.cells[a].note)}</t></r></text></comment>`).join('')}</commentList></comments>`]);
    files.push([`xl/drawings/vmlDrawing${n}.vml`, `<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel"><o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="${n}"/></o:shapelayout><v:shapetype id="_x0000_t202" coordsize="21600,21600" o:spt="202" path="m,l,21600r21600,l21600,xe"><v:stroke joinstyle="miter"/><v:path gradientshapeok="t" o:connecttype="rect"/></v:shapetype>${notes.map((a, i) => { const p = parseAddr(a); return `<v:shape id="_x0000_s${n * 1024 + i + 1}" type="#_x0000_t202" style="position:absolute;width:140pt;height:70pt;z-index:${i + 1};visibility:hidden" fillcolor="#ffffe1" o:insetmode="auto"><v:fill color2="#ffffe1"/><v:shadow on="t" color="black" obscured="t"/><v:path o:connecttype="none"/><v:textbox style="mso-direction-alt:auto"><div style="text-align:left"></div></v:textbox><x:ClientData ObjectType="Note"><x:MoveWithCells/><x:SizeWithCells/><x:Anchor>${p.c + 1}, 15, ${p.r}, 2, ${p.c + 3}, 15, ${p.r + 4}, 16</x:Anchor><x:AutoFill>False</x:AutoFill><x:Row>${p.r}</x:Row><x:Column>${p.c}</x:Column></x:ClientData></v:shape>`; }).join('')}</xml>`]);
    types.push(`<Override PartName="/xl/comments${n}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"/>`);
  }
  if (rels.length) files.push([`xl/worksheets/_rels/sheet${n}.xml.rels`, `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${rels.join('')}</Relationships>`]);
  return { tail, files, types };
}

/* ---- zip (sem compressão) ---- */
const T = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = b => { let c = -1; for (let i = 0; i < b.length; i++) c = T[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ -1) >>> 0; };
function zip(files) {
  const enc = new TextEncoder(), parts = [], cd = [], u16 = n => [n & 255, n >> 8 & 255], u32 = n => [n & 255, n >> 8 & 255, n >> 16 & 255, n >> 24 & 255]; let off = 0;
  for (const [name, str] of files) {
    const nm = enc.encode(name), d = enc.encode(str), c = crc(d);
    const lh = Uint8Array.from([0x50, 0x4b, 3, 4, ...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(c), ...u32(d.length), ...u32(d.length), ...u16(nm.length), ...u16(0)]);
    cd.push(Uint8Array.from([0x50, 0x4b, 1, 2, ...u16(20), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(c), ...u32(d.length), ...u32(d.length), ...u16(nm.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(off)]), nm);
    parts.push(lh, nm, d); off += lh.length + nm.length + d.length;
  }
  const size = cd.reduce((t, x) => t + x.length, 0), n = files.length;
  return new Blob([...parts, ...cd, Uint8Array.from([0x50, 0x4b, 5, 6, 0, 0, 0, 0, ...u16(n), ...u16(n), ...u32(size), ...u32(off), ...u16(0)])], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

function build(st, onlyActive) {
  InkEngine.clear();
  const sheets = onlyActive ? [st.sheets.find(s => s.id === st.activeSheetId) || st.sheets[0]] : st.sheets, styles = makeStyles(), used = new Set();
  const names = sheets.map(s => { let n = (s.name || 'Planilha').replace(/[\\/?*[\]:]/g, '-').slice(0, 31) || 'Planilha', k = 1; while (used.has(n.toLowerCase())) n = n.slice(0, 28) + '-' + ++k; used.add(n.toLowerCase()); return n; });
  const ns = 'xmlns="http://schemas.openxmlformats.org/', head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const files = [
    ['[Content_Types].xml', `${head}<Types ${ns}package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="vml" ContentType="application/vnd.openxmlformats-officedocument.vmlDrawing"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`],
    ['_rels/.rels', `${head}<Relationships ${ns}package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
    ['xl/workbook.xml', `${head}<workbook ${ns}spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${names.map((n, i) => `<sheet name="${esc(n)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets></workbook>`],
    ['xl/_rels/workbook.xml.rels', `${head}<Relationships ${ns}package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`],
  ];
  const ex = sheets.map((s, i) => extras(s, i + 1)), sx = sheets.map((s, i) => sheetXml(s, styles, ex[i].tail));
  files[0][1] = files[0][1].replace('</Types>', ex.flatMap(e => e.types).join('') + '</Types>'); ex.forEach(e => files.push(...e.files));
  files.push(['xl/styles.xml', styles.xml()], ...sx.map((x, i) => [`xl/worksheets/sheet${i + 1}.xml`, x]));
  return zip(files);
}
window.InkXlsx = { build };

const run = onlyActive => { titleInput.value && (state.title = titleInput.value.trim() || state.title); downloadBlob(build(state, onlyActive), `${safeName(state.title)}${onlyActive ? '-' + safeName(activeSheet().name) : ''}.xlsx`); };
const menuAll = $('#menuExportXls'); menuAll.textContent = 'Exportar pasta inteira (.xlsx)'; menuAll.onclick = () => run(false);
const menuOne = document.createElement('button'); menuOne.type = 'button'; menuOne.textContent = 'Exportar aba atual (.xlsx)'; menuOne.onclick = () => run(true);
menuAll.after(menuOne);
})();
