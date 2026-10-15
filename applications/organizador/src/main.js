import { t, tr, applyLanguage, errorText } from './services/i18n.js';
import './styles/app.css';
import { el, icon, iconButton, button, showError, emptyState, toast } from './components/ui.js';
import { openDatabase, currentRevision } from './storage/database.js';
import { changes } from './services/data-service.js';
import { applyTheme, preference, setPreference } from './services/preferences-service.js';
import "./organizer-presence.js";

const routes = {
  dashboard: { get label() { return t('Visão geral'); }, icon: 'home', load: () => import('./modules/dashboard/index.js') },
  tasks: { get label() { return t('Tarefas'); }, icon: 'tasks', load: () => import('./modules/tasks/index.js') },
  projects: { get label() { return t('Projetos'); }, icon: 'projects', load: () => import('./modules/projects/index.js') },
  notes: { get label() { return t('Notas'); }, icon: 'notes', load: () => import('./modules/notes/index.js') },
  boards: { get label() { return t('Quadros'); }, icon: 'boards', load: () => import('./modules/boards/index.js') },
  settings: { get label() { return t('Configurações'); }, icon: 'settings', load: () => import('./modules/settings/index.js') },
};
const app = document.querySelector('#app');
let main, shell, crumb, cleanup, controller, beforeLeave = () => true, dataRefresh, lastHash = '', routeKey, refreshTimer, pendingRefresh = {}, revision = 0, rendering = 0;
const openSearch = async () => (await import('./modules/search/index.js')).openSearch();
applyTheme();
applyLanguage();

function buildShell() {
  shell = el('div', { className: 'app-shell' });
  if (preference('collapsed', 'false') === 'true') shell.classList.add('collapsed');
  const brand = el('a', { className: 'brand', href: '#/dashboard', 'aria-label': t('Organizador — início') }, el('span', { className: 'brand-mark' }, icon('organizer')), el('span', { className: 'brand-word' }, 'organizador', el('span', {}, t('SEU ESPAÇO PESSOAL'))));
  const navigation = el('nav', { className: 'sidebar-nav', 'aria-label': t('Navegação principal') });
  for (const [key, route] of Object.entries(routes).filter(([key]) => key !== 'settings')) navigation.append(el('a', { className: 'nav-item', href: `#/${key}`, title: route.label, dataset: { route: key } }, icon(route.icon), el('span', {}, route.label)));
  navigation.append(button(t('Busca global'), openSearch, { variant: 'nav-item search-nav', symbol: 'search', title: t('Busca global') }));
  const sidebar = el('aside', { className: 'sidebar' }, brand, el('div', { className: 'workspace-switch' }, icon('projects'), el('span', {}, t('Meu espaço')), el('span', { className: 'workspace-indicator', 'aria-hidden': 'true' }, '01')), el('div', { className: 'sidebar-label' }, t('Área de trabalho')), navigation, el('div', { className: 'sidebar-bottom' }, el('div', { className: 'local-note' }, el('span', { className: 'local-dot' }), el('div', {}, el('strong', {}, t('Só seu. Sempre por perto.')), el('small', {}, t('Seus dados neste dispositivo.')))), el('a', { className: 'nav-item', href: '#/settings', title: t('Configurações'), dataset: { route: 'settings' } }, icon('settings'), el('span', {}, t('Configurações'))), el('div', { className: 'sidebar-profile' }, el('span', { className: 'avatar' }, t('EU')), el('span', { className: 'profile-label' }, el('strong', {}, t('Meu espaço')), el('small', {}, t('Pessoal · local'))), iconButton(t('Recolher ou expandir menu'), 'panel', () => { shell.classList.toggle('collapsed'); setPreference('collapsed', String(shell.classList.contains('collapsed'))); }))));
  const menu = iconButton(t('Abrir menu'), 'menu', () => shell.classList.toggle('mobile-open'), { className: 'icon-button mobile-menu' });
  crumb = el('span', { className: 'breadcrumb' }, t('Visão geral'));
  const searchButton = el('button', { className: 'header-search', onClick: openSearch, 'aria-label': t('Abrir busca global') }, icon('search'), el('span', {}, t('Buscar no seu espaço…')), el('kbd', {}, 'Ctrl K'));
  const header = el('header', { className: 'topbar' }, el('div', { className: 'header-location' }, menu, icon('home'), el('span', { className: 'crumb-slash' }, '/'), crumb), searchButton, el('span', { className: 'header-local', title: t('Dados locais neste navegador') }, el('i', { className: 'local-dot' }), 'Local'));
  main = el('main', { id: 'main-content', className: 'main-content', tabIndex: -1 });
  shell.append(sidebar, el('div', { className: 'main-shell' }, header, main), el('button', { className: 'menu-backdrop', 'aria-label': t('Fechar menu'), onClick: () => shell.classList.remove('mobile-open') }));
  app.replaceChildren(shell);
}

