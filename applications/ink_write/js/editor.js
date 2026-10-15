const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const editor = $('#editor');
const page = $('#documentPage');
const layout = $('#editorLayout');
const titleInput = $('#documentTitle');
const saveStatus = $('#saveStatus');
const importInput = $('#projectInput');
const imageInput = $('#imageInput');
const pageGuides = $('#pageGuides');
const canvasArea = document.querySelector('.canvas-area');
const ruler = $('#ruler');
const rulerShell = $('#rulerShell');
const tableTools = $('#tableTools');
const selectionManager = InkWriteSelection.create(editor);

const THEME_KEY = 'inkwrite-ui-theme';
const LOCAL_FONTS_KEY = 'inkwrite-local-fonts-v1';
const FORMAT_MARKS_KEY = 'inkwrite-show-formatting-v1';
const inWorkspace = document.documentElement.dataset.workspace === 'true';

function readStandaloneTheme(fallback='light') {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') return saved;
  if (fallback === 'dark' || fallback === 'light') return fallback;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyStandaloneTheme(theme, persistTheme=false) {
  if (inWorkspace) return;
  const dark = theme === 'dark';
  document.documentElement.classList.toggle('dark', dark);
  document.body.classList.toggle('dark', dark);
  if (persistTheme) localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light');
  const button = $('#themeButton');
  if (button) {
    button.textContent = dark ? '☀' : '◐';
    button.title = dark ? 'Usar tema claro' : 'Usar tema escuro';
  }
}

function setupThemeMode(documentTheme='light') {
  const button = $('#themeButton');
  const note = $('#workspaceThemeNote');
  if (inWorkspace) {
    document.body.classList.add('workspace-mode');
    if (button) button.hidden = true;
    if (note) {
      note.hidden = false;
      note.title = 'No Workspace, altere o tema nas Configurações globais ou pelo Terminal.';
    }
    return;
  }
  if (note) note.hidden = true;
  const hasSavedTheme = ['dark','light'].includes(localStorage.getItem(THEME_KEY));
  const theme = readStandaloneTheme(hasSavedTheme ? undefined : documentTheme);
  applyStandaloneTheme(theme, !hasSavedTheme);
}

function addFontOption(family) {
  const select = $('#fontName');
  const clean = String(family || '').trim();
  if (!clean || [...select.options].some(option => option.value.toLowerCase() === clean.toLowerCase())) return false;
  const option = document.createElement('option');
  option.value = clean;
  option.textContent = clean;
  select.append(option);
  return true;
}

function restoreImportedFonts() {
  try {
    const saved = JSON.parse(localStorage.getItem(LOCAL_FONTS_KEY) || '[]');
    if (Array.isArray(saved)) saved.forEach(addFontOption);
  } catch {}
}

async function importLocalFonts() {
  if (typeof window.queryLocalFonts !== 'function') {
    alert('Este navegador não permite listar as fontes do computador. No Chrome/Edge em localhost, atualize o navegador e tente novamente.');
    return;
  }
  try {
    const fonts = await window.queryLocalFonts();
    const families = [...new Set(fonts.map(font => font.family).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
    families.forEach(addFontOption);
    localStorage.setItem(LOCAL_FONTS_KEY, JSON.stringify(families));
    alert(`${families.length} fonte${families.length === 1 ? '' : 's'} do computador adicionada${families.length === 1 ? '' : 's'} ao menu.`);
  } catch (error) {
    if (error?.name === 'NotAllowedError') {
      alert('A permissão para acessar a lista de fontes foi negada pelo navegador.');
    } else {
      console.error(error);
      alert('Não foi possível importar a lista de fontes deste computador.');
    }
  }
}

let currentDocument = null;
let currentDocumentId = null;
let saveTimer = null;
let recoveryTimer = null;
let findIndex = -1;
let formatPainter = null;
let formatPainterArmed = false;
let editingLink = null;
let editRevision = 0;
let savedRevision = 0;
let saveInFlight = false;
let queuedSave = null;
let saveIdleWaiters = [];
let lastVersionAt = 0;
let versionCompareSelection = [];
let uiUpdateTimer = null;
let uiUpdateFrame = 0;
let lastOutlineSignature = '';
let lastPageGuideCount = -1;
let highlightTypingEnabled = false;

const AUTO_VERSION_INTERVAL = 2 * 60 * 1000;
const RECOVERY_DRAFT_DELAY = 180;

const DEFAULT_CONTENT = '';

const TEMPLATE_CONFIG = {
  blank: null,
  school: {
    title: 'Trabalho escolar',
    description: 'Visual acadêmico e atalhos para montar capa, seções e referências somente quando você pedir.',
    defaultStyle: 'academic',
    styles: [
      ['academic', 'Acadêmico'],
      ['clean', 'Limpo'],
      ['compact', 'Compacto']
    ],
    actions: [
      ['school-cover', '▣ Inserir capa'],
      ['school-section', '＋ Nova seção'],
      ['school-references', '≡ Referências']
    ]
  },
  letter: {
    title: 'Carta',
    description: 'Mude o estilo da correspondência e insira blocos de carta quando forem necessários.',
    defaultStyle: 'classic',
    styles: [
      ['classic', 'Clássica'],
      ['modern', 'Moderna'],
      ['minimal', 'Minimalista']
    ],
    actions: [
      ['letter-sender', '↥ Remetente'],
      ['letter-date', '◷ Data'],
      ['letter-recipient', '→ Destinatário'],
      ['letter-closing', '✎ Assinatura']
    ]
  },
  notes: {
    title: 'Anotações',
    description: 'Ferramentas rápidas para checklist, destaques e divisores sem preencher a página automaticamente.',
    defaultStyle: 'ruled',
    styles: [
      ['ruled', 'Pautado'],
      ['clean', 'Limpo'],
      ['compact', 'Compacto']
    ],
    actions: [
      ['notes-check', '☐ Checklist'],
      ['notes-callout', '◇ Destaque'],
      ['notes-date', '— Data / divisor']
    ]
  },
  report: {
    title: 'Relatório',
    description: 'Componentes de relatório para montar seções, destaques, dados e status de forma modular.',
    defaultStyle: 'business',
    styles: [
      ['business', 'Executivo'],
      ['technical', 'Técnico'],
      ['minimal', 'Minimalista']
    ],
    actions: [
      ['report-section', '＋ Seção'],
      ['report-highlight', '◇ Destaque'],
      ['report-table', '▦ Tabela de dados'],
      ['report-status', '● Status']
    ]
  }
};

const { escapeHtml, sanitizeImportedBody, sanitizeHtml, safeFilename, safeUrl } = InkWriteDocumentModel;

const commandManager = InkWriteCommands.create({
  root: editor,
  selection: selectionManager,
  afterEdit: commitHistory => afterEdit(commitHistory ? 'immediate' : false)
});
const tableManager = InkWriteTables.create({ editor, tools: tableTools, afterEdit });
const imageManager = InkWriteImages.create({ editor, input: imageInput, insertHtml: html => commandManager.insertHtml(html), escapeHtml, restoreSelection, afterEdit, scheduleSave, pushHistoryNow });
const dialogManager = InkWriteDialogs.create();
const shortcutManager = InkWriteShortcuts.create();
const footnoteManager = InkWriteFootnotes.create({ editor, selection: selectionManager, insertHtml: html => commandManager.insertHtml(html), afterEdit });
const spellingManager = InkWriteSpelling.create({ editor, getLanguage: () => $('#spellLanguage')?.value || 'pt-BR', afterEdit });
let layoutManager = null;

function exec(cmd, value=null) { return commandManager.execute(cmd, value); }

function formatBlock(tag) { exec('formatBlock', `<${tag}>`); }

function applyQuickStyle(style) {
  if (style !== 'caption') {
    formatBlock(style);
    return;
  }
  const blocks = getActiveBlocks();
  if (!blocks.length) return;
  blocks.forEach(block => {
    const target = block.tagName === 'P' ? block : replaceBlockTag(block, 'p');
    target.classList.add('ink-caption');
  });
  saveSelection();
  afterEdit(true);
}

function saveSelection() { return selectionManager.save(); }
function restoreSelection() { return selectionManager.restore(); }

editor.addEventListener('keyup', saveSelection);
editor.addEventListener('mouseup', saveSelection);
editor.addEventListener('focus', saveSelection);
let editorSelectionFrame = 0;
document.addEventListener('selectionchange', () => {
  const selection = window.getSelection();
  if (!selection?.anchorNode || !editor.contains(selection.anchorNode) || editorSelectionFrame) return;
  editorSelectionFrame = requestAnimationFrame(() => {
    editorSelectionFrame = 0;
    syncHighlightUi();
    updateRuler();
  });
});

function templateDefaultStyle(template=currentDocument?.template || 'blank') {
  return TEMPLATE_CONFIG[template]?.defaultStyle || 'default';
}

function getSettings() {
  return {
    paper: $('#paperSize').value,
    orientation: $('#orientation').value,
    margin: $('#marginPreset').value,
    customMargin: +$('#customMargin').value || 72,
    pageColor: $('#pageColor').value,
    lineHeight: $('#lineHeight').value,
    paragraphBefore: +$('#paragraphBefore').value || 0,
    paragraphSpacing: +$('#paragraphSpacing').value || 0,
    firstLineIndent: +$('#firstLineIndent').value || 0,
    headerText: $('#headerText').value || '',
    footerText: $('#footerText').value || '',
    pageNumberStyle: $('#pageNumberStyle').value || 'none',
    spellLanguage: $('#spellLanguage').value || 'pt-BR',
    spellcheck: $('#spellcheckEnabled').checked,
    zoom: +$('#zoomRange').value || 90,
    accent: $('#accentColor').value,
    uiTheme: inWorkspace ? (currentDocument?.settings?.uiTheme || 'light') : (document.body.classList.contains('dark') ? 'dark' : 'light'),
    templateStyle: $('#templateStyle').value || currentDocument?.settings?.templateStyle || templateDefaultStyle()
  };
}

function editorHtmlForStorage() {
  return InkWriteDocumentModel.serializeEditor(editor);
}

function collectDocument() {
  const base = currentDocument || {};
  return InkWriteDB.normalize({
    ...base,
    id: currentDocumentId || base.id,
    title: titleInput.value.trim() || 'Documento sem título',
    content: editorHtmlForStorage(),
    semantic: InkWriteDocumentModel.createSemanticSnapshot(editor),
    settings: getSettings()
  });
}

const exportManager = InkWriteExport.create({ editor, collectDocument, templateDefaultStyle });
const accessibilityManager = InkWriteAccessibility.create({ editor, root: editor, page });
function exportHtml() { return exportManager.exportHtml(); }
function exportWord() { return exportManager.exportWord(); }
function exportDocx() { return exportManager.exportDocx(); }
function exportTxt() { return exportManager.exportTxt(); }
function exportMarkdown() { return exportManager.exportMarkdown(); }
function exportRtf() { return exportManager.exportRtf(); }
function printDocument() { return exportManager.printDocument(); }
function openExportDialog() { return exportManager.openDialog(); }
function closeExportDialog() { return exportManager.closeDialog(); }

function syncDocumentUrl() {
  if (!currentDocumentId) return;
  const params = new URLSearchParams(location.search);
  if (params.get('document') === currentDocumentId) return;
  window.history.replaceState({}, '', `editor.html?document=${encodeURIComponent(currentDocumentId)}`);
}

function resetTransientEditorState() {
  imageManager.reset();
  selectionManager.clear();
  tableManager.reset();
  formatPainter = null;
  formatPainterArmed = false;
  const painterButton = $('#formatPainterButton');
  painterButton?.classList.remove('active');
  painterButton?.setAttribute('aria-pressed', 'false');
  const imagePanel = $('#imageProperties');
  if (imagePanel) imagePanel.hidden = true;
}

function resetSaveTracking() {
  clearTimeout(saveTimer);
  clearTimeout(recoveryTimer);
  saveTimer = null;
  recoveryTimer = null;
  editRevision = 0;
  savedRevision = 0;
  saveInFlight = false;
  queuedSave = null;
  saveIdleWaiters.splice(0).forEach(resolve => resolve(false));
  lastVersionAt = 0;
}

function ensureCurrentDocumentId() {
  if (!currentDocumentId) currentDocumentId = currentDocument?.id || InkWriteDB.createId();
  return currentDocumentId;
}

function sameDocumentPayload(a, b) {
  if (!a || !b) return false;
  return InkWriteDB.documentFingerprint(a) === InkWriteDB.documentFingerprint(b);
}

function queueRecoveryDraft() {
  ensureCurrentDocumentId();
  clearTimeout(recoveryTimer);
  recoveryTimer = setTimeout(async () => {
    try { await InkWriteDB.putDraft(collectDocument()); }
    catch (error) { console.warn('InkWrite: não foi possível atualizar o rascunho de recuperação.', error); }
  }, RECOVERY_DRAFT_DELAY);
}

async function createVersionCheckpoint(doc, reason='autosave', force=false) {
  const elapsed = Date.now() - lastVersionAt;
  if (!force && reason === 'autosave' && elapsed < AUTO_VERSION_INTERVAL) return null;
  const version = await InkWriteDB.createVersion(doc, { reason });
  if (version?.createdAt) lastVersionAt = Math.max(lastVersionAt, Date.parse(version.createdAt) || Date.now());
  return version;
}

async function persist(showMessage=false, options={}) {
  ensureCurrentDocumentId();
  clearTimeout(saveTimer);
  saveTimer = null;
  const reason = options.reason || (showMessage ? 'manual' : 'autosave');
  const forceVersion = !!options.forceVersion || reason !== 'autosave';

  if (saveInFlight) {
    queuedSave = {
      showMessage: !!(queuedSave?.showMessage || showMessage),
      reason: showMessage ? 'manual' : (queuedSave?.reason || reason),
      forceVersion: !!(queuedSave?.forceVersion || forceVersion)
    };
    return new Promise(resolve => saveIdleWaiters.push(resolve));
  }

  saveInFlight = true;
  const targetRevision = editRevision;
  const documentToSave = collectDocument();
  saveStatus.textContent = 'Salvando…';

  let documentSaved = false;
  let versionFailed = false;
  try {
    currentDocument = await InkWriteDB.putDocument(documentToSave);
    currentDocumentId = currentDocument.id;
    documentSaved = true;
    localStorage.setItem('inkwrite-last-document', currentDocumentId);
    syncDocumentUrl();

    try { await createVersionCheckpoint(currentDocument, reason, forceVersion); }
    catch (error) {
      versionFailed = true;
      console.warn('InkWrite: documento salvo, mas o checkpoint de versão falhou.', error);
    }

    const stillCurrent = targetRevision === editRevision && sameDocumentPayload(currentDocument, collectDocument());
    if (stillCurrent) {
      savedRevision = targetRevision;
      try { await InkWriteDB.deleteDraft(currentDocumentId); }
      catch (error) { console.warn('InkWrite: não foi possível limpar o rascunho já salvo.', error); }
      saveStatus.textContent = versionFailed ? 'Salvo · versão falhou' : (showMessage ? 'Salvo agora' : 'Salvo');
    } else {
      saveStatus.textContent = 'Alterado';
      try { await InkWriteDB.putDraft(collectDocument()); } catch {}
      queuedSave ||= { showMessage: false, reason: 'autosave', forceVersion: false };
    }
    void checkStorageHealth();
    return true;
  } catch (error) {
    console.error(error);
    saveStatus.textContent = 'Falha ao salvar';
    try { InkWriteDB.putDraftSync(collectDocument()); } catch {}
    return false;
  } finally {
    saveInFlight = false;
    if (queuedSave || (documentSaved && savedRevision < editRevision)) {
      const next = queuedSave || { showMessage: false, reason: 'autosave', forceVersion: false };
      queuedSave = null;
      setTimeout(() => persist(next.showMessage, next), 0);
    } else {
      saveIdleWaiters.splice(0).forEach(resolve => resolve(documentSaved));
    }
  }
}

async function checkStorageHealth() {
  const banner = $('#storageWarning');
  const text = $('#storageWarningText');
  if (!banner || !text) return;
  try {
    const summary = await InkWriteDB.getStorageSummary(currentDocumentId);
    const settings = InkWriteDB.getStorageSettings();
    const softLimit = settings.maxVersionStorageMB * 1024 * 1024;
    const overDocumentLimit = summary.versionsBytes > softLimit;
    const ratio = summary.browserQuota && Number.isFinite(summary.browserUsage) ? summary.browserUsage / summary.browserQuota : 0;
    if (!overDocumentLimit && ratio < .85) { banner.hidden = true; return; }
    const percent = ratio ? Math.round(ratio * 100) : 0;
    text.textContent = overDocumentLimit
      ? `O histórico deste documento ultrapassou o limite suave de ${settings.maxVersionStorageMB} MB. Checkpoints nomeados são preservados; remova-os manualmente se quiser liberar espaço.`
      : `${percent}% da quota do navegador está em uso. Exporte documentos importantes e remova versões antigas se necessário.`;
    const dismissedAt = +(sessionStorage.getItem('inkwrite-storage-warning-dismissed') || 0);
    banner.hidden = !overDocumentLimit && ratio < .95 && Date.now() - dismissedAt < 30 * 60 * 1000;
  } catch { banner.hidden = true; }
}
$('#storageWarningDismiss')?.addEventListener('click', () => {
  sessionStorage.setItem('inkwrite-storage-warning-dismissed', String(Date.now()));
  $('#storageWarning').hidden = true;
});

function scheduleSave() {
  editRevision += 1;
  saveStatus.textContent = 'Alterado';
  queueRecoveryDraft();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => persist(false, { reason: 'autosave' }), 650);
}

function snapshot() {
  return { content: editor.innerHTML, title: titleInput.value, settings: getSettings() };
}

function applyHistorySnapshot(shot) {
  resetTransientEditorState();
  editor.innerHTML = shot.content;
  normalizeEditorBlocks({ ensureParagraph: true });
  titleInput.value = shot.title;
  applySettings(shot.settings);
  updateAll();
  scheduleSave();
}

const historyManager = InkWriteHistory.create({
  capture: snapshot,
  apply: applyHistorySnapshot,
  limit: 60,
  delay: 420,
  onChange: state => {
    $('#undoButton').disabled = !state.canUndo;
    $('#redoButton').disabled = !state.canRedo;
  }
});

function pushHistoryNow() { return historyManager.pushNow(); }
function scheduleHistory() { return historyManager.schedule(); }
function updateHistoryButtons() {
  const state = historyManager.state();
  $('#undoButton').disabled = !state.canUndo;
  $('#redoButton').disabled = !state.canRedo;
}
function undo() { historyManager.undo(); }
function redo() { historyManager.redo(); }

function afterEdit(commitHistory=false) {
  scheduleUiUpdate();
  scheduleSave();
  if (commitHistory === 'immediate') pushHistoryNow();
  else if (commitHistory) scheduleHistory();
}

function renderTemplatePanel(selectedStyle) {
  const template = currentDocument?.template || 'blank';
  const config = TEMPLATE_CONFIG[template];
  page.dataset.template = template;
  const panel = $('#templatePanel');
  const select = $('#templateStyle');
  const actions = $('#templateActions');

  if (!config) {
    panel.hidden = true;
    select.innerHTML = '<option value="default">Padrão</option>';
    select.value = 'default';
    page.dataset.templateStyle = 'default';
    return;
  }

  panel.hidden = false;
  $('#templatePanelTitle').textContent = config.title;
  $('#templatePanelDescription').textContent = config.description;
  select.innerHTML = config.styles.map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
  const style = config.styles.some(([value]) => value === selectedStyle) ? selectedStyle : config.defaultStyle;
  select.value = style;
  page.dataset.templateStyle = style;
  actions.innerHTML = '';
  config.actions.forEach(([action, label]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.templateAction = action;
    button.textContent = label;
    actions.append(button);
  });
}

function applySettings(settings={}) {
  const s = {
    paper: 'a4', orientation: 'portrait', margin: 'normal', customMargin: 72,
    pageColor: '#ffffff', lineHeight: '1.6', paragraphBefore: 0, paragraphSpacing: 8, firstLineIndent: 0,
    headerText: '', footerText: '', pageNumberStyle: 'none', spellLanguage: 'pt-BR', spellcheck: true, zoom: 90,
    accent: '#2563eb', uiTheme: 'light', templateStyle: templateDefaultStyle(),
    ...settings
  };

  $('#paperSize').value = s.paper;
  $('#orientation').value = s.orientation;
  $('#marginPreset').value = s.margin;
  $('#customMargin').value = s.customMargin;
  $('#pageColor').value = s.pageColor;
  $('#lineHeight').value = s.lineHeight;
  $('#paragraphBefore').value = s.paragraphBefore;
  $('#paragraphSpacing').value = s.paragraphSpacing;
  $('#firstLineIndent').value = s.firstLineIndent;
  $('#headerText').value = s.headerText;
  $('#footerText').value = s.footerText;
  $('#pageNumberStyle').value = s.pageNumberStyle;
  $('#spellLanguage').value = s.spellLanguage;
  $('#spellcheckEnabled').checked = s.spellcheck !== false;
  editor.lang = s.spellLanguage || 'pt-BR';
  editor.spellcheck = s.spellcheck !== false;
  $('#zoomRange').value = s.zoom;
  $('#accentColor').value = s.accent;

  page.dataset.paper = s.paper;
  page.dataset.orientation = s.orientation;
  const paperGeometry = {
    a4: { portrait: [794, 1123], landscape: [1123, 794] },
    letter: { portrait: [816, 1056], landscape: [1056, 816] },
    a5: { portrait: [559, 794], landscape: [794, 559] }
  };
  const [pageWidth, pageHeight] = paperGeometry[s.paper]?.[s.orientation] || paperGeometry.a4.portrait;
  page.style.setProperty('--page-width', `${pageWidth}px`);
  page.style.setProperty('--page-min-height', `${pageHeight}px`);
  page.style.setProperty('--page', s.pageColor);
  page.style.backgroundColor = s.pageColor;
  page.style.backgroundImage = '';

  const margins = { narrow: 38, normal: 72, wide: 108, custom: +s.customMargin || 72 };
  page.style.setProperty('--page-padding', `${margins[s.margin] || 72}px`);
  page.style.setProperty('--line-height', s.lineHeight);
  page.style.setProperty('--paragraph-before', `${s.paragraphBefore}px`);
  page.style.setProperty('--paragraph-spacing', `${s.paragraphSpacing}px`);
  page.style.setProperty('--first-line-indent', `${s.firstLineIndent}px`);
  page.style.setProperty('--zoom', String(s.zoom / 100));
  document.documentElement.style.setProperty('--accent', s.accent);
  document.documentElement.style.setProperty('--accent-dark', shadeHex(s.accent, -20));

  $('#customMarginRow').hidden = s.margin !== 'custom';
  $('#paragraphBeforeValue').textContent = `${s.paragraphBefore} px`;
  $('#paragraphSpacingValue').textContent = `${s.paragraphSpacing} px`;
  $('#firstLineIndentValue').textContent = `${s.firstLineIndent} px`;
  $('#zoomValue').textContent = `${s.zoom}%`;
  const zoomPreset = $('#zoomPreset');
  if (zoomPreset) zoomPreset.value = ['75','100','125'].includes(String(s.zoom)) ? String(s.zoom) : 'custom';
  $('#statusZoom').textContent = `${s.zoom}%`;
  renderTemplatePanel(s.templateStyle);
  updatePaperStatus();
  requestAnimationFrame(updateRuler);
}

function shadeHex(hex, amt) {
  try {
    const num = parseInt(hex.slice(1), 16);
    const r = Math.max(0, Math.min(255, (num >> 16) + amt));
    const g = Math.max(0, Math.min(255, ((num >> 8) & 255) + amt));
    const b = Math.max(0, Math.min(255, (num & 255) + amt));
    return `#${(b | (g << 8) | (r << 16)).toString(16).padStart(6, '0')}`;
  } catch { return hex; }
}


const EDITOR_BLOCK_SELECTOR = 'p,h1,h2,h3,blockquote,pre,li';
const ROOT_PRESERVED_SELECTOR = 'p,h1,h2,h3,blockquote,pre,ul,ol,table,hr,img,figure,.page-break,.ink-toc,.ink-footnotes,.school-cover,.letter-block,.note-callout,.report-highlight,.report-status,.note-date-divider';

function normalizeEditorBlocks({ ensureParagraph=false } = {}) {
  const children = [...editor.childNodes];
  let currentParagraph = null;
  let changed = false;

  const paragraphBefore = node => {
    if (currentParagraph?.isConnected) return currentParagraph;
    const p = document.createElement('p');
    editor.insertBefore(p, node || null);
    currentParagraph = p;
    return p;
  };

  children.forEach(node => {
    if (!node.isConnected || node.parentNode !== editor) return;
    if (node.nodeType === Node.TEXT_NODE) {
      // Indentação/quebras entre blocos vindas de HTML importado não são
      // parágrafos reais. Removê-las evita criar linhas vazias artificiais.
      if (!node.nodeValue?.trim()) { node.remove(); changed = true; return; }
      paragraphBefore(node).append(node);
      changed = true;
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node;
    if (element.matches(ROOT_PRESERVED_SELECTOR)) {
      currentParagraph = null;
      return;
    }

    // Chrome/Edge podem criar DIVs genéricos dentro de contenteditable.
    // Convertê-los para P mantém a semântica de parágrafo e faz os comandos
    // de alinhamento, lista e recuo encontrarem um bloco válido.
    if (element.tagName === 'DIV' && !element.querySelector(ROOT_PRESERVED_SELECTOR)) {
      const p = document.createElement('p');
      [...element.attributes].forEach(attr => p.setAttribute(attr.name, attr.value));
      while (element.firstChild) p.append(element.firstChild);
      element.replaceWith(p);
      currentParagraph = null;
      changed = true;
      return;
    }

    // Elementos inline soltos na raiz também pertencem a um parágrafo.
    if (element.matches('span,a,strong,b,em,i,u,s,strike,sup,sub,font,code,br,mark')) {
      paragraphBefore(element).append(element);
      changed = true;
      return;
    }
    currentParagraph = null;
  });

  if (ensureParagraph && !editor.childNodes.length) {
    const p = document.createElement('p');
    p.append(document.createElement('br'));
    editor.append(p);
    changed = true;
  }
  return changed;
}

function normalizeActiveEditingBlock() {
  const selection = window.getSelection();
  let node = selection?.anchorNode;
  if (!node || !editor.contains(node)) {
    if (!editor.childNodes.length) normalizeEditorBlocks({ ensureParagraph: true });
    return;
  }

  if (node.nodeType === Node.TEXT_NODE && node.parentNode === editor) {
    const p = document.createElement('p');
    editor.insertBefore(p, node);
    p.append(node);
    return;
  }

  let element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  while (element?.parentElement && element.parentElement !== editor) element = element.parentElement;
  if (!element || element.parentElement !== editor) return;

  if (element.tagName === 'DIV' && !element.matches(ROOT_PRESERVED_SELECTOR) && !element.querySelector(ROOT_PRESERVED_SELECTOR)) {
    const p = document.createElement('p');
    [...element.attributes].forEach(attr => p.setAttribute(attr.name, attr.value));
    while (element.firstChild) p.append(element.firstChild);
    element.replaceWith(p);
  } else if (element.matches('span,a,strong,b,em,i,u,s,strike,sup,sub,font,code,br,mark')) {
    const p = document.createElement('p');
    editor.insertBefore(p, element);
    p.append(element);
  }
}

function getSelectionRange() {
  const selection = window.getSelection();
  if (selection?.rangeCount && editor.contains(selection.anchorNode)) return selection.getRangeAt(0).cloneRange();
  return selectionManager.getRange();
}

function blockAtBoundary(container, offset, preferPrevious=false) {
  if (!container) return null;
  let node = container;

  if (container === editor) {
    const children = [...editor.childNodes];
    if (!children.length) return null;
    const index = preferPrevious
      ? Math.max(0, Math.min(children.length - 1, offset - 1))
      : Math.max(0, Math.min(children.length - 1, offset));
    node = children[index];
  }

  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  if (!element) return null;
  if (element !== editor && element.matches?.(EDITOR_BLOCK_SELECTOR)) return element;
  const closest = element.closest?.(EDITOR_BLOCK_SELECTOR);
  if (closest && editor.contains(closest)) return closest;

  // Quando o boundary cai num contêiner (por exemplo, o próprio editor),
  // escolha o primeiro/último bloco descendente conforme o lado do Range.
  if (element.querySelectorAll) {
    const descendants = [...element.querySelectorAll(EDITOR_BLOCK_SELECTOR)];
    if (descendants.length) return preferPrevious ? descendants.at(-1) : descendants[0];
  }
  return null;
}

function blockPrefixIsEmpty(block, container, offset) {
  if (!block || !block.contains(container)) return false;
  try {
    const probe = document.createRange();
    probe.selectNodeContents(block);
    probe.setEnd(container, offset);
    return probe.toString().length === 0;
  } catch {
    return false;
  }
}

function blockSuffixIsEmpty(block, container, offset) {
  if (!block || !block.contains(container)) return false;
  try {
    const probe = document.createRange();
    probe.selectNodeContents(block);
    probe.setStart(container, offset);
    return probe.toString().length === 0;
  } catch {
    return false;
  }
}

function getActiveBlocks(range=null) {
  // Regra única para comandos de parágrafo/lista:
  // - cursor sem seleção => somente o bloco atual;
  // - seleção => somente os blocos entre o início e o fim realmente selecionados.
  if (!range) {
    normalizeActiveEditingBlock();
    range = getSelectionRange();
  }
  if (!range) return [];

  const ordered = [...editor.querySelectorAll(EDITOR_BLOCK_SELECTOR)].filter(block => !block.closest('.page-break'));
  if (!ordered.length) return [];

  if (range.collapsed) {
    const block = blockAtBoundary(range.startContainer, range.startOffset, false);
    return block ? [block] : [];
  }

  let startBlock = blockAtBoundary(range.startContainer, range.startOffset, false);
  let endBlock = blockAtBoundary(range.endContainer, range.endOffset, true);
  if (!startBlock || !endBlock) return [];

  let startIndex = ordered.indexOf(startBlock);
  let endIndex = ordered.indexOf(endBlock);
  if (startIndex < 0 || endIndex < 0) return [];
  if (startIndex > endIndex) [startIndex, endIndex] = [endIndex, startIndex];

  // Se a seleção começa exatamente no fim de um bloco, ele não foi escolhido.
  if (startIndex < endIndex && blockSuffixIsEmpty(ordered[startIndex], range.startContainer, range.startOffset)) {
    startIndex += 1;
  }
  // Se termina exatamente no começo do próximo bloco, ele também não foi escolhido.
  if (endIndex > startIndex && blockPrefixIsEmpty(ordered[endIndex], range.endContainer, range.endOffset)) {
    endIndex -= 1;
  }

  return startIndex <= endIndex ? ordered.slice(startIndex, endIndex + 1) : [];
}

function getActiveBlock() {
  return getActiveBlocks()[0] || null;
}

function createSelectionBookmarks(range) {
  if (!range) return null;
  const token = `ink-bookmark-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const makeMarker = kind => {
    const marker = document.createElement('span');
    marker.setAttribute('data-ink-selection-bookmark', `${token}-${kind}`);
    marker.setAttribute('aria-hidden', 'true');
    marker.style.cssText = 'display:inline-block;width:0;height:0;overflow:hidden;line-height:0;';
    return marker;
  };

  if (range.collapsed) {
    const marker = makeMarker('caret');
    const point = range.cloneRange();
    point.collapse(true);
    point.insertNode(marker);
    return { token, collapsed: true, marker };
  }

  const endMarker = makeMarker('end');
  const endPoint = range.cloneRange();
  endPoint.collapse(false);
  endPoint.insertNode(endMarker);

  const startMarker = makeMarker('start');
  const startPoint = range.cloneRange();
  startPoint.collapse(true);
  startPoint.insertNode(startMarker);
  return { token, collapsed: false, startMarker, endMarker };
}

function restoreSelectionBookmarks(bookmarks) {
  if (!bookmarks) return null;
  const selector = value => editor.querySelector(`[data-ink-selection-bookmark=\"${value}\"]`);
  let next = null;

  if (bookmarks.collapsed) {
    const marker = selector(`${bookmarks.token}-caret`);
    if (!marker) return null;
    next = document.createRange();
    next.setStartBefore(marker);
    next.collapse(true);
    commandManager.selectRange(next);
    marker.remove();
    saveSelection();
    return commandManager.currentRange({ restore: false });
  }

  const startMarker = selector(`${bookmarks.token}-start`);
  const endMarker = selector(`${bookmarks.token}-end`);
  if (!startMarker || !endMarker) {
    startMarker?.remove();
    endMarker?.remove();
    return null;
  }

  next = document.createRange();
  next.setStartAfter(startMarker);
  next.setEndBefore(endMarker);
  commandManager.selectRange(next);
  startMarker.remove();
  endMarker.remove();
  saveSelection();
  return commandManager.currentRange({ restore: false });
}

function cloneBlockShell(block, index=0) {
  const shell = block.cloneNode(false);
  if (index > 0) shell.removeAttribute('id');
  shell.removeAttribute('data-ink-selection-bookmark');
  return shell;
}

function splitBlockAtVisualBreaks(block) {
  if (!block?.isConnected || !block.querySelector?.('br')) return [block];
  // Quebras dentro de elementos estruturais aninhados não devem desmontar
  // tabelas/callouts inteiros. Aqui só lidamos com o conteúdo do bloco textual.
  const breaks = [...block.querySelectorAll('br')];
  if (!breaks.length) return [block];

  const segments = [];
  let startContainer = block;
  let startOffset = 0;

  const appendSegment = (endContainer, endOffset) => {
    const segmentRange = document.createRange();
    segmentRange.setStart(startContainer, startOffset);
    segmentRange.setEnd(endContainer, endOffset);
    const shell = cloneBlockShell(block, segments.length);
    const fragment = segmentRange.cloneContents();
    shell.append(fragment);
    if (!shell.childNodes.length || (!shell.textContent && !shell.querySelector('img,mark,span,a,strong,em,u,s,sup,sub'))) {
      shell.append(document.createElement('br'));
    }
    segments.push(shell);
  };

  breaks.forEach(br => {
    if (!block.contains(br)) return;
    const parent = br.parentNode;
    const index = [...parent.childNodes].indexOf(br);
    appendSegment(parent, index);
    startContainer = parent;
    startOffset = index + 1;
  });
  appendSegment(block, block.childNodes.length);

  // cloneContents pode gerar segmentos vazios extras quando há <br> final; isso
  // é intencional: visualmente essa quebra representa uma linha editável.
  block.replaceWith(...segments);
  return segments;
}

function prepareVisualLinesForBlockCommands(range=null) {
  range = range || getSelectionRange();
  if (!range) return null;

  // O contenteditable pode representar Enter de três formas diferentes entre
  // navegadores/estados do documento: P irmãos, DIVs irmãos ou um único bloco
  // com BRs. Primeiro normalize DIV/texto solto sem perder a seleção.
  const normalizeBookmarks = createSelectionBookmarks(range);
  normalizeEditorBlocks({ ensureParagraph: true });
  range = restoreSelectionBookmarks(normalizeBookmarks) || getSelectionRange();
  if (!range) return null;

  const blocks = getActiveBlocks(range);
  if (!blocks.length || !blocks.some(block => block.querySelector?.('br'))) return range;

  // Bookmarks viajam junto com cloneContents, então a seleção é restaurada na
  // linha exata depois que um <p>a<br>b<br>c</p> vira três blocos irmãos.
  const splitBookmarks = createSelectionBookmarks(range);
  blocks.forEach(block => {
    if (block?.isConnected && block.querySelector?.('br')) splitBlockAtVisualBreaks(block);
  });
  return restoreSelectionBookmarks(splitBookmarks) || getSelectionRange();
}

function replaceBlockTag(block, tagName) {
  const targetTag = String(tagName || '').toLowerCase();
  if (!block || !/^(p|h1|h2|h3|blockquote|pre)$/.test(targetTag)) return block;
  if (block.tagName.toLowerCase() === targetTag) return block;
  const replacement = document.createElement(targetTag);
  [...block.attributes].forEach(attr => replacement.setAttribute(attr.name, attr.value));
  replacement.classList.remove('ink-caption');
  if (!replacement.className) replacement.removeAttribute('class');
  while (block.firstChild) replacement.append(block.firstChild);
  block.replaceWith(replacement);
  return replacement;
}

commandManager.register('formatBlock', ({ value }) => {
  const tag = String(value || '').replace(/[<>]/g, '').toLowerCase();
  const blocks = getActiveBlocks().filter(block => block.tagName !== 'LI');
  if (!blocks.length) return false;
  selectionManager.save();
  blocks.forEach(block => replaceBlockTag(block, tag));
  selectionManager.restore();
  saveSelection();
  afterEdit(true);
  return true;
});

const ALIGN_COMMANDS = {
  justifyLeft: 'left',
  justifyCenter: 'center',
  justifyRight: 'right',
  justifyFull: 'justify'
};
Object.entries(ALIGN_COMMANDS).forEach(([command, alignment]) => {
  commandManager.register(command, () => {
    const preparedRange = prepareVisualLinesForBlockCommands();
    const blocks = getActiveBlocks(preparedRange);
    if (!blocks.length) return false;
    blocks.forEach(block => { block.style.textAlign = alignment; });
    saveSelection();
    afterEdit(true);
    return true;
  });
});

[
  ['bold', 'strong'],
  ['italic', 'em'],
  ['underline', 'u'],
  ['strikeThrough', 's'],
  ['superscript', 'sup'],
  ['subscript', 'sub']
].forEach(([command, tag]) => commandManager.registerInline(command, tag));

function textOffsetInsideBlock(block, container, offset) {
  if (!block || !container || !block.contains(container)) return 0;
  try {
    const probe = document.createRange();
    probe.selectNodeContents(block);
    probe.setEnd(container, offset);
    return probe.toString().length;
  } catch {
    return 0;
  }
}

function placeCaretAtTextOffset(block, wantedOffset=0) {
  if (!block) return false;
  let remaining = Math.max(0, Number(wantedOffset) || 0);
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const length = node.nodeValue?.length || 0;
    if (remaining <= length) {
      const next = document.createRange();
      next.setStart(node, remaining);
      next.collapse(true);
      commandManager.selectRange(next);
      return true;
    }
    remaining -= length;
  }
  const next = document.createRange();
  next.selectNodeContents(block);
  next.collapse(false);
  commandManager.selectRange(next);
  return true;
}

function copyUsefulBlockAttributes(source, target) {
  [...source.attributes].forEach(attr => {
    const name = attr.name.toLowerCase();
    if (name === 'id' || name === 'value' || name === 'start' || name === 'reversed' || name === 'type') return;
    target.setAttribute(attr.name, attr.value);
  });
}

function makeListShell(sourceList, tagName) {
  const list = document.createElement(tagName);
  [...sourceList.attributes].forEach(attr => {
    const name = attr.name.toLowerCase();
    if (name === 'id' || name === 'start' || name === 'reversed' || name === 'type') return;
    list.setAttribute(attr.name, attr.value);
  });
  return list;
}

function liToParagraph(item) {
  const p = document.createElement('p');
  copyUsefulBlockAttributes(item, p);
  while (item.firstChild) p.append(item.firstChild);
  return p;
}

function selectionGroupsForList(blocks) {
  const groups = [];
  blocks.forEach(block => {
    const isLi = block.tagName === 'LI';
    const parent = block.parentNode;
    const previous = groups.at(-1);
    const sameKind = previous && previous.isLi === isLi && previous.parent === parent;
    const prevBlock = previous?.blocks?.at(-1);
    const consecutive = prevBlock && prevBlock.nextElementSibling === block;
    if (sameKind && consecutive) previous.blocks.push(block);
    else groups.push({ isLi, parent, blocks: [block] });
  });
  return groups;
}

function transformListGroup(group, listTag) {
  const outputs = [];
  if (!group?.blocks?.length) return outputs;

  if (!group.isLi) {
    const parent = group.parent;
    const first = group.blocks[0];
    if (!parent || !first?.isConnected) return outputs;
    const list = document.createElement(listTag);
    parent.insertBefore(list, first);
    group.blocks.forEach(block => {
      if (!block.isConnected || block.parentNode !== parent) return;
      const item = document.createElement('li');
      copyUsefulBlockAttributes(block, item);
      while (block.firstChild) item.append(block.firstChild);
      list.append(item);
      block.remove();
      outputs.push(item);
    });
    if (!list.children.length) list.remove();
    return outputs;
  }

  const sourceList = group.parent;
  if (!sourceList?.isConnected || !sourceList.matches?.('ul,ol')) return outputs;
  const allItems = [...sourceList.children].filter(child => child.tagName === 'LI');
  const firstIndex = allItems.indexOf(group.blocks[0]);
  const lastIndex = allItems.indexOf(group.blocks.at(-1));
  if (firstIndex < 0 || lastIndex < firstIndex) return outputs;

  const beforeItems = allItems.slice(0, firstIndex);
  const selectedItems = allItems.slice(firstIndex, lastIndex + 1);
  const afterItems = allItems.slice(lastIndex + 1);
  const replacements = [];

  if (beforeItems.length) {
    const beforeList = makeListShell(sourceList, sourceList.tagName.toLowerCase());
    beforeList.append(...beforeItems);
    replacements.push(beforeList);
  }

  const sourceTag = sourceList.tagName.toLowerCase();
  if (sourceTag === listTag) {
    // Mesma lista clicada de novo: apenas as linhas escolhidas saem da lista.
    selectedItems.forEach(item => {
      const p = liToParagraph(item);
      replacements.push(p);
      outputs.push(p);
    });
  } else {
    // Trocar marcador/número também respeita somente os itens escolhidos.
    const middleList = makeListShell(sourceList, listTag);
    middleList.append(...selectedItems);
    replacements.push(middleList);
    outputs.push(...selectedItems);
  }

  if (afterItems.length) {
    const afterList = makeListShell(sourceList, sourceList.tagName.toLowerCase());
    afterList.append(...afterItems);
    replacements.push(afterList);
  }

  sourceList.replaceWith(...replacements);
  return outputs;
}

function registerListCommand(command, listTag) {
  commandManager.register(command, () => {
    let range = getSelectionRange();
    if (!range) return false;
    range = prepareVisualLinesForBlockCommands(range) || range;
    const blocks = getActiveBlocks(range);
    if (!blocks.length) return false;

    const wasCollapsed = range.collapsed;
    const caretBlock = wasCollapsed ? blocks[0] : null;
    const caretOffset = wasCollapsed ? textOffsetInsideBlock(caretBlock, range.startContainer, range.startOffset) : 0;
    const groups = selectionGroupsForList(blocks);
    const outputs = groups.flatMap(group => transformListGroup(group, listTag)).filter(Boolean);
    if (!outputs.length) return false;

    if (wasCollapsed) {
      placeCaretAtTextOffset(outputs[0], caretOffset);
    } else {
      const next = document.createRange();
      next.setStart(outputs[0], 0);
      const last = outputs.at(-1);
      next.setEnd(last, last.childNodes.length);
      commandManager.selectRange(next);
    }
    saveSelection();
    afterEdit(true);
    return true;
  });
}
registerListCommand('insertUnorderedList', 'ul');
registerListCommand('insertOrderedList', 'ol');

const LEGACY_FONT_SIZE_PX = { '1': 10, '2': 12, '3': 16, '4': 18, '5': 24, '6': 32, '7': 48 };
function registerInlineStyleCommand(command, property, transform = value => value) {
  commandManager.register(command, ({ value, currentRange, wrapSelection }) => {
    const range = currentRange();
    if (!range) return false;
    const resolved = transform(value);
    if (resolved == null || resolved === '') return false;
    return wrapSelection('span', { style: { [property]: resolved } });
  });
}
registerInlineStyleCommand('fontName', 'fontFamily');
registerInlineStyleCommand('fontSize', 'fontSize', value => `${LEGACY_FONT_SIZE_PX[String(value)] || 16}px`);
registerInlineStyleCommand('foreColor', 'color');
registerInlineStyleCommand('hiliteColor', 'backgroundColor');
registerInlineStyleCommand('backColor', 'backgroundColor');

function highlightedAncestor(node) {
  let element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  while (element && element !== editor) {
    // Marca-texto é formatação inline. Não trate fundo de parágrafo/callout
    // como se o modo de marca-texto estivesse ativo.
    const inlineHighlight = element.tagName === 'MARK'
      || (['SPAN','FONT'].includes(element.tagName) && !!element.style?.backgroundColor);
    if (inlineHighlight) return element;
    element = element.parentElement;
  }
  return null;
}

commandManager.register('clearHiliteColor', ({ currentRange, selectRange }) => {
  const range = currentRange();
  if (!range) return false;
  if (range.collapsed) {
    const active = highlightedAncestor(range.startContainer);
    if (!active) return true;
    const next = document.createRange();
    next.setStartAfter(active);
    next.collapse(true);
    selectRange(next);
    saveSelection();
    return true;
  }

  const fragment = range.extractContents();
  const candidates = [];
  if (fragment.nodeType === Node.ELEMENT_NODE) candidates.push(fragment);
  if (fragment.querySelectorAll) candidates.push(...fragment.querySelectorAll('mark,[style]'));
  candidates.forEach(element => {
    if (element.tagName === 'MARK') {
      const span = document.createElement('span');
      [...element.attributes].forEach(attr => span.setAttribute(attr.name, attr.value));
      span.style.removeProperty('background-color');
      while (element.firstChild) span.append(element.firstChild);
      element.replaceWith(span);
      return;
    }
    if (!element.style?.backgroundColor) return;
    element.style.removeProperty('background-color');
    if (!element.getAttribute('style')) element.removeAttribute('style');
  });
  [...fragment.querySelectorAll?.('span:not([style]):not([class]):not([id])') || []].reverse().forEach(span => span.replaceWith(...span.childNodes));
  const nodes = [...fragment.childNodes];
  range.insertNode(fragment);
  if (nodes.length) {
    const next = document.createRange();
    next.setStartBefore(nodes[0]);
    next.setEndAfter(nodes[nodes.length - 1]);
    selectRange(next);
  }
  saveSelection();
  afterEdit(true);
  return true;
});

['indent', 'outdent'].forEach(command => {
  commandManager.register(command, () => {
    const blocks = getActiveBlocks();
    if (!blocks.length) return false;
    const delta = command === 'indent' ? 24 : -24;
    blocks.forEach(block => {
      const current = parseFloat(block.style.marginLeft || getComputedStyle(block).marginLeft) || 0;
      const next = Math.max(0, current + delta);
      block.style.marginLeft = next ? `${next}px` : '';
    });
    saveSelection();
    afterEdit(true);
    return true;
  });
});

commandManager.register('removeFormat', ({ currentRange, selectRange }) => {
  const range = currentRange();
  if (!range || range.collapsed) return false;
  const fragment = range.extractContents();
  const blocked = 'strong,b,em,i,u,s,strike,sup,sub,span,font';
  [...fragment.querySelectorAll?.(blocked) || []].reverse().forEach(el => el.replaceWith(...el.childNodes));
  [...fragment.querySelectorAll?.('[style]') || []].forEach(el => el.removeAttribute('style'));
  const nodes = [...fragment.childNodes];
  range.insertNode(fragment);
  if (nodes.length) {
    const next = document.createRange();
    next.setStartBefore(nodes[0]);
    next.setEndAfter(nodes[nodes.length - 1]);
    selectRange(next);
  }
  saveSelection();
  afterEdit(true);
  return true;
});

async function writeClipboardSelection(cut=false) {
  restoreSelection();
  const selection = window.getSelection();
  if (!selection?.rangeCount || !editor.contains(selection.anchorNode) || selection.isCollapsed) return false;
  const range = selection.getRangeAt(0);
  const fragment = range.cloneContents();
  const holder = document.createElement('div');
  holder.append(fragment);
  const text = selection.toString();
  try {
    if (navigator.clipboard?.write && typeof ClipboardItem !== 'undefined') {
      const item = new ClipboardItem({
        'text/plain': new Blob([text], { type: 'text/plain' }),
        'text/html': new Blob([holder.innerHTML], { type: 'text/html' })
      });
      await navigator.clipboard.write([item]);
    } else if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      throw new Error('Clipboard API indisponível');
    }
    if (cut) {
      range.deleteContents();
      saveSelection();
      afterEdit('immediate');
    }
    return true;
  } catch (error) {
    console.warn('InkWrite: clipboard indisponível.', error);
    alert('O navegador bloqueou o acesso à área de transferência. Use Ctrl+C/Ctrl+X diretamente.');
    return false;
  }
}
commandManager.register('copy', () => { void writeClipboardSelection(false); return true; });
commandManager.register('cut', () => { void writeClipboardSelection(true); return true; });

commandManager.register('selectAll', ({ selectRange }) => {
  const range = document.createRange();
  range.selectNodeContents(editor);
  selectRange(range);
  saveSelection();
  return true;
});

function blockIndentMetrics(block=getActiveBlocks()[0]) {
  if (!block) return { left: 0, right: 0, first: +$('#firstLineIndent').value || 0 };
  const style = getComputedStyle(block);
  return {
    left: parseFloat(style.marginLeft) || 0,
    right: parseFloat(style.marginRight) || 0,
    first: parseFloat(style.textIndent) || 0
  };
}

function updateRuler() {
  if (!ruler || !rulerShell) return;
  const { width, padding } = visualPageMetrics();
  const zoom = Math.max(.5, Math.min(1.5, (+$('#zoomRange').value || 100) / 100));
  const displayWidth = width * zoom;
  ruler.style.width = `${displayWidth}px`;
  ruler.style.setProperty('--ruler-margin-left', `${padding * zoom}px`);
  ruler.style.setProperty('--ruler-margin-right', `${padding * zoom}px`);
  const metrics = blockIndentMetrics();
  const leftX = Math.max(padding, Math.min(width - padding - 20, padding + metrics.left));
  const firstX = Math.max(padding, Math.min(width - padding - 20, padding + metrics.left + metrics.first));
  const rightX = Math.max(padding + 20, Math.min(width - padding, width - padding - metrics.right));
  const set = (kind, value) => {
    const marker = ruler.querySelector(`[data-ruler-marker="${kind}"]`);
    if (marker) marker.style.left = `${value * zoom}px`;
  };
  set('left', leftX); set('first', firstX); set('right', rightX);
}

function applyIndentToBlocks(kind, rawX) {
  const { width, padding } = visualPageMetrics();
  const blocks = getActiveBlocks(selectionManager.getRange() || getSelectionRange());
  if (!blocks.length) return;
  const firstBlockMetrics = blockIndentMetrics(blocks[0]);
  const x = Math.max(padding, Math.min(width - padding, rawX));
  if (kind === 'left') {
    const value = Math.max(0, Math.min(width / 2, x - padding));
    blocks.forEach(block => block.style.marginLeft = `${Math.round(value)}px`);
  } else if (kind === 'right') {
    const value = Math.max(0, Math.min(width / 2, width - padding - x));
    blocks.forEach(block => block.style.marginRight = `${Math.round(value)}px`);
  } else if (kind === 'first') {
    const value = Math.max(-firstBlockMetrics.left, Math.min(160, x - padding - firstBlockMetrics.left));
    blocks.forEach(block => block.style.textIndent = `${Math.round(value)}px`);
  }
  updateRuler();
  afterEdit(false);
}

if (ruler) {
  ruler.addEventListener('pointerdown', event => {
    const marker = event.target.closest('[data-ruler-marker]');
    if (!marker) return;
    event.preventDefault();
    restoreSelection();
    saveSelection();
    const kind = marker.dataset.rulerMarker;
    marker.setPointerCapture?.(event.pointerId);
    const move = e => {
      const rect = ruler.getBoundingClientRect();
      const zoom = Math.max(.01, (+$('#zoomRange').value || 100) / 100);
      applyIndentToBlocks(kind, (e.clientX - rect.left) / zoom);
    };
    const up = e => {
      marker.releasePointerCapture?.(e.pointerId);
      marker.removeEventListener('pointermove', move);
      marker.removeEventListener('pointerup', up);
      marker.removeEventListener('pointercancel', up);
      afterEdit(true);
      restoreSelection();
      editor.focus();
    };
    marker.addEventListener('pointermove', move);
    marker.addEventListener('pointerup', up);
    marker.addEventListener('pointercancel', up);
  });
}

function selectCurrentParagraph() {
  editor.focus();
  restoreSelection();
  const range = getSelectionRange();
  const node = range?.startContainer;
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  const block = element?.closest?.('p,h1,h2,h3,blockquote,pre,li');
  if (!block || !editor.contains(block)) return;
  const next = document.createRange();
  next.selectNodeContents(block);
  const selection = window.getSelection();
  selection.removeAllRanges(); selection.addRange(next); saveSelection();
}

function duplicateSelection() {
  editor.focus();
  restoreSelection();
  const selection = window.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed || !editor.contains(selection.anchorNode)) {
    alert('Selecione um trecho do documento para duplicar.');
    return;
  }
  const range = selection.getRangeAt(0);
  const fragment = range.cloneContents();
  const insert = range.cloneRange();
  insert.collapse(false);
  insert.insertNode(fragment);
  selection.removeAllRanges();
  afterEdit(true);
}

function disableFormatPainter(message='Pincel desativado') {
  formatPainterArmed = false;
  formatPainter = null;
  const button = $('#formatPainterButton');
  button?.classList.remove('active');
  button?.setAttribute('aria-pressed', 'false');
  if (saveStatus) saveStatus.textContent = message;
}

function captureFormatPainter() {
  if (formatPainterArmed) {
    disableFormatPainter();
    return;
  }
  restoreSelection();
  const selection = window.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed || !editor.contains(selection.anchorNode)) {
    alert('Selecione um texto com a formatação que deseja copiar.');
    return;
  }
  const range = selection.getRangeAt(0);
  const node = range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement;
  const block = node?.closest?.('p,h1,h2,h3,blockquote,pre,li');
  const style = node ? getComputedStyle(node) : null;
  formatPainter = {
    fontName: style?.fontFamily?.split(',')[0]?.replace(/["']/g, '').trim() || '',
    fontSize: style?.fontSize || '',
    foreColor: style?.color || '',
    hiliteColor: style?.backgroundColor || '',
    bold: style ? (Number.parseInt(style.fontWeight, 10) >= 600 || style.fontWeight === 'bold') : false,
    italic: style?.fontStyle === 'italic',
    underline: style?.textDecorationLine?.includes('underline') || false,
    strikeThrough: style?.textDecorationLine?.includes('line-through') || false,
    block: block?.tagName?.toLowerCase() || 'p',
    align: block ? getComputedStyle(block).textAlign : 'left'
  };
  formatPainterArmed = true;
  const painterButton = $('#formatPainterButton');
  painterButton?.classList.add('active');
  painterButton?.setAttribute('aria-pressed', 'true');
  saveStatus.textContent = 'Pincel: selecione o destino';
}

function applyFormatPainter() {
  if (!formatPainterArmed || !formatPainter) return;
  const selection = window.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed || !editor.contains(selection.anchorNode)) return;
  const range = selection.getRangeAt(0);
  const blocks = getActiveBlocks(range);
  const wrapper = document.createElement('span');
  if (formatPainter.fontName) wrapper.style.fontFamily = formatPainter.fontName;
  if (formatPainter.fontSize) wrapper.style.fontSize = formatPainter.fontSize;
  if (formatPainter.foreColor) wrapper.style.color = formatPainter.foreColor;
  if (formatPainter.hiliteColor && !/rgba?\(0, 0, 0, 0\)|transparent/i.test(formatPainter.hiliteColor)) wrapper.style.backgroundColor = formatPainter.hiliteColor;
  if (formatPainter.bold) wrapper.style.fontWeight = '700';
  if (formatPainter.italic) wrapper.style.fontStyle = 'italic';
  const decorations = [];
  if (formatPainter.underline) decorations.push('underline');
  if (formatPainter.strikeThrough) decorations.push('line-through');
  if (decorations.length) wrapper.style.textDecorationLine = decorations.join(' ');
  wrapper.append(range.extractContents());
  range.insertNode(wrapper);
  const nextRange = document.createRange();
  nextRange.selectNodeContents(wrapper);
  selection.removeAllRanges();
  selection.addRange(nextRange);
  selectionManager.setRange(nextRange);

  blocks.forEach(block => {
    let target = block;
    if (block.tagName !== 'LI' && ['p','h1','h2','h3','blockquote','pre'].includes(formatPainter.block)) {
      target = replaceBlockTag(block, formatPainter.block);
    }
    target.style.textAlign = ['center', 'right', 'justify'].includes(formatPainter.align) ? formatPainter.align : 'left';
  });

  disableFormatPainter('Pincel aplicado');
  saveSelection();
  afterEdit('immediate');
}

function updatePaperStatus() {
  const names = { a4: 'A4', letter: 'Carta', a5: 'A5' };
  const orientation = $('#orientation').value === 'portrait' ? 'Retrato' : 'Paisagem';
  $('#statusPaper').textContent = `${names[$('#paperSize').value]} · ${orientation}`;
}

function visualPageMetrics() {
  const styles = getComputedStyle(page);
  return {
    height: parseFloat(styles.getPropertyValue('--page-min-height')) || 1123,
    width: parseFloat(styles.getPropertyValue('--page-width')) || 794,
    padding: parseFloat(styles.getPropertyValue('--page-padding')) || 72
  };
}

function estimatePageCount() {
  const { height, padding } = visualPageMetrics();
  const usableHeight = Math.max(120, height - (padding * 2));
  const contentHeight = Math.max(1, editor.scrollHeight);
  const automaticPages = Math.max(1, Math.ceil(contentHeight / usableHeight));
  const manualMinimum = editor.querySelectorAll('.page-break').length + 1;
  return Math.max(automaticPages, manualMinimum);
}

function currentVisualPage(totalPages=estimatePageCount()) {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return 1;
  try {
    const range = selection.getRangeAt(0).cloneRange();
    range.collapse(true);
    const rect = range.getBoundingClientRect();
    const pageRect = page.getBoundingClientRect();
    const zoom = Math.max(.01, (+$('#zoomRange').value || 100) / 100);
    const y = Math.max(0, (rect.top - pageRect.top) / zoom);
    const { height } = visualPageMetrics();
    return Math.max(1, Math.min(totalPages, Math.floor(y / height) + 1));
  } catch {
    return 1;
  }
}

function updateCurrentPageStatus(totalPages=estimatePageCount()) {
  const current = currentVisualPage(totalPages);
  const status = $('#statusCurrentPage');
  if (status) status.textContent = `Página ${current} de ${totalPages}`;
}

function updatePageGuides(force=false) {
  if (!pageGuides) return;
  const { height } = visualPageMetrics();
  const pages = estimatePageCount();
  page.style.setProperty('--page-stack-height', `${pages * height}px`);
  if (force || pages !== lastPageGuideCount) {
    lastPageGuideCount = pages;
    pageGuides.replaceChildren();
    const fragment = document.createDocumentFragment();
    for (let i = 1; i < pages; i++) {
      const guide = document.createElement('div');
      guide.className = 'page-guide';
      guide.style.top = `${i * height}px`;
      guide.dataset.label = `Página ${i + 1}`;
      fragment.append(guide);
    }
    pageGuides.append(fragment);
  }
  const stat = $('#statPages');
  const status = $('#statusPages');
  if (stat) stat.textContent = String(pages);
  if (status) status.textContent = `${pages} página${pages === 1 ? '' : 's'}`;
  updateCurrentPageStatus(pages);
  updateRuler();
}

function fitZoom(mode='width') {
  if (!canvasArea) return;
  const { width, height } = visualPageMetrics();
  const availableWidth = Math.max(160, canvasArea.clientWidth - 72);
  const availableHeight = Math.max(160, canvasArea.clientHeight - 72);
  let scale = availableWidth / width;
  if (mode === 'page') scale = Math.min(scale, availableHeight / height);
  setZoom(Math.round(scale * 100));
}

function toggleFormattingMarks(force) {
  const enabled = typeof force === 'boolean' ? force : !editor.classList.contains('show-formatting');
  editor.classList.toggle('show-formatting', enabled);
  localStorage.setItem(FORMAT_MARKS_KEY, enabled ? '1' : '0');
  const button = document.querySelector('[data-action="toggle-formatting"]');
  if (button) button.textContent = enabled ? 'Ocultar marcas ¶' : 'Mostrar marcas ¶';
}

async function pasteFromClipboard(mode = 'rich') {
  saveSelection();
  try {
    if (mode === 'plain') {
      if (!navigator.clipboard?.readText) throw new Error('Clipboard API indisponível');
      insertText(await navigator.clipboard.readText());
      return;
    }
    if (!navigator.clipboard?.read) throw new Error('Leitura avançada da área de transferência indisponível');
    const items = await navigator.clipboard.read();
    for (const item of items) {
      const imageType = item.types.find(type => type.startsWith('image/'));
      if (imageType) {
        await imageManager.insertFile(await item.getType(imageType), 'Imagem colada');
        return;
      }
      if (item.types.includes('text/html')) {
        const html = await (await item.getType('text/html')).text();
        insertHtml(sanitizeHtml(html, { paste: true, mergeFormatting: mode === 'merge' }));
        return;
      }
      if (item.types.includes('text/plain')) {
        insertText(await (await item.getType('text/plain')).text());
        return;
      }
    }
  } catch (error) {
    console.warn('InkWrite: clipboard programático bloqueado.', error);
    alert(mode === 'plain'
      ? 'O navegador bloqueou a leitura da área de transferência. Use Ctrl+Shift+V dentro do documento.'
      : 'O navegador bloqueou o botão de colar. Use Ctrl+V dentro do documento; o InkWrite ainda sanitiza a colagem.');
  }
}

async function pastePlainText() { return pasteFromClipboard('plain'); }

function openSymbolDialog() {
  saveSelection();
  dialogManager.open('symbolDialog');
}

function editorTextForStats() {
  const parts = [];
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || parent.closest('.page-break,[data-page-break-remove],.ink-footnote-back')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  while (walker.nextNode()) {
    const value = walker.currentNode.nodeValue?.replace(/\u200B/g, '');
    if (value) parts.push(value);
  }
  return parts.join(' ').replace(/\s+/g, ' ').trim();
}

function updateStats() {
  const text = editorTextForStats();
  const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
  const chars = text.length;
  const noSpaces = text.replace(/\s/g, '').length;
  const paragraphs = editor.querySelectorAll('p,h1,h2,h3,li,blockquote,pre').length || (text ? 1 : 0);
  const minutes = words ? Math.max(1, Math.ceil(words / 220)) : 0;
  $('#statWords').textContent = words;
  $('#statChars').textContent = chars;
  $('#statCharsNoSpaces').textContent = noSpaces;
  $('#statParagraphs').textContent = paragraphs;
  $('#statReadTime').textContent = `${minutes} min`;
  $('#statusWords').textContent = `${words} palavra${words === 1 ? '' : 's'}`;
  $('#statusChars').textContent = `${chars} caractere${chars === 1 ? '' : 's'}`;
  $('#statusParagraphs').textContent = `${paragraphs} parágrafo${paragraphs === 1 ? '' : 's'}`;
}

function updateOutline(force=false) {
  const list = $('#outlineList');
  const headings = [...editor.querySelectorAll('h1,h2,h3')];
  const signature = headings.map(h => `${h.tagName}:${h.textContent.trim()}`).join('|');
  if (!force && signature === lastOutlineSignature) return;
  lastOutlineSignature = signature;
  list.innerHTML = '';
  if (!headings.length) {
    list.innerHTML = '<p class="sidebar-empty">Adicione títulos para criar uma estrutura navegável.</p>';
    return;
  }
  headings.forEach((h, i) => {
    if (!h.id) h.id = `heading-${Date.now()}-${i}`;
    const b = document.createElement('button');
    b.className = `outline-item level-${h.tagName.slice(1)}`;
    b.textContent = h.textContent.trim() || '(Título vazio)';
    b.onclick = () => h.scrollIntoView({ behavior: 'smooth', block: 'center' });
    list.append(b);
  });
}

function cancelScheduledUiUpdate() {
  if (uiUpdateTimer) clearTimeout(uiUpdateTimer);
  uiUpdateTimer = null;
  if (uiUpdateFrame) cancelAnimationFrame(uiUpdateFrame);
  uiUpdateFrame = 0;
}

function updateAll() {
  cancelScheduledUiUpdate();
  normalizeEditorBlocks({ ensureParagraph: true });
  decoratePageBreaks();
  footnoteManager.renumber();
  updateStats();
  updateOutline(true);
  updateFindCount();
  updatePageGuides(true);
  layoutManager?.update();
  spellingManager.render();
  syncHighlightUi();
}

function scheduleUiUpdate() {
  // O caret/régua precisam responder rápido; as varreduras do documento podem
  // esperar alguns milissegundos e são agrupadas durante digitação contínua.
  if (!uiUpdateFrame) {
    uiUpdateFrame = requestAnimationFrame(() => {
      uiUpdateFrame = 0;
      layoutManager?.syncBlockFlow?.();
      syncHighlightUi();
    });
  }
  clearTimeout(uiUpdateTimer);
  uiUpdateTimer = setTimeout(() => {
    uiUpdateTimer = null;
    normalizeEditorBlocks({ ensureParagraph: true });
    decoratePageBreaks();
    footnoteManager.renumber();
    updateStats();
    updateOutline();
    updateFindCount();
    updatePageGuides();
    layoutManager?.update();
    spellingManager.render();
    syncHighlightUi();
  }, 140);
}

function openMenu(id, button) {
  $$('.top-menu').forEach(m => { if (m.id !== id) m.hidden = true; });
  $$('[data-menu-button]').forEach(b => { if (b !== button) b.classList.remove('active'); });
  const menu = $(`#${id}`);
  menu.hidden = !menu.hidden;
  button.classList.toggle('active', !menu.hidden);
}

function closeMenus() {
  $$('.top-menu').forEach(m => m.hidden = true);
  $$('[data-menu-button]').forEach(b => b.classList.remove('active'));
}

$$('[data-menu-button]').forEach(btn => btn.onclick = e => {
  e.stopPropagation();
  openMenu(btn.dataset.menuButton, btn);
});
document.addEventListener('click', e => { if (!e.target.closest('.menu-item')) closeMenus(); });

$$('[data-cmd]').forEach(btn => btn.addEventListener('mousedown', e => { saveSelection(); e.preventDefault(); }));
$$('[data-cmd]').forEach(btn => btn.addEventListener('click', () => exec(btn.dataset.cmd)));
$$('[data-block]').forEach(btn => btn.onclick = () => formatBlock(btn.dataset.block));
$('#blockStyle').onchange = e => applyQuickStyle(e.target.value);
$$('[data-quick-style]').forEach(button => button.addEventListener('click', () => applyQuickStyle(button.dataset.quickStyle)));
$('#fontName').onchange = e => exec('fontName', e.target.value);
$('#importFontsButton').onclick = importLocalFonts;
$('#fontSize').onchange = e => exec('fontSize', e.target.value);
$('#textColor').oninput = e => exec('foreColor', e.target.value);

function selectionHighlightElement(range=getSelectionRange()) {
  if (!range) return null;
  return highlightedAncestor(range.startContainer);
}

function syncHighlightUi() {
  const button = $('#highlightToggleButton');
  const colorInput = $('#highlightColor');
  if (!button || !colorInput) return;
  button.style.setProperty('--highlight-color', colorInput.value);
  // O botão representa somente o modo de escrita com marca-texto.
  // Estar com o cursor sobre um texto já marcado não liga a ferramenta.
  button.classList.toggle('active', highlightTypingEnabled);
  button.setAttribute('aria-pressed', highlightTypingEnabled ? 'true' : 'false');
  button.title = highlightTypingEnabled
    ? 'Marca-texto ligado para a escrita — clique novamente ou pressione Esc para desligar'
    : 'Ativar marca-texto para a escrita';
}

function collapseEditorSelectionToEnd() {
  const range = getSelectionRange();
  if (!range) return false;
  const next = range.cloneRange();
  next.collapse(false);
  commandManager.selectRange(next);
  saveSelection();
  return true;
}

function disableHighlightTyping() {
  if (!highlightTypingEnabled) { syncHighlightUi(); return false; }
  restoreSelection();
  const range = getSelectionRange();
  const active = range ? highlightedAncestor(range.startContainer) : null;
  if (active?.parentNode) {
    // Sair explicitamente do span destacado impede o navegador de herdar
    // background-color para os próximos caracteres.
    const next = document.createRange();
    next.setStartAfter(active);
    next.collapse(true);
    commandManager.selectRange(next);
  }
  highlightTypingEnabled = false;
  commandManager.cleanupMarkers();
  saveSelection();
  syncHighlightUi();
  return true;
}

$('#highlightToggleButton')?.addEventListener('mousedown', event => { saveSelection(); event.preventDefault(); });
$('#highlightToggleButton')?.addEventListener('click', () => {
  restoreSelection();
  const range = getSelectionRange();
  if (!range) return;

  if (range.collapsed) {
    if (highlightTypingEnabled) {
      disableHighlightTyping();
      return;
    }
    // Cursor sem seleção: liga explicitamente o modo para o que será digitado.
    exec('hiliteColor', $('#highlightColor').value);
    highlightTypingEnabled = true;
    saveSelection();
    syncHighlightUi();
    return;
  }

  // Texto selecionado: operação pontual. Nunca deixa o marca-texto grudado
  // na escrita seguinte.
  const alreadyHighlighted = !!selectionHighlightElement(range);
  if (alreadyHighlighted) exec('clearHiliteColor');
  else exec('hiliteColor', $('#highlightColor').value);
  highlightTypingEnabled = false;
  // Aplicação em seleção é pontual: ao terminar, o cursor fica depois do
  // trecho tratado, impedindo que a escrita seguinte herde o fundo.
  collapseEditorSelectionToEnd();
  syncHighlightUi();
});

$('#highlightColor')?.addEventListener('input', event => {
  $('#highlightToggleButton')?.style.setProperty('--highlight-color', event.target.value);
});
$('#highlightColor')?.addEventListener('change', event => {
  restoreSelection();
  const range = getSelectionRange();
  // Trocar a cor só aplica imediatamente quando existe texto selecionado.
  // Com apenas o cursor, a cor fica preparada para a próxima ativação do botão.
  if (range && !range.collapsed) {
    exec('hiliteColor', event.target.value);
    highlightTypingEnabled = false;
    collapseEditorSelectionToEnd();
  }
  syncHighlightUi();
});

function selectedTextTransform(mode) {
  const sel = window.getSelection();
  if (!sel.rangeCount || sel.isCollapsed) return;
  const text = sel.toString();
  const transformed = mode === 'upper' ? text.toUpperCase() : text.toLowerCase();
  commandManager.insertText(transformed);
}

function changeFontSize(delta) {
  const select = $('#fontSize');
  const options = [...select.options];
  let idx = select.selectedIndex;
  idx = Math.max(0, Math.min(options.length - 1, idx + delta));
  select.selectedIndex = idx;
  exec('fontSize', select.value);
}

function insertHtml(html) { return commandManager.insertHtml(html); }

function insertText(text) { return commandManager.insertText(text); }

function pageBreakHtml() {
  return '<div class="page-break" contenteditable="false" role="separator" aria-label="Quebra de página"><span class="page-break-label">Quebra de página</span><button type="button" class="page-break-remove" data-page-break-remove aria-label="Remover quebra de página" title="Remover quebra de página">× Remover</button></div>';
}

function decoratePageBreaks() {
  editor.querySelectorAll('.page-break').forEach(breakEl => {
    breakEl.setAttribute('contenteditable', 'false');
    breakEl.setAttribute('role', 'separator');
    breakEl.setAttribute('aria-label', 'Quebra de página');
    const label = breakEl.querySelector('span');
    if (label) label.classList.add('page-break-label');
    if (!breakEl.querySelector('[data-page-break-remove]')) {
      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'page-break-remove';
      removeButton.dataset.pageBreakRemove = '';
      removeButton.setAttribute('aria-label', 'Remover quebra de página');
      removeButton.title = 'Remover quebra de página';
      removeButton.textContent = '× Remover';
      breakEl.append(removeButton);
    }
  });
}

function removePageBreak(breakEl) {
  if (!breakEl?.classList?.contains('page-break')) return;
  breakEl.remove();
  afterEdit(true);
  editor.focus();
}

function insertPageBreak() {
  insertHtml(`${pageBreakHtml()}<p><br></p>`);
  decoratePageBreaks();
}
function insertQuote() { formatBlock('blockquote'); }
function insertCode() { formatBlock('pre'); }

function uniqueHeadingId(base, heading) {
  const clean = String(base || 'secao')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'secao';
  let id = clean;
  let suffix = 2;
  while (editor.querySelector(`#${CSS.escape(id)}`) && editor.querySelector(`#${CSS.escape(id)}`) !== heading) id = `${clean}-${suffix++}`;
  return id;
}

function buildTocHtml() {
  const headings = [...editor.querySelectorAll('h1,h2,h3')].filter(heading => !heading.closest('.ink-toc'));
  if (!headings.length) return '';
  headings.forEach(heading => {
    if (!heading.id) heading.id = uniqueHeadingId(heading.textContent, heading);
  });
  const items = headings.map(heading => {
    const level = Number(heading.tagName.slice(1)) || 1;
    return `<li class="toc-level-${level}"><a href="#${escapeHtml(heading.id)}">${escapeHtml(heading.textContent.trim() || 'Seção')}</a></li>`;
  }).join('');
  return `<nav class="ink-toc" contenteditable="false" aria-label="Sumário"><h2>Sumário</h2><ol>${items}</ol></nav>`;
}

function insertOrUpdateToc() {
  const html = buildTocHtml();
  if (!html) {
    alert('Adicione pelo menos um Título 1, 2 ou 3 antes de criar o sumário.');
    return;
  }
  const current = editor.querySelector('.ink-toc');
  if (current) {
    const doc = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html');
    current.replaceWith(doc.body.firstElementChild);
    afterEdit('immediate');
    return;
  }
  insertHtml(`${html}<p><br></p>`);
}

function selectedOrCaretLink() {
  const range = getSelectionRange();
  if (!range) return null;
  const node = range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement;
  const link = node?.closest?.('a');
  return link && editor.contains(link) ? link : null;
}

function openLinkDialog() {
  saveSelection();
  const sel = window.getSelection();
  editingLink = selectedOrCaretLink();
  $('#linkDialogTitle').textContent = editingLink ? 'Editar link' : 'Inserir link';
  $('#linkSubmitButton').textContent = editingLink ? 'Salvar' : 'Inserir';
  $('#removeLinkButton').hidden = !editingLink;
  $('#linkText').value = editingLink ? (editingLink.textContent || '') : (sel?.toString() || '');
  $('#linkUrl').value = editingLink?.getAttribute('href') || 'https://';
  $('#linkNewTab').checked = editingLink ? editingLink.getAttribute('target') === '_blank' : true;
  $('#linkDialog').showModal();
  setTimeout(() => $('#linkUrl').focus(), 30);
}

function unwrapLink(link) {
  if (!link?.parentNode) return;
  const fragment = document.createDocumentFragment();
  while (link.firstChild) fragment.append(link.firstChild);
  link.replaceWith(fragment);
}

$('#linkDialog').querySelectorAll('[data-dialog-close]').forEach(button => button.addEventListener('click', () => {
  editingLink = null;
  $('#linkDialog').close('cancel');
}));
$('#removeLinkButton').addEventListener('click', () => {
  if (!editingLink) return;
  unwrapLink(editingLink);
  editingLink = null;
  $('#linkDialog').close('default');
  afterEdit('immediate');
  editor.focus();
});
$('#linkForm').addEventListener('submit', e => {
  e.preventDefault();
  const text = $('#linkText').value.trim();
  const rawUrl = $('#linkUrl').value.trim();
  const url = safeUrl(rawUrl, 'href');
  if (!url) {
    alert('Use um endereço http, https, mailto ou tel válido.');
    $('#linkUrl').focus();
    return;
  }
  const label = text || rawUrl;
  const newTab = $('#linkNewTab').checked;
  if (editingLink) {
    editingLink.href = url;
    editingLink.textContent = label;
    if (newTab) {
      editingLink.target = '_blank';
      editingLink.rel = 'noopener noreferrer';
    } else {
      editingLink.removeAttribute('target');
      editingLink.removeAttribute('rel');
    }
    editingLink = null;
    $('#linkDialog').close('default');
    afterEdit('immediate');
    editor.focus();
    return;
  }
  const target = newTab ? ' target="_blank" rel="noopener noreferrer"' : '';
  $('#linkDialog').close('default');
  restoreSelection();
  insertHtml(`<a href="${escapeHtml(url)}"${target}>${escapeHtml(label)}</a>`);
});

function openTableDialog() {
  saveSelection();
  dialogManager.open('tableDialog');
}

$('#tableDialog').querySelectorAll('[data-dialog-close]').forEach(button => button.addEventListener('click', () => $('#tableDialog').close('cancel')));
$('#tableForm').addEventListener('submit', e => {
  e.preventDefault();
  const rows = Math.max(1, Math.min(50, +$('#tableRows').value || 3));
  const cols = Math.max(1, Math.min(20, +$('#tableCols').value || 3));
  const header = $('#tableHeader').checked;
  $('#tableDialog').close('default');
  restoreSelection();
  insertHtml(tableManager.tableHtml(rows, cols, header));
});

$('#symbolDialog')?.querySelectorAll('[data-symbol-close]').forEach(button => button.addEventListener('click', () => $('#symbolDialog').close('cancel')));
$('#symbolDialog')?.addEventListener('click', event => {
  const button = event.target.closest('[data-symbol]');
  if (!button) return;
  const symbol = button.dataset.symbol || '';
  $('#symbolDialog').close('default');
  restoreSelection();
  insertText(symbol);
});

function handleTemplateAction(action) {
  saveSelection();
  const today = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long' }).format(new Date());
  const snippets = {
    'school-cover': `<section class="school-cover"><p>[Instituição]</p><p>[Aluno(a)]</p><div class="school-cover-center"><h1>[Título]</h1><p>[Subtítulo, se houver]</p></div><p>[Cidade]<br>[Ano]</p></section><div class="page-break" contenteditable="false" role="separator" aria-label="Quebra de página"><span class="page-break-label">Quebra de página</span><button type="button" class="page-break-remove" data-page-break-remove aria-label="Remover quebra de página" title="Remover quebra de página">× Remover</button></div><p><br></p>`,
    'school-references': '<h2>Referências</h2><p><br></p>',
    'letter-sender': '<div class="letter-block letter-sender"><strong>[Seu nome]</strong><br>[Endereço ou contato]</div><p><br></p>',
    'letter-date': `<p class="letter-date" style="text-align:right">[Cidade], ${today}</p>`,
    'letter-recipient': '<div class="letter-block letter-recipient"><strong>[Destinatário]</strong><br>[Empresa / endereço, se necessário]</div><p><br></p>',
    'letter-closing': '<p>Atenciosamente,</p><div class="letter-signature"><br><br><strong>[Seu nome]</strong></div>',
    'notes-check': '<p class="check-item">☐&nbsp; </p>',
    'notes-callout': '<div class="note-callout"><p><strong>Nota</strong></p><p><br></p></div><p><br></p>',
    'notes-date': `<div class="note-date-divider"><span>${today}</span></div><p><br></p>`,
    'report-highlight': '<div class="report-highlight"><p><strong>[Destaque]</strong></p><p><br></p></div><p><br></p>',
    'report-table': '<table class="report-data"><thead><tr><th><br></th><th><br></th><th><br></th></tr></thead><tbody><tr><td><br></td><td><br></td><td><br></td></tr><tr><td><br></td><td><br></td><td><br></td></tr></tbody></table><p><br></p>',
    'report-status': '<div class="report-status"><span class="status-dot"></span><strong>[Status]</strong><span>[Detalhe]</span></div><p><br></p>'
  };

  if (action === 'school-section' || action === 'report-section') {
    const title = prompt('Nome da seção:')?.trim();
    if (!title) return;
    insertHtml(`<h2>${escapeHtml(title)}</h2><p><br></p>`);
    return;
  }

  if (snippets[action]) insertHtml(snippets[action]);
}

$('#templateActions').addEventListener('click', e => {
  const button = e.target.closest('[data-template-action]');
  if (button) handleTemplateAction(button.dataset.templateAction);
});

$('#templateStyle').addEventListener('change', e => {
  page.dataset.templateStyle = e.target.value;
  afterEdit(true);
});

function showFind(replace=false) {
  $('#findPanel').hidden = false;
  $('#replaceRow').hidden = !replace;
  findIndex = -1;
  $('#findInput').focus();
  $('#findInput').select();
  updateFindCount();
}

function escapeRegExp(v) { return v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function buildSearchTextIndex() {
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
  const entries = [];
  let text = '';
  let previousBlock = null;
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.closest('script,style,.page-break,.ink-toc')) continue;
    const block = node.parentElement?.closest('p,h1,h2,h3,li,blockquote,pre,td,th,figcaption') || node.parentElement;
    if (previousBlock && block !== previousBlock) text += '\n';
    const start = text.length;
    text += node.nodeValue || '';
    entries.push({ node, start, end: text.length });
    previousBlock = block;
  }
  return { text, entries };
}

