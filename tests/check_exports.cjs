// Exercise the actual export controls, selection state and binary download path.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements={},listeners={},parts=[1,2,3].map(id=>({id,text:'Đoạn <'+id+'>',characters:8,start_ms:(id-1)*5000,end_ms:id*5000}));
function element(key){return elements[key]||=( {addEventListener(){},classList:{add(){},remove(){}},querySelectorAll:()=>[],disabled:false,checked:true,dataset:{}} );}
const boxes=parts.map(p=>({dataset:{srtPart:String(p.id)},checked:true}));
const document={querySelector:element,querySelectorAll:s=>s==='[data-srt-part]'?boxes:[],addEventListener:(name,handler)=>listeners[name]=handler};
let post,download,notice,html='';
const ctx={document,window:{addEventListener(){}},localStorage:{getItem:()=>null},setTimeout,clearTimeout,console,URL,Blob,TextEncoder,FormData,AbortSignal,
fetch:async(url,options={})=>{
 if(!options.method)return {ok:true,json:async()=>({title:'Bản thử',timing_note:'Mốc thử',parts})};
 post={url,body:JSON.parse(options.body)};const name=post.body.scope==='full'?'Tiếng Việt.srt':post.body.parts.length===1?'Đoạn riêng.srt':'Các đoạn.zip';
 return {ok:true,headers:{get:()=>"attachment; filename*=UTF-8''"+encodeURIComponent(name)},blob:async()=>new Blob(['nội dung tải'],{type:name.endsWith('.zip')?'application/zip':'application/x-subrip'})};
}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../dist/subtitles.js','utf8'),ctx);let code=fs.readFileSync(__dirname+'/../dist/app.js','utf8');vm.runInContext(code.slice(0,code.lastIndexOf('(async()=>')),ctx);
ctx.saveDownload=(name,blob,type)=>download={name,blob,type};ctx.saveNotice=s=>notice=s;ctx.saveHTML=s=>html=s;
vm.runInContext('S.connected=true;modal=(title,body)=>saveHTML(body);downloadBlob=saveDownload;toast=saveNotice',ctx);
async function clickDownload(){await element('#download-srt-export').onclick({currentTarget:element('#download-srt-export')});}
(async()=>{
 await vm.runInContext('openSrtExport("job123")',ctx);
 assert(html.includes('một file SRT đầy đủ'));await clickDownload();
 assert.equal(post.url,'/api/jobs/job123/exports');assert.deepEqual(post.body,{format:'srt',scope:'full',parts:null,timeline:'local'});
 assert.equal(download.name,'Tiếng Việt.srt');assert.equal(await download.blob.text(),'nội dung tải');
 element('#srt-scope').onchange({target:{value:'parts'}});
 assert(html.includes('Đoạn &lt;1&gt;')&&!html.includes('Đoạn <1>'));assert(html.includes('srt-select-all'));
 boxes[1].checked=false;boxes[1].onchange();assert.equal(element('#srt-select-all').checked,false);
 element('#srt-timeline').onchange({target:{value:'global'}});await clickDownload();
 assert.deepEqual(post.body.parts,[1,3]);assert.equal(post.body.timeline,'global');assert.equal(download.name,'Các đoạn.zip');assert.equal(download.type,'application/zip');
 element('#srt-select-all').onchange({target:{checked:false}});post=null;await clickDownload();assert.equal(post,null);assert(notice.includes('ít nhất một đoạn'));assert.equal(element('#download-srt-export').disabled,false);
 boxes[2].checked=true;boxes[2].onchange();await clickDownload();assert.deepEqual(post.body.parts,[3]);assert.equal(download.name,'Đoạn riêng.srt');
 element('#srt-select-all').onchange({target:{checked:true}});await clickDownload();assert.deepEqual(post.body.parts,[1,2,3]);
 const text='Tiếng Việt.\r\n\r\n'.repeat(20000);ctx.longText=text;vm.runInContext('S.text=longText',ctx);
 await listeners.click({target:{closest:()=>({dataset:{action:'export-txt'}})}});
 assert.equal(download.name,'QuanVoice-VanBan.txt');assert.equal(download.blob,text);assert.equal(download.type,'text/plain;charset=utf-8');
 for(const type of ['tts','asr']){ctx.job={id:'job123',type,status:'done',title:'Thử',engine:'vieneu',created:0,file:'voice.wav'};const row=vm.runInContext('jobRow(job)',ctx);assert(row.includes('data-export-srt="job123"'));assert(row.includes('Tải TXT'));}
 // Header action must work on the static web preview without completed audio.
 vm.runInContext(`S.connected=false;S.text='Xin chào Việt Nam.\\n\\nĐoạn hai.\\n\\nĐoạn ba.'`,ctx);
 await listeners.click({target:{closest:()=>({dataset:{action:'export-srt'}})}});
 assert(html.includes('srt-duration')&&html.includes('Chưa có âm thanh'));assert.equal(vm.runInContext('S.exportDialog.id',ctx),'draft');
 element('#srt-duration').value='15';post=null;await clickDownload();assert.equal(post,null);assert.equal(download.name,'QuanVoice-VanBan.srt');assert(download.blob.includes('00:00:15,000'));assert(download.blob.includes('Việt Nam'));
 element('#srt-scope').onchange({target:{value:'parts'}});element('#srt-duration').value='15';await clickDownload();assert.equal(download.type,'application/zip');
 const zipBytes=Buffer.from(await download.blob.arrayBuffer());assert.equal(zipBytes.readUInt32LE(0),0x04034b50);assert.equal(zipBytes.readUInt32LE(zipBytes.length-22),0x06054b50);assert.equal(zipBytes.readUInt16LE(zipBytes.length-12),3);
 if(process.env.QV_TEST_ZIP)fs.writeFileSync(process.env.QV_TEST_ZIP,zipBytes);
 element('#srt-select-all').onchange({target:{checked:false}});boxes[1].checked=true;boxes[1].onchange();element('#srt-duration').value='15';await clickDownload();assert.equal(download.name,'QuanVoice-doan-0002.srt');assert(download.blob.startsWith('1\r\n00:00:00,000'));
 element('#srt-timeline').onchange({target:{value:'global'}});await clickDownload();assert(!download.blob.startsWith('1\r\n00:00:00,000'));
 download=null;element('#srt-duration').value='0';await clickDownload();assert.equal(download,null);assert(notice.includes('lớn hơn 0'));
 assert.throws(()=>ctx.window.QVSubtitles.draft('abc',NaN));assert.throws(()=>ctx.window.QVSubtitles.draft(' ',10));
 const long=ctx.window.QVSubtitles.draft(text,30000);assert.equal(long.parts.length,20000);assert.equal(long.parts.at(-1).end_ms,30000000);
 vm.runInContext(`S.connected=true;S.jobs=[{id:'job123',type:'tts',status:'done',text:S.text,title:'Bản khớp'}]`,ctx);await vm.runInContext('openSrtExport()',ctx);assert.equal(vm.runInContext('S.exportDialog.id',ctx),'job123');
 console.log('Exports: full SRT, local/global parts, checked selection, ZIP/direct filename, empty validation, exact long TXT, TTS/ASR result actions passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
