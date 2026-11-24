"""Windows CPU compatibility helpers; upstream source copies remain recoverable."""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

def windows_gpt_requirements(text):
    result=[]
    for line in text.splitlines():
        name=re.split(r'[<>=!~;\[\s]',line.strip(),maxsplit=1)[0].lower().replace('_','-')
        if line.strip().startswith('--no-binary'):continue
        if name in ('opencc','jieba-fast','pyopenjtalk','onnxruntime-gpu','onnxruntime'):continue
        result.append(line)
    return '\n'.join(result+['opencc-python-reimplemented==0.1.7','jieba','pyopenjtalk-plus==0.4.1.post9','onnxruntime'])+'\n'

def patch_jieba(repo):
    changed=[]
    for p in (Path(repo)/'GPT_SoVITS'/'text').rglob('*.py'):
        original=p.read_text(encoding='utf-8')
        if re.search(r'\bjieba_fast\b',original):
            backup=p.with_suffix(p.suffix+'.quanvoice-original')
            if not backup.exists():shutil.copy2(p,backup)
            p.write_text(re.sub(r'\bjieba_fast\b','jieba',original),encoding='utf-8');changed.append(str(p))
    return changed

def decode_wsl_output(data):
    if isinstance(data,str):return data
    if data.startswith((b'\xff\xfe',b'\xfe\xff')):return data.decode('utf-16',errors='replace').replace('\x00','')
    return data.decode('utf-16-le' if b'\x00' in data else 'utf-8',errors='replace').replace('\x00','')

def copy_missing(source,target):
    source=Path(source);target=Path(target)
    for p in source.rglob('*'):
        relative=p.relative_to(source)
        if any(part in ('.git','.venv','__pycache__') for part in relative.parts):continue
        dest=target/relative
        if p.is_file() and (not dest.exists() or dest.stat().st_size==0):
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)

def ensure_source(engine,entry,repo,bundled,lockpath):
    repo=Path(repo);required=['pyproject.toml']
    if engine=='gpt-sovits':required=['requirements.txt','extra-req.txt','api_v2.py','GPT_SoVITS/configs/tts_infer.yaml']
    elif engine=='vibevoice':required+=['demo/realtime_model_inference_from_file.py']
    if all((repo/name).is_file() and (repo/name).stat().st_size for name in required):return
    repo.parent.mkdir(parents=True,exist_ok=True)
    if Path(bundled).is_dir():copy_missing(bundled,repo)
    else:
        # Clone into a temporary checkout so an interrupted previous copy can be
        # filled in without deleting user configs or downloaded checkpoints.
        with tempfile.TemporaryDirectory(dir=repo.parent,prefix=engine+'-source-') as temp:
            import os
            subprocess.run(['git','clone',entry['repo']+'.git',temp],check=True,env={**os.environ,'GIT_LFS_SKIP_SMUDGE':'1'})
            locks=json.loads(Path(lockpath).read_text());sha=next(x['sha'] for x in locks if x['id']==engine)
            subprocess.run(['git','checkout',sha],cwd=temp,check=True);copy_missing(temp,repo)
    missing=[name for name in required if not (repo/name).is_file() or not (repo/name).stat().st_size]
    if missing:raise RuntimeError('Mã nguồn chưa đầy đủ: '+', '.join(missing))

def check_fish_launch():
    """Retry only our owned distro; never shut down other WSL instances."""
    def probe():
        return subprocess.run(['wsl.exe','-d','QuanVoice-Fish','-u','root','--exec','/bin/true'],capture_output=True,timeout=45)
    try:
        first=probe()
        if first.returncode==0:return
        subprocess.run(['wsl.exe','--terminate','QuanVoice-Fish'],capture_output=True,timeout=30)
        result=probe()
        if result.returncode==0:return
        detail=decode_wsl_output(result.stdout+result.stderr)[-2200:]
    except (OSError,subprocess.TimeoutExpired) as error:detail=str(error)
    raise RuntimeError('WSL không khởi động được QuanVoice-Fish. Đã thử khởi động lại riêng distro này. Chạy SUA_FISH_WSL.bat để cập nhật WSL, khởi động lại Windows rồi Thử lại Fish. Kiểm tra dung lượng ổ lưu WSL và ảo hóa. Không xóa hoặc unregister distro. Chi tiết: '+detail)

def move_fish_storage(data):
    """Use the supported WSL move command, preserving distro identity and models."""
    import os
    if os.name!='nt':return
    import winreg
    base=None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Lxss') as parent:
            for i in range(winreg.QueryInfoKey(parent)[0]):
                with winreg.OpenKey(parent,winreg.EnumKey(parent,i)) as key:
                    if winreg.QueryValueEx(key,'DistributionName')[0]=='QuanVoice-Fish':
                        base=winreg.QueryValueEx(key,'BasePath')[0];break
    except FileNotFoundError:return
    if not base:return
    target=Path(data)/'wsl'/'QuanVoice-Fish'
    if os.path.normcase(os.path.abspath(base.removeprefix('\\\\?\\')))==os.path.normcase(os.path.abspath(target)):return
    target.parent.mkdir(parents=True,exist_ok=True)
    from storage import require_space
    disk=Path(base.removeprefix('\\\\?\\'))/'ext4.vhdx'
    if disk.is_file():require_space(target.parent,disk.stat().st_size+512*2**20)
    subprocess.run(['wsl.exe','--terminate','QuanVoice-Fish'],capture_output=True,timeout=30)
    print('Chuyển ổ WSL Fish sang '+str(target)+' bằng lệnh quản lý WSL; giữ nguyên trọng số.',flush=True)
    result=subprocess.run(['wsl.exe','--manage','QuanVoice-Fish','--move',str(target)],capture_output=True,timeout=1800)
    if result.returncode:
        raise RuntimeError('Chưa chuyển được dữ liệu WSL Fish từ '+base+' sang '+str(target)+'. Chạy SUA_FISH_WSL.bat để cập nhật WSL rồi Thử lại Fish. Cần WSL hỗ trợ --manage --move và ổ đích đủ chỗ. Bộ cài không tự xóa file WSL. Nếu lệnh chuyển ổ dở dang, giữ cả hai vị trí và gửi chẩn đoán trước khi thao tác tiếp. '+decode_wsl_output(result.stdout+result.stderr)[-1800:])
