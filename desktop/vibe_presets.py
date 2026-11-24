"""Legacy ModelOutput pickle compatibility, restricted to exact upstream bytes."""
import hashlib, io, json, pickle
from pathlib import Path

def load_voice(path,device='cpu'):
    import torch
    from transformers.cache_utils import DynamicCache
    from transformers.modeling_outputs import BaseModelOutputWithPast
    # Read once: validation and unpickling use identical bytes even if the file changes.
    raw=Path(path).read_bytes()
    with torch.serialization.safe_globals([BaseModelOutputWithPast,DynamicCache]):
        try:return torch.load(io.BytesIO(raw),map_location=device,weights_only=True)
        except pickle.UnpicklingError as error:
            manifest=json.loads(Path(__file__).with_name('vibe-voices.lock.json').read_text(encoding='utf-8'))
            trusted=any(entry['bytes']==len(raw) and entry['sha256']==hashlib.sha256(raw).hexdigest() for entry in manifest['files'])
            if not trusted:
                raise ValueError('Tệp giọng VibeVoice không khớp 25 giọng chính thức đã kiểm chứng. Không mở pickle không rõ nguồn; khôi phục gói giọng chính thức hoặc dùng tệp hỗ trợ weights_only.') from error
    # The pinned Microsoft presets contain ModelOutput objects. Newer PyTorch
    # rejects SETITEMS on this subclass even when allowlisted. Full loading is
    # permitted ONLY after the exact SHA256 and size match our shipped manifest.
    return torch.load(io.BytesIO(raw),map_location=device,weights_only=False)
