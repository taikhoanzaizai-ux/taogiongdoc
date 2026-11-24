"""Small, deterministic setup policy shared by the API and tests."""
import hashlib, json
ORDER=('vieneu','whisper','chatterbox','index-tts','vibevoice','gpt-sovits','fish-speech','omnivoice','moss-tts')
def selected(profile):
    if profile not in ('all','recommended','none'):raise ValueError('Chọn all, recommended hoặc none')
    return ORDER if profile=='all' else ORDER[:2] if profile=='recommended' else ()
def fingerprint(cfg):
    fields=('python','repo','checkpoint','device','variant','endpoint','wsl_distro')
    return hashlib.sha256(json.dumps({k:cfg.get(k) for k in fields},sort_keys=True).encode()).hexdigest()
def reusable(receipt,cfg,installed):
    return bool(installed and receipt and receipt.get('state')=='ready' and receipt.get('fingerprint')==fingerprint(cfg))
