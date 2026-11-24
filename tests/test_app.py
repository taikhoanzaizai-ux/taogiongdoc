"""Integration tests with real ffmpeg and isolated test providers; no model weights."""
import base64, importlib.util, io, json, os, sys, tempfile, threading, time, wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture(scope='module')
def app(tmp_path_factory):
    data=tmp_path_factory.mktemp('voice-data');os.environ['QUAN_VOICE_DATA']=str(data)
    spec=importlib.util.spec_from_file_location('studio_server',ROOT/'desktop/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    yield m
    m.POOL.shutdown(wait=True)
@pytest.fixture
def client(app):return TestClient(app.app)
def wav_bytes(seconds=1):
    b=io.BytesIO()
    with wave.open(b,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x01\x00'*int(24000*seconds))
    return b.getvalue()
def upload(client,name='Giọng thử',transcript='Xin chào',language='vi'):
    r=client.post('/api/voices',files={'file':('voice.wav',wav_bytes(),'audio/wav')},data={'name':name,'transcript':transcript,'language':language});assert r.status_code==200,r.text;return r.json()
def wait(client,identifier):
    for _ in range(200):
        j=next(x for x in client.get('/api/jobs').json() if x['id']==identifier)
        if j['status'] not in ('queued','running'):return j
        time.sleep(.025)
    pytest.fail('Job timeout')
def configure(client,app,tmp_path,engine='vieneu'):
    repo=tmp_path/'source with spaces';repo.mkdir(exist_ok=True)
    if engine=='vieneu':
        (repo/'vieneu.py').write_text('''import wave,time
class Vieneu:
 def __init__(self,**kw): pass
 def infer(self,text,**kw):
  if text=='SLOW':time.sleep(10)
  return b'\\x01\\x00'*24000
 def save(self,a,p):
  with wave.open(p,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(a)
''')
    elif engine=='whisper':
        (repo/'whisper.py').write_text('''class Model:
 def transcribe(self,*a,**kw):return {'text':'Xin chào Việt Nam.','segments':[{'start':0.125,'end':1.5,'text':'Xin chào Việt Nam.'}]}
def load_model(*a,**kw):return Model()
''');(repo/'torch.py').write_text('')
    r=client.put('/api/engines/'+engine,json={'python':sys.executable,'repo':str(repo),'checkpoint':'','device':'cpu','variant':'base' if engine=='whisper' else 'v3turbo','endpoint':''});assert r.status_code==200,r.text
    return repo

def test_catalog_and_static(client):
    r=client.get('/');assert r.status_code==200;assert 'QUÂN Voice Studio' in r.text
    catalog=client.get('/engines.json').json();assert len(catalog)==8;assert sum(e['clone'] for e in catalog)==6
    status=client.get('/api/status').json();assert status['ffmpeg'];assert not status['engines'][0]['available']
def test_upload_normalizes_and_persists(client,app):
    v=upload(client);assert v['name']=='Giọng thử';assert v['duration']==1
    assert any(x['id']==v['id'] for x in client.get('/api/voices').json())
    r=client.get('/api/voices/'+v['id']+'/audio');assert r.status_code==200
    with wave.open(io.BytesIO(r.content)) as w:assert w.getnchannels()==1;assert w.getframerate()==24000
    assert app.get('voices',v['id'])['transcript']=='Xin chào'
def test_invalid_audio_and_short_clip(client):
    r=client.post('/api/voices',files={'file':('bad.wav',b'not audio')},data={'name':'bad'});assert r.status_code==400
    r=client.post('/api/voices',files={'file':('short.wav',wav_bytes(.1))},data={'name':'short'});assert r.status_code==400

def test_capability_validation(client):
    for body in [{'engine':'missing'},{'engine':'whisper','language':'vi'},{'engine':'chatterbox','language':'vi','text':'hi'},{'engine':'vieneu','text':'','language':'vi'}]:
        assert client.post('/api/jobs',json=body).status_code in (400,404)
    v=upload(client)
    assert client.post('/api/jobs',json={'engine':'vibevoice','language':'en','text':'hi','voice_id':v['id']}).status_code==400
    assert client.post('/api/jobs',json={'engine':'vieneu','language':'vi','text':'hi','speed':10}).status_code==422

def test_real_worker_and_audio_export(client,app,tmp_path):
    configure(client,app,tmp_path);v=upload(client)
    for fmt in ('wav','mp3'):
        r=client.post('/api/jobs',json={'engine':'vieneu','language':'vi','text':'Xin chào','voice_id':v['id'],'speed':1.5,'format':fmt});assert r.status_code==202,r.text
        j=wait(client,r.json()['id']);assert j['status']=='done',j
        audio=client.get('/api/jobs/'+j['id']+'/download');assert audio.status_code==200
        if fmt=='wav':
            with wave.open(io.BytesIO(audio.content)) as w:assert .5<w.getnframes()/w.getframerate()<.8
        else:assert len(audio.content)>100

def test_asr_txt_srt_downloads(client,app,tmp_path):
    configure(client,app,tmp_path,'whisper');v=upload(client)
    r=client.post('/api/jobs',json={'engine':'whisper','language':'vi','voice_id':v['id']});assert r.status_code==202
    j=wait(client,r.json()['id']);assert j['status']=='done',j
    assert 'Việt Nam' in client.get('/api/jobs/'+j['id']+'/download').text
    srt=client.get('/api/jobs/'+j['id']+'/download?kind=srt').text;assert '00:00:00,125 --> 00:00:01,500' in srt

def test_queued_and_running_cancellation(client,app,tmp_path):
    configure(client,app,tmp_path)
    first=client.post('/api/jobs',json={'engine':'vieneu','text':'SLOW','language':'vi'}).json()
    second=client.post('/api/jobs',json={'engine':'vieneu','text':'Should not run','language':'vi'}).json()
    for _ in range(80):
        if first['id'] in app.PROCESSES:break
        time.sleep(.025)
    assert client.post('/api/jobs/'+second['id']+'/cancel').status_code==200
    assert client.post('/api/jobs/'+first['id']+'/cancel').status_code==200
    assert wait(client,first['id'])['status']=='cancelled'
    assert wait(client,second['id'])['status']=='cancelled'
    assert client.get('/api/jobs/'+second['id']+'/download').status_code==404

def test_worker_failure_visible_and_retryable(client,app,tmp_path):
    configure(client,app,tmp_path);cfg=app.config('vieneu');cfg['python']=str(tmp_path/'missing-python');app.put('settings','vieneu',cfg)
    # Insert a job that had a valid engine before the interpreter was removed.
    identifier='failing-job';app.put('jobs',identifier,{'id':identifier,'engine':'vieneu','type':'tts','status':'queued','language':'vi','text':'hi','voice_id':None,'created':time.time()})
    app.run_job(identifier);j=app.get('jobs',identifier);assert j['status']=='failed';assert j['error']
    configure(client,app,tmp_path)

def test_loopback_origin_and_path_guards(client):
    assert client.post('/api/install/vieneu',headers={'Origin':'https://external.example'}).status_code==403
    assert client.get('/api/status',headers={'Host':'external.example'}).status_code==403
    r=client.put('/api/engines/fish-speech',json={'endpoint':'https://external.example'});assert r.status_code==400
    assert client.post('/api/install/not-an-engine').status_code==404
    assert client.get('/api/jobs/not-found/download').status_code==404

def test_reference_delete(client):
    v=upload(client);assert client.delete('/api/voices/'+v['id']).status_code==200
    assert client.get('/api/voices/'+v['id']+'/audio').status_code==404

@pytest.mark.parametrize('engine,endpoint',[('gpt-sovits','/tts'),('fish-speech','/v1/tts')])
def test_official_api_payloads(client,app,tmp_path,engine,endpoint):
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'OK')
        def do_POST(self):
            received.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200);self.send_header('Content-Type','audio/wav');self.end_headers();self.wfile.write(wav_bytes())
    server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        cfg=app.config(engine);cfg['endpoint']='http://127.0.0.1:'+str(server.server_port);app.put('settings',engine,cfg)
        v=upload(client,language='en',transcript='Hello')
        r=client.post('/api/jobs',json={'engine':engine,'language':'en','text':'New words','voice_id':v['id']});assert r.status_code==202,r.text
        j=wait(client,r.json()['id']);assert j['status']=='done',j
        path,body=received[0];assert path==endpoint;assert body['text']=='New words';assert not body.get('streaming',False)
        if engine=='gpt-sovits':assert body['prompt_text']=='Hello';assert body['prompt_lang']=='en';assert Path(body['ref_audio_path']).exists()
        else:assert base64.b64decode(body['references'][0]['audio'])[:4]==b'RIFF';assert body['references'][0]['text']=='Hello'
    finally:server.shutdown();server.server_close()

