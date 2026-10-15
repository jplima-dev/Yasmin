/* InkSheet engine.js — motor de fórmulas. Carregar DEPOIS de editor.js. */
(() => {
const MAXR = 1048576, MAXC = 16384, MS = 864e5;
const ERRS = ['#REF!', '#VALUE!', '#NAME?', '#DIV/0!', '#CIRC!', '#N/A', '#NUM!', '#ERROR!'];
class FErr { constructor(c) { this.code = c; } }
const fail = c => { throw new FErr(c); };
class Rng { constructor(rows) { this.rows = rows; } }
const cache = new Map(), visiting = new Set(), asts = new Map();

function parseNum(s) {
  s = String(s).trim().replace(/^([-+]?)\s*R\$\s*/, '$1'); if (s === '') return null;
  if (/^[-+]?\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) return Number(s.replace(/\./g, '').replace(',', '.'));
  if (/^[-+]?(\d+([.,]\d*)?|[.,]\d+)(e[-+]?\d+)?$/i.test(s)) return Number(s.replace(',', '.'));
  if (/^[-+]?[\d.,]+%$/.test(s)) { const n = parseNum(s.slice(0, -1)); return n === null ? null : n / 100; }
  return null;
}
function parseDate(s) {
  let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s), y, mo, d;
  if (m) [y, mo, d] = [+m[1], +m[2], +m[3]];
  else if ((m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s))) [d, mo, y] = [+m[1], +m[2], +m[3]];
  else return null;
  return Date.UTC(y, mo - 1, d) / MS + 25569;
}
const serialDate = n => new Date(Math.round((n - 25569) * MS));
const iso = n => serialDate(n).toISOString().slice(0, 10);
function toNum(v) {
  if (v instanceof Rng) v = v.rows[0]?.[0];
  if (typeof v === 'number') return v;
  if (typeof v === 'boolean') return +v;
  if (v === '' || v == null) return 0;
  const n = parseNum(v); if (n !== null) return n;
  const d = parseDate(String(v)); if (d !== null) return d;
  return fail('#VALUE!');
}
const toBool = v => typeof v === 'boolean' ? v : toNum(v) !== 0;
const txt = v => v instanceof Rng ? txt(v.rows[0]?.[0]) : v == null ? '' : typeof v === 'boolean' ? (v ? 'VERDADEIRO' : 'FALSO') : typeof v === 'number' ? String(Math.round(v * 1e10) / 1e10) : String(v);

