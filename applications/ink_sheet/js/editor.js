const $ = s => document.querySelector(s);
const table = $('#sheetTable');
const viewport = $('#gridViewport');
const formulaInput = $('#formulaInput');
const cellEditor = $('#cellEditor');
const titleInput = $('#projectTitle');
const saveState = $('#saveState');
const sheetTabs = $('#sheetTabs');
const DEFAULT_ROWS = 60;
const DEFAULT_COLS = 26;
const MAX_HISTORY = 80;
let projectId = null;
let projectCreatedAt = null;
let state = null;
let selection = { start:{r:0,c:0}, end:{r:0,c:0} };
let history = [];
let future = [];
let editing = false;
let autosaveTimer = 0;
let zoom = 1;
let findMatches = [];
let findIndex = -1;

const clone = value => SheetDB.clone(value);
const nowId = () => SheetDB.createId();
function colName(index){let n=index+1,s='';while(n>0){const m=(n-1)%26;s=String.fromCharCode(65+m)+s;n=Math.floor((n-1)/26);}return s;}
function colIndex(name){let n=0;for(const ch of name.toUpperCase())n=n*26+(ch.charCodeAt(0)-64);return n-1;}
function addr(r,c){return `${colName(c)}${r+1}`;}
function parseAddr(a){const m=/^([A-Z]+)(\d+)$/i.exec(a||'');return m?{r:+m[2]-1,c:colIndex(m[1])}:null;}
function activeSheet(){return state.sheets.find(s=>s.id===state.activeSheetId)||state.sheets[0];}
function cellAt(a, sheet=activeSheet()){return sheet.cells[a] || null;}
function ensureCell(a,sheet=activeSheet()){return sheet.cells[a] ||= {raw:'',style:{}};}
function normalizeRange(){return {r1:Math.min(selection.start.r,selection.end.r),r2:Math.max(selection.start.r,selection.end.r),c1:Math.min(selection.start.c,selection.end.c),c2:Math.max(selection.start.c,selection.end.c)};}
function rangeAddresses(){const x=normalizeRange(),out=[];for(let r=x.r1;r<=x.r2;r++)for(let c=x.c1;c<=x.c2;c++)out.push(addr(r,c));return out;}
function selectedAddr(){return addr(selection.end.r,selection.end.c);}

function baseState(title='Minha planilha'){
  const sheet={id:nowId(),name:'Planilha1',rows:DEFAULT_ROWS,cols:DEFAULT_COLS,cells:{},colWidths:{},rowHeights:{}};
  return {title,sheets:[sheet],activeSheetId:sheet.id,gridlines:true,dark:false};
}
function setRaw(sheet,a,raw,style){const cell=sheet.cells[a] ||= {raw:'',style:{}};cell.raw=raw??''; if(style)cell.style={...(cell.style||{}),...style}; if(cell.raw===''&&Object.keys(cell.style||{}).length===0)delete sheet.cells[a];}
function setTemplate(template,title){state=baseState(title);const s=activeSheet();const put=(a,raw,style={})=>setRaw(s,a,raw,style);const header={bold:true,fill:'#eaf4f0',color:'#0f766e',align:'center'};const money={format:'currency'};
  if(template==='budget'){
    s.name='Orçamento';
    put('A1','ORÇAMENTO MENSAL',{bold:true,fontSize:16,color:'#0f766e'}); put('A3','Receitas',header); put('B3','Valor',header); put('D3','Despesas',header); put('E3','Valor',header);
    ['Salário','Freelance','Outros'].forEach((v,i)=>put(`A${4+i}`,v)); ['Moradia','Alimentação','Transporte','Lazer','Outros'].forEach((v,i)=>put(`D${4+i}`,v));
    put('A8','Total de receitas',header); put('B8','=SUM(B4:B6)',{...money,bold:true}); put('D10','Total de despesas',header); put('E10','=SUM(E4:E8)',{...money,bold:true}); put('A11','Saldo',header); put('B11','=B8-E10',{...money,bold:true});
  } else if(template==='expenses'){
    s.name='Gastos'; ['Data','Categoria','Descrição','Pagamento','Valor','Observações'].forEach((v,i)=>put(addr(0,i),v,header));
    put('A2',new Date().toISOString().slice(0,10),{format:'date'}); put('B2','Alimentação'); put('C2','Exemplo: almoço'); put('D2','Pix'); put('E2','0',{format:'currency'}); put('D5','TOTAL',header); put('E5','=SUM(E2:E4)',{format:'currency',bold:true});
  } else if(template==='inventory'){
    s.name='Estoque'; ['Produto','Código','Quantidade','Mínimo','Custo','Preço','Valor em estoque','Status'].forEach((v,i)=>put(addr(0,i),v,header));
    put('A2','Produto exemplo'); put('B2','001'); put('C2','0',{format:'number'}); put('D2','5',{format:'number'}); put('E2','0',{format:'currency'}); put('F2','0',{format:'currency'}); put('G2','=C2*E2',{format:'currency'}); put('H2','=IF(C2<=D2,"REPOR","OK")',{align:'center'});
  } else if(template==='schedule'){
    s.name='Cronograma'; ['Tarefa','Responsável','Prioridade','Status','Início','Prazo','Observações'].forEach((v,i)=>put(addr(0,i),v,header)); put('A2','Primeira tarefa'); put('C2','Média'); put('D2','Não iniciado');
  }
}

