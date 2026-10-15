(() => {
  const BLOCKED_ELEMENTS = 'script,iframe,object,embed,link,meta,base,form,input,button,textarea,select,option,noscript';
  const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:', 'blob:']);
  const URL_ATTRS = new Set(['href', 'src', 'poster', 'cite']);
  const SAFE_STYLE_PROPERTIES = new Set([
    'color', 'background-color',
    'font-family', 'font-size', 'font-weight', 'font-style',
    'text-decoration', 'text-decoration-line', 'text-align', 'text-indent',
    'line-height', 'letter-spacing', 'vertical-align', 'white-space',
    'margin-left', 'margin-right', 'margin-top', 'margin-bottom',
    'padding-left', 'padding-right',
    'width', 'max-width', 'min-width', 'height', 'max-height',
    'border', 'border-width', 'border-style', 'border-color', 'border-radius',
    'list-style-type'
  ]);

  function escapeHtml(value = '') {
    const div = document.createElement('div');
    div.textContent = String(value ?? '');
    return div.innerHTML;
  }

  function safeFilename(value = 'documento') {
    return (String(value || 'documento')).replace(/[\\/:*?"<>|]+/g, '-').trim() || 'documento';
  }

  function safeUrl(raw, attributeName = 'href') {
    const value = String(raw || '').trim();
    if (!value) return '';
    if (value.startsWith('#')) return value;
    if (/^data:/i.test(value)) {
      return attributeName === 'src' && /^data:image\/(?:png|jpe?g|gif|webp);base64,/i.test(value) ? value : '';
    }
    try {
      const parsed = new URL(value, location.href);
      return SAFE_PROTOCOLS.has(parsed.protocol) ? value : '';
    } catch {
      return '';
    }
  }

  function sanitizeStyle(styleText = '') {
    const text = String(styleText || '');
    if (!text || /url\s*\(|expression\s*\(|behavior\s*:|-moz-binding|@import/i.test(text)) return '';
    const probe = document.createElement('span');
    probe.style.cssText = text;
    const clean = [];
    for (let index = 0; index < probe.style.length; index += 1) {
      const property = probe.style[index].toLowerCase();
      if (!SAFE_STYLE_PROPERTIES.has(property) && !property.startsWith('--inkwrite-')) continue;
      const value = probe.style.getPropertyValue(property).trim();
      const priority = probe.style.getPropertyPriority(property);
      if (!value || /url\s*\(|expression\s*\(|javascript:/i.test(value)) continue;
      clean.push(`${property}:${value}${priority ? ' !important' : ''}`);
    }
    return clean.join(';');
  }

  function cleanElementAttributes(el, { keepClasses = true } = {}) {
    [...el.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value;
      if (name.startsWith('on') || name === 'srcdoc' || name === 'formaction' || name === 'nonce') {
        el.removeAttribute(attr.name);
        return;
      }
      if (name === 'style') {
        const clean = sanitizeStyle(value);
        if (clean) el.setAttribute('style', clean);
        else el.removeAttribute('style');
        return;
      }
      if (URL_ATTRS.has(name)) {
        const clean = safeUrl(value, name);
        if (clean) el.setAttribute(attr.name, clean);
        else el.removeAttribute(attr.name);
        return;
      }
      if (name === 'srcset' || name === 'integrity' || name === 'crossorigin') {
        el.removeAttribute(attr.name);
        return;
      }
      if (!keepClasses && name === 'class') el.removeAttribute('class');
    });
    if (el.tagName === 'A' && el.getAttribute('target') === '_blank') {
      el.setAttribute('rel', 'noopener noreferrer');
    }
  }

  function cleanupPastedMarkup(root, { mergeFormatting = false } = {}) {
    root.querySelectorAll('xml,style,title').forEach(el => el.remove());
    const all = [...root.querySelectorAll('*')];
    all.forEach(el => {
      cleanElementAttributes(el, { keepClasses: false });
      if (mergeFormatting) {
        el.removeAttribute('style');
        if (['FONT', 'SPAN'].includes(el.tagName)) el.replaceWith(...el.childNodes);
      } else if (el.tagName === 'FONT') {
        const span = document.createElement('span');
        const color = safeCssColor(el.getAttribute('color'));
        const face = el.getAttribute('face');
        if (color) span.style.color = color;
        if (face) span.style.fontFamily = face;
        span.append(...el.childNodes);
        el.replaceWith(span);
      }
    });

    root.querySelectorAll('span').forEach(span => {
      if (!span.attributes.length) span.replaceWith(...span.childNodes);
    });
    root.querySelectorAll('p').forEach(p => {
      const className = p.getAttribute('class') || '';
      if (/Mso/i.test(className)) p.removeAttribute('class');
    });
    return root;
  }

  function safeCssColor(value = '') {
    const probe = document.createElement('span');
    probe.style.color = '';
    probe.style.color = String(value || '');
    return probe.style.color || '';
  }

  function sanitizeImportedBody(doc, options = {}) {
    if (!doc?.body) return '';
    doc.querySelectorAll(BLOCKED_ELEMENTS).forEach(el => el.remove());
    doc.body.querySelectorAll('*').forEach(el => cleanElementAttributes(el, { keepClasses: options.keepClasses !== false }));
    if (options.paste) cleanupPastedMarkup(doc.body, { mergeFormatting: !!options.mergeFormatting });
    return doc.body.innerHTML || '';
  }

  function sanitizeHtml(html = '', options = {}) {
    const doc = new DOMParser().parseFromString(`<body>${String(html || '')}</body>`, 'text/html');
    return sanitizeImportedBody(doc, options);
  }

  function serializeEditor(root) {
    const clone = root.cloneNode(true);
    clone.querySelectorAll('.selected-image,.selected-table-cell,.accessibility-focus').forEach(el => el.classList.remove('selected-image', 'selected-table-cell', 'accessibility-focus'));
    clone.querySelectorAll('[data-transient]').forEach(el => el.remove());
    return clone.innerHTML;
  }

  function plainTextFromHtml(html = '') {
    const doc = new DOMParser().parseFromString(`<body>${String(html || '')}</body>`, 'text/html');
    return (doc.body.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function blockType(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return 'unknown';
    const tag = el.tagName.toLowerCase();
    if (/^h[1-6]$/.test(tag)) return 'heading';
    if (tag === 'p') return el.classList.contains('ink-caption') ? 'caption' : 'paragraph';
    if (tag === 'blockquote') return 'quote';
    if (tag === 'pre') return 'code';
    if (tag === 'ul' || tag === 'ol') return 'list';
    if (tag === 'table') return 'table';
    if (tag === 'img' || (tag === 'figure' && el.querySelector('img'))) return 'image';
    if (tag === 'hr') return 'divider';
    if (el.classList.contains('page-break')) return 'page-break';
    if (el.classList.contains('ink-toc')) return 'toc';
    if (el.classList.contains('ink-footnotes')) return 'footnotes';
    return 'container';
  }

  function semanticAttributes(el) {
    const attrs = {};
    [...el.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      if (name === 'style' || name === 'class' || name === 'data-transient') return;
      if (name.startsWith('on') || name === 'srcdoc' || name === 'nonce') return;
      if (URL_ATTRS.has(name)) {
        const clean = safeUrl(attr.value, name);
        if (clean) attrs[name] = clean;
        return;
      }
      if (name === 'srcset' || name === 'integrity' || name === 'crossorigin') return;
      attrs[name] = attr.value;
    });
    return attrs;
  }

  function nodeToSemantic(node) {
    if (node.nodeType === Node.TEXT_NODE) return { kind: 'text', text: node.nodeValue || '' };
    if (node.nodeType !== Node.ELEMENT_NODE) return null;
    if (node.matches?.('[data-transient],script,iframe,object,embed,link,meta,base,form,input,button,textarea,select,option,noscript')) return null;
    const style = sanitizeStyle(node.getAttribute('style') || '');
    const classes = [...node.classList].filter(name => !['selected-image','selected-table-cell','accessibility-focus'].includes(name));
    return {
      kind: 'element',
      tag: node.tagName.toLowerCase(),
      role: blockType(node),
      attrs: semanticAttributes(node),
      classes,
      presentation: style ? { style } : {},
      children: [...node.childNodes].map(nodeToSemantic).filter(Boolean)
    };
  }

  function createSemanticSnapshot(root) {
    return {
      schemaVersion: 2,
      format: 'inkwrite-dom-tree',
      blocks: [...root.childNodes].map(nodeToSemantic).filter(Boolean)
    };
  }

  function isSemanticSnapshot(value) {
    return !!value && [1, 2].includes(value.schemaVersion) && Array.isArray(value.blocks);
  }

  function renderSemanticNode(node) {
    if (!node) return '';
    if (node.kind === 'text') return escapeHtml(node.text || '');
    if (node.kind !== 'element' || !/^[a-z][a-z0-9-]*$/.test(node.tag || '')) return '';
    const tag = node.tag.toLowerCase();
    if (BLOCKED_ELEMENTS.split(',').includes(tag)) return '';
    const attrs = [];
    Object.entries(node.attrs || {}).forEach(([name, raw]) => {
      if (!/^[a-z_:][a-z0-9_:.-]*$/i.test(name) || name.startsWith('on')) return;
      let value = String(raw ?? '');
      if (URL_ATTRS.has(name)) value = safeUrl(value, name);
      if (!value && URL_ATTRS.has(name)) return;
      attrs.push(`${name}="${escapeHtml(value)}"`);
    });
    const classes = Array.isArray(node.classes) ? node.classes.filter(name => /^[a-z0-9_-]+$/i.test(name)) : [];
    if (classes.length) attrs.push(`class="${escapeHtml(classes.join(' '))}"`);
    const style = sanitizeStyle(node.presentation?.style || '');
    if (style) attrs.push(`style="${escapeHtml(style)}"`);
    const voidTags = new Set(['br','hr','img']);
    const open = `<${tag}${attrs.length ? ` ${attrs.join(' ')}` : ''}>`;
    if (voidTags.has(tag)) return open;
    return `${open}${(node.children || []).map(renderSemanticNode).join('')}</${tag}>`;
  }

  function semanticToHtml(snapshot) {
    if (!isSemanticSnapshot(snapshot)) return '';
    if (snapshot.schemaVersion === 1) {
      return snapshot.blocks.map(block => typeof block?.html === 'string' ? block.html : '').join('');
    }
    return snapshot.blocks.map(renderSemanticNode).join('');
  }

  function resolveDocumentHtml(doc = {}) {
    if (isSemanticSnapshot(doc.semantic)) {
      const semanticHtml = semanticToHtml(doc.semantic);
      if (semanticHtml || doc.semantic.blocks.length === 0) return semanticHtml;
    }
    return typeof doc.content === 'string' ? doc.content : '';
  }

  window.InkWriteDocumentModel = {
    format: 'semantic-v2+html-fallback-v1',
    escapeHtml,
    safeFilename,
    safeUrl,
    safeCssColor,
    sanitizeStyle,
    sanitizeImportedBody,
    sanitizeHtml,
    serializeEditor,
    plainTextFromHtml,
    createSemanticSnapshot,
    isSemanticSnapshot,
    semanticToHtml,
    resolveDocumentHtml
  };
})();
