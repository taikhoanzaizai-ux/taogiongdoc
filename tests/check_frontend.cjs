const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=__dirname+'/../dist/';
const dummy={addEventListener(){},setAttribute(){},classList:{add(){},remove(){}},innerHTML:'',textContent:''};
const stored={};const styles={};const doc={documentElement:{dataset:{},style:{setProperty:(k,v)=>styles[k]=v}},querySelector:()=>dummy,addEventListener(){},querySelectorAll:()=>[]};
const window={addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
const ctx={document:doc,window,localStorage:{getItem:k=>stored[k]||null,setItem:(k,v)=>stored[k]=v},setTimeout,clearTimeout,console,URL,Blob,AbortSignal};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(root+'theme.js','utf8'),ctx);
let source=fs.readFileSync(root+'app.js','utf8');source=source.slice(0,source.lastIndexOf('(async()=>'));vm.runInContext(source,ctx);
ctx.catalog=JSON.parse(fs.readFileSync(root+'engines.json','utf8'));ctx.banks=JSON.parse(fs.readFileSync(root+'presets.json','utf8'));
vm.runInContext(`
S.engines=catalog;S.banks=banks;
for(const view of [studio,clone,transcribe,voices,models,history,settings]){const html=view();if(!html||html.includes('undefined'))throw Error('Invalid rendered view: '+view.name);}
for(const e of S.engines.filter(e=>e.kind==='tts')){S.engine=e.id;S.language=e.languages[0];ensurePreset();const html=studio();if(!html.includes(e.name))throw Error('Missing model');}
S.engine='vieneu';S.engines[0].config={variant:'v3nano'};ensurePreset();if(!nativeChoices().some(v=>v.id===S.preset)||nativeChoices().length!==11)throw Error('Nano selection invalid');
S.engines[0].config.variant='v3turbo';S.preset='Hải Đăng';ensurePreset();if(nativeChoices().length!==25||S.preset!=='Hải Đăng')throw Error('Turbo selection invalid');
S.engine='vibevoice';S.language='ja';ensurePreset();if(nativeChoices().some(v=>v.language!=='ja')||!S.preset.startsWith('jp-'))throw Error('Vibe language routing failed');
S.libraryTab='uploaded';if(!voices().includes('Giọng bạn đã lưu'))throw Error('Library tabs missing');
if(esc('<img onerror="bad">').includes('<'))throw Error('Escaping failed');
`,ctx);
for(const mode of ['light','dark'])for(const color of ['#ffffff','#000000','#ffff00','#2563eb','#0f766e','#7c3aed','#c2410c','#be185d','#475569']){
 window.QVTheme.set({mode,accent:color});const c=window.QVTheme.colors(mode,color);assert(window.QVTheme.ratio(c['--purple'],c['--surface'])>=4.5,mode+' accent');assert(window.QVTheme.ratio(c['--accent-on'],color)>=4.5,mode+' button');assert(window.QVTheme.ratio(c['--text-secondary'],c['--surface'])>=4.5,mode+' secondary');assert(window.QVTheme.ratio(c['--ink'],c['--surface'])>=7,mode+' body');
}
window.QVTheme.set({mode:'dark',accent:'#0f766e',scale:1.2,contrast:true});assert(JSON.parse(stored['qv-theme-v1']).scale===1.2);assert(doc.documentElement.dataset.theme==='dark');window.QVTheme.set({accent:'invalid'});assert(/^#[a-f0-9]{6}$/i.test(window.QVTheme.get().accent));
console.log('Frontend: 7 screens, presets by variant/language, library tabs, 18 theme/color combinations (WCAG contrast), preference persistence passed. Browser layout not tested.');
