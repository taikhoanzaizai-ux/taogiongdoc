"""Prepare an isolated Ubuntu WSL2 distro; do not touch existing user distros."""
import hashlib, json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path
from install_support import decode_wsl_output, check_fish_launch, move_fish_storage
from storage import configure_cache, require_space
from network_support import run_download
DISTRO='QuanVoice-Fish';BASE='https://cloud-images.ubuntu.com/wsl/releases/24.04/current/'
def run(*args,**kw):return subprocess.run(list(map(str,args)),check=True,**kw)
def wsl(*args,**kw):return run('wsl.exe','-d',DISTRO,'-u','root','--exec',*args,**kw)
def sha256_file(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    if os.name!='nt':raise RuntimeError('This helper targets Windows WSL2')
    data=Path(sys.argv[1]);configure_cache(data);require_space(data,2*2**30);bootstrap=data/'bootstrap';bootstrap.mkdir(exist_ok=True)
    try:
        result=subprocess.run(['wsl.exe','--status'],capture_output=True,timeout=30)
        if result.returncode:raise RuntimeError(decode_wsl_output(result.stdout+result.stderr)[-2000:])
    except Exception as error:raise RuntimeError('WSL2 chưa sẵn sàng. Kiểm tra ảo hóa / cập nhật WSL, khởi động lại Windows nếu được yêu cầu rồi bấm Thử lại Fish. Chi tiết: '+str(error))
    result=run('wsl.exe','--list','--quiet',capture_output=True,timeout=30)
    distros=decode_wsl_output(result.stdout).splitlines()
    if DISTRO not in [x.strip() for x in distros]:
        name='ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz';file=bootstrap/name
        print('Tải Ubuntu WSL2 chính thức và kiểm tra SHA256...',flush=True)
        sums=urllib.request.urlopen(BASE+'SHA256SUMS',timeout=60).read().decode()
        expected=next(line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip('*')==name)
        if not file.exists() or sha256_file(file)!=expected:
            part=file.with_suffix('.part');urllib.request.urlretrieve(BASE+name,part)
            with part.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=expected:part.unlink(missing_ok=True);raise RuntimeError('Ubuntu checksum mismatch')
            part.replace(file)
        location=data/'wsl'/DISTRO;location.parent.mkdir(exist_ok=True)
        run('wsl.exe','--import',DISTRO,location,file,'--version','2')
    try:
        move_fish_storage(data)
    except (RuntimeError, subprocess.TimeoutExpired) as move_error:
        try:
            check_fish_launch()
        except Exception as launch_error:
            raise RuntimeError(
                "Không mở được WSL QuanVoice-Fish ở vị trí đã đăng ký. "
                "Giữ nguyên các file ext4.vhdx và kiểm tra đường dẫn trước khi cài lại. "
                f"Lỗi chuyển ổ: {move_error}. Lỗi mở WSL: {launch_error}"
            ) from launch_error
        print("Chưa chuyển được ổ WSL. Tiếp tục dùng QuanVoice-Fish ở vị trí hiện tại.", flush=True)
    else:
        check_fish_launch()
    # Existing completed/partial checkpoints reduce the remaining download budget.
    measured=subprocess.run(['wsl.exe','-d',DISTRO,'-u','root','--exec','du','-sb','/opt/quanvoice/fish-speech/checkpoints'],capture_output=True,timeout=30)
    try:existing=int(decode_wsl_output(measured.stdout).split()[0]) if measured.returncode==0 else 0
    except (ValueError,IndexError):existing=0
    require_space(data,max(1*2**30,18*2**30-existing))
    wsl('env','DEBIAN_FRONTEND=noninteractive','apt-get','-o','Acquire::Retries=3','update')
    wsl('env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y','python3-venv','python3-pip','git','ffmpeg','portaudio19-dev','libsox-dev','build-essential','ca-certificates')
    source=Path(__file__).resolve().parent.parent/'upstream'/'fish-speech'
    if not source.is_dir():
        source=data/'sources'/'fish-speech'
        if not source.exists():
            run('git','clone','https://github.com/fishaudio/fish-speech.git',source,env={**os.environ,'GIT_LFS_SKIP_SMUDGE':'1'})
            lock=json.loads((Path(__file__).parent/'sources.lock.json').read_text());run('git','checkout',next(x['sha'] for x in lock if x['id']=='fish-speech'),cwd=source)
    linux_source=wsl('wslpath','-a',str(source),capture_output=True,text=True).stdout.strip()
    wsl('mkdir','-p','/opt/quanvoice/fish-speech')
    # Copy on each retry: interrupted copies can resume without deleting checkpoints.
    wsl('cp','-a',linux_source+'/.','/opt/quanvoice/fish-speech/')
    wsl('python3','-m','venv','/opt/quanvoice/bootstrap')
    wsl('/opt/quanvoice/bootstrap/bin/python','-m','pip','install','uv')
    wsl('/opt/quanvoice/bootstrap/bin/python','-m','uv','sync','--directory','/opt/quanvoice/fish-speech','--python','3.12','--extra','cpu')
    code="from huggingface_hub import snapshot_download;snapshot_download('fishaudio/s2-pro',local_dir='/opt/quanvoice/fish-speech/checkpoints/s2-pro')"
    run_download(['wsl.exe','-d',DISTRO,'-u','root','--exec','env','HF_HOME=/opt/quanvoice/cache/huggingface','/opt/quanvoice/fish-speech/.venv/bin/python','-c',code])
    print('Fish Speech: đã cài WSL và tải trọng số. Đang chờ kiểm tra API.',flush=True)
if __name__=='__main__':main()