function pushHistory(){history.push(clone(state));if(history.length>MAX_HISTORY)history.shift();future=[];updateUndoButtons();}
function restore(snapshot){state=clone(snapshot);ensureActiveSheet();selection={start:{r:0,c:0},end:{r:0,c:0}};renderAll();scheduleSave();}
function undo(){if(!history.length)return;future.push(clone(state));restore(history.pop());}
function redo(){if(!future.length)return;history.push(clone(state));restore(future.pop());}
function updateUndoButtons(){$('#undoButton').disabled=$('#menuUndo').disabled=!history.length;$('#redoButton').disabled=$('#menuRedo').disabled=!future.length;}
function ensureActiveSheet(){if(!state.sheets.some(s=>s.id===state.activeSheetId))state.activeSheetId=state.sheets[0]?.id;}

function formatValue(value,style={}){
  if(value===null||value===undefined)return '';
  if(value instanceof Date)return value.toLocaleDateString('pt-BR');
  if(typeof value==='number'){
    if(!Number.isFinite(value))return '#NUM!';
    if(style.format==='currency')return value.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
    if(style.format==='percent')return (value*100).toLocaleString('pt-BR',{maximumFractionDigits:2})+'%';
    if(style.format==='number')return value.toLocaleString('pt-BR',{maximumFractionDigits:8});
    if(style.format==='date'){const d=new Date(value);if(!Number.isNaN(d.getTime()))return d.toLocaleDateString('pt-BR');}
    return String(Math.round(value*1e10)/1e10);
  }
  if(style.format==='date' && /^\d{4}-\d{2}-\d{2}/.test(String(value))){const [y,m,d]=String(value).slice(0,10).split('-');return `${d}/${m}/${y}`;}
  return String(value);
}
function cellDisplay(sheet,a){const cell=cellAt(a,sheet);if(!cell)return '';return formatValue(evaluateCell(sheet,a,new Set()),cell.style||{});}
function primitive(v,sheet,stack){if(v&&v.__ref)return evaluateCell(sheet,v.addr,new Set(stack));if(v&&v.__range)return valuesOfRange(sheet,v,new Set(stack));return v;}
function numeric(v,sheet,stack){v=primitive(v,sheet,stack);if(Array.isArray(v))return v.map(x=>numeric(x,sheet,stack));if(typeof v==='number')return v;if(typeof v==='boolean')return v?1:0;if(v===''||v==null)return 0;const n=Number(String(v).replace(',','.'));return Number.isFinite(n)?n:0;}
function valuesOfRange(sheet,range,stack){const a=parseAddr(range.start),b=parseAddr(range.end);if(!a||!b)return[];const out=[];for(let r=Math.min(a.r,b.r);r<=Math.max(a.r,b.r);r++)for(let c=Math.min(a.c,b.c);c<=Math.max(a.c,b.c);c++)out.push(evaluateCell(sheet,addr(r,c),new Set(stack)));return out;}
function flattenArgs(args,sheet,stack){return args.flatMap(v=>{const x=primitive(v,sheet,stack);return Array.isArray(x)?x:[x];});}
function tokenizer(src){const t=[];let i=0;while(i<src.length){const ch=src[i];if(/\s/.test(ch)){i++;continue;}if(ch==='"'){let s='';i++;while(i<src.length){if(src[i]==='"'&&src[i+1]==='"'){s+='"';i+=2;continue;}if(src[i]==='"'){i++;break;}s+=src[i++];}t.push({type:'str',v:s});continue;}const two=src.slice(i,i+2);if(['<=','>=','<>','!='].includes(two)){t.push({type:'op',v:two});i+=2;continue;}if(/[+\-*/^%=(),:;<>]/.test(ch)){t.push({type:'op',v:ch});i++;continue;}const nm=/^(?:\d+(?:[.,]\d+)?|[.,]\d+)/.exec(src.slice(i));if(nm){t.push({type:'num',v:Number(nm[0].replace(',','.'))});i+=nm[0].length;continue;}const id=/^[A-Za-z_À-ÿ][A-Za-z0-9_À-ÿ.]*/.exec(src.slice(i));if(id){t.push({type:'id',v:id[0]});i+=id[0].length;continue;}throw new Error('TOKEN');}return t;}
function formulaEval(sheet,source,stack){const tokens=tokenizer(source),p={i:0};const peek=()=>tokens[p.i];const take=(v)=>{const x=tokens[p.i];if(!x||(v&&x.v!==v))return null;p.i++;return x;};const unwrap=v=>primitive(v,sheet,stack);const num=v=>numeric(v,sheet,stack);
  function expression(){return comparison();}
  function comparison(){let left=add();while(peek()&&['=','<>','!=','<','>','<=','>='].includes(peek().v)){const op=take().v,right=add(),a=unwrap(left),b=unwrap(right);left=op==='='?a==b:(op==='<>'||op==='!=')?a!=b:op==='<'?a<b:op==='>'?a>b:op==='<='?a<=b:a>=b;}return left;}
  function add(){let left=mul();while(peek()&&['+','-'].includes(peek().v)){const op=take().v,right=mul();left=op==='+'?num(left)+num(right):num(left)-num(right);}return left;}
  function mul(){let left=power();while(peek()&&['*','/','%'].includes(peek().v)){const op=take().v,right=power(),a=num(left),b=num(right);left=op==='*'?a*b:op==='/'?(b===0?'#DIV/0!':a/b):a%b;}return left;}
  function power(){let left=unary();while(peek()&&peek().v==='^'){take('^');left=Math.pow(num(left),num(unary()));}return left;}
  function unary(){if(take('+'))return num(unary());if(take('-'))return -num(unary());return primary();}
  function primary(){const tk=peek();if(!tk)return 0;if(take('(')){const v=expression();if(!take(')'))throw new Error('PAREN');return v;}if(tk.type==='num'){p.i++;return tk.v;}if(tk.type==='str'){p.i++;return tk.v;}if(tk.type==='id'){p.i++;const name=tk.v.toUpperCase();if(take('(')){const args=[];if(!take(')')){do{args.push(expression());}while(take(',')||take(';'));if(!take(')'))throw new Error('PAREN');}return callFunction(name,args);}if(name==='TRUE'||name==='VERDADEIRO')return true;if(name==='FALSE'||name==='FALSO')return false;let ref=/^[A-Z]+\d+$/.test(name)?{__ref:true,addr:name}:name;if(ref.__ref&&take(':')){const other=peek();if(!other||other.type!=='id'||!/^[A-Z]+\d+$/i.test(other.v))throw new Error('RANGE');p.i++;ref={__range:true,start:ref.addr,end:other.v.toUpperCase()};}return ref;}throw new Error('PRIMARY');}
  function callFunction(name,args){const vals=flattenArgs(args,sheet,stack),nums=vals.map(v=>numeric(v,sheet,stack)).filter(Number.isFinite);const first=()=>unwrap(args[0]);switch(name){case'SUM':case'SOMA':return nums.reduce((a,b)=>a+b,0);case'AVERAGE':case'MÉDIA':case'MEDIA':return nums.length?nums.reduce((a,b)=>a+b,0)/nums.length:0;case'MIN':return nums.length?Math.min(...nums):0;case'MAX':return nums.length?Math.max(...nums):0;case'COUNT':case'CONT.NÚM':return vals.filter(v=>v!==''&&Number.isFinite(Number(v))).length;case'COUNTA':case'CONT.VALORES':return vals.filter(v=>v!==''&&v!=null).length;case'IF':case'SE':return primitive(args[0],sheet,stack)?primitive(args[1],sheet,stack):primitive(args[2],sheet,stack);case'ROUND':case'ARRED':{const n=num(args[0]),d=Math.trunc(num(args[1]??0));const m=10**d;return Math.round(n*m)/m;}case'ABS':return Math.abs(num(args[0]));case'INT':return Math.floor(num(args[0]));case'MOD':return num(args[0])%num(args[1]);case'POWER':case'POTÊNCIA':case'POTENCIA':return Math.pow(num(args[0]),num(args[1]));case'SQRT':case'RAIZ':return Math.sqrt(num(args[0]));case'CONCAT':return vals.join('');case'LEN':case'NÚM.CARACT':return String(first()??'').length;case'UPPER':case'MAIÚSCULA':return String(first()??'').toUpperCase();case'LOWER':case'MINÚSCULA':return String(first()??'').toLowerCase();case'TODAY':case'HOJE':return new Date().toISOString().slice(0,10);case'NOW':case'AGORA':return new Date().toLocaleString('pt-BR');default:return '#NAME?';}}
  const result=expression();if(p.i<tokens.length)throw new Error('TAIL');return primitive(result,sheet,stack);
}
function evaluateCell(sheet,a,stack){const cell=cellAt(a,sheet);if(!cell)return '';const raw=cell.raw??'';if(typeof raw!=='string')return raw;if(!raw.startsWith('=')){if(raw.trim()!==''&&!Number.isNaN(Number(raw.replace(',','.'))))return Number(raw.replace(',','.'));return raw;}if(stack.has(a))return '#CYCLE!';stack.add(a);try{return formulaEval(sheet,raw.slice(1),stack);}catch{return '#ERROR!';}}

