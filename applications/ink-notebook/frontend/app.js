'use strict';
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtSize = n => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
const fmtDate = iso => iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '';
const plural = (n, a, b) => `${n} ${n === 1 ? a : b}`;

async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {} };
  if (opts.json !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.json); }
  if (opts.form) init.body = opts.form;
  let r;
  try { r = await fetch('/api' + path, init); } catch { throw new Error('Não consegui falar com o servidor local. Ele ainda está rodando?'); }
  let data = null; try { data = await r.json(); } catch { }
  if (!r.ok) throw new Error((data && data.error) || `Erro ${r.status}`);
  return data;
}

function toast(msg, kind = '') {
  const t = document.createElement('div');
  t.className = 'toast ' + kind; t.textContent = msg;
  $('#toasts').append(t); setTimeout(() => t.remove(), kind === 'error' ? 7000 : 3500);
}

/* ---------- diálogo simples (promessa) ---------- */
function ask({ title, message = '', input = null, ok = 'OK', danger = false }) {
  return new Promise(resolve => {
    const d = $('#dlg'), inp = $('#dlg-input');
    $('#dlg-title').textContent = title; $('#dlg-msg').textContent = message;
    inp.hidden = input === null; inp.value = input ?? '';
    const okb = $('#dlg-ok'); okb.textContent = ok; okb.className = 'btn ' + (danger ? 'danger' : 'primary');
    $('#dlg-cancel').onclick = () => d.close('cancel');
    d.onclose = () => resolve(d.returnValue === 'ok' ? (input === null ? true : inp.value.trim()) : null);
    d.showModal(); if (input !== null) { inp.focus(); inp.select(); }
  });
}

/* ---------- atividade (vem do backend) ---------- */
let actOpen = false;
async function refreshActivity() {
  try {
    const items = await api('/activity?limit=60');
    const last = items[0];
    if (last) {
      $('#act-last').textContent = `${last.ts.slice(11)}  ${last.message}`;
      $('#act-dot').className = 'dot ' + (state.busy ? 'busy' : last.level === 'error' ? 'error' : last.level === 'warn' ? 'warn' : '');
    }
    $('#act-list').innerHTML = items.map(a => `<div class="${a.level}"><time>${a.ts.slice(11)}</time><span>${esc(a.message)}</span></div>`).join('') || '<div class="muted">Sem atividade ainda.</div>';
  } catch { }
}
$('#act-bar').onclick = () => { actOpen = !actOpen; $('#act-list').hidden = !actOpen; if (actOpen) refreshActivity(); };
setInterval(() => { if (!document.hidden) refreshActivity(); }, 3000);

/* ---------- estado e rotas ---------- */
const state = { nb: null, docs: [], result: null, query: '', busy: false, poll: null };
const view = $('#view');

function crumbs(parts) {
  $('#crumbs').innerHTML = parts.map(p => `<span>/</span><b>${esc(p)}</b>`).join('');
}

