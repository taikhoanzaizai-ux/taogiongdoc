"""Read arbitrarily long input in bounded chunks and stream PCM to disk."""
import itertools, json, re, shutil, subprocess, unicodedata
from pathlib import Path
from subtitle_exports import audio_duration,paragraph_blocks

# Per-call sizes protect model context; they never truncate the complete input.
CHUNK_SIZE={'vieneu':350,'chatterbox':240,'index-tts':240,'gpt-sovits':350,'fish-speech':350,'vibevoice':400,'omnivoice':240}
def chunk_size(engine,language):
    size=CHUNK_SIZE[engine]
    return min(size,80) if language in ('zh','yue','ja','ko') else size
def text_chunks(text,limit):
    if limit<1:raise ValueError('Chunk size must be positive')
    start=0
    while start<len(text):
        end=min(start+limit,len(text))
        if end<len(text):
            window=text[start:end]
            stops=list(re.finditer(r'[.!?。！？;؛\n]+(?:\s+|$)',window))
            spaces=list(re.finditer(r'\s+',window))
            candidates=[m.end() for m in stops if m.end()>=len(window)//3]
            if candidates:end=start+candidates[-1]
            elif spaces:end=start+spaces[-1].end()
            # Keep combining marks with the preceding code point.
            while end<len(text) and unicodedata.combining(text[end]):end+=1
        yield text[start:end]
        start=end

def progress(output,done,total,part):
    p=Path(output).parent/'progress.json';temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps({'processed_chars':done,'total_chars':total,'part':part},ensure_ascii=False),encoding='utf-8');temp.replace(p)

def speech_units(text,limit):
    for part,block in paragraph_blocks(text):
        for chunk in text_chunks(block,limit):yield part,chunk

def save_timing(out,units):
    file=out.with_suffix('.timing.json');temp=file.with_suffix('.tmp')
    temp.write_text(json.dumps({'units':units},ensure_ascii=False),encoding='utf-8');temp.replace(file)

def render(p,synthesize):
    """synthesize(text, path) reuses the loaded SDK across all chunks."""
    out=Path(p['output']);text=p['text'];total=len(text);chunks=iter(speech_units(text,chunk_size(p['engine'],p.get('language'))));units=[];frames=0
    out.with_suffix('.timing.json').unlink(missing_ok=True)
    first=next(chunks);second=next(chunks,None)
    progress(out,0,total,0)
    if second is None:
        synthesize(first[1],str(out));save_timing(out,[{'part':first[0],'text':first[1],'start':0,'end':audio_duration(out)}]);progress(out,total,total,1);return
    folder=out.parent/'parts';folder.mkdir(exist_ok=True)
    combined=folder/'combined.pcm';done=0
    try:
        with combined.open('wb') as sink:
            for i,(part,chunk) in enumerate(itertools.chain((first,second),chunks),1):
                print(f'Đang đọc phần {i}: {done}/{total} ký tự',flush=True)
                if chunk.strip():
                    wav=folder/'current.wav';pcm=folder/'current.pcm'
                    synthesize(chunk,str(wav))
                    # Fixed PCM format permits streaming concatenation across SDKs
                    # without keeping the complete audio in RAM.
                    subprocess.run(['ffmpeg','-y','-v','error','-i',str(wav),'-f','s16le','-acodec','pcm_s16le','-ar','48000','-ac','1',str(pcm)],check=True)
                    count=pcm.stat().st_size//2
                    units.append({'part':part,'text':chunk,'start':frames/48000,'end':(frames+count)/48000});frames+=count
                    with pcm.open('rb') as source:shutil.copyfileobj(source,sink,1024*1024)
                    wav.unlink(missing_ok=True);pcm.unlink(missing_ok=True)
                done+=len(chunk);progress(out,done,total,i)
        subprocess.run(['ffmpeg','-y','-v','error','-f','s16le','-ar','48000','-ac','1','-i',str(combined),'-c:a','pcm_s16le','-rf64','auto',str(out)],check=True)
        save_timing(out,units)
    finally:shutil.rmtree(folder,ignore_errors=True)
