"""Screenshot regression: real SQLite + missing aliases -> real FastAPI startup.

Runs on Linux with PowerShell; native junction/GUI checks still need Windows.
"""
import importlib.util,json,os,shutil,sqlite3,subprocess,sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('legacy_json',[False,True])
@pytest.mark.parametrize('foreign',[False,True])
def test_missing_inplace_folders_allow_startup_and_preserve_saved_data(tmp_path,monkeypatch,foreign,legacy_json):
    pwsh=os.environ.get('QV_TEST_PWSH') or shutil.which('pwsh')
    if not pwsh or os.name=='nt':pytest.skip('PowerShell/Linux filesystem test')
    legacy=tmp_path/'old C'/'QuanVoiceStudio';data=tmp_path/'E Phần mềm'/'QuanVoice-Studio'/'data'
    legacy.mkdir(parents=True);data.mkdir(parents=True)
    names=['app-env','cache','jobs','logs','models','sources','envs','tools','runtimes','voices','preview_refs','outputs','references','unknown-legacy-folder']
    owner=tmp_path/'E Phần mềm cũ'/'QuanVoice-Studio'/'data' if foreign else data
    for name in names:(legacy/name).symlink_to(owner/name,target_is_directory=True)
    (data/'sources'/'vieneu').mkdir(parents=True)
    with sqlite3.connect(legacy/'studio.db') as db:
        for table in ['settings','voices','jobs','preview_refs']:db.execute(f'CREATE TABLE {table} (id TEXT PRIMARY KEY, value TEXT)')
        db.execute('INSERT INTO settings VALUES (?,?)',('vieneu',json.dumps({'repo':str(owner/'sources'/'vieneu')})))
        db.execute('INSERT INTO settings VALUES (?,?)',('retained',json.dumps({'keep':'saved preferences'})))
        db.execute('INSERT INTO settings VALUES (?,?)',('ui_preferences',json.dumps({'warm_on_start':False})))
        db.execute('INSERT INTO voices VALUES (?,?)',('saved-voice',json.dumps({'id':'saved-voice','name':'Giọng cũ','language':'vi','transcript':'Xin chào','kind':'voice'})))
    script=tmp_path/'migrate.ps1'
    shim="""function ConvertFrom-Json {
[CmdletBinding()]
param([Parameter(ValueFromPipeline=$true)][string]$InputObject)
process{$parsed=Microsoft.PowerShell.Utility\\ConvertFrom-Json -InputObject $InputObject -NoEnumerate;$PSCmdlet.WriteObject($parsed,$false)}
}
""" if legacy_json else ''
    script.write_text("$ErrorActionPreference='Stop'\n"+shim+". (Join-Path $env:QV_SOURCE 'windows/portable-data.ps1')\nInitialize-PortableData $env:QV_SOURCE $env:QV_DEST\n",encoding='utf-8-sig')
    result=subprocess.run([pwsh,'-NoProfile','-File',str(script)],env={**os.environ,'LOCALAPPDATA':str(legacy.parent),'QV_SOURCE':str(ROOT),'QV_DEST':str(data)},capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    assert all((data/n).is_dir() for n in names)
    assert (data/'migration-from-localappdata.done').is_file()
    records=json.loads((data/'migration-link-recovery.json').read_text(encoding='utf-8-sig'))
    assert len(records)==len(names)-(0 if foreign else 1) and not any(r['source_available'] for r in records)
    monkeypatch.setenv('QUAN_VOICE_DATA',str(data));monkeypatch.setenv('QUAN_VOICE_SETUP_PROFILE','none')
    sys.path.insert(0,str(ROOT/'desktop'))
    spec=importlib.util.spec_from_file_location('migration_startup',ROOT/'desktop/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    try:
        with TestClient(m.app) as client:
            assert client.get('/api/health').status_code==200
            status=client.get('/api/status');assert status.status_code==200 and len(status.json()['engines'])==7
            assert 'Xuất SRT' in client.get('/app.js').text
            assert m.get('settings','vieneu')['repo']==str(data/'sources'/'vieneu')
            assert m.get('settings','retained')=={'keep':'saved preferences'}
            assert client.get('/api/voices').json()[0]['name']=='Giọng cũ'
            missing=client.get('/api/voices/saved-voice/audio');assert missing.status_code==404 and 'Nhập lại' in missing.json()['detail']
            create=client.post('/api/jobs',json={'engine':'vieneu','language':'vi','text':'Xin chào','voice_id':'saved-voice'})
            assert create.status_code==400 and 'Nhập lại' in create.json()['detail']
            assert client.get('/api/jobs').json()==[]
    finally:m.RUNTIME.stop();m.POOL.shutdown();m.SETUP_POOL.shutdown()
