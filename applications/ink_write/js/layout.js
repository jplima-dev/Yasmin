(() => {
  const TOOLBAR_KEY = 'inkwrite-toolbar-groups-v1';

  function create({ editor, page, canvas, getPageMetrics, getPageCount, getCurrentPage, onMarginChange, getActiveBlock, afterEdit }) {
    const vertical = document.querySelector('#verticalRuler');
    const topMarker = document.querySelector('#verticalMarginTop');
    const bottomMarker = document.querySelector('#verticalMarginBottom');
    const navigator = document.querySelector('#pageNavigator');
    const navigatorCount = document.querySelector('#pageNavigatorCount');

    function zoom() {
      return Math.max(.5, Math.min(1.5, (+document.querySelector('#zoomRange')?.value || 100) / 100));
    }

    function updateVerticalRuler() {
      if (!vertical) return;
      const { height, padding } = getPageMetrics();
      const scale = zoom();
      vertical.style.height = `${height * scale}px`;
      if (topMarker) topMarker.style.top = `${padding * scale}px`;
      if (bottomMarker) bottomMarker.style.top = `${(height - padding) * scale}px`;
    }

    function bindVerticalMarker(marker, side) {
      if (!marker) return;
      marker.addEventListener('pointerdown', event => {
        event.preventDefault();
        marker.setPointerCapture?.(event.pointerId);
        const move = e => {
          const rect = vertical.getBoundingClientRect();
          const { height } = getPageMetrics();
          const value = side === 'top'
            ? (e.clientY - rect.top) / zoom()
            : height - ((e.clientY - rect.top) / zoom());
          const margin = Math.round(Math.max(8, Math.min(180, value)));
          onMarginChange(margin, false);
          updateVerticalRuler();
        };
        const up = e => {
          marker.releasePointerCapture?.(e.pointerId);
          marker.removeEventListener('pointermove', move);
          marker.removeEventListener('pointerup', up);
          marker.removeEventListener('pointercancel', up);
          afterEdit(true);
        };
        marker.addEventListener('pointermove', move);
        marker.addEventListener('pointerup', up);
        marker.addEventListener('pointercancel', up);
      });
    }

    function renderPageNavigator() {
      if (!navigator) return;
      const count = Math.max(1, Math.min(200, getPageCount()));
      const current = Math.max(1, Math.min(count, getCurrentPage(count)));
      if (navigatorCount) navigatorCount.textContent = String(count);
      const existing = [...navigator.children];
      if (existing.length !== count) {
        navigator.innerHTML = '';
        for (let i = 1; i <= count; i += 1) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'page-nav-button';
          button.dataset.page = String(i);
          button.textContent = String(i);
          button.title = `Ir para a página ${i}`;
          navigator.append(button);
        }
      }
      [...navigator.children].forEach(button => button.classList.toggle('active', +button.dataset.page === current));
    }

    navigator?.addEventListener('click', event => {
      const button = event.target.closest('[data-page]');
      if (!button || !canvas) return;
      const targetPage = Math.max(1, +button.dataset.page || 1);
      const { height } = getPageMetrics();
      const top = Math.max(0, (targetPage - 1) * height * zoom());
      canvas.scrollTo({ top, behavior: 'smooth' });
    });

    function syncBlockFlow() {
      const block = getActiveBlock();
      const map = [
        ['#keepWithNext', 'keepWithNext'],
        ['#keepLinesTogether', 'keepLines'],
        ['#pageBreakBefore', 'pageBreakBefore']
      ];
      map.forEach(([selector, key]) => {
        const input = document.querySelector(selector);
        if (!input) return;
        input.disabled = !block;
        input.checked = !!block && block.dataset[key] === 'true';
      });
    }

    function bindBlockControl(selector, key) {
      document.querySelector(selector)?.addEventListener('change', event => {
        const block = getActiveBlock();
        if (!block) return;
        if (event.target.checked) block.dataset[key] = 'true';
        else delete block.dataset[key];
        afterEdit('immediate');
        syncBlockFlow();
      });
    }
    bindBlockControl('#keepWithNext', 'keepWithNext');
    bindBlockControl('#keepLinesTogether', 'keepLines');
    bindBlockControl('#pageBreakBefore', 'pageBreakBefore');

    function setupToolbarGroups() {
      let saved = {};
      try { saved = JSON.parse(localStorage.getItem(TOOLBAR_KEY) || '{}') || {}; } catch {}
      document.querySelectorAll('.toolbar .tool-group').forEach((group, index) => {
        const key = group.dataset.groupLabel || `group-${index}`;
        if (group.querySelector('.tool-group-collapse')) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'tool-group-collapse';
        button.textContent = '•••';
        button.title = `Recolher/expandir ${key}`;
        button.setAttribute('aria-label', button.title);
        button.addEventListener('click', () => {
          const collapsed = group.classList.toggle('group-collapsed');
          saved[key] = collapsed;
          localStorage.setItem(TOOLBAR_KEY, JSON.stringify(saved));
        });
        group.append(button);
        group.classList.toggle('group-collapsed', !!saved[key]);
      });
    }

    function update() {
      updateVerticalRuler();
      renderPageNavigator();
      syncBlockFlow();
    }

    bindVerticalMarker(topMarker, 'top');
    bindVerticalMarker(bottomMarker, 'bottom');
    setupToolbarGroups();
    let selectionFrame = 0;
    let scrollFrame = 0;
    let resizeFrame = 0;
    document.addEventListener('selectionchange', () => {
      const selection = window.getSelection();
      if (!selection?.anchorNode || !editor.contains(selection.anchorNode) || selectionFrame) return;
      selectionFrame = requestAnimationFrame(() => {
        selectionFrame = 0;
        renderPageNavigator();
        syncBlockFlow();
      });
    });
    canvas?.addEventListener('scroll', () => {
      if (scrollFrame) return;
      scrollFrame = requestAnimationFrame(() => { scrollFrame = 0; renderPageNavigator(); });
    }, { passive: true });
    window.addEventListener('resize', () => {
      if (resizeFrame) cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => { resizeFrame = 0; update(); });
    });

    return { update, updateVerticalRuler, renderPageNavigator, syncBlockFlow, setupToolbarGroups };
  }

  window.InkWriteLayout = { create };
})();
