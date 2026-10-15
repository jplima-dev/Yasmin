const $ = selector => document.querySelector(selector);
const grid = $('#documentGrid');
const empty = $('#emptyDocuments');
const dialog = $('#newDocumentDialog');
const form = $('#newDocumentForm');
const nameInput = $('#newDocumentName');
const templateInput = $('#newDocumentTemplate');
const importInput = $('#importInput');
const openLastLink = $('#openLastDocument');

const THEME_KEY = 'inkwrite-ui-theme';
const inWorkspace = document.documentElement.dataset.workspace === 'true';

function preferredStandaloneTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') return saved;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyStandaloneTheme(theme, persist=false) {
  if (inWorkspace) return;
  const dark = theme === 'dark';
  document.documentElement.classList.toggle('dark', dark);
  document.body.classList.toggle('dark', dark);
  if (persist) localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light');
  const button = $('#homeThemeButton');
  if (button) {
    button.textContent = dark ? '☀' : '◐';
    button.title = dark ? 'Usar tema claro' : 'Usar tema escuro';
  }
}

function setupThemeControls() {
  const button = $('#homeThemeButton');
  const note = $('#workspaceThemeNote');
  if (inWorkspace) {
    if (button) button.hidden = true;
    if (note) {
      note.hidden = false;
      note.title = 'No Workspace, altere o tema nas Configurações globais ou pelo Terminal.';
    }
    return;
  }
  if (note) note.hidden = true;
  applyStandaloneTheme(preferredStandaloneTheme());
  if (button) button.addEventListener('click', () => {
    const next = document.body.classList.contains('dark') ? 'light' : 'dark';
    applyStandaloneTheme(next, true);
  });
}

const TEMPLATE_NAMES = {
  blank: 'Documento sem título',
  school: 'Trabalho escolar',
  letter: 'Carta',
  notes: 'Anotações',
  report: 'Relatório'
};

const TEMPLATE_CONTENT = {
  blank: '',
  school: `
    <h1>Trabalho escolar</h1>
    <p><strong>Aluno:</strong> [Seu nome]<br><strong>Turma:</strong> [Sua turma]<br><strong>Disciplina:</strong> [Disciplina]</p>
    <h2>Introdução</h2>
    <p>Apresente aqui o tema do trabalho, o objetivo e o contexto principal.</p>
    <h2>Desenvolvimento</h2>
    <p>Organize as ideias em seções. Você pode inserir novas seções pelo painel de ferramentas do modelo.</p>
    <h2>Conclusão</h2>
    <p>Retome os pontos principais e escreva a conclusão do trabalho.</p>
    <h3>Referências</h3>
    <p>[Autor]. [Título]. [Fonte / ano].</p>
  `,
  letter: `
    <div class="letter-block letter-sender"><strong>[Seu nome]</strong><br>[Seu contato]</div>
    <p class="letter-date" style="text-align:right">[Cidade], [data]</p>
    <div class="letter-block letter-recipient"><strong>[Nome do destinatário]</strong><br>[Empresa / endereço, se necessário]</div>
    <p>Olá, [nome],</p>
    <p>Escreva aqui a mensagem principal da carta. Este texto é apenas um exemplo e pode ser substituído por completo.</p>
    <p>Atenciosamente,</p>
    <div class="letter-signature"><br><strong>[Seu nome]</strong></div>
  `,
  notes: `
    <h1>Anotações</h1>
    <p class="check-item">☐ Revisar o primeiro item</p>
    <p class="check-item">☐ Adicionar uma nova tarefa</p>
    <div class="note-callout"><p><strong>Ideia importante</strong></p><p>Use este bloco para algo que você não quer esquecer.</p></div>
    <h2>Resumo</h2>
    <p>Escreva aqui observações rápidas, tópicos de aula ou ideias do projeto.</p>
  `,
  report: `
    <h1>Relatório</h1>
    <p><strong>Responsável:</strong> [Nome] &nbsp; <strong>Data:</strong> [Data]</p>
    <h2>Resumo</h2>
    <p>Explique em poucas linhas o objetivo deste relatório e o resultado principal.</p>
    <div class="report-status"><span class="status-dot"></span><strong>Status</strong><span>[Em andamento / concluído]</span></div>
    <h2>Dados principais</h2>
    <table class="report-data"><thead><tr><th>Item</th><th>Valor</th><th>Observação</th></tr></thead><tbody><tr><td>Exemplo</td><td>—</td><td>Substitua pelos seus dados</td></tr></tbody></table>
    <h2>Conclusão</h2>
    <p>Registre a conclusão, próximos passos ou recomendações.</p>
  `
};

