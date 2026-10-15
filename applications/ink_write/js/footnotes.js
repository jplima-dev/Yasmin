(() => {
  function create({ editor, selection, insertHtml, afterEdit }) {
    let draftRange = null;

    const makeId = () => `fn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    const escapeSelector = value => window.CSS?.escape ? CSS.escape(value) : String(value).replace(/[^a-zA-Z0-9_-]/g, ch => `\${ch}`);

    function section() {
      let host = editor.querySelector(':scope > .ink-footnotes');
      if (!host) {
        host = document.createElement('section');
        host.className = 'ink-footnotes';
        host.setAttribute('aria-label', 'Notas de rodapé');
        host.innerHTML = '<hr><h2>Notas</h2><ol></ol>';
        editor.append(host);
      }
      return host;
    }

    function renumber() {
      const refs = [...editor.querySelectorAll('sup.ink-footnote-ref[data-footnote-id]')];
      const used = [];
      refs.forEach(ref => {
        const id = ref.dataset.footnoteId;
        if (id && !used.includes(id)) used.push(id);
        const number = used.indexOf(id) + 1;
        ref.dataset.footnoteNumber = String(number);
        let link = ref.querySelector('a');
        if (!link) {
          link = document.createElement('a');
          ref.replaceChildren(link);
        }
        link.href = `#footnote-${id}`;
        link.textContent = String(number);
        link.setAttribute('aria-label', `Nota de rodapé ${number}`);
      });

      const host = editor.querySelector(':scope > .ink-footnotes');
      if (!host) return refs.length;
      const list = host.querySelector('ol') || host.appendChild(document.createElement('ol'));
      [...list.querySelectorAll('li[data-footnote-id]')].forEach(li => {
        if (!used.includes(li.dataset.footnoteId)) li.remove();
      });
      used.forEach((id, index) => {
        let li = list.querySelector(`li[data-footnote-id="${escapeSelector(id)}"]`);
        if (!li) {
          li = document.createElement('li');
          li.dataset.footnoteId = id;
          li.innerHTML = '<span class="footnote-text"><br></span> <a class="footnote-back" href="#" contenteditable="false">↩</a>';
          list.append(li);
        }
        li.id = `footnote-${id}`;
        li.dataset.footnoteNumber = String(index + 1);
        const back = li.querySelector('.footnote-back');
        if (back) {
          back.href = `#footnote-ref-${id}`;
          back.setAttribute('aria-label', `Voltar à chamada da nota ${index + 1}`);
        }
        const ref = refs.find(item => item.dataset.footnoteId === id);
        if (ref) ref.id = `footnote-ref-${id}`;
        list.append(li);
      });
      if (!used.length) host.remove();
      return refs.length;
    }

    function openDialog() {
      selection.save();
      draftRange = selection.getRange?.() || null;
      const dialog = document.querySelector('#footnoteDialog');
      const input = document.querySelector('#footnoteText');
      if (!dialog || !input) return;
      input.value = '';
      dialog.showModal();
      setTimeout(() => input.focus(), 0);
    }

    function closeDialog() {
      const dialog = document.querySelector('#footnoteDialog');
      if (dialog?.open) dialog.close('cancel');
      draftRange = null;
    }

    function insert(text) {
      const clean = String(text || '').trim();
      if (!clean) return false;
      if (draftRange) selection.setRange(draftRange);
      selection.restore();
      const id = makeId();
      insertHtml(`<sup class="ink-footnote-ref" id="footnote-ref-${id}" data-footnote-id="${id}" contenteditable="false"><a href="#footnote-${id}" aria-label="Nota de rodapé">?</a></sup>`);
      const host = section();
      const list = host.querySelector('ol');
      const li = document.createElement('li');
      li.id = `footnote-${id}`;
      li.dataset.footnoteId = id;
      const span = document.createElement('span');
      span.className = 'footnote-text';
      span.textContent = clean;
      const back = document.createElement('a');
      back.className = 'footnote-back';
      back.href = `#footnote-ref-${id}`;
      back.contentEditable = 'false';
      back.textContent = '↩';
      li.append(span, document.createTextNode(' '), back);
      list.append(li);
      renumber();
      afterEdit('immediate');
      draftRange = null;
      return true;
    }

    function bindDialog() {
      const dialog = document.querySelector('#footnoteDialog');
      const form = document.querySelector('#footnoteForm');
      if (!dialog || !form || form.dataset.bound === '1') return;
      form.dataset.bound = '1';
      dialog.querySelectorAll('[data-footnote-close]').forEach(button => button.addEventListener('click', closeDialog));
      form.addEventListener('submit', event => {
        event.preventDefault();
        const text = document.querySelector('#footnoteText')?.value || '';
        if (!text.trim()) return document.querySelector('#footnoteText')?.focus();
        dialog.close('default');
        insert(text);
      });
      editor.addEventListener('click', event => {
        const back = event.target.closest('.footnote-back');
        if (!back) return;
        const target = editor.querySelector(back.getAttribute('href'));
        if (target) {
          event.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    }

    bindDialog();
    return { openDialog, closeDialog, insert, renumber };
  }

  window.InkWriteFootnotes = { create };
})();
