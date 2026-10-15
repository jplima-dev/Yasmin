import { t } from '../../services/i18n.js';
import { el, pageHeading, button, select, emptyState, toast, icon } from '../../components/ui.js';
import { projectOptions, get, setBoardProject } from '../../services/data-service.js';

export async function mount(root, ctx) {
  root.classList.add('boards-page');
  const [status, projects] = await Promise.all([fetch('/integration-status').then(response => response.json()).catch(() => ({ available: false })), projectOptions()]);
  if (ctx.signal.aborted) return;
  root.append(pageHeading(t('Quadros'), t('Pense livremente. Escreva, conecte e mova suas ideias.'), el('a', { className: 'button secondary', href: '/notas-flutuantes/', target: '_blank', rel: 'noopener' }, icon('external'), t('Abrir em tela inteira'))));
  if (!status.available) { root.append(emptyState('boards', t('Conecte seu Notas Flutuantes'), t('A pasta compartilhada não foi encontrada. Execute npm run link:notes na pasta do Organizador. O projeto original precisa permanecer disponível.'))); return; }
  const projectSelect = select([{ value: '', label: t('Sem projeto') }, ...projects.map(project => ({ value: project.id, label: project.name }))], '', { 'aria-label': t('Projeto do quadro atual'), disabled: true });
  const state = el('span', { className: 'muted' }, t('Abrindo o quadro…'));
  const reload = button(t('Atualizar quadro'), async () => { if (await flush()) frame.contentWindow.location.reload(); }, { variant: 'text' });
  const frame = el('iframe', { className: 'notes-frame', src: '/notas-flutuantes/', title: t('Notas Flutuantes — quadro livre'), allow: 'fullscreen' });
  root.append(el('div', { className: 'board-context' }, el('div', {}, icon('projects'), el('label', { htmlFor: 'board-project' }, t('Projeto do quadro')), projectSelect), el('div', { className: 'board-status' }, state, reload)), frame);
  projectSelect.id = 'board-project';
  let boardSelect, observer, readyTimer, readyAttempts = 0, boardGeneration = 0;
  let requestedBoard = ctx.query.get('board');
  const requestedProject = ctx.query.get('project');
  async function flush() {
    if (!boardSelect || !frame.contentWindow?.flushBoardSave) return true;
    const saved = await frame.contentWindow.flushBoardSave(boardSelect.value);
    if (!saved) toast(t('O quadro não pôde ser salvo. Resolva o erro no Notas Flutuantes antes de sair.'), true);
    return saved;
  }
  ctx.setBeforeLeave(flush);
  async function boardChanged() {
    const run = ++boardGeneration;
    const board = boardSelect.value;
    const link = await get('boardLinks', board);
    if (ctx.signal.aborted || run !== boardGeneration) return;
    projectSelect.disabled = false;
    projectSelect.value = link?.projectId || '';
    state.textContent = status.mode === 'linked' ? t('Código ligado à pasta original') : t('Versão desta distribuição');
    if (requestedProject && !link) { projectSelect.value = requestedProject; state.textContent = t('Clique em Vincular para relacionar este quadro ao projeto.'); }
  }
  const linkButton = button(t('Vincular'), async () => {
    if (!boardSelect) return;
    await setBoardProject(boardSelect.value, boardSelect.selectedOptions[0]?.textContent || t('Quadro'), projectSelect.value || null);
    toast(projectSelect.value ? t('Quadro vinculado ao projeto.') : t('Vínculo removido.'));
    state.textContent = status.mode === 'linked' ? t('Código ligado à pasta original') : t('Versão desta distribuição');
  });
  projectSelect.after(linkButton);
  function whenReady() {
    if (ctx.signal.aborted) return;
    boardSelect = frame.contentDocument?.querySelector('#boardSelect');
    if (!boardSelect?.options.length) {
      if (++readyAttempts > 100) { state.textContent = t('O quadro não respondeu. Abra em tela inteira para verificar.'); return; }
      readyTimer = setTimeout(whenReady, 100); return;
    }
    if (requestedBoard) {
      if ([...boardSelect.options].some(option => option.value === requestedBoard)) {
        frame.contentWindow.switchBoard(requestedBoard).then(boardChanged).catch(ctx.error);
      } else toast(t('O quadro vinculado não existe neste navegador. Importe o backup original ou vincule outro quadro.'), true);
      requestedBoard = null;
    }
    boardSelect.addEventListener('change', boardChanged, { signal: ctx.signal });
    observer?.disconnect();
    observer = new MutationObserver(() => boardChanged().catch(ctx.error));
    observer.observe(boardSelect, { childList: true });
    frame.contentDocument.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); ctx.openSearch(); }
    }, { signal: ctx.signal });
    const dark = document.documentElement.dataset.theme === 'dark';
    if (frame.contentDocument.body.classList.contains('dark') !== dark) frame.contentDocument.querySelector('#darkMode')?.click();
    boardChanged().catch(ctx.error);
  }
  frame.addEventListener('load', () => { clearTimeout(readyTimer); readyAttempts = 0; whenReady(); }, { signal: ctx.signal });
  async function changedSource() {
    if (!ctx.signal.aborted && await flush()) { toast(t('Notas Flutuantes atualizado a partir do código compartilhado.')); frame.contentWindow.location.reload(); }
  }
  import.meta.hot?.on('notes-source-changed', changedSource);
  return () => { observer?.disconnect(); clearTimeout(readyTimer); import.meta.hot?.off('notes-source-changed', changedSource); };
}
