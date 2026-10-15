(() => {
  const encoder = new TextEncoder();

  function xml(value = '') {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');
  }

  function utf8(value) { return encoder.encode(String(value)); }

  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  function u16(value) {
    const out = new Uint8Array(2);
    new DataView(out.buffer).setUint16(0, value, true);
    return out;
  }
  function u32(value) {
    const out = new Uint8Array(4);
    new DataView(out.buffer).setUint32(0, value >>> 0, true);
    return out;
  }
  function concat(parts) {
    const length = parts.reduce((sum, part) => sum + part.length, 0);
    const out = new Uint8Array(length);
    let offset = 0;
    parts.forEach(part => { out.set(part, offset); offset += part.length; });
    return out;
  }
  function dosDateTime(date = new Date()) {
    const year = Math.max(1980, date.getFullYear());
    const time = (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
    const day = (year - 1980) << 9 | ((date.getMonth() + 1) << 5) | date.getDate();
    return { time, date: day };
  }

  function zipStore(files) {
    const localParts = [];
    const centralParts = [];
    let offset = 0;
    const { time, date } = dosDateTime();

    files.forEach(file => {
      const name = utf8(file.name);
      const data = file.data instanceof Uint8Array ? file.data : utf8(file.data);
      const crc = crc32(data);
      const local = concat([
        u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(time), u16(date),
        u32(crc), u32(data.length), u32(data.length), u16(name.length), u16(0), name, data
      ]);
      localParts.push(local);

      const central = concat([
        u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(time), u16(date),
        u32(crc), u32(data.length), u32(data.length), u16(name.length), u16(0), u16(0),
        u16(0), u16(0), u32(0), u32(offset), name
      ]);
      centralParts.push(central);
      offset += local.length;
    });

    const central = concat(centralParts);
    const locals = concat(localParts);
    const end = concat([
      u32(0x06054b50), u16(0), u16(0), u16(files.length), u16(files.length),
      u32(central.length), u32(locals.length), u16(0)
    ]);
    return new Blob([locals, central, end], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  }

  function dataUrlBytes(src) {
    const match = String(src || '').match(/^data:(image\/(?:png|jpe?g|gif|webp));base64,(.+)$/i);
    if (!match) return null;
    const binary = atob(match[2]);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const mime = match[1].toLowerCase();
    const ext = mime.includes('jpeg') ? 'jpg' : mime.split('/')[1];
    return { bytes, mime, ext };
  }

  function hexColor(value = '') {
    const text = String(value).trim();
    const short = text.match(/^#([0-9a-f]{3})$/i);
    if (short) return short[1].split('').map(ch => ch + ch).join('').toUpperCase();
    const full = text.match(/^#([0-9a-f]{6})$/i);
    if (full) return full[1].toUpperCase();
    const rgb = text.match(/^rgba?\((\d+)[, ]+\s*(\d+)[, ]+\s*(\d+)/i);
    if (rgb) return [rgb[1], rgb[2], rgb[3]].map(n => Math.max(0, Math.min(255, +n)).toString(16).padStart(2, '0')).join('').toUpperCase();
    return '';
  }

  function halfPoints(value) {
    const number = parseFloat(value);
    if (!Number.isFinite(number)) return null;
    if (/pt/i.test(value)) return Math.round(number * 2);
    if (/px/i.test(value)) return Math.round(number * 1.5);
    return null;
  }

  function runProperties(state) {
    const props = [];
    if (state.bold) props.push('<w:b/>');
    if (state.italic) props.push('<w:i/>');
    if (state.underline) props.push('<w:u w:val="single"/>');
    if (state.strike) props.push('<w:strike/>');
    if (state.vertAlign) props.push(`<w:vertAlign w:val="${state.vertAlign}"/>`);
    if (state.color) props.push(`<w:color w:val="${state.color}"/>`);
    if (state.highlight) props.push(`<w:shd w:fill="${state.highlight}"/>`);
    if (state.font) props.push(`<w:rFonts w:ascii="${xml(state.font)}" w:hAnsi="${xml(state.font)}"/>`);
    if (state.size) props.push(`<w:sz w:val="${state.size}"/><w:szCs w:val="${state.size}"/>`);
    return props.length ? `<w:rPr>${props.join('')}</w:rPr>` : '';
  }

  function makeRun(text, state = {}) {
    if (!text) return '';
    return `<w:r>${runProperties(state)}<w:t xml:space="preserve">${xml(text)}</w:t></w:r>`;
  }

  function mergeState(state, element) {
    const next = { ...state };
    const tag = element.tagName.toLowerCase();
    if (tag === 'strong' || tag === 'b') next.bold = true;
    if (tag === 'em' || tag === 'i') next.italic = true;
    if (tag === 'u') next.underline = true;
    if (tag === 's' || tag === 'strike') next.strike = true;
    if (tag === 'sup') next.vertAlign = 'superscript';
    if (tag === 'sub') next.vertAlign = 'subscript';
    const style = element.style;
    if (style?.fontWeight && (+style.fontWeight >= 600 || /bold/i.test(style.fontWeight))) next.bold = true;
    if (style?.fontStyle === 'italic') next.italic = true;
    if (style?.textDecorationLine?.includes('underline') || style?.textDecoration?.includes('underline')) next.underline = true;
    if (style?.textDecorationLine?.includes('line-through') || style?.textDecoration?.includes('line-through')) next.strike = true;
    const color = hexColor(style?.color);
    if (color) next.color = color;
    const background = hexColor(style?.backgroundColor);
    if (background) next.highlight = background;
    if (style?.fontFamily) next.font = style.fontFamily.split(',')[0].replace(/["']/g, '').trim();
    const size = halfPoints(style?.fontSize || '');
    if (size) next.size = size;
    return next;
  }

  function build({ editor, document: doc }) {
    const escapeSelector = value => window.CSS?.escape ? CSS.escape(value) : String(value).replace(/[^a-zA-Z0-9_-]/g, ch => `\${ch}`);
    const files = [];
    const relationships = [];
    const images = [];
    const footnoteIds = new Map();
    const footnoteTexts = new Map();
    [...editor.querySelectorAll('sup.ink-footnote-ref[data-footnote-id]')].forEach(ref => {
      const key = ref.dataset.footnoteId;
      if (!key || footnoteIds.has(key)) return;
      const number = footnoteIds.size + 1;
      footnoteIds.set(key, number);
      const item = editor.querySelector(`.ink-footnotes li[data-footnote-id="${escapeSelector(key)}"] .footnote-text`);
      footnoteTexts.set(key, item?.textContent?.trim() || '');
    });
    let relationshipCounter = 2; // rId1 = styles
    let drawingCounter = 1;

    function addRelationship(type, target, mode = '') {
      const id = `rId${relationshipCounter++}`;
      relationships.push({ id, type, target, mode });
      return id;
    }

    function imageRun(img) {
      const parsed = dataUrlBytes(img.getAttribute('src'));
      if (!parsed) return makeRun(`[Imagem externa: ${img.getAttribute('alt') || 'imagem'}]`, { italic: true });
      const fileName = `image${images.length + 1}.${parsed.ext}`;
      images.push({ name: `word/media/${fileName}`, data: parsed.bytes, mime: parsed.mime, ext: parsed.ext });
      const relId = addRelationship('http://schemas.openxmlformats.org/officeDocument/2006/relationships/image', `media/${fileName}`);
      const widthPercent = Math.max(10, Math.min(100, parseFloat(img.style.width) || 60));
      const contentWidthInches = 6.27;
      const cx = Math.round(contentWidthInches * (widthPercent / 100) * 914400);
      const ratio = img.naturalWidth && img.naturalHeight ? img.naturalHeight / img.naturalWidth : .65;
      const cy = Math.max(180000, Math.round(cx * ratio));
      const id = drawingCounter++;
      const alt = xml(img.getAttribute('alt') || 'Imagem');
      return `<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${id}" name="Imagem ${id}" descr="${alt}"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="${id}" name="${alt}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${relId}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>`;
    }

    function inline(node, state = {}) {
      if (node.nodeType === Node.TEXT_NODE) return makeRun(node.nodeValue || '', state);
      if (node.nodeType !== Node.ELEMENT_NODE) return '';
      const tag = node.tagName.toLowerCase();
      if (tag === 'sup' && node.classList.contains('ink-footnote-ref')) {
        const id = footnoteIds.get(node.dataset.footnoteId);
        return id ? `<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="${id}"/></w:r>` : '';
      }
      if (tag === 'br') return '<w:r><w:br/></w:r>';
      if (tag === 'img') return imageRun(node);
      if (tag === 'a') {
        const href = node.getAttribute('href') || '';
        const child = [...node.childNodes].map(childNode => inline(childNode, { ...mergeState(state, node), color: '0563C1', underline: true })).join('');
        if (!href) return child;
        if (href.startsWith('#')) return child;
        const relId = addRelationship('http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', href, 'External');
        return `<w:hyperlink r:id="${relId}">${child}</w:hyperlink>`;
      }
      const next = mergeState(state, node);
      return [...node.childNodes].map(child => inline(child, next)).join('');
    }

    function paragraphProperties(element, options = {}) {
      const props = [];
      const tag = element?.tagName?.toLowerCase?.() || 'p';
      const classes = element?.classList;
      let styleId = 'Normal';
      if (tag === 'h1') styleId = 'Heading1';
      else if (tag === 'h2') styleId = 'Heading2';
      else if (tag === 'h3') styleId = 'Heading3';
      else if (tag === 'blockquote') styleId = 'Quote';
      else if (tag === 'pre') styleId = 'Code';
      else if (classes?.contains('ink-caption')) styleId = 'Caption';
      props.push(`<w:pStyle w:val="${styleId}"/>`);
      if (element?.dataset?.keepWithNext === 'true') props.push('<w:keepNext/>');
      if (element?.dataset?.keepLines === 'true') props.push('<w:keepLines/>');
      if (element?.dataset?.pageBreakBefore === 'true') props.push('<w:pageBreakBefore/>');
      const align = element?.style?.textAlign;
      if (align) props.push(`<w:jc w:val="${align === 'justify' ? 'both' : align}"/>`);
      if (options.numId) props.push(`<w:numPr><w:ilvl w:val="${options.level || 0}"/><w:numId w:val="${options.numId}"/></w:numPr>`);
      const left = parseFloat(element?.style?.marginLeft || '');
      const right = parseFloat(element?.style?.marginRight || '');
      const first = parseFloat(element?.style?.textIndent || '');
      if ([left, right, first].some(Number.isFinite)) {
        props.push(`<w:ind${Number.isFinite(left) ? ` w:left="${Math.round(left * 15)}"` : ''}${Number.isFinite(right) ? ` w:right="${Math.round(right * 15)}"` : ''}${Number.isFinite(first) ? ` w:firstLine="${Math.round(first * 15)}"` : ''}/>`);
      }
      return `<w:pPr>${props.join('')}</w:pPr>`;
    }

    function paragraph(element, options = {}) {
      return `<w:p>${paragraphProperties(element, options)}${[...element.childNodes].map(node => inline(node)).join('')}</w:p>`;
    }

    function tableXml(table) {
      const rows = [...table.rows].map(row => {
        const cells = [...row.cells].map(cell => {
          const span = cell.colSpan > 1 ? `<w:gridSpan w:val="${cell.colSpan}"/>` : '';
          const shading = cell.tagName === 'TH' ? '<w:shd w:fill="F2F5FA"/>' : '';
          const cellProps = `<w:tcPr>${span}${shading}<w:vAlign w:val="top"/></w:tcPr>`;
          const paragraphs = [...cell.children].filter(el => /^(P|H1|H2|H3|BLOCKQUOTE|PRE)$/.test(el.tagName)).map(el => paragraph(el));
          const body = paragraphs.length ? paragraphs.join('') : `<w:p>${[...cell.childNodes].map(node => inline(node, { bold: cell.tagName === 'TH' })).join('')}</w:p>`;
          return `<w:tc>${cellProps}${body}</w:tc>`;
        }).join('');
        return `<w:tr>${cells}</w:tr>`;
      }).join('');
      return `<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="C8D1DF"/><w:left w:val="single" w:sz="4" w:color="C8D1DF"/><w:bottom w:val="single" w:sz="4" w:color="C8D1DF"/><w:right w:val="single" w:sz="4" w:color="C8D1DF"/><w:insideH w:val="single" w:sz="4" w:color="C8D1DF"/><w:insideV w:val="single" w:sz="4" w:color="C8D1DF"/></w:tblBorders></w:tblPr>${rows}</w:tbl>`;
    }

    function blockXml(element) {
      if (!(element instanceof Element)) return '';
      const tag = element.tagName.toLowerCase();
      if (element.classList.contains('ink-footnotes')) return '';
      if (element.classList.contains('ink-toc')) return '<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Sumário automático</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>';
      if (element.classList.contains('page-break')) return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>';
      if (tag === 'table') return tableXml(element);
      if (tag === 'img') return `<w:p><w:pPr><w:jc w:val="center"/></w:pPr>${imageRun(element)}</w:p>`;
      if (tag === 'figure') {
        const image = element.querySelector(':scope > img');
        const caption = element.querySelector(':scope > figcaption');
        return `${image ? `<w:p><w:pPr><w:jc w:val="center"/></w:pPr>${imageRun(image)}</w:p>` : ''}${caption ? paragraph(caption) : ''}`;
      }
      if (tag === 'ul' || tag === 'ol') {
        const numId = tag === 'ol' ? 2 : 1;
        return [...element.children].filter(child => child.tagName === 'LI').map(li => paragraph(li, { numId })).join('');
      }
      if (tag === 'hr') return '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="B8C2D0"/></w:pBdr></w:pPr></w:p>';
      if (['nav', 'section', 'article'].includes(tag)) return [...element.children].map(blockXml).join('');
      if (tag === 'div' && [...element.children].some(child => /^(P|H1|H2|H3|UL|OL|TABLE|BLOCKQUOTE|PRE)$/.test(child.tagName))) return [...element.children].map(blockXml).join('');
      if (['p', 'h1', 'h2', 'h3', 'blockquote', 'pre', 'figcaption', 'div'].includes(tag)) return paragraph(element);
      return `<w:p>${inline(element)}</w:p>`;
    }

    const clone = editor.cloneNode(true);
    clone.querySelectorAll('.selected-image,.selected-table-cell,.accessibility-focus').forEach(el => el.classList.remove('selected-image', 'selected-table-cell', 'accessibility-focus'));
    clone.querySelectorAll('[data-page-break-remove]').forEach(el => el.remove());
    const body = [...clone.children].map(blockXml).join('') || '<w:p/>';

    const paper = { a4: [11906, 16838], letter: [12240, 15840], a5: [8391, 11906] }[doc.settings?.paper] || [11906, 16838];
    const landscape = doc.settings?.orientation === 'landscape';
    const pgW = landscape ? paper[1] : paper[0];
    const pgH = landscape ? paper[0] : paper[1];
    const marginPx = { narrow: 38, normal: 72, wide: 108, custom: Math.max(0, Number(doc.settings?.customMargin) || 72) }[doc.settings?.margin] ?? 72;
    const margin = Math.round(marginPx * 15);

    let headerRel = '';
    let footerRel = '';
    const replaceTokens = value => String(value || '')
      .replace(/\{titulo\}/gi, doc.title || '')
      .replace(/\{data\}/gi, new Intl.DateTimeFormat('pt-BR').format(new Date()));
    const headerText = replaceTokens(doc.settings?.headerText).trim();
    const footerText = replaceTokens(doc.settings?.footerText).trim();
    const pageStyle = doc.settings?.pageNumberStyle || 'none';
    if (headerText) {
      headerRel = addRelationship('http://schemas.openxmlformats.org/officeDocument/2006/relationships/header', 'header1.xml');
      files.push({ name: 'word/header1.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>${makeRun(headerText)}</w:p></w:hdr>` });
    }
    if (footerText || pageStyle !== 'none') {
      footerRel = addRelationship('http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer', 'footer1.xml');
      const pageField = pageStyle !== 'none' ? `<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>` : '';
      const pagePrefix = pageStyle === 'page' ? 'Página ' : '';
      files.push({ name: 'word/footer1.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>${footerText ? makeRun(`${footerText}${pageField ? ' · ' : ''}`) : ''}${pagePrefix ? makeRun(pagePrefix) : ''}${pageField}</w:p></w:ftr>` });
    }

    let footnotesRel = '';
    if (footnoteIds.size) {
      footnotesRel = addRelationship('http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes', 'footnotes.xml');
      const definitions = [...footnoteIds.entries()].map(([key, id]) => `<w:footnote w:id="${id}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr><w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r><w:r><w:t xml:space="preserve"> ${xml(footnoteTexts.get(key) || '')}</w:t></w:r></w:p></w:footnote>`).join('');
      const footnotesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote><w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>${definitions}</w:footnotes>`;
      files.push({ name: 'word/footnotes.xml', data: footnotesXml });
    }
    const settingsRel = addRelationship('http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings', 'settings.xml');
    files.push({ name: 'word/settings.xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:updateFields w:val="true"/><w:widowControl/></w:settings>' });

    const sectPr = `<w:sectPr>${headerRel ? `<w:headerReference w:type="default" r:id="${headerRel}"/>` : ''}${footerRel ? `<w:footerReference w:type="default" r:id="${footerRel}"/>` : ''}<w:pgSz w:w="${pgW}" w:h="${pgH}"${landscape ? ' w:orient="landscape"' : ''}/><w:pgMar w:top="${margin}" w:right="${margin}" w:bottom="${margin}" w:left="${margin}" w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>`;

    const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>${body}${sectPr}</w:body></w:document>`;

    const stylesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="480"/><w:spacing w:before="120" w:after="120"/></w:pPr><w:rPr><w:i/><w:color w:val="4B5563"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:i/><w:color w:val="667085"/><w:sz w:val="20"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/><w:sz w:val="20"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style><w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style></w:styles>`;

    const numberingXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="720"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="720"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>`;

    relationships.unshift({ id: 'rId1', type: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles', target: 'styles.xml', mode: '' });
    const numberingId = `rId${relationshipCounter++}`;
    relationships.push({ id: numberingId, type: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering', target: 'numbering.xml', mode: '' });
    const documentRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${relationships.map(rel => `<Relationship Id="${rel.id}" Type="${rel.type}" Target="${xml(rel.target)}"${rel.mode ? ` TargetMode="${rel.mode}"` : ''}/>`).join('')}</Relationships>`;

    const imageDefaults = [...new Map(images.map(image => [image.ext, image.mime])).entries()].map(([ext, mime]) => `<Default Extension="${ext}" ContentType="${mime}"/>`).join('');
    const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>${imageDefaults}<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>${headerRel ? '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>' : ''}${footerRel ? '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>' : ''}${footnotesRel ? '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>' : ''}<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`;

    const rootRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>`;
    const now = new Date().toISOString();
    const core = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${xml(doc.title || 'Documento')}</dc:title><dc:creator>InkWrite</dc:creator><cp:lastModifiedBy>InkWrite</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">${now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">${now}</dcterms:modified></cp:coreProperties>`;
    const app = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>InkWrite</Application><AppVersion>2.0</AppVersion></Properties>`;

    files.push(
      { name: '[Content_Types].xml', data: contentTypes },
      { name: '_rels/.rels', data: rootRels },
      { name: 'docProps/core.xml', data: core },
      { name: 'docProps/app.xml', data: app },
      { name: 'word/document.xml', data: documentXml },
      { name: 'word/styles.xml', data: stylesXml },
      { name: 'word/numbering.xml', data: numberingXml },
      { name: 'word/_rels/document.xml.rels', data: documentRels },
      ...images
    );

    return zipStore(files);
  }

  window.InkWriteDocx = { build };
})();
