(() => {
  function create({ editor, input, insertHtml, escapeHtml, restoreSelection, afterEdit, scheduleSave, pushHistoryNow }) {
    let selectedImage = null;

    function blobToDataUrl(blob) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = () => reject(reader.error || new Error('Falha ao ler imagem'));
        reader.readAsDataURL(blob);
      });
    }

    async function optimizeFile(file) {
      const MAX_INPUT = 25 * 1024 * 1024;
      const MAX_OUTPUT = 4 * 1024 * 1024;
      if (!file?.type?.startsWith('image/')) throw new Error('Arquivo não é uma imagem.');
      if (file.size > MAX_INPUT) throw new Error('Imagem muito grande. Use um arquivo com até 25 MB.');
      if (file.type === 'image/svg+xml') throw new Error('SVG incorporado não é aceito por segurança. Converta para PNG, JPEG ou WebP.');

      if (file.type === 'image/gif') {
        if (file.size > MAX_OUTPUT) throw new Error('GIFs animados não são recomprimidos. Use um GIF com até 4 MB.');
        return blobToDataUrl(file);
      }

      let bitmap;
      try {
        bitmap = await createImageBitmap(file);
        const render = async (maxDimension, quality) => {
          const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
          const width = Math.max(1, Math.round(bitmap.width * scale));
          const height = Math.max(1, Math.round(bitmap.height * scale));
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const context = canvas.getContext('2d', { alpha: true });
          context.drawImage(bitmap, 0, 0, width, height);
          return new Promise(resolve => canvas.toBlob(resolve, 'image/webp', quality));
        };
        let blob = await render(1800, .86);
        if (!blob) throw new Error('Este navegador não conseguiu compactar a imagem.');
        if (blob.size > MAX_OUTPUT) blob = await render(1400, .74);
        if (!blob || blob.size > MAX_OUTPUT) throw new Error('A imagem continua maior que 4 MB depois da compactação.');
        return await blobToDataUrl(blob);
      } finally {
        bitmap?.close?.();
      }
    }

    async function insertFile(file, altText = '') {
      try {
        const dataUrl = await optimizeFile(file);
        insertHtml(`<img src="${dataUrl}" alt="${escapeHtml(altText || file.name || 'Imagem')}" data-flow="block" data-align="center" style="width:60%;margin-left:auto;margin-right:auto;border:0 solid #cbd5e1;border-radius:8px">`);
        return true;
      } catch (error) {
        console.error(error);
        alert(error?.message || 'Não foi possível inserir esta imagem.');
        return false;
      }
    }

    function applyLayout(img) {
      if (!img) return;
      const align = img.dataset.align || 'center';
      const flow = img.dataset.flow || 'block';
      img.style.float = '';
      img.style.clear = '';
      if (flow === 'wrap' && align !== 'center') {
        img.style.float = align;
        img.style.marginLeft = align === 'right' ? '14px' : '0px';
        img.style.marginRight = align === 'left' ? '14px' : '0px';
      } else {
        img.style.clear = flow === 'wrap' ? 'both' : '';
        if (align === 'left') { img.style.marginLeft = '0px'; img.style.marginRight = 'auto'; }
        else if (align === 'right') { img.style.marginLeft = 'auto'; img.style.marginRight = '0px'; }
        else { img.style.marginLeft = 'auto'; img.style.marginRight = 'auto'; }
      }
    }

    function select(img) {
      if (selectedImage) selectedImage.classList.remove('selected-image');
      selectedImage = img || null;
      const panel = document.querySelector('#imageProperties');
      if (panel) panel.hidden = !selectedImage;
      if (!selectedImage) return;
      selectedImage.classList.add('selected-image');
      const width = parseInt(selectedImage.style.width, 10) || 60;
      document.querySelector('#imageWidth').value = width;
      document.querySelector('#imageWidthValue').textContent = `${width}%`;
      document.querySelector('#imageAlt').value = selectedImage.alt || '';
      document.querySelector('#imageBorder').value = parseInt(selectedImage.style.borderWidth, 10) || 0;
      document.querySelector('#imageBorderValue').textContent = `${document.querySelector('#imageBorder').value} px`;
      document.querySelector('#imageRadius').value = parseInt(selectedImage.style.borderRadius, 10) || 0;
      document.querySelector('#imageRadiusValue').textContent = `${document.querySelector('#imageRadius').value} px`;
      const ml = selectedImage.style.marginLeft, mr = selectedImage.style.marginRight;
      const inferredAlign = (ml === 'auto' && mr === '0px') ? 'right' : (ml === '0px' && mr === 'auto') ? 'left' : 'center';
      selectedImage.dataset.align ||= inferredAlign;
      selectedImage.dataset.flow ||= 'block';
      document.querySelector('#imageAlign').value = selectedImage.dataset.align;
      document.querySelector('#imageFlow').value = selectedImage.dataset.flow;
    }

    function updateCropPreview() {
      const preview = document.querySelector('#cropPreview');
      if (!preview) return;
      const values = ['cropTop','cropRight','cropBottom','cropLeft'].map(id => Math.max(0, Math.min(45, +document.querySelector(`#${id}`)?.value || 0)));
      preview.style.clipPath = `inset(${values[0]}% ${values[1]}% ${values[2]}% ${values[3]}%)`;
    }

    function openCropDialog() {
      if (!selectedImage) return;
      document.querySelector('#cropPreview').src = selectedImage.src;
      ['cropTop','cropRight','cropBottom','cropLeft'].forEach(id => { document.querySelector(`#${id}`).value = 0; });
      updateCropPreview();
      document.querySelector('#cropImageDialog')?.showModal();
    }
    function closeCropDialog() { if (document.querySelector('#cropImageDialog')?.open) document.querySelector('#cropImageDialog').close(); }

    async function crop() {
      if (!selectedImage) { closeCropDialog(); return false; }
      const [top, right, bottom, left] = ['cropTop','cropRight','cropBottom','cropLeft'].map(id => Math.max(0, Math.min(45, +document.querySelector(`#${id}`).value || 0)) / 100);
      if (left + right >= .95 || top + bottom >= .95) {
        alert('O recorte remove área demais da imagem.');
        return false;
      }
      try {
        const source = new Image();
        source.decoding = 'async';
        const loaded = new Promise((resolve, reject) => { source.onload = resolve; source.onerror = () => reject(new Error('Não foi possível carregar a imagem para recorte.')); });
        source.src = selectedImage.src;
        await loaded;
        const sx = Math.round(source.naturalWidth * left);
        const sy = Math.round(source.naturalHeight * top);
        const sw = Math.max(1, Math.round(source.naturalWidth * (1 - left - right)));
        const sh = Math.max(1, Math.round(source.naturalHeight * (1 - top - bottom)));
        const scale = Math.min(1, 1800 / Math.max(sw, sh));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(sw * scale));
        canvas.height = Math.max(1, Math.round(sh * scale));
        canvas.getContext('2d').drawImage(source, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/webp', .9));
        if (!blob) throw new Error('O navegador não conseguiu gerar o recorte.');
        selectedImage.src = await blobToDataUrl(blob);
        closeCropDialog();
        afterEdit('immediate');
        return true;
      } catch (error) {
        console.error(error);
        alert('Não foi possível recortar esta imagem. Imagens externas podem bloquear o Canvas; imagens incorporadas funcionam normalmente.');
        return false;
      }
    }

    function reset() { select(null); }

    input?.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (!file) return;
      restoreSelection();
      await insertFile(file, file.name);
      input.value = '';
    });
    editor.addEventListener('click', event => {
      if (event.target.tagName === 'IMG') select(event.target);
      else if (selectedImage && !event.target.closest('#imageProperties')) select(null);
    });
    document.querySelector('#imageWidth')?.addEventListener('input', event => {
      if (!selectedImage) return;
      selectedImage.style.width = `${event.target.value}%`;
      document.querySelector('#imageWidthValue').textContent = `${event.target.value}%`;
      afterEdit(false);
    });
    document.querySelector('#imageWidth')?.addEventListener('change', () => afterEdit(true));
    document.querySelector('#imageAlign')?.addEventListener('change', event => {
      if (!selectedImage) return;
      selectedImage.dataset.align = event.target.value;
      applyLayout(selectedImage); afterEdit('immediate');
    });
    document.querySelector('#imageFlow')?.addEventListener('change', event => {
      if (!selectedImage) return;
      selectedImage.dataset.flow = event.target.value;
      applyLayout(selectedImage); afterEdit('immediate');
    });
    document.querySelector('#imageAlt')?.addEventListener('input', event => {
      if (selectedImage) { selectedImage.alt = event.target.value; scheduleSave(); }
    });
    document.querySelector('#imageAlt')?.addEventListener('change', () => pushHistoryNow());
    document.querySelector('#imageBorder')?.addEventListener('input', event => {
      if (!selectedImage) return;
      selectedImage.style.border = `${event.target.value}px solid #cbd5e1`;
      document.querySelector('#imageBorderValue').textContent = `${event.target.value} px`;
      afterEdit(false);
    });
    document.querySelector('#imageBorder')?.addEventListener('change', () => afterEdit(true));
    document.querySelector('#imageRadius')?.addEventListener('input', event => {
      if (!selectedImage) return;
      selectedImage.style.borderRadius = `${event.target.value}px`;
      document.querySelector('#imageRadiusValue').textContent = `${event.target.value} px`;
      afterEdit(false);
    });
    document.querySelector('#imageRadius')?.addEventListener('change', () => afterEdit(true));
    ['cropTop','cropRight','cropBottom','cropLeft'].forEach(id => document.querySelector(`#${id}`)?.addEventListener('input', updateCropPreview));
    document.querySelector('#cropImageButton')?.addEventListener('click', openCropDialog);
    document.querySelector('#cropImageDialog')?.querySelectorAll('[data-crop-close]').forEach(button => button.addEventListener('click', closeCropDialog));
    document.querySelector('#cropImageForm')?.addEventListener('submit', async event => { event.preventDefault(); await crop(); });
    document.querySelector('#removeImageButton')?.addEventListener('click', () => {
      if (!selectedImage) return;
      selectedImage.remove(); select(null); afterEdit('immediate');
    });

    return { insertFile, optimizeFile, select, reset, selected: () => selectedImage, applyLayout, openCropDialog, closeCropDialog };
  }
  window.InkWriteImages = { create };
})();
