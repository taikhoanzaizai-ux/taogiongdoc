import json, os, sqlite3, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parent
from storage import data_dir, configure_cache
data=data_dir()
configure_cache(data)
e=sys.argv[1] if len(sys.argv)>1 else 'gpt-sovits'
if e not in ('gpt-sovits','fish-speech'):raise SystemExit('Only gpt-sovits or fish-speech')
with sqlite3.connect(data/'studio.db') as c:r=c.execute('SELECT value FROM settings WHERE id=?',(e,)).fetchone()
if not r:raise SystemExit('Hay cai mo hinh trong Kho mo hinh truoc.')
cfg=json.loads(r[0]);os.environ['HF_HOME']=str(data/'cache'/'huggingface')
if e=='gpt-sovits':args=[cfg['python'],'api_v2.py','-a','127.0.0.1','-p','9880','-c','GPT_SoVITS/configs/tts_infer.yaml']
else:args=[cfg['python'],'tools/api_server.py','--listen','127.0.0.1:8080','--llama-checkpoint-path','checkpoints/s2-pro','--decoder-checkpoint-path','checkpoints/s2-pro/codec.pth','--decoder-config-name','modded_dac_vq']
subprocess.run(args,cwd=cfg['repo'],env=os.environ,check=True)