async function route() {
  clearTimeout(state.poll); closePreview();
  const h = location.hash.replace(/^#/, '') || '/';
  try {
    let m;
    if ((m = h.match(/^\/n\/(\d+)$/))) await notebookView(+m[1]);
    else if ((m = h.match(/^\/c\/(\d+)$/))) await window.CodeNotebook.render(view, +m[1]);
    else if (h === '/settings') await settingsView();
    else await homeView();
  } catch (e) {
    view.innerHTML = `<div class="empty"><b>Algo deu errado</b>${esc(e.message)}<br><br><a class="btn" href="#/">Voltar aos cadernos</a></div>`;
  }
  refreshActivity();
}
window.addEventListener('hashchange', route);

/* ---------- cadernos ---------- */
async function homeView() {
  crumbs([]);
  const list = await api('/notebooks');
  view.innerHTML = `
    <div class="page-head"><h1>Cadernos</h1><button class="btn primary" id="new-nb">+ Novo caderno</button></div>
    ${list.length ? `<div class="grid">${list.map(n => `
      <div class="card" data-id="${n.id}">
        <h3>${esc(n.name)}</h3>
        <div class="muted">${plural(n.doc_count, 'documento', 'documentos')} · ${fmtSize(n.total_size)}</div>
        <div class="muted" style="font-size:11.5px">criado em ${fmtDate(n.created_at)}</div>
        <div class="row"><button class="btn sm" data-act="code">Código</button><button class="btn sm" data-act="rename">Renomear</button><button class="btn sm danger" data-act="del">Excluir</button></div>
      </div>`).join('')}</div>` :
      `<div class="empty"><b>Nenhum caderno ainda</b>Crie um caderno e arraste seus .md, .txt, código ou PDFs para dentro dele.</div>`}`;
  $('#new-nb').onclick = createNotebook;
  view.querySelectorAll('.card').forEach(card => {
    const id = +card.dataset.id, nb = list.find(n => n.id === id);
    card.onclick = e => {
      const act = e.target.dataset.act;
      if (act === 'code') return (location.hash = `#/c/${id}`);
      if (act === 'rename') return renameNotebook(nb);
      if (act === 'del') return deleteNotebook(nb);
      location.hash = `#/n/${id}`;
    };
  });
}
async function createNotebook() {
  const name = await ask({ title: 'Novo caderno', message: 'Dê um nome (ex.: Workspace, Faculdade).', input: '', ok: 'Criar' });
  if (name === null) return;
  try { const r = await api('/notebooks', { method: 'POST', json: { name } }); location.hash = `#/n/${r.id}`; }
  catch (e) { toast(e.message, 'error'); }
}
async function renameNotebook(nb) {
  const name = await ask({ title: 'Renomear caderno', input: nb.name, ok: 'Salvar' });
  if (name === null) return;
  try { await api(`/notebooks/${nb.id}`, { method: 'PATCH', json: { name } }); route(); } catch (e) { toast(e.message, 'error'); }
}
async function deleteNotebook(nb) {
  const ok = await ask({ title: `Excluir “${nb.name}”?`, message: 'Os arquivos adicionados a este caderno (cópias em data/notebooks) e o índice serão apagados. Seus arquivos originais fora do app não são tocados.', ok: 'Excluir', danger: true });
  if (!ok) return;
  try { await api(`/notebooks/${nb.id}`, { method: 'DELETE' }); toast('Caderno excluído.'); if (location.hash.startsWith('#/n/')) location.hash = '#/'; else route(); }
  catch (e) { toast(e.message, 'error'); }
}

/* ---------- tela do caderno ---------- */
async function notebookView(id) {
  const data = await api(`/notebooks/${id}`);
  state.nb = data.notebook; state.docs = data.documents; state.result = null; state.query = '';
  crumbs([state.nb.name]);
  view.innerHTML = `
    <div class="page-head"><h1>${esc(state.nb.name)}</h1>
      <a class="btn sm" id="nb-code" href="#/c/${id}" title="Indexar e perguntar sobre um projeto de código">Código</a><button class="btn sm" id="nb-rename">Renomear</button><button class="btn sm" id="nb-reindex" title="Relê os arquivos da pasta de fontes">Reconstruir índice</button><button class="btn sm danger" id="nb-del">Excluir</button></div>
    <div class="layout">
      <section class="panel sources">
        <div class="panel-head">Fontes <span class="cnt" id="src-count"></span></div>
        <div class="dropzone" id="dropzone"><b>Arraste arquivos ou pastas aqui</b>.md .txt .py .js .json .csv .pdf …<br>
          <div class="row" style="justify-content:center; gap:8px; margin-top:8px">
            <button class="btn sm" id="pick">Selecionar arquivos</button>
            <button class="btn sm" id="pick-folder">Selecionar pasta</button>
          </div>
          <input type="file" id="file-input" multiple hidden>
          <input type="file" id="folder-input" webkitdirectory hidden>
        </div>
        <div class="doc-list" id="doc-list"></div>
      </section>
      <section class="panel">
        <div class="searchbox"><input id="q" type="search" placeholder="Pesquise ou pergunte dentro deste caderno…  ( / )" autocomplete="off"><button class="btn primary" id="go">Buscar</button></div>
    
        <div id="results"></div>
      </section>
    </div>`;
  $('#nb-rename').onclick = () => renameNotebook(state.nb);
  $('#nb-del').onclick = () => deleteNotebook(state.nb);
  $('#nb-reindex').onclick = reindexNotebook;
  $('#pick').onclick = () => $('#file-input').click();
  $('#pick-folder').onclick = () => $('#folder-input').click();

  const handleInputFiles = async e => {
    toast('Lendo arquivos...');
    const exts = await getValidExts();
    const files = [...e.target.files].filter(f => isValidFile(f, exts));
    e.target.value = '';
    if (!files.length) return toast('Nenhum arquivo reconhecido.', 'error');
    upload(files);
  };
  $('#file-input').onchange = handleInputFiles;
  $('#folder-input').onchange = handleInputFiles;

  $('#go').onclick = runSearch;
  $('#q').onkeydown = e => { if (e.key === 'Enter') runSearch(); };
  renderDocs(); renderResults();
}

function renderDocs() {
  const docs = state.docs;
  $('#src-count').textContent = docs.length ? `(${docs.length})` : '';
  $('#doc-list').innerHTML = docs.length ? docs.map(d => `
    <div class="doc" data-id="${d.id}" title="${esc(d.filename)}">
      <span class="ext">${esc(d.ext.replace('.', '') || 'txt')}</span>
      <div class="doc-main">
        <div class="doc-name">${esc(d.filename)}</div>
        <div class="doc-meta">${fmtSize(d.size)}${d.status === 'indexado' ? ` · ${d.lines} linhas` : ''} · ${fmtDate(d.added_at)}
          <span class="pill ${d.status}">${d.status}</span></div>
        ${d.error ? `<div class="doc-err">${esc(d.error)}</div>` : ''}
      </div>
      <button class="icon-btn" data-del title="Remover do caderno">🗑</button>
    </div>`).join('') : `<div class="muted" style="padding:4px 8px 10px">Nenhuma fonte ainda. Solte arquivos acima para começar.</div>`;
  $('#doc-list').querySelectorAll('.doc').forEach(el => {
    el.onclick = e => e.target.closest('[data-del]') ? removeDoc(+el.dataset.id) : openPreview(+el.dataset.id);
  });
  state.busy = docs.some(d => d.status === 'indexando');
  clearTimeout(state.poll);
  if (state.busy) state.poll = setTimeout(reloadDocs, 700);
}
async function reloadDocs() {
  if (!state.nb || !location.hash.startsWith('#/n/')) return;
  try {
    const data = await api(`/notebooks/${state.nb.id}`);
    const wasBusy = state.busy; state.docs = data.documents; renderDocs();
    if (wasBusy && !state.busy) { refreshActivity(); toast('Índice atualizado.'); if (state.query) runSearch(); }
  } catch { }
}
async function removeDoc(id) {
  const d = state.docs.find(x => x.id === id);
  const ok = await ask({ title: 'Remover fonte?', message: `“${d.filename}” será removido do caderno (a cópia em sources/ e o índice).`, ok: 'Remover', danger: true });
  if (!ok) return;
  try { await api(`/documents/${id}`, { method: 'DELETE' }); closePreview(); await reloadDocs(); if (state.query) runSearch(); toast('Fonte removida.'); }
  catch (e) { toast(e.message, 'error'); }
}
async function reindexNotebook() {
  try { const r = await api(`/notebooks/${state.nb.id}/reindex`, { method: 'POST' }); toast(`Reconstruindo ${plural(r.documents, 'documento', 'documentos')}…`); await reloadDocs(); }
  catch (e) { toast(e.message, 'error'); }
}

async function getValidExts() {
  if (state.extensions) return state.extensions;
  try { state.extensions = (await api('/settings')).extensions.map(x => x.toLowerCase()); }
  catch { state.extensions = ['.txt', '.md', '.py', '.js', '.json', '.csv', '.pdf', '.html', '.css']; }
  return state.extensions;
}

function isValidFile(file, exts, pathOverride = '') {
  const pathParts = (pathOverride || file.webkitRelativePath || file.name || '').toLowerCase().split(/[\/\\]/);
  const blockedDirs = ['node_modules', 'venv', '.venv', '__pycache__', '.git'];
  if (pathParts.some(p => blockedDirs.includes(p))) return false;

  const name = file.name.toLowerCase();
  if (name === '__init__.py' || name === '.ds_store') return false;

  const ext = name.includes('.') ? '.' + name.split('.').pop() : '';
  return exts.includes(ext) || !ext;
}

async function readEntry(entry, exts, pathPrefix = '') {
  const fullPath = pathPrefix + entry.name;
  if (entry.isFile) {
    return new Promise(resolve => {
      entry.file(f => {
        if (isValidFile(f, exts, fullPath)) resolve([f]);
        else resolve([]);
      }, () => resolve([]));
    });
  }
  if (!entry.isDirectory) return [];
  const reader = entry.createReader();
  const children = [];
  for (; ;) {
    const batch = await new Promise(resolve => reader.readEntries(resolve, () => resolve([])));
    if (!batch.length) break;
    children.push(...batch);
  }
  const files = [];
  for (const child of children) files.push(...await readEntry(child, exts, fullPath + '/'));
  return files;
}

/* ---------- upload (botão e arrastar/soltar) ---------- */
async function upload(files) {
  if (!files.length || !state.nb) return;
  const form = new FormData(); files.forEach(f => form.append('files', f, f.name));
  toast(`Enviando ${plural(files.length, 'arquivo', 'arquivos')}…`);
  try {
    const r = await api(`/notebooks/${state.nb.id}/documents`, { method: 'POST', form });
    const ok = r.results.filter(x => x.ok).length;
    r.results.filter(x => !x.ok).forEach(x => toast(`${x.name}: ${x.error}`, 'error'));
    if (ok) toast(`${plural(ok, 'arquivo adicionado', 'arquivos adicionados')} — indexando…`);
    await reloadDocs();
  } catch (e) { toast(e.message, 'error'); }
}
let dragDepth = 0;
const hasFiles = e => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
const inNotebook = () => !!$('#dropzone');
window.addEventListener('dragenter', e => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth++; if (inNotebook()) document.body.classList.add('dragging'); });
window.addEventListener('dragleave', e => { if (!hasFiles(e)) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) document.body.classList.remove('dragging'); });
window.addEventListener('dragover', e => {
  if (!hasFiles(e)) return; e.preventDefault();
  const dz = $('#dropzone'); if (dz) dz.classList.toggle('over', !!e.target.closest('.sources'));
});
window.addEventListener('drop', async e => {
  if (!hasFiles(e)) return; e.preventDefault(); dragDepth = 0;
  document.body.classList.remove('dragging'); $('#dropzone')?.classList.remove('over');
  if (!inNotebook()) return toast('Abra um caderno para adicionar arquivos.', 'error');

  toast('Lendo arquivos...');
  const exts = await getValidExts();
  const entries = [...e.dataTransfer.items || []].map(item => item.webkitGetAsEntry?.()).filter(Boolean);
  let files = [];
  if (entries.length) {
    for (const entry of entries) files.push(...await readEntry(entry, exts));
  } else {
    // fallback if no entries
    files = [...e.dataTransfer.files].filter(f => isValidFile(f, exts));
  }

  if (!files.length) return toast('Nenhum arquivo reconhecido encontrado.', 'error');
  upload(files);
});