def test_real_preset_catalogs_and_variants(client,app,tmp_path):
    banks=client.get('/api/presets').json()
    assert len(banks['vieneu']['voices'])==25
    assert len(banks['vieneu']['variants']['v3nano']['voices'])==11
    assert len(banks['vibevoice']['voices'])==25
    assert len(banks['index-tts']['voices'])==11
    assert not banks['whisper']['voices']
    cfg=app.config('vieneu');cfg['variant']='v3nano';app.put('settings','vieneu',cfg)
    bank=client.get('/api/presets').json()['vieneu'];assert len(bank['voices'])==11;assert not any(v['id']=='Hải Đăng' for v in bank['voices'])
    r=client.post('/api/jobs',json={'engine':'vieneu','language':'vi','text':'Hi','preset':'Hải Đăng'});assert r.status_code==400
    cfg['variant']='v3turbo';app.put('settings','vieneu',cfg)

def test_preset_id_validation_and_exact_vibe_language(client):
    r=client.post('/api/jobs',json={'engine':'vieneu','language':'vi','text':'Hi','preset':'invented-name'});assert r.status_code==400
    r=client.post('/api/jobs',json={'engine':'vibevoice','language':'en','text':'Hi','preset':'jp-spk0_man'});assert r.status_code==400;assert 'ngôn ngữ' in r.json()['detail']
    assert client.get('/api/engines/index-tts/presets/unknown.wav/audio').status_code==400