/* ---------- lexer / parser ---------- */
function lex(src) {
  const dec = src.includes(';');
  const T = [[/(?:'(?:[^']|'')+'|[A-Za-zÀ-ÿ_][\wÀ-ÿ.]*)!\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?(?![\w(.])/y, 'xref'], [/"(?:[^"]|"")*"/y, 's'], [/\$?[A-Za-z]{1,3}\$?\d+(?![\w(.])/y, 'ref'],
    [/\$?[A-Za-z]{1,3}:\$?[A-Za-z]{1,3}(?![\w(.])/y, 'col'],
    [null, 'n'], [/[A-Za-zÀ-ÿ_][\wÀ-ÿ.]*/y, 'id'],
    [/<=|>=|<>|!=|[-+*\/^%=(),:;<>&]/y, 'op']];
  const out = [], stack = []; let i = 0; const RD = /\d+(?:\.\d+)?|\.\d+/y, RC = /\d+(?:[.,]\d+)?|,\d+/y; // vírgula decimal: com ';' na fórmula ou fora de chamada de função
  while (i < src.length) {
    if (/\s/.test(src[i])) { i++; continue; }
    let ok = false;
    for (const [r0, t] of T) {
      const re = t === 'n' ? (dec || stack[stack.length - 1] !== 'f' ? RC : RD) : r0; re.lastIndex = i; const m = re.exec(src);
      if (m) {
        if (t === 'op') { if (m[0] === '(') stack.push(out.length && out[out.length - 1].t === 'id' ? 'f' : 'g'); else if (m[0] === ')') stack.pop(); }
        out.push({ t, v: m[0] }); i += m[0].length; ok = true; break;
      }
    }
    if (!ok) fail('#NAME?');
  }
  return out;
}
const refOf = s => {
  const m = /^\$?([A-Za-z]+)\$?(\d+)$/.exec(s), c = colIndex(m[1]), r = +m[2] - 1;
  if (c >= MAXC || r < 0 || r >= MAXR) fail('#REF!');
  return { c, r };
};
function parse(src) {
  if (asts.has(src)) return asts.get(src);
  const tk = lex(src), dec = src.includes(';'); let p = 0;
  const eat = v => { if (tk[p] && tk[p].t === 'op' && tk[p].v === v) { p++; return true; } return false; };
  const bin = (next, ops) => () => { let l = next(); while (tk[p] && tk[p].t === 'op' && ops.includes(tk[p].v)) { const op = tk[p++].v; l = { k: 'bin', op, l, r: next() }; } return l; };
  let expr;
  const prim = () => {
    const t = tk[p++]; if (!t) return fail('#ERROR!');
    if (t.t === 'op' && t.v === '(') { const e = expr(); if (!eat(')')) fail('#ERROR!'); return e; }
    if (t.t === 'n') return { k: 'v', v: Number(t.v.replace(',', '.')) };
    if (t.t === 's') return { k: 'v', v: t.v.slice(1, -1).replace(/""/g, '"') };
    if (t.t === 'xref') { const i = t.v.lastIndexOf('!'), nm = t.v.slice(0, i).replace(/^'|'$/g, '').replace(/''/g, "'"), [x, y] = t.v.slice(i + 1).split(':'); return y ? { k: 'rng', sh: nm, a: refOf(x), b: refOf(y) } : { k: 'ref', sh: nm, a: refOf(x) }; }
    if (t.t === 'col') { const [x, y] = t.v.replace(/\$/g, '').split(':'); return { k: 'rng', a: { c: colIndex(x), r: 0 }, b: { c: colIndex(y), r: MAXR - 1 } }; }
    if (t.t === 'ref') {
      const a = refOf(t.v);
      if (eat(':')) { const u = tk[p++]; if (!u || u.t !== 'ref') fail('#REF!'); return { k: 'rng', a, b: refOf(u.v) }; }
      return { k: 'ref', a };
    }
    if (t.t === 'id') {
      const n = t.v.toUpperCase();
      if (eat('(')) {
        const args = [];
        if (!eat(')')) { do args.push(expr()); while (eat(',') || eat(';')); if (!eat(')')) fail('#ERROR!'); }
        return { k: 'fn', n, args };
      }
      if (n === 'TRUE' || n === 'VERDADEIRO') return { k: 'v', v: true };
      if (n === 'FALSE' || n === 'FALSO') return { k: 'v', v: false };
      fail('#NAME?');
    }
    return fail('#ERROR!');
  };
  const post = () => { let e = prim(); while (eat('%')) e = { k: 'bin', op: '%', l: e }; return e; };
  const un = () => eat('-') ? { k: 'un', x: un() } : eat('+') ? un() : pw();
  const pw = () => { let l = post(); while (eat('^')) l = { k: 'bin', op: '^', l, r: un() }; return l; };
  expr = bin(bin(bin(bin(un, ['*', '/']), ['+', '-']), ['&']), ['=', '<>', '!=', '<', '>', '<=', '>=']);
  const ast = expr(); if (p < tk.length) fail('#ERROR!');
  asts.set(src, ast); return ast;
}

/* ---------- avaliação ---------- */
function cmp(op, a, b) {
  let x = a, y = b;
  if (typeof a === 'string' && typeof b === 'string') { const da = parseDate(a), db = parseDate(b); if (da !== null && db !== null) { x = da; y = db; } else { x = a.toLowerCase(); y = b.toLowerCase(); } }
  else { try { x = toNum(a); y = toNum(b); } catch { x = txt(a).toLowerCase(); y = txt(b).toLowerCase(); } }
  switch (op) { case '=': return x === y; case '<>': case '!=': return x !== y; case '<': return x < y; case '>': return x > y; case '<=': return x <= y; default: return x >= y; }
}
const usedOf = sh => { const k = sh.id + '#u'; if (!cache.has(k)) cache.set(k, usedRange(sh)); return cache.get(k); };
const tsh = (n, sh) => n.sh ? (state.sheets.find(x => x.name.toLowerCase() === n.sh.toLowerCase()) || fail('#REF!')) : sh;
function ev(n, sh) {
  switch (n.k) {
    case 'v': return n.v;
    case 'ref': { const v = evalCell(tsh(n, sh), addr(n.a.r, n.a.c)); if (ERRS.includes(v)) fail(v); return v; }
    case 'rng': {
      const T = tsh(n, sh), u = usedOf(T), r1 = Math.min(n.a.r, n.b.r), c1 = Math.min(n.a.c, n.b.c), c2 = Math.max(n.a.c, n.b.c);
      const r2 = Math.min(Math.max(n.a.r, n.b.r), Math.max(u.r2, r1)), rows = [];
      for (let r = r1; r <= r2; r++) { const row = []; for (let c = c1; c <= c2; c++) row.push(evalCell(T, addr(r, c))); rows.push(row); }
      return new Rng(rows);
    }
    case 'un': return -toNum(ev(n.x, sh));
    case 'bin': {
      const op = n.op; if (op === '%') return toNum(ev(n.l, sh)) / 100;
      const a = ev(n.l, sh), b = ev(n.r, sh);
      if (op === '&') return txt(a) + txt(b);
      if (['=', '<>', '!=', '<', '>', '<=', '>='].includes(op)) return cmp(op, a instanceof Rng ? a.rows[0][0] : a, b instanceof Rng ? b.rows[0][0] : b);
      const x = toNum(a), y = toNum(b);
      if (op === '/') return y === 0 ? fail('#DIV/0!') : x / y;
      const v = op === '+' ? x + y : op === '-' ? x - y : op === '*' ? x * y : Math.pow(x, y);
      if (!Number.isFinite(v)) return fail('#NUM!');
      if (op === '+' || op === '-') { const isD = q => typeof q === 'string' && parseDate(q) !== null, da = isD(a), db = isD(b); if ((op === '+' && da !== db) || (op === '-' && da && !db)) return iso(v); } // data ± dias = data
      return v;
    }
    case 'fn': { const f = FN[n.n]; return f ? f(n.args, sh) : fail('#NAME?'); }
  }
}
function evalCell(sh, a) {
  const k = sh.id + '!' + a; if (cache.has(k)) return cache.get(k);
  const cell = sh.cells[a]; if (!cell) return '';
  let v = cell.raw ?? '';
  if (typeof v === 'string') {
    if (v.startsWith('=') && v.length > 1) {
      if (visiting.has(k)) return '#CIRC!';
      visiting.add(k);
      try { v = ev(parse(v.slice(1)), sh); if (v instanceof Rng) v = v.rows[0]?.[0] ?? ''; }
      catch (e) { v = e instanceof FErr ? e.code : '#ERROR!'; }
      finally { visiting.delete(k); }
    } else { const n = parseNum(v); if (n !== null && !/^[-+]?0\d/.test(v)) v = n; }
  }
  cache.set(k, v); return v;
}

/* ---------- funções ---------- */
const FN = {}, def = (names, f) => names.split('|').forEach(n => FN[n] = f);
const sc = (n, s) => { const v = ev(n, s); return v instanceof Rng ? v.rows[0]?.[0] ?? '' : v; };
const rg = (n, s) => { const v = ev(n, s); return v instanceof Rng ? v : new Rng([[v]]); };
const fl = (args, s) => args.map(a => ev(a, s)).flatMap(v => v instanceof Rng ? v.rows.flat() : [v]).map(v => ERRS.includes(v) ? fail(v) : v);
const ns = (a, s) => fl(a, s).filter(v => typeof v === 'number');
const sum = a => a.reduce((x, y) => x + y, 0);
const eq = (a, b) => typeof a === 'number' && typeof b === 'number' ? a === b : txt(a).toLowerCase() === txt(b).toLowerCase();
function crit(c) {
  if (typeof c !== 'string') return v => eq(v, c);
  const m = /^(<=|>=|<>|=|<|>)?([\s\S]*)$/.exec(c), op = m[1] || '=', rhs = m[2], n = parseNum(rhs);
  return v => {
    if (n !== null && typeof v === 'number') return cmp(op, v, n);
    if (op !== '=' && op !== '<>') return false;
    const re = new RegExp('^' + rhs.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$', 'i');
    return re.test(txt(v)) === (op === '=');
  };
}
def('SUM|SOMA', (a, s) => sum(ns(a, s)));
def('AVERAGE|MÉDIA|MEDIA', (a, s) => { const n = ns(a, s); return n.length ? sum(n) / n.length : fail('#DIV/0!'); });
def('MIN|MÍNIMO|MINIMO', (a, s) => { const n = ns(a, s); return n.length ? Math.min(...n) : 0; });
def('MAX|MÁXIMO|MAXIMO', (a, s) => { const n = ns(a, s); return n.length ? Math.max(...n) : 0; });
def('COUNT|CONT.NÚM|CONT.NUM', (a, s) => ns(a, s).length);
def('COUNTA|CONT.VALORES', (a, s) => fl(a, s).filter(v => v !== '' && v != null).length);
def('IF|SE', (a, s) => toBool(sc(a[0], s)) ? (a[1] ? ev(a[1], s) : true) : (a[2] ? ev(a[2], s) : false));
def('IFERROR|SEERRO', (a, s) => { try { return sc(a[0], s); } catch (e) { if (e instanceof FErr) return ev(a[1], s); throw e; } });
def('AND|E', (a, s) => fl(a, s).every(toBool));
def('OR|OU', (a, s) => fl(a, s).some(toBool));
def('NOT|NÃO|NAO', (a, s) => !toBool(sc(a[0], s)));
def('ROUND|ARRED', (a, s) => { const m = 10 ** (a[1] ? Math.trunc(toNum(ev(a[1], s))) : 0); return Math.round(toNum(sc(a[0], s)) * m) / m; });
def('ABS', (a, s) => Math.abs(toNum(sc(a[0], s))));
def('INT', (a, s) => Math.floor(toNum(sc(a[0], s))));
def('MOD|RESTO', (a, s) => { const d = toNum(sc(a[1], s)); return d === 0 ? fail('#DIV/0!') : toNum(sc(a[0], s)) % d; });
def('POWER|POTÊNCIA|POTENCIA', (a, s) => Math.pow(toNum(sc(a[0], s)), toNum(sc(a[1], s))));
def('SQRT|RAIZ', (a, s) => { const n = toNum(sc(a[0], s)); return n < 0 ? fail('#NUM!') : Math.sqrt(n); });
def('SUMIF|SOMASE', (a, s) => { const R = rg(a[0], s).rows.flat(), S = (a[2] ? rg(a[2], s) : { rows: [R] }).rows.flat(), f = crit(sc(a[1], s)); return R.reduce((t, v, i) => f(v) && typeof S[i] === 'number' ? t + S[i] : t, 0); });
def('COUNTIF|CONT.SE', (a, s) => { const f = crit(sc(a[1], s)); return rg(a[0], s).rows.flat().filter(f).length; });
const masks = (a, s, from) => { let mask = null; for (let i = from; i + 1 < a.length; i += 2) { const R = rg(a[i], s).rows.flat(), f = crit(sc(a[i + 1], s)); mask = (mask || R.map(() => true)).map((m, j) => m && f(R[j])); } return mask || []; };
const pick = (a, s, mask) => rg(a, s).rows.flat().filter((v, i) => mask[i] && typeof v === 'number');
def('SUMIFS|SOMASES', (a, s) => sum(pick(a[0], s, masks(a, s, 1))));
def('COUNTIFS|CONT.SES', (a, s) => masks(a, s, 0).filter(Boolean).length);
def('AVERAGEIF|MÉDIASE', (a, s) => { const R = rg(a[0], s).rows.flat(), f = crit(sc(a[1], s)), V = (a[2] ? rg(a[2], s) : { rows: [R] }).rows.flat().filter((v, i) => f(R[i]) && typeof v === 'number'); return V.length ? sum(V) / V.length : fail('#DIV/0!'); });
def('AVERAGEIFS|MÉDIASES', (a, s) => { const V = pick(a[0], s, masks(a, s, 1)); return V.length ? sum(V) / V.length : fail('#DIV/0!'); });
def('MATCH|CORRESP', (a, s) => {
  const v = sc(a[0], s), L = rg(a[1], s).rows.flat(), t = a[2] ? toNum(sc(a[2], s)) : 1; let idx = -1;
  if (t === 0) idx = L.findIndex(x => eq(x, v));
  else for (let i = 0; i < L.length; i++) { if (L[i] === '') continue; if (t > 0 ? cmp('<=', L[i], v) : cmp('>=', L[i], v)) idx = i; else break; }
  return idx < 0 ? fail('#N/A') : idx + 1;
});
def('INDEX|ÍNDICE|INDICE', (a, s) => {
  const R = rg(a[0], s).rows; let r = a[1] ? toNum(sc(a[1], s)) : 1, c = a[2] ? toNum(sc(a[2], s)) : 1;
  if (R.length === 1 && !a[2]) { c = r; r = 1; }
  const v = R[r - 1]?.[c - 1]; return v === undefined ? fail('#REF!') : v;
});
def('VLOOKUP|PROCV', (a, s) => {
  const v = sc(a[0], s), R = rg(a[1], s).rows, i = toNum(sc(a[2], s)), exact = a[3] && !toBool(sc(a[3], s)); let hit = -1;
  if (exact) hit = R.findIndex(r => eq(r[0], v));
  else for (let k = 0; k < R.length; k++) { if (R[k][0] === '') continue; if (cmp('<=', R[k][0], v)) hit = k; else break; }
  if (hit < 0) fail('#N/A'); if (i < 1 || i > R[hit].length) fail('#REF!'); return R[hit][i - 1];
});
def('XLOOKUP|PROCX', (a, s) => {
  const v = sc(a[0], s), L = rg(a[1], s).rows.flat(), Rt = rg(a[2], s).rows.flat(), i = L.findIndex(x => eq(x, v));
  return i < 0 ? (a[3] ? ev(a[3], s) : fail('#N/A')) : Rt[i] ?? '';
});
def('CONCAT|CONCATENAR|CONCATENATE', (a, s) => fl(a, s).map(txt).join(''));
def('TEXTJOIN|UNIRTEXTO', (a, s) => { const d = txt(sc(a[0], s)), ig = toBool(sc(a[1], s)); return fl(a.slice(2), s).filter(v => !ig || v !== '').map(txt).join(d); });
def('LEN|NÚM.CARACT|NUM.CARACT', (a, s) => txt(sc(a[0], s)).length);
def('UPPER|MAIÚSCULA|MAIUSCULA', (a, s) => txt(sc(a[0], s)).toUpperCase());
def('LOWER|MINÚSCULA|MINUSCULA', (a, s) => txt(sc(a[0], s)).toLowerCase());
def('TRIM|ARRUMAR', (a, s) => txt(sc(a[0], s)).trim().replace(/\s+/g, ' '));
def('LEFT|ESQUERDA', (a, s) => txt(sc(a[0], s)).slice(0, a[1] ? toNum(sc(a[1], s)) : 1));
def('RIGHT|DIREITA', (a, s) => { const t = txt(sc(a[0], s)), n = a[1] ? toNum(sc(a[1], s)) : 1; return n ? t.slice(-n) : ''; });
def('MID|EXT.TEXTO', (a, s) => { const st = toNum(sc(a[1], s)) - 1; return txt(sc(a[0], s)).substr(Math.max(0, st), toNum(sc(a[2], s))); });
def('SUBSTITUTE|SUBSTITUIR', (a, s) => txt(sc(a[0], s)).split(txt(sc(a[1], s))).join(txt(sc(a[2], s))));
const p2 = n => String(n).padStart(2, '0');
def('TODAY|HOJE', () => { const d = new Date(); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`; });
def('NOW|AGORA', () => new Date().toLocaleString('pt-BR'));
def('DATE|DATA', (a, s) => iso(Date.UTC(toNum(sc(a[0], s)), toNum(sc(a[1], s)) - 1, toNum(sc(a[2], s))) / MS + 25569));
def('YEAR|ANO', (a, s) => serialDate(toNum(sc(a[0], s))).getUTCFullYear());
def('MONTH|MÊS|MES', (a, s) => serialDate(toNum(sc(a[0], s))).getUTCMonth() + 1);
def('DAY|DIA', (a, s) => serialDate(toNum(sc(a[0], s))).getUTCDate());

const rnd = f => (a, s) => { const m = 10 ** (a[1] ? Math.trunc(toNum(sc(a[1], s))) : 0); return f(toNum(sc(a[0], s)) * m) / m; };
const srt = (a, s, d) => ns([a[0]], s).sort((x, y) => d * (x - y));
const blank = v => v === '' || v == null;
def('TEXT|TEXTO', (a, s) => {
  const v = sc(a[0], s), f = txt(sc(a[1], s)), bare = f.replace(/"[^"]*"/g, '');
  if (/[dmya]/i.test(bare) && !/[0#]/.test(bare)) {
    const d = serialDate(toNum(v)), p = x => String(x).padStart(2, '0');
    return f.replace(/yyyy|aaaa/gi, d.getUTCFullYear()).replace(/yy|aa/gi, String(d.getUTCFullYear()).slice(2)).replace(/dd/gi, p(d.getUTCDate())).replace(/mm/gi, p(d.getUTCMonth() + 1)).replace(/d/gi, d.getUTCDate()).replace(/m/gi, d.getUTCMonth() + 1);
  }
  let n = toNum(v); const pct = f.includes('%'); if (pct) n *= 100;
  const m = /^([^0#]*)([0#.,]*[0#])(.*)$/.exec(f.replace(/"/g, '')) || ['', '', '0', ''], thou = /#[.,]##0/.test(m[2]), b2 = m[2].replace(/#[.,]##0/, '0'), dm = /[.,]([0#]+)$/.exec(b2), dec = dm ? dm[1].length : 0;
  return m[1] + n.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec, useGrouping: thou }) + (pct ? '%' : '') + m[3].replace('%', '');
});
def('SUMPRODUCT|SOMARPRODUTO', (a, s) => { const L = a.map(x => rg(x, s).rows.flat()); return L[0].reduce((t, _, i) => t + L.reduce((p, l) => p * (typeof l[i] === 'number' ? l[i] : 0), 1), 0); });
def('MEDIAN|MED', (a, s) => { const n = ns(a, s).sort((x, y) => x - y), m = n.length >> 1; return n.length ? (n.length % 2 ? n[m] : (n[m - 1] + n[m]) / 2) : fail('#NUM!'); });
def('LARGE|MAIOR', (a, s) => srt(a, s, -1)[toNum(sc(a[1], s)) - 1] ?? fail('#NUM!'));
def('SMALL|MENOR', (a, s) => srt(a, s, 1)[toNum(sc(a[1], s)) - 1] ?? fail('#NUM!'));
def('PRODUCT|MULT', (a, s) => ns(a, s).reduce((x, y) => x * y, 1));
def('COUNTBLANK|CONTAR.VAZIO', (a, s) => rg(a[0], s).rows.flat().filter(blank).length);
def('ISNUMBER|ÉNÚM|ENUM', (a, s) => typeof sc(a[0], s) === 'number');
def('ISTEXT|ÉTEXTO|ETEXTO', (a, s) => { const v = sc(a[0], s); return typeof v === 'string' && v !== ''; });
def('ISBLANK|ÉCÉL.VAZIA|ECEL.VAZIA', (a, s) => blank(sc(a[0], s)));
def('ISERROR|ÉERRO|EERRO', (a, s) => { try { sc(a[0], s); return false; } catch (e) { if (e instanceof FErr) return true; throw e; } });
def('ROUNDUP|ARREDONDAR.PARA.CIMA', rnd(x => x < 0 ? -Math.ceil(-x) : Math.ceil(x)));
def('ROUNDDOWN|ARREDONDAR.PARA.BAIXO|TRUNC|TRUNCAR', rnd(Math.trunc));
def('PROPER|PRI.MAIÚSCULA|PRI.MAIUSCULA', (a, s) => txt(sc(a[0], s)).toLowerCase().replace(/(^|[^a-zà-ÿ])([a-zà-ÿ])/g, (m, p, c) => p + c.toUpperCase()));
def('FIND|PROCURAR', (a, s) => { const i = txt(sc(a[1], s)).indexOf(txt(sc(a[0], s)), a[2] ? toNum(sc(a[2], s)) - 1 : 0); return i < 0 ? fail('#VALUE!') : i + 1; });
def('SEARCH|LOCALIZAR', (a, s) => { const i = txt(sc(a[1], s)).toLowerCase().indexOf(txt(sc(a[0], s)).toLowerCase(), a[2] ? toNum(sc(a[2], s)) - 1 : 0); return i < 0 ? fail('#VALUE!') : i + 1; });
def('DAYS|DIAS', (a, s) => toNum(sc(a[0], s)) - toNum(sc(a[1], s)));
def('EOMONTH|FIMMÊS|FIMMES', (a, s) => { const d = serialDate(toNum(sc(a[0], s))); return iso(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + toNum(sc(a[1], s)) + 1, 0) / MS + 25569); });
def('CHOOSE|ESCOLHER', (a, s) => { const i = toNum(sc(a[0], s)); return a[i] ? ev(a[i], s) : fail('#VALUE!'); });
def('IFS|SES', (a, s) => { for (let i = 0; i + 1 < a.length; i += 2) if (toBool(sc(a[i], s))) return ev(a[i + 1], s); return fail('#N/A'); });
def('EXP', (a, s) => Math.exp(toNum(sc(a[0], s))));
def('LN', (a, s) => { const n = toNum(sc(a[0], s)); return n > 0 ? Math.log(n) : fail('#NUM!'); });
def('PI', () => Math.PI);
def('HYPERLINK|HIPERLINK', (a, s) => sc(a[1] || a[0], s));

/* ---------- ajuste de referências (preencher / colar) ---------- */
function shiftFormula(raw, dr, dc) {
  return raw.split(/("(?:[^"]|"")*")/).map((p, i) => i % 2 ? p : p.replace(/(?<![\w.$])(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![\w(.!])/g, (m, ac, col, ar, row) => {
    let c = colIndex(col), r = +row - 1; if (!ac) c += dc; if (!ar) r += dr;
    return c < 0 || r < 0 || c >= MAXC || r >= MAXR ? '#REF!' : `${ac}${colName(c)}${ar}${r + 1}`;
  })).join('');
}

window.InkEngine = { evalCell, shiftFormula, parseNum, clear: () => cache.clear(), ERRS, MAXR, MAXC };
window.evaluateCell = (sh, a) => evalCell(sh, a);
const _fv = window.formatValue;
window.formatValue = (v, st = {}) => {
  if (typeof v === 'number' && st.format === 'date' && v > 0 && v < 2958466) return serialDate(v).toLocaleDateString('pt-BR', { timeZone: 'UTC' });
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return v.split('-').reverse().join('/');
  if (typeof v === 'boolean') return v ? 'VERDADEIRO' : 'FALSO';
  if (typeof v === 'number' && (!st.format || st.format === 'general')) return Number.isFinite(v) ? v.toLocaleString('pt-BR', { maximumFractionDigits: 10, useGrouping: false }) : '#NUM!';
  return _fv(v, st);
};
})();
