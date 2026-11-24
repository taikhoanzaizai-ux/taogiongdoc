"""Regression coverage for the four reported failures and application-local data."""
import importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
import storage,network_support,install_support
from diagnostics import explain

def test_default_data_is_beside_extracted_app_and_explicit_override_wins(tmp_path,monkeypatch):
    monkeypatch.delenv('QUAN_VOICE_DATA',raising=False)
    monkeypatch.setattr(storage,'__file__',str(tmp_path/'app/desktop/storage.py'))
    assert storage.data_dir()==tmp_path/'app/data'
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path/'custom'))
    assert storage.data_dir()==tmp_path/'custom'

def test_all_large_caches_and_temp_follow_app_drive(tmp_path,monkeypatch):
    monkeypatch.setattr(os,'environ',os.environ.copy());monkeypatch.setattr(tempfile,'tempdir',None)
    os.environ['HF_HOME']='old C cache';paths=storage.configure_cache(tmp_path/'drive D/data')
    assert len(paths)>=15
    for key,path in paths.items():assert Path(os.environ[key]).is_relative_to(tmp_path) and path.is_dir()
    with tempfile.NamedTemporaryFile() as file:assert Path(file.name).is_relative_to(tmp_path/'drive D/data/temp')
    info=storage.disk_info(tmp_path/'new/notcreated');assert info['free_bytes']>0
    with pytest.raises(RuntimeError,match='No space left'):storage.require_space(tmp_path,2**99)

def test_migrated_settings_keep_verified_receipt_and_voice(tmp_path,monkeypatch):
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path));monkeypatch.delenv('QUAN_VOICE_SETUP_PROFILE',raising=False)
    spec=importlib.util.spec_from_file_location('storage_server',ROOT/'desktop/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    try:
        old=r'C:\Users\KIU\AppData\Local\QuanVoiceStudio'
        cfg={**m.config('vieneu'),'python':old+r'\envs\vieneu\Scripts\python.exe','repo':old+r'\sources\vieneu'}
        python=tmp_path/'envs/vieneu/Scripts/python.exe';python.parent.mkdir(parents=True);python.write_text('test')
        (tmp_path/'sources/vieneu').mkdir(parents=True)
        m.put('settings','vieneu',cfg);m.put('voices','saved',{'id':'saved','name':'Giọng của Quân'})
        m.put('settings','setup:vieneu',{'state':'ready','fingerprint':m.fingerprint(cfg)})
        (tmp_path/'migration-from-localappdata.done').write_text('\ufeff'+old)
        m.relocate_saved_paths();updated=m.config('vieneu')
        assert updated['python']==str(python) and updated['repo']==str(tmp_path/'sources/vieneu')
        assert m.reusable(m.get('settings','setup:vieneu'),updated,True)
        assert m.get('voices','saved')['name']=='Giọng của Quân'
        m.relocate_saved_paths();assert m.config('vieneu')==updated
    finally:m.POOL.shutdown();m.SETUP_POOL.shutdown()

def test_network_retry_resumes_after_dns_then_stops_on_success(tmp_path,monkeypatch):
    count=tmp_path/'count';delays=[];monkeypatch.setattr(network_support.time,'sleep',delays.append)
    code="from pathlib import Path;import sys;p=Path(sys.argv[1]);n=int(p.read_text())+1 if p.exists() else 1;p.write_text(str(n));print('dns error: No such host is known (11001)' if n==1 else 'OK');sys.exit(1 if n==1 else 0)"
    network_support.run_download([sys.executable,'-c',code,str(count)])
    assert count.read_text()=='2' and delays==[5]

@pytest.mark.parametrize('message',['No space left on device','403 client error','certificate_verify_failed'])
def test_non_network_failure_is_not_retried(message,monkeypatch):
    monkeypatch.setattr(network_support.time,'sleep',lambda _:pytest.fail('Should not retry'))
    with pytest.raises(subprocess.CalledProcessError):network_support.run_download([sys.executable,'-c',f'print({message!r});raise SystemExit(1)'])

def test_wsl_probe_restarts_only_owned_distro(monkeypatch):
    calls=[]
    def run(args,**kw):
        calls.append(args)
        return subprocess.CompletedProcess(args,1 if len(calls)==1 else 0,b'WSL E_FAIL',b'')
    monkeypatch.setattr(install_support.subprocess,'run',run);install_support.check_fish_launch()
    assert calls[1]==['wsl.exe','--terminate','QuanVoice-Fish']
    assert calls[0]==calls[2] and all('--shutdown' not in c and '--unregister' not in c for c in calls)

def test_wsl_still_failing_preserves_original_error(monkeypatch):
    def run(args,**kw):return subprocess.CompletedProcess(args,1,'Wsl/Service/CreateInstance/E_FAIL'.encode('utf-16'),b'')
    monkeypatch.setattr(install_support.subprocess,'run',run)
    with pytest.raises(RuntimeError,match='E_FAIL') as error:install_support.check_fish_launch()
    assert 'SUA_FISH_WSL.bat' in str(error.value)

@pytest.mark.parametrize('engine,message,expected',[
 ('gpt-sovits','dns error: No such host is known. (os error 11001)','tên miền'),
 ('index-tts','OSError: [Errno 28] No space left on device','không đủ chỗ'),
 ('vibevoice','Can only SETITEMS for dict but got BaseModelOutputWithPast','tệp giọng'),
 ('fish-speech','The distribution failed to start. Wsl/Service/CreateInstance/E_FAIL','WSL2')])
def test_four_screenshots_have_specific_diagnostics(engine,message,expected):
    assert expected in explain(engine,message)[0]