function textOffsetToBoundary(entries, offset, preferEnd=false) {
  if (!entries.length) return null;
  const entry = entries.find(item => offset < item.end || (preferEnd && offset === item.end)) || entries[entries.length - 1];
  const local = Math.max(0, Math.min((entry.node.nodeValue || '').length, offset - entry.start));
  return { node: entry.node, offset: local };
}

function getFindMatches() {
  const q = $('#findInput').value;
  if (!q) return [];
  const caseSensitive = $('#matchCase').checked;
  const wholeWord = $('#wholeWord')?.checked;
  const index = buildSearchTextIndex();
  const haystack = caseSensitive ? index.text : index.text.toLowerCase();
  const needle = caseSensitive ? q : q.toLowerCase();
  const matches = [];
  let from = 0;
  const wordChar = ch => !!ch && /[\p{L}\p{N}_]/u.test(ch);
  while (from <= haystack.length - needle.length) {
    const at = haystack.indexOf(needle, from);
    if (at < 0) break;
    const endAt = at + needle.length;
    if (wholeWord && (wordChar(haystack[at - 1] || '') || wordChar(haystack[endAt] || ''))) {
      from = at + Math.max(1, needle.length);
      continue;
    }
    // Não cruze separadores artificiais de bloco.
    if (!index.text.slice(at, endAt).includes('\n')) {
      const start = textOffsetToBoundary(index.entries, at);
      const end = textOffsetToBoundary(index.entries, endAt, true);
      if (start && end) {
        try {
          const range = document.createRange();
          range.setStart(start.node, start.offset);
          range.setEnd(end.node, end.offset);
          matches.push(range);
        } catch {}
      }
    }
    from = at + Math.max(1, needle.length);
  }
  return matches;
}