function renderGrid(){const s=activeSheet();const frag=document.createDocumentFragment();const thead=document.createElement('thead');const hr=document.createElement('tr');const corner=document.createElement('th');corner.className='corner';hr.append(corner);for(let c=0;c<s.cols;c++){const th=document.createElement('th');th.textContent=colName(c);th.style.width=`${s.colWidths[c]||96}px`;th.style.minWidth=th.style.width;hr.append(th);}thead.append(hr);frag.append(thead);const tbody=document.createElement('tbody');for(let r=0;r<s.rows;r++){const tr=document.createElement('tr');const rh=document.createElement('th');rh.className='row-header';rh.textContent=r+1;if(s.rowHeights[r])rh.style.height=`${s.rowHeights[r]}px`;tr.append(rh);for(let c=0;c<s.cols;c++){const td=document.createElement('td');const a=addr(r,c);td.className='cell';td.dataset.r=r;td.dataset.c=c;td.dataset.addr=a;const cell=cellAt(a,s);td.textContent=cellDisplay(s,a);td.title=cell?.raw||'';td.style.width=`${s.colWidths[c]||96}px`;td.style.minWidth=td.style.width;td.style.maxWidth=td.style.width;if(s.rowHeights[r])td.style.height=`${s.rowHeights[r]}px`;applyCellStyle(td,cell?.style||{});tr.append(td);}tbody.append(tr);}frag.append(tbody);table.replaceChildren(frag);table.classList.toggle('no-gridlines',!state.gridlines);applyZoom();renderSelection();}
function applyCellStyle(td,st){td.style.fontWeight=st.bold?'700':'';td.style.fontStyle=st.italic?'italic':'';td.style.textDecoration=st.underline?'underline':'';td.style.textAlign=st.align||'';td.style.color=st.color||'';td.style.backgroundColor=st.fill||'';td.style.fontFamily=st.fontFamily||'';td.style.fontSize=st.fontSize?`${st.fontSize}px`:'';}
function renderSelection(){const x=normalizeRange();table.querySelectorAll('.cell.selected,.cell.range-selected').forEach(el=>el.classList.remove('selected','range-selected'));for(let r=x.r1;r<=x.r2;r++)for(let c=x.c1;c<=x.c2;c++){const td=table.querySelector(`[data-r="${r}"][data-c="${c}"]`);if(td)td.classList.add('range-selected');}const td=table.querySelector(`[data-r="${selection.end.r}"][data-c="${selection.end.c}"]`);if(td)td.classList.add('selected');updateFormulaBar();updateSelectionStats();updateFormatControls();}
function updateFormulaBar(){const a=selectedAddr();$('#nameBox').textContent=rangeAddresses().length>1?`${addr(normalizeRange().r1,normalizeRange().c1)}:${addr(normalizeRange().r2,normalizeRange().c2)}`:a;formulaInput.value=cellAt(a)?.raw||'';}
function updateSelectionStats(){const vals=rangeAddresses().map(a=>evaluateCell(activeSheet(),a,new Set())).filter(v=>v!==''&&v!=null);const nums=vals.map(Number).filter(Number.isFinite);let text=`${rangeAddresses().length} célula${rangeAddresses().length===1?'':'s'}`;if(nums.length)text+=` · Soma ${formatValue(nums.reduce((a,b)=>a+b,0),{format:'number'})} · Média ${formatValue(nums.reduce((a,b)=>a+b,0)/nums.length,{format:'number'})}`;$('#selectionStats').textContent=text;}
function updateFormatControls(){const st=cellAt(selectedAddr())?.style||{};$('#boldButton').classList.toggle('active',!!st.bold);$('#italicButton').classList.toggle('active',!!st.italic);$('#underlineButton').classList.toggle('active',!!st.underline);document.querySelectorAll('.align-button').forEach(b=>b.classList.toggle('active',b.dataset.align===(st.align||'left')));$('#fontFamily').value=st.fontFamily||'Arial';$('#fontSize').value=st.fontSize||12;$('#textColor').value=toColor(st.color||'#18302b');$('#fillColor').value=toColor(st.fill||'#ffffff');$('#numberFormat').value=st.format||'general';}
function toColor(v){return /^#[0-9a-f]{6}$/i.test(v)?v:'#18302b';}
function renderTabs(){sheetTabs.innerHTML='';state.sheets.forEach((s,i)=>{const b=document.createElement('button');b.className='sheet-tab'+(s.id===state.activeSheetId?' active':'');b.type='button';const label=document.createElement('span');label.textContent=s.name;label.ondblclick=e=>{e.stopPropagation();renameSheet(s.id)};const close=document.createElement('span');close.className='tab-close';close.textContent='×';close.onclick=e=>{e.stopPropagation();removeSheet(s.id)};b.append(label,close);b.onclick=()=>{state.activeSheetId=s.id;selection={start:{r:0,c:0},end:{r:0,c:0}};renderAll(false)};sheetTabs.append(b);});}
function renderAll(full=true){document.body.classList.toggle('dark',!!state.dark);if(full)renderGrid();else{renderGrid()}renderTabs();titleInput.value=state.title;updateUndoButtons();}

function setSelection(r,c,extend=false,scroll=true){const s=activeSheet();r=Math.max(0,Math.min(s.rows-1,r));c=Math.max(0,Math.min(s.cols-1,c));if(extend)selection.end={r,c};else selection={start:{r,c},end:{r,c}};renderSelection();if(scroll)table.querySelector(`[data-r="${r}"][data-c="${c}"]`)?.scrollIntoView({block:'nearest',inline:'nearest'});}
function startEdit(initial=null){if(editing)return;const td=table.querySelector(`[data-r="${selection.end.r}"][data-c="${selection.end.c}"]`);if(!td)return;editing=true;const rect=td.getBoundingClientRect();cellEditor.hidden=false;Object.assign(cellEditor.style,{left:`${rect.left}px`,top:`${rect.top}px`,width:`${Math.max(rect.width,110)}px`,height:`${rect.height}px`});cellEditor.value=initial!==null?initial:(cellAt(selectedAddr())?.raw||'');cellEditor.focus();cellEditor.select();}
function finishEdit(commit=true){if(!editing)return;const value=cellEditor.value;cellEditor.hidden=true;editing=false;if(commit){pushHistory();setRaw(activeSheet(),selectedAddr(),value);afterDataChange();}}
function afterDataChange(){renderGrid();scheduleSave();}
function commitFormula(){pushHistory();setRaw(activeSheet(),selectedAddr(),formulaInput.value);afterDataChange();}

function applyStyle(patch){pushHistory();for(const a of rangeAddresses()){const cell=ensureCell(a);cell.style={...(cell.style||{}),...patch};}renderGrid();scheduleSave();}
function clearFormat(){pushHistory();for(const a of rangeAddresses()){const cell=ensureCell(a);cell.style={};if(!cell.raw)delete activeSheet().cells[a];}renderGrid();scheduleSave();}
function clearContents(){pushHistory();for(const a of rangeAddresses()){const cell=cellAt(a);if(cell){cell.raw='';if(!Object.keys(cell.style||{}).length)delete activeSheet().cells[a];}}afterDataChange();}

function selectedMatrix(raw=true){const x=normalizeRange(),s=activeSheet(),rows=[];for(let r=x.r1;r<=x.r2;r++){const row=[];for(let c=x.c1;c<=x.c2;c++){const a=addr(r,c);row.push(raw?(cellAt(a)?.raw||''):cellDisplay(s,a));}rows.push(row);}return rows;}
async function copySelection(cut=false){const text=selectedMatrix(true).map(row=>row.join('\t')).join('\n');try{await navigator.clipboard.writeText(text);}catch{}window.__sheetClipboard=text;if(cut)clearContents();}
function parseTSV(text){return text.replace(/\r/g,'').split('\n').map(r=>r.split('\t'));}
function pasteText(text){if(!text)return;const matrix=parseTSV(text);pushHistory();const s=activeSheet(),base=selection.end;matrix.forEach((row,ri)=>row.forEach((v,ci)=>{const r=base.r+ri,c=base.c+ci;if(r<s.rows&&c<s.cols)setRaw(s,addr(r,c),v);}));afterDataChange();}
async function pasteSelection(){let text='';try{text=await navigator.clipboard.readText();}catch{}pasteText(text||window.__sheetClipboard||'');}

function addSheet(){pushHistory();let n=state.sheets.length+1,name=`Planilha${n}`;while(state.sheets.some(s=>s.name===name))name=`Planilha${++n}`;const s={id:nowId(),name,rows:DEFAULT_ROWS,cols:DEFAULT_COLS,cells:{},colWidths:{},rowHeights:{}};state.sheets.push(s);state.activeSheetId=s.id;selection={start:{r:0,c:0},end:{r:0,c:0}};renderAll();scheduleSave();}
function renameSheet(id){const s=state.sheets.find(x=>x.id===id);if(!s)return;const next=prompt('Nome da aba:',s.name)?.trim();if(!next||next===s.name)return;pushHistory();s.name=next.slice(0,31);renderTabs();scheduleSave();}
function removeSheet(id){if(state.sheets.length===1)return alert('A planilha precisa ter pelo menos uma aba.');const s=state.sheets.find(x=>x.id===id);if(!confirm(`Excluir a aba “${s?.name||''}”?`))return;pushHistory();state.sheets=state.sheets.filter(x=>x.id!==id);ensureActiveSheet();selection={start:{r:0,c:0},end:{r:0,c:0}};renderAll();scheduleSave();}
function addRow(){pushHistory();activeSheet().rows=Math.min(300,activeSheet().rows+1);renderGrid();scheduleSave();}
function addColumn(){pushHistory();activeSheet().cols=Math.min(52,activeSheet().cols+1);renderGrid();scheduleSave();}

function autoSum(){const x=normalizeRange();let target,range;if(x.r1!==x.r2||x.c1!==x.c2){target=addr(x.r2+1,x.c1);range=`${addr(x.r1,x.c1)}:${addr(x.r2,x.c1)}`;}else{const c=x.c1,r=x.r1;let start=r-1;while(start>=0&&cellAt(addr(start,c)))start--;start++;target=addr(r,c);range=`${addr(start,c)}:${addr(Math.max(start,r-1),c)}`;}const p=parseAddr(target);if(!p||p.r>=activeSheet().rows)return;pushHistory();setRaw(activeSheet(),target,`=SUM(${range})`,{bold:true});setSelection(p.r,p.c);afterDataChange();}
function sortSelection(desc=false){const x=normalizeRange();if(x.r1===x.r2)return;pushHistory();const s=activeSheet(),rows=[];for(let r=x.r1;r<=x.r2;r++){const row=[];for(let c=x.c1;c<=x.c2;c++)row.push(clone(cellAt(addr(r,c))||{raw:'',style:{}}));rows.push(row);}rows.sort((a,b)=>{const av=String(a[0]?.raw??''),bv=String(b[0]?.raw??'');const an=Number(av),bn=Number(bv);const cmp=Number.isFinite(an)&&Number.isFinite(bn)?an-bn:av.localeCompare(bv,'pt-BR',{numeric:true});return desc?-cmp:cmp;});rows.forEach((row,ri)=>row.forEach((cell,ci)=>{const a=addr(x.r1+ri,x.c1+ci);if(cell.raw||Object.keys(cell.style||{}).length)s.cells[a]=cell;else delete s.cells[a];}));afterDataChange();}
function removeDuplicates(){const x=normalizeRange();if(x.r1===x.r2)return;pushHistory();const s=activeSheet(),seen=new Set(),kept=[];for(let r=x.r1;r<=x.r2;r++){const row=[];const key=[];for(let c=x.c1;c<=x.c2;c++){const cell=clone(cellAt(addr(r,c))||{raw:'',style:{}});row.push(cell);key.push(cell.raw??'');}const k=JSON.stringify(key);if(!seen.has(k)){seen.add(k);kept.push(row);}}for(let r=x.r1;r<=x.r2;r++)for(let c=x.c1;c<=x.c2;c++)delete s.cells[addr(r,c)];kept.forEach((row,ri)=>row.forEach((cell,ci)=>{if(cell.raw||Object.keys(cell.style||{}).length)s.cells[addr(x.r1+ri,x.c1+ci)]=cell;}));afterDataChange();}

function parseCSV(text){const rows=[];let row=[],field='',quote=false;for(let i=0;i<text.length;i++){const ch=text[i];if(quote){if(ch==='"'&&text[i+1]==='"'){field+='"';i++;}else if(ch==='"')quote=false;else field+=ch;}else if(ch==='"')quote=true;else if(ch===','||ch===';'){row.push(field);field='';}else if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}else field+=ch;}row.push(field.replace(/\r$/,''));if(row.some(v=>v!==''))rows.push(row);return rows;}
function csvEscape(v){const s=String(v??'');return /[",;\n]/.test(s)?`"${s.replaceAll('"','""')}"`:s;}
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1200);}
function usedRange(sheet){let maxR=0,maxC=0,has=false;for(const a of Object.keys(sheet.cells)){const p=parseAddr(a);if(!p)continue;has=true;maxR=Math.max(maxR,p.r);maxC=Math.max(maxC,p.c);}return has?{r2:maxR,c2:maxC}:{r2:0,c2:0};}
function exportCSV(){const s=activeSheet(),u=usedRange(s),rows=[];for(let r=0;r<=u.r2;r++){const row=[];for(let c=0;c<=u.c2;c++)row.push(csvEscape(cellDisplay(s,addr(r,c))));rows.push(row.join(';'));}downloadBlob(new Blob(['\ufeff'+rows.join('\r\n')],{type:'text/csv;charset=utf-8'}),`${safeName(state.title)}-${safeName(s.name)}.csv`);}
function exportHTML(){let html='<!doctype html><meta charset="utf-8"><title>'+escapeHtml(state.title)+'</title><style>body{font-family:Arial}table{border-collapse:collapse;margin:0 0 32px}td,th{border:1px solid #ccc;padding:6px 9px}h2{margin-top:28px}</style><h1>'+escapeHtml(state.title)+'</h1>';for(const s of state.sheets){const u=usedRange(s);html+=`<h2>${escapeHtml(s.name)}</h2><table>`;for(let r=0;r<=u.r2;r++){html+='<tr>';for(let c=0;c<=u.c2;c++)html+=`<td>${escapeHtml(cellDisplay(s,addr(r,c)))}</td>`;html+='</tr>';}html+='</table>';}downloadBlob(new Blob([html],{type:'text/html;charset=utf-8'}),`${safeName(state.title)}.html`);}
function exportXls(){let tables='';for(const s of state.sheets){const u=usedRange(s);tables+=`<h2>${escapeHtml(s.name)}</h2><table>`;for(let r=0;r<=u.r2;r++){tables+='<tr>';for(let c=0;c<=u.c2;c++)tables+=`<td>${escapeHtml(cellDisplay(s,addr(r,c)))}</td>`;tables+='</tr>';}tables+='</table>';}const html=`<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8"></head><body>${tables}</body></html>`;downloadBlob(new Blob(['\ufeff'+html],{type:'application/vnd.ms-excel'}),`${safeName(state.title)}.xls`);}
function exportJSON(){downloadBlob(new Blob([JSON.stringify({app:'InkSheet',version:1,state},null,2)],{type:'application/json'}),`${safeName(state.title)}.json`);}
function safeName(s){return String(s||'planilha').replace(/[\\/:*?"<>|]+/g,'-').trim()||'planilha';}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}

function scheduleSave(){saveState.textContent='Alterações não salvas';clearTimeout(autosaveTimer);autosaveTimer=setTimeout(()=>saveProject(false),650);}
async function saveProject(show=true){if(!state)return;state.title=titleInput.value.trim()||'Minha planilha';const saved=await SheetDB.putProject({id:projectId,title:state.title,createdAt:projectCreatedAt,state});projectId=saved.id;projectCreatedAt=saved.createdAt;localStorage.setItem('planilha-studio-last-project',projectId);saveState.textContent='Salvo';if(show)flashStatus('Salvo agora');}
function flashStatus(text){saveState.textContent=text;setTimeout(()=>{if(saveState.textContent===text)saveState.textContent='Salvo';},1200);}

function findText(replaceMode=false){const term=prompt('Localizar:');if(term==null||term==='')return;findMatches=[];for(const s of state.sheets)for(const [a,cell] of Object.entries(s.cells))if(String(cell.raw??'').toLowerCase().includes(term.toLowerCase()))findMatches.push({sheetId:s.id,a});if(!findMatches.length)return alert('Nenhuma ocorrência encontrada.');if(replaceMode){const rep=prompt('Substituir por:','')??'';pushHistory();for(const m of findMatches){const s=state.sheets.find(x=>x.id===m.sheetId),cell=s.cells[m.a];cell.raw=String(cell.raw??'').replaceAll(term,rep);}renderAll();scheduleSave();alert(`${findMatches.length} ocorrência(s) substituída(s).`);return;}findIndex=(findIndex+1)%findMatches.length;const m=findMatches[findIndex];state.activeSheetId=m.sheetId;const p=parseAddr(m.a);setSelection(p.r,p.c);renderAll();setTimeout(()=>table.querySelector(`[data-addr="${m.a}"]`)?.classList.add('match'),0);}

function chartData(){const m=selectedMatrix(false);const labels=[],values=[];for(const row of m){if(row.length<2)continue;const n=Number(String(row[1]).replace(/[^0-9,.-]/g,'').replace(',','.'));if(Number.isFinite(n)){labels.push(String(row[0]||`Item ${labels.length+1}`));values.push(n);}}return{labels,values};}
function drawChart(){const canvas=$('#chartCanvas'),ctx=canvas.getContext('2d'),{labels,values}=chartData(),type=$('#chartType').value;ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);if(!values.length){ctx.fillStyle='#667b75';ctx.font='18px Arial';ctx.fillText('Selecione duas colunas: rótulos + valores.',40,60);return;}const pad={l:70,r:30,t:35,b:90},w=canvas.width-pad.l-pad.r,h=canvas.height-pad.t-pad.b,max=Math.max(...values.map(Math.abs),1);const colors=['#0f766e','#ed7b5d','#c99c4c','#5f7db9','#8b65a7','#4c9a6a'];ctx.strokeStyle='#dbe8e4';ctx.fillStyle='#667b75';ctx.font='12px Arial';if(type==='pie'){const total=values.reduce((a,b)=>a+Math.abs(b),0)||1,cx=canvas.width/2,cy=canvas.height/2,r=Math.min(w,h)*.38;let angle=-Math.PI/2;values.forEach((v,i)=>{const da=Math.abs(v)/total*Math.PI*2;ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,angle,angle+da);ctx.closePath();ctx.fillStyle=colors[i%colors.length];ctx.fill();angle+=da;});labels.slice(0,8).forEach((l,i)=>{ctx.fillStyle=colors[i%colors.length];ctx.fillRect(20,20+i*22,12,12);ctx.fillStyle='#18302b';ctx.fillText(l,40,30+i*22);});return;}ctx.beginPath();ctx.moveTo(pad.l,pad.t);ctx.lineTo(pad.l,pad.t+h);ctx.lineTo(pad.l+w,pad.t+h);ctx.stroke();const step=w/Math.max(values.length,1);if(type==='bar'){values.forEach((v,i)=>{const bh=Math.abs(v)/max*h,bw=Math.max(8,step*.62),x=pad.l+i*step+(step-bw)/2,y=pad.t+h-bh;ctx.fillStyle=colors[i%colors.length];ctx.fillRect(x,y,bw,bh);ctx.save();ctx.translate(x+bw/2,pad.t+h+12);ctx.rotate(-.55);ctx.fillStyle='#667b75';ctx.textAlign='right';ctx.fillText(labels[i].slice(0,20),0,0);ctx.restore();});}else{ctx.beginPath();values.forEach((v,i)=>{const x=pad.l+i*(w/Math.max(values.length-1,1)),y=pad.t+h-(v/max*h);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle='#0f766e';ctx.lineWidth=3;ctx.stroke();values.forEach((v,i)=>{const x=pad.l+i*(w/Math.max(values.length-1,1)),y=pad.t+h-(v/max*h);ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fillStyle=colors[i%colors.length];ctx.fill();ctx.save();ctx.translate(x,pad.t+h+12);ctx.rotate(-.55);ctx.fillStyle='#667b75';ctx.textAlign='right';ctx.fillText(labels[i].slice(0,20),0,0);ctx.restore();});}}
function openChart(){drawChart();$('#chartDialog').showModal();}

function setZoom(next){zoom=Math.max(.6,Math.min(1.6,next));applyZoom();$('#zoomLabel').textContent=`${Math.round(zoom*100)}%`;}
function applyZoom(){table.style.zoom=zoom;}
function toggleTheme(){state.dark=!state.dark;document.body.classList.toggle('dark',state.dark);scheduleSave();}

function bindMenus(){document.querySelectorAll('[data-menu-target]').forEach(btn=>btn.addEventListener('click',e=>{e.stopPropagation();const target=$(`#${btn.dataset.menuTarget}`);document.querySelectorAll('.top-menu').forEach(m=>{if(m!==target)m.hidden=true});target.hidden=!target.hidden;}));document.addEventListener('click',()=>document.querySelectorAll('.top-menu').forEach(m=>m.hidden=true));document.querySelectorAll('.top-menu').forEach(m=>m.addEventListener('click',e=>e.stopPropagation()));}

viewport.addEventListener('mousedown',e=>{const td=e.target.closest('.cell');if(!td)return;const r=+td.dataset.r,c=+td.dataset.c;setSelection(r,c,e.shiftKey,false);if(e.detail===2)startEdit();});
viewport.addEventListener('scroll',()=>{if(editing)finishEdit(true)});
cellEditor.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();finishEdit(true);setSelection(selection.end.r+1,selection.end.c);}else if(e.key==='Escape'){e.preventDefault();finishEdit(false);}else if(e.key==='Tab'){e.preventDefault();finishEdit(true);setSelection(selection.end.r,selection.end.c+(e.shiftKey?-1:1));}});cellEditor.addEventListener('blur',()=>finishEdit(true));
formulaInput.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();commitFormula();viewport.focus();}else if(e.key==='Escape')updateFormulaBar();});
document.addEventListener('keydown',e=>{if(editing||e.target===formulaInput||e.target.matches('input,select'))return;const ctrl=e.ctrlKey||e.metaKey;if(ctrl&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo();return;}if(ctrl&&e.key.toLowerCase()==='y'){e.preventDefault();redo();return;}if(ctrl&&e.key.toLowerCase()==='c'){e.preventDefault();copySelection(false);return;}if(ctrl&&e.key.toLowerCase()==='x'){e.preventDefault();copySelection(true);return;}if(ctrl&&e.key.toLowerCase()==='v'){e.preventDefault();pasteSelection();return;}if(ctrl&&e.key.toLowerCase()==='s'){e.preventDefault();saveProject(true);return;}if(ctrl&&e.key.toLowerCase()==='f'){e.preventDefault();findText(false);return;}if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();clearContents();return;}if(e.key==='F2'){e.preventDefault();startEdit();return;}const move={ArrowUp:[-1,0],ArrowDown:[1,0],ArrowLeft:[0,-1],ArrowRight:[0,1]};if(move[e.key]){e.preventDefault();setSelection(selection.end.r+move[e.key][0],selection.end.c+move[e.key][1],e.shiftKey);return;}if(e.key==='Enter'){e.preventDefault();setSelection(selection.end.r+1,selection.end.c);return;}if(e.key==='Tab'){e.preventDefault();setSelection(selection.end.r,selection.end.c+(e.shiftKey?-1:1));return;}if(e.key.length===1&&!ctrl&&!e.altKey){e.preventDefault();startEdit(e.key);}});
document.addEventListener('paste',e=>{if(editing||e.target===formulaInput)return;const text=e.clipboardData?.getData('text/plain');if(text){e.preventDefault();pasteText(text);}});

