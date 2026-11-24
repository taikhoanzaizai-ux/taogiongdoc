(function(root){
'use strict';
const defaults={mode:'light',accent:'#2563eb',contrast:true,scale:1};
const palette=[{name:'Xanh dương',color:'#2563eb'},{name:'Xanh ngọc',color:'#0f766e'},{name:'Tím',color:'#7c3aed'},{name:'Cam',color:'#c2410c'},{name:'Hồng',color:'#be185d'},{name:'Xám',color:'#475569'}];
function rgb(hex){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16))}
function lum(hex){const c=rgb(hex).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return c[0]*.2126+c[1]*.7152+c[2]*.0722}
function ratio(a,b){const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
function mix(a,b,t){return '#'+rgb(a).map((v,i)=>Math.round(v*(1-t)+rgb(b)[i]*t).toString(16).padStart(2,'0')).join('')}
function sanitize(value){return {mode:['light','dark','system'].includes(value?.mode)?value.mode:'light',accent:/^#[a-f\d]{6}$/i.test(value?.accent||'')?value.accent:defaults.accent,contrast:typeof value?.contrast==='boolean'?value.contrast:defaults.contrast,scale:[1,1.1,1.2].includes(Number(value?.scale))?Number(value.scale):1}}
let state={...defaults};try{state=sanitize(JSON.parse(localStorage.getItem('qv-theme-v1')||'null'))}catch{}
const media=root.matchMedia?root.matchMedia('(prefers-color-scheme: dark)'):null;
function colors(mode,accent){const dark=mode==='dark';const bg=dark?'#101827':'#f4f6fa',surface=dark?'#192437':'#ffffff';let ink=accent;for(let i=0;ratio(ink,surface)<4.5&&i<30;i++)ink=mix(ink,dark?'#ffffff':'#000000',.1);return {'--bg':bg,'--surface':surface,'--surface-soft':dark?'#223149':'#edf2f8','--ink':dark?'#f1f5f9':'#172033','--text-secondary':dark?'#c3cddd':'#475569','--muted':dark?'#b3c0d3':'#526276','--line':state.contrast?(dark?'#71829a':'#a5b3c6'):(dark?'#3b4d64':'#d7dfe9'),'--purple':ink,'--accent':accent,'--purple-dark':mix(accent,'#000000',.14),'--accent-on':ratio(accent,'#ffffff')>=4.5?'#ffffff':'#101827','--soft':mix(surface,accent,dark?.17:.09),'--green':dark?'#80d8bb':'#13654f','--orange':dark?'#f0c68a':'#7d4e13','--ui-scale':String(state.scale)}}
function apply(){const mode=state.mode==='system'?(media?.matches?'dark':'light'):state.mode;const el=document.documentElement;el.dataset.theme=mode;el.dataset.contrast=state.contrast?'high':'normal';el.style.colorScheme=mode;Object.entries(colors(mode,state.accent)).forEach(([k,v])=>el.style.setProperty(k,v));}
function set(patch){state=sanitize({...state,...patch});try{localStorage.setItem('qv-theme-v1',JSON.stringify(state))}catch{}apply();if(root.dispatchEvent&&typeof Event!=='undefined')root.dispatchEvent(new Event('qv-appearance'));return {...state}}
apply();media?.addEventListener('change',()=>{if(state.mode==='system')apply()});root.addEventListener('storage',e=>{if(e.key==='qv-theme-v1'){try{state=sanitize(JSON.parse(e.newValue));apply()}catch{}}});
root.QVTheme={get:()=>({...state}),set,reset:()=>set(defaults),palette,ratio,colors};
})(window);
