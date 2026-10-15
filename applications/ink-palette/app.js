const colorInput = document.querySelector("#color");
const hexInput = document.querySelector("#hex");
const preview = document.querySelector("#preview");
const shades = document.querySelector("#shades");
const harmonies = document.querySelector("#harmonies");
const formats = document.querySelector("#formats");
const cssOutput = document.querySelector("#css-output");
const shadeStops = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900];

function normalizeHex(value) {
  const raw = String(value).trim().replace(/^#/, "");
  if (/^[0-9a-f]{3}$/i.test(raw)) return `#${raw.split("").map((item) => item + item).join("")}`.toUpperCase();
  return /^[0-9a-f]{6}$/i.test(raw) ? `#${raw.toUpperCase()}` : null;
}
function hexToRgb(hex) { const value = Number.parseInt(hex.slice(1), 16); return { r: value >> 16, g: value >> 8 & 255, b: value & 255 }; }
function rgbToHex({ r, g, b }) { return `#${[r,g,b].map((value) => Math.round(value).toString(16).padStart(2,"0")).join("")}`.toUpperCase(); }
function mix(hex, target, amount) { const a = hexToRgb(hex), b = hexToRgb(target); return rgbToHex({ r: a.r + (b.r-a.r)*amount, g: a.g + (b.g-a.g)*amount, b: a.b + (b.b-a.b)*amount }); }
function rgbToHsl({ r, g, b }) {
  r/=255; g/=255; b/=255; const max=Math.max(r,g,b), min=Math.min(r,g,b); let h=0, s=0; const l=(max+min)/2;
  if(max!==min){const d=max-min;s=l>.5?d/(2-max-min):d/(max+min);switch(max){case r:h=(g-b)/d+(g<b?6:0);break;case g:h=(b-r)/d+2;break;default:h=(r-g)/d+4;}h*=60;}
  return { h:Math.round(h), s:Math.round(s*100), l:Math.round(l*100) };
}
function hslToHex(h, s, l) {
  s/=100;l/=100;const c=(1-Math.abs(2*l-1))*s,x=c*(1-Math.abs(h/60%2-1)),m=l-c/2;let r=0,g=0,b=0;
  if(h<60){r=c;g=x}else if(h<120){r=x;g=c}else if(h<180){g=c;b=x}else if(h<240){g=x;b=c}else if(h<300){r=x;b=c}else{r=c;b=x}
  return rgbToHex({r:(r+m)*255,g:(g+m)*255,b:(b+m)*255});
}
function contrastColor(hex) { const {r,g,b}=hexToRgb(hex); return (r*299+g*587+b*114)/1000 > 155 ? "#202124" : "#FFFFFF"; }

async function copy(value) {
  try { await navigator.clipboard.writeText(value); formats.textContent = `${value} copiado.`; formats.className = "tool-status success"; }
  catch { formats.textContent = "Não foi possível copiar."; formats.className = "tool-status error"; }
}
function swatch(label, value) {
  const button = document.createElement("button"); button.type="button"; button.className="swatch"; button.style.setProperty("--swatch",value); button.style.setProperty("--swatch-text",contrastColor(value));
  const strong=document.createElement("strong");strong.textContent=label;const small=document.createElement("small");small.textContent=value;button.append(strong,small);button.addEventListener("click",()=>copy(value));return button;
}
function render(value) {
  const hex = normalizeHex(value); if(!hex){formats.textContent="Digite uma cor HEX válida.";formats.className="tool-status error";return;}
  colorInput.value=hex;hexInput.value=hex;preview.style.setProperty("--chosen",hex);
  const rgb=hexToRgb(hex),hsl=rgbToHsl(rgb);formats.textContent=`HEX ${hex} · RGB ${rgb.r}, ${rgb.g}, ${rgb.b} · HSL ${hsl.h}°, ${hsl.s}%, ${hsl.l}%`;formats.className="tool-status success";
  const values=shadeStops.map((stop,index)=> index<5?mix(hex,"#FFFFFF",.9-index*.18):index===5?hex:mix(hex,"#000000",(index-5)*.14));
  shades.replaceChildren(...values.map((item,index)=>swatch(String(shadeStops[index]),item)));
  const harmonyItems=[
    ["Base",hex],["Complementar",hslToHex((hsl.h+180)%360,hsl.s,hsl.l)],
    ["Análoga −30°",hslToHex((hsl.h+330)%360,hsl.s,hsl.l)],["Análoga +30°",hslToHex((hsl.h+30)%360,hsl.s,hsl.l)],
    ["Triádica +120°",hslToHex((hsl.h+120)%360,hsl.s,hsl.l)],["Triádica +240°",hslToHex((hsl.h+240)%360,hsl.s,hsl.l)],
  ];
  harmonies.replaceChildren(...harmonyItems.map(([label,item])=>swatch(label,item)));
  cssOutput.value=`:root {\n${values.map((item,index)=>`  --ink-${shadeStops[index]}: ${item};`).join("\n")}\n  --ink-rgb: ${rgb.r}, ${rgb.g}, ${rgb.b};\n  --ink-hsl: ${hsl.h}, ${hsl.s}%, ${hsl.l}%;\n  --ink-complementary: ${harmonyItems[1][1]};\n}`;
}
colorInput.addEventListener("input",()=>render(colorInput.value));hexInput.addEventListener("input",()=>{const valid=normalizeHex(hexInput.value);if(valid)render(valid)});
document.querySelector("#random").addEventListener("click",()=>render(`#${Math.floor(Math.random()*0xFFFFFF).toString(16).padStart(6,"0")}`));
document.querySelector("#copy-css").addEventListener("click",()=>copy(cssOutput.value));
document.querySelector("#download-css").addEventListener("click",()=>{const link=document.createElement("a");link.href=URL.createObjectURL(new Blob([cssOutput.value],{type:"text/css"}));link.download="ink-palette.css";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),0)});
render(colorInput.value);