function updateFindCount() {
  const matches = getFindMatches();
  if (!matches.length) {
    findIndex = -1;
    $('#findCount').textContent = '0';
    return 0;
  }
  if (findIndex >= matches.length) findIndex = -1;
  $('#findCount').textContent = findIndex >= 0 ? `${findIndex + 1}/${matches.length}` : String(matches.length);
  return matches.length;
}

function findNext(backward=false) {
  const matches = getFindMatches();
  if (!matches.length) { updateFindCount(); return false; }
  if (backward) findIndex = findIndex <= 0 ? matches.length - 1 : findIndex - 1;
  else findIndex = findIndex < 0 || findIndex >= matches.length - 1 ? 0 : findIndex + 1;
  const range = matches[findIndex];
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  range.startContainer.parentElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  saveSelection();
  updateFindCount();
  return true;
}

function replaceOne() {
  const q = $('#findInput').value;
  const repl = $('#replaceInput').value;
  if (!q) return;
  let sel = window.getSelection();
  let selected = sel.toString();
  let match = sel.rangeCount && editor.contains(sel.anchorNode) && ($('#matchCase').checked ? selected === q : selected.toLowerCase() === q.toLowerCase());
  if (!match) {
    if (!findNext(false)) return;
    sel = window.getSelection();
    selected = sel.toString();
    match = true;
  }
  if (match) {
    commandManager.insertText(repl);
    findIndex = -1;
    findNext(false);
  }
}

