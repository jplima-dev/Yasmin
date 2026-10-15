(() => {
  function create({ editor, tools, afterEdit }) {
    let selectedTable = null;
    let selectedCell = null;

    function positionTools() {
      if (!tools || !selectedCell || tools.hidden) return;
      const rect = selectedCell.getBoundingClientRect();
      const width = tools.offsetWidth || 520;
      const left = Math.max(8, Math.min(window.innerWidth - width - 8, rect.left));
      const top = Math.max(8, rect.top - (tools.offsetHeight || 36) - 6);
      tools.style.left = `${left}px`;
      tools.style.top = `${top}px`;
    }

    function selectCell(cell) {
      editor.querySelectorAll('.selected-table-cell').forEach(el => el.classList.remove('selected-table-cell'));
      selectedCell = cell || null;
      selectedTable = cell?.closest('table') || null;
      if (!selectedCell || !selectedTable) {
        if (tools) tools.hidden = true;
        return;
      }
      selectedCell.classList.add('selected-table-cell');
      if (tools) tools.hidden = false;
      requestAnimationFrame(positionTools);
    }

    function cellIndex(cell) { return cell ? [...cell.parentElement.children].indexOf(cell) : -1; }

    function action(actionName) {
      if (!selectedTable || !selectedCell) return false;
      const row = selectedCell.closest('tr');
      const rowIndex = [...selectedTable.rows].indexOf(row);
      const colIndex = cellIndex(selectedCell);
      if (actionName === 'row-add') {
        const newRow = selectedTable.insertRow(rowIndex + 1);
        const cells = Math.max(1, row.cells.length);
        for (let i = 0; i < cells; i += 1) newRow.insertCell().innerHTML = '<br>';
        selectCell(newRow.cells[Math.min(colIndex, newRow.cells.length - 1)]);
      } else if (actionName === 'row-remove') {
        if (selectedTable.rows.length <= 1) { selectedTable.remove(); selectCell(null); }
        else {
          selectedTable.deleteRow(rowIndex);
          const targetRow = selectedTable.rows[Math.min(rowIndex, selectedTable.rows.length - 1)];
          selectCell(targetRow?.cells[Math.min(colIndex, targetRow.cells.length - 1)] || null);
        }
      } else if (actionName === 'col-add') {
        [...selectedTable.rows].forEach(r => {
          const ref = r.cells[Math.min(colIndex, r.cells.length - 1)];
          const tag = ref?.tagName?.toLowerCase() === 'th' ? 'th' : 'td';
          const cell = document.createElement(tag);
          cell.innerHTML = '<br>';
          if (ref?.nextSibling) r.insertBefore(cell, ref.nextSibling); else r.append(cell);
        });
        selectCell(row.cells[Math.min(colIndex + 1, row.cells.length - 1)]);
      } else if (actionName === 'col-remove') {
        const maxCols = Math.max(...[...selectedTable.rows].map(r => r.cells.length));
        if (maxCols <= 1) { selectedTable.remove(); selectCell(null); }
        else {
          [...selectedTable.rows].forEach(r => { if (r.cells[colIndex]) r.cells[colIndex].remove(); });
          const targetRow = selectedTable.rows[Math.min(rowIndex, selectedTable.rows.length - 1)];
          selectCell(targetRow?.cells[Math.min(colIndex, targetRow.cells.length - 1)] || null);
        }
      } else if (actionName === 'merge-right') {
        const next = selectedCell.nextElementSibling;
        if (!next) return false;
        const extra = next.innerHTML.trim();
        if (extra && extra !== '<br>') selectedCell.insertAdjacentHTML('beforeend', `${selectedCell.innerHTML.trim() && selectedCell.innerHTML.trim() !== '<br>' ? '<br>' : ''}${extra}`);
        selectedCell.colSpan = (selectedCell.colSpan || 1) + (next.colSpan || 1);
        next.remove();
      } else if (actionName === 'split') {
        const span = selectedCell.colSpan || 1;
        if (span <= 1) return false;
        selectedCell.colSpan = 1;
        let anchor = selectedCell;
        for (let i = 1; i < span; i += 1) {
          const cell = document.createElement(selectedCell.tagName.toLowerCase());
          cell.innerHTML = '<br>';
          anchor.after(cell); anchor = cell;
        }
      } else if (actionName === 'header-toggle') {
        const firstRow = selectedTable.rows[0];
        if (!firstRow) return false;
        const shouldBecomeHeader = firstRow.parentElement?.tagName !== 'THEAD' || [...firstRow.cells].some(cell => cell.tagName !== 'TH');
        const selectedIndex = firstRow === row ? colIndex : -1;
        [...firstRow.cells].forEach(cell => {
          const replacement = document.createElement(shouldBecomeHeader ? 'th' : 'td');
          [...cell.attributes].forEach(attr => replacement.setAttribute(attr.name, attr.value));
          while (cell.firstChild) replacement.append(cell.firstChild);
          cell.replaceWith(replacement);
        });
        if (shouldBecomeHeader) {
          let head = selectedTable.tHead;
          if (!head) head = selectedTable.createTHead();
          head.append(firstRow);
        } else if (firstRow.parentElement?.tagName === 'THEAD') {
          let body = selectedTable.tBodies[0];
          if (!body) body = selectedTable.createTBody();
          body.insertBefore(firstRow, body.firstChild);
          if (selectedTable.tHead && !selectedTable.tHead.rows.length) selectedTable.deleteTHead();
        }
        if (selectedIndex >= 0) selectCell(firstRow.cells[Math.min(selectedIndex, firstRow.cells.length - 1)]);
      } else if (['cell-left', 'cell-center', 'cell-right'].includes(actionName)) {
        selectedCell.style.textAlign = actionName === 'cell-center' ? 'center' : actionName === 'cell-right' ? 'right' : 'left';
      } else if (actionName === 'distribute') {
        const maxCols = Math.max(...[...selectedTable.rows].map(r => [...r.cells].reduce((sum, c) => sum + (c.colSpan || 1), 0)));
        [...selectedTable.rows].forEach(r => [...r.cells].forEach(c => { c.style.width = `${((c.colSpan || 1) / maxCols) * 100}%`; }));
      } else return false;
      afterEdit('immediate');
      requestAnimationFrame(positionTools);
      return true;
    }

    function tableHtml(rows = 3, cols = 3, header = true) {
      rows = Math.max(1, Math.min(50, Number(rows) || 3));
      cols = Math.max(1, Math.min(20, Number(cols) || 3));
      let html = '<table>';
      if (header) {
        html += '<thead><tr>' + '<th><br></th>'.repeat(cols) + '</tr></thead>';
      }
      html += '<tbody>';
      const bodyRows = header ? Math.max(0, rows - 1) : rows;
      for (let r = 0; r < bodyRows; r += 1) html += '<tr>' + '<td><br></td>'.repeat(cols) + '</tr>';
      if (!bodyRows && header) html += '<tr>' + '<td><br></td>'.repeat(cols) + '</tr>';
      return `${html}</tbody></table><p><br></p>`;
    }

    function reset() { selectCell(null); }

    tools?.addEventListener('click', event => {
      const button = event.target.closest('[data-table-action]');
      if (!button) return;
      event.preventDefault();
      action(button.dataset.tableAction);
    });
    editor.addEventListener('click', event => {
      const cell = event.target.closest('td,th');
      if (cell && editor.contains(cell)) selectCell(cell);
      else if (!event.target.closest('table')) selectCell(null);
    });
    window.addEventListener('resize', positionTools);
    document.querySelector('.canvas-area')?.addEventListener('scroll', positionTools, { passive: true });

    return { selectCell, positionTools, action, tableHtml, reset, selectedCell: () => selectedCell, selectedTable: () => selectedTable };
  }
  window.InkWriteTables = { create };
})();
