const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=__dirname+'/../dist/',handlers={},elements={};
const dummy={addEventListener(){},classList:{add(){},remove(){}},querySelectorAll(){return []},textContent:''};
const document={querySelector:s=>elements[s]||dummy,querySelectorAll:()=>[],addEventListener:(name,fn)=>handlers[name]=fn};
const storage={};let quota=false;
const ctx={document,window:{addEventListener(){}},localStorage:{getItem:k=>storage[k]||null,setItem:(k,v)=>{if(quota)throw Error('Quota');storage[k]=v}},setTimeout,clearTimeout,console,URL,Blob,FormData,AbortSignal};
vm.createContext(ctx);let source=fs.readFileSync(root+'app.js','utf8');source=source.slice(0,source.lastIndexOf('(async()=>'));vm.runInContext(source,ctx);
ctx.catalog=JSON.parse(fs.readFileSync(root+'engines.json'));ctx.banks=JSON.parse(fs.readFileSync(root+'presets.json'));ctx.long='Xin chào! '.repeat(30000);ctx.calls=[];
vm.runInContext(`S.engines=catalog;S.banks=banks;S.connected=true;S.engine='vieneu';S.language='vi';S.engines[0].available=true;S.view='history';S.text=long;
render=()=>{};navigate=()=>{};toast=()=>{};
pickFile=async(accept,cb)=>{await cb({size:long.length*4,text:async()=>accept==='.json'?JSON.stringify({text:long,engine:'vieneu',language:'vi'}):long})};
api=async(path,o)=>{calls.push({path,body:JSON.parse(o.body)});return {id:'job'+calls.length}};`,ctx);
(async()=>{
 for(const action of ['import-text','import-draft']){
  vm.runInContext(`S.text=''`,ctx);
  await handlers.click({target:{closest:()=>({dataset:{action}})}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(vm.runInContext('S.text',ctx),ctx.long,action+' truncated text');
 }
 const html=vm.runInContext('studio()',ctx);assert(!/maxlength="(?:20000|400)"/.test(html));
 await vm.runInContext('generate()',ctx);assert.equal(ctx.calls.at(-1).body.text,ctx.long);
 quota=true;vm.runInContext('saveDraft()',ctx);assert.equal(vm.runInContext('S.text',ctx),ctx.long);
 vm.runInContext(`S.batch=true;S.text=Array(61).fill('Đoạn nội dung.').join('\\n\\n')`,ctx);
 const before=ctx.calls.length;await vm.runInContext('generate()',ctx);assert.equal(ctx.calls.length-before,61);
 console.log('Long text UI: 300,000 characters preserved through TXT/JSON imports, generation, storage quota failure, and 61 batch paragraphs.');
})().catch(e=>{console.error(e);process.exitCode=1});