async function render({ force = false } = {}) {
  const hash = location.hash || '#/dashboard';
  if (!force && hash === lastHash) return;
  const seamless = Boolean(main?.querySelector('.page-inner'));
  const run = ++rendering;
  if (lastHash && !await beforeLeave()) { history.replaceState(null, '', lastHash); return; }
  if (run !== rendering) return;
  controller?.abort(); cleanup?.(); cleanup = null; beforeLeave = () => true; dataRefresh = null;
  controller = new AbortController();
  const [path, queryString = ''] = hash.slice(1).split('?');
  const [key, id] = path.split('/').filter(Boolean);
  routeKey = key || 'dashboard';
  lastHash = hash;
  shell.classList.remove('mobile-open');
  const route = routes[routeKey];
  for (const link of shell.querySelectorAll('[data-route]')) {
    const selected = link.dataset.route === routeKey;
    link.classList.toggle('active', selected);
    if (selected) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  }
  crumb.textContent = route?.label || t('Página não encontrada');
  document.title = tr`${route?.label || t('Página não encontrada')} · Organizador`;
  main.className = 'main-content';
  main.dataset.page = routeKey;
  if (!seamless) main.replaceChildren(el('div', { className: 'page-loading', role: 'status' }, t('Carregando…')));
  if (!route) { main.replaceChildren(emptyState('search', t('Este caminho não existe'), t('Volte ao início para continuar.'), el('a', { className: 'button primary', href: '#/dashboard' }, t('Ir para o início')))); return; }
  try {
    const module = await route.load();
    if (run !== rendering) return;
    const content = el('div', { className: seamless ? 'page-inner data-refresh' : 'page-inner' });
    if (!seamless) { main.replaceChildren(); main.append(content); }
    const context = { id, query: new URLSearchParams(queryString), signal: controller.signal, error: showError, openSearch, navigate: path => { location.hash = path; }, setBeforeLeave: fn => { beforeLeave = fn; }, setDataRefresh: fn => { dataRefresh = fn; }, refresh: refreshContent };
    const dispose = await module.mount(content, context);
    if (run !== rendering) { dispose?.(); return; }
    if (seamless) main.replaceChildren(content);
    cleanup = dispose;
    revision = await currentRevision();
  } catch (error) {
    if (run !== rendering) return;
    main.replaceChildren(emptyState('warning', t('Não foi possível abrir esta página'), errorText(error), button(t('Tentar novamente'), () => render({ force: true }), { variant: 'primary' })));
    showError(error);
  }
}

function focusSnapshot() {
  const active = document.activeElement;
  if (!active || !main.contains(active)) return null;
  if (active.dataset.focusKey) return { key: active.dataset.focusKey };
  const path = [];
  for (let node = active; node && node !== main; node = node.parentElement) path.unshift([...node.parentElement.children].indexOf(node));
  return { path, tag: active.tagName, type: active.type || '', aria: active.getAttribute('aria-label') || '' };
}

function restoreFocus(snapshot) {
  if (!snapshot) return;
  let target;
  if (snapshot.key) target = [...main.querySelectorAll('[data-focus-key]')].find(node => node.dataset.focusKey === snapshot.key);
  else {
    target = snapshot.path.reduce((node, index) => node?.children[index], main);
    if (target?.tagName !== snapshot.tag || (target.type || '') !== snapshot.type || (target.getAttribute('aria-label') || '') !== snapshot.aria) target = null;
  }
  target?.focus({ preventScroll: true });
}