def test_native_vieneu_passes_exact_preset_to_sdk(client,app,tmp_path):
    repo=configure(client,app,tmp_path)
    p=repo/'vieneu.py';s=p.read_text().replace(" def infer(self,text,**kw):", " def infer(self,text,**kw):\n  import json,pathlib\n  pathlib.Path(__file__).with_name('received.json').write_text(json.dumps(kw,ensure_ascii=False))");p.write_text(s)
    r=client.post('/api/jobs',json={'engine':'vieneu','text':'Xin chào','language':'vi','preset':'Ngọc Trân'});assert r.status_code==202,r.text
    j=wait(client,r.json()['id']);assert j['status']=='done',j
    assert json.loads((repo/'received.json').read_text())['voice']=='Ngọc Trân'

def test_fish_reference_discovery_and_native_payload(client,app):
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            body=json.dumps({'success':True,'reference_ids':['Giọng mẫu A','speaker_b']}).encode() if self.path.endswith('references/list') else b'{}'
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));self.send_response(200);self.send_header('Content-Type','audio/wav');self.end_headers();self.wfile.write(wav_bytes())
    service=HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=service.serve_forever,daemon=True).start()
    try:
        cfg=app.config('fish-speech');cfg['endpoint']='http://127.0.0.1:'+str(service.server_port);app.put('settings','fish-speech',cfg)
        bank=client.get('/api/presets').json()['fish-speech'];assert bank['connected'];assert [v['id'] for v in bank['voices']]==['Giọng mẫu A','speaker_b']
        r=client.post('/api/jobs',json={'engine':'fish-speech','text':'Hello','language':'en','preset':'speaker_b'});assert r.status_code==202,r.text
        j=wait(client,r.json()['id']);assert j['status']=='done',j;assert received[0]['reference_id']=='speaker_b';assert received[0]['references']==[]
    finally:service.shutdown();service.server_close()

def test_scan_installed_vibe_voices_including_optional_packs(client,app,tmp_path):
    cfg=app.config('vibevoice');cfg['repo']=str(tmp_path/'vibe-repo');folder=Path(cfg['repo'])/'demo/voices/streaming_model/experimental_voices';folder.mkdir(parents=True)
    (folder/'en-Custom_man.pt').write_bytes(b'fixture');(folder/'fr-Test_woman.pt').write_bytes(b'fixture');app.put('settings','vibevoice',cfg)
    bank=client.get('/api/presets').json()['vibevoice'];assert {v['id'] for v in bank['voices']}=={'en-custom_man','fr-test_woman'};assert all(v['installed'] for v in bank['voices'])