/* ---------- busca ---------- */
async function runSearch() {
  const q = $('#q').value.trim(); state.query = q;
  if (!q) { state.result = null; return renderResults(); }
  $('#results').innerHTML = '<div class="note">Buscando…</div>';
  try { state.result = await api(`/notebooks/${state.nb.id}/search?q=${encodeURIComponent(q)}`); renderResults(); refreshActivity(); }
  catch (e) { $('#results').innerHTML = ''; toast(e.message, 'error'); }
}
const REASONS = {
  no_terms: 'Sua busca só tem palavras muito comuns (como “de”, “the”). Tente termos mais específicos.',
  empty_notebook: 'Este caderno ainda não tem nenhum trecho indexado. Adicione documentos e aguarde a indexação.',
  no_match: 'Nada encontrado nas fontes deste caderno. Tente outras palavras, menos termos ou um radical (ex.: “autent”).'
};
function renderResults() {
  const box = $('#results'), r = state.result;
  if (!r) { box.innerHTML = `<div class="empty" style="margin:0 10px 10px"><b>Pesquise suas fontes</b>${state.docs.length ? 'Digite uma palavra, expressão ou pergunta acima.' : 'Comece adicionando documentos ao caderno.'}</div>`; return; }
  if (r.reason) { box.innerHTML = `<div class="empty" style="margin:0 10px 10px"><b>Sem resultados para “${esc(r.query)}”</b>${REASONS[r.reason]}</div>`; return; }
  box.innerHTML = `
    <div class="results">
      <div class="summary">${plural(r.hits.length, 'trecho', 'trechos')}${r.total > r.hits.length ? ` (de ${r.total} correspondências)` : ''} em ${plural(r.files.length, 'arquivo', 'arquivos')} · ${r.took_ms} ms —
        ${r.files.map(f => `<span class="chip" data-doc="${f.document_id}">${esc(f.filename)} · ${f.count}</span>`).join('')}</div>
      ${r.hits.map((h, i) => `
        <div class="hit" data-i="${i}">
          <div class="hit-head"><strong>${esc(h.filename)}</strong><span>linhas ${h.start_line}–${h.end_line}</span>${h.heading ? `<span>§ ${esc(h.heading)}</span>` : ''}<span class="score">relevância ${h.score}</span></div>
          <div class="snip">${h.snippet.map(s => `<div class="l"><span class="n">${s.n}</span><span>${s.html}</span></div>`).join('')}</div>
        </div>`).join('')}
    </div>
    ${r.generation && !r.generation.enabled ? `<div class="gen-note">Resposta gerada por IA: não disponível — ${esc(r.generation.reason)}</div>` : ''}`;
  box.querySelectorAll('.hit').forEach(el => el.onclick = () => { const h = r.hits[+el.dataset.i]; openPreview(h.document_id, { line: h.line, start: h.start_line, end: h.end_line }); });
  box.querySelectorAll('.chip').forEach(el => el.onclick = () => openPreview(+el.dataset.doc));
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !$('#preview').hidden) closePreview();
  if (e.key === '/' && $('#q') && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); $('#q').focus(); }
});