function replaceAllText() {
  const q = $('#findInput').value;
  const repl = $('#replaceInput').value;
  if (!q) return;
  const matches = getFindMatches();
  if (!matches.length) return;
  [...matches].reverse().forEach(range => {
    try {
      range.deleteContents();
      range.insertNode(document.createTextNode(repl));
    } catch {}
  });
  findIndex = -1;
  afterEdit('immediate');
  updateFindCount();
}

$('#findInput').oninput = () => { findIndex = -1; updateFindCount(); };
$('#matchCase').onchange = () => { findIndex = -1; updateFindCount(); };
$('#wholeWord').onchange = () => { findIndex = -1; updateFindCount(); };
$('#findNext').onclick = () => findNext(false);
$('#findPrev').onclick = () => findNext(true);
$('#findClose').onclick = () => { $('#findPanel').hidden = true; findIndex = -1; };
$('#replaceOne').onclick = replaceOne;
$('#replaceAll').onclick = replaceAllText;

function renderAccessibilityReport() {
  const issues = accessibilityManager.scan();
  const summary = $('#accessibilitySummary');
  const list = $('#accessibilityList');
  const errors = issues.filter(issue => issue.severity === 'error').length;
  const warnings = issues.length - errors;
  summary.textContent = issues.length
    ? `${issues.length} ponto${issues.length === 1 ? '' : 's'} para revisar · ${errors} erro${errors === 1 ? '' : 's'} · ${warnings} aviso${warnings === 1 ? '' : 's'}`
    : 'Nenhum problema comum encontrado nesta verificação.';
  list.innerHTML = '';
  if (!issues.length) {
    const empty = document.createElement('div');
    empty.className = 'accessibility-empty';
    empty.textContent = 'Tudo certo nesta checagem automática.';
    list.append(empty);
    return;
  }
  issues.forEach((issue, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'accessibility-item';
    button.dataset.accessibilityIndex = String(index);
    button.dataset.severity = issue.severity;
    const icon = document.createElement('span');
    icon.className = 'accessibility-severity';
    icon.textContent = issue.severity === 'error' ? '!' : 'i';
    const copy = document.createElement('span');
    const title = document.createElement('b');
    title.textContent = issue.severity === 'error' ? 'Corrigir' : 'Revisar';
    const message = document.createElement('span');
    message.textContent = issue.message;
    copy.append(title, document.createElement('br'), message);
    button.append(icon, copy);
    list.append(button);
  });
}

