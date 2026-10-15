const before = document.querySelector("#before");
const after = document.querySelector("#after");
const output = document.querySelector("#diff");
const status = document.querySelector("#status");
let unified = "";

function normalized(value) {
  let result = value;
  if (document.querySelector("#ignore-space").checked) result = result.trim().replace(/\s+/g, " ");
  if (document.querySelector("#ignore-case").checked) result = result.toLocaleLowerCase("pt-BR");
  return result;
}

function calculateDiff(left, right) {
  const a = left.split(/\r?\n/), b = right.split(/\r?\n/);
  if (a.length > 1500 || b.length > 1500) throw new Error("Limite de 1.500 linhas por lado excedido.");
  const rows = Array.from({ length: a.length + 1 }, () => new Uint16Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i -= 1) for (let j = b.length - 1; j >= 0; j -= 1) rows[i][j] = normalized(a[i]) === normalized(b[j]) ? rows[i+1][j+1]+1 : Math.max(rows[i+1][j], rows[i][j+1]);
  const changes=[];let i=0,j=0,oldLine=1,newLine=1;
  while(i<a.length||j<b.length){
    if(i<a.length&&j<b.length&&normalized(a[i])===normalized(b[j])){changes.push({type:"same",text:a[i],old:oldLine++,new:newLine++});i++;j++;}
    else if(j<b.length&&(i===a.length||rows[i][j+1]>=rows[i+1][j])){changes.push({type:"add",text:b[j],old:null,new:newLine++});j++;}
    else{changes.push({type:"remove",text:a[i],old:oldLine++,new:null});i++;}
  }
  return changes;
}

function compare() {
  try {
    const changes=calculateDiff(before.value,after.value);output.replaceChildren();
    let add=0,remove=0,same=0;const lines=["--- anterior","+++ nova"];
    for(const change of changes){
      if(change.type==="add")add++;else if(change.type==="remove")remove++;else same++;
      const row=document.createElement("div");row.className=`diff-line ${change.type}`;
      const number=document.createElement("span");number.className="number";number.textContent=`${change.old??""}${change.old||change.new?"→":""}${change.new??""}`;
      const sign=document.createElement("span");sign.className="sign";sign.textContent=change.type==="add"?"+":change.type==="remove"?"−":" ";
      const text=document.createElement("span");text.textContent=change.text||" ";row.append(number,sign,text);output.append(row);
      lines.push(`${change.type==="add"?"+":change.type==="remove"?"-":" "}${change.text}`);
    }
    unified=lines.join("\n");document.querySelector("#added").textContent=add;document.querySelector("#removed").textContent=remove;document.querySelector("#unchanged").textContent=same;
    status.textContent=add||remove?`${add+remove} alterações encontradas.`:"Os textos são equivalentes com as opções atuais.";status.className="tool-status success";
    document.querySelector("#result-card").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(error){status.textContent=error.message;status.className="tool-status error";}
}

document.querySelector("#compare").addEventListener("click",compare);
document.querySelector("#before-file").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;before.value=await file.text();event.target.value="";compare()});
document.querySelectorAll("[data-clear]").forEach(button=>button.addEventListener("click",()=>{document.querySelector(`#${button.dataset.clear}`).value=""}));
document.querySelector("#copy").addEventListener("click",async()=>{if(!unified)return;try{await navigator.clipboard.writeText(unified);status.textContent="Diff copiado.";status.className="tool-status success"}catch{status.textContent="Não foi possível copiar.";status.className="tool-status error"}});
document.querySelector("#download").addEventListener("click",()=>{if(!unified)return;const link=document.createElement("a");link.href=URL.createObjectURL(new Blob([unified],{type:"text/x-diff"}));link.download="alteracoes.diff";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),0)});
before.value="const tema = 'claro';\nconst versao = 1;\nconsole.log(tema);";after.value="const tema = 'escuro';\nconst versao = 2;\nconsole.log(tema);";compare();
