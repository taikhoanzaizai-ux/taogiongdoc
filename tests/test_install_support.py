from pathlib import Path
import importlib.util,json,sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
from install_support import windows_gpt_requirements,patch_jieba,decode_wsl_output,ensure_source
from diagnostics import explain,redact

def test_gpt_windows_requirements_do_not_force_cpp_builds():
    req='--no-binary=opencc\nnumpy<2.0\nopencc\njieba_fast\npyopenjtalk>=0.4.1\nonnxruntime-gpu; platform_machine == "AMD64"\nfunasr>=1.3.7\n'
    fixed=windows_gpt_requirements(req)
    assert 'numpy<2.0' in fixed and 'funasr>=1.3.7' in fixed
    assert '--no-binary' not in fixed and 'jieba_fast' not in fixed and 'onnxruntime-gpu' not in fixed
    assert 'opencc-python-reimplemented==0.1.7' in fixed and 'pyopenjtalk-plus==0.4.1.post9' in fixed

def test_jieba_patch_preserves_original_and_is_idempotent(tmp_path):
    p=tmp_path/'GPT_SoVITS/text/chinese.py';p.parent.mkdir(parents=True)
    original='import jieba_fast\nimport jieba_fast.posseg as psg\nwords=jieba_fast.lcut("你好")\n';p.write_text(original)
    assert len(patch_jieba(tmp_path))==1
    assert p.with_suffix('.py.quanvoice-original').read_text()==original
    assert 'jieba_fast' not in p.read_text() and 'import jieba.posseg as psg' in p.read_text()
    assert patch_jieba(tmp_path)==[]

@pytest.mark.parametrize('encoding',['utf-8','utf-16','utf-16-le'])
def test_wsl_output_formats(encoding):
    text='QuanVoice-Fish\r\nUbuntu\r\n'
    assert decode_wsl_output(text.encode(encoding))==text

def test_partial_bundled_source_repair_keeps_user_files(tmp_path):
    bundled=tmp_path/'bundled';bundled.mkdir()
    for name in ('pyproject.toml','demo/realtime_model_inference_from_file.py'):
        p=bundled/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('bundled')
    repo=tmp_path/'source';repo.mkdir();(repo/'pyproject.toml').write_text('custom user settings')
    ensure_source('vibevoice',{},repo,bundled,tmp_path/'unused-lock')
    assert (repo/'pyproject.toml').read_text()=='custom user settings'
    assert (repo/'demo/realtime_model_inference_from_file.py').read_text()=='bundled'

def test_diagnostics_distinguishes_known_and_unknown_errors():
    assert 'WSL' in explain('fish-speech','WSL2 chưa sẵn sàng: restart')[0]
    assert 'biên dịch' in explain('gpt-sovits','Failed building wheel for opencc')[0]
    assert 'bộ nhớ' in explain('vibevoice','RuntimeError: out of memory')[0]
    assert 'thông báo gốc' in explain('vibevoice','unknown error')[0]
    assert 'hf_' not in redact('token hf_'+'a'*30)

def test_combined_setup_diagnostics_has_service_log_and_no_script(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('QUAN_VOICE_DATA',str(tmp_path));monkeypatch.delenv('QUAN_VOICE_SETUP_PROFILE',raising=False)
    spec=importlib.util.spec_from_file_location('diagnostic_server',ROOT/'desktop/server.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    try:
        app.put('jobs','job1',{'id':'job1','engine':'gpt-sovits','type':'setup_engine','status':'failed','text':'PRIVATE SCRIPT','error':'API failed'})
        app.put('settings','setup:gpt-sovits',{'state':'failed','job_id':'job1'})
        (tmp_path/'logs/job1.log').write_text('Installation output')
        (tmp_path/'logs/service-gpt-sovits.log').write_text('ModuleNotFoundError: No module named torchaudio')
        client=TestClient(app.app);r=client.get('/api/engines/gpt-sovits/diagnostics')
        assert r.status_code==200 and 'torchaudio' in r.json()['log']
        assert 'PRIVATE SCRIPT' not in r.text
        report=client.get('/api/diagnostics/download')
        assert report.status_code==200 and 'attachment' in report.headers['content-disposition']
        assert 'PRIVATE SCRIPT' not in report.text and 'Installation output' in report.text
        assert client.get('/api/engines/unknown/diagnostics').status_code==404
    finally:app.POOL.shutdown();app.SETUP_POOL.shutdown()
