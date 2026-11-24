"""TXT/SubRip downloads from measured TTS units or Whisper segment timestamps."""
import io,json,math,re,subprocess,textwrap,wave,zipfile
from pathlib import Path

def audio_duration(path):
    try:
        with wave.open(str(path),'rb') as wav:return wav.getnframes()/wav.getframerate()
    except (OSError,wave.Error,EOFError):pass
    try:
        result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=30)
        value=float(json.loads(result.stdout)['format']['duration'])
        if math.isfinite(value) and value>0:return value
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):pass
    # FFmpeg is required by Studio; support installations lacking ffprobe too.
    result=subprocess.run(['ffmpeg','-hide_banner','-i',str(path)],capture_output=True,text=True,timeout=30)
    match=re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)',result.stderr)
    if not match:raise ValueError('Không đọc được thời lượng âm thanh để xuất SRT.')
    return int(match[1])*3600+int(match[2])*60+float(match[3])

def paragraph_blocks(text):
    start=0;part=0
    for match in re.finditer(r'\r?\n[ \t]*\r?\n',text):
        block=text[start:match.end()];start=match.end()
        if block.strip():part+=1
        yield part,block
    if start<len(text):
        block=text[start:]
        if block.strip():part+=1
        yield part,block

def filename(title):
    title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title or 'Ban-thu').strip(' .')[:100].rstrip(' .') or 'Ban-thu'
    if title.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:title='_'+title
    return title

def stamp(ms):
    ms=max(0,int(ms));return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def captions(text,start,end,split=True):
    clean=' '.join(text.replace('\x00','').split())
    if not clean:return []
    chunks=textwrap.wrap(clean,width=84,break_on_hyphens=False) if split else [clean]
    start=max(0,round(start*1000));end=max(start+1,round(end*1000));duration=end-start
    if len(chunks)>duration:
        # Every cue needs a positive, non-overlapping integer millisecond span.
        step=math.ceil(len(chunks)/duration);chunks=[' '.join(chunks[i:i+step]) for i in range(0,len(chunks),step)]
    total=sum(map(len,chunks));done=0;cursor=start;result=[]
    for i,chunk in enumerate(chunks):
        done+=len(chunk)
        stop=end if i==len(chunks)-1 else max(cursor+1,min(end-(len(chunks)-i-1),start+round(duration*done/total)))
        lines='\n'.join(textwrap.wrap(chunk,width=42,break_on_hyphens=False))
        result.append({'start_ms':cursor,'end_ms':stop,'text':lines});cursor=stop
    return result

def plain_text(job,folder):
    if job['type']=='tts':return job.get('text','')
    if job.get('text_result') is not None:return job['text_result']
    return json.loads((Path(folder)/'transcript.json').read_text(encoding='utf-8'))['text']

def document(job,folder):
    folder=Path(folder);parts=[]
    if job['type']=='asr':
        raw=json.loads((folder/'transcript.json').read_text(encoding='utf-8'))
        units=[{'part':i,'start':s['start'],'end':s['end'],'text':s['text']} for i,s in enumerate(raw['segments'],1) if s['text'].strip()]
        source='recognition';scale=1
    else:
        timing=folder/'raw.timing.json'
        if timing.is_file():
            units=json.loads(timing.read_text(encoding='utf-8'))['units'];source='synthesis'
            raw_end=max((float(u['end']) for u in units),default=0)
            scale=audio_duration(folder/job['file'])/raw_end if raw_end else 1
        else:
            # Existing recordings remain exportable without generating the voice again.
            blocks=[(n,t) for n,t in paragraph_blocks(job.get('text','')) if t.strip()]
            duration=audio_duration(folder/job['file']);total=sum(len(t.strip()) for _,t in blocks);cursor=0;units=[]
            for number,text in blocks:
                stop=cursor+duration*len(text.strip())/max(1,total)
                units.append({'part':number,'text':text,'start':cursor,'end':stop});cursor=stop
            source='estimated';scale=1
    current=None
    for unit in units:
        start=float(unit['start'])*scale;end=float(unit['end'])*scale
        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<start:raise ValueError('Mốc thời gian phụ đề không hợp lệ.')
        cues=captions(unit['text'],start,end,split=source!='recognition')
        if not cues:continue
        if current!=unit['part']:
            parts.append({'id':len(parts)+1,'text':'','cues':[]});current=unit['part']
        part=parts[-1];part['text']+=unit['text'];part['cues'].extend(cues)
    for part in parts:
        part['text']=part['text'].strip();part['start_ms']=part['cues'][0]['start_ms'];part['end_ms']=part['cues'][-1]['end_ms']
    messages={'recognition':'Mốc thời gian lấy từ các đoạn Whisper nhận dạng.','synthesis':'Mốc đoạn lấy theo âm thanh đã tạo; thời gian từng dòng SRT được ước lượng trong đoạn.','estimated':'Bản thu cũ: thời gian SRT được ước lượng theo tổng thời lượng âm thanh. Tạo lại giọng để có mốc từng đoạn.'}
    return {'parts':parts,'timing':source,'timing_note':messages[source]}

def render_srt(parts,local=False):
    offset=parts[0]['start_ms'] if local and parts else 0
    return '\r\n\r\n'.join(f"{i}\r\n{stamp(cue['start_ms']-offset)} --> {stamp(cue['end_ms']-offset)}\r\n{cue['text'].replace(chr(10),chr(13)+chr(10))}" for i,cue in enumerate((c for part in parts for c in part['cues']),1))+'\r\n'

def export(job,folder,format='srt',scope='full',selected=None,timeline='local'):
    if format not in ('txt','srt') or scope not in ('full','parts') or timeline not in ('local','global'):raise ValueError('Tùy chọn xuất không hợp lệ.')
    title=filename(job.get('title'));mime='text/plain; charset=utf-8' if format=='txt' else 'application/x-subrip; charset=utf-8'
    if format=='txt' and scope=='full':return title+'.txt',mime,plain_text(job,folder).encode('utf-8')
    doc=document(job,folder);parts=doc['parts']
    if not parts:raise ValueError('Chưa có đoạn văn bản để xuất.')
    if scope=='full':return title+'.'+format,mime,render_srt(parts).encode('utf-8')
    if selected is not None:
        if not selected or any(type(i) is not int or i<1 or i>len(parts) for i in selected):raise ValueError('Chọn ít nhất một đoạn hợp lệ.')
        chosen=set(selected);parts=[p for p in parts if p['id'] in chosen]
    def content(part):return (part['text'] if format=='txt' else render_srt([part],local=timeline=='local')).encode('utf-8')
    def name(part):return f"{title}-doan-{part['id']:04}.{format}"
    if len(parts)==1:return name(parts[0]),mime,content(parts[0])
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for part in parts:archive.writestr(name(part),content(part))
    return title+'-'+format.upper()+'-tung-doan.zip','application/zip',buffer.getvalue()
