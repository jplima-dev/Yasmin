const dialog = document.querySelector('#newProjectDialog');
const form = document.querySelector('#newProjectForm');
const nameInput = document.querySelector('#newProjectName');
const templateInput = document.querySelector('#newProjectTemplate');
const templateHint = document.querySelector('#templateHint');
const grid = document.querySelector('#projectGrid');
const empty = document.querySelector('#emptyProjects');

const templates = {
  blank: ['Minha planilha', 'Começa vazia, com uma aba pronta para editar.'],
  budget: ['Orçamento mensal', 'Receitas, despesas, totais e saldo com fórmulas prontas.'],
  expenses: ['Controle de gastos', 'Tabela preparada para registrar gastos por data e categoria.'],
  inventory: ['Controle de estoque', 'Produtos, estoque mínimo, custo, preço e valor total.'],
  schedule: ['Cronograma', 'Tarefas, responsável, prioridade, status e prazo.'],
};

function openEditor(name, template='blank') {
  window.location.href = `editor.html?new=${encodeURIComponent(name)}&template=${encodeURIComponent(template)}`;
}
function openProject(id) {
  localStorage.setItem('planilha-studio-last-project', id);
  window.location.href = `editor.html?project=${encodeURIComponent(id)}`;
}
function showDialog(template='blank') {
  const [name, hint] = templates[template] || templates.blank;
  templateInput.value = template; nameInput.value = name; templateHint.textContent = hint;
  dialog.showModal(); nameInput.select();
}
function closeDialog() { if (dialog.open) dialog.close('cancel'); }
function formatDate(value) {
  try { return new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short'}).format(new Date(value)); } catch { return ''; }
}
function previewCell(sheet, row, col) {
  const addr = `${String.fromCharCode(65 + col)}${row + 1}`;
  const cell = sheet?.cells?.[addr];
  return cell?.raw || '';
}
function buildPreview(project) {
  const box = document.createElement('div'); box.className = 'project-preview';
  const sheet = project.state?.sheets?.[0];
  for (let r=0;r<4;r++) for(let c=0;c<5;c++) {
    const span=document.createElement('span'); const value=previewCell(sheet,r,c); span.textContent=String(value).replace(/^=/,'ƒ '); if(r===0 && value) span.classList.add('head'); box.append(span);
  }
  return box;
}
async function card(project) {
  const el=document.createElement('article'); el.className='project-card';
  const content=document.createElement('div'); content.className='project-card-content';
  const h=document.createElement('h3'); h.textContent=project.title || 'Planilha';
  const p=document.createElement('p'); const sheets=project.state?.sheets?.length || 1; p.textContent=`${formatDate(project.updatedAt)} · ${sheets} aba${sheets===1?'':'s'}`; content.append(h,p);
  const actions=document.createElement('div'); actions.className='project-actions';
  const edit=document.createElement('button'); edit.className='project-action primary-link'; edit.textContent='Editar'; edit.onclick=()=>openProject(project.id);
  const rename=document.createElement('button'); rename.className='project-action'; rename.textContent='Renomear'; rename.onclick=async()=>{const next=prompt('Novo nome:',h.textContent)?.trim(); if(!next)return; await SheetDB.renameProject(project.id,next); await render();};
  const duplicate=document.createElement('button'); duplicate.className='project-action'; duplicate.textContent='Duplicar'; duplicate.onclick=async()=>{await SheetDB.duplicateProject(project.id); await render();};
  const remove=document.createElement('button'); remove.className='project-action danger-link'; remove.textContent='Excluir'; remove.onclick=async()=>{if(!confirm('Excluir esta planilha?'))return; await SheetDB.deleteProject(project.id); if(localStorage.getItem('planilha-studio-last-project')===project.id)localStorage.removeItem('planilha-studio-last-project'); await render();};
  actions.append(edit,rename,duplicate,remove); el.append(buildPreview(project),content,actions); return el;
}
async function render() {
  let projects=[]; try{projects=await SheetDB.getAllProjects();}catch(error){console.error(error)}
  grid.innerHTML=''; empty.hidden=projects.length>0; for(const p of projects) grid.append(await card(p));
}

document.querySelectorAll('[data-template]').forEach(button=>button.addEventListener('click',()=>showDialog(button.dataset.template)));
document.querySelector('#newProjectButton').onclick=()=>showDialog('blank');
document.querySelector('#cancelProjectClose').onclick=closeDialog;
document.querySelector('#cancelProjectButton').onclick=closeDialog;
form.addEventListener('submit',event=>{event.preventDefault(); const name=nameInput.value.trim()||'Minha planilha'; const template=templateInput.value||'blank'; dialog.close('default'); openEditor(name,template);});
document.querySelector('#openLastProject').addEventListener('click',async event=>{event.preventDefault(); const id=localStorage.getItem('planilha-studio-last-project'); if(id){const p=await SheetDB.getProject(id).catch(()=>null); if(p)return openProject(id);} const latest=(await SheetDB.getAllProjects().catch(()=>[]))[0]; latest?openProject(latest.id):showDialog('blank');});
render();
