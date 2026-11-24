"""Real loopback sockets and Uvicorn; no native GUI or model downloads."""
import json,os,socket,subprocess,sys,threading,types,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
from local_server import Session,DataLock,VERSION,existing_url,reserve_socket

@pytest.fixture
def busy_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));sock.listen()
        yield sock.getsockname()[1]

@pytest.fixture
def health_server(tmp_path):
    value={'product':'QuanVoiceStudio','version':VERSION,'data_dir':str(tmp_path)}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            raw=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield http.server_port,value
    http.shutdown();http.server_close();thread.join()

def test_busy_port_uses_another_port_and_keeps_it_reserved(tmp_path,busy_port):
    session=Session(tmp_path,ports=(busy_port,0)).open()
    try:
        assert session.owned and session.socket.getsockname()[1]!=busy_port
        record=json.loads((tmp_path/'server-instance.json').read_text());assert record['port']==session.socket.getsockname()[1]
        with socket.socket() as rival:
            with pytest.raises(OSError):rival.bind(('127.0.0.1',record['port']))
    finally:session.close()
    assert not (tmp_path/'server-instance.json').exists()
    with socket.socket() as reuse:reuse.bind(('127.0.0.1',record['port']))

def test_existing_instance_reused_from_saved_port(tmp_path,health_server):
    port,value=health_server;(tmp_path/'server-instance.json').write_text(json.dumps({'port':port,'pid':1}))
    session=Session(tmp_path).open()
    try:assert not session.owned and session.socket is None and session.url==f'http://127.0.0.1:{port}'
    finally:session.close()
    assert (tmp_path/'server-instance.json').exists()  # not owned, never remove it

def test_unrelated_http_app_or_other_data_does_not_get_reused(tmp_path,health_server):
    port,value=health_server
    for update in ({'product':'OtherApp'},{'product':'QuanVoiceStudio','data_dir':str(tmp_path/'other library')}):
        value.update(update);assert existing_url(tmp_path,[port]) is None

def test_legacy_version_gets_clear_close_instruction(tmp_path,health_server):
    port,value=health_server;value['version']='1.4.1'
    with pytest.raises(RuntimeError,match='phiên Studio cũ'):existing_url(tmp_path,[port])

def test_stale_record_does_not_block_launch(tmp_path):
    (tmp_path/'server-instance.json').write_text('{invalid JSON')
    session=Session(tmp_path,ports=(0,)).open()
    try:assert session.owned and json.loads((tmp_path/'server-instance.json').read_text())['pid']==os.getpid()
    finally:session.close()

def test_data_lock_prevents_second_backend_and_releases_on_process_exit(tmp_path):
    first=DataLock(tmp_path);second=DataLock(tmp_path);assert first.acquire()
    try:assert not second.acquire()
    finally:first.close()
    assert second.acquire();second.close()
    code="import sys;sys.path.insert(0,sys.argv[1]);from local_server import DataLock;x=DataLock(sys.argv[2]);assert x.acquire();raise SystemExit(0)"
    subprocess.run([sys.executable,'-c',code,str(ROOT/'desktop'),str(tmp_path)],check=True)
    assert first.acquire();first.close()  # OS released the dead process lock

def test_desktop_opens_real_server_on_fallback_port(tmp_path,busy_port,monkeypatch):
    from fastapi import FastAPI
    import desktop_app,local_server
    app=FastAPI();fake_server=types.SimpleNamespace(app=app)
    @app.get('/api/health')
    def health():return {'product':'QuanVoiceStudio','version':VERSION,'data_dir':str(tmp_path)}
    @app.get('/api/status')
    def status():return {'local_url':app.state.local_url}
    seen={}
    def start(**kw):
        with urllib.request.urlopen(seen['url']+'/api/health') as response:assert json.load(response)['version']==VERSION
        with urllib.request.urlopen(seen['url']+'/api/status') as response:assert json.load(response)['local_url']==seen['url']
        app.state.request_exit()
    fake_webview=types.SimpleNamespace(settings={},create_window=lambda title,url,**kw:(seen.update(url=url) or types.SimpleNamespace(destroy=lambda:seen.update(closed=True))),start=start)
    monkeypatch.setitem(sys.modules,'server',fake_server);monkeypatch.setitem(sys.modules,'webview',fake_webview)
    monkeypatch.setattr(desktop_app,'DATA',tmp_path);monkeypatch.setattr(desktop_app,'URL','http://127.0.0.1:'+str(busy_port));monkeypatch.setattr(desktop_app,'probe',lambda:None)
    real_session=local_server.Session;monkeypatch.setattr(local_server,'Session',lambda data:real_session(data,ports=(busy_port,0)))
    desktop_app.main()
    assert seen['url']!='http://127.0.0.1:'+str(busy_port) and seen['closed']
    assert not (tmp_path/'server-instance.json').exists()
    lock=DataLock(tmp_path);assert lock.acquire();lock.close()


def test_previous_backend_requires_restart_for_new_export_api(tmp_path,health_server):
    port,value=health_server;value['version']='1.4.2'
    with pytest.raises(RuntimeError,match='phiên Studio cũ'):existing_url(tmp_path,[port])