const TEMPLATE_SETTINGS = {
  blank: { templateStyle: 'default' },
  school: {
    paper: 'a4', orientation: 'portrait', margin: 'normal', lineHeight: '1.5',
    paragraphSpacing: 8, templateStyle: 'academic'
  },
  letter: {
    paper: 'a4', orientation: 'portrait', margin: 'wide', lineHeight: '1.45',
    paragraphSpacing: 10, templateStyle: 'classic'
  },
  notes: {
    paper: 'a4', orientation: 'portrait', margin: 'narrow', lineHeight: '1.45',
    paragraphSpacing: 7, pageColor: '#fffdf7', templateStyle: 'ruled'
  },
  report: {
    paper: 'a4', orientation: 'portrait', margin: 'normal', lineHeight: '1.5',
    paragraphSpacing: 9, templateStyle: 'business'
  }
};

function escapeHtml(value='') {
  const div = document.createElement('div');
  div.textContent = value;
  return div.innerHTML;
}

function sanitizeImportedBody(doc) {
  doc.querySelectorAll('script,iframe,object,embed,link,meta,base').forEach(el => el.remove());
  doc.body.querySelectorAll('*').forEach(el => {
    [...el.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim().toLowerCase();
      if (name.startsWith('on') || ((name === 'href' || name === 'src') && value.startsWith('javascript:'))) {
        el.removeAttribute(attr.name);
      }
    });
  });
  return doc.body.innerHTML || '';
}

function markdownToHtml(markdown='') {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  let html = '';
  let inList = false;
  let listType = '';
  let inCode = false;
  let code = [];

  const inline = text => escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    .replace(/~~(.+?)~~/g, '<s>$1</s>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>');

  const closeList = () => {
    if (inList) html += `</${listType}>`;
    inList = false;
    listType = '';
  };

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      closeList();
      if (!inCode) { inCode = true; code = []; }
      else { html += `<pre>${escapeHtml(code.join('\n'))}</pre>`; inCode = false; code = []; }
      continue;
    }
    if (inCode) { code.push(line); continue; }

    if (!line.trim()) { closeList(); html += '<p><br></p>'; continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) { closeList(); html += `<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`; continue; }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) { closeList(); html += `<blockquote>${inline(quote[1])}</blockquote>`; continue; }
    const unordered = line.match(/^[-*+]\s+(.+)$/);
    if (unordered) {
      if (!inList || listType !== 'ul') { closeList(); html += '<ul>'; inList = true; listType = 'ul'; }
      html += `<li>${inline(unordered[1])}</li>`;
      continue;
    }
    const ordered = line.match(/^\d+[.)]\s+(.+)$/);
    if (ordered) {
      if (!inList || listType !== 'ol') { closeList(); html += '<ol>'; inList = true; listType = 'ol'; }
      html += `<li>${inline(ordered[1])}</li>`;
      continue;
    }
    closeList();
    html += `<p>${inline(line)}</p>`;
  }
  closeList();
  if (inCode) html += `<pre>${escapeHtml(code.join('\n'))}</pre>`;
  return html;
}

function stripText(html='') {
  const div = document.createElement('div');
  div.innerHTML = html;
  return div.textContent.replace(/\s+/g, ' ').trim();
}

function wordCount(html='') {
  const text = stripText(html);
  return text ? text.split(/\s+/).length : 0;
}

function formatDate(value) {
  try { return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)); }
  catch { return ''; }
}

function openEditor(id) {
  localStorage.setItem('inkwrite-last-document', id);
  location.href = `editor.html?document=${encodeURIComponent(id)}`;
}

function showNew(template='blank') {
  templateInput.value = template;
  nameInput.value = TEMPLATE_NAMES[template] || 'Documento sem título';
  dialog.showModal();
  requestAnimationFrame(() => nameInput.select());
}

async function createDocument(name, template='blank') {
  const doc = InkWriteDB.normalize({
    title: name,
    template,
    content: TEMPLATE_CONTENT[template] ?? '',
    settings: TEMPLATE_SETTINGS[template] || TEMPLATE_SETTINGS.blank
  });
  await InkWriteDB.putDocument(doc);
  openEditor(doc.id);
}