titleInput.addEventListener('change',()=>{pushHistory();state.title=titleInput.value.trim()||'Minha planilha';scheduleSave();});
$('#boldButton').onclick=()=>applyStyle({bold:!$('#boldButton').classList.contains('active')});
$('#italicButton').onclick=()=>applyStyle({italic:!$('#italicButton').classList.contains('active')});
$('#underlineButton').onclick=()=>applyStyle({underline:!$('#underlineButton').classList.contains('active')});
document.querySelectorAll('.align-button').forEach(b=>b.onclick=()=>applyStyle({align:b.dataset.align}));
$('#fontFamily').onchange=e=>applyStyle({fontFamily:e.target.value});$('#fontSize').onchange=e=>applyStyle({fontSize:+e.target.value||12});$('#textColor').onchange=e=>applyStyle({color:e.target.value});$('#fillColor').onchange=e=>applyStyle({fill:e.target.value});$('#numberFormat').onchange=e=>applyStyle({format:e.target.value});$('#clearFormatButton').onclick=clearFormat;$('#autoSumButton').onclick=autoSum;$('#chartButton').onclick=openChart;
$('#addSheetButton').onclick=addSheet;$('#zoomInButton').onclick=()=>setZoom(zoom+.1);$('#zoomOutButton').onclick=()=>setZoom(zoom-.1);
$('#undoButton').onclick=undo;$('#redoButton').onclick=redo;$('#saveProjectButton').onclick=()=>saveProject(true);$('#exportButton').onclick=exportCSV;

