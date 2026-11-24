"""Build UI metadata from the pinned upstream assets, without embeddings/weights."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
up=Path('/workspace/scratch/2388c5e4d298/upstream')
banks={}
variants={}
for variant in ('v3turbo','v3nano'):
    data=json.loads((up/'vieneu/src/vieneu/assets'/('voices_v3_'+('turbo' if variant=='v3turbo' else 'nano')+'.json')).read_text())
    voices=[{'id':name,'name':name,'description':v.get('description',''),'language':'vi','gender':v.get('gender',''),'region':v.get('region',''),'featured':bool(v.get('featured')),'kind':'preset'} for name,v in data['presets'].items()]
    variants[variant]={'voices':voices,'default':data['default_voice'],'source':'Danh sách preset từ mã nguồn VieNeu '+variant}
banks['vieneu']={'variants':variants,**variants['v3turbo']}
voices=[]
langmap={'jp':'ja','kr':'ko','sp':'es','in':'en'}
for f in sorted((up/'vibevoice/demo/voices/streaming_model').rglob('*.pt')):
    stem=f.stem;prefix=stem.split('-')[0];language=langmap.get(prefix,prefix)
    display=stem.split('-',1)[-1].replace('_man',' · Nam').replace('_woman',' · Nữ')
    voices.append({'id':stem.lower(),'name':display,'description':'Preset Microsoft · '+prefix.upper(),'language':language,'gender':'female' if 'woman' in stem else 'male','kind':'preset'})
banks['vibevoice']={'voices':voices,'default':'en-carter_man','source':'Preset đi kèm VibeVoice Realtime; có thể quét thêm giọng mở rộng đã cài.'}
banks['chatterbox']={'voices':[{'id':'default','name':'Giọng mặc định checkpoint','description':'Giọng điều kiện conds.pt do checkpoint cung cấp, nếu có.','language':'','kind':'default'}],'default':'default','source':'Chatterbox Multilingual không có danh mục nhiều giọng có tên. Có thể dùng giọng mặc định hoặc giọng clone.'}
examples={}
for line in (up/'index-tts/examples/cases.jsonl').read_text().splitlines():
    x=json.loads(line);name=x['prompt_audio'];examples.setdefault(name,{'id':name,'name':'Mẫu '+name.removesuffix('.wav').removeprefix('voice_'),'description':'File tham chiếu chính thức của IndexTTS · tải khi dùng lần đầu','language':'','kind':'sample'})
banks['index-tts']={'voices':list(sorted(examples.values(),key=lambda v:v['id'])),'default':'voice_01.wav','source':'File mẫu tham chiếu của dự án, không phải danh sách giọng đã huấn luyện có tên.'}
banks['gpt-sovits']={'voices':[],'default':'','source':'GPT-SoVITS không kèm kho giọng preset. Chọn giọng bạn đã lưu hoặc tải âm thanh tham chiếu.'}
banks['fish-speech']={'voices':[],'default':'','source':'Danh sách giọng được đọc từ /v1/references/list của Fish Speech trên máy bạn khi API đang chạy.'}
banks['whisper']={'voices':[],'default':'','source':'Whisper chép lời âm thanh, không có giọng đọc.'}
(root/'dist/presets.json').write_text(json.dumps(banks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'dist/engines.json';engines=json.loads(p.read_text())
for e in engines:
    if e['id']=='vibevoice':e['languages']=['en','de','fr','it','ja','ko','nl','pl','pt','es'];e['preset']='en-carter_man';e['note']='Preset Realtime có sẵn theo ngôn ngữ; một số giọng mở rộng là thử nghiệm. Không clone file tùy ý.'
p.write_text(json.dumps(engines,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print({k:len(v['voices']) for k,v in banks.items()})