/* ---------- prévia ---------- */
async function openPreview(docId, pos = {}) {
  try {
    const p = await api(`/documents/${docId}/content`), d = p.document;
    $('#pv-name').textContent = d.filename;
    $('#pv-meta').textContent = `${fmtSize(d.size)} · ${p.total_lines} linhas · adicionado em ${fmtDate(d.added_at)} · ${d.status}`;
    $('#pv-body').innerHTML = p.lines.map((t, i) => {
      const n = i + 1, cls = n === pos.line ? 'hit' : (pos.start && n >= pos.start && n <= pos.end ? 'rng' : '');
      return `<div class="ln ${cls}" data-n="${n}"><span class="no">${n}</span><span class="tx">${esc(t) || ' '}</span></div>`;
    }).join('') + (p.truncated ? `<div class="muted" style="padding:8px 12px">Prévia limitada às primeiras ${p.lines.length} linhas.</div>` : '');
    $('#preview').hidden = false;
    const target = pos.line && $(`#pv-body [data-n="${pos.line}"]`);
    if (target) target.scrollIntoView({ block: 'center' }); else $('#pv-body').scrollTop = 0;
  } catch (e) { toast(e.message, 'error'); }
}
function closePreview() { $('#preview').hidden = true; }
$('#pv-close').onclick = closePreview;

