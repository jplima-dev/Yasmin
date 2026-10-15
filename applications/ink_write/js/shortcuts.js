(() => {
  const KEY = 'inkwrite-shortcuts-v1';
  const DEFAULTS = Object.freeze({
    save: 'Mod+S',
    bold: 'Mod+B',
    italic: 'Mod+I',
    underline: 'Mod+U',
    link: 'Mod+K',
    find: 'Mod+F',
    replace: 'Mod+H',
    undo: 'Mod+Z',
    redo: 'Mod+Shift+Z',
    print: 'Mod+Shift+P',
    export: 'Mod+Shift+E',
    pageBreak: 'Mod+Enter',
    footnote: 'Mod+Alt+F',
    toc: 'Mod+Alt+T'
  });

  const LABELS = {
    save: 'Salvar', bold: 'Negrito', italic: 'Itálico', underline: 'Sublinhado', link: 'Inserir link',
    find: 'Buscar', replace: 'Substituir', undo: 'Desfazer', redo: 'Refazer', print: 'PDF / Imprimir',
    export: 'Exportar', pageBreak: 'Quebra de página', footnote: 'Nota de rodapé', toc: 'Sumário'
  };

  function load() {
    try {
      const value = JSON.parse(localStorage.getItem(KEY) || '{}');
      return { ...DEFAULTS, ...(value && typeof value === 'object' ? value : {}) };
    } catch { return { ...DEFAULTS }; }
  }

  function normalizeCombo(combo = '') {
    const parts = String(combo).split('+').map(part => part.trim()).filter(Boolean);
    const mods = [];
    const key = parts.pop() || '';
    const set = new Set(parts.map(part => part.toLowerCase()));
    if (set.has('mod')) mods.push('Mod');
    else {
      if (set.has('ctrl') || set.has('control')) mods.push('Ctrl');
      if (set.has('meta') || set.has('cmd') || set.has('command')) mods.push('Meta');
    }
    if (set.has('alt') || set.has('option')) mods.push('Alt');
    if (set.has('shift')) mods.push('Shift');
    const cleanKey = key.length === 1 ? key.toUpperCase() : key;
    return [...mods, cleanKey].filter(Boolean).join('+');
  }

  function eventCombo(event) {
    const parts = [];
    if (event.ctrlKey || event.metaKey) parts.push('Mod');
    if (event.altKey) parts.push('Alt');
    if (event.shiftKey) parts.push('Shift');
    let key = event.key;
    if (['Control','Meta','Alt','Shift'].includes(key)) return '';
    if (key === ' ') key = 'Space';
    if (key.length === 1) key = key.toUpperCase();
    parts.push(key);
    return normalizeCombo(parts.join('+'));
  }

  function create() {
    let shortcuts = load();

    function save() { localStorage.setItem(KEY, JSON.stringify(shortcuts)); }
    function get(action) { return shortcuts[action] || DEFAULTS[action] || ''; }
    function set(action, combo) {
      if (!(action in DEFAULTS)) return false;
      const normalized = normalizeCombo(combo);
      if (!normalized) return false;
      shortcuts[action] = normalized;
      save();
      return true;
    }
    function reset() { shortcuts = { ...DEFAULTS }; save(); renderDialog(); }
    function matches(event, action) {
      const combo = eventCombo(event);
      if (combo === normalizeCombo(get(action))) return true;
      // Compatibilidade esperada no Windows/Linux mesmo quando o atalho principal
      // de Refazer está configurado como Mod+Shift+Z.
      if (action === 'redo' && combo === 'Mod+Y') return true;
      return false;
    }

    function openDialog() {
      renderDialog();
      document.querySelector('#shortcutDialog')?.showModal();
    }
    function closeDialog() { if (document.querySelector('#shortcutDialog')?.open) document.querySelector('#shortcutDialog').close(); }

    function renderDialog() {
      const list = document.querySelector('#shortcutList');
      if (!list) return;
      list.innerHTML = '';
      Object.keys(DEFAULTS).forEach(action => {
        const row = document.createElement('label');
        row.className = 'shortcut-row';
        const title = document.createElement('span');
        title.textContent = LABELS[action] || action;
        const input = document.createElement('input');
        input.type = 'text';
        input.readOnly = true;
        input.value = get(action);
        input.dataset.shortcutAction = action;
        input.setAttribute('aria-label', `Atalho para ${title.textContent}`);
        input.title = 'Clique e pressione a nova combinação';
        row.append(title, input);
        list.append(row);
      });
    }

    function bindDialog() {
      const dialog = document.querySelector('#shortcutDialog');
      if (!dialog || dialog.dataset.bound === '1') return;
      dialog.dataset.bound = '1';
      dialog.querySelectorAll('[data-shortcut-close]').forEach(button => button.addEventListener('click', closeDialog));
      document.querySelector('#shortcutReset')?.addEventListener('click', reset);
      dialog.addEventListener('keydown', event => {
        const input = event.target.closest?.('[data-shortcut-action]');
        if (!input) return;
        event.preventDefault();
        const combo = eventCombo(event);
        if (!combo) return;
        const action = input.dataset.shortcutAction;
        const conflict = Object.entries(shortcuts).find(([other, value]) => other !== action && normalizeCombo(value) === combo);
        if (conflict) {
          input.setCustomValidity(`Esse atalho já está em uso por ${LABELS[conflict[0]] || conflict[0]}.`);
          input.reportValidity();
          setTimeout(() => input.setCustomValidity(''), 1200);
          return;
        }
        set(action, combo);
        input.value = combo;
      });
    }

    bindDialog();
    return { get, set, reset, matches, eventCombo, openDialog, closeDialog, renderDialog, defaults: { ...DEFAULTS } };
  }

  window.InkWriteShortcuts = { create };
})();
