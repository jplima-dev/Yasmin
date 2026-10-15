const viewport = document.getElementById('viewport');
const world = document.getElementById('world');
const canvas = document.getElementById('canvas');
const svg = document.getElementById('links');
const SVG_NS = 'http://www.w3.org/2000/svg';

const LEGACY_KEY = 'notas-flutuantes';
const BOARDS_KEY = 'notas-flutuantes:boards';
const CURRENT_BOARD_KEY = 'notas-flutuantes:current-board';

const LANGUAGE_KEY = 'notas-flutuantes:language';
const AUTO_SNAPSHOTS_KEY = 'notas-flutuantes:auto-snapshots';
const SNAPSHOT_INTERVAL_KEY = 'notas-flutuantes:snapshot-interval';
const RECOVERY_PREFIX = 'notas-flutuantes:recovery:';

const TRANSLATIONS = {
  'pt-BR': {
    documentTitle: 'Notas Flutuantes',
    metaDescription: 'App de notas flutuantes com quadros, ligações entre notas, busca, zoom e calendário.',
    addNote: 'Nova nota',
    addNoteTitle: 'Criar uma nova nota',
    undo: 'Desfazer',
    undoTitle: 'Desfazer (Ctrl+Z)',
    redo: 'Refazer',
    redoTitle: 'Refazer (Ctrl+Shift+Z ou Ctrl+Y)',
    linkMode: 'Ligar',
    linkModeTitle: 'Ativar modo de ligar notas',
    calendarTitle: 'Mostrar/ocultar calendário',
    boardSelectTitle: 'Trocar de quadro',
    addBoard: 'Quadro',
    addBoardTitle: 'Novo quadro',
    renameBoardTitle: 'Renomear quadro',
    searchPlaceholder: 'Buscar nas notas... (Enter navega)',
    zoomOutTitle: 'Diminuir zoom',
    zoomInTitle: 'Aumentar zoom',
    zoomResetTitle: 'Redefinir visualização',
    saved: 'Salvo',
    saveError: 'Erro ao salvar',
    settings: 'Configurações',
    settingsTitle: 'Configurações',
    close: 'Fechar',
    backup: 'Backup',
    exportAll: 'Exportar tudo',
    exportAllTitle: 'Baixar backup com todos os quadros em JSON',
    exportBoard: 'Exportar quadro atual',
    exportBoardTitle: 'Baixar backup apenas do quadro atual em JSON',
    importBackup: 'Importar backup',
    importBackupTitle: 'Carregar backup em JSON',
    history: 'Histórico e recuperação',
    autoSnapshots: 'Versões automáticas',
    snapshotInterval: 'Intervalo',
    snapshotIntervalTitle: 'Intervalo das versões automáticas',
    saveSnapshotNow: 'Salvar versão agora',
    saveSnapshotNowTitle: 'Salvar uma versão de recuperação agora',
    savedVersions: 'Versões salvas',
    snapshotSelectTitle: 'Escolher versão salva',
    restoreSnapshot: 'Restaurar versão selecionada',
    restoreSnapshotTitle: 'Restaurar a versão selecionada em todos os quadros',
    exportSnapshot: 'Exportar versão selecionada',
    exportSnapshotTitle: 'Exportar todos os quadros exatamente como estavam na versão selecionada',
    deleteSnapshotTitle: 'Excluir versão selecionada',
    confirmDeleteSnapshot: 'Excluir esta versão? Você poderá recuperá-la com Ctrl+Z.',
    noSnapshots: 'Nenhuma versão salva',
    automaticSnapshot: 'Automática',
    manualSnapshot: 'Manual',
    confirmRestoreSnapshot: 'Restaurar esta versão em TODOS os quadros? O estado atual poderá ser desfeito com Ctrl+Z.',
    snapshotSaved: 'Versão salva.',
    snapshotSaveError: 'Não foi possível salvar a versão.',
    intervalMinute: '1 minuto',
    intervalMinutes: ({ n }) => `${n} minutos`,
    appearance: 'Aparência',
    darkMode: 'Modo escuro',
    darkModeTitle: 'Alternar modo escuro',
    language: 'Idioma',
    languageLabel: 'Idioma da interface',
    languageTitle: 'Escolher idioma',
    languagePt: 'Português (Brasil)',
    languageEn: 'English',
    delete: 'Apagar',
    clearBoard: 'Limpar notas do quadro atual',
    clearBoardTitle: 'Apagar todas as notas do quadro atual',
    deleteBoard: 'Apagar quadro atual',
    deleteBoardTitle: 'Apagar o quadro atual inteiro',
    previousMonth: 'Mês anterior',
    nextMonth: 'Próximo mês',
    calendarFoot: 'Clique em um dia para inserir na nota ativa',
    createLink: 'Criar link',
    linkPlaceholder: 'Cole uma URL ou caminho local...',
    insertLink: 'Inserir link',
    cancel: 'Cancelar',
    file: 'Arquivo',
    fileLower: 'arquivo',
    closeEsc: 'Fechar',
    closeEscTitle: 'Fechar (Esc)',
    defaultBoard: ({ n }) => `Quadro ${n}`,
    boardFallback: 'Quadro',
    newBoardPrompt: 'Nome do novo quadro:',
    renameBoardPrompt: 'Renomear quadro:',
    cannotDeleteLastBoard: 'Não é possível apagar o último quadro.',
    confirmDeleteBoard: ({ name }) => `Apagar o quadro "${name}" e todas as suas notas?`,
    previewUnavailable: 'Pré-visualização não disponível.',
    previewUnavailableType: 'Pré-visualização não disponível para este tipo de arquivo.',
    saveChanges: 'Salvar alterações na nota',
    discard: 'Descartar',
    editHint: 'Edite o texto acima e salve para atualizar a nota',
    savedShort: 'Salvo!',
    downloadFile: 'Baixar arquivo',
    siteCannotEmbed: 'Este site não permite ser exibido aqui.',
    openNewTab: 'Abrir em nova aba',
    imageTooLarge: ({ name }) => `${name} (imagem grande demais pra importar)`,
    textFileTooLarge: ({ name }) => `${name} (arquivo grande demais pra importar o conteúdo)`,
    pdfTooLarge: ({ name }) => `${name} (PDF grande demais pra importar)`,
    dragExplorerToOpen: 'Arraste do Explorer para abrir',
    folder: 'Pasta',
    stats: ({ notes, links }) => `${notes} nota${notes === 1 ? '' : 's'} · ${links} ligaç${links === 1 ? 'ão' : 'ões'}`,
    view: 'Ver',
    pinNote: 'Fixar nota',
    unpinNote: 'Desafixar nota',
    noteColor: 'Cor da nota',
    insertDate: 'Inserir data',
    makeLink: 'Transformar texto selecionado em link',
    linkButton: 'Link',
    openLink: 'Abrir link (Shift+clique abre no navegador)',
    deleteNote: 'Apagar',
    notePlaceholder: 'Escreva algo...',
    removeLink: 'Remover link',
    linkLabelPrompt: 'Rótulo da ligação:',
    colorNumber: ({ n }) => `Cor ${n}`,
    colors: ['Amarelo', 'Laranja', 'Vermelho', 'Rosa claro', 'Rosa escuro', 'Roxo', 'Azul', 'Ciano', 'Verde claro', 'Verde escuro', 'Marrom', 'Cinza'],
    confirmClearBoard: 'Apagar todas as notas deste quadro?',
    importAllConfirm: ({ boards, notes }) => `Importar ${boards} quadro(s) com ${notes} nota(s) no total.\n\nIsso vai substituir TODOS os seus quadros atuais. Continuar?`,
    importSuccess: ({ boards }) => `${boards} quadro(s) importado(s) com sucesso!`,
    importBoardConfirm: 'Importar vai substituir as notas do quadro atual. Continuar?',
    unrecognizedFileFormat: 'Formato de arquivo não reconhecido.',
    importError: ({ message }) => `Não foi possível importar esse arquivo: ${message}`,
    confirmDeleteSelected: ({ count }) => `Apagar ${count} nota(s) selecionada(s)?`,
    months: ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'],
    dow: ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']
  },
  en: {
    documentTitle: 'Floating Notes',
    metaDescription: 'Floating notes app with boards, links between notes, search, zoom, and calendar.',
    addNote: 'New note',
    addNoteTitle: 'Create a new note',
    undo: 'Undo',
    undoTitle: 'Undo (Ctrl+Z)',
    redo: 'Redo',
    redoTitle: 'Redo (Ctrl+Shift+Z or Ctrl+Y)',
    linkMode: 'Link',
    linkModeTitle: 'Enable note linking mode',
    calendarTitle: 'Show/hide calendar',
    boardSelectTitle: 'Switch board',
    addBoard: 'Board',
    addBoardTitle: 'New board',
    renameBoardTitle: 'Rename board',
    searchPlaceholder: 'Search notes... (Enter to navigate)',
    zoomOutTitle: 'Zoom out',
    zoomInTitle: 'Zoom in',
    zoomResetTitle: 'Reset view',
    saved: 'Saved',
    saveError: 'Save error',
    settings: 'Settings',
    settingsTitle: 'Settings',
    close: 'Close',
    backup: 'Backup',
    exportAll: 'Export all',
    exportAllTitle: 'Download a JSON backup with all boards',
    exportBoard: 'Export current board',
    exportBoardTitle: 'Download a JSON backup of the current board only',
    importBackup: 'Import backup',
    importBackupTitle: 'Load a JSON backup',
    history: 'History and recovery',
    autoSnapshots: 'Automatic versions',
    snapshotInterval: 'Interval',
    snapshotIntervalTitle: 'Automatic version interval',
    saveSnapshotNow: 'Save version now',
    saveSnapshotNowTitle: 'Save a recovery version now',
    savedVersions: 'Saved versions',
    snapshotSelectTitle: 'Choose a saved version',
    restoreSnapshot: 'Restore selected version',
    restoreSnapshotTitle: 'Restore the selected version across all boards',
    exportSnapshot: 'Export selected version',
    exportSnapshotTitle: 'Export all boards exactly as they were in the selected version',
    deleteSnapshotTitle: 'Delete selected version',
    confirmDeleteSnapshot: 'Delete this version? You can recover it with Ctrl+Z.',
    noSnapshots: 'No saved versions',
    automaticSnapshot: 'Automatic',
    manualSnapshot: 'Manual',
    confirmRestoreSnapshot: 'Restore this version across ALL boards? You can undo the current state with Ctrl+Z.',
    snapshotSaved: 'Version saved.',
    snapshotSaveError: 'Could not save the version.',
    intervalMinute: '1 minute',
    intervalMinutes: ({ n }) => `${n} minutes`,
    appearance: 'Appearance',
    darkMode: 'Dark mode',
    darkModeTitle: 'Toggle dark mode',
    language: 'Language',
    languageLabel: 'Interface language',
    languageTitle: 'Choose language',
    languagePt: 'Português (Brasil)',
    languageEn: 'English',
    delete: 'Delete',
    clearBoard: 'Clear notes from current board',
    clearBoardTitle: 'Delete all notes from the current board',
    deleteBoard: 'Delete current board',
    deleteBoardTitle: 'Delete the entire current board',
    previousMonth: 'Previous month',
    nextMonth: 'Next month',
    calendarFoot: 'Click a day to insert it into the active note',
    createLink: 'Create link',
    linkPlaceholder: 'Paste a URL or local path...',
    insertLink: 'Insert link',
    cancel: 'Cancel',
    file: 'File',
    fileLower: 'file',
    closeEsc: 'Close',
    closeEscTitle: 'Close (Esc)',
    defaultBoard: ({ n }) => `Board ${n}`,
    boardFallback: 'Board',
    newBoardPrompt: 'New board name:',
    renameBoardPrompt: 'Rename board:',
    cannotDeleteLastBoard: 'You cannot delete the last board.',
    confirmDeleteBoard: ({ name }) => `Delete the board "${name}" and all its notes?`,
    previewUnavailable: 'Preview unavailable.',
    previewUnavailableType: 'Preview unavailable for this file type.',
    saveChanges: 'Save changes to note',
    discard: 'Discard',
    editHint: 'Edit the text above and save to update the note',
    savedShort: 'Saved!',
    downloadFile: 'Download file',
    siteCannotEmbed: 'This site cannot be displayed here.',
    openNewTab: 'Open in new tab',
    imageTooLarge: ({ name }) => `${name} (image is too large to import)`,
    textFileTooLarge: ({ name }) => `${name} (file is too large to import its contents)`,
    pdfTooLarge: ({ name }) => `${name} (PDF is too large to import)`,
    dragExplorerToOpen: 'Drag from File Explorer to open',
    folder: 'Folder',
    stats: ({ notes, links }) => `${notes} note${notes === 1 ? '' : 's'} · ${links} link${links === 1 ? '' : 's'}`,
    view: 'View',
    pinNote: 'Pin note',
    unpinNote: 'Unpin note',
    noteColor: 'Note color',
    insertDate: 'Insert date',
    makeLink: 'Turn selected text into a link',
    linkButton: 'Link',
    openLink: 'Open link (Shift+click opens in browser)',
    deleteNote: 'Delete',
    notePlaceholder: 'Write something...',
    removeLink: 'Remove link',
    linkLabelPrompt: 'Link label:',
    colorNumber: ({ n }) => `Color ${n}`,
    colors: ['Yellow', 'Orange', 'Red', 'Light pink', 'Dark pink', 'Purple', 'Blue', 'Cyan', 'Light green', 'Dark green', 'Brown', 'Gray'],
    confirmClearBoard: 'Delete all notes from this board?',
    importAllConfirm: ({ boards, notes }) => `Import ${boards} board(s) with ${notes} note(s) total.\n\nThis will replace ALL your current boards. Continue?`,
    importSuccess: ({ boards }) => `${boards} board(s) imported successfully!`,
    importBoardConfirm: 'Importing will replace the notes on the current board. Continue?',
    unrecognizedFileFormat: 'Unrecognized file format.',
    importError: ({ message }) => `Could not import this file: ${message}`,
    confirmDeleteSelected: ({ count }) => `Delete ${count} selected note(s)?`,
    months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    dow: ['S', 'M', 'T', 'W', 'T', 'F', 'S']
  }
};