def test_index_preview_does_not_create_incomplete_install_source(client,app,tmp_path,monkeypatch):
    cfg=app.config('index-tts');cfg['repo']=str(tmp_path/'not-installed-source');app.put('settings','index-tts',cfg)
    seen=[]
    def sample(root,identifier,bank):
        seen.append(Path(root));p=Path(root)/'sample.wav';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(wav_bytes());return p
    monkeypatch.setattr(app,'index_sample',sample)
    r=client.get('/api/engines/index-tts/presets/voice_01.wav/audio');assert r.status_code==200;assert r.content[:4]==b'RIFF'
    assert not Path(cfg['repo']).exists();assert seen[0]==app.DATA/'cache'/'index-samples'

def wait_preview(client,identifier):
    for _ in range(200):
        r=client.get('/api/previews/'+identifier);assert r.status_code==200,r.text;j=r.json()
        if j['status'] not in ('queued','running'):return j
        time.sleep(.025)
    pytest.fail('Preview timeout')

def test_preview_audio_cache_and_no_production_history(client,app,tmp_path):
    configure(client,app,tmp_path)
    body={'engine':'vieneu','language':'vi','text':'Xin chào, nghe thử.','preset':'Trúc Ly'}
    before=client.get('/api/jobs').json()
    r=client.post('/api/previews',json=body);assert r.status_code==202,r.text
    identifier=r.json()['id'];job=wait_preview(client,identifier);assert job['status']=='done',job;assert job['type']=='preview'
    assert client.get('/api/jobs/'+identifier+'/download').content[:4]==b'RIFF'
    again=client.post('/api/previews',json=body).json();assert again['id']==identifier;assert again['cached'] is True
    assert client.get('/api/jobs').json()==before
    changed=client.post('/api/previews',json={**body,'text':'Một câu nghe thử khác.'}).json();assert changed['id']!=identifier;assert wait_preview(client,changed['id'])['status']=='done'

def test_preview_reference_is_separate_from_saved_voices(client,app,tmp_path):
    configure(client,app,tmp_path);before=client.get('/api/voices').json()
    r=client.post('/api/preview-references',files={'file':('reference.wav',wav_bytes(),'audio/wav')},data={'language':'vi','transcript':'Xin chào'});assert r.status_code==200,r.text
    ref=r.json();assert client.get('/api/voices').json()==before
    r=client.post('/api/previews',json={'engine':'vieneu','language':'vi','text':'Đây là giọng clone thử.','preview_ref_id':ref['id']});assert r.status_code==202,r.text
    j=wait_preview(client,r.json()['id']);assert j['status']=='done',j;assert j['preview_ref_id']==ref['id']
    data=json.loads((app.DATA/'jobs'/(j['id']+'.json')).read_text());assert data['ref']==str(app.DATA/'preview_refs'/(ref['id']+'.wav'));assert data['reference_transcript']=='Xin chào'
    assert client.get('/api/voices').json()==before

def test_preview_capability_and_unlimited_text(client,app,tmp_path):
    configure(client,app,tmp_path)
    assert client.post('/api/previews',json={'engine':'whisper','language':'vi','text':'hello'}).status_code==400
    response=client.post('/api/previews',json={'engine':'vieneu','language':'vi','text':'x'*401})
    assert response.status_code==202,response.text
    assert wait_preview(client,response.json()['id'])['status']=='done'
    assert client.post('/api/previews',json={'engine':'vieneu','language':'vi','text':'hello','preview_ref_id':'../bad'}).status_code==404
    r=client.post('/api/preview-references',files={'file':('bad.wav',b'bad')});assert r.status_code==400
    r=client.post('/api/preview-references',files={'file':('ref.wav',wav_bytes())},data={'language':'en'});ref=r.json()
    r=client.post('/api/previews',json={'engine':'vibevoice','language':'en','text':'Hello','preview_ref_id':ref['id']});assert r.status_code==400

