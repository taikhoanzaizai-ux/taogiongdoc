"""Resident workers and preference persistence, using isolated deterministic SDKs."""
import importlib.util,json,os,sys,threading,time,types,wave
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
from runtime_manager import RuntimeManager

@pytest.fixture
def resident(tmp_path):
    repo=tmp_path/'fake-sdk';repo.mkdir();data=tmp_path/'data'
    for folder in ('jobs','logs','outputs'):(data/folder).mkdir(parents=True)
    (repo/'vieneu.py').write_text('''import json,os,time,wave
from pathlib import Path
LOG=Path(__file__).with_name('calls.jsonl')
def record(x):
 with LOG.open('a') as f:f.write(json.dumps(x)+'\\n')
class Vieneu:
 def __init__(self,**kw):record({'init':kw,'offline':os.environ.get('HF_HUB_OFFLINE')})
 def infer(self,text,**kw):
  record({'text':text,'options':kw})
  if text=='SLOW':time.sleep(20)
  return b'\\x01\\x00'*2400
 def save(self,a,p):
  with wave.open(p,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(a)
''')
    cfg={'repo':str(repo),'python':sys.executable,'device':'cpu','variant':'v3turbo','_cached_only':True}
    manager=RuntimeManager(ROOT/'desktop',data)
    def payload(identifier,**values):
        out=data/'outputs'/identifier;out.mkdir(exist_ok=True)
        p={'engine':'vieneu','config':cfg,'text':'Hello','language':'vi','preset':'Hải Đăng','output':str(out/'raw.wav'),**values}
        path=data/'jobs'/(identifier+'.json');path.write_text(json.dumps(p));return path
    yield manager,cfg,payload,repo
    manager.stop()

def test_worker_warm_reused_across_jobs_and_clone_changes(resident):
    m,cfg,payload,repo=resident
    m.run('vieneu',cfg,payload('warm'),'warm',warm=True);pid=m.process.pid
    m.run('vieneu',cfg,payload('one',preset='Trúc Ly'),'one')
    m.run('vieneu',cfg,payload('two',ref='my saved voice.wav',preset=''),'two')
    assert m.process.pid==pid and m.describe()['loaded'] and m.loads==1
    calls=[json.loads(x) for x in (repo/'calls.jsonl').read_text().splitlines()]
    assert sum('init' in x for x in calls)==1
    assert calls[0]['offline']=='1'
    assert calls[1]['options']['voice']=='Trúc Ly' and calls[2]['options']['ref_audio']=='my saved voice.wav'

def test_switch_config_releases_old_worker(resident):
    m,cfg,payload,repo=resident;m.run('vieneu',cfg,payload('one'),'one');old=m.process
    cfg['variant']='v3nano';m.run('vieneu',cfg,payload('two'),'two')
    assert old.poll() is not None and m.process.pid!=old.pid and m.loads==2
    m.stop();assert not m.describe()['loaded']

def test_cancel_resident_job_stops_worker_and_next_job_can_run(resident):
    m,cfg,payload,repo=resident;cancel=threading.Event();errors=[]
    def run():
        try:m.run('vieneu',cfg,payload('slow',text='SLOW'),'slow',cancelled=cancel.is_set)
        except RuntimeError as e:errors.append(str(e))
    t=threading.Thread(target=run);t.start()
    for _ in range(100):
        if (repo/'calls.jsonl').exists() and 'SLOW' in (repo/'calls.jsonl').read_text():break
        time.sleep(.03)
    cancel.set();t.join(timeout=5)
    assert not t.is_alive() and errors and not m.describe()['loaded']
    m.run('vieneu',cfg,payload('next'),'next');assert m.describe()['loaded']