function openAccessibilityDialog() {
  renderAccessibilityReport();
  $('#accessibilityDialog')?.showModal();
}
function closeAccessibilityDialog() { if ($('#accessibilityDialog')?.open) $('#accessibilityDialog').close(); }
$('#accessibilityDialog')?.querySelectorAll('[data-accessibility-close]').forEach(button => button.addEventListener('click', closeAccessibilityDialog));
$('#rerunAccessibility')?.addEventListener('click', renderAccessibilityReport);
$('#accessibilityList')?.addEventListener('click', event => {
  const item = event.target.closest('[data-accessibility-index]');
  if (!item) return;
  const index = Number(item.dataset.accessibilityIndex);
  closeAccessibilityDialog();
  accessibilityManager.focusIssue(index);
});

const VERSION_REASON_LABELS = {
  manual: 'Salvamento manual',
  autosave: 'Autosave',
  import: 'Importação',
  new: 'Documento criado',
  recovery: 'Rascunho recuperado',
  restore: 'Versão restaurada',
  named: 'Checkpoint manual',
  'before-restore': 'Antes de restaurar'
};

function closeVersionsDialog() {
  const dialog = $('#versionsDialog');
  if (dialog?.open) dialog.close();
}

function formatVersionDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Data desconhecida';
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium' }).format(date);
}

