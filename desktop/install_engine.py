"""Install only the explicitly selected engine; never share ML environments."""
import json, os, shutil, subprocess, sys
from install_support import ensure_source, windows_gpt_requirements, patch_jieba
from pathlib import Path
from storage import configure_cache, require_space, remaining_space
from network_support import run_download
ROOT=Path(__file__).resolve().parent
engine=sys.argv[1];data=Path(sys.argv[2]);web=ROOT/'web' if (ROOT/'web').exists() else ROOT.parent/'dist'
configure_cache(data)
os.environ.setdefault('UV_HTTP_RETRIES','5')
os.environ.setdefault('UV_HTTP_TIMEOUT','120')
require_space(data,512*2**20)
catalog={e['id']:e for e in json.loads((web/'engines.json').read_text(encoding='utf-8'))}
if engine not in catalog:raise ValueError('Unknown engine')
if engine=='fish-speech' and os.name=='nt':
    raise SystemExit('Fish Speech bản hiện tại yêu cầu Linux/WSL. Dùng HUONG_DAN.md để cài trong WSL; sau đó kết nối API http://127.0.0.1:8080 trong Kho mô hình.')
e=catalog[engine];repo=data/'sources'/engine;bundled=ROOT.parent/'upstream'/engine
print('Chuẩn bị mã nguồn '+e['repo'],flush=True)
if engine=='omnivoice':repo.mkdir(parents=True,exist_ok=True)
else:ensure_source(engine,e,repo,bundled,ROOT/'sources.lock.json')
def uv(*args,cwd=None):run_download([sys.executable,'-m','uv',*map(str,args)],cwd=cwd)
if engine in ('index-tts','fish-speech'):
    args=['sync','--python',e['python'],'--extra','webui'] if engine=='index-tts' else ['sync','--python',e['python'],'--extra','cpu']
    uv(*args,cwd=repo);env=repo/'.venv'
else:
    env=data/'envs'/engine
    if not (env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')).is_file():uv('venv','--allow-existing','--python',e['python'],env)
    py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if os.name=='nt' and engine in ('gpt-sovits','vibevoice'):
        print('Kiểm tra cặp PyTorch / torchaudio cho Windows CPU...',flush=True)
        probe=subprocess.run([str(py),'-c','import torch,torchaudio'],capture_output=True)
        if probe.returncode:
            print(probe.stderr.decode('utf-8',errors='replace')[-1500:],flush=True)
            uv('pip','install','--python',py,'--reinstall-package','torch','--reinstall-package','torchaudio','torch','torchaudio','--index-url','https://download.pytorch.org/whl/cpu')
    if engine=='omnivoice':
        device=sys.argv[3] if len(sys.argv)>3 else 'cpu'
        uv('pip','install','--python',py,'--torch-backend','cu128' if device=='cuda' else 'cpu','omnivoice')
    elif engine=='gpt-sovits':
        uv('pip','install','--python',py,'-r',repo/'extra-req.txt','--no-deps')
        requirements=repo/'requirements.txt'
        if os.name=='nt':
            requirements=repo/'requirements.quanvoice-windows.txt'
            requirements.write_text(windows_gpt_requirements((repo/'requirements.txt').read_text(encoding='utf-8')),encoding='utf-8')
            uv('pip','uninstall','--python',py,'opencc','pyopenjtalk','jieba-fast','onnxruntime-gpu')
            changed=patch_jieba(repo)
            print('Windows CPU: dùng wheel tiếng Nhật, OpenCC Python và jieba; đã giữ bản gốc các file sửa: '+str(len(changed)),flush=True)
        uv('pip','install','--python',py,'-r',requirements)
    else:
        source=str(repo)+('[streamingtts]' if engine=='vibevoice' else '')
        if engine=='chatterbox':
            uv('pip','install','--python',py,'--reinstall-package','chatterbox-tts',source)
        else:
            uv('pip','install','--python',py,'-e',source)
    uv('pip','install','--python',py,'soundfile')
    if engine in ('vibevoice','gpt-sovits'):
        uv('pip','check','--python',py)
        subprocess.run([str(py),'-c','import torch,torchaudio; print("PyTorch / torchaudio import OK")'],cwd=repo,check=True)
py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if engine=='index-tts':
    require_space(repo,remaining_space(repo/'checkpoints',14*2**30))
    print('Tải checkpoint IndexTTS-2.5. Có thể mất nhiều GB; các lần sau dùng lại dữ liệu.',flush=True)
    run_download([str(py),'-c',"from huggingface_hub import snapshot_download; snapshot_download('IndexTeam/IndexTTS-2.5',local_dir='checkpoints')"],cwd=repo)
if engine=='fish-speech':
    run_download([str(py),'-c',"from huggingface_hub import snapshot_download; snapshot_download('fishaudio/s2-pro',local_dir='checkpoints/s2-pro')"],cwd=repo)
if engine=='gpt-sovits':
    require_space(repo,remaining_space(repo/'GPT_SoVITS/pretrained_models',5*2**30))
    print('Tải checkpoint GPT-SoVITS v2 và bộ mã hóa tham chiếu.',flush=True)
    run_download([str(py),'-c',"from huggingface_hub import snapshot_download; snapshot_download('lj1995/GPT-SoVITS',local_dir='GPT_SoVITS/pretrained_models',allow_patterns=['chinese-roberta-wwm-ext-large/*','chinese-hubert-base/*','gsv-v2final-pretrained/*'])"],cwd=repo)
    import re
    config=repo/'GPT_SoVITS/configs/tts_infer.yaml';text=config.read_text(encoding='utf-8');text=re.sub(r'device: cuda','device: cpu',text);text=re.sub(r'is_half: true','is_half: false',text);config.write_text(text,encoding='utf-8')
print('Cài thư viện hoàn tất. Một số mô hình tải thêm trọng số khi tạo lần đầu. API được Studio tự khởi động khi đã chuẩn bị xong.',flush=True)
