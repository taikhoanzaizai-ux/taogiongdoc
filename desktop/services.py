"""Start only local, configured API services. Never use shell interpolation."""
import atexit, os, subprocess, threading, time
from pathlib import Path
from urllib.parse import urlparse
import httpx
OWNED={};LOCK=threading.RLock()
def healthy(engine,cfg):
    u=urlparse(cfg['endpoint'])
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.password or u.path not in ('','/'):return False
    try:return httpx.get(cfg['endpoint'].rstrip('/')+('/docs' if engine=='gpt-sovits' else '/v1/health'),timeout=1,trust_env=False).status_code==200
    except Exception:return False
def command(engine,cfg):
    u=urlparse(cfg['endpoint']);port=u.port or 80
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.password or u.path not in ('','/'):raise ValueError('API phải ở localhost')
    if engine=='gpt-sovits':return [cfg['python'],'api_v2.py','-a','127.0.0.1','-p',str(port),'-c','GPT_SoVITS/configs/tts_infer.yaml']
    args=['tools/api_server.py','--listen','127.0.0.1:'+str(port),'--device',cfg['device'],'--llama-checkpoint-path','checkpoints/s2-pro','--decoder-checkpoint-path','checkpoints/s2-pro/codec.pth','--decoder-config-name','modded_dac_vq']
    if cfg.get('wsl_distro'):
        if cfg['wsl_distro']!='QuanVoice-Fish':raise ValueError('Unknown managed WSL distribution')
        # A fixed script writes its own PID; paths and options remain separate argv.
        return ['wsl.exe','-d','QuanVoice-Fish','-u','root','--cd','/opt/quanvoice/fish-speech','--exec','bash','-c','echo $$ > /opt/quanvoice/fish-service.pid; exec "$@"','quanvoice-service','env','HF_HOME=/opt/quanvoice/cache/huggingface',*(['HF_HUB_OFFLINE=1','TRANSFORMERS_OFFLINE=1'] if cfg.get('_cached_only') else []),'/opt/quanvoice/fish-speech/.venv/bin/python',*args]
    return [cfg['python'],*args]
def stop_all():
    with LOCK:
        for engine,(p,cfg) in list(OWNED.items()):
            if cfg.get('wsl_distro'):
                script='p=$(cat /opt/quanvoice/fish-service.pid 2>/dev/null) || exit 0; case "$p" in ""|*[!0-9]*) exit 0;; esac; if tr "\\0" " " < /proc/$p/cmdline 2>/dev/null | grep -q "/opt/quanvoice/fish-speech/.venv/bin/python tools/api_server.py"; then kill "$p"; fi'
                try:subprocess.run(['wsl.exe','-d','QuanVoice-Fish','-u','root','--exec','sh','-c',script],capture_output=True,timeout=10)
                except Exception:pass
            if p.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
                else:p.terminate()
            OWNED.pop(engine,None)
def ensure(engine,cfg,data,timeout=600,cancelled=lambda:False):
    with LOCK:
        if healthy(engine,cfg):return
        if not cfg.get('auto_start'):raise RuntimeError('API chưa chạy. Bấm Cài tự động trong Kho mô hình.')
        stop_all();log=Path(data)/'logs'/('service-'+engine+'.log')
        with log.open('a',encoding='utf-8') as f:
            env=os.environ.copy()
            if cfg.get('_cached_only'):env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
            p=subprocess.Popen(command(engine,cfg),cwd=None if cfg.get('wsl_distro') else cfg['repo'],stdout=f,stderr=subprocess.STDOUT,env=env)
        OWNED[engine]=(p,cfg);end=time.monotonic()+timeout
        while time.monotonic()<end:
            if cancelled():stop_all();raise RuntimeError('Đã hủy khởi động API')
            if healthy(engine,cfg):return
            if p.poll() is not None:break
            time.sleep(1)
        stop_all();raise RuntimeError('API không khởi động được. '+log.read_text(encoding='utf-8',errors='replace')[-2000:])
atexit.register(stop_all)
