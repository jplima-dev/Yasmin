(() => {
  function create({ editor, collectDocument, templateDefaultStyle }) {
    const { escapeHtml, safeFilename } = InkWriteDocumentModel;

    function downloadBlob(blob, name) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
    }

    function getCleanEditorClone() {
      const clone = editor.cloneNode(true);
      clone.querySelectorAll('.selected-image,.selected-table-cell,.accessibility-focus').forEach(el => el.classList.remove('selected-image', 'selected-table-cell', 'accessibility-focus'));
      clone.querySelectorAll('[data-page-break-remove]').forEach(el => el.remove());
      clone.querySelectorAll('[contenteditable]').forEach(el => el.removeAttribute('contenteditable'));
      clone.removeAttribute('contenteditable');
      return clone;
    }

    function getExportCss(doc) {
      const accent = doc.settings.accent || '#2563eb';
      const pageColor = doc.settings.pageColor || '#ffffff';
      let templateCss = '';
      const template = doc.template || 'blank';
      const style = doc.settings.templateStyle || templateDefaultStyle(template);

      if (template === 'letter') {
        if (style === 'classic') templateCss += 'body{font-family:Georgia,serif}';
        if (style === 'modern') templateCss += `body{font-family:Arial,sans-serif;border-top:6px solid ${accent};padding-top:36px}`;
        if (style === 'minimal') templateCss += 'body{font-family:Arial,sans-serif}';
      }
      if (template === 'school') {
        if (style === 'academic') templateCss += 'body{font-family:"Times New Roman",serif}';
        if (style === 'clean') templateCss += 'body{font-family:Arial,sans-serif}';
        if (style === 'compact') templateCss += 'body{font-family:Arial,sans-serif;font-size:14px}';
      }
      if (template === 'notes') {
        if (style === 'ruled') templateCss += 'body{font-family:Arial,sans-serif;background-image:repeating-linear-gradient(to bottom,transparent 0,transparent 29px,rgba(80,110,160,.12) 30px);background-color:' + pageColor + '}';
        if (style === 'clean') templateCss += 'body{font-family:Arial,sans-serif}';
        if (style === 'compact') templateCss += 'body{font-family:Arial,sans-serif;font-size:14px}';
      }
      if (template === 'report') {
        if (style === 'business') templateCss += `body{font-family:Arial,sans-serif;border-top:6px solid ${accent};padding-top:34px}`;
        if (style === 'technical') templateCss += 'body{font-family:"Courier New",monospace}';
        if (style === 'minimal') templateCss += 'body{font-family:Arial,sans-serif}';
      }

      return `
        *{box-sizing:border-box}body{max-width:800px;margin:48px auto;padding:0 32px;line-height:${doc.settings.lineHeight};color:#111827;background-color:${pageColor};overflow-wrap:anywhere}
        p{margin-top:${doc.settings.paragraphBefore || 0}px;margin-bottom:${doc.settings.paragraphSpacing}px;text-indent:${doc.settings.firstLineIndent || 0}px}h1,h2,h3{line-height:1.18}h1{font-size:32px}h2{font-size:25px}h3{font-size:20px}h1 *,h2 *,h3 *{font-size:inherit!important}
        img{max-width:100%;height:auto}table{width:100%;max-width:100%;table-layout:fixed;border-collapse:collapse;margin:14px 0}th,td{min-width:0;padding:8px;border:1px solid #cfd7e5;vertical-align:top;overflow-wrap:anywhere;word-break:break-word}th{background:#f2f5fa}
        blockquote{border-left:4px solid ${accent};padding:10px 14px;background:#f7f9fc;color:#4b5563}pre{padding:12px;background:#111827;color:#fff;white-space:pre-wrap}
        .page-break{height:0;overflow:hidden;break-after:page;page-break-after:always}.page-break span{display:none}
        [data-keep-with-next="true"]{break-after:avoid;page-break-after:avoid}[data-keep-lines="true"]{break-inside:avoid;page-break-inside:avoid}[data-page-break-before="true"]{break-before:page;page-break-before:always}
        p,li,blockquote{orphans:2;widows:2}h1,h2,h3{break-after:avoid;page-break-after:avoid}thead{display:table-header-group}tr,img,figure,pre,blockquote{break-inside:avoid;page-break-inside:avoid}
        .ink-footnote-ref{font-size:.72em;vertical-align:super;line-height:0}.ink-footnotes{margin-top:32px;padding-top:12px;border-top:1px solid #d1d5db;font-size:.9em}.ink-footnotes ol{padding-left:22px}.ink-footnotes li{margin:6px 0}.ink-footnote-back{margin-left:6px;text-decoration:none;color:${accent}}
        .school-cover{min-height:760px;display:flex;flex-direction:column;text-align:center;justify-content:space-between}.school-cover-center{margin:auto 0}.letter-block{margin:18px 0}.letter-signature{margin-top:24px}
        .note-callout,.report-highlight{padding:14px 16px;border-left:4px solid ${accent};background:#f6f8fc;border-radius:6px}.note-date-divider{display:flex;align-items:center;gap:10px;color:#6b7280}.note-date-divider:before,.note-date-divider:after{content:"";height:1px;background:#d1d5db;flex:1}
        .report-status{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid #dbe2ee;border-radius:7px}.status-dot{width:8px;height:8px;border-radius:50%;background:${accent};display:inline-block}
        ${templateCss}`;
    }

    function headerFooterHtml(doc, mode = 'html') {
      const header = String(doc.settings.headerText || '').trim();
      const footer = String(doc.settings.footerText || '').trim();
      const numberStyle = doc.settings.pageNumberStyle || 'none';
      const title = escapeHtml(doc.title || '');
      const replaceTokens = value => escapeHtml(value).replace(/\{titulo\}/gi, title).replace(/\{data\}/gi, new Intl.DateTimeFormat('pt-BR').format(new Date()));
      if (mode === 'print') {
        const number = numberStyle === 'none' ? '' : `<span class="print-page-number ${numberStyle === 'page' ? 'with-label' : ''}"></span>`;
        return `${header ? `<div class="print-header">${replaceTokens(header)}</div>` : ''}${footer || number ? `<div class="print-footer"><span>${replaceTokens(footer)}</span>${number}</div>` : ''}`;
      }
      return `${header ? `<header class="export-header">${replaceTokens(header)}</header>` : ''}${footer ? `<footer class="export-footer">${replaceTokens(footer)}</footer>` : ''}`;
    }

    function exportHtml() {
      const doc = collectDocument();
      const content = getCleanEditorClone().innerHTML;
      const chrome = headerFooterHtml(doc, 'html');
      const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(doc.title)}</title><style>${getExportCss(doc)}.export-header,.export-footer{font-size:12px;color:#6b7280;padding:8px 0;border-color:#dbe2ea}.export-header{border-bottom:1px solid #dbe2ea;margin-bottom:24px}.export-footer{border-top:1px solid #dbe2ea;margin-top:24px}</style></head><body>${chrome}${content}</body></html>`;
      downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), `${safeFilename(doc.title)}.html`);
    }

    function exportWord() {
      const doc = collectDocument();
      const content = getCleanEditorClone().innerHTML;
      const chrome = headerFooterHtml(doc, 'html');
      const html = `<!doctype html><html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><title>${escapeHtml(doc.title)}</title><style>${getExportCss(doc)}@page{size:auto;margin:2cm}.export-header,.export-footer{font-size:10pt;color:#666;padding:6pt 0}.export-header{border-bottom:1px solid #ccc;margin-bottom:14pt}.export-footer{border-top:1px solid #ccc;margin-top:14pt}</style></head><body>${chrome}${content}</body></html>`;
      downloadBlob(new Blob(['\ufeff', html], { type: 'application/msword;charset=utf-8' }), `${safeFilename(doc.title)}.doc`);
    }

    async function exportDocx() {
      const doc = collectDocument();
      if (!window.InkWriteDocx?.build) throw new Error('Exportador DOCX indisponível.');
      const blob = InkWriteDocx.build({ editor: getCleanEditorClone(), document: doc });
      downloadBlob(blob, `${safeFilename(doc.title)}.docx`);
    }

    function plainTextFromEditor() {
      const clone = getCleanEditorClone();
      clone.querySelectorAll('.page-break').forEach(el => {
        const marker = document.createElement('div');
        marker.textContent = '\f';
        el.replaceWith(marker);
      });
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:-99999px;top:0;width:800px;white-space:normal';
      host.append(clone);
      document.body.append(host);
      const text = clone.innerText || '';
      host.remove();
      return text.replace(/\n{3,}/g, '\n\n').trimEnd();
    }

    function exportTxt() {
      const doc = collectDocument();
      downloadBlob(new Blob([plainTextFromEditor()], { type: 'text/plain;charset=utf-8' }), `${safeFilename(doc.title)}.txt`);
    }

    function nodeToMarkdown(node, depth = 0) {
      if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || '';
      if (node.nodeType !== Node.ELEMENT_NODE) return '';
      const tag = node.tagName.toLowerCase();
      if (node.classList?.contains('page-break')) return '\n\n<div style="page-break-after: always;"></div>\n\n';
      const children = () => [...node.childNodes].map(child => nodeToMarkdown(child, depth)).join('');
      if (tag === 'br') return '\n';
      if (tag === 'h1') return `# ${children().trim()}\n\n`;
      if (tag === 'h2') return `## ${children().trim()}\n\n`;
      if (tag === 'h3') return `### ${children().trim()}\n\n`;
      if (tag === 'p') return `${children().trimEnd()}\n\n`;
      if (tag === 'strong' || tag === 'b') return `**${children()}**`;
      if (tag === 'em' || tag === 'i') return `*${children()}*`;
      if (tag === 's' || tag === 'strike') return `~~${children()}~~`;
      if (tag === 'code' && node.parentElement?.tagName.toLowerCase() !== 'pre') return `\`${node.textContent}\``;
      if (tag === 'pre') return `\`\`\`\n${node.textContent}\n\`\`\`\n\n`;
      if (tag === 'blockquote') return `${node.textContent.split('\n').map(line => `> ${line}`).join('\n')}\n\n`;
      if (tag === 'a') return `[${children() || node.getAttribute('href')}](${node.getAttribute('href') || ''})`;
      if (tag === 'img') {
        const alt = node.getAttribute('alt') || 'imagem';
        const src = node.getAttribute('src') || '';
        return src.startsWith('data:') ? `*[Imagem incorporada: ${alt}]*` : `![${alt}](${src})`;
      }
      if (tag === 'hr') return '\n---\n\n';
      if (tag === 'ul' || tag === 'ol') {
        return [...node.children].map((li, i) => `${tag === 'ol' ? `${i + 1}.` : '-'} ${[...li.childNodes].map(ch => nodeToMarkdown(ch, depth + 1)).join('').trim()}\n`).join('') + '\n';
      }
      if (tag === 'li') return children();
      if (tag === 'table') {
        const rows = [...node.querySelectorAll('tr')].map(row => [...row.children].map(cell => cell.innerText.trim().replace(/\|/g, '\\|')));
        if (!rows.length) return '';
        const cols = Math.max(...rows.map(r => r.length));
        const normalized = rows.map(r => [...r, ...Array(Math.max(0, cols - r.length)).fill('')]);
        const first = `| ${normalized[0].join(' | ')} |\n| ${Array(cols).fill('---').join(' | ')} |\n`;
        const rest = normalized.slice(1).map(r => `| ${r.join(' | ')} |\n`).join('');
        return `${first}${rest}\n`;
      }
      if (['div', 'section', 'article'].includes(tag)) return `${children()}${children().endsWith('\n') ? '' : '\n'}`;
      return children();
    }

    function exportMarkdown() {
      const doc = collectDocument();
      const clone = getCleanEditorClone();
      const footnoteDefinitions = [];
      const footnoteSection = clone.querySelector('.ink-footnotes');
      if (footnoteSection) {
        const notes = new Map([...footnoteSection.querySelectorAll('li[data-footnote-id]')].map((li, index) => {
          const copy = li.cloneNode(true);
          copy.querySelectorAll('.ink-footnote-back').forEach(link => link.remove());
          const id = li.dataset.footnoteId || String(index + 1);
          return [id, { number: index + 1, text: (copy.innerText || copy.textContent || '').trim() }];
        }));
        clone.querySelectorAll('.ink-footnote-ref[data-footnote-id]').forEach((ref, index) => {
          const id = ref.dataset.footnoteId;
          const note = notes.get(id);
          const number = note?.number || index + 1;
          ref.replaceWith(document.createTextNode(`[^${number}]`));
        });
        [...notes.values()].forEach(note => footnoteDefinitions.push(`[^${note.number}]: ${note.text}`));
        footnoteSection.remove();
      }
      let md = [...clone.childNodes].map(node => nodeToMarkdown(node)).join('').replace(/\n{3,}/g, '\n\n').trimEnd();
      if (footnoteDefinitions.length) md += `\n\n${footnoteDefinitions.join('\n')}`;
      downloadBlob(new Blob([md], { type: 'text/markdown;charset=utf-8' }), `${safeFilename(doc.title)}.md`);
    }

    function rtfEscape(text) {
      let out = '';
      for (const char of text) {
        if (char === '\\' || char === '{' || char === '}') out += `\\${char}`;
        else if (char === '\n') out += '\\par\n';
        else if (char === '\t') out += '\\tab ';
        else if (char === '\f') out += '\\page\n';
        else {
          const code = char.charCodeAt(0);
          if (code > 127) out += `\\u${code > 32767 ? code - 65536 : code}?`;
          else out += char;
        }
      }
      return out;
    }

    function exportRtf() {
      const doc = collectDocument();
      const text = plainTextFromEditor();
      const rtf = `{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\viewkind4\\uc1\\f0\\fs24 ${rtfEscape(text)}}`;
      downloadBlob(new Blob([rtf], { type: 'application/rtf;charset=utf-8' }), `${safeFilename(doc.title)}.rtf`);
    }

    function openDialog() { document.querySelector('#exportDialog')?.showModal(); }
    function closeDialog() {
      const dialog = document.querySelector('#exportDialog');
      if (dialog?.open) dialog.close();
    }

    function printDocument() {
      const doc = collectDocument();
      const content = getCleanEditorClone().innerHTML;
      const paperGeometryMm = { a4: [210, 297], letter: [215.9, 279.4], a5: [148, 210] };
      const [portraitWidthMm, portraitHeightMm] = paperGeometryMm[doc.settings.paper] || paperGeometryMm.a4;
      const landscapeSource = doc.settings.orientation === 'landscape';
      const sourceWidthMm = landscapeSource ? portraitHeightMm : portraitWidthMm;
      const sourceHeightMm = landscapeSource ? portraitWidthMm : portraitHeightMm;
      const marginPixels = { narrow: 38, normal: 72, wide: 108, custom: Math.max(0, Number(doc.settings.customMargin) || 72) }[doc.settings.margin] ?? 72;
      const marginMm = Math.max(0, marginPixels * 25.4 / 96).toFixed(2);
      const hasHeader = !!String(doc.settings.headerText || '').trim();
      const hasFooter = !!String(doc.settings.footerText || '').trim() || doc.settings.pageNumberStyle !== 'none';
      const topPaddingMm = (Number(marginMm) + (hasHeader ? 8 : 0)).toFixed(2);
      const bottomPaddingMm = (Number(marginMm) + (hasFooter ? 8 : 0)).toFixed(2);
      const printChrome = headerFooterHtml(doc, 'print');
      const printCss = `${getExportCss(doc)}
        @page{size:${portraitWidthMm}mm ${portraitHeightMm}mm;margin:0}
        html{width:${portraitWidthMm}mm!important;min-width:${portraitWidthMm}mm!important;margin:0!important;padding:0!important;background:#fff!important}
        body{box-sizing:border-box!important;width:${sourceWidthMm}mm!important;min-width:${sourceWidthMm}mm!important;min-height:${sourceHeightMm}mm!important;max-width:none!important;margin:0!important;padding:${topPaddingMm}mm ${marginMm}mm ${bottomPaddingMm}mm!important;overflow:visible!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
        body.pdf-landscape-source{transform-origin:0 0!important;transform:translateX(${portraitWidthMm}mm) rotate(90deg)!important}
        img,svg,canvas{max-width:100%!important;height:auto}table{width:100%!important;max-width:100%!important;table-layout:fixed!important}th,td{min-width:0!important;overflow-wrap:anywhere!important;word-break:break-word!important}pre{max-width:100%!important;white-space:pre-wrap!important;overflow-wrap:anywhere!important}.page-break{break-after:page!important;page-break-after:always!important}.ink-footnote-back{display:none!important}
        [data-keep-with-next="true"]{break-after:avoid!important;page-break-after:avoid!important}[data-keep-lines="true"]{break-inside:avoid!important;page-break-inside:avoid!important}[data-page-break-before="true"]{break-before:page!important;page-break-before:always!important}
        .print-header,.print-footer{position:fixed!important;left:${marginMm}mm!important;right:${marginMm}mm!important;color:#667085!important;font:9pt/1.3 Arial,sans-serif!important;z-index:9999!important}.print-header{top:5mm!important;padding-bottom:2mm!important;border-bottom:.2mm solid #d0d5dd!important}.print-footer{bottom:5mm!important;padding-top:2mm!important;border-top:.2mm solid #d0d5dd!important;display:flex!important;justify-content:space-between!important;gap:8mm!important}.print-page-number::after{content:counter(page)}.print-page-number.with-label::before{content:"Página "}
        @media print{html,body{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}`;

      const printFrame = document.createElement('iframe');
      printFrame.setAttribute('aria-hidden', 'true');
      printFrame.style.cssText = 'position:fixed;right:100%;bottom:100%;width:1px;height:1px;border:0;visibility:hidden;';
      document.body.append(printFrame);
      const printDoc = printFrame.contentDocument || printFrame.contentWindow?.document;
      if (!printDoc) {
        printFrame.remove();
        alert('Não foi possível preparar o PDF neste navegador.');
        return;
      }
      const bodyClass = landscapeSource ? 'pdf-landscape-source' : 'pdf-portrait-source';
      printDoc.open();
      printDoc.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title></title><style>${printCss}</style></head><body class="${bodyClass}">${printChrome}${content}</body></html>`);
      printDoc.close();
      closeDialog();

      const runPrint = () => {
        const printWindow = printFrame.contentWindow;
        if (!printWindow) { printFrame.remove(); return; }
        const cleanup = () => setTimeout(() => printFrame.remove(), 0);
        printWindow.addEventListener('afterprint', cleanup, { once: true });
        printWindow.focus();
        printWindow.print();
        setTimeout(() => { if (printFrame.isConnected) printFrame.remove(); }, 60000);
      };
      const images = [...printDoc.images];
      if (!images.length || images.every(image => image.complete)) setTimeout(runPrint, 0);
      else {
        let pending = images.filter(image => !image.complete).length;
        const done = () => { pending -= 1; if (pending <= 0) setTimeout(runPrint, 0); };
        images.filter(image => !image.complete).forEach(image => {
          image.addEventListener('load', done, { once: true });
          image.addEventListener('error', done, { once: true });
        });
        setTimeout(() => { if (printFrame.isConnected) runPrint(); }, 2000);
      }
    }

    return { exportHtml, exportWord, exportDocx, exportTxt, exportMarkdown, exportRtf, printDocument, openDialog, closeDialog, getCleanEditorClone };
  }

  window.InkWriteExport = { create };
})();