async function refreshContent() {
  const hash = location.hash || '#/dashboard';
  if (hash !== lastHash) return render();
  const route = routes[routeKey];
  if (!route) return render({ force: true });
  const run = ++rendering;
  const nextController = new AbortController();
  const [, queryString = ''] = hash.slice(1).split('?');
  const [, id] = hash.slice(1).split('?')[0].split('/').filter(Boolean);
  const content = el('div', { className: 'page-inner data-refresh' });
  let nextCleanup, nextBeforeLeave = () => true, nextDataRefresh = null;
  try {
    const module = await route.load();
    const context = { id, query: new URLSearchParams(queryString), signal: nextController.signal, error: showError, openSearch, navigate: path => { location.hash = path; }, setBeforeLeave: fn => { nextBeforeLeave = fn; }, setDataRefresh: fn => { nextDataRefresh = fn; }, refresh: refreshContent };
    nextCleanup = await module.mount(content, context);
    if (run !== rendering || hash !== (location.hash || '#/dashboard')) { nextController.abort(); nextCleanup?.(); return; }
    const scrollTop = main.scrollTop;
    const focus = focusSnapshot();
    controller?.abort(); cleanup?.();
    controller = nextController; cleanup = nextCleanup; beforeLeave = nextBeforeLeave; dataRefresh = nextDataRefresh;
    main.replaceChildren(content);
    main.scrollTop = scrollTop;
    restoreFocus(focus);
    revision = await currentRevision();
  } catch (error) {
    nextController.abort(); nextCleanup?.();
    if (run === rendering) showError(error);
  }
}

async function runScheduledRefresh() {
  const dialog = document.querySelector('dialog[open]');
  if (dialog) {
    dialog.addEventListener('close', () => scheduleRefresh(), { once: true });
    return;
  }
  const detail = pendingRefresh;
  pendingRefresh = {};
  const scrollTop = main.scrollTop;
  const focus = focusSnapshot();
  const handled = dataRefresh ? await dataRefresh(detail) : false;
  if (!handled) await refreshContent();
  else {
    main.scrollTop = scrollTop;
    restoreFocus(focus);
    revision = await currentRevision();
  }
  if (detail.external) toast(t('Dados atualizados em outra aba.'));
}

function scheduleRefresh(detail = {}) {
  clearTimeout(refreshTimer);
  if (routeKey === 'boards') return; // Preserve the original canvas and its in-flight saves.
  pendingRefresh = { ...pendingRefresh, ...detail, external: pendingRefresh.external || detail.external };
  refreshTimer = setTimeout(() => runScheduledRefresh().catch(showError), 40);
}

async function start() {
  try {
    await openDatabase();
    buildShell();
    await render({ force: true });
  } catch (error) {
    app.replaceChildren(emptyState('warning', t('Precisamos abrir seu armazenamento'), tr`${errorText(error)}. Seus dados não serão substituídos por uma base temporária.`, button(t('Tentar novamente'), start, { variant: 'primary' })));
  }
}

window.addEventListener('languagechange', () => {
  if (!main) return;
  buildShell();
  render({ force: true }).then(() => document.querySelector('#interface-language')?.focus()).catch(showError);
});
window.addEventListener('hashchange', () => render().catch(showError));
document.querySelector('.skip-link').addEventListener('click', event => { event.preventDefault(); main?.focus(); });
window.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch().catch(showError); } if (event.key === 'Escape') shell?.classList.remove('mobile-open'); });
window.addEventListener('focus', async () => { try { if (main && await currentRevision() !== revision) scheduleRefresh(); } catch (error) { showError(error); } });
window.addEventListener('database-blocked', () => { app.replaceChildren(emptyState('warning', t('Outra aba está usando uma versão anterior'), t('Feche a outra aba deste painel para liberar a atualização. Esta tela continuará automaticamente.'))); });
window.addEventListener('database-versionchange', () => toast(t('Uma nova versão foi aberta em outra aba. Salve seu texto e recarregue esta página.'), true));
changes.addEventListener('change', event => scheduleRefresh(event.detail));
setInterval(() => { if (routeKey === 'dashboard' && !document.hidden) scheduleRefresh(); }, 60000);
start();