async function renderVersions() {
  const list = $('#versionList');
  const count = $('#versionCount');
  if (!list || !currentDocumentId) return;
  const versions = await InkWriteDB.getVersions(currentDocumentId, 100);
  count.textContent = `${versions.length} vers${versions.length === 1 ? 'ão' : 'ões'}`;
  list.replaceChildren();

  if (!versions.length) {
    const empty = document.createElement('div');
    empty.className = 'version-empty';
    empty.textContent = 'Nenhum checkpoint salvo ainda. O primeiro aparece após um salvamento importante ou alguns minutos de edição.';
    list.append(empty);
    return;
  }

  versions.forEach(version => {
    const item = document.createElement('article');
    item.className = 'version-item';
    item.dataset.versionId = version.id;

    const meta = document.createElement('div');
    meta.className = 'version-meta';
    const title = document.createElement('strong');
    title.textContent = version.label || VERSION_REASON_LABELS[version.reason] || 'Checkpoint';
    const detail = document.createElement('small');
    const words = String(version.content || '').replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;
    detail.textContent = `${formatVersionDate(version.createdAt)} · ${words} palavra${words === 1 ? '' : 's'}`;
    meta.append(title, detail);

    const actions = document.createElement('div');
    actions.className = 'version-actions';
    const compare = document.createElement('button');
    compare.type = 'button';
    compare.className = 'version-compare-toggle';
    compare.dataset.versionCompare = version.id;
    compare.setAttribute('aria-pressed', versionCompareSelection.includes(version.id) ? 'true' : 'false');
    compare.textContent = versionCompareSelection.includes(version.id) ? 'Selecionada' : 'Comparar';
    const restore = document.createElement('button');
    restore.type = 'button';
    restore.dataset.versionRestore = version.id;
    restore.textContent = 'Restaurar';
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'version-delete';
    remove.dataset.versionDelete = version.id;
    remove.textContent = 'Excluir';
    actions.append(compare, restore, remove);
    item.append(meta, actions);
    list.append(item);
  });

  await refreshVersionStorageSummary();
}