let currentLanguage = localStorage.getItem(LANGUAGE_KEY);
if (!TRANSLATIONS[currentLanguage]) currentLanguage = 'pt-BR';

function t(key, params = {}) {
  const value = TRANSLATIONS[currentLanguage][key] ?? TRANSLATIONS['pt-BR'][key] ?? key;
  if (typeof value === 'function') return value(params);
  if (typeof value === 'string') {
    return value.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`);
  }
  return value;
}

function setText(id, key) {
  const el = document.getElementById(id);
  if (el) el.textContent = t(key);
}

function setAttr(id, attr, key) {
  const el = document.getElementById(id);
  if (el) el.setAttribute(attr, t(key));
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLanguage === 'en' ? 'en' : 'pt-BR';
  document.title = t('documentTitle');
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute('content', t('metaDescription'));

  setText('addNote', 'addNote'); setAttr('addNote', 'title', 'addNoteTitle');
  setText('undoBtn', 'undo'); setAttr('undoBtn', 'title', 'undoTitle');
  setText('redoBtn', 'redo'); setAttr('redoBtn', 'title', 'redoTitle');
  setText('linkMode', 'linkMode'); setAttr('linkMode', 'title', 'linkModeTitle');
  setAttr('toggleCal', 'title', 'calendarTitle');
  setAttr('boardSelect', 'title', 'boardSelectTitle');
  setText('addBoard', 'addBoard'); setAttr('addBoard', 'title', 'addBoardTitle');
  setAttr('renameBoard', 'title', 'renameBoardTitle');
  setAttr('searchInput', 'placeholder', 'searchPlaceholder');
  setAttr('zoomOut', 'title', 'zoomOutTitle');
  setAttr('zoomIn', 'title', 'zoomInTitle');
  setAttr('zoomReset', 'title', 'zoomResetTitle');
  setText('settingsToggle', 'settings'); setAttr('settingsToggle', 'title', 'settingsTitle');
  setText('settingsHeaderText', 'settings');
  setAttr('settingsClose', 'title', 'close'); setAttr('settingsClose', 'aria-label', 'close');
  setText('backupHeading', 'backup');
  setText('exportNotes', 'exportAll'); setAttr('exportNotes', 'title', 'exportAllTitle');
  setText('exportBoardNotes', 'exportBoard'); setAttr('exportBoardNotes', 'title', 'exportBoardTitle');
  setText('importNotes', 'importBackup'); setAttr('importNotes', 'title', 'importBackupTitle');
  setText('historyHeading', 'history');
  setText('autoSnapshotsLabel', 'autoSnapshots');
  setText('snapshotIntervalLabel', 'snapshotInterval'); setAttr('snapshotInterval', 'title', 'snapshotIntervalTitle');
  setText('saveSnapshotNow', 'saveSnapshotNow'); setAttr('saveSnapshotNow', 'title', 'saveSnapshotNowTitle');
  setText('snapshotSelectLabel', 'savedVersions'); setAttr('snapshotSelect', 'title', 'snapshotSelectTitle');
  setAttr('deleteSnapshot', 'title', 'deleteSnapshotTitle'); setAttr('deleteSnapshot', 'aria-label', 'deleteSnapshotTitle');
  setText('restoreSnapshot', 'restoreSnapshot'); setAttr('restoreSnapshot', 'title', 'restoreSnapshotTitle');
  setText('exportSnapshot', 'exportSnapshot'); setAttr('exportSnapshot', 'title', 'exportSnapshotTitle');
  setText('appearanceHeading', 'appearance');
  setText('darkMode', 'darkMode'); setAttr('darkMode', 'title', 'darkModeTitle');
  setText('languageHeading', 'language'); setText('languageLabel', 'languageLabel'); setAttr('languageSelect', 'title', 'languageTitle');
  setText('deleteHeading', 'delete');
  setText('clearAll', 'clearBoard'); setAttr('clearAll', 'title', 'clearBoardTitle');
  setText('deleteBoard', 'deleteBoard'); setAttr('deleteBoard', 'title', 'deleteBoardTitle');
  setAttr('calPrev', 'aria-label', 'previousMonth'); setAttr('calNext', 'aria-label', 'nextMonth');
  setText('calFoot', 'calendarFoot');
  setText('llp-label', 'createLink'); setAttr('llp-url-input', 'placeholder', 'linkPlaceholder');
  setText('llp-confirm', 'insertLink'); setText('llp-cancel', 'cancel');
  setText('file-viewer-close', 'closeEsc'); setAttr('file-viewer-close', 'title', 'closeEscTitle');

  const snapshotInterval = document.getElementById('snapshotInterval');
  if (snapshotInterval) {
    snapshotInterval.querySelectorAll('option').forEach(option => {
      const n = Number(option.value);
      option.textContent = n === 1 ? t('intervalMinute') : t('intervalMinutes', { n });
    });
  }

  const languageSelect = document.getElementById('languageSelect');
  if (languageSelect) {
    languageSelect.value = currentLanguage;
    const pt = languageSelect.querySelector('option[value="pt-BR"]');
    const en = languageSelect.querySelector('option[value="en"]');
    if (pt) pt.textContent = t('languagePt');
    if (en) en.textContent = t('languageEn');
  }

  const viewer = document.getElementById('file-viewer-overlay');
  if (viewer && viewer.classList.contains('hidden')) setText('file-viewer-title', 'file');
  const saveIndicator = document.getElementById('saveIndicator');
  if (saveIndicator && !saveIndicator.classList.contains('show')) saveIndicator.textContent = t('saved');
}

function setLanguage(language) {
  if (!TRANSLATIONS[language]) return;
  currentLanguage = language;
  localStorage.setItem(LANGUAGE_KEY, currentLanguage);
  applyStaticTranslations();
  render();
  if (!document.getElementById('calendar').classList.contains('hidden')) renderCalendar();
  if (appReady) refreshSnapshotList();
}


const NOTE_COLORS = [
  { name: 'Amarelo',
    light: { bg: '#fff8c4', border: '#e0ce6a', handle: '#ffe874', swatch: '#f0c800' },
    dark:  { bg: '#3a3210', border: '#5e5428', handle: '#4a4018', swatch: '#c8a800' }
  },
  { name: 'Laranja',
    light: { bg: '#ffe6cc', border: '#e6a850', handle: '#ffd4a0', swatch: '#f08020' },
    dark:  { bg: '#3a2610', border: '#6a4820', handle: '#4a3018', swatch: '#c06018' }
  },
  { name: 'Vermelho',
    light: { bg: '#ffd8d8', border: '#e08888', handle: '#ffb8b8', swatch: '#d84040' },
    dark:  { bg: '#3a1010', border: '#6a2828', handle: '#4a1818', swatch: '#a02828' }
  },
  { name: 'Rosa claro',
    light: { bg: '#ffe1ef', border: '#e8a0c0', handle: '#ffc4de', swatch: '#f070a8' },
    dark:  { bg: '#3a1828', border: '#6a3050', handle: '#4a2038', swatch: '#b04878' }
  },
  { name: 'Rosa escuro',
    light: { bg: '#ffc8dc', border: '#e06090', handle: '#ffaac8', swatch: '#d83878' },
    dark:  { bg: '#3e1030', border: '#701848', handle: '#501838', swatch: '#a02860' }
  },
  { name: 'Roxo',
    light: { bg: '#ecdcff', border: '#b890e0', handle: '#ddc0ff', swatch: '#9050d0' },
    dark:  { bg: '#281840', border: '#502878', handle: '#382058', swatch: '#6830a8' }
  },
  { name: 'Azul',
    light: { bg: '#dbeeff', border: '#88bce8', handle: '#bcd8ff', swatch: '#3880d0' },
    dark:  { bg: '#101e38', border: '#203860', handle: '#182848', swatch: '#2060a8' }
  },
  { name: 'Ciano',
    light: { bg: '#d4f4f8', border: '#60c0cc', handle: '#a8e4ec', swatch: '#18a0b0' },
    dark:  { bg: '#082830', border: '#105060', handle: '#103840', swatch: '#108090' }
  },
  { name: 'Verde claro',
    light: { bg: '#dcf5d0', border: '#80c860', handle: '#c0ecac', swatch: '#48a828' },
    dark:  { bg: '#102010', border: '#205818', handle: '#183018', swatch: '#307818' }
  },
  { name: 'Verde escuro',
    light: { bg: '#c4e8b4', border: '#50a830', handle: '#a0d880', swatch: '#288818' },
    dark:  { bg: '#081808', border: '#184010', handle: '#102010', swatch: '#186010' }
  },
  { name: 'Marrom',
    light: { bg: '#f0e0c8', border: '#c09060', handle: '#e0c8a0', swatch: '#a06030' },
    dark:  { bg: '#281808', border: '#503020', handle: '#382010', swatch: '#784828' }
  },
  { name: 'Cinza',
    light: { bg: '#efefef', border: '#a8a8b8', handle: '#d8d8e4', swatch: '#7070a0' },
    dark:  { bg: '#1c1c28', border: '#404058', handle: '#282840', swatch: '#505080' }
  },
];

let linkMode = false;
let linkPick = null;
let moveMode = false;
let activeNoteId = null;

// Seleção múltipla
let selectedNoteIds = new Set();
let isMultiSelecting = false;

let topZ = 10;

let panX = 0;
let panY = 0;
let zoom = 1;

let searchCycleIndex = -1;

let calView = new Date();
calView.setDate(1);

/* ===== QUADROS (BOARDS) ===== */

function boardDataKey(id) {
  return `notas-flutuantes:board:${id}`;
}

function loadBoardsList() {
  try {
    const raw = localStorage.getItem(BOARDS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length) return parsed;
    }
  } catch {}
  return null;
}

function saveBoardsList() {
  localStorage.setItem(BOARDS_KEY, JSON.stringify(boards));
}

function readLegacyData() {
  try {
    const raw = localStorage.getItem(LEGACY_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.notes)) return null;

    return {
      notes: parsed.notes,
      links: Array.isArray(parsed.links) ? parsed.links : [],
      nextId: typeof parsed.nextId === 'number' ? parsed.nextId : parsed.notes.length + 1
    };
  } catch {
    return null;
  }
}

function loadLegacyBoardData(id) {
  try {
    const raw = localStorage.getItem(boardDataKey(id));
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        notes: Array.isArray(parsed.notes) ? parsed.notes : [],
        links: Array.isArray(parsed.links) ? parsed.links : [],
        nextId: typeof parsed.nextId === 'number' ? parsed.nextId : 1
      };
    }
  } catch {}
  return null;
}

function recoveryKey(id) {
  return RECOVERY_PREFIX + id;
}

function readRecoveryState(id) {
  try {
    const raw = localStorage.getItem(recoveryKey(id));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.state || !Array.isArray(parsed.state.notes)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeRecoveryState(id, boardState, savedAt = Date.now()) {
  try {
    localStorage.setItem(recoveryKey(id), JSON.stringify({
      savedAt,
      state: NotesStorage.cleanState(boardState)
    }));
  } catch (err) {
    console.warn('Não foi possível gravar o estado de recuperação:', err);
  }
}

async function loadBoardData(id) {
  const recovery = readRecoveryState(id);
  if (recovery) {
    const recovered = NotesStorage.cleanState(recovery.state);
    try {
      await NotesStorage.saveBoard(id, recovered);
      localStorage.removeItem(recoveryKey(id));
    } catch {}
    return recovered;
  }

  const stored = await NotesStorage.loadBoard(id);
  if (stored) return stored;

  let legacy = loadLegacyBoardData(id);
  if (!legacy && id === 'default') legacy = readLegacyData();

  const migrated = await NotesStorage.migrateState(
    id,
    legacy || { notes: [], links: [], nextId: 1 }
  );

  await NotesStorage.saveBoard(id, migrated);
  localStorage.removeItem(boardDataKey(id));
  if (id === 'default') localStorage.removeItem(LEGACY_KEY);
  return migrated;
}

let boards = loadBoardsList();
if (!boards || !boards.length) {
  boards = [{ id: 'default', name: t('defaultBoard', { n: 1 }) }];
  saveBoardsList();
}

let currentBoardId = localStorage.getItem(CURRENT_BOARD_KEY) || boards[0].id;
if (!boards.find(b => b.id === currentBoardId)) currentBoardId = boards[0].id;

let state = { notes: [], links: [], nextId: 1 };
let appReady = false;
let snapshotDirty = false;

const pendingBoardSaves = new Map();
const boardSaveTimers = new Map();
const SAVE_DELAY_MS = 180;
let saveIndicatorTimeout = null;

function scheduleBoardSave(boardId, boardState) {
  const savedAt = Date.now();
  const clean = NotesStorage.cleanState(boardState);
  pendingBoardSaves.set(boardId, { state: clean, savedAt });
  writeRecoveryState(boardId, clean, savedAt);

  const oldTimer = boardSaveTimers.get(boardId);
  if (oldTimer) clearTimeout(oldTimer);
  boardSaveTimers.set(boardId, setTimeout(() => {
    flushBoardSave(boardId);
  }, SAVE_DELAY_MS));
}

async function flushBoardSave(boardId) {
  const timer = boardSaveTimers.get(boardId);
  if (timer) clearTimeout(timer);
  boardSaveTimers.delete(boardId);

  const pending = pendingBoardSaves.get(boardId);
  if (!pending) return true;
  pendingBoardSaves.delete(boardId);

  try {
    await NotesStorage.saveBoard(boardId, pending.state);
    const recovery = readRecoveryState(boardId);
    if (recovery && recovery.savedAt === pending.savedAt) {
      localStorage.removeItem(recoveryKey(boardId));
    }
    if (boardId === currentBoardId) flashSaveIndicator(true);
    return true;
  } catch (err) {
    console.error('Falha ao salvar notas:', err);
    if (boardId === currentBoardId) flashSaveIndicator(false);
    return false;
  }
}

async function flushAllPendingSaves() {
  await Promise.all([...pendingBoardSaves.keys()].map(id => flushBoardSave(id)));
}

function save() {
  if (!appReady) return;
  snapshotDirty = true;
  scheduleBoardSave(currentBoardId, state);
}

function flashSaveIndicator(ok) {
  const el = document.getElementById('saveIndicator');
  if (!el) return;

  el.textContent = ok ? t('saved') : t('saveError');
  el.dataset.status = ok ? 'saved' : 'error';
  el.classList.add('show');

  clearTimeout(saveIndicatorTimeout);
  saveIndicatorTimeout = setTimeout(() => el.classList.remove('show'), 1200);
}

async function switchBoard(id) {
  if (!boards.find(b => b.id === id)) return;
  if (appReady) await flushBoardSave(currentBoardId);

  currentBoardId = id;
  localStorage.setItem(CURRENT_BOARD_KEY, id);
  state = await loadBoardData(id);
  activeNoteId = null;
  linkPick = null;
  linkMode = false;
  linkBtn.classList.remove('active');
  setMoveMode(false);
  selectedNoteIds.clear();

  undoStack = [];
  redoStack = [];
  updateUndoRedoButtons();

  resetView();
  renderBoardSelect();
  render();
  refreshSnapshotList();
}

document.getElementById('boardSelect').addEventListener('change', async e => {
  await switchBoard(e.target.value);
});

document.getElementById('addBoard').addEventListener('click', async () => {
  const name = prompt(t('newBoardPrompt'), t('defaultBoard', { n: boards.length + 1 }));
  if (!name) return;

  const id = 'b' + Date.now();
  boards.push({ id, name: name.trim() || t('defaultBoard', { n: boards.length + 1 }) });
  saveBoardsList();
  await NotesStorage.saveBoard(id, { notes: [], links: [], nextId: 1 });
  snapshotDirty = true;
  await switchBoard(id);
});

document.getElementById('renameBoard').addEventListener('click', () => {
  const board = boards.find(b => b.id === currentBoardId);
  if (!board) return;

  const name = prompt(t('renameBoardPrompt'), board.name);
  if (!name || !name.trim()) return;

  board.name = name.trim();
  saveBoardsList();
  snapshotDirty = true;
  renderBoardSelect();
});

document.getElementById('deleteBoard').addEventListener('click', async () => {
  if (boards.length <= 1) {
    alert(t('cannotDeleteLastBoard'));
    return;
  }

  const board = boards.find(b => b.id === currentBoardId);
  if (!board) return;
  if (!confirm(t('confirmDeleteBoard', { name: board.name }))) return;

  const deletedId = currentBoardId;
  pendingBoardSaves.delete(deletedId);
  const timer = boardSaveTimers.get(deletedId);
  if (timer) clearTimeout(timer);
  boardSaveTimers.delete(deletedId);

  await NotesStorage.deleteBoard(deletedId);
  localStorage.removeItem(boardDataKey(deletedId));
  localStorage.removeItem(recoveryKey(deletedId));
  boards = boards.filter(b => b.id !== deletedId);
  saveBoardsList();
  snapshotDirty = true;

  await switchBoard(boards[0].id);
});

window.addEventListener('pagehide', () => {
  if (appReady && pendingBoardSaves.has(currentBoardId)) {
    writeRecoveryState(currentBoardId, state);
  }
});

/* ===== ZOOM & PAN ===== */

function applyTransform() {
  world.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
  document.getElementById('zoomLevel').textContent = Math.round(zoom * 100) + '%';
}

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

function zoomAt(screenX, screenY, factor) {
  const worldXBefore = (screenX - panX) / zoom;
  const worldYBefore = (screenY - panY) / zoom;

  zoom = clamp(zoom * factor, 0.4, 2.5);

  panX = screenX - worldXBefore * zoom;
  panY = screenY - worldYBefore * zoom;

  applyTransform();
}

function zoomAtCenter(factor) {
  const rect = viewport.getBoundingClientRect();
  zoomAt(rect.width / 2, rect.height / 2, factor);
}

function resetView() {
  panX = 0;
  panY = 0;
  zoom = 1;
  applyTransform();
}

function screenToWorld(clientX, clientY) {
  const rect = viewport.getBoundingClientRect();
  return {
    x: (clientX - rect.left - panX) / zoom,
    y: (clientY - rect.top - panY) / zoom
  };
}

function centerOfView() {
  const rect = viewport.getBoundingClientRect();
  return {
    x: (rect.width / 2 - panX) / zoom,
    y: (rect.height / 2 - panY) / zoom
  };
}

viewport.addEventListener('wheel', e => {
  // Allow natural scroll in textareas
  if (e.target.tagName === 'TEXTAREA') return;
  
  e.preventDefault();

  const rect = viewport.getBoundingClientRect();
  const factor = Math.exp(-e.deltaY * 0.001);

  zoomAt(e.clientX - rect.left, e.clientY - rect.top, factor);
}, { passive: false });

document.getElementById('zoomIn').addEventListener('click', () => zoomAtCenter(1.2));
document.getElementById('zoomOut').addEventListener('click', () => zoomAtCenter(1 / 1.2));
document.getElementById('zoomReset').addEventListener('click', resetView);

/* Arrastar o fundo para navegar (pan) ou selecionar múltiplas notas (Shift) */

// Retângulo de seleção via arraste com Shift
const selectionRect = document.createElement('div');
selectionRect.id = 'selection-rect';
document.body.appendChild(selectionRect);

function updateMultiSelectHighlight() {
  document.querySelectorAll('.note').forEach(el => {
    const id = Number(el.dataset.id);
    el.classList.toggle('multi-selected', selectedNoteIds.has(id));
  });
}

viewport.addEventListener('mousedown', e => {
  if (e.target !== canvas && e.target !== viewport) return;

  // Shift + arraste = seleção por retângulo
  if (e.shiftKey) {
    e.preventDefault();
    const vRect = viewport.getBoundingClientRect();
    const startX = e.clientX;
    const startY = e.clientY;
    let moved = false;

    selectionRect.style.display = 'none';

    function moveSelect(ev) {
      moved = true;
      const x1 = Math.min(startX, ev.clientX);
      const y1 = Math.min(startY, ev.clientY);
      const x2 = Math.max(startX, ev.clientX);
      const y2 = Math.max(startY, ev.clientY);

      selectionRect.style.display = 'block';
      selectionRect.style.left   = x1 + 'px';
      selectionRect.style.top    = y1 + 'px';
      selectionRect.style.width  = (x2 - x1) + 'px';
      selectionRect.style.height = (y2 - y1) + 'px';

      // Converte coordenadas de tela para espaço do mundo
      const wx1 = (x1 - vRect.left - panX) / zoom;
      const wy1 = (y1 - vRect.top  - panY) / zoom;
      const wx2 = (x2 - vRect.left - panX) / zoom;
      const wy2 = (y2 - vRect.top  - panY) / zoom;

      selectedNoteIds.clear();
      state.notes.forEach(note => {
        const el = canvas.querySelector(`.note[data-id="${note.id}"]`);
        if (!el) return;
        const nw = el.offsetWidth, nh = el.offsetHeight;
        const inside = note.x < wx2 && note.x + nw > wx1 &&
                       note.y < wy2 && note.y + nh > wy1;
        if (inside) selectedNoteIds.add(note.id);
      });
      updateMultiSelectHighlight();
    }

    function upSelect() {
      document.removeEventListener('mousemove', moveSelect);
      document.removeEventListener('mouseup', upSelect);
      selectionRect.style.display = 'none';
      if (!moved) {
        selectedNoteIds.clear();
        updateMultiSelectHighlight();
      }
    }

    document.addEventListener('mousemove', moveSelect);
    document.addEventListener('mouseup', upSelect);
    return;
  }

  // Clique no fundo sem shift: limpa seleção múltipla
  if (selectedNoteIds.size > 0) {
    selectedNoteIds.clear();
    updateMultiSelectHighlight();
  }

  const startX = e.clientX;
  const startY = e.clientY;
  const origPanX = panX;
  const origPanY = panY;
  let moved = false;

  viewport.classList.add('panning');

  function move(ev) {
    moved = true;
    panX = origPanX + (ev.clientX - startX);
    panY = origPanY + (ev.clientY - startY);
    applyTransform();
  }

  function preventSelect(ev) {
    ev.preventDefault();
  }

  function up() {
    document.removeEventListener('mousemove', move);
    document.removeEventListener('mouseup', up);
    document.removeEventListener('selectstart', preventSelect);
    viewport.classList.remove('panning');
  }

  document.addEventListener('mousemove', move);
  document.addEventListener('mouseup', up);
  document.addEventListener('selectstart', preventSelect);
});

/* Duplo clique no fundo cria uma nota ali */

viewport.addEventListener('dblclick', e => {
  if (e.target !== canvas && e.target !== viewport) return;

  const p = screenToWorld(e.clientX, e.clientY);
  createNote(p.x - 110, p.y - 20);
});

/* ===== ARRASTAR ARQUIVOS E LINKS PARA O QUADRO ===== */

const MAX_TEXT_INLINE_SIZE = 2 * 1024 * 1024; // 2MB; anexos maiores continuam armazenados, mas não viram texto da nota

function isUrl(str) {
  return /^https?:\/\/\S+$/i.test((str || '').trim());
}

// Detecta todas as URLs http/https num texto e retorna array de {url, start, end}
function extractUrls(text) {
  const results = [];
  const re = /https?:\/\/[^\s<>"')\]]+/gi;
  let m;
  while ((m = re.exec(text)) !== null) {
    results.push({ url: m[0], start: m.index, end: m.index + m[0].length });
  }
  return results;
}

// Detecta links no formato [texto](url) e (url) simples
// Retorna array de {text, url, start, end, isLocal}
function extractMarkdownLinks(text) {
  const results = [];

  // [label](url) — label pode ser vazio
  const reMd = /\[([^\]]*)\]\(([^)]+)\)/g;
  let m;
  while ((m = reMd.exec(text)) !== null) {
    const url = m[2].trim();
    const isLocal = !url.match(/^https?:\/\//i);
    const displayText = m[1].trim() || formatLinkLabel(url);
    results.push({ text: displayText, rawLabel: m[1], url, start: m.index, end: m.index + m[0].length, isLocal });
  }

  // (url) — http(s) ou local: file:// ou caminho Windows
  const reParen = /\(((?:https?:\/\/|file:\/\/|[A-Za-z]:\\)[^)\s]+)\)/g;
  while ((m = reParen.exec(text)) !== null) {
    const url = m[1].trim();
    const isLocal = !url.match(/^https?:\/\//i);
    const already = results.some(r => r.start <= m.index && r.end >= m.index + m[0].length);
    if (!already) {
      results.push({ text: formatLinkLabel(url), rawLabel: '', url, start: m.index, end: m.index + m[0].length, isLocal });
    }
  }

  return results;
}

// Formata um URL/caminho para exibição amigável no badge
function formatLinkLabel(url) {
  if (url.startsWith('file://')) {
    // Remove prefixo file:// e decodifica URI
    let path = decodeURIComponent(url.replace(/^file:\/\//, ''));
    // Normaliza barras
    path = path.replace(/\//g, '\\');
    // Se o caminho for longo, trunca mostrando início e fim
    const parts = path.split('\\').filter(Boolean);
    if (parts.length > 3) {
      return parts[0] + '\\...' + '\\' + parts.slice(-2).join('\\');
    }
    return path;
  }
  if (url.startsWith('http')) {
    try {
      const u = new URL(url);
      return u.hostname + (u.pathname !== '/' ? u.pathname.slice(0, 20) + (u.pathname.length > 20 ? '…' : '') : '');
    } catch { return url.slice(0, 30); }
  }
  return url.length > 30 ? url.slice(0, 28) + '…' : url;
}

// Combina URLs soltas e links Markdown; retorna lista unificada ordenada por posição
function extractAllLinks(text) {
  const mdLinks = extractMarkdownLinks(text);
  // Índices ocupados por links Markdown (para não detectar URLs internas como soltas)
  const occupied = new Set();
  mdLinks.forEach(l => { for (let i = l.start; i < l.end; i++) occupied.add(i); });

  const bareUrls = extractUrls(text).filter(u => !occupied.has(u.start));

  const all = [
    ...mdLinks,
    ...bareUrls.map(u => ({ text: u.url, url: u.url, start: u.start, end: u.end, isLocal: false }))
  ];
  all.sort((a, b) => a.start - b.start);
  return all;
}

/* ===== VISUALIZADOR DE ARQUIVO ===== */

const fileViewerOverlay = document.getElementById('file-viewer-overlay');
const fileViewerBody   = document.getElementById('file-viewer-body');
const fileViewerTitle  = document.getElementById('file-viewer-title');

document.getElementById('file-viewer-close').addEventListener('click', closeFileViewer);

fileViewerOverlay.addEventListener('mousedown', e => {
  if (e.target === fileViewerOverlay) closeFileViewer();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !fileViewerOverlay.classList.contains('hidden')) {
    closeFileViewer();
    e.stopPropagation();
  }
}, true);

function closeFileViewer() {
  fileViewerOverlay.classList.add('hidden');
  // Limpa o corpo para libertar memória (revogar blob URLs, parar vídeos, etc.)
  fileViewerBody.innerHTML = '';
}

function getFileIcon(mime, name) {
  if (!mime) mime = '';
  if (!name) name = '';
  if (mime.startsWith('image/')) return '<span class="ui-icon icon-image" aria-hidden="true"></span>';
  if (mime === 'application/pdf') return '<span class="ui-icon icon-file" aria-hidden="true"></span>';
  if (mime.startsWith('text/') || /\.(txt|md|log|csv|json)$/i.test(name)) return '<span class="ui-icon icon-file" aria-hidden="true"></span>';
  if (/\.(zip|rar|7z|tar|gz)$/i.test(name)) return '<span class="ui-icon icon-archive" aria-hidden="true"></span>';
  return '<span class="ui-icon icon-attachment" aria-hidden="true"></span>';
}

const attachmentUrlCache = new Map();

async function getAttachmentObjectUrl(attachmentId) {
  if (!attachmentId) return null;
  if (attachmentUrlCache.has(attachmentId)) return attachmentUrlCache.get(attachmentId);
  const attachment = await NotesStorage.getAttachment(attachmentId);
  if (!attachment || !attachment.blob) return null;
  const url = URL.createObjectURL(attachment.blob);
  attachmentUrlCache.set(attachmentId, url);
  return url;
}

function clearAttachmentObjectUrl(attachmentId) {
  const url = attachmentUrlCache.get(attachmentId);
  if (url) URL.revokeObjectURL(url);
  attachmentUrlCache.delete(attachmentId);
}

async function openFileViewer(noteRef) {
  const fileName = noteRef && noteRef.fileName ? noteRef.fileName : t('file');
  const mimeType = noteRef && noteRef.fileMime ? noteRef.fileMime : '';
  fileViewerTitle.textContent = fileName;
  fileViewerBody.innerHTML = '';
  fileViewerOverlay.classList.remove('hidden');

  if (!noteRef || !noteRef.attachmentId) {
    fileViewerBody.innerHTML = `<div class="viewer-placeholder"><span class="ph-icon"><span class="ui-icon icon-attachment" aria-hidden="true"></span></span><p>${t('previewUnavailable')}</p></div>`;
    return;
  }

  const attachment = await NotesStorage.getAttachment(noteRef.attachmentId);
  if (!attachment || !attachment.blob) {
    fileViewerBody.innerHTML = `<div class="viewer-placeholder"><span class="ph-icon"><span class="ui-icon icon-attachment" aria-hidden="true"></span></span><p>${t('previewUnavailable')}</p></div>`;
    return;
  }

  const blob = attachment.blob;
  const effectiveMime = mimeType || attachment.mime || blob.type || 'application/octet-stream';

  if (effectiveMime.startsWith('image/')) {
    const img = document.createElement('img');
    img.src = await getAttachmentObjectUrl(noteRef.attachmentId);
    img.alt = fileName;
    fileViewerBody.appendChild(img);

  } else if (effectiveMime === 'application/pdf') {
    const iframe = document.createElement('iframe');
    iframe.src = await getAttachmentObjectUrl(noteRef.attachmentId);
    iframe.title = fileName;
    fileViewerBody.appendChild(iframe);

  } else if (effectiveMime.startsWith('text/') || effectiveMime === 'application/json' || /\.(txt|md|log|csv|json)$/i.test(fileName)) {
    const text = await blob.text();

    const bar = document.createElement('div');
    bar.className = 'viewer-edit-bar';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'viewer-save-btn';
    saveBtn.textContent = t('saveChanges');
    saveBtn.disabled = true;

    const discardBtn = document.createElement('button');
    discardBtn.className = 'viewer-discard-btn';
    discardBtn.textContent = t('discard');
    discardBtn.disabled = true;

    const hint = document.createElement('span');
    hint.className = 'viewer-edit-hint';
    hint.textContent = t('editHint');

    bar.append(saveBtn, discardBtn, hint);

    const ta = document.createElement('textarea');
    ta.className = 'viewer-textarea';
    ta.value = text;
    ta.spellcheck = false;

    let originalText = text;

    ta.addEventListener('input', () => {
      const changed = ta.value !== originalText;
      saveBtn.disabled = !changed;
      discardBtn.disabled = !changed;
    });

    saveBtn.addEventListener('click', async () => {
      const newText = ta.value;
      const newBlob = new Blob([newText], { type: effectiveMime || 'text/plain' });

      if (noteRef) {
        pushUndoSnapshot();
        const oldAttachmentId = noteRef.attachmentId;
        const newAttachmentId = await NotesStorage.putAttachment(currentBoardId, newBlob, {
          name: fileName,
          mime: effectiveMime
        });
        noteRef.attachmentId = newAttachmentId;
        clearAttachmentObjectUrl(oldAttachmentId);
        noteRef.text = newText;

        const noteTa = canvas.querySelector(`.note[data-id="${noteRef.id}"] textarea`);
        if (noteTa) noteTa.value = newText;
        save();
      }

      originalText = newText;
      saveBtn.disabled = true;
      discardBtn.disabled = true;
      hint.textContent = t('savedShort');
      setTimeout(() => { hint.textContent = t('editHint'); }, 2000);
    });

    discardBtn.addEventListener('click', () => {
      ta.value = originalText;
      saveBtn.disabled = true;
      discardBtn.disabled = true;
    });

    fileViewerBody.appendChild(ta);
    fileViewerBody.appendChild(bar);

  } else {
    const a = document.createElement('a');
    a.href = await getAttachmentObjectUrl(noteRef.attachmentId);
    a.download = fileName || t('fileLower');
    a.textContent = t('downloadFile');

    fileViewerBody.innerHTML = `<div class="viewer-placeholder">
      <span class="ph-icon">${getFileIcon(effectiveMime, fileName)}</span>
      <p>${t('previewUnavailableType')}</p>
    </div>`;
    fileViewerBody.querySelector('.viewer-placeholder').appendChild(a);
  }
}

// Abre uma URL externa num iframe dentro do visualizador
function openUrlViewer(url) {
  fileViewerTitle.textContent = url;
  fileViewerBody.innerHTML = '';
  fileViewerOverlay.classList.remove('hidden');

  // Tenta carregar num iframe; se o site bloquear, avisa e oferece abrir numa aba
  const iframe = document.createElement('iframe');
  iframe.src = url;
  iframe.title = url;
  iframe.sandbox = 'allow-scripts allow-same-origin allow-forms allow-popups';

  iframe.addEventListener('error', () => {
    showUrlFallback(url);
  });

  fileViewerBody.appendChild(iframe);

  // Fallback em 5s (sites bloqueados via X-Frame-Options não disparam "error")
  const fallbackTimer = setTimeout(() => {
    // Se o iframe ainda não tem conteúdo acessível, não fazemos nada —
    // o usuário já vê o iframe tentando carregar.
  }, 5000);

  iframe.addEventListener('load', () => clearTimeout(fallbackTimer));
}

function showUrlFallback(url) {
  fileViewerBody.innerHTML = `<div class="viewer-placeholder">
    <span class="ph-icon"><span class="ui-icon icon-link" aria-hidden="true"></span></span>
    <p>${t('siteCannotEmbed')}</p>
    <a id="open-external-link">${t('openNewTab')}</a>
  </div>`;
  document.getElementById('open-external-link').addEventListener('click', () => {
    window.open(url, '_blank', 'noopener');
  });
}

let dragCounter = 0;
let internalDrag = false;

// Evita criar nota nova quando o usuário só está arrastando texto
// selecionado de dentro de uma nota (ex.: reordenando texto no textarea).
document.addEventListener('dragstart', () => { internalDrag = true; });
document.addEventListener('dragend', () => { internalDrag = false; });

viewport.addEventListener('dragenter', e => {
  if (internalDrag) return;
  e.preventDefault();
  dragCounter++;
  viewport.classList.add('drag-active');
});

viewport.addEventListener('dragleave', () => {
  dragCounter = Math.max(0, dragCounter - 1);
  if (dragCounter === 0) viewport.classList.remove('drag-active');
});

viewport.addEventListener('dragover', e => {
  if (internalDrag) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
});

viewport.addEventListener('drop', async e => {
  if (internalDrag) return;

  e.preventDefault();
  dragCounter = 0;
  viewport.classList.remove('drag-active');

  const p = screenToWorld(e.clientX, e.clientY);
  const files = Array.from(e.dataTransfer.files || []);

  if (files.length) {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const x = p.x - 110 + i * 24;
      const y = p.y - 70 + i * 24;

      const entry = e.dataTransfer.items && e.dataTransfer.items[i]
        ? e.dataTransfer.items[i].webkitGetAsEntry && e.dataTransfer.items[i].webkitGetAsEntry()
        : null;

      if (entry && entry.isDirectory) {
        const dirPath = file.path || file.name;
        const dirUrl = file.path
          ? (dirPath.startsWith('file://') ? dirPath : 'file://' + dirPath.replace(/\\/g, '/'))
          : null;
        createNote(x, y, {
          text: dirUrl
            ? `[${file.name}](${dirUrl})`
            : `${file.name}\n(${t('dragExplorerToOpen')})`,
          fileName: file.name,
          fileMime: 'inode/directory'
        });
        continue;
      }

      try {
        const attachmentId = await NotesStorage.putAttachment(currentBoardId, file, {
          name: file.name,
          mime: file.type || 'application/octet-stream'
        });

        if (file.type.startsWith('text/') || /\.(txt|md|csv|json|log)$/i.test(file.name)) {
          const text = file.size <= MAX_TEXT_INLINE_SIZE
            ? await file.text()
            : t('textFileTooLarge', { name: file.name });
          createNote(x, y, {
            text,
            attachmentId,
            fileName: file.name,
            fileMime: file.type || 'text/plain'
          });
        } else {
          createNote(x, y, {
            text: file.name,
            attachmentId,
            fileName: file.name,
            fileMime: file.type || 'application/octet-stream'
          });
        }
      } catch (err) {
        console.error('Falha ao armazenar anexo:', err);
        createNote(x, y, { text: file.name });
        flashSaveIndicator(false);
      }
    }
    return;
  }

  const dropped = (e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain') || '').trim();
  if (dropped) {
    const isDir = dropped.startsWith('file://') && !dropped.match(/\.[a-zA-Z0-9]{1,6}$/);
    if (isDir) {
      const dirName = dropped.split('/').filter(Boolean).pop() || t('folder');
      createNote(p.x - 110, p.y - 20, {
        text: `[${decodeURIComponent(dirName)}](${dropped})`,
        fileMime: 'inode/directory'
      });
    } else {
      createNote(p.x - 110, p.y - 20, { text: dropped });
    }
  }
});

function focusOnNote(note) {
  const rect = viewport.getBoundingClientRect();
  const el = canvas.querySelector(`.note[data-id="${note.id}"]`);

  const w = el ? el.offsetWidth : (note.width || 220);
  const h = el ? el.offsetHeight : (note.height || 160);

  const cx = note.x + w / 2;
  const cy = note.y + h / 2;

  panX = rect.width / 2 - cx * zoom;
  panY = rect.height / 2 - cy * zoom;

  applyTransform();
}

/* ===== RENDER ===== */

function render() {
  canvas.innerHTML = '';

  state.notes.forEach(renderNote);

  drawLinks();
  updateActiveHighlight();
  updateStats();
}

function updateStats() {
  const el = document.getElementById('stats');
  if (!el) return;

  el.textContent = t('stats', { notes: state.notes.length, links: state.links.length });
}

function setActiveNote(id) {
  activeNoteId = id;
  updateActiveHighlight();
}

function updateActiveHighlight() {
  document.querySelectorAll('.note').forEach(n => {
    n.classList.toggle('active', Number(n.dataset.id) === activeNoteId);
  });
}

function bringToFront(el) {
  topZ += 1;
  el.style.zIndex = topZ;
}

/* ===== NOTAS ===== */

// Cores de accent do botão Link — 1 entrada por NOTE_COLORS
const LINK_BTN_COLORS = [
  { light: { bg: '#ffe034', border: '#c9a020', color: '#3a2f00' }, dark: { bg: '#504818', border: '#988030', color: '#ffe090' } }, // Amarelo
  { light: { bg: '#ffbb70', border: '#c07020', color: '#3a1800' }, dark: { bg: '#503018', border: '#a06020', color: '#ffd890' } }, // Laranja
  { light: { bg: '#ff9999', border: '#c03838', color: '#500000' }, dark: { bg: '#501010', border: '#903030', color: '#ffb8b8' } }, // Vermelho
  { light: { bg: '#ffb0d0', border: '#c07090', color: '#50002a' }, dark: { bg: '#501830', border: '#985070', color: '#ffc8e0' } }, // Rosa claro
  { light: { bg: '#ff90b8', border: '#c03868', color: '#500020' }, dark: { bg: '#581028', border: '#a02858', color: '#ffb0d0' } }, // Rosa escuro
  { light: { bg: '#cc99ff', border: '#8850c8', color: '#300058' }, dark: { bg: '#382058', border: '#7840a8', color: '#e8c8ff' } }, // Roxo
  { light: { bg: '#88c8ff', border: '#3880c8', color: '#002040' }, dark: { bg: '#182840', border: '#3060a0', color: '#b8d8ff' } }, // Azul
  { light: { bg: '#70d8e8', border: '#189ab0', color: '#002830' }, dark: { bg: '#103038', border: '#187898', color: '#a8e4ef' } }, // Ciano
  { light: { bg: '#98d870', border: '#40a020', color: '#0a2800' }, dark: { bg: '#183018', border: '#307818', color: '#b8e8a0' } }, // Verde claro
  { light: { bg: '#70c848', border: '#288018', color: '#081800' }, dark: { bg: '#102010', border: '#205818', color: '#98d878' } }, // Verde escuro
  { light: { bg: '#e0b880', border: '#a06020', color: '#381800' }, dark: { bg: '#382010', border: '#784020', color: '#e8c898' } }, // Marrom
  { light: { bg: '#c8c8d8', border: '#7070a0', color: '#202040' }, dark: { bg: '#282840', border: '#484870', color: '#d0d0e8' } }, // Cinza
];

function applyNoteColor(el, handle, colorIndex) {
  const isDark = document.body.classList.contains('dark');
  const entry = NOTE_COLORS[colorIndex] || NOTE_COLORS[0];
  const c = isDark ? entry.dark : entry.light;

  el.style.background = c.bg;
  el.style.borderColor = c.border;
  handle.style.background = c.handle;
  handle.style.borderBottomColor = c.border;

  const ta = el.querySelector('textarea');
  if (ta) ta.style.color = isDark ? '#eee' : '#3a2f00';

  el.querySelectorAll('.handle button:not(.del):not(.make-link-btn)').forEach(b => {
    b.style.color = isDark ? '#ddd' : '#5a4a00';
    b.style.background = '';
    b.style.border = '';
  });

  const delBtn = el.querySelector('.del');
  if (delBtn) delBtn.style.color = isDark ? '#ff9a9a' : '#844';

  // Botão Link: cor de accent baseada na cor da nota
  const mlb = el.querySelector('.make-link-btn');
  if (mlb) {
    const lc = (LINK_BTN_COLORS[colorIndex] || LINK_BTN_COLORS[0]);
    const lcc = isDark ? lc.dark : lc.light;
    mlb.style.background = lcc.bg;
    mlb.style.borderColor = lcc.border;
    mlb.style.border = `1px solid ${lcc.border}`;
    mlb.style.color = lcc.color;
    mlb.style.borderRadius = '4px';
    mlb.style.padding = '1px 5px';
    mlb.style.fontWeight = '600';
  }
}

function renderNote(note) {
  const el = document.createElement('div');

  el.className = 'note';
  el.style.left = note.x + 'px';
  el.style.top = note.y + 'px';

  if (note.width) el.style.width = note.width + 'px';
  if (note.height) el.style.height = note.height + 'px';

  el.dataset.id = note.id;
  el.classList.toggle('pinned', !!note.pinned);

  // Barra de preview de arquivo (anexo armazenado no IndexedDB)
  const filePreviewHtml = note.attachmentId
    ? `<div class="note-file-preview" data-action="open-file">
         <span class="file-icon">${getFileIcon(note.fileMime, note.fileName)}</span>
         <span class="file-name" title="${escapeHtml(note.fileName || t('fileLower'))}">${escapeHtml(note.fileName || t('fileLower'))}</span>
         <span class="file-open-btn">${t('view')}</span>
       </div>`
    : '';

  el.innerHTML = `
    <div class="handle">
      <button class="pin-btn" title="${t(note.pinned ? 'unpinNote' : 'pinNote')}"></button>
      <button class="color-btn" title="${t('noteColor')}"></button>
      <button class="cal-btn" title="${t('insertDate')}"></button>
      <button class="make-link-btn" title="${t('makeLink')}">${t('linkButton')}</button>
      <button class="link-open-btn" title="${t('openLink')}" style="display:${isUrl(note.text) ? 'inline-flex' : 'none'}"></button>
      <button class="del" title="${t('deleteNote')}"></button>
    </div>

    ${filePreviewHtml}
    ${note.attachmentId && (note.fileMime || '').startsWith('image/') ? `<img class="note-image" data-attachment-id="${note.attachmentId}" alt="">` : ''}
    <textarea placeholder="${t('notePlaceholder')}">${escapeHtml(note.text)}</textarea>
    <div class="note-link-overlay" aria-hidden="true"></div>
  `;

  canvas.appendChild(el);

  const imagePreview = el.querySelector('.note-image[data-attachment-id]');
  if (imagePreview) {
    getAttachmentObjectUrl(note.attachmentId).then(url => {
      if (url && imagePreview.isConnected) imagePreview.src = url;
    }).catch(err => console.warn('Falha ao carregar prévia do anexo:', err));
  }

  const handle = el.querySelector('.handle');
  const ta = el.querySelector('textarea');
  const del = el.querySelector('.del');
  const calBtn = el.querySelector('.cal-btn');
  const pinBtn = el.querySelector('.pin-btn');
  const colorBtn = el.querySelector('.color-btn');
  const linkOpenBtn = el.querySelector('.link-open-btn');
  const makeLinkBtn = el.querySelector('.make-link-btn');
  const linkOverlay = el.querySelector('.note-link-overlay');

  linkOpenBtn.addEventListener('click', e => {
    e.stopPropagation();
    if (e.shiftKey) {
      window.open(ta.value.trim(), '_blank', 'noopener');
    } else {
      openUrlViewer(ta.value.trim());
    }
  });

  // Botão "Link" — abre popup para transformar texto selecionado em link Markdown
  makeLinkBtn.addEventListener('click', e => {
    e.stopPropagation();
    openLocalLinkPopup(ta, el);
  });

  // Botão "Ver arquivo" na barra de preview
  const filePreviewBar = el.querySelector('.note-file-preview');
  if (filePreviewBar) {
    filePreviewBar.addEventListener('click', e => {
      e.stopPropagation();
      openFileViewer(note);
    });
  }

  // ---- OVERLAY DE LINKS ----
  // Abordagem: não espelha o texto (causava sobreposição e bloqueava seleção).
  // Em vez disso mostra badges de link flutuantes no canto inferior da nota,
  // de forma que o textarea fica totalmente livre para seleção e cópia.
  function rebuildLinkOverlay() {
    if (!linkOverlay) return;
    const text = ta.value;
    const links = extractAllLinks(text);

    linkOverlay.innerHTML = '';

    if (!links.length) {
      linkOverlay.style.display = 'none';
      return;
    }

    linkOverlay.style.display = '';

    links.forEach(link => {
      const badge = document.createElement('span');
      badge.className = 'link-badge' + (link.isLocal ? ' local-link' : '');
      badge.title = link.url;
      badge.dataset.url = link.url;
      badge.dataset.local = link.isLocal;

      // Ícone + label truncado
      const label = link.text.length > 28 ? link.text.slice(0, 26) + '…' : link.text;

      const mainSpan = document.createElement('span');
      mainSpan.className = 'link-badge-label';
      mainSpan.textContent = label;

      mainSpan.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        const url = badge.dataset.url;
        const isLocal = badge.dataset.local === 'true';

        if (isLocal) {
          const href = url.startsWith('file://') || url.startsWith('http') ? url : 'file://' + url;
          window.open(href, '_blank', 'noopener,width=900,height=700');
        } else if (e.shiftKey) {
          window.open(url, '_blank', 'noopener,width=900,height=700');
        } else {
          openUrlViewer(url);
        }
      });

      // Botão × para remover o link da nota
      const removeBtn = document.createElement('button');
      removeBtn.className = 'link-badge-remove';
      removeBtn.title = t('removeLink');
      removeBtn.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();

        // Remove o trecho markdown [label](url) do texto da nota
        const currentText = ta.value;
        // Recalcula posição do link no texto atual
        const allLinks = extractAllLinks(currentText);
        const target = allLinks.find(l => l.url === link.url && l.text === link.text);

        if (target) {
          // Mesmo problema/solução de applyLocalLink: seleciona o trecho e
          // apaga via execCommand para manter o desfazer nativo do textarea
          // (atribuir ta.value direto apagaria esse histórico).
          ta.focus();
          ta.setSelectionRange(target.start, target.end);
          const ok = document.execCommand('delete', false, null);

          if (ok) {
            // Colapsa 3+ quebras de linha deixadas pela remoção, se houver
            const run = /\n{3,}/.exec(ta.value);
            if (run) {
              ta.setSelectionRange(run.index, run.index + run[0].length);
              document.execCommand('insertText', false, '\n\n');
            }
          } else {
            const before = currentText.slice(0, target.start);
            const after  = currentText.slice(target.end);
            ta.value = (before + after).replace(/\n{3,}/g, '\n\n');
            note.text = ta.value;
            ta.dispatchEvent(new Event('input', { bubbles: true }));
          }
        } else {
          // Fallback: remove qualquer ocorrência do padrão com essa URL
          const escaped = link.url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          ta.value = currentText.replace(new RegExp(`\\[[^\\]]*\\]\\(${escaped}\\)`, 'g'), '').replace(/\n{3,}/g, '\n\n');
          note.text = ta.value;
          ta.dispatchEvent(new Event('input', { bubbles: true }));
        }
      });

      badge.appendChild(mainSpan);
      badge.appendChild(removeBtn);
      linkOverlay.appendChild(badge);
    });
  }

  rebuildLinkOverlay();

  applyNoteColor(el, handle, note.colorIndex || 0);

  /* ===== FOCO ===== */

  let editSnapshotTaken = false;

  ta.addEventListener('focus', () => {
    setActiveNote(note.id);
    bringToFront(el);
    editSnapshotTaken = false;
  });

  ta.addEventListener('input', () => {
    if (!editSnapshotTaken) {
      pushUndoSnapshot();
      editSnapshotTaken = true;
    }

    note.text = ta.value;
    save();

    linkOpenBtn.style.display = isUrl(ta.value) ? 'inline-flex' : 'none';
    rebuildLinkOverlay();
  });

  ta.addEventListener('blur', () => {
    editSnapshotTaken = false;
  });

  /* ===== APAGAR ===== */

  del.addEventListener('click', e => {
    e.stopPropagation();

    pushUndoSnapshot();

    state.notes = state.notes.filter(n => n.id !== note.id);
    state.links = state.links.filter(l => l.a !== note.id && l.b !== note.id);

    if (activeNoteId === note.id) activeNoteId = null;

    save();
    render();
  });

  /* ===== FIXAR ===== */

  pinBtn.addEventListener('click', e => {
    e.stopPropagation();

    pushUndoSnapshot();

    note.pinned = !note.pinned;

    el.classList.toggle('pinned', note.pinned);
    pinBtn.title = t(note.pinned ? 'unpinNote' : 'pinNote');

    save();
  });

  /* ===== COR ===== */

  colorBtn.addEventListener('click', e => {
    e.stopPropagation();

    const existing = el.querySelector('.color-popup');
    if (existing) {
      existing.remove();
      return;
    }

    closeAllColorPopups();

    const popup = document.createElement('div');
    popup.className = 'color-popup';

    const isDarkNow = document.body.classList.contains('dark');

    NOTE_COLORS.forEach((c, i) => {
      const sw = document.createElement('button');
      sw.className = 'color-swatch' + (i === (note.colorIndex || 0) ? ' active-swatch' : '');
      sw.style.background = isDarkNow ? c.dark.swatch : c.light.swatch;
      const colorNames = t('colors');
      sw.title = colorNames[i] || t('colorNumber', { n: i + 1 });

      sw.addEventListener('click', ev => {
        ev.stopPropagation();
        pushUndoSnapshot();
        note.colorIndex = i;
        applyNoteColor(el, handle, i);
        popup.remove();
        save();
      });

      popup.appendChild(sw);
    });

    handle.appendChild(popup);
  });

  /* ===== CALENDÁRIO ===== */

  calBtn.addEventListener('click', e => {
    e.stopPropagation();

    setActiveNote(note.id);
    ta.focus();
    openCalendar();
  });

  /* ===== REDIMENSIONAR ===== */

  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      note.width = Math.round(el.offsetWidth);
      note.height = Math.round(el.offsetHeight);
      drawLinks();
    });

    ro.observe(el);
  }

  // A alça nativa de redimensionar fica no canto inferior direito, numa
  // área que não pertence à textarea nem à handle (mousedown cai direto
  // no elemento da nota). O ResizeObserver acima é assíncrono e atrasa a
  // ligação em relação ao arraste — por isso ela "não tocava" na nota ao
  // crescer. Isto força o recálculo a cada movimento, igual ao arraste.
  el.addEventListener('mousedown', e => {
    if (e.target !== el) return;

    pushUndoSnapshot();
    bringToFront(el);
    setActiveNote(note.id);

    function move() {
      drawLinks();
    }

    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);

      note.width = Math.round(el.offsetWidth);
      note.height = Math.round(el.offsetHeight);
      save();
    }

    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });

  /* ===== ARRASTAR ===== */

  handle.addEventListener('mousedown', e => {
    if (e.target.tagName === 'BUTTON') return;
    if (note.pinned) return;

    // Se a nota clicada faz parte da seleção múltipla, arrasta todas juntas
    const isMultiDrag = selectedNoteIds.size > 1 && selectedNoteIds.has(note.id);

    pushUndoSnapshot();
    bringToFront(el);
    setActiveNote(note.id);

    const startX = e.clientX;
    const startY = e.clientY;

    // Salva posições originais de todas as notas envolvidas
    const dragNotes = isMultiDrag
      ? state.notes.filter(n => selectedNoteIds.has(n.id) && !n.pinned)
      : [note];

    const origPositions = dragNotes.map(n => ({ note: n, x: n.x, y: n.y }));

    function move(ev) {
      const dx = (ev.clientX - startX) / zoom;
      const dy = (ev.clientY - startY) / zoom;

      origPositions.forEach(({ note: n, x, y }) => {
        n.x = x + dx;
        n.y = y + dy;
        const el2 = canvas.querySelector(`.note[data-id="${n.id}"]`);
        if (el2) {
          el2.style.left = n.x + 'px';
          el2.style.top  = n.y + 'px';
        }
      });

      drawLinks();
    }

    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      save();
    }

    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });

  /* ===== CLIQUE NA NOTA (seleção múltipla + ligar) ===== */

  el.addEventListener('click', e => {
    // Shift+clique na nota: adiciona/remove da seleção múltipla
    if (e.shiftKey && !linkMode) {
      e.stopPropagation();
      if (selectedNoteIds.has(note.id)) {
        selectedNoteIds.delete(note.id);
      } else {
        selectedNoteIds.add(note.id);
      }
      updateMultiSelectHighlight();
      return;
    }

    if (!linkMode) return;

    if (e.target.tagName === 'TEXTAREA') return;
    if (e.target.tagName === 'BUTTON') return;

    if (linkPick == null) {
      linkPick = note.id;
      el.classList.add('selected');
    } else if (linkPick === note.id) {
      linkPick = null;
      el.classList.remove('selected');
    } else {
      const exists = state.links.some(
        l => (l.a === linkPick && l.b === note.id) || (l.a === note.id && l.b === linkPick)
      );

      pushUndoSnapshot();

      if (!exists) {
        state.links.push({ a: linkPick, b: note.id, label: '' });
      } else {
        state.links = state.links.filter(
          l => !((l.a === linkPick && l.b === note.id) || (l.a === note.id && l.b === linkPick))
        );
      }

      document.querySelectorAll('.note.selected').forEach(n => n.classList.remove('selected'));
      linkPick = null;

      save();
      drawLinks();
      updateStats();
    }
  });
}

function closeAllColorPopups() {
  document.querySelectorAll('.color-popup').forEach(p => p.remove());
}

/* ===== LINHAS ===== */

function noteRect(note) {
  const el = canvas.querySelector(`.note[data-id="${note.id}"]`);

  if (el) {
    return { x: note.x, y: note.y, w: el.offsetWidth, h: el.offsetHeight };
  }

  return { x: note.x, y: note.y, w: note.width || 220, h: note.height || 160 };
}

// Ponto onde a linha (do centro do retângulo até "target") cruza a borda do retângulo.
// Antes a ligação ia de centro a centro e ficava escondida atrás da nota; em notas
// de tamanhos bem diferentes isso podia parecer uma linha cortada antes de chegar.
function rectEdgePoint(rect, target) {
  const cx = rect.x + rect.w / 2;
  const cy = rect.y + rect.h / 2;

  const dx = target.x - cx;
  const dy = target.y - cy;

  if (!dx && !dy) return { x: cx, y: cy };

  const scaleX = dx ? (rect.w / 2) / Math.abs(dx) : Infinity;
  const scaleY = dy ? (rect.h / 2) / Math.abs(dy) : Infinity;
  const scale = Math.min(scaleX, scaleY);

  return { x: cx + dx * scale, y: cy + dy * scale };
}

function promptLinkLabel(link) {
  const value = prompt(t('linkLabelPrompt'), link.label || '');
  if (value === null) return;

  const trimmed = value.trim();
  if (trimmed === (link.label || '')) return;

  pushUndoSnapshot();

  link.label = trimmed;
  save();
  drawLinks();
}

function drawLinks() {
  svg.innerHTML = '';

  state.links.forEach(link => {
    const a = state.notes.find(n => n.id === link.a);
    const b = state.notes.find(n => n.id === link.b);

    if (!a || !b) return;

    const rectA = noteRect(a);
    const rectB = noteRect(b);
    const centerA = { x: rectA.x + rectA.w / 2, y: rectA.y + rectA.h / 2 };
    const centerB = { x: rectB.x + rectB.w / 2, y: rectB.y + rectB.h / 2 };

    const pA = rectEdgePoint(rectA, centerB);
    const pB = rectEdgePoint(rectB, centerA);

    const line = document.createElementNS(SVG_NS, 'line');

    line.setAttribute('x1', pA.x);
    line.setAttribute('y1', pA.y);
    line.setAttribute('x2', pB.x);
    line.setAttribute('y2', pB.y);
    line.style.pointerEvents = 'stroke';
    line.style.cursor = 'pointer';

    line.addEventListener('click', e => {
      e.stopPropagation();
      promptLinkLabel(link);
    });

    svg.appendChild(line);

    if (link.label) {
      const mx = (pA.x + pB.x) / 2;
      const my = (pA.y + pB.y) / 2;

      const text = document.createElementNS(SVG_NS, 'text');
      text.setAttribute('x', mx);
      text.setAttribute('y', my);
      text.setAttribute('class', 'link-label');
      text.style.pointerEvents = 'all';
      text.style.cursor = 'pointer';
      text.textContent = link.label;

      text.addEventListener('click', e => {
        e.stopPropagation();
        promptLinkLabel(link);
      });

      svg.appendChild(text);
    }
  });
}

/* ===== HTML SAFE ===== */

function escapeHtml(s) {
  return (s || '').replace(
    /[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
}

/* ===== NOVA NOTA ===== */

function createNote(x, y, extra) {
  pushUndoSnapshot();

  let pos;

  if (x != null && y != null) {
    pos = { x, y };
  } else {
    const c = centerOfView();
    pos = { x: c.x - 110 + (Math.random() * 60 - 30), y: c.y - 70 + (Math.random() * 60 - 30) };
  }

  const note = Object.assign({
    id: state.nextId++,
    x: pos.x,
    y: pos.y,
    text: '',
    colorIndex: 0,
    pinned: false
  }, extra);

  state.notes.push(note);
  setActiveNote(note.id);

  save();
  render();

  return note;
}

document.getElementById('addNote').addEventListener('click', () => createNote());

/* ===== COPIAR / COLAR ===== */

let clipboardNote = null;

function copyActiveNote() {
  // Se há seleção múltipla, copia todas as notas selecionadas
  const ids = selectedNoteIds.size > 0
    ? [...selectedNoteIds]
    : (activeNoteId != null ? [activeNoteId] : []);

  if (!ids.length) return;

  const notes = ids.map(id => state.notes.find(n => n.id === id)).filter(Boolean);
  if (!notes.length) return;

  // Ligações entre as notas copiadas (internas ao grupo)
  const internalLinks = state.links.filter(l =>
    ids.includes(l.a) && ids.includes(l.b)
  );

  clipboardNote = {
    notes: notes.map(n => ({ ...n })),
    links: internalLinks.map(l => ({ ...l })),
    x: notes[0].x,
    y: notes[0].y
  };
}

function pasteNote() {
  if (!clipboardNote) return;

  pushUndoSnapshot();

  const offset = 24;
  const idMap = {};

  clipboardNote.notes.forEach(src => {
    const newId = state.nextId++;
    idMap[src.id] = newId;

    const newNote = {
      ...src,
      id: newId,
      x: src.x + offset,
      y: src.y + offset,
      pinned: false
    };

    state.notes.push(newNote);
    setActiveNote(newId);
  });

  // Recria as ligações internas com os novos IDs
  clipboardNote.links.forEach(l => {
    const newA = idMap[l.a];
    const newB = idMap[l.b];
    if (newA && newB) {
      state.links.push({ a: newA, b: newB, label: l.label || '' });
    }
  });

  // Desloca a origem para o próximo Ctrl+V empilhar
  clipboardNote.notes = clipboardNote.notes.map(n => ({ ...n, x: n.x + offset, y: n.y + offset }));

  save();
  render();
}

/* ===== MODO LIGAÇÃO ===== */

const linkBtn = document.getElementById('linkMode');

linkBtn.addEventListener('click', () => {
  linkMode = !linkMode;
  linkPick = null;

  linkBtn.classList.toggle('active', linkMode);

  document.querySelectorAll('.note.selected').forEach(n => n.classList.remove('selected'));
});

/* ===== LIMPAR ===== */

document.getElementById('clearAll').addEventListener('click', () => {
  if (!confirm(t('confirmClearBoard'))) return;

  pushUndoSnapshot();

  state = { notes: [], links: [], nextId: 1 };
  activeNoteId = null;

  save();
  render();
});

window.addEventListener('resize', drawLinks);

/* ===== BUSCA ===== */

const searchInput = document.getElementById('searchInput');

function getSearchMatches() {
  const q = searchInput.value.trim().toLowerCase();
  if (!q) return [];

  return state.notes.filter(n => (n.text || '').toLowerCase().includes(q));
}

searchInput.addEventListener('input', () => {
  searchCycleIndex = -1;

  const q = searchInput.value.trim().toLowerCase();

  document.querySelectorAll('.note').forEach(el => {
    const id = Number(el.dataset.id);
    const note = state.notes.find(n => n.id === id);
    const match = q && note && (note.text || '').toLowerCase().includes(q);
    el.classList.toggle('search-match', !!match);
  });
});

searchInput.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;

  const matches = getSearchMatches();
  if (!matches.length) return;

  searchCycleIndex = (searchCycleIndex + 1) % matches.length;

  const note = matches[searchCycleIndex];
  setActiveNote(note.id);
  focusOnNote(note);
});

/* ===== EXPORTAR / IMPORTAR ===== */

function downloadJson(payload, fileName) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

document.getElementById('exportNotes').addEventListener('click', async () => {
  await flushBoardSave(currentBoardId);

  const allBoards = [];
  for (const board of boards) {
    const data = board.id === currentBoardId ? state : await loadBoardData(board.id);
    const exported = await NotesStorage.exportStateWithAttachments(data);
    allBoards.push({
      id: board.id,
      name: board.name,
      notes: exported.notes,
      links: exported.links,
      nextId: exported.nextId
    });
  }

  const payload = {
    version: 3,
    exportedAt: new Date().toISOString(),
    currentBoard: currentBoardId,
    boards: allBoards
  };

  const stamp = new Date().toISOString().slice(0, 10);
  downloadJson(payload, `notas-flutuantes-${stamp}.json`);
});

const importInput = document.getElementById('importInput');
document.getElementById('importNotes').addEventListener('click', () => importInput.click());

importInput.addEventListener('change', async () => {
  const file = importInput.files[0];
  if (!file) return;

  try {
    const parsed = JSON.parse(await file.text());

    if (parsed && parsed.version >= 2 && Array.isArray(parsed.boards)) {
      const totalNotes = parsed.boards.reduce((n, b) => n + (b.notes ? b.notes.length : 0), 0);
      const totalBoards = parsed.boards.length;
      if (!confirm(t('importAllConfirm', { boards: totalBoards, notes: totalNotes }))) return;

      await flushAllPendingSaves();
      for (const oldBoard of boards) {
        await NotesStorage.deleteBoard(oldBoard.id);
        localStorage.removeItem(boardDataKey(oldBoard.id));
        localStorage.removeItem(recoveryKey(oldBoard.id));
      }

      const newBoards = [];
      for (const importedBoard of parsed.boards) {
        const id = importedBoard.id || ('b' + Date.now() + Math.random().toString(36).slice(2));
        const name = importedBoard.name || t('boardFallback');
        const rawState = {
          notes: Array.isArray(importedBoard.notes) ? importedBoard.notes : [],
          links: Array.isArray(importedBoard.links) ? importedBoard.links : [],
          nextId: typeof importedBoard.nextId === 'number'
            ? importedBoard.nextId
            : (importedBoard.notes || []).reduce((m, n) => Math.max(m, n.id || 0), 0) + 1
        };
        const migrated = await NotesStorage.migrateState(id, rawState);
        await NotesStorage.saveBoard(id, migrated);
        newBoards.push({ id, name });
      }

      boards = newBoards.length ? newBoards : [{ id: 'default', name: t('defaultBoard', { n: 1 }) }];
      if (!newBoards.length) await NotesStorage.saveBoard('default', { notes: [], links: [], nextId: 1 });
      saveBoardsList();
      snapshotDirty = true;

      const target = parsed.currentBoard && boards.find(b => b.id === parsed.currentBoard)
        ? parsed.currentBoard
        : boards[0].id;

      await switchBoard(target);
      alert(t('importSuccess', { boards: totalBoards }));

    } else if (parsed && Array.isArray(parsed.notes)) {
      const proceed = state.notes.length === 0 || confirm(t('importBoardConfirm'));
      if (!proceed) return;

      pushUndoSnapshot();
      const rawState = {
        notes: parsed.notes,
        links: Array.isArray(parsed.links) ? parsed.links : [],
        nextId: typeof parsed.nextId === 'number'
          ? parsed.nextId
          : parsed.notes.reduce((m, n) => Math.max(m, n.id || 0), 0) + 1
      };
      state = await NotesStorage.migrateState(currentBoardId, rawState);

      if (parsed.board) {
        const board = boards.find(b => b.id === currentBoardId);
        if (board) {
          board.name = parsed.board;
          saveBoardsList();
          renderBoardSelect();
        }
      }

      activeNoteId = null;
      save();
      render();

    } else {
      throw new Error(t('unrecognizedFileFormat'));
    }
  } catch (err) {
    alert(t('importError', { message: err.message }));
  } finally {
    importInput.value = '';
  }
});

/* ===== BACKUP DE UM QUADRO SÓ ===== */

document.getElementById('exportBoardNotes').addEventListener('click', async () => {
  await flushBoardSave(currentBoardId);

  const board = boards.find(b => b.id === currentBoardId);
  const boardName = board ? board.name : t('boardFallback');
  const exported = await NotesStorage.exportStateWithAttachments(state);
  const payload = {
    version: 3,
    exportedAt: new Date().toISOString(),
    board: boardName,
    notes: exported.notes,
    links: exported.links,
    nextId: exported.nextId
  };

  const stamp = new Date().toISOString().slice(0, 10);
  const slug = boardName
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'quadro';

  downloadJson(payload, `notas-flutuantes-${slug}-${stamp}.json`);
});

/* ===== VERSÕES AUTOMÁTICAS / RECUPERAÇÃO ===== */

const autoSnapshotsInput = document.getElementById('autoSnapshots');
const snapshotIntervalSelect = document.getElementById('snapshotInterval');
const snapshotSelect = document.getElementById('snapshotSelect');
const restoreSnapshotBtn = document.getElementById('restoreSnapshot');
const exportSnapshotBtn = document.getElementById('exportSnapshot');
const deleteSnapshotBtn = document.getElementById('deleteSnapshot');
let autoSnapshotTimer = null;

function snapshotIntervalMinutes() {
  const value = Number(localStorage.getItem(SNAPSHOT_INTERVAL_KEY) || '5');
  return [1, 5, 15, 30].includes(value) ? value : 5;
}

function autoSnapshotsEnabled() {
  return localStorage.getItem(AUTO_SNAPSHOTS_KEY) !== 'false';
}

function configureAutoSnapshots() {
  if (autoSnapshotTimer) clearInterval(autoSnapshotTimer);
  autoSnapshotTimer = null;

  const enabled = autoSnapshotsInput.checked;
  snapshotIntervalSelect.disabled = !enabled;
  localStorage.setItem(AUTO_SNAPSHOTS_KEY, String(enabled));
  localStorage.setItem(SNAPSHOT_INTERVAL_KEY, snapshotIntervalSelect.value);

  if (!enabled) return;
  const intervalMs = Number(snapshotIntervalSelect.value) * 60 * 1000;
  autoSnapshotTimer = setInterval(async () => {
    if (!appReady || !snapshotDirty) return;
    await saveRecoverySnapshot('auto');
  }, intervalMs);
}

function formatSnapshotLabel(snapshot) {
  const date = new Date(snapshot.createdAt);
  const when = date.toLocaleString(currentLanguage === 'en' ? 'en-US' : 'pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
  const kind = snapshot.reason === 'manual' ? t('manualSnapshot') : t('automaticSnapshot');
  return `${when} - ${kind}`;
}

async function captureWorkspaceState() {
  await flushAllPendingSaves();
  const workspaceBoards = [];

  for (const board of boards) {
    const boardState = board.id === currentBoardId
      ? NotesStorage.cleanState(state)
      : await loadBoardData(board.id);
    workspaceBoards.push({
      id: board.id,
      name: board.name,
      state: NotesStorage.cleanState(boardState)
    });
  }

  return NotesStorage.cleanWorkspace({
    currentBoard: currentBoardId,
    boards: workspaceBoards
  });
}

async function applyWorkspaceState(workspace) {
  const clean = NotesStorage.cleanWorkspace(workspace);
  if (!clean.boards.length) return false;

  await flushAllPendingSaves();

  const targetIds = new Set(clean.boards.map(board => board.id));
  for (const oldBoard of boards) {
    if (!targetIds.has(oldBoard.id)) {
      await NotesStorage.deleteBoardState(oldBoard.id);
      localStorage.removeItem(recoveryKey(oldBoard.id));
    }
  }

  for (const board of clean.boards) {
    await NotesStorage.saveBoard(board.id, board.state);
    localStorage.removeItem(recoveryKey(board.id));
  }

  boards = clean.boards.map(board => ({ id: board.id, name: board.name || t('boardFallback') }));
  saveBoardsList();

  currentBoardId = boards.some(board => board.id === clean.currentBoard)
    ? clean.currentBoard
    : boards[0].id;
  localStorage.setItem(CURRENT_BOARD_KEY, currentBoardId);

  const activeBoard = clean.boards.find(board => board.id === currentBoardId) || clean.boards[0];
  state = NotesStorage.cleanState(activeBoard.state);
  activeNoteId = null;
  linkPick = null;
  linkMode = false;
  linkBtn.classList.remove('active');
  setMoveMode(false);
  selectedNoteIds.clear();
  snapshotDirty = true;

  renderBoardSelect();
  render();
  flashSaveIndicator(true);
  await refreshSnapshotList();
  return true;
}

async function refreshSnapshotList(preferredId = null) {
  if (!snapshotSelect || !appReady) return;
  const previous = preferredId || snapshotSelect.value;
  const snapshots = await NotesStorage.listWorkspaceSnapshots(30);
  snapshotSelect.innerHTML = '';

  if (!snapshots.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = t('noSnapshots');
    snapshotSelect.appendChild(option);
    snapshotSelect.disabled = true;
    restoreSnapshotBtn.disabled = true;
    exportSnapshotBtn.disabled = true;
    deleteSnapshotBtn.disabled = true;
    return;
  }

  snapshotSelect.disabled = false;
  restoreSnapshotBtn.disabled = false;
  exportSnapshotBtn.disabled = false;
  deleteSnapshotBtn.disabled = false;
  snapshots.forEach(snapshot => {
    const option = document.createElement('option');
    option.value = snapshot.id;
    option.textContent = formatSnapshotLabel(snapshot);
    snapshotSelect.appendChild(option);
  });

  if (previous && snapshots.some(snapshot => snapshot.id === previous)) {
    snapshotSelect.value = previous;
  }
}

async function saveRecoverySnapshot(reason = 'manual') {
  if (!appReady) return;
  try {
    const workspace = await captureWorkspaceState();
    const snapshot = await NotesStorage.createWorkspaceSnapshot(workspace, reason);
    snapshotDirty = false;
    await refreshSnapshotList(snapshot.id);
    if (reason === 'manual') flashSaveIndicator(true);
  } catch (err) {
    console.error(t('snapshotSaveError'), err);
    flashSaveIndicator(false);
  }
}

async function selectedWorkspaceSnapshot() {
  const snapshotId = snapshotSelect.value;
  if (!snapshotId) return null;
  const snapshot = await NotesStorage.getSnapshot(snapshotId);
  return snapshot && snapshot.workspace ? snapshot : null;
}

async function exportSelectedSnapshot() {
  const snapshot = await selectedWorkspaceSnapshot();
  if (!snapshot) return;

  const allBoards = [];
  for (const board of snapshot.workspace.boards) {
    const exported = await NotesStorage.exportStateWithAttachments(board.state);
    allBoards.push({
      id: board.id,
      name: board.name,
      notes: exported.notes,
      links: exported.links,
      nextId: exported.nextId
    });
  }

  const payload = {
    version: 4,
    exportedAt: new Date().toISOString(),
    snapshotCreatedAt: new Date(snapshot.createdAt).toISOString(),
    snapshotReason: snapshot.reason,
    currentBoard: snapshot.workspace.currentBoard,
    boards: allBoards
  };

  const d = new Date(snapshot.createdAt);
  const stamp = [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0')
  ].join('-');
  const time = `${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`;
  downloadJson(payload, `notas-flutuantes-versao-${stamp}-${time}.json`);
}

autoSnapshotsInput.addEventListener('change', configureAutoSnapshots);
snapshotIntervalSelect.addEventListener('change', configureAutoSnapshots);
document.getElementById('saveSnapshotNow').addEventListener('click', () => saveRecoverySnapshot('manual'));
exportSnapshotBtn.addEventListener('click', exportSelectedSnapshot);

deleteSnapshotBtn.addEventListener('click', async () => {
  const snapshot = await selectedWorkspaceSnapshot();
  if (!snapshot || !confirm(t('confirmDeleteSnapshot'))) return;

  await NotesStorage.deleteSnapshot(snapshot.id);
  pushUndoAction({ type: 'snapshot-presence', snapshot, present: true });
  await refreshSnapshotList();
});

restoreSnapshotBtn.addEventListener('click', async () => {
  const snapshot = await selectedWorkspaceSnapshot();
  if (!snapshot || !confirm(t('confirmRestoreSnapshot'))) return;

  const before = await captureWorkspaceState();
  const restored = await applyWorkspaceState(snapshot.workspace);
  if (restored) pushUndoAction({ type: 'workspace-state', workspace: before });
  updateUndoRedoButtons();
});

/* ===== PAINEL DE CONFIGURAÇÕES ===== */

const settingsPanel  = document.getElementById('settingsPanel');
const settingsToggle = document.getElementById('settingsToggle');
const settingsClose  = document.getElementById('settingsClose');

function openSettings() {
  closeCalendar();
  settingsPanel.classList.remove('hidden');
  settingsToggle.classList.add('active');
  refreshSnapshotList();
}

function closeSettings() {
  settingsPanel.classList.add('hidden');
  settingsToggle.classList.remove('active');
}

function toggleSettingsPanel() {
  settingsPanel.classList.contains('hidden') ? openSettings() : closeSettings();
}

settingsToggle.addEventListener('click', toggleSettingsPanel);
settingsClose.addEventListener('click', closeSettings);
document.getElementById('languageSelect').addEventListener('change', e => setLanguage(e.target.value));

// Fecha ao clicar fora do painel
document.addEventListener('mousedown', e => {
  if (settingsPanel.classList.contains('hidden')) return;
  if (settingsPanel.contains(e.target)) return;
  if (settingsToggle.contains(e.target)) return;

  closeSettings();
});

/* ===== DESFAZER / REFAZER ===== */

let undoStack = [];
let redoStack = [];
const UNDO_LIMIT = 50;

const undoBtn = document.getElementById('undoBtn');
const redoBtn = document.getElementById('redoBtn');

function updateUndoRedoButtons() {
  undoBtn.disabled = undoStack.length === 0;
  redoBtn.disabled = redoStack.length === 0;
}

function pushHistoryEntry(stack, entry) {
  stack.push(entry);
  if (stack.length > UNDO_LIMIT) stack.shift();
}

function pushUndoAction(entry) {
  pushHistoryEntry(undoStack, entry);
  redoStack = [];
  updateUndoRedoButtons();
}

function pushUndoSnapshot() {
  pushUndoAction({
    type: 'board-state',
    boardId: currentBoardId,
    state: NotesStorage.cleanState(state)
  });
}

async function executeHistoryEntry(entry, inverseStack) {
  if (!entry) return;

  if (entry.type === 'board-state') {
    // Trocar de quadro limpa o histórico, então normalmente o ID coincide.
    // A checagem evita aplicar acidentalmente um estado no quadro errado.
    if (entry.boardId !== currentBoardId) return;

    pushHistoryEntry(inverseStack, {
      type: 'board-state',
      boardId: currentBoardId,
      state: NotesStorage.cleanState(state)
    });
    state = NotesStorage.cleanState(entry.state);
    activeNoteId = null;
    linkPick = null;
    selectedNoteIds.clear();
    save();
    render();
    return;
  }

  if (entry.type === 'workspace-state') {
    const currentWorkspace = await captureWorkspaceState();
    const applied = await applyWorkspaceState(entry.workspace);
    if (applied) {
      pushHistoryEntry(inverseStack, {
        type: 'workspace-state',
        workspace: currentWorkspace
      });
    }
    return;
  }

  if (entry.type === 'snapshot-presence' && entry.snapshot) {
    if (entry.present) {
      await NotesStorage.putSnapshot(entry.snapshot);
      await refreshSnapshotList(entry.snapshot.id);
    } else {
      await NotesStorage.deleteSnapshot(entry.snapshot.id);
      await refreshSnapshotList();
    }

    pushHistoryEntry(inverseStack, {
      type: 'snapshot-presence',
      snapshot: entry.snapshot,
      present: !entry.present
    });
  }
}

async function undo() {
  if (!undoStack.length) return;
  const entry = undoStack.pop();
  await executeHistoryEntry(entry, redoStack);
  updateUndoRedoButtons();
}

async function redo() {
  if (!redoStack.length) return;
  const entry = redoStack.pop();
  await executeHistoryEntry(entry, undoStack);
  updateUndoRedoButtons();
}

undoBtn.addEventListener('click', undo);
redoBtn.addEventListener('click', redo);

/* ===== MOVER COM TECLADO (M) ===== */

const MOVE_STEP = 10;
const MOVE_STEP_FAST = 40;

function setMoveMode(on) {
  moveMode = on;
  document.body.classList.toggle('move-mode', moveMode);
}

// Nota(s)-alvo do modo mover: a seleção múltipla, senão a nota ativa
function moveTargets() {
  const ids = selectedNoteIds.size > 0
    ? [...selectedNoteIds]
    : (activeNoteId != null ? [activeNoteId] : []);

  return state.notes.filter(n => ids.includes(n.id) && !n.pinned);
}

function nudgeNotes(dx, dy) {
  const targets = moveTargets();
  if (!targets.length) return false;

  targets.forEach(n => {
    n.x += dx;
    n.y += dy;
    const el = canvas.querySelector(`.note[data-id="${n.id}"]`);
    if (el) {
      el.style.left = n.x + 'px';
      el.style.top  = n.y + 'px';
    }
  });

  drawLinks();
  save();
  return true;
}

/* ===== ATALHOS DE TECLADO ===== */

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (document.activeElement === searchInput) searchInput.blur();

    if (linkPick != null) {
      linkPick = null;
      document.querySelectorAll('.note.selected').forEach(n => n.classList.remove('selected'));
    }

    if (linkMode) {
      linkMode = false;
      linkBtn.classList.remove('active');
    }

    if (moveMode) setMoveMode(false);

    closeAllColorPopups();
    closeCalendar();
    closeSettings();
    return;
  }

  const tag = document.activeElement && document.activeElement.tagName;
  const inField = tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT';

  // Atalho L: ativar/desativar modo ligação (fora de campos de texto)
  if (!inField && !e.ctrlKey && !e.metaKey && e.key.toLowerCase() === 'l') {
    e.preventDefault();
    linkBtn.click();
    return;
  }

  // Atalho M: ativar/desativar modo mover (fora de campos de texto).
  // Com o modo ativo, as setas do teclado deslocam a nota ativa (ou toda
  // a seleção múltipla); Shift+seta desloca mais rápido.
  if (!inField && !e.ctrlKey && !e.metaKey && e.key.toLowerCase() === 'm') {
    e.preventDefault();
    if (!moveMode && !moveTargets().length) return; // nada selecionado/ativo pra mover
    if (!moveMode) pushUndoSnapshot();
    setMoveMode(!moveMode);
    return;
  }

  if (!inField && moveMode && e.key.startsWith('Arrow')) {
    e.preventDefault();
    const step = e.shiftKey ? MOVE_STEP_FAST : MOVE_STEP;
    const moved =
      e.key === 'ArrowUp'    ? nudgeNotes(0, -step) :
      e.key === 'ArrowDown'  ? nudgeNotes(0, step) :
      e.key === 'ArrowLeft'  ? nudgeNotes(-step, 0) :
      e.key === 'ArrowRight' ? nudgeNotes(step, 0) : false;
    if (!moved) setMoveMode(false); // nota-alvo sumiu (ex.: desfazer) — sai do modo
    return;
  }

  // Delete / Backspace: apagar notas da seleção múltipla (fora de campos de texto)
  if (!inField && (e.key === 'Delete' || e.key === 'Backspace')) {
    if (selectedNoteIds.size > 0) {
      e.preventDefault();
      if (!confirm(t('confirmDeleteSelected', { count: selectedNoteIds.size }))) return;
      pushUndoSnapshot();
      const ids = [...selectedNoteIds];
      state.notes = state.notes.filter(n => !ids.includes(n.id));
      state.links = state.links.filter(l => !ids.includes(l.a) && !ids.includes(l.b));
      selectedNoteIds.clear();
      save();
      render();
      return;
    }
  }

  const mod = e.ctrlKey || e.metaKey;
  if (!mod) return;

  if (inField) return; // deixa o navegador cuidar de copiar/colar/desfazer texto normalmente

  const key = e.key.toLowerCase();

  if (key === 'z') {
    e.preventDefault();
    e.shiftKey ? redo() : undo();
  } else if (key === 'y') {
    e.preventDefault();
    redo();
  } else if (key === 'c') {
    e.preventDefault();
    copyActiveNote();
  } else if (key === 'v') {
    e.preventDefault();
    pasteNote();
  }
});

/* Fecha popups de cor ao clicar fora */

document.addEventListener('mousedown', e => {
  if (e.target.closest('.color-popup') || e.target.closest('.color-btn')) return;
  closeAllColorPopups();
});

/* ===== CALENDÁRIO ===== */

const calEl = document.getElementById('calendar');
const calTitle = document.getElementById('calTitle');
const calGrid = document.getElementById('calGrid');
const calToggle = document.getElementById('toggleCal');


function openCalendar() {
  closeSettings();
  calEl.classList.remove('hidden');
  calToggle.classList.add('active');
  renderCalendar();
}

function closeCalendar() {
  calEl.classList.add('hidden');
  calToggle.classList.remove('active');
}

function toggleCalendar() {
  calEl.classList.contains('hidden') ? openCalendar() : closeCalendar();
}

calToggle.addEventListener('click', toggleCalendar);

document.addEventListener('mousedown', e => {
  if (calEl.classList.contains('hidden')) return;
  if (calEl.contains(e.target)) return;
  if (e.target === calToggle) return;

  closeCalendar();
});

document.getElementById('calPrev').addEventListener('click', () => {
  calView.setMonth(calView.getMonth() - 1);
  renderCalendar();
});

document.getElementById('calNext').addEventListener('click', () => {
  calView.setMonth(calView.getMonth() + 1);
  renderCalendar();
});

function renderCalendar() {
  const year = calView.getFullYear();
  const month = calView.getMonth();

  const months = t('months');
  calTitle.textContent = `${months[month]} ${year}`;

  calGrid.innerHTML = '';

  t('dow').forEach(d => {
    const c = document.createElement('div');
    c.className = 'dow';
    c.textContent = d;
    calGrid.appendChild(c);
  });

  const first = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  for (let i = 0; i < first; i++) {
    const c = document.createElement('div');
    c.className = 'day empty';
    calGrid.appendChild(c);
  }

  const today = new Date();

  for (let d = 1; d <= daysInMonth; d++) {
    const c = document.createElement('div');
    c.className = 'day';

    if (d === today.getDate() && month === today.getMonth() && year === today.getFullYear()) {
      c.classList.add('today');
    }

    c.textContent = d;

    c.addEventListener('click', () => insertDateIntoActiveNote(year, month, d));

    calGrid.appendChild(c);
  }
}

function insertDateIntoActiveNote(y, m, d) {
  let note = state.notes.find(n => n.id === activeNoteId);

  if (!note) {
    const c = centerOfView();
    note = createNote(c.x - 110, c.y - 70);
  }

  const dd = String(d).padStart(2, '0');
  const mm = String(m + 1).padStart(2, '0');
  const dateStr = currentLanguage === 'en' ? `${mm}/${dd}/${y}` : `${dd}/${mm}/${y}`;

  const el = document.querySelector(`.note[data-id="${note.id}"] textarea`);

  if (el) {
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;

    const before = el.value.slice(0, start);
    const after = el.value.slice(end);

    const insert =
      (before && !before.endsWith(' ') && !before.endsWith('\n') ? ' ' : '') + `${dateStr} `;

    el.focus();
    el.setSelectionRange(start, end);

    // Mesmo problema/solução de applyLocalLink: execCommand preserva o
    // desfazer nativo do textarea; atribuir .value direto o apaga.
    const ok = document.execCommand('insertText', false, insert);

    if (!ok) {
      el.value = before + insert + after;
      note.text = el.value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      const pos = (before + insert).length;
      el.setSelectionRange(pos, pos);
    }

    save();
  }
}

/* ===== MODO ESCURO ===== */

const darkBtn = document.getElementById('darkMode');

function applyNotesTheme(isDarkNow) {
  document.body.classList.toggle('dark', isDarkNow);

  // Reaplica cores de fundo/borda das notas
  document.querySelectorAll('.note').forEach(el => {
    const id = Number(el.dataset.id);
    const note = state.notes.find(n => n.id === id);
    const handle = el.querySelector('.handle');
    if (note && handle) applyNoteColor(el, handle, note.colorIndex || 0);

    // Atualiza bolinhas de popup de cor que estiver aberto
    el.querySelectorAll('.color-swatch').forEach((sw, i) => {
      const c = NOTE_COLORS[i];
      if (c) sw.style.background = isDarkNow ? c.dark.swatch : c.light.swatch;
    });
  });
}

const initialGlobalTheme = globalThis.Mega?.settings?.get('theme');
const initialDark = initialGlobalTheme
  ? (initialGlobalTheme === 'dark' || (initialGlobalTheme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches))
  : localStorage.getItem('dark-mode') === 'true';
applyNotesTheme(initialDark);

darkBtn.addEventListener('click', () => {
  const nextDark = !document.body.classList.contains('dark');
  applyNotesTheme(nextDark);
  localStorage.setItem('dark-mode', String(nextDark));
  globalThis.Mega?.settings?.set('theme', nextDark ? 'dark' : 'light').catch(() => {});
});

globalThis.Mega?.settings?.subscribe((settings) => {
  const isDark = settings.theme === 'dark' || (settings.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  applyNotesTheme(isDark);
}, { immediate: false });

document.addEventListener('workspace:settings-applied', event => {
  const isDark = event.detail.theme === 'dark' || (event.detail.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  applyNotesTheme(isDark);
});

/* ===== POPUP DE LINK LOCAL ===== */

const localLinkPopup = document.getElementById('local-link-popup');
const llpUrlInput    = document.getElementById('llp-url-input');
const llpConfirm     = document.getElementById('llp-confirm');
const llpCancel      = document.getElementById('llp-cancel');

let llpTargetTextarea = null;
let llpSelStart = 0;
let llpSelEnd   = 0;
let llpSelectedText = '';

function openLocalLinkPopup(textarea, noteEl) {
  const selStart = textarea.selectionStart;
  const selEnd   = textarea.selectionEnd;
  const selected = textarea.value.slice(selStart, selEnd).trim();

  llpTargetTextarea = textarea;
  llpSelStart = selStart;
  llpSelEnd   = selEnd;
  llpSelectedText = selected;

  // Aplica dark mode no popup dinamicamente
  const isDark = document.body.classList.contains('dark');
  localLinkPopup.classList.toggle('dark', isDark);

  // Posiciona o popup abaixo do handle da nota
  const handleEl = noteEl.querySelector('.handle');
  const rect = handleEl.getBoundingClientRect();

  localLinkPopup.classList.remove('hidden');
  localLinkPopup.offsetHeight; // força reflow
  localLinkPopup.classList.add('visible');

  localLinkPopup.style.left = Math.min(rect.left, window.innerWidth - 400) + 'px';
  localLinkPopup.style.top  = (rect.bottom + 6) + 'px';

  llpUrlInput.value = '';
  if (selected && /^(https?|file):\/\//.test(selected)) {
    llpUrlInput.value = selected;
  }
  llpUrlInput.focus();
  llpUrlInput.select();
}

function closeLocalLinkPopup() {
  localLinkPopup.classList.remove('visible');
  setTimeout(() => {
    if (!localLinkPopup.classList.contains('visible')) {
      localLinkPopup.classList.add('hidden');
    }
  }, 200);
  llpTargetTextarea = null;
}

function applyLocalLink() {
  if (!llpTargetTextarea) return;
  const url = llpUrlInput.value.trim();
  if (!url) { closeLocalLinkPopup(); return; }

  const ta = llpTargetTextarea;

  // Com texto selecionado → [texto](url) (markdown com rótulo)
  // Sem texto           → (url)          (parêntese simples, sem colchetes)
  const insertion = llpSelectedText
    ? `[${llpSelectedText}](${url})`
    : `(${url})`;

  ta.focus();
  ta.setSelectionRange(llpSelStart, llpSelEnd);

  // execCommand insere pelo mesmo caminho de uma digitação normal, então
  // mantém o histórico nativo de desfazer do textarea. Atribuir ta.value
  // diretamente apaga esse histórico — por isso o Ctrl+Z não desfazia o
  // link (mas desfazia uma edição de texto normal).
  const ok = document.execCommand('insertText', false, insertion);

  if (!ok) {
    // Navegador sem suporte a execCommand: aplica sem preservar o undo nativo
    const before = ta.value.slice(0, llpSelStart);
    const after  = ta.value.slice(llpSelEnd);
    ta.value = before + insertion + after;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    const newPos = before.length + insertion.length;
    ta.setSelectionRange(newPos, newPos);
  }

  closeLocalLinkPopup();
}

llpConfirm.addEventListener('click', applyLocalLink);

llpCancel.addEventListener('click', closeLocalLinkPopup);

llpUrlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); applyLocalLink(); }
  if (e.key === 'Escape') { e.preventDefault(); closeLocalLinkPopup(); }
});

// Fecha ao clicar fora do popup
document.addEventListener('mousedown', e => {
  if (localLinkPopup.classList.contains('hidden')) return;
  if (!localLinkPopup.contains(e.target)) closeLocalLinkPopup();
});

/* ===== START ===== */

function renderBoardSelect() {
  const sel = document.getElementById('boardSelect');
  sel.innerHTML = '';
  boards.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.id;
    opt.textContent = b.name;
    if (b.id === currentBoardId) opt.selected = true;
    sel.appendChild(opt);
  });
}

async function initializeApp() {
  try {
    await NotesStorage.open();
    state = await loadBoardData(currentBoardId);
    appReady = true;

    applyStaticTranslations();
    renderBoardSelect();
    applyTransform();
    render();
    updateUndoRedoButtons();

    autoSnapshotsInput.checked = autoSnapshotsEnabled();
    snapshotIntervalSelect.value = String(snapshotIntervalMinutes());
    configureAutoSnapshots();
    await refreshSnapshotList();
  } catch (err) {
    console.error('Falha ao iniciar o aplicativo:', err);
    flashSaveIndicator(false);
    alert(t('saveError'));
  }
}

initializeApp();
