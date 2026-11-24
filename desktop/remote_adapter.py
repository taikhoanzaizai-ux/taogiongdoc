"""Loopback API clients for official GPT-SoVITS API v2 and Fish Speech API."""
import base64,json,sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
from longform import render
p=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));cfg=p['config'];ref=p.get('ref');host=urlparse(cfg['endpoint'])
if host.scheme!='http' or host.hostname not in ('127.0.0.1','localhost'):raise ValueError('Only loopback services supported')
if p['engine']=='gpt-sovits':
    body={'text_lang':p['language'],'ref_audio_path':ref,'prompt_text':p['reference_transcript'],'prompt_lang':p['reference_language'],'media_type':'wav','streaming_mode':False}
    url=cfg['endpoint'].rstrip('/')+'/tts'
else:
    body={'format':'wav','streaming':False,'references':[{'audio':base64.b64encode(Path(ref).read_bytes()).decode(),'text':p['reference_transcript']}] if ref else []}
    if p.get('preset') and not ref:body['reference_id']=p['preset']
    url=cfg['endpoint'].rstrip('/')+'/v1/tts'
with httpx.Client(timeout=7200,trust_env=False) as client:
    def synthesize(text,path):
        with client.stream('POST',url,json={**body,'text':text}) as response:
            response.raise_for_status()
            if 'json' in response.headers.get('content-type',''):
                raise RuntimeError('API không trả âm thanh: '+response.read().decode(errors='replace')[:500])
            with Path(path).open('wb') as f:
                for block in response.iter_bytes():f.write(block)
    render(p,synthesize)
