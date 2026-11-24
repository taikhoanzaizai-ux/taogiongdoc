"""Application-local storage shared by launchers, installers and workers."""
import os, shutil, tempfile
from pathlib import Path

def data_dir():
    return Path(os.environ.get('QUAN_VOICE_DATA') or Path(__file__).resolve().parent.parent/'data').expanduser().absolute()

def configure_cache(data):
    data=Path(data)
    paths={'HF_HOME':data/'cache/huggingface','HUGGINGFACE_HUB_CACHE':data/'cache/huggingface/hub','HF_HUB_CACHE':data/'cache/huggingface/hub','TRANSFORMERS_CACHE':data/'cache/huggingface/hub','TORCH_HOME':data/'cache/torch','WHISPER_CACHE':data/'cache/whisper','UV_CACHE_DIR':data/'cache/uv','UV_PYTHON_INSTALL_DIR':data/'runtimes/uv-python','PIP_CACHE_DIR':data/'cache/pip','XDG_CACHE_HOME':data/'cache','NUMBA_CACHE_DIR':data/'cache/numba','MPLCONFIGDIR':data/'cache/matplotlib','GRADIO_TEMP_DIR':data/'temp/gradio','TMP':data/'temp','TEMP':data/'temp','TMPDIR':data/'temp'}
    for key,path in paths.items():
        path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    os.environ['QUAN_VOICE_DATA']=str(data)
    tempfile.tempdir=str(data/'temp')
    return paths

def disk_info(path):
    path=Path(path).absolute();probe=path
    while not probe.exists() and probe!=probe.parent:probe=probe.parent
    usage=shutil.disk_usage(probe)
    return {'path':str(path),'free_bytes':usage.free,'total_bytes':usage.total}

def require_space(path,required):
    info=disk_info(path)
    if info['free_bytes']<required:
        raise RuntimeError(f"Ổ lưu dữ liệu không đủ chỗ (No space left): {info['path']}. Còn {info['free_bytes']/2**30:.1f} GiB; cần dự phòng khoảng {required/2**30:.1f} GiB cho bước này. Giữ cache, giải phóng ổ này rồi Thử lại. Dữ liệu mặc định ở thư mục data cạnh ứng dụng.")

def remaining_space(checkpoint,budget):
    checkpoint=Path(checkpoint)
    existing=sum(p.stat().st_size for p in checkpoint.rglob('*') if p.is_file()) if checkpoint.is_dir() else 0
    return max(1*2**30,budget-existing+1*2**30)
