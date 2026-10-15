(() => {
  function parseColor(value) {
    const match = String(value || '').match(/rgba?\((\d+(?:\.\d+)?)[, ]+\s*(\d+(?:\.\d+)?)[, ]+\s*(\d+(?:\.\d+)?)(?:[, /]+\s*(\d+(?:\.\d+)?))?\)/i);
    if (!match) return null;
    return { r: +match[1], g: +match[2], b: +match[3], a: match[4] == null ? 1 : +match[4] };
  }

  function luminance({ r, g, b }) {
    const channel = value => {
      const v = value / 255;
      return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
    };
    return .2126 * channel(r) + .7152 * channel(g) + .0722 * channel(b);
  }

  function contrastRatio(a, b) {
    const la = luminance(a);
    const lb = luminance(b);
    return (Math.max(la, lb) + .05) / (Math.min(la, lb) + .05);
  }

  function effectiveBackground(node, fallback) {
    let current = node;
    while (current && current instanceof Element) {
      const color = parseColor(getComputedStyle(current).backgroundColor);
      if (color && color.a > .95) return color;
      current = current.parentElement;
    }
    return parseColor(fallback) || { r: 255, g: 255, b: 255, a: 1 };
  }

  function create({ root, page }) {
    let lastIssues = [];

    function scan() {
      const issues = [];
      const push = (severity, message, node, code) => issues.push({ severity, message, node, code });

      root.querySelectorAll('img').forEach(img => {
        if (!img.hasAttribute('alt') || !img.alt.trim()) push('error', 'Imagem sem texto alternativo.', img, 'image-alt');
      });

      let previousHeading = 0;
      root.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(heading => {
        const level = Number(heading.tagName.slice(1));
        if (previousHeading && level > previousHeading + 1) {
          push('warning', `Hierarquia de títulos pula de Título ${previousHeading} para Título ${level}.`, heading, 'heading-order');
        }
        previousHeading = level;
      });

      root.querySelectorAll('a').forEach(link => {
        const text = (link.textContent || '').trim();
        const href = (link.getAttribute('href') || '').trim();
        if (!text) push('error', 'Link sem texto descritivo.', link, 'link-empty');
        else if (/^(clique aqui|aqui|link|saiba mais|mais)$/i.test(text)) push('warning', `Link com texto pouco descritivo: “${text}”.`, link, 'link-generic');
        else if (href && (text === href || /^https?:\/\//i.test(text))) push('warning', 'Link usa o endereço como texto; prefira uma descrição do destino.', link, 'link-url-text');
      });

      root.querySelectorAll('table').forEach(table => {
        if (!table.querySelector('th')) push('warning', 'Tabela sem célula de cabeçalho.', table, 'table-header');
      });

      const text = (root.innerText || '').trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      if (words > 500 && !root.querySelector('h1')) push('warning', 'Documento longo sem Título 1.', root, 'missing-h1');

      const backgroundFallback = getComputedStyle(page).backgroundColor || '#fff';
      root.querySelectorAll('p,h1,h2,h3,li,blockquote,td,th,figcaption').forEach(element => {
        if (!(element.textContent || '').trim()) return;
        const style = getComputedStyle(element);
        const foreground = parseColor(style.color);
        const background = effectiveBackground(element, backgroundFallback);
        if (!foreground || foreground.a < .95 || !background) return;
        const ratio = contrastRatio(foreground, background);
        const fontSize = parseFloat(style.fontSize) || 16;
        const bold = Number(style.fontWeight) >= 700;
        const large = fontSize >= 24 || (bold && fontSize >= 18.66);
        const minimum = large ? 3 : 4.5;
        if (ratio < minimum) push('warning', `Contraste de texto baixo (${ratio.toFixed(1)}:1; recomendado ${minimum}:1).`, element, 'contrast');
      });

      lastIssues = issues;
      return issues;
    }

    function focusIssue(index) {
      const issue = lastIssues[index];
      const node = issue?.node;
      if (!node?.isConnected) return false;
      root.querySelectorAll('.accessibility-focus').forEach(el => el.classList.remove('accessibility-focus'));
      if (node instanceof Element && node !== root) node.classList.add('accessibility-focus');
      node.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      if (node instanceof HTMLElement) node.focus?.({ preventScroll: true });
      setTimeout(() => node.classList?.remove('accessibility-focus'), 2200);
      return true;
    }

    return { scan, focusIssue, getIssues: () => [...lastIssues] };
  }

  window.InkWriteAccessibility = { create };
})();