$('#menuNew').onclick=()=>{if(confirm('Criar uma nova planilha? Alterações salvas continuarão nos projetos recentes.'))location.href='index.html';};$('#menuSave').onclick=()=>saveProject(true);$('#menuImportCsv').onclick=()=>$('#csvFileInput').click();$('#menuImportJson').onclick=()=>$('#jsonFileInput').click();$('#menuDownloadJson').onclick=exportJSON;$('#menuExportCsv').onclick=exportCSV;$('#menuExportXls').onclick=exportXls;$('#menuExportHtml').onclick=exportHTML;$('#menuPrint').onclick=()=>window.print();$('#menuUndo').onclick=undo;$('#menuRedo').onclick=redo;$('#menuCopy').onclick=()=>copySelection(false);$('#menuCut').onclick=()=>copySelection(true);$('#menuPaste').onclick=pasteSelection;$('#menuDelete').onclick=clearContents;$('#menuFind').onclick=()=>findText(false);$('#menuReplace').onclick=()=>findText(true);$('#menuAddRow').onclick=addRow;$('#menuAddColumn').onclick=addColumn;$('#menuAddSheet').onclick=addSheet;$('#menuChart').onclick=openChart;$('#menuSortAsc').onclick=()=>sortSelection(false);$('#menuSortDesc').onclick=()=>sortSelection(true);$('#menuRemoveDuplicates').onclick=removeDuplicates;$('#menuAutoSum').onclick=autoSum;$('#menuZoomIn').onclick=()=>setZoom(zoom+.1);$('#menuZoomOut').onclick=()=>setZoom(zoom-.1);$('#menuZoomReset').onclick=()=>setZoom(1);$('#menuGridlines').onclick=()=>{state.gridlines=!state.gridlines;renderGrid();scheduleSave();};$('#menuTheme').onclick=toggleTheme;

