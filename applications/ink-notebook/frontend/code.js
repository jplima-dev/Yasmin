'use strict';
/* Code Notebook — interface do projeto de código (#/c/<id>). Não altera as telas existentes. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtN = n => Number(n).toLocaleString('pt-BR');
  const toast = (m, k = '') => { const t = document.createElement('div'); t.className = 'toast ' + k; t.textContent = m; $('#toasts').append(t); setTimeout(() => t.remove(), k === 'error' ? 7000 : 3500); };
  async function api(path, o = {}) {
    const init = { method: o.method || 'GET', headers: {} };
    if (o.json !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(o.json); }
    if (o.form) init.body = o.form;
    let r; try { r = await fetch('/api/code' + path, init); } catch { throw new Error('Não consegui falar com o servidor local.'); }
    let d = null; try { d = await r.json(); } catch { }
    if (!r.ok) throw new Error((d && d.error) || `Erro ${r.status}`);
    return d;
  }

  const S = { id: null, name: '', ov: null, files: [], rules: null, tab: 'ask', chat: [], wiki: 'arq', openFile: null, graph: { path: '', depth: 1, dir: 'both', kinds: 'imports,references,calls', filter: '' } };
  let root;

  /* ---------- entrada ---------- */
  async function render(el, id) {
    root = el; S.id = id;
    if (!S.rules) S.rules = await api('/rules');
    const [ov, tree, hist] = await Promise.all([api(`/${id}/overview`), api(`/${id}/tree`), api(`/${id}/history`)]);
    S.name = ov.name; S.ov = ov; S.files = tree.files;
    S.chat = hist.items.flatMap(h => [{ role: 'user', text: h.question }, { role: 'bot', ...h }]);
    document.querySelector('#crumbs').innerHTML = `<span>/</span><a href="#/n/${id}">${esc(S.name)}</a><span>/</span><b>Código</b>`;
    root.innerHTML = `
  <div class="page-head"><h1>${esc(S.name)} <span class="muted" style="font-weight:400">· Code Notebook</span></h1>
    <a class="btn sm" href="#/n/${id}">Documentos</a><button class="btn sm danger" <a class="btn sm" href="#/n/${id}">Documentos</a><button class="btn sm" id="c-ai">⚙ IA</button><button class="btn sm danger" id="c-clear">Limpar índice</button></div> id="c-clear">Limpar índice</button></div>
  <div class="cn-layout">
    <aside class="panel cn-side">
      <div class="panel-head">Projeto <span class="cnt" id="c-count"></span></div>
      <div class="dropzone" id="c-drop"><b>Arraste uma pasta, arquivos ou ZIP</b>
        <span class="muted">node_modules, .git, .venv, binários e mídia são ignorados</span><br>
        <button class="btn sm" id="c-pick-dir">Pasta</button> <button class="btn sm" id="c-pick-files">Arquivos / ZIP</button>
        <input type="file" id="c-in-dir" webkitdirectory hidden><input type="file" id="c-in-files" multiple hidden></div>
      <div id="c-progress"></div>
      <input class="cn-filter" id="c-filter" placeholder="Filtrar arquivos…" autocomplete="off">
      <div class="cn-tree" id="c-tree"></div>
    </aside>
    <section class="panel cn-main">
      <div class="cn-tabs" id="c-tabs">
        ${[['ask', 'Pergunte ao projeto'], ['search', 'Busca'], ['wiki', 'Wiki'], ['graph', 'Grafo']].map(([k, l]) => `<button data-tab="${k}">${l}</button>`).join('')}
      </div>
      <div id="c-body"></div>
    </section>
  </div>
  <aside class="cn-viewer" id="c-viewer" hidden></aside>`;
    $('#c-ai').onclick = aiDialog;
    $('#c-clear').onclick = async () => { if (!confirm('Apagar todo o índice de código deste caderno? (Seus arquivos originais não são tocados.)')) return; await api(`/${id}/project`, { method: 'DELETE' }); render(root, id); };
    $('#c-pick-dir').onclick = () => $('#c-in-dir').click();
    $('#c-pick-files').onclick = () => $('#c-in-files').click();
    $('#c-in-dir').onchange = e => { importList([...e.target.files].map(f => ({ file: f, path: f.webkitRelativePath || f.name })), {}); e.target.value = ''; };
    $('#c-in-files').onchange = e => { importList([...e.target.files].map(f => ({ file: f, path: f.name })), {}); e.target.value = ''; };
    $('#c-filter').oninput = renderTree;
    const dz = $('#c-drop');
    root.ondragover = e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { e.preventDefault(); dz.classList.add('over'); } };
    root.ondragleave = e => { if (!root.contains(e.relatedTarget)) dz.classList.remove('over'); };
    root.ondrop = async e => {
      if (![...(e.dataTransfer?.types || [])].includes('Files')) return;
      e.preventDefault(); e.stopPropagation(); dz.classList.remove('over'); document.body.classList.remove('dragging');
      const { out, ign } = await collectDrop(e.dataTransfer); importList(out, ign);
    };
    $('#c-tabs').onclick = e => { if (e.target.dataset.tab) { S.tab = e.target.dataset.tab; renderTab(); } };
    renderTree(); renderTab();
  }

  /* ---------- importação ---------- */
  const clientIgnore = (path, size) => {
    const parts = path.split('/'); for (const d of parts.slice(0, -1)) if (S.rules.ignore_dirs.includes(d)) return 'pasta ' + d;
    const n = parts.at(-1).toLowerCase(), ext = n.includes('.') ? '.' + n.split('.').pop() : '';
    if (S.rules.ignore_names.includes(n)) return 'arquivo gerado (lock/temporário)';
    if (S.rules.ignore_ext.includes(ext) && ext !== '.zip') return `binário/mídia (${ext})`;
    if (size > S.rules.max_bytes && ext !== '.zip') return 'arquivo grande demais (>1 MB)';
    return null;
  };
  async function collectDrop(dt) {
    const entries = [...dt.items].map(i => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean); // síncrono
    const out = [], ign = {};
    const bump = r => ign[r] = (ign[r] || 0) + 1;
    async function walk(en, prefix) {
      if (en.isFile) { const file = await new Promise((ok, no) => en.file(ok, no)); out.push({ file, path: prefix + en.name }); return; }
      if (S.rules.ignore_dirs.includes(en.name)) { bump('pasta ' + en.name); return; }   // nem entra na pasta
      const rd = en.createReader(); let all = [];
      for (; ;) { const b = await new Promise((ok, no) => rd.readEntries(ok, no)); if (!b.length) break; all = all.concat(b); }
      for (const c of all) await walk(c, prefix + en.name + '/');
    }
    for (const en of entries) await walk(en, '');
    return { out, ign };
  }
  async function importList(list, ign0) {
    const tops = new Set(list.map(i => i.path.split('/')[0]));   // tira a pasta raiz comum (ex.: "meu-projeto/")
    if (tops.size === 1 && list.every(i => i.path.includes('/'))) list = list.map(i => ({ ...i, path: i.path.split('/').slice(1).join('/') }));
    const P = { found: list.length, ignored: { ...ign0 }, sent: 0, new: 0, updated: 0, unchanged: 0, langs: {}, errors: [], secrets: [], phase: 'Enviando' };
    const box = $('#c-progress'); const draw = () => {
      const ig = Object.values(P.ignored).reduce((a, b) => a + b, 0), total = P.found;
      box.innerHTML = `<div class="cn-prog"><div class="bar"><i style="width:${total ? Math.round(P.sent / total * 100) : 0}%"></i></div>
      <div><b>${P.phase}</b> · ${fmtN(P.sent)}/${fmtN(total)} arquivos · ${fmtN(ig)} ignorados</div>
      <div class="muted">${P.new} novos · ${P.updated} alterados · ${P.unchanged} inalterados</div>
      ${Object.keys(P.langs).length ? `<div class="muted">${Object.entries(P.langs).map(([k, v]) => `${k} ${v}`).join(' · ')}</div>` : ''}
      ${ig ? `<details><summary class="muted">Ignorados (${ig})</summary><div class="muted">${Object.entries(P.ignored).map(([k, v]) => `${esc(k)}: ${v}`).join('<br>')}</div></details>` : ''}
      ${P.secrets.length ? `<div class="cn-warn">⚠ ${P.secrets.length} arquivo(s) sensível(is): conteúdo não armazenado nem enviado à IA.</div>` : ''}
      ${P.errors.length ? `<details open><summary class="cn-err">${P.errors.length} erro(s)</summary><div class="muted">${P.errors.slice(0, 8).map(esc).join('<br>')}</div></details>` : ''}</div>`;
    };
    const keep = [];
    for (const it of list) { const r = clientIgnore(it.path, it.file.size); if (r) { P.ignored[r] = (P.ignored[r] || 0) + 1; P.sent++; } else keep.push(it); }
    if (!keep.length) { P.phase = 'Nada para indexar'; draw(); return; }
    draw();
    let batch = [], bytes = 0;
    const flush = async () => {
      if (!batch.length) return;
      const form = new FormData(); batch.forEach(b => { form.append('files', b.file, b.path.split('/').pop()); form.append('paths', b.path); });
      try {
        const r = await api(`/${S.id}/import`, { method: 'POST', form });
        for (const k of ['new', 'updated', 'unchanged']) P[k] += r[k];
        for (const [k, v] of Object.entries(r.ignored)) P.ignored[k] = (P.ignored[k] || 0) + v;
        for (const [k, v] of Object.entries(r.languages)) P.langs[k] = (P.langs[k] || 0) + v;
        P.errors.push(...r.errors); P.secrets.push(...r.secrets);
      } catch (e) { P.errors.push(e.message); }
      P.sent += batch.length; batch = []; bytes = 0; draw();
    };
    for (const it of keep) { batch.push(it); bytes += it.file.size; if (batch.length >= 100 || bytes > 6e6) await flush(); }
    await flush();
    P.phase = 'Resolvendo relações'; draw();
    try { await api(`/${S.id}/finalize`, { method: 'POST' }); } catch (e) { P.errors.push(e.message); }
    P.phase = 'Pronto'; draw();
    const [ov, tree] = await Promise.all([api(`/${S.id}/overview`), api(`/${S.id}/tree`)]);
    S.ov = ov; S.files = tree.files; renderTree(); renderTab();
    toast(`Indexado: ${P.new} novos, ${P.updated} alterados, ${P.unchanged} inalterados.`);
  }

  /* ---------- explorador ---------- */
  function renderTree() {
    const f = ($('#c-filter')?.value || '').toLowerCase();
    const files = S.files.filter(x => !f || x.path.toLowerCase().includes(f));
    $('#c-count').textContent = S.files.length ? `(${fmtN(S.files.length)})` : '';
    if (!S.files.length) { $('#c-tree').innerHTML = '<div class="muted" style="padding:6px 10px">Nenhum arquivo ainda. Importe um projeto acima.</div>'; return; }
    const dirs = {}; files.forEach(x => { const d = x.path.includes('/') ? x.path.slice(0, x.path.lastIndexOf('/')) : ''; (dirs[d] ||= []).push(x); });
    const open = f ? true : null;
    $('#c-tree').innerHTML = Object.keys(dirs).sort().map(d => `
    <details ${open || d.split('/').length <= 1 ? 'open' : ''}><summary>${esc(d || '(raiz)')} <span class="muted">${dirs[d].length}</span></summary>
    ${dirs[d].map(x => `<div class="cn-file" data-p="${esc(x.path)}" title="${esc(x.path)}"><span class="ext">${esc(x.lang.slice(0, 4))}</span>${esc(x.path.split('/').pop())}${x.secret ? ' 🔒' : ''}</div>`).join('')}</details>`).join('');
    $('#c-tree').onclick = e => { const el = e.target.closest('.cn-file'); if (el) openFile(el.dataset.p); };
  }

  /* ---------- abas ---------- */
  function renderTab() {
    root.querySelectorAll('#c-tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.tab));
    ({ ask: askTab, search: searchTab, wiki: wikiTab, graph: graphTab })[S.tab]();
  }
  const empty = () => !S.files.length;
  const noProject = '<div class="empty" style="margin:12px"><b>Projeto vazio</b>Arraste uma pasta, arquivos ou um ZIP para a área à esquerda. Tudo é indexado localmente.</div>';

  /* ---------- chat ---------- */
  const SUGG = ['Como adiciono um módulo novo?', 'Onde fica o sistema de módulos?', 'Qual arquivo controla o tema?', 'Quem importa config.py?', 'Quais são os pontos de entrada?'];
  function askTab() {
    if (empty()) { $('#c-body').innerHTML = noProject; return; }
    $('#c-body').innerHTML = `<div class="cn-chat" id="c-chat"></div>
    <div class="searchbox"><input id="c-q" placeholder="Pergunte ao projeto… ex.: Quem chama createNote?" autocomplete="off"><button class="btn primary" id="c-send">Perguntar</button></div>
    <div class="note">Perguntas estruturais (quem importa, onde fica, quem chama…) são respondidas pelo índice local, Nada é enviado à internet.</div>`;
    const send = () => { const q = $('#c-q').value.trim(); if (q) { $('#c-q').value = ''; ask(q); } };
    $('#c-send').onclick = send; $('#c-q').onkeydown = e => { if (e.key === 'Enter') send(); };
    drawChat();
  }
  function drawChat() {
    const el = $('#c-chat'); if (!el) return;
    el.innerHTML = S.chat.length ? S.chat.map((m, i) => m.role === 'user' ? `<div class="msg me">${esc(m.text)}</div>` : botMsg(m, i)).join('')
      : `<div class="empty" style="margin:0"><b>Converse com o projeto</b><div class="cn-sugg">${SUGG.map(s => `<button class="btn sm" data-s="${esc(s)}">${esc(s)}</button>`).join('')}</div></div>`;
    el.onclick = e => {
      const s = e.target.closest('[data-s]'); if (s) return ask(s.dataset.s);
      const l = e.target.closest('[data-open]'); if (l) return openFile(l.dataset.open, +l.dataset.line || null, +l.dataset.end || null);
      const a = e.target.closest('[data-act]'); if (!a) return; const m = S.chat[+a.dataset.i];
      const first = m.sources?.[0]; if (!first) return;
      if (a.dataset.act === 'code') openFile(first.path, first.start, first.end);
      if (a.dataset.act === 'files') a.closest('.msg').querySelector('.rel').hidden = false;
      if (a.dataset.act === 'flow' || a.dataset.act === 'deps') { S.graph = { ...S.graph, path: first.path, depth: a.dataset.act === 'flow' ? 2 : 1, dir: a.dataset.act === 'flow' ? 'out' : 'both' }; S.tab = 'graph'; renderTab(); }
      if (a.dataset.act === 'confirm') ask(m.question, true);
      if (a.dataset.act === 'cancel') { S.chat.splice(+a.dataset.i, 1); drawChat(); }
    };
    el.scrollTop = el.scrollHeight;
  }
  function fmt(text, links) {
    let h = esc(text).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^_(.+)_$/gm, '<i>$1</i>').replace(/```[\w]*\n([\s\S]*?)```/g, '<pre>$1</pre>');
    h = h.replace(/`([^`\n]+)`/g, (m, t) => { const L = links?.[t.replace(/&amp;/g, '&')] || links?.[t]; return L ? `<a class="cn-link" data-open="${esc(L.path)}" data-line="${L.line || ''}">${t}</a>` : `<code>${t}</code>`; });
    return h.replace(/^(\d+\.|-) (.*)$/gm, '<div class="li">$1 $2</div>').replace(/<\/div>\n/g, '</div>').replace(/\n/g, '<br>');
  }
  function botMsg(m, i) {
    if (m.mode === 'needs_confirmation') return `<div class="msg bot warn"><b>Confirmar envio a IA externa</b><br>Provedor: ${esc(m.provider)}. Serão enviados trechos de:
    <div class="cn-sent">${m.sent.map(s => `<div><code>${esc(s.path)}</code> ${s.ranges.map(r => `linhas ${r[0]}–${r[1]}`).join(', ')}</div>`).join('')}</div>
    Segredos detectados são ocultados antes do envio.<div class="cn-actions"><button class="btn sm primary" data-act="confirm" data-i="${i}">Enviar à IA</button><button class="btn sm" data-act="cancel" data-i="${i}">Cancelar</button></div></div>`;
    const badge = m.mode === 'ai' ? `<span class="badge ai">Com auxílio de IA${m.provider ? ' · ' + esc(m.provider) : ''}</span>` : '<span class="badge idx">Do índice local</span>';
    const src = (m.sources || []).filter((s, k, a) => a.findIndex(x => x.path === s.path) === k);
    return `<div class="msg bot">${badge}${m.warning ? `<div class="cn-warn">${esc(m.warning)}</div>` : ''}<div class="txt">${fmt(m.text, m.links)}</div>
    ${src.length ? `<div class="based"><span class="muted">Baseado em:</span> ${src.map(s => `<a class="chip" data-open="${esc(s.path)}" data-line="${s.start || ''}" data-end="${s.end || ''}" title="${esc(s.reason || '')}">${esc(s.path)}${s.start ? ':' + s.start : ''}</a>`).join('')}</div>` : ''}
    ${m.mode === 'ai' && m.sent ? `<details class="muted"><summary>Trechos enviados à IA (${m.sent.length} arquivos)</summary>${m.sent.map(s => `<div><code>${esc(s.path)}</code> ${s.ranges.map(r => r.join('–')).join(', ')}</div>`).join('')}</details>` : ''}
    ${src.length ? `<div class="cn-actions"><button class="btn sm" data-act="code" data-i="${i}">Ver código relevante</button><button class="btn sm" data-act="files" data-i="${i}">Ver arquivos relacionados</button><button class="btn sm" data-act="flow" data-i="${i}">Ver fluxo</button><button class="btn sm" data-act="deps" data-i="${i}">Ver dependências</button></div>
    <div class="rel" hidden>${src.map(s => `<div><a class="cn-link" data-open="${esc(s.path)}" data-line="${s.start || ''}">${esc(s.path)}</a> <span class="muted">— ${esc(s.reason || '')}</span></div>`).join('')}</div>` : ''}</div>`;
  }
  async function ask(q, confirm = false) {
    if (!confirm) S.chat.push({ role: 'user', text: q });
    else S.chat = S.chat.filter(m => m.mode !== 'needs_confirmation');
    S.tab = 'ask'; if (!$('#c-chat')) renderTab(); drawChat();
    const wait = { role: 'bot', mode: 'index', text: 'Consultando o índice…' }; S.chat.push(wait); drawChat();
    try { const r = await api(`/${S.id}/ask`, { method: 'POST', json: { question: q, confirm } }); S.chat[S.chat.indexOf(wait)] = { role: 'bot', question: q, ...r }; }
    catch (e) { S.chat[S.chat.indexOf(wait)] = { role: 'bot', mode: 'index', text: e.message }; }
    drawChat();
  }

  /* ---------- busca ---------- */
  function searchTab() {
    if (empty()) { $('#c-body').innerHTML = noProject; return; }
    $('#c-body').innerHTML = `<div class="searchbox"><input id="s-q" placeholder="Arquivo, função, classe, ID, classe CSS, texto, conceito…" autocomplete="off"><button class="btn primary" id="s-go">Buscar</button></div><div id="s-res"></div>`;
    const go = async () => {
      const q = $('#s-q').value.trim(); if (!q) return;
      const r = await api(`/${S.id}/search?q=${encodeURIComponent(q)}`);
      $('#s-res').innerHTML = r.hits.length ? `<div class="results"><div class="summary">${r.hits.length} arquivo(s)${r.extra_terms?.length ? ` · termos relacionados usados: ${r.extra_terms.map(esc).join(', ')}` : ''}</div>
      ${r.hits.map(h => `<div class="hit" data-p="${esc(h.path)}" data-l="${h.line || ''}"><div class="hit-head"><strong>${esc(h.path)}</strong><span>${esc(h.lang)}</span><span class="score">relevância ${h.score}</span></div>
      <div class="why">${h.why.map(w => `<span class="chip">${esc(w)}</span>`).join('')}</div>
      <div class="snip">${h.snippet.map(s => `<div class="l"><span class="n">${s.n}</span><span>${s.html}</span></div>`).join('')}</div></div>`).join('')}</div>`
        : `<div class="empty" style="margin:10px"><b>Não encontrei isso no índice.</b>Tente outro termo ou um radical.</div>`;
      $('#s-res').onclick = e => { const h = e.target.closest('.hit'); if (h) openFile(h.dataset.p, +h.dataset.l || null); };
    };
    $('#s-go').onclick = go; $('#s-q').onkeydown = e => { if (e.key === 'Enter') go(); }; $('#s-q').focus();
  }

  /* ---------- wiki ---------- */
  async function wikiTab() {
    if (empty()) { $('#c-body').innerHTML = noProject; return; }
    const ov = S.ov.overview, subs = [['arq', 'Arquitetura'], ['mod', 'Módulos'], ['dep', 'Dependências'], ['flow', 'Fluxos'], ['docs', 'Documentos']];
    const nav = `<div class="cn-sub">${subs.map(([k, l]) => `<button data-w="${k}" class="${S.wiki === k ? 'on' : ''}">${l}</button>`).join('')}</div>`;
    let body = '';
    const li = p => `<a class="cn-link" data-open="${esc(p)}">${esc(p)}</a>`;
    if (S.wiki === 'arq') body = `<h3>Visão geral</h3><p>${fmtN(ov.files)} arquivos em ${fmtN(ov.folders)} pastas · ${fmtN(ov.lines)} linhas · ${fmtN(ov.symbols)} símbolos · ${fmtN(ov.edges)} relações resolvidas.</p>
      <p class="muted">${Object.entries(ov.languages).map(([k, v]) => `${k}: ${v}`).join(' · ')}</p>
      <h3>Pontos de entrada</h3>${ov.entry_points.map(e => `<div>${li(e.path)} <span class="muted">${esc(e.doc || '')}</span></div>`).join('') || '<span class="muted">Nenhum detectado.</span>'}
      <h3>Arquivos mais usados</h3>${ov.hubs.map(h => `<div>${li(h.path)} <span class="muted">← ${h.n} arquivo(s)</span></div>`).join('') || '<span class="muted">Sem relações detectadas.</span>'}
      ${ov.secrets ? `<div class="cn-warn" style="margin-top:10px">⚠ ${ov.secrets} arquivo(s) com possíveis segredos: nunca vão para IA externa.</div>` : ''}
      <p class="muted">Gerado só a partir do índice: descreve o que foi detectado, não interpreta intenção.</p>`;
    if (S.wiki === 'mod') body = S.ov.modules.map(m => `<div class="mod"><b>${esc(m.module)}</b> ${m.manifest ? '<span class="chip">ink-module.json</span>' : ''}<div class="muted">${m.files} arquivos · ${m.symbols} funções/classes · ${Object.keys(m.langs).join(', ')}</div>${m.doc ? `<div>${esc(m.doc)}</div>` : ''}<div>${m.sample.map(li).join(' ')}</div></div>`).join('');
    if (S.wiki === 'dep') body = `<h3>Mais importados</h3>${ov.hubs.map(h => `<div>${li(h.path)} <span class="muted">← ${h.n}</span></div>`).join('')}<h3>Bibliotecas externas</h3><div>${ov.external.map(([n, c]) => `<span class="chip">${esc(n)} · ${c}</span>`).join('') || '<span class="muted">Nenhuma.</span>'}</div>`;
    if (S.wiki === 'flow') body = S.ov.flows.map(f => `<div class="mod"><b>${li(f.entry)}</b>${f.steps.map(s => `<div style="margin-left:${s.depth * 16}px">↳ ${li(s.path)} <span class="muted">${esc(s.via)}</span></div>`).join('')}</div>`).join('') || '<span class="muted">Nenhum fluxo detectado.</span>';
    $('#c-body').innerHTML = nav + `<div class="cn-wiki" id="c-wiki">${body || '<span class="muted">Carregando…</span>'}</div>`;
    $('#c-body .cn-sub').onclick = e => { if (e.target.dataset.w) { S.wiki = e.target.dataset.w; wikiTab(); } };
    $('#c-wiki').onclick = e => { const l = e.target.closest('[data-open]'); if (l) openFile(l.dataset.open); };
    if (S.wiki === 'docs') {
      const { docs } = await api(`/${S.id}/docs`);
      $('#c-wiki').innerHTML = `<p class="muted">Documentos gerados do índice (a documentação é opcional; o índice é a fonte principal).</p>` + Object.entries(docs).map(([n, c]) => `<details class="mod"><summary><b>${n}</b> <button class="btn sm" data-dl="${n}">Baixar</button></summary><pre>${esc(c)}</pre></details>`).join('');
      $('#c-wiki').onclick = e => { const n = e.target.dataset.dl; if (!n) return; e.preventDefault(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([docs[n]], { type: 'text/markdown' })); a.download = n; a.click(); };
    }
  }

  /* ---------- grafo ---------- */
  async function graphTab() {
    if (empty()) { $('#c-body').innerHTML = noProject; return; }
    const g = S.graph;
    $('#c-body').innerHTML = `<div class="cn-gctl"><input id="g-p" list="g-list" placeholder="Arquivo central (vazio = visão por pastas)" value="${esc(g.path)}"><datalist id="g-list">${S.files.slice(0, 3000).map(f => `<option value="${esc(f.path)}">`).join('')}</datalist>
    <label>Profundidade <select id="g-d">${[1, 2, 3].map(n => `<option ${g.depth === n ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
    <label>Direção <select id="g-dir">${[['both', 'ambas'], ['out', 'importa'], ['in', 'usado por']].map(([v, l]) => `<option value="${v}" ${g.dir === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <label>Tipo <select id="g-k">${[['imports,references,calls', 'tudo'], ['imports,references', 'imports'], ['calls', 'chamadas']].map(([v, l]) => `<option value="${v}" ${g.kinds === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <input id="g-f" placeholder="filtrar nós…" value="${esc(g.filter)}" style="max-width:130px"></div><div id="g-svg" class="cn-graph"></div><div id="g-info" class="note"></div>`;
    const reload = () => { Object.assign(S.graph, { path: $('#g-p').value.trim(), depth: +$('#g-d').value, dir: $('#g-dir').value, kinds: $('#g-k').value, filter: $('#g-f').value }); graphTab(); };
    ['g-d', 'g-dir', 'g-k'].forEach(i => $('#' + i).onchange = reload); $('#g-p').onchange = reload; $('#g-f').oninput = () => { S.graph.filter = $('#g-f').value; drawGraph(data); };
    let data; try { data = await api(`/${S.id}/graph?path=${encodeURIComponent(g.path)}&depth=${g.depth}&dir=${g.dir}&kinds=${g.kinds}`); } catch (e) { $('#g-svg').innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
    drawGraph(data);
  }
  function drawGraph(data) {
    const f = (S.graph.filter || '').toLowerCase(), box = $('#g-svg');
    let nodes = data.nodes.filter(n => !f || n.path.toLowerCase().includes(f) || n.depth === 0 && !data.group), ids = new Set(nodes.map(n => n.id));
    if (!nodes.length) { box.innerHTML = '<div class="empty">Sem relações detectadas para este filtro.</div>'; return; }
    const cols = {}; // coluna: -d (usa o raiz) | 0 | +d (importado pelo raiz)
    if (data.group) nodes.forEach((n, i) => (cols[i % 3] ||= []).push(n));
    else {
      const out = new Set(data.edges.filter(e => e.src === data.root).map(e => e.dst)), inn = new Set(data.edges.filter(e => e.dst === data.root).map(e => e.src));
      nodes.forEach(n => { const c = n.id === data.root ? 0 : (out.has(n.id) ? n.depth : inn.has(n.id) ? -n.depth : (n.depth)); (cols[c] ||= []).push(n); });
    }
    const keys = Object.keys(cols).map(Number).sort((a, b) => a - b), W = 220, GX = 90, H = 30, GY = 12;
    const pos = {}; let maxRows = 0;
    keys.forEach((k, ci) => { cols[k].sort((a, b) => a.path.localeCompare(b.path)); maxRows = Math.max(maxRows, cols[k].length); cols[k].forEach((n, r) => pos[n.id] = { x: 10 + ci * (W + GX), y: 10 + r * (H + GY), n }); });
    const width = 20 + keys.length * (W + GX) - GX, height = 20 + maxRows * (H + GY);
    const lab = p => { const s = p.length > 30 ? '…' + p.slice(-29) : p; return s; };
    const edges = data.edges.filter(e => ids.has(e.src) && ids.has(e.dst) && pos[e.src] && pos[e.dst]).map(e => {
      const a = pos[e.src], b = pos[e.dst], x1 = a.x + (a.x <= b.x ? W : 0), x2 = b.x + (a.x <= b.x ? 0 : W), y1 = a.y + H / 2, y2 = b.y + H / 2, mx = (x1 + x2) / 2;
      return `<path class="e ${e.kind}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" marker-end="url(#ar)"><title>${e.kind}${e.weight ? ' ×' + e.weight : ''}</title></path>`;
    }).join('');
    box.innerHTML = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><defs><marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8z" fill="currentColor"/></marker></defs>${edges}
    ${Object.values(pos).map(p => `<g class="nd ${p.n.id === data.root ? 'root' : ''}" data-id="${esc(p.n.id)}" data-p="${esc(p.n.path)}" transform="translate(${p.x},${p.y})"><rect width="${W}" height="${H}" rx="6"/><text x="8" y="${H / 2 + 4}">${esc(lab(p.n.path))}${p.n.files ? ' (' + p.n.files + ')' : ''}</text><title>${esc(p.n.path)}</title></g>`).join('')}</svg>`
      + (data.truncated ? '<div class="note">Grafo limitado para continuar legível. Reduza a profundidade ou filtre.</div>' : '');
    box.onclick = async e => {
      const g = e.target.closest('.nd'); if (!g) return;
      if (data.group) { S.graph.filter = g.dataset.p; $('#g-f').value = g.dataset.p; return drawGraph(data); }
      const d = await api(`/${S.id}/file?path=${encodeURIComponent(g.dataset.p)}`);
      $('#g-info').innerHTML = `<b>${esc(d.path)}</b> — ${d.symbols.filter(s => ['function', 'class', 'method'].includes(s.kind)).length} funções/classes · importa ${d.imports.length} · usado por ${d.used_by.length}
      <div><a class="cn-link" data-open="${esc(d.path)}">ver código</a> · <a class="cn-link" data-center="${esc(d.path)}">centralizar aqui</a></div>`;
      $('#g-info').onclick = ev => { const o = ev.target.dataset; if (o.open) openFile(o.open); if (o.center) { S.graph.path = o.center; graphTab(); } };
    };
  }

  /* ---------- visualizador de código ---------- */
  async function openFile(path, line = null, end = null) {
    const v = $('#c-viewer'); v.hidden = false; v.innerHTML = '<div class="muted" style="padding:14px">Abrindo…</div>';
    let d; try { d = await api(`/${S.id}/file?path=${encodeURIComponent(path)}`); } catch (e) { v.innerHTML = `<div style="padding:14px">${esc(e.message)}</div>`; return; }
    const secret = new Set(d.secret_lines);
    const chips = (arr, k) => arr.length ? `<div class="rel2"><span class="muted">${k}</span> ${arr.slice(0, 14).map(r => `<a class="chip" data-open="${esc(r.path)}">${esc(r.path.split('/').pop())}</a>`).join('')}${arr.length > 14 ? ` <span class="muted">+${arr.length - 14}</span>` : ''}</div>` : '';
    const syms = d.symbols.filter(s => ['function', 'class', 'method', 'route'].includes(s.kind));
    v.innerHTML = `<div class="pv-head"><div class="pv-title"><strong>${esc(d.path)}</strong><span class="muted">${esc(d.lang)} · ${d.lines} linhas${d.entry ? ' · ponto de entrada' : ''}${d.doc ? ' · ' + esc(d.doc.slice(0, 80)) : ''}</span></div>
    <button class="icon-btn" id="v-graph" title="Ver no grafo">⌖</button><button class="icon-btn" id="v-x">✕</button></div>
    <div class="cn-vmeta">${chips(d.imports, 'importa')}${chips(d.used_by, 'usado por')}${d.external.length ? `<div class="rel2"><span class="muted">externas</span> ${d.external.slice(0, 10).map(e => `<span class="chip">${esc(e)}</span>`).join('')}</div>` : ''}
      ${syms.length ? `<details><summary class="muted">Símbolos (${syms.length})</summary><div class="cn-syms">${syms.map(s => `<a data-ln="${s.line}" data-end="${s.end_line}">${esc(s.parent && s.kind === 'method' ? s.parent + '.' : '')}${esc(s.name)}<i>${s.kind} ${s.line}</i></a>`).join('')}</div></details>` : ''}</div>
    <div class="pv-body" id="v-body">${d.content.map((t, i) => { const n = i + 1; return `<div class="ln ${line && n >= line && n <= (end || line) ? 'hit' : ''}" data-n="${n}"><span class="no">${n}</span><span class="tx">${secret.has(n) ? '«linha com possível segredo»' : esc(t) || ' '}</span></div>`; }).join('')}</div>`;
    $('#v-x').onclick = () => v.hidden = true;
    $('#v-graph').onclick = () => { S.graph.path = d.path; S.tab = 'graph'; renderTab(); };
    v.onclick = e => {
      const o = e.target.closest('[data-open]'); if (o) return openFile(o.dataset.open);
      const s = e.target.closest('[data-ln]'); if (s) { v.querySelectorAll('.ln.hit').forEach(x => x.classList.remove('hit')); for (let n = +s.dataset.ln; n <= +s.dataset.end; n++) v.querySelector(`[data-n="${n}"]`)?.classList.add('hit'); v.querySelector(`[data-n="${s.dataset.ln}"]`)?.scrollIntoView({ block: 'center' }); }
    };
    if (line) v.querySelector(`[data-n="${line}"]`)?.scrollIntoView({ block: 'center' });
  }

  /* ---------- IA ---------- */
  async function aiDialog() {
    const s = await api('/settings');

    const d = document.createElement('dialog');
    d.className = 'cn-dlg';

    d.innerHTML = `
      <form method="dialog">
        <h3>Configurar IA (opcional)</h3>

        <p class="muted">
          Sem IA, o Code Notebook continua respondendo pelo índice local.
          Com IA, só um contexto pequeno e relevante é enviado, com segredos
          ocultados. Provedores externos pedem confirmação mostrando os trechos.
        </p>

        <label>
          Provedor
          <select id="a-p">
            ${[
        ['none', 'Nenhum (somente índice)'],
        ['ollama', 'Ollama (local)'],
        ['openai', 'OpenAI / compatível'],
        ['gemini', 'Gemini']
      ].map(([v, l]) => `
              <option value="${v}" ${s.ai_provider === v ? 'selected' : ''}>
                ${l}
              </option>
            `).join('')}
          </select>
        </label>

        <label>
          URL base
          <input
            id="a-u"
            value="${esc(s.ai_base_url)}"
            placeholder="Ollama: http://127.0.0.1:11434 · OpenAI: https://api.openai.com/v1"
          >
        </label>

        <label>
          Modelo
          <input
            id="a-m"
            value="${esc(s.ai_model)}"
            placeholder="ex.: llama3.1, gpt-4o-mini, gemini-2.0-flash"
          >
        </label>

        <label>
          Chave de API
          <input
            id="a-k"
            type="password"
            placeholder="${s.has_key ? '(salva — deixe vazio para manter)' : 'opcional para modelos locais'}"
            autocomplete="off"
          >
        </label>

        <label>
          Limite de contexto (caracteres)
          <input
            id="a-c"
            type="number"
            min="2000"
            max="60000"
            value="${esc(s.ctx_max_chars)}"
          >
        </label>

        <label class="row">
          <input
            type="checkbox"
            id="a-r"
            ${s.review_external === '1' ? 'checked' : ''}
          >
          Revisar contexto antes de enviar a provedores externos
        </label>

        <div class="dlg-actions">
          <button type="button" class="btn" id="a-x">
            Cancelar
          </button>

          <button class="btn primary" value="ok">
            Salvar
          </button>
        </div>
      </form>
    `;

    document.body.append(d);
    d.showModal();

    $('#a-x', d).onclick = () => d.close('cancel');

    d.onclose = async () => {
      if (d.returnValue === 'ok') {
        await api('/settings', {
          method: 'POST',
          json: {
            ai_provider: $('#a-p', d).value,
            ai_base_url: $('#a-u', d).value.trim(),
            ai_model: $('#a-m', d).value.trim(),
            ai_key: $('#a-k', d).value,
            ctx_max_chars: $('#a-c', d).value,
            review_external: $('#a-r', d).checked ? '1' : '0'
          }
        });

        toast('Configuração de IA salva.');
      }

      d.remove();
    };
  }

  window.CodeNotebook = { render };
})();