function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(value < 10 * 1024 ? 1 : 0)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(value < 10 * 1024 ** 2 ? 1 : 0)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

async function refreshVersionStorageSummary() {
  const output = $('#versionStorage');
  if (!output || !currentDocumentId) return;
  try {
    const summary = await InkWriteDB.getStorageSummary(currentDocumentId);
    const local = `Este documento: ~${formatBytes(summary.totalBytes)}`;
    if (summary.browserUsage != null && summary.browserQuota) {
      const pct = Math.min(100, (summary.browserUsage / summary.browserQuota) * 100);
      output.textContent = `${local} · Navegador: ${formatBytes(summary.browserUsage)} / ${formatBytes(summary.browserQuota)} (${pct.toFixed(pct < 10 ? 1 : 0)}%)`;
      output.title = pct >= 80 ? 'Atenção: o armazenamento deste site está próximo da quota estimada pelo navegador.' : '';
      output.classList.toggle('storage-warning', pct >= 80);
    } else {
      output.textContent = local;
      output.title = 'A quota total não foi informada por este navegador.';
      output.classList.remove('storage-warning');
    }
  } catch (error) {
    console.warn('InkWrite: não foi possível estimar o armazenamento.', error);
    output.textContent = 'Armazenamento: estimativa indisponível';
  }
}

async function createNamedCheckpoint() {
  const raw = prompt('Nome deste checkpoint:', `Checkpoint ${new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date())}`);
  if (raw == null) return;
  const label = raw.trim();
  if (!label) return;
  await persist(false, { reason: 'autosave' });
  const version = await InkWriteDB.createVersion(collectDocument(), { reason: 'named', label });
  if (!version) {
    alert('Não foi possível criar um novo checkpoint porque o conteúdo é idêntico à versão mais recente.');
  }
  await renderVersions();
}

function versionPlainText(version) {
  return InkWriteDocumentModel.plainTextFromHtml(version?.content || '');
}

function versionPreviewDocument(version) {
  const settings = version?.settings || {};
  const pageColor = /^#[0-9a-f]{6}$/i.test(settings.pageColor || '') ? settings.pageColor : '#ffffff';
  const content = String(version?.content || '');
  return `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#eef1f5;font:14px/1.55 Arial,sans-serif;color:#172033}main{box-sizing:border-box;width:min(100% - 24px,760px);min-height:calc(100vh - 24px);margin:12px auto;padding:42px;background:${pageColor};box-shadow:0 6px 24px rgba(15,23,42,.12);overflow-wrap:anywhere}img{max-width:100%;height:auto}table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{border:1px solid #cfd7e5;padding:6px;overflow-wrap:anywhere}.page-break{margin:20px 0;border-top:2px dashed #9aa6b8;color:#667085}.page-break button{display:none}</style></head><body><main>${content}</main></body></html>`;
}

function compareTextStats(a, b) {
  const textA = versionPlainText(a);
  const textB = versionPlainText(b);
  const wordsA = textA ? textA.split(/\s+/).length : 0;
  const wordsB = textB ? textB.split(/\s+/).length : 0;
  let prefix = 0;
  while (prefix < textA.length && prefix < textB.length && textA[prefix] === textB[prefix]) prefix += 1;
  let suffix = 0;
  while (suffix < textA.length - prefix && suffix < textB.length - prefix && textA[textA.length - 1 - suffix] === textB[textB.length - 1 - suffix]) suffix += 1;
  const changedA = Math.max(0, textA.length - prefix - suffix);
  const changedB = Math.max(0, textB.length - prefix - suffix);
  return { wordsA, wordsB, charsA: textA.length, charsB: textB.length, changedA, changedB };
}

async function renderVersionComparison() {
  const selectA = $('#compareVersionA');
  const selectB = $('#compareVersionB');
  if (!selectA || !selectB) return;
  const [a, b] = await Promise.all([InkWriteDB.getVersion(selectA.value), InkWriteDB.getVersion(selectB.value)]);
  if (!a || !b) return;
  $('#comparePreviewA').srcdoc = versionPreviewDocument(a);
  $('#comparePreviewB').srcdoc = versionPreviewDocument(b);
  $('#compareLabelA').textContent = a.label || VERSION_REASON_LABELS[a.reason] || 'Versão A';
  $('#compareLabelB').textContent = b.label || VERSION_REASON_LABELS[b.reason] || 'Versão B';
  const stats = compareTextStats(a, b);
  const deltaWords = stats.wordsB - stats.wordsA;
  const deltaChars = stats.charsB - stats.charsA;
  $('#compareStats').textContent = `A: ${stats.wordsA} palavras / ${stats.charsA} caracteres · B: ${stats.wordsB} palavras / ${stats.charsB} caracteres · diferença B−A: ${deltaWords >= 0 ? '+' : ''}${deltaWords} palavras, ${deltaChars >= 0 ? '+' : ''}${deltaChars} caracteres · trechos centrais alterados: ~${stats.changedA} → ~${stats.changedB} caracteres.`;
}

async function openVersionCompareDialog() {
  const versions = await InkWriteDB.getVersions(currentDocumentId, 100);
  if (versions.length < 2) {
    alert('Crie pelo menos duas versões para comparar.');
    return;
  }
  const selectA = $('#compareVersionA');
  const selectB = $('#compareVersionB');
  const makeOption = version => {
    const option = document.createElement('option');
    option.value = version.id;
    option.textContent = `${version.label || VERSION_REASON_LABELS[version.reason] || 'Checkpoint'} · ${formatVersionDate(version.createdAt)}`;
    return option;
  };
  selectA.replaceChildren(...versions.map(makeOption));
  selectB.replaceChildren(...versions.map(makeOption));
  const preferred = versionCompareSelection.filter(id => versions.some(version => version.id === id));
  selectA.value = preferred[0] || versions[1].id;
  selectB.value = preferred[1] || versions[0].id;
  await renderVersionComparison();
  $('#versionCompareDialog')?.showModal();
}

function closeVersionCompareDialog() {
  const dialog = $('#versionCompareDialog');
  if (dialog?.open) dialog.close();
}

async function openVersionsDialog() {
  await persist(false, { reason: 'autosave' });
  const settings = InkWriteDB.getStorageSettings();
  const limit = $('#versionLimit');
  const storageLimit = $('#versionStorageLimit');
  if (limit) limit.value = String(settings.maxVersions);
  if (storageLimit) storageLimit.value = String(settings.maxVersionStorageMB);
  await renderVersions();
  $('#versionsDialog')?.showModal();
}

async function restoreVersion(versionId) {
  const version = await InkWriteDB.getVersion(versionId);
  if (!version) {
    alert('Essa versão não está mais disponível.');
    await renderVersions();
    return;
  }
  if (!confirm(`Restaurar a versão de ${formatVersionDate(version.createdAt)}? A versão atual será preservada como checkpoint.`)) return;

  await persist(false, { reason: 'before-restore', forceVersion: true });
  resetTransientEditorState();
  const createdAt = currentDocument?.createdAt;
  currentDocument = InkWriteDB.normalize({
    ...currentDocument,
    id: currentDocumentId,
    createdAt,
    title: version.title,
    template: version.template,
    content: version.content,
    semantic: version.semantic || null,
    settings: version.settings
  });
  titleInput.value = currentDocument.title;
  editor.innerHTML = InkWriteDocumentModel.resolveDocumentHtml(currentDocument);
  normalizeEditorBlocks({ ensureParagraph: true });
  applySettings(currentDocument.settings);
  editRevision += 1;
  queueRecoveryDraft();
  updateAll();
  pushHistoryNow();
  await persist(true, { reason: 'restore', forceVersion: true });
  await renderVersions();
}

$('#exportDialog').querySelectorAll('[data-export-close]').forEach(button => button.addEventListener('click', closeExportDialog));
$('#exportDialog').addEventListener('click', e => { if (e.target === $('#exportDialog')) closeExportDialog(); });
$('#exportDialog').querySelectorAll('[data-export-format]').forEach(button => button.addEventListener('click', () => {
  const format = button.dataset.exportFormat;
  closeExportDialog();
  if (format === 'docx') exportDocx();
  else if (format === 'word') exportWord();
  else if (format === 'rtf') exportRtf();
  else if (format === 'html') exportHtml();
  else if (format === 'md') exportMarkdown();
  else if (format === 'txt') exportTxt();
  else if (format === 'pdf') printDocument();
}));


$('#versionsDialog')?.querySelectorAll('[data-versions-close]').forEach(button => button.addEventListener('click', closeVersionsDialog));
$('#versionsDialog')?.addEventListener('click', event => { if (event.target === $('#versionsDialog')) closeVersionsDialog(); });
$('#versionList')?.addEventListener('click', async event => {
  const compare = event.target.closest('[data-version-compare]');
  if (compare) {
    const id = compare.dataset.versionCompare;
    if (versionCompareSelection.includes(id)) versionCompareSelection = versionCompareSelection.filter(item => item !== id);
    else versionCompareSelection = [...versionCompareSelection.slice(-1), id];
    await renderVersions();
    return;
  }
  const restore = event.target.closest('[data-version-restore]');
  if (restore) {
    await restoreVersion(restore.dataset.versionRestore);
    return;
  }
  const remove = event.target.closest('[data-version-delete]');
  if (!remove) return;
  if (!confirm('Excluir somente este checkpoint? O documento atual não será alterado.')) return;
  await InkWriteDB.deleteVersion(remove.dataset.versionDelete);
  await renderVersions();
});
$('#versionLimit')?.addEventListener('change', async event => {
  const settings = InkWriteDB.setStorageSettings({ maxVersions: event.target.value });
  event.target.value = String(settings.maxVersions);
  await InkWriteDB.pruneVersions(currentDocumentId, settings.maxVersions, settings.maxVersionStorageMB);
  await renderVersions();
});
$('#versionStorageLimit')?.addEventListener('change', async event => {
  const settings = InkWriteDB.setStorageSettings({ maxVersionStorageMB: event.target.value });
  event.target.value = String(settings.maxVersionStorageMB);
  await InkWriteDB.pruneVersions(currentDocumentId, settings.maxVersions, settings.maxVersionStorageMB);
  await renderVersions();
});
$('#createNamedVersion')?.addEventListener('click', createNamedCheckpoint);
$('#compareVersions')?.addEventListener('click', openVersionCompareDialog);
$('#compareVersionA')?.addEventListener('change', renderVersionComparison);
$('#compareVersionB')?.addEventListener('change', renderVersionComparison);
$('#versionCompareDialog')?.querySelectorAll('[data-compare-close]').forEach(button => button.addEventListener('click', closeVersionCompareDialog));
$('#versionCompareDialog')?.addEventListener('click', event => { if (event.target === $('#versionCompareDialog')) closeVersionCompareDialog(); });

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
  const closeList = () => { if (inList) html += `</${listType}>`; inList = false; listType = ''; };

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

async function importFile(file) {
  if (currentDocumentId && (editRevision > savedRevision || saveTimer || saveInFlight)) {
    await persist(false, { reason: 'autosave' });
  }
  const raw = await file.text();
  const lower = file.name.toLowerCase();
  let doc;

  if (lower.endsWith('.html') || lower.endsWith('.htm')) {
    const parsed = new DOMParser().parseFromString(raw, 'text/html');
    doc = InkWriteDB.normalize({
      id: InkWriteDB.createId(),
      title: parsed.title?.trim() || file.name.replace(/\.html?$/i, ''),
      template: 'blank',
      content: sanitizeImportedBody(parsed)
    });
  } else if (lower.endsWith('.md') || lower.endsWith('.markdown')) {
    doc = InkWriteDB.normalize({
      id: InkWriteDB.createId(),
      title: file.name.replace(/\.(md|markdown)$/i, ''),
      template: 'blank',
      content: markdownToHtml(raw)
    });
  } else if (lower.endsWith('.txt')) {
    doc = InkWriteDB.normalize({
      id: InkWriteDB.createId(),
      title: file.name.replace(/\.txt$/i, ''),
      template: 'blank',
      content: raw ? `<p>${escapeHtml(raw).replace(/\n/g, '<br>')}</p>` : ''
    });
  } else {
    throw new Error('Formato não suportado');
  }

  resetTransientEditorState();
  resetSaveTracking();
  currentDocument = doc;
  currentDocumentId = doc.id;
  titleInput.value = doc.title;
  editor.innerHTML = InkWriteDocumentModel.resolveDocumentHtml(doc);
  normalizeEditorBlocks({ ensureParagraph: true });
  applySettings(doc.settings);
  await persist(true, { reason: 'import', forceVersion: true });
  historyManager.reset(snapshot());
  updateAll();
}

importInput.onchange = async () => {
  const file = importInput.files[0];
  if (file) {
    try { await importFile(file); }
    catch (error) {
      console.error(error);
      alert('Não foi possível importar esse arquivo. Use HTML, TXT ou Markdown.');
    }
  }
  importInput.value = '';
};

async function newDocument() {
  if (!confirm('Criar um novo documento em branco? As alterações atuais já salvas continuarão na Home.')) return;
  if (currentDocumentId && (editRevision > savedRevision || saveTimer || saveInFlight)) {
    await persist(false, { reason: 'autosave' });
  }
  const doc = InkWriteDB.normalize({ id: InkWriteDB.createId(), title: 'Documento sem título', template: 'blank', content: '' });
  resetTransientEditorState();
  resetSaveTracking();
  currentDocument = doc;
  currentDocumentId = doc.id;
  titleInput.value = doc.title;
  editor.innerHTML = '';
  normalizeEditorBlocks({ ensureParagraph: true });
  applySettings(doc.settings);
  await persist(true, { reason: 'new', forceVersion: true });
  historyManager.reset(snapshot());
  updateAll();
}