/* ---------- configurações ---------- */
async function settingsView() {
  crumbs(['Configurações']);
  const s = await api('/settings'), st = s.stats;
  view.innerHTML = `
    <div class="page-head"><h1>Configurações</h1><button class="btn primary" id="reindex-all">Reconstruir índice de todos os cadernos</button></div>
    <div class="settings">
      ${[['Cadernos', st.notebooks], ['Documentos', st.documents], ['Indexados', st.indexed], ['Com problema', st.errors], ['Trechos', st.chunks], ['Termos únicos', st.terms]]
      .map(([l, v]) => `<div class="panel stat"><b>${v}</b><span class="muted">${l}</span></div>`).join('')}
    </div>
    <div class="panel"><div class="panel-head">Armazenamento</div><dl class="kv">
      <dt>Pasta de dados</dt><dd>${esc(s.data_dir)}</dd>
      <dt>Arquivos originais</dt><dd>${esc(s.sources_pattern)} <span class="muted">(${fmtSize(s.sources_size)})</span></dd>
      <dt>Índice interno (SQLite)</dt><dd>${esc(s.db_path)} <span class="muted">(${fmtSize(s.db_size)})</span></dd></dl></div>
    <div class="panel" style="margin-top:12px"><div class="panel-head">Índice e busca</div><dl class="kv">
      <dt>Método</dt><dd>${esc(s.index_method)}</dd>
      <dt>Modelo de linguagem</dt><dd>${s.llm.enabled ? 'conectado' : 'não conectado — ' + esc(s.llm.note)}</dd>
      <dt>Formatos aceitos</dt><dd>${esc(s.extensions.join(' '))}</dd>
      <dt>Tamanho máximo</dt><dd>${s.max_file_mb} MB por arquivo</dd></dl></div>`;
  $('#reindex-all').onclick = async () => {
    try { const r = await api('/reindex', { method: 'POST' }); toast(`Reconstruindo ${plural(r.documents, 'documento', 'documentos')}…`); setTimeout(route, 1200); }
    catch (e) { toast(e.message, 'error'); }
  };
}

route();