def load_server(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'desktop/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_preferences_and_saved_voice_survive_server_restart(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path));monkeypatch.delenv('QUAN_VOICE_SETUP_PROFILE',raising=False)
    a=load_server('preference_first');b=None
    try:
        a.put('voices','voice1',{'id':'voice1','name':'Giọng đã lưu','preferred_engine':'vieneu'})
        c=TestClient(a.app)
        body={'engine':'vieneu','voice':'voice1','preset':'','speed':1.2,'warm_on_start':True,'cached_only':True,'theme':{'mode':'dark','accent':'#2563eb'},'text':'Kịch bản đã lưu'}
        assert c.put('/api/preferences',json=body).status_code==200
        assert c.post('/api/preferences',json={'speed':1.5}).json()['voice']=='voice1'
        b=load_server('preference_second');d=TestClient(b.app)
        restored=d.get('/api/preferences').json();assert restored['voice']=='voice1' and restored['speed']==1.5 and restored['text']=='Kịch bản đã lưu'
        assert d.get('/api/voices').json()[0]['name']=='Giọng đã lưu'
        assert d.put('/api/preferences',json={'engine':'whisper'}).status_code==400
    finally:
        for m in (a,b):
            if m:m.RUNTIME.stop();m.POOL.shutdown();m.SETUP_POOL.shutdown()

def test_reopen_does_not_reinstall_saved_models(tmp_path,monkeypatch):
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path));monkeypatch.setenv('QUAN_VOICE_SETUP_PROFILE','all')
    m=load_server('startup_policy')
    try:
        m.put('settings','setup:vieneu',{'state':'ready'});m.put('settings','ui_preferences',{'warm_on_start':False})
        monkeypatch.setattr(m,'schedule_setup',lambda e:pytest.fail('Reinstalled '+e))
        m.automatic_setup();m.automatic_setup()
        assert m.get('settings','automatic_setup_requested') is True
    finally:m.RUNTIME.stop();m.POOL.shutdown();m.SETUP_POOL.shutdown()

def test_native_window_remembers_webview_profile(tmp_path,monkeypatch):
    import desktop_app
    seen={}
    fake=types.SimpleNamespace(settings={},create_window=lambda *a,**kw:seen.update(window=kw),start=lambda **kw:seen.update(start=kw))
    monkeypatch.setitem(sys.modules,'webview',fake);monkeypatch.setattr(desktop_app,'DATA',tmp_path)
    monkeypatch.setattr(desktop_app,'probe',lambda:{'product':'QuanVoiceStudio','version':'1.5.4'})
    desktop_app.main()
    assert seen['start']['private_mode'] is False
    assert seen['start']['storage_path']==str(tmp_path/'desktop-profile')
    assert seen['window']['min_size']==(980,650) and fake.settings['ALLOW_DOWNLOADS']

def test_vibe_sdk_loads_once_and_copies_voice_cache(tmp_path,monkeypatch):
    import contextlib
    from adapter import EngineRuntime
    events={'model':0,'processor':0,'voice':0,'prompts':[]}
    def module(name):
        m=types.ModuleType(name);m.__path__=[];monkeypatch.setitem(sys.modules,name,m);return m
    for name in ('vibevoice','vibevoice.modular','vibevoice.processor','transformers'):module(name)
    torch=module('torch');torch.float32='float32';torch.bfloat16='bfloat16';torch.is_tensor=lambda v:False;torch.inference_mode=contextlib.nullcontext
    torch.serialization=types.SimpleNamespace(safe_globals=lambda _:contextlib.nullcontext())
    def load(*a,**kw):events['voice']+=1;return {'original':True}
    torch.load=load
    module('transformers.cache_utils').DynamicCache=type('DynamicCache',(),{})
    module('transformers.modeling_outputs').BaseModelOutputWithPast=type('BaseModelOutputWithPast',(),{})
    class Model:
        @classmethod
        def from_pretrained(cls,*a,**kw):events['model']+=1;return cls()
        def eval(self):pass
        def set_ddpm_inference_steps(self,**kw):pass
        def generate(self,**kw):
            assert kw['all_prefilled_outputs']['original'];kw['all_prefilled_outputs']['original']=False
            return types.SimpleNamespace(speech_outputs=[b'audio'])
    class Processor:
        tokenizer=object()
        @classmethod
        def from_pretrained(cls,*a,**kw):events['processor']+=1;return cls()
        def process_input_with_cached_prompt(self,**kw):events['prompts'].append(kw['cached_prompt']['original']);return {}
        def save_audio(self,a,output_path):
            with wave.open(output_path,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x00\x00'*100)
    module('vibevoice.modular.modeling_vibevoice_streaming_inference').VibeVoiceStreamingForConditionalGenerationInference=Model
    module('vibevoice.processor.vibevoice_streaming_processor').VibeVoiceStreamingProcessor=Processor
    voice=tmp_path/'demo/voices/streaming_model/en-carter_man.pt';voice.parent.mkdir(parents=True);voice.write_bytes(b'fixture')
    p={'engine':'vibevoice','config':{'repo':str(tmp_path),'device':'cpu'},'preset':'en-carter_man','text':'Hello','language':'en','output':str(tmp_path/'one.wav')}
    r=EngineRuntime(p);r.run(p);r.run({**p,'text':'Another sentence','output':str(tmp_path/'two.wav')})
    assert events=={'model':1,'processor':1,'voice':1,'prompts':[True,True]}