function handleAction(action) {
  closeMenus();
  const actions = {
    'new-document': newDocument,
    save: () => persist(true, { reason: 'manual', forceVersion: true }),
    versions: openVersionsDialog,
    'import-file': () => importInput.click(),
    'open-export': openExportDialog,
    'export-docx': exportDocx,
    'export-word': exportWord,
    'export-rtf': exportRtf,
    'export-html': exportHtml,
    'export-md': exportMarkdown,
    'export-txt': exportTxt,
    print: printDocument,
    home: () => location.href = 'index.html',
    undo,
    redo,
    cut: () => exec('cut'),
    copy: () => exec('copy'),
    paste: () => pasteFromClipboard('rich'),
    'paste-merge': () => pasteFromClipboard('merge'),
    'paste-plain': pastePlainText,
    'select-all': () => exec('selectAll'),
    'select-paragraph': selectCurrentParagraph,
    'duplicate-selection': duplicateSelection,
    find: () => showFind(false),
    replace: () => showFind(true),
    'insert-link': openLinkDialog,
    'insert-image': () => { saveSelection(); imageInput.click(); },
    'insert-table': openTableDialog,
    'insert-symbol': openSymbolDialog,
    'insert-rule': () => insertHtml('<hr><p><br></p>'),
    'insert-toc': insertOrUpdateToc,
    'insert-footnote': () => footnoteManager.openDialog(),
    'insert-date': () => insertText(new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long' }).format(new Date())),
    'insert-time': () => insertText(new Intl.DateTimeFormat('pt-BR', { timeStyle: 'short' }).format(new Date())),
    'page-break': insertPageBreak,
    quote: insertQuote,
    caption: () => applyQuickStyle('caption'),
    code: insertCode,
    'format-painter': captureFormatPainter,
    'clear-format': () => exec('removeFormat'),
    uppercase: () => selectedTextTransform('upper'),
    lowercase: () => selectedTextTransform('lower'),
    'font-smaller': () => changeFontSize(-1),
    'font-bigger': () => changeFontSize(1),
    'toggle-outline': () => layout.classList.toggle('no-outline'),
    'toggle-properties': () => layout.classList.toggle('no-properties'),
    'toggle-formatting': () => toggleFormattingMarks(),
    accessibility: openAccessibilityDialog,
    shortcuts: () => shortcutManager.openDialog(),
    'focus-mode': () => document.body.classList.toggle('focus-mode'),
    'fit-width': () => fitZoom('width'),
    'fit-page': () => fitZoom('page'),
    'zoom-75': () => setZoom(75),
    'zoom-100': () => setZoom(100),
    'zoom-125': () => setZoom(125),
    'zoom-out': () => setZoom(+$('#zoomRange').value - 10),
    'zoom-reset': () => setZoom(100),
    'zoom-in': () => setZoom(+$('#zoomRange').value + 10)
  };
  actions[action]?.();
}

$$('[data-action]').forEach(btn => btn.addEventListener('click', () => handleAction(btn.dataset.action)));
$('#undoButton').onclick = undo;
$('#redoButton').onclick = redo;
$('#saveButton').onclick = () => persist(true, { reason: 'manual', forceVersion: true });
$('#exportButton').onclick = openExportDialog;

function setZoom(value) {
  value = Math.max(50, Math.min(150, value));
  $('#zoomRange').value = value;
  page.style.setProperty('--zoom', String(value / 100));
  $('#zoomValue').textContent = `${value}%`;
  $('#statusZoom').textContent = `${value}%`;
  const preset = $('#zoomPreset');
  if (preset) preset.value = ['75','100','125'].includes(String(value)) ? String(value) : 'custom';
  updateCurrentPageStatus();
  updateRuler();
  scheduleSave();
}

layoutManager = InkWriteLayout.create({
  editor,
  page,
  canvas: canvasArea,
  getPageMetrics: visualPageMetrics,
  getPageCount: estimatePageCount,
  getCurrentPage: currentVisualPage,
  getActiveBlock,
  onMarginChange: (margin, commit=true) => {
    $('#marginPreset').value = 'custom';
    $('#customMargin').value = margin;
    applySettings(getSettings());
    if (commit) afterEdit(true);
  },
  afterEdit
});

$('#themeButton').onclick = () => {
  if (inWorkspace) return;
  const next = document.body.classList.contains('dark') ? 'light' : 'dark';
  applyStandaloneTheme(next, true);
  scheduleSave();
};
$('#focusExitButton').onclick = () => document.body.classList.remove('focus-mode');

['paperSize','orientation','marginPreset','customMargin','pageColor','lineHeight','paragraphBefore','paragraphSpacing','firstLineIndent','accentColor','headerText','footerText','pageNumberStyle','spellLanguage','spellcheckEnabled'].forEach(id => {
  const el = $(`#${id}`);
  if (!el) return;
  const live = ['customMargin','paragraphBefore','paragraphSpacing','firstLineIndent','headerText','footerText'].includes(id);
  el.addEventListener(live ? 'input' : 'change', () => {
    applySettings(getSettings());
    afterEdit(live ? false : true);
  });
});
$('#zoomRange').oninput = e => setZoom(+e.target.value);
$('#zoomRange').onchange = () => pushHistoryNow();
$('#zoomPreset').onchange = e => {
  const value = e.target.value;
  if (value === 'fit-width') fitZoom('width');
  else if (value === 'fit-page') fitZoom('page');
  else if (value !== 'custom') setZoom(+value);
};

function insertParagraphBlockFromCaret() {
  let range = getSelectionRange();
  if (!range) return false;

  // Se houver seleção, apague apenas o trecho escolhido e use o início como
  // ponto de divisão. O navegador faria algo equivalente antes de criar Enter.
  if (!range.collapsed) {
    range.deleteContents();
    range.collapse(true);
    commandManager.selectRange(range);
    saveSelection();
  }

  const block = blockAtBoundary(range.startContainer, range.startOffset, false);
  // Listas têm semântica própria para Enter (novo LI / sair de lista). Deixe o
  // navegador tratar esses casos. PRE também mantém quebra de linha interna.
  if (!block || block.tagName === 'LI' || block.tagName === 'PRE') return false;
  if (!block.matches('p,h1,h2,h3,blockquote')) return false;

  const tailRange = document.createRange();
  tailRange.selectNodeContents(block);
  try { tailRange.setStart(range.startContainer, range.startOffset); }
  catch { return false; }
  const tail = tailRange.extractContents();

  const nextBlock = cloneBlockShell(block, 1);
  nextBlock.append(tail);
  if (!nextBlock.childNodes.length) nextBlock.append(document.createElement('br'));
  if (!block.childNodes.length) block.append(document.createElement('br'));
  block.after(nextBlock);

  const next = document.createRange();
  next.selectNodeContents(nextBlock);
  next.collapse(true);
  commandManager.selectRange(next);
  saveSelection();
  afterEdit('immediate');
  return true;
}

commandManager.registerBeforeInput('historyUndo', () => undo());
commandManager.registerBeforeInput('historyRedo', () => redo());
commandManager.registerBeforeInput('formatBold', () => exec('bold'));
commandManager.registerBeforeInput('formatItalic', () => exec('italic'));
commandManager.registerBeforeInput('formatUnderline', () => exec('underline'));
commandManager.registerBeforeInput('formatStrikeThrough', () => exec('strikeThrough'));
editor.addEventListener('beforeinput', event => {
  if (event.inputType === 'insertParagraph' && insertParagraphBlockFromCaret()) {
    event.preventDefault();
    return;
  }
  commandManager.handleBeforeInput(event);
});

editor.addEventListener('input', event => {
  commandManager.cleanupMarkers();
  if (event.isComposing) { afterEdit(true); return; }
  normalizeActiveEditingBlock();
  saveSelection();
  afterEdit(true);
});
titleInput.addEventListener('input', () => afterEdit(true));
titleInput.addEventListener('change', () => persist(false));

editor.addEventListener('click', event => {
  const removeButton = event.target.closest('[data-page-break-remove]');
  if (!removeButton) return;
  event.preventDefault();
  event.stopPropagation();
  removePageBreak(removeButton.closest('.page-break'));
});

editor.addEventListener('keydown', event => {
  if (event.key !== 'Backspace' && event.key !== 'Delete') return;
  const removeButton = document.activeElement?.closest?.('[data-page-break-remove]');
  if (!removeButton) return;
  event.preventDefault();
  removePageBreak(removeButton.closest('.page-break'));
});

editor.addEventListener('paste', async event => {
  saveSelection();
  const items = [...(event.clipboardData?.items || [])];
  const imageItem = items.find(item => item.type.startsWith('image/'));
  if (imageItem) {
    event.preventDefault();
    const file = imageItem.getAsFile();
    if (file) await imageManager.insertFile(file, 'Imagem colada');
    return;
  }

  const html = event.clipboardData?.getData('text/html') || '';
  const text = event.clipboardData?.getData('text/plain') || '';
  if (!html && !text) return;
  event.preventDefault();
  if (html) insertHtml(sanitizeHtml(html, { paste: true }));
  else insertText(text);
});

window.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (highlightTypingEnabled) { disableHighlightTyping(); return; }
    if (formatPainterArmed) { disableFormatPainter(); return; }
    if ($('#cropImageDialog')?.open) { imageManager.closeCropDialog(); return; }
    if ($('#footnoteDialog')?.open) { footnoteManager.closeDialog(); return; }
    if ($('#shortcutDialog')?.open) { shortcutManager.closeDialog(); return; }
    if ($('#accessibilityDialog')?.open) { closeAccessibilityDialog(); return; }
    if ($('#versionCompareDialog')?.open) { closeVersionCompareDialog(); return; }
    if ($('#versionsDialog')?.open) { closeVersionsDialog(); return; }
    if ($('#exportDialog').open) { closeExportDialog(); return; }
    if (document.body.classList.contains('focus-mode')) { document.body.classList.remove('focus-mode'); return; }
  }

  const actions = [
    ['pageBreak', () => insertPageBreak()],
    ['footnote', () => footnoteManager.openDialog()],
    ['toc', () => insertOrUpdateToc()],
    ['save', () => persist(true, { reason: 'manual', forceVersion: true })],
    ['bold', () => exec('bold')],
    ['italic', () => exec('italic')],
    ['underline', () => exec('underline')],
    ['link', () => openLinkDialog()],
    ['find', () => showFind(false)],
    ['replace', () => showFind(true)],
    ['undo', () => undo()],
    ['redo', () => redo()],
    ['print', () => printDocument()],
    ['export', () => openExportDialog()]
  ];
  const match = actions.find(([name]) => shortcutManager.matches(event, name));
  if (!match) return;
  event.preventDefault();
  match[1]();
});

editor.addEventListener('mouseup', () => {
  if (formatPainterArmed) setTimeout(applyFormatPainter, 0);
});

document.addEventListener('selectionchange', () => {
  const selection = window.getSelection();
  if (selection?.rangeCount && editor.contains(selection.anchorNode)) {
    updateCurrentPageStatus();
    requestAnimationFrame(updateRuler);
  }
});

if ('ResizeObserver' in window) {
  new ResizeObserver(() => updatePageGuides()).observe(editor);
}

window.addEventListener('resize', () => { updateCurrentPageStatus(); updateRuler(); });

window.addEventListener('beforeunload', () => {
  if (editRevision <= savedRevision && !saveInFlight && !saveTimer) return;
  clearTimeout(saveTimer);
  clearTimeout(recoveryTimer);
  try { InkWriteDB.putDraftSync(collectDocument()); } catch {}
});

async function initialize() {
  resetSaveTracking();
  const params = new URLSearchParams(location.search);
  const requestedId = params.get('document');
  let recoveryDraft = requestedId ? await InkWriteDB.getDraft(requestedId) : null;
  if (requestedId) currentDocument = await InkWriteDB.getDocument(requestedId);

  let recovered = false;
  if (!currentDocument && recoveryDraft) {
    currentDocument = InkWriteDB.normalize({
      id: requestedId,
      title: recoveryDraft.title,
      createdAt: recoveryDraft.createdAt,
      template: recoveryDraft.template,
      content: recoveryDraft.content,
      settings: recoveryDraft.settings
    });
    recovered = true;
  }

  if (!currentDocument) {
    currentDocument = InkWriteDB.normalize({
      id: InkWriteDB.createId(),
      title: 'Documento sem título',
      template: 'blank',
      content: ''
    });
    await InkWriteDB.putDocument(currentDocument);
  }

  currentDocumentId = currentDocument.id;
  recoveryDraft ||= await InkWriteDB.getDraft(currentDocumentId);
  if (!recovered && recoveryDraft) {
    const draftIsNewer = Date.parse(recoveryDraft.updatedAt || 0) > Date.parse(currentDocument.updatedAt || 0);
    const draftDiffers = !sameDocumentPayload(recoveryDraft, currentDocument);
    if (draftIsNewer && draftDiffers) {
      const shouldRecover = confirm('O InkWrite encontrou um rascunho mais recente que a última versão salva. Deseja recuperá-lo?');
      if (shouldRecover) {
        currentDocument = InkWriteDB.normalize({
          ...currentDocument,
          title: recoveryDraft.title,
          template: recoveryDraft.template,
          content: recoveryDraft.content,
          settings: recoveryDraft.settings,
          id: currentDocumentId,
          createdAt: currentDocument.createdAt
        });
        recovered = true;
      } else {
        await InkWriteDB.deleteDraft(currentDocumentId);
      }
    } else {
      await InkWriteDB.deleteDraft(currentDocumentId);
    }
  }

  localStorage.setItem('inkwrite-last-document', currentDocumentId);
  syncDocumentUrl();
  resetTransientEditorState();
  titleInput.value = currentDocument.title;
  editor.innerHTML = InkWriteDocumentModel.resolveDocumentHtml(currentDocument) || DEFAULT_CONTENT;
  normalizeEditorBlocks({ ensureParagraph: true });
  restoreImportedFonts();
  setupThemeMode(currentDocument.settings?.uiTheme || 'light');
  applySettings(currentDocument.settings);
  toggleFormattingMarks(localStorage.getItem(FORMAT_MARKS_KEY) === '1');
  updateAll();
  historyManager.reset(snapshot());

  const [latestVersion] = await InkWriteDB.getVersions(currentDocumentId, 1);
  lastVersionAt = latestVersion?.createdAt ? (Date.parse(latestVersion.createdAt) || 0) : 0;

  if (recovered) {
    editRevision = 1;
    saveStatus.textContent = 'Rascunho recuperado';
    await persist(false, { reason: 'recovery', forceVersion: true });
    saveStatus.textContent = 'Rascunho recuperado e salvo';
  } else {
    savedRevision = editRevision;
    saveStatus.textContent = 'Salvo';
  }
  layoutManager?.update();
  spellingManager.render();
  void checkStorageHealth();
}

initialize();
