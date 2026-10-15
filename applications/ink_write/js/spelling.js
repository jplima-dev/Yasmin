(() => {
  const KEY = 'inkwrite-local-dictionary-v1';
  const BASE = {
    'pt-BR': 'a agora ainda ao aos aqui as até bem cada com como da das de dela dele depois do dos e ela ele em entre era essa esse esta este eu foi há isso já mais mas me mesmo meu minha muito na não nas no nos nós o os ou para pela pelo por porque quando que quem se sem ser seu sua também tem ter um uma você trabalho texto documento página título imagem tabela nota rodapé sumário palavra palavras escola relatório carta dados projeto arquivo salvar editar inserir remover formato estilo revisão português brasil'.split(' '),
    'en-US': 'a about after all also an and are as at be because been but by can document edit file for from has have he her his how i if image in insert is it more not of on one or page remove report save she style table text that the their them then there these they this title to was we what when which who will with word you your'.split(' '),
    'es-ES': 'a ahora al algo como con de del documento el ella en es esta este guardar imagen la las los más no o página para palabra por que se sin su tabla texto título un una y yo'.split(' ')
  };

  function read() {
    try {
      const parsed = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch { return []; }
  }

  function distance(a, b) {
    a = a.toLowerCase(); b = b.toLowerCase();
    const row = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i += 1) {
      let prev = row[0]; row[0] = i;
      for (let j = 1; j <= b.length; j += 1) {
        const old = row[j];
        row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1));
        prev = old;
      }
    }
    return row[b.length];
  }

  function create({ editor, getLanguage, afterEdit }) {
    let custom = read();
    const save = () => localStorage.setItem(KEY, JSON.stringify(custom));
    const normalize = value => String(value || '').trim().toLocaleLowerCase(getLanguage?.() || 'pt-BR');

    function currentWord() {
      const selection = window.getSelection();
      if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return '';
      const selected = selection.toString().trim();
      if (selected && /^[\p{L}\p{M}'’-]+$/u.test(selected)) return selected;
      const node = selection.anchorNode;
      if (node?.nodeType !== Node.TEXT_NODE) return '';
      const text = node.nodeValue || '';
      const offset = selection.anchorOffset || 0;
      let start = offset, end = offset;
      while (start > 0 && /[\p{L}\p{M}'’-]/u.test(text[start - 1])) start -= 1;
      while (end < text.length && /[\p{L}\p{M}'’-]/u.test(text[end])) end += 1;
      return text.slice(start, end);
    }

    function currentWordRange() {
      const selection = window.getSelection();
      if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return null;
      const range = selection.getRangeAt(0);
      if (!range.collapsed && /^[\p{L}\p{M}'’-]+$/u.test(selection.toString().trim())) return range.cloneRange();
      const node = selection.anchorNode;
      if (node?.nodeType !== Node.TEXT_NODE) return null;
      const text = node.nodeValue || '';
      const offset = selection.anchorOffset || 0;
      let start = offset, end = offset;
      while (start > 0 && /[\p{L}\p{M}'’-]/u.test(text[start - 1])) start -= 1;
      while (end < text.length && /[\p{L}\p{M}'’-]/u.test(text[end])) end += 1;
      if (start === end) return null;
      const wordRange = document.createRange();
      wordRange.setStart(node, start);
      wordRange.setEnd(node, end);
      return wordRange;
    }

    function replaceCurrentWord(value) {
      const range = currentWordRange();
      if (!range) return false;
      const text = document.createTextNode(String(value || ''));
      range.deleteContents();
      range.insertNode(text);
      const caret = document.createRange();
      caret.setStartAfter(text);
      caret.collapse(true);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(caret);
      afterEdit?.('immediate');
      render();
      return true;
    }

    function isAccepted(word) {
      const value = normalize(word);
      if (!value) return false;
      const lang = getLanguage?.() || 'pt-BR';
      return custom.some(item => normalize(item) === value) || (BASE[lang] || []).some(item => normalize(item) === value);
    }

    function suggestions(word, limit = 5) {
      const value = normalize(word);
      if (!value) return [];
      const lang = getLanguage?.() || 'pt-BR';
      const pool = [...new Set([...(BASE[lang] || []), ...custom])];
      return pool
        .map(candidate => ({ candidate, score: distance(value, normalize(candidate)) }))
        .filter(item => item.score <= Math.max(2, Math.floor(value.length / 3)))
        .sort((a, b) => a.score - b.score || a.candidate.localeCompare(b.candidate, lang))
        .slice(0, limit)
        .map(item => item.candidate);
    }

    function add(word = currentWord()) {
      const clean = String(word || '').trim();
      if (!clean || !/^[\p{L}\p{M}'’-]+$/u.test(clean)) return false;
      if (!custom.some(item => normalize(item) === normalize(clean))) custom.push(clean);
      custom.sort((a, b) => a.localeCompare(b, getLanguage?.() || 'pt-BR'));
      save();
      render();
      return true;
    }

    function remove(word) {
      custom = custom.filter(item => normalize(item) !== normalize(word));
      save(); render();
    }

    function render() {
      const word = currentWord();
      const current = document.querySelector('#dictionaryCurrentWord');
      const status = document.querySelector('#dictionaryStatus');
      const list = document.querySelector('#dictionarySuggestions');
      const customList = document.querySelector('#dictionaryWords');
      if (current) current.textContent = word || '—';
      if (status) status.textContent = !word ? 'Selecione uma palavra ou posicione o cursor dentro dela.' : isAccepted(word) ? 'Palavra reconhecida pelo dicionário local.' : 'Não está no dicionário local. O navegador ainda faz a correção ortográfica principal.';
      if (list) {
        list.innerHTML = '';
        if (word && !isAccepted(word)) suggestions(word).forEach(value => {
          const button = document.createElement('button');
          button.type = 'button'; button.textContent = value; button.title = 'Substituir pela sugestão'; button.dataset.dictionarySuggestion = value;
          list.append(button);
        });
      }
      if (customList) {
        customList.innerHTML = '';
        custom.slice(0, 30).forEach(value => {
          const chip = document.createElement('button');
          chip.type = 'button'; chip.textContent = `${value} ×`; chip.dataset.dictionaryRemove = value;
          customList.append(chip);
        });
      }
    }

    document.querySelector('#dictionaryAdd')?.addEventListener('click', () => {
      const word = currentWord();
      if (!add(word)) alert('Selecione uma única palavra para adicioná-la ao dicionário local.');
    });
    document.querySelector('#dictionaryRefresh')?.addEventListener('click', render);
    document.querySelector('#dictionaryWords')?.addEventListener('click', event => {
      const button = event.target.closest('[data-dictionary-remove]');
      if (button) remove(button.dataset.dictionaryRemove);
    });
    document.querySelector('#dictionarySuggestions')?.addEventListener('click', event => {
      const button = event.target.closest('[data-dictionary-suggestion]');
      if (button) replaceCurrentWord(button.dataset.dictionarySuggestion);
    });
    let renderFrame = 0;
    document.addEventListener('selectionchange', () => {
      const selection = window.getSelection();
      if (!selection?.anchorNode || !editor.contains(selection.anchorNode) || renderFrame) return;
      renderFrame = requestAnimationFrame(() => { renderFrame = 0; render(); });
    });

    render();
    return { currentWord, currentWordRange, replaceCurrentWord, isAccepted, suggestions, add, remove, render, words: () => [...custom] };
  }

  window.InkWriteSpelling = { create };
})();