$('#csvFileInput').onchange=async e=>{const file=e.target.files[0];if(!file)return;const rows=parseCSV(await file.text());pushHistory();const s=activeSheet();s.cells={};s.rows=Math.max(DEFAULT_ROWS,rows.length+5);s.cols=Math.max(DEFAULT_COLS,Math.min(52,Math.max(...rows.map(r=>r.length),1)+3));rows.forEach((row,r)=>row.forEach((v,c)=>setRaw(s,addr(r,c),v)));renderGrid();scheduleSave();e.target.value='';};
$('#jsonFileInput').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const parsed=JSON.parse(await file.text());const next=parsed.state||parsed;if(!next?.sheets?.length)throw new Error('Formato inválido');pushHistory();state=next;projectId=null;projectCreatedAt=null;ensureActiveSheet();renderAll();scheduleSave();}catch(error){alert('Não foi possível abrir esse projeto.');console.error(error)}e.target.value='';};
$('#chartClose').onclick=()=>$('#chartDialog').close();$('#chartType').onchange=drawChart;$('#chartDownload').onclick=()=>$('#chartCanvas').toBlob(blob=>blob&&downloadBlob(blob,'grafico.png'),'image/png');

bindMenus();

(async function init(){const params=new URLSearchParams(location.search),id=params.get('project'),newName=params.get('new'),template=params.get('template')||'blank';if(id){const p=await SheetDB.getProject(id).catch(()=>null);if(p){projectId=p.id;projectCreatedAt=p.createdAt;state=p.state;state.title=p.title||state.title;}}if(!state){setTemplate(template,newName||'Minha planilha');}ensureActiveSheet();renderAll();setZoom(1);if(!projectId)await saveProject(false);})();
