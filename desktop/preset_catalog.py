"""Discover real upstream presets without loading model weights."""
import copy,json
from pathlib import Path
import httpx

def discover(engine,cfg,bundled):
    bank=copy.deepcopy(bundled[engine]);repo=Path(cfg['repo'])
    if engine=='vieneu':
        variant='v3nano' if cfg.get('variant')=='v3nano' else 'v3turbo'
        bank={**bank,**bank['variants'][variant],'variant':variant}
        asset=repo/'src/vieneu/assets'/('voices_v3_nano.json' if variant=='v3nano' else 'voices_v3_turbo.json')
        if asset.is_file():
            d=json.loads(asset.read_text(encoding='utf-8'));bank['default']=d['default_voice'];bank['voices']=[{'id':k,'name':k,'description':v.get('description',''),'language':'vi','gender':v.get('gender',''),'region':v.get('region',''),'featured':bool(v.get('featured')),'kind':'preset'} for k,v in d['presets'].items()]
    elif engine=='vibevoice':
        folder=repo/'demo/voices/streaming_model'
        if folder.is_dir():
            voices=[];codes={'jp':'ja','kr':'ko','sp':'es','in':'en'}
            for file in sorted(folder.rglob('*.pt')):
                stem=file.stem;prefix=stem.split('-')[0];lang=codes.get(prefix,prefix)
                if lang not in ('en','de','fr','it','ja','ko','nl','pl','pt','es'):continue
                voices.append({'id':stem.lower(),'name':stem.split('-',1)[-1].replace('_woman',' · Nữ').replace('_man',' · Nam'),'description':'Microsoft · '+prefix.upper()+(' · Thử nghiệm' if 'experimental_voices' in file.parts else ''),'language':lang,'gender':'female' if 'woman' in stem else 'male','kind':'preset'})
            bank['voices']=voices
        for v in bank['voices']:v['installed']=(folder/(v['id']+'.pt')).exists() or any(p.stem.lower()==v['id'] for p in folder.rglob('*.pt')) if folder.is_dir() else False
    elif engine=='index-tts':
        for v in bank['voices']:v['installed']=(repo/'examples'/v['id']).is_file()
    elif engine=='fish-speech':
        bank['connected']=False
        try:
            response=httpx.get(cfg['endpoint'].rstrip('/')+'/v1/references/list',timeout=2,trust_env=False);response.raise_for_status();data=response.json()
            if data.get('success',True):
                bank['voices']=[{'id':name,'name':name,'description':'Giọng đã lưu trên Fish Speech API','language':'','kind':'reference'} for name in data.get('reference_ids',[])];bank['connected']=True
        except (httpx.HTTPError,ValueError,KeyError):pass
    return bank

def index_sample(repo,voice_id,bank):
    if voice_id not in {v['id'] for v in bank['voices']}:raise ValueError('Giọng mẫu IndexTTS không hợp lệ')
    path=Path(repo)/'examples'/voice_id
    if path.is_file():return path
    path.parent.mkdir(parents=True,exist_ok=True)
    url='https://huggingface.co/spaces/IndexTeam/IndexTTS-2-Demo/resolve/main/examples/'+voice_id
    with httpx.Client(timeout=60,follow_redirects=True) as c:
        result=c.get(url);result.raise_for_status()
    content=result.content
    if content[:4] not in (b'RIFF',b'fLaC') or len(content)>20*1024*1024:raise ValueError('Nguồn mẫu không trả file âm thanh hợp lệ')
    temp=path.with_suffix('.download');temp.write_bytes(content);temp.replace(path);return path