async function renderDocuments() {
  const documents = await InkWriteDB.getAllDocuments();
  const lastId = localStorage.getItem('inkwrite-last-document');
  const lastExists = !!lastId && documents.some(doc => doc.id === lastId);
  if (lastId && !lastExists) localStorage.removeItem('inkwrite-last-document');
  openLastLink.hidden = !lastExists;
  grid.innerHTML = '';
  empty.hidden = documents.length > 0;

  for (const doc of documents) {
    const card = document.createElement('article');
    card.className = 'document-card';

    const openLink = document.createElement('a');
    openLink.className = 'document-card-open';
    openLink.href = `editor.html?document=${encodeURIComponent(doc.id)}`;
    openLink.setAttribute('aria-label', `Abrir ${doc.title}`);
    openLink.addEventListener('click', event => {
      event.preventDefault();
      openEditor(doc.id);
    });

    const preview = document.createElement('div');
    preview.className = `doc-preview template-${doc.template || 'blank'}`;
    const previewTitle = document.createElement('strong');
    previewTitle.textContent = doc.title;
    const previewText = document.createElement('p');
    previewText.textContent = stripText(doc.content).slice(0, 220) || 'Documento vazio';
    preview.append(previewTitle, previewText);

    const title = document.createElement('h3');
    title.textContent = doc.title;
    const meta = document.createElement('p');
    meta.className = 'meta';
    const words = wordCount(doc.content);
    const typeName = TEMPLATE_NAMES[doc.template] || 'Documento';
    meta.textContent = `${typeName} · ${formatDate(doc.updatedAt)} · ${words} palavra${words === 1 ? '' : 's'}`;

    const actions = document.createElement('div');
    actions.className = 'document-actions';
    const edit = action('Editar', 'edit', () => openEditor(doc.id));
    const rename = action('Renomear', '', async () => {
      const next = prompt('Novo nome do documento:', doc.title)?.trim();
      if (!next || next === doc.title) return;
      await InkWriteDB.renameDocument(doc.id, next);
      renderDocuments();
    });
    const duplicate = action('Duplicar', '', async () => {
      await InkWriteDB.duplicateDocument(doc.id);
      renderDocuments();
    });
    const remove = action('Excluir', 'danger', async () => {
      if (!confirm(`Excluir “${doc.title}”?`)) return;
      await InkWriteDB.deleteDocument(doc.id);
      if (localStorage.getItem('inkwrite-last-document') === doc.id) localStorage.removeItem('inkwrite-last-document');
      renderDocuments();
    });
    actions.append(edit, rename, duplicate, remove);
    card.append(openLink, preview, title, meta, actions);
    grid.append(card);
  }
}

function action(label, cls, handler) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = `document-action ${cls}`;
  b.textContent = label;
  b.onclick = handler;
  return b;
}

async function importFile(file) {
  const raw = await file.text();
  const lower = file.name.toLowerCase();
  let content = '';
  let title = file.name.replace(/\.(html?|txt|md|markdown)$/i, '');

  if (lower.endsWith('.html') || lower.endsWith('.htm')) {
    const parsed = new DOMParser().parseFromString(raw, 'text/html');
    content = sanitizeImportedBody(parsed);
    title = parsed.title?.trim() || title;
  } else if (lower.endsWith('.md') || lower.endsWith('.markdown')) {
    content = markdownToHtml(raw);
  } else if (lower.endsWith('.txt')) {
    content = raw ? `<p>${escapeHtml(raw).replace(/\n/g, '<br>')}</p>` : '';
  } else {
    throw new Error('Formato não suportado');
  }

  const doc = InkWriteDB.normalize({
    id: InkWriteDB.createId(),
    title,
    template: 'blank',
    content
  });
  await InkWriteDB.putDocument(doc);
  openEditor(doc.id);
}

document.querySelectorAll('[data-template]').forEach(btn => btn.addEventListener('click', () => showNew(btn.dataset.template)));
$('#heroNew').onclick = () => showNew('blank');
$('#newDocumentButton').onclick = () => showNew('blank');
$('#importButton').onclick = () => importInput.click();
$('#heroImport').onclick = () => importInput.click();

importInput.onchange = async () => {
  const file = importInput.files[0];
  if (file) {
    try { await importFile(file); }
    catch (error) {
      console.error(error);
      alert('Não foi possível abrir esse arquivo. Use HTML, TXT ou Markdown.');
    }
  }
  importInput.value = '';
};

dialog.querySelectorAll('[data-dialog-close]').forEach(button => button.addEventListener('click', () => dialog.close('cancel')));
form.addEventListener('submit', event => {
  event.preventDefault();
  const name = nameInput.value.trim() || 'Documento sem título';
  const template = templateInput.value || 'blank';
  dialog.close('default');
  createDocument(name, template);
});

openLastLink.addEventListener('click', async event => {
  event.preventDefault();
  const id = localStorage.getItem('inkwrite-last-document');
  if (!id) { openLastLink.hidden = true; return; }
  const doc = await InkWriteDB.getDocument(id);
  if (!doc) {
    localStorage.removeItem('inkwrite-last-document');
    openLastLink.hidden = true;
    return;
  }
  openEditor(id);
});

setupThemeControls();
renderDocuments();
