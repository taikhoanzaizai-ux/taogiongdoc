// Offline SubRip export for drafts. Recording timestamps come from the local API.
(function(){
 'use strict';
 const stamp=ms=>{ms=Math.max(0,Math.round(ms));return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`};
 function wrap(text,width){const result=[];let line='';for(const word of text.split(/\s+/)){if(!word)continue;if(line&&line.length+word.length+1>width){result.push(line);line=''}if(word.length>width){if(line){result.push(line);line=''}for(let i=0;i<word.length;i+=width)result.push(word.slice(i,i+width));}else line+=(line?' ':'')+word;}if(line)result.push(line);return result;}
 function draft(text,seconds){
  if(!text.trim())throw Error('Chưa có văn bản để xuất SRT.');
  if(!Number.isFinite(seconds)||seconds<=0)throw Error('Nhập tổng thời lượng lớn hơn 0 giây.');
  const blocks=text.trim().split(/\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*/).filter(t=>t.trim());
  const units=blocks.map(t=>wrap(t.trim(),84));const cueCount=units.reduce((n,u)=>n+u.length,0);const duration=Math.round(seconds*1000);
  if(!Number.isSafeInteger(duration)||duration<cueCount)throw Error('Thời lượng quá ngắn để chia phụ đề. Hãy tăng tổng thời lượng.');
  const total=units.flat().reduce((n,t)=>n+t.length,0);let done=0,cursor=0,index=0;
  const parts=blocks.map((text,i)=>{
   const cues=units[i].map(t=>{done+=t.length;index++;const stop=index===cueCount?duration:Math.max(cursor+1,Math.min(duration-(cueCount-index),Math.round(duration*done/total)));const cue={start_ms:cursor,end_ms:stop,text:wrap(t,42).join('\n')};cursor=stop;return cue;});
   return {id:i+1,text:text.trim(),characters:text.trim().length,start_ms:cues[0].start_ms,end_ms:cues[cues.length-1].end_ms,cues};
  });
  return {title:'Văn bản đang soạn',parts,timing:'estimated',timing_note:'Chưa có âm thanh: toàn bộ mốc SRT được ước lượng theo thời lượng bạn nhập. Chọn bản thu đã tạo để dùng thời lượng âm thanh thực.'};
 }
 function render(parts,local=false){const offset=local&&parts.length?parts[0].start_ms:0;return parts.flatMap(p=>p.cues).map((c,i)=>`${i+1}\r\n${stamp(c.start_ms-offset)} --> ${stamp(c.end_ms-offset)}\r\n${c.text.replace(/\r?\n/g,'\r\n')}`).join('\r\n\r\n')+'\r\n';}
 const crcTable=Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0});
 function crc32(bytes){let crc=0xffffffff;for(const b of bytes)crc=crcTable[(crc^b)&255]^(crc>>>8);return (crc^0xffffffff)>>>0;}
 function zip(files){
  if(files.length>65535)throw Error('ZIP hỗ trợ tối đa 65.535 file. Hãy xuất thành nhiều lần.');
  const enc=new TextEncoder(),chunks=[],central=[];let offset=0,centralSize=0;
  for(const file of files){
   const name=enc.encode(file.name),bytes=enc.encode(file.text),crc=crc32(bytes),header=new Uint8Array(30+name.length),h=new DataView(header.buffer);
   h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);h.setUint16(6,0x800,true);h.setUint16(12,33,true);h.setUint32(14,crc,true);h.setUint32(18,bytes.length,true);h.setUint32(22,bytes.length,true);h.setUint16(26,name.length,true);header.set(name,30);
   const entry=new Uint8Array(46+name.length),v=new DataView(entry.buffer);v.setUint32(0,0x02014b50,true);v.setUint16(4,20,true);v.setUint16(6,20,true);v.setUint16(8,0x800,true);v.setUint16(14,33,true);v.setUint32(16,crc,true);v.setUint32(20,bytes.length,true);v.setUint32(24,bytes.length,true);v.setUint16(28,name.length,true);v.setUint32(42,offset,true);entry.set(name,46);
   chunks.push(header,bytes);central.push(entry);offset+=header.length+bytes.length;centralSize+=entry.length;
  }
  if(offset+centralSize>0xffffffff)throw Error('ZIP vượt quá 4 GB. Hãy chọn ít đoạn hơn.');
  const end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,files.length,true);v.setUint16(10,files.length,true);v.setUint32(12,centralSize,true);v.setUint32(16,offset,true);
  return new Blob([...chunks,...central,end],{type:'application/zip'});
 }
 function download(manifest,scope,selected,timeline){
  if(scope==='full')return {name:'QuanVoice-VanBan.srt',content:render(manifest.parts),type:'application/x-subrip;charset=utf-8'};
  const parts=manifest.parts.filter(p=>selected.has(p.id));if(!parts.length)throw Error('Chọn ít nhất một đoạn để tải.');
  const files=parts.map(p=>({name:`QuanVoice-doan-${String(p.id).padStart(4,'0')}.srt`,text:render([p],timeline==='local')}));
  return files.length===1?{name:files[0].name,content:files[0].text,type:'application/x-subrip;charset=utf-8'}:{name:'QuanVoice-SRT-tung-doan.zip',content:zip(files),type:'application/zip'};
 }
 window.QVSubtitles={draft,render,download};
})();
