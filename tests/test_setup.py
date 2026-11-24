"""Setup orchestration tests: isolated SDK processes, no large model downloads."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
import setup_policy, services

@pytest.fixture
def studio(tmp_path,monkeypatch):
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path))
    monkeypatch.delenv('QUAN_VOICE_SETUP_PROFILE',raising=False)
    spec=importlib.util.spec_from_file_location('setup_server',ROOT/'desktop/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    yield m
    m.SETUP_POOL.shutdown(wait=True);m.POOL.shutdown(wait=True)

def test_profiles_and_receipt_fingerprint():
    assert len(setup_policy.selected('all'))==7
    assert setup_policy.selected('recommended')==('vieneu','whisper')
    assert setup_policy.selected('none')==()
    with pytest.raises(ValueError):setup_policy.selected('invalid')
    cfg={'repo':'a path with spaces','device':'cpu'}
    receipt={'state':'ready','fingerprint':setup_policy.fingerprint(cfg)}
    assert setup_policy.reusable(receipt,cfg,True)
    assert not setup_policy.reusable(receipt,{**cfg,'device':'cuda'},True)
    assert not setup_policy.reusable(receipt,cfg,False)

def test_schedule_duplicates_and_skip_verified(studio,monkeypatch):
    submitted=[];monkeypatch.setattr(studio.SETUP_POOL,'submit',lambda *a:submitted.append(a))
    a=studio.schedule_setup('vieneu');b=studio.schedule_setup('vieneu')
    assert a['id']==b['id'] and len(submitted)==1
    studio.patch_job(a['id'],status='done')
    cfg=studio.config('vieneu');studio.put('settings','setup:vieneu',{'state':'ready','fingerprint':setup_policy.fingerprint(cfg)})
    monkeypatch.setattr(studio,'engine_status',lambda e:{'installed':True})
    assert studio.schedule_setup('vieneu') is None
    cfg['variant']='v3nano';studio.put('settings','vieneu',cfg)
    assert studio.schedule_setup('vieneu')['id']!=a['id']

def test_failed_model_does_not_stop_next_model(studio,monkeypatch):
    monkeypatch.setattr(studio.SETUP_POOL,'submit',lambda *a:None)
    first=studio.schedule_setup('vieneu');second=studio.schedule_setup('whisper')
    calls=[]
    def process(identifier,args,cwd=None):
        calls.append(args)
        if identifier==first['id']:raise RuntimeError('Interrupted download')
    monkeypatch.setattr(studio,'run_process',process)
    studio.run_setup_job(first['id']);studio.run_setup_job(second['id'])
    assert studio.get('jobs',first['id'])['status']=='failed'
    assert studio.get('settings','setup:vieneu')['state']=='failed'
    assert studio.get('jobs',second['id'])['status']=='done'
    assert studio.get('settings','setup:whisper')['state']=='ready'
    assert any('prepare_model.py' in str(a) for a in calls)

def test_cancel_queued_setup_never_runs(studio,monkeypatch):
    monkeypatch.setattr(studio.SETUP_POOL,'submit',lambda *a:None)
    job=studio.schedule_setup('vieneu');studio.patch_job(job['id'],status='cancelled')
    monkeypatch.setattr(studio,'run_process',lambda *a:pytest.fail('Cancelled work ran'))
    studio.run_setup_job(job['id']);assert studio.get('jobs',job['id'])['status']=='cancelled'

def test_setup_api_validation_and_real_queue(studio,monkeypatch):
    monkeypatch.setattr(studio.SETUP_POOL,'submit',lambda *a:None)
    client=TestClient(studio.app)
    assert client.post('/api/setup/start',json={'profile':'wrong'}).status_code==400
    assert client.post('/api/setup/engine/unknown').status_code==404
    result=client.post('/api/setup/start',json={'profile':'all'})
    assert result.status_code==202 and len(result.json()['scheduled'])==7
    assert len(client.get('/api/setup').json())==7
    assert all(j['type']=='setup_engine' for j in client.get('/api/jobs').json())

def test_failed_receipt_not_advertised_available(studio,monkeypatch):
    studio.put('settings','setup:vieneu',{'state':'failed','error':'No weights'})
    cfg=studio.config('vieneu');studio.INSTALLED_CACHE[(cfg['python'],cfg['repo'],'vieneu')]=(__import__('time').time(),True)
    state=studio.engine_status('vieneu');assert state['installed'] and not state['available']

def test_service_argv_keeps_paths_and_localhost():
    cfg={'python':'C:/path with spaces/python.exe','endpoint':'http://127.0.0.1:9880','device':'cpu'}
    args=services.command('gpt-sovits',cfg);assert args[0]==cfg['python'];assert args[args.index('-a')+1]=='127.0.0.1'
    with pytest.raises(ValueError):services.command('gpt-sovits',{**cfg,'endpoint':'http://outside.example:9880'})
    fish=services.command('fish-speech',{**cfg,'endpoint':'http://127.0.0.1:8080','wsl_distro':'QuanVoice-Fish'})
    assert fish[:3]==['wsl.exe','-d','QuanVoice-Fish'] and '--device' in fish
    with pytest.raises(ValueError):services.command('fish-speech',{**cfg,'wsl_distro':'MyPersonalUbuntu'})

def test_manifest_assets_and_offline_wheel_target():
    m=json.loads((ROOT/'windows/assets-manifest.json').read_text())
    assert {x['file'] for x in m['assets']}=={'python-installer.exe','mingit.zip','ffmpeg.zip','vc_redist.x64.exe'}
    assert len(m['wheels'])>=10
    for entry in [*m['assets'],*m['wheels']]:assert len(entry['sha256'])==64 and entry['bytes']>0
    from packaging.tags import cpython_tags,compatible_tags
    from packaging.utils import parse_wheel_filename
    target=set(cpython_tags((3,11),platforms=['win_amd64']))|set(compatible_tags((3,11),'cp311',['win_amd64']))
    for x in m['wheels']:
        assert target.intersection(parse_wheel_filename(Path(x['file']).name)[3]),x['file']
