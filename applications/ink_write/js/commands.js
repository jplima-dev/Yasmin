(() => {
  const FORMAT_CARET_ATTR = 'data-ink-format-caret';
  const ZWSP = '\u200B';

  function create({ root, selection, afterEdit }) {
    const handlers = new Map();
    const beforeInputHandlers = new Map();

    function register(name, handler) {
      if (typeof handler !== 'function') throw new TypeError('Command handler must be a function');
      handlers.set(name, handler);
    }

    function registerBeforeInput(inputType, handler) {
      if (typeof handler !== 'function') throw new TypeError('beforeinput handler must be a function');
      beforeInputHandlers.set(inputType, handler);
    }

    function currentRange({ restore = true } = {}) {
      if (restore) selection.restore();
      const nativeSelection = window.getSelection();
      if (!nativeSelection?.rangeCount || !selection.selectionInsideRoot(nativeSelection)) return null;
      return nativeSelection.getRangeAt(0);
    }

    function selectRange(range) {
      const nativeSelection = window.getSelection();
      if (!nativeSelection || !range) return false;
      nativeSelection.removeAllRanges();
      nativeSelection.addRange(range);
      selection.setRange(range);
      return true;
    }

    function placeCaretAfter(node) {
      if (!node?.parentNode) return false;
      const range = document.createRange();
      range.setStartAfter(node);
      range.collapse(true);
      return selectRange(range);
    }

    function insertCaretWrapper(tagName, attributes = {}) {
      let range = currentRange();
      if (!range) {
        range = document.createRange();
        range.selectNodeContents(root);
        range.collapse(false);
      }
      range.deleteContents();
      const wrapper = document.createElement(tagName);
      Object.entries(attributes).forEach(([name, value]) => {
        if (name === 'style' && value && typeof value === 'object') Object.assign(wrapper.style, value);
        else if (value != null) wrapper.setAttribute(name, String(value));
      });
      wrapper.setAttribute(FORMAT_CARET_ATTR, '1');
      const marker = document.createTextNode(ZWSP);
      wrapper.append(marker);
      range.insertNode(wrapper);
      const next = document.createRange();
      next.setStart(marker, 0);
      next.collapse(true);
      selectRange(next);
      afterEdit(true);
      return true;
    }

    function cleanupMarkers() {
      root.querySelectorAll(`[${FORMAT_CARET_ATTR}]`).forEach(wrapper => {
        const textNodes = [];
        const walker = document.createTreeWalker(wrapper, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) textNodes.push(walker.currentNode);
        textNodes.forEach(node => {
          if (node.nodeValue?.includes(ZWSP)) node.nodeValue = node.nodeValue.replaceAll(ZWSP, '');
        });
        wrapper.removeAttribute(FORMAT_CARET_ATTR);
        if (!wrapper.textContent && !wrapper.querySelector('br,img')) wrapper.remove();
      });
    }

    function insertText(text = '') {
      root.focus();
      let range = currentRange();
      if (!range) {
        range = document.createRange();
        range.selectNodeContents(root);
        range.collapse(false);
      }
      range.deleteContents();
      const node = document.createTextNode(String(text));
      range.insertNode(node);
      placeCaretAfter(node);
      afterEdit(true);
      return true;
    }

    function insertHtml(html = '') {
      root.focus();
      let range = currentRange();
      if (!range) {
        range = document.createRange();
        range.selectNodeContents(root);
        range.collapse(false);
      }
      range.deleteContents();
      const fragment = range.createContextualFragment(String(html || ''));
      const inserted = [...fragment.childNodes];
      range.insertNode(fragment);
      if (inserted.length) {
        const next = document.createRange();
        next.setStartBefore(inserted[0]);
        next.setEndAfter(inserted[inserted.length - 1]);
        selectRange(next);
      } else selection.save();
      afterEdit(true);
      return true;
    }

    function closestTag(node, tagName) {
      const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
      const match = element?.closest?.(tagName);
      return match && root.contains(match) ? match : null;
    }

    function unwrapMatching(container, selector) {
      [...container.querySelectorAll(selector)].reverse().forEach(el => el.replaceWith(...el.childNodes));
      if (container.nodeType === Node.ELEMENT_NODE && container.matches?.(selector)) {
        const frag = document.createDocumentFragment();
        frag.append(...container.childNodes);
        return frag;
      }
      return container;
    }

    function insertFragmentAndSelect(range, fragment) {
      const nodes = [...fragment.childNodes];
      range.insertNode(fragment);
      if (!nodes.length) return false;
      const next = document.createRange();
      next.setStartBefore(nodes[0]);
      next.setEndAfter(nodes[nodes.length - 1]);
      selectRange(next);
      return true;
    }

    function wrapSelection(tagName, attributes = {}) {
      const range = currentRange();
      if (!range) return false;
      if (range.collapsed) return insertCaretWrapper(tagName, attributes);
      const wrapper = document.createElement(tagName);
      Object.entries(attributes).forEach(([name, value]) => {
        if (name === 'style' && value && typeof value === 'object') Object.assign(wrapper.style, value);
        else if (value != null) wrapper.setAttribute(name, String(value));
      });
      wrapper.append(range.extractContents());
      range.insertNode(wrapper);
      const next = document.createRange();
      next.selectNodeContents(wrapper);
      selectRange(next);
      afterEdit(true);
      return true;
    }

    function toggleInline(tagName) {
      root.focus();
      const range = currentRange();
      if (!range) return false;
      const startMatch = closestTag(range.startContainer, tagName);
      const endMatch = closestTag(range.endContainer, tagName);
      const active = !!startMatch && (!!endMatch || range.collapsed);

      if (range.collapsed) {
        if (active) {
          const next = document.createRange();
          next.setStartAfter(startMatch);
          next.collapse(true);
          selectRange(next);
          afterEdit(true);
          return true;
        }
        return insertCaretWrapper(tagName);
      }

      if (!active) return wrapSelection(tagName);

      const fragment = range.extractContents();
      const cleaned = unwrapMatching(fragment, tagName);
      insertFragmentAndSelect(range, cleaned);
      afterEdit(true);
      return true;
    }

    function registerInline(name, tagName) {
      register(name, () => toggleInline(tagName));
    }

    function execute(name, value = null, context = {}) {
      const handler = handlers.get(name);
      if (!handler) return false;
      return handler({ name, value, context, root, selection, currentRange, selectRange, insertText, insertHtml, wrapSelection, toggleInline, cleanupMarkers });
    }

    function handleBeforeInput(event) {
      const handler = beforeInputHandlers.get(event.inputType);
      if (!handler) return false;
      event.preventDefault();
      handler(event);
      return true;
    }

    return {
      execute,
      register,
      registerInline,
      registerBeforeInput,
      handleBeforeInput,
      insertText,
      insertHtml,
      currentRange,
      selectRange,
      wrapSelection,
      toggleInline,
      cleanupMarkers,
      has: name => handlers.has(name)
    };
  }

  window.InkWriteCommands = { create };
})();
