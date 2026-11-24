"""Real WAV durations, SubRip parsing, API downloads and selected ZIP contents."""
import importlib.util,io,json,re,subprocess,sys,wave,zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
import subtitle_exports as ex
from longform import render

def wav(path,seconds):
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes(b'\x01\x00'*round(seconds*48000))

def parse(text):
    result=[]
    for i,block in enumerate(re.split(r'\r?\n\r?\n',text.strip()),1):
        lines=block.splitlines();assert lines[0]==str(i)
        match=re.fullmatch(r'(\d{2,}):(\d\d):(\d\d),(\d{3}) --> (\d{2,}):(\d\d):(\d\d),(\d{3})',lines[1]);assert match
        nums=list(map(int,match.groups()));a=nums[0]*3600000+nums[1]*60000+nums[2]*1000+nums[3];b=nums[4]*3600000+nums[5]*60000+nums[6]*1000+nums[7]
        assert b>a and len(lines)>=3
        if result:assert a>=result[-1][1]
        result.append((a,b,'\n'.join(lines[2:])))
    return result

@pytest.fixture
def studio(tmp_path,monkeypatch):
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path));monkeypatch.delenv('QUAN_VOICE_SETUP_PROFILE',raising=False)
    spec=importlib.util.spec_from_file_location('export_server',ROOT/'desktop/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    yield m,TestClient(m.app),tmp_path
    m.POOL.shutdown();m.SETUP_POOL.shutdown();m.RUNTIME.stop()

def seed(studio,identifier='voice',kind='tts',text='Xin chào Việt Nam.\n\nĐoạn thứ hai giữ dấu tiếng Việt.'):
    m,client,root=studio;folder=root/'outputs'/identifier;folder.mkdir()
    job={'id':identifier,'type':kind,'engine':'vieneu' if kind=='tts' else 'whisper','status':'done','text':text,'file':'voice.wav' if kind=='tts' else 'transcript.txt','title':'Tiêu đề / bản tin?','speed':2,'created':0}
    if kind=='tts':wav(folder/'voice.wav',2)
    else:
        result={'text':text,'segments':[{'start':1.25,'end':2,'text':'Xin chào Việt Nam.'},{'start':5.5,'end':6,'text':'Đoạn thứ hai.'}]}
        (folder/'transcript.json').write_text(json.dumps(result,ensure_ascii=False));job['text_result']=text;(folder/'transcript.txt').write_text(text)
    m.put('jobs',identifier,job);return job,folder

def test_measured_paragraphs_follow_real_audio_after_speed_change(studio):
    job,folder=seed(studio);calls=[]
    def synthesize(text,path):calls.append(text);wav(path,1 if len(calls)==1 else 3)
    render({'engine':'vieneu','text':job['text'],'output':str(folder/'raw.wav')},synthesize)
    assert len(calls)==2 and ''.join(calls)==job['text']
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(folder/'raw.wav'),'-af','atempo=2',str(folder/'voice.wav')],check=True)
    doc=ex.document(job,folder);duration=ex.audio_duration(folder/'voice.wav')
    assert doc['timing']=='synthesis' and len(doc['parts'])==2
    assert doc['parts'][0]['end_ms']==round(duration*1000/4)
    assert doc['parts'][-1]['end_ms']==round(duration*1000)
    full=parse(ex.render_srt(doc['parts']));assert full[-1][1]==round(duration*1000)
    assert 'Việt Nam' in full[0][2]
    assert parse(ex.render_srt([doc['parts'][1]],local=True))[0][0]==0

def test_full_txt_keeps_unicode_and_all_characters_without_audio(studio):
    text=('Tiếng Việt không bị cắt.\r\n\r\n'*12000);job,folder=seed(studio,text=text);(folder/'voice.wav').unlink()
    r=studio[1].get('/api/jobs/voice/download?kind=txt')
    assert r.status_code==200 and r.content.decode('utf-8')==text
    assert 'filename*=UTF-8' in r.headers['content-disposition']

def test_whisper_full_and_individual_time_modes(studio):
    seed(studio,'asr',kind='asr');client=studio[1]
    manifest=client.get('/api/jobs/asr/exports').json();assert manifest['timing']=='recognition' and len(manifest['parts'])==2
    full=client.get('/api/jobs/asr/download?kind=srt');cues=parse(full.text)
    assert [(a,b) for a,b,_ in cues]==[(1250,2000),(5500,6000)]
    local=client.get('/api/jobs/asr/download?kind=srt&part=2&timeline=local')
    assert parse(local.text)[0][:2]==(0,500)
    glob=client.get('/api/jobs/asr/download?kind=srt&part=2&timeline=global')
    assert parse(glob.text)[0][:2]==(5500,6000)

def test_selected_parts_zip_order_names_and_no_extra_files(studio):
    seed(studio,'asr',kind='asr');client=studio[1]
    r=client.post('/api/jobs/asr/exports',json={'scope':'parts','parts':[2,1,2],'timeline':'local'})
    assert r.status_code==200 and r.headers['content-type']=='application/zip'
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert len(z.namelist())==2 and '0001' in z.namelist()[0] and '0002' in z.namelist()[1]
        for name in z.namelist():
            assert '/' not in name and '\\' not in name and name.endswith('.srt')
            assert parse(z.read(name).decode('utf-8'))[0][0]==0
    one=client.post('/api/jobs/asr/exports',json={'scope':'parts','parts':[2]})
    assert one.status_code==200 and one.headers['content-type'].startswith('application/x-subrip')
    assert '0002' in one.headers['content-disposition'] and 'Đoạn thứ hai.' in one.text

def test_old_recordings_export_without_regeneration(studio):
    seed(studio);client=studio[1]
    manifest=client.get('/api/jobs/voice/exports').json();assert manifest['timing']=='estimated' and len(manifest['parts'])==2
    r=client.post('/api/jobs/voice/exports',json={});assert r.status_code==200
    assert parse(r.text)[-1][1]==2000

@pytest.mark.parametrize('body,code',[
 ({'scope':'parts','parts':[]},400),({'scope':'parts','parts':[0]},400),({'scope':'parts','parts':[99]},400),
 ({'scope':'parts','parts':[True]},422),({'format':'exe'},422),({'timeline':'anything'},422)])
def test_invalid_exports_are_rejected(studio,body,code):
    seed(studio);assert studio[1].post('/api/jobs/voice/exports',json=body).status_code==code

def test_incomplete_unknown_and_cross_origin_exports_are_rejected(studio):
    job,_=seed(studio);m,client,_=studio
    job['status']='running';m.put('jobs',job['id'],job)
    assert client.get('/api/jobs/voice/exports').status_code==404
    assert client.post('/api/jobs/missing/exports',json={}).status_code==404
    assert client.post('/api/jobs/voice/exports',json={},headers={'Origin':'https://elsewhere.test'}).status_code==403

def test_caption_cues_keep_long_text_and_positive_intervals():
    text=' '.join(['Chào Việt Nam']*1500);cues=ex.captions(text,0,.25)
    parts=[{'start_ms':0,'cues':cues}];parsed=parse(ex.render_srt(parts))
    assert re.sub(r'\s+','',text)==re.sub(r'\s+','',''.join(t for _,_,t in parsed))
    assert parsed[-1][1]==250 and ex.filename('CON')=='_CON'