def test_selected_clone_model_is_stored(client):
    r=client.post('/api/voices',files={'file':('reference.wav',wav_bytes())},data={'name':'Selected engine','language':'en','preferred_engine':'chatterbox'});assert r.status_code==200,r.text
    assert r.json()['preferred_engine']=='chatterbox'
    assert next(v for v in client.get('/api/voices').json() if v['id']==r.json()['id'])['preferred_engine']=='chatterbox'
    r=client.post('/api/voices',files={'file':('reference.wav',wav_bytes())},data={'name':'Invalid engine','preferred_engine':'whisper'});assert r.status_code==400

def test_preview_dedup_and_cancellation(client,app,tmp_path):
    configure(client,app,tmp_path);body={'engine':'vieneu','language':'vi','text':'SLOW','preset':'Mai Anh'}
    first=client.post('/api/previews',json=body).json();second=client.post('/api/previews',json=body).json();assert second['id']==first['id']
    for _ in range(100):
        if first['id'] in app.PROCESSES:break
        time.sleep(.02)
    assert client.post('/api/jobs/'+first['id']+'/cancel').status_code==200
    assert wait_preview(client,first['id'])['status']=='cancelled'
    assert client.get('/api/jobs/'+first['id']+'/download').status_code==404

def test_queued_job_keeps_model_configuration(client,app,tmp_path,monkeypatch):
    configure(client,app,tmp_path)
    submitted=[];monkeypatch.setattr(app.POOL,'submit',lambda fn,identifier:submitted.append(identifier))
    cfg=app.config('vieneu');cfg['variant']='v3turbo';app.put('settings','vieneu',cfg)
    job=client.post('/api/jobs',json={'engine':'vieneu','text':'Hello','language':'vi','preset':'Hải Đăng'}).json();assert submitted==[job['id']]
    cfg['variant']='v3nano';app.put('settings','vieneu',cfg)
    assert app.get('jobs',job['id'])['config_snapshot']['variant']=='v3turbo'
    assert client.post('/api/jobs/'+job['id']+'/cancel').status_code==200

def test_long_script_and_preview_api_preserve_all_text(client,app,tmp_path,monkeypatch):
    configure(client,app,tmp_path)
    monkeypatch.setattr(app.POOL,'submit',lambda *args:None)
    text='Xin chào. '*10001
    body={'engine':'vieneu','text':text,'language':'vi','preset':'Hải Đăng'}
    for route in ('/api/jobs','/api/previews'):
        r=client.post(route,json=body);assert r.status_code==202,r.text
        identifier=r.json()['id'];assert app.get('jobs',identifier)['text']==text
        assert client.post('/api/jobs/'+identifier+'/cancel').status_code==200
    ref=client.post('/api/voices',files={'file':('test.wav',wav_bytes())},data={'name':'Long transcript','transcript':text})
    assert ref.status_code==200 and ref.json()['transcript']==text

def test_long_native_job_reuses_sdk_and_exports_whole_audio(client,app,tmp_path):
    repo=configure(client,app,tmp_path)
    source=repo/'vieneu.py'
    source.write_text('''import json,wave
from pathlib import Path
LOG=Path(__file__).with_name('chunks.jsonl')
class Vieneu:
 def __init__(self,**kw):
  with LOG.open('a') as f:f.write(json.dumps({'init':kw})+'\\n')
 def infer(self,text,**kw):
  with LOG.open('a') as f:f.write(json.dumps({'text':text,'options':kw})+'\\n')
  return b'\\x01\\x00'*24000
 def save(self,a,p):
  with wave.open(p,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(a)
''')
    text='Nội dung dài được giữ nguyên. '*40
    response=client.post('/api/jobs',json={'engine':'vieneu','text':text,'language':'vi','speed':2,'preset':'Ngọc Trân'})
    assert response.status_code==202,response.text
    job=wait(client,response.json()['id']);assert job['status']=='done',job
    entries=[json.loads(line) for line in (repo/'chunks.jsonl').read_text().splitlines()]
    assert sum('init' in e for e in entries)==1
    calls=[e for e in entries if 'text' in e]
    assert ''.join(e['text'] for e in calls).strip()==text.strip()
    assert len(calls)>1 and all(e['options']['voice']=='Ngọc Trân' for e in calls)
    assert job['processed_chars']==job['total_chars']==len(text)
    audio=client.get('/api/jobs/'+job['id']+'/download')
    with wave.open(io.BytesIO(audio.content)) as w:assert abs(w.getnframes()/w.getframerate()-len(calls)/2)<.08
