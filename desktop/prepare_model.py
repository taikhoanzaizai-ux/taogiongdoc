"""Executed in the engine environment: fetch/load defaults, never fake readiness."""
import json, os, sys
from pathlib import Path
def main():
    p=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));e=p['engine'];cfg=p['config']
    sys.path.insert(0,cfg['repo'])
    if e=='whisper':
        import whisper
        whisper.load_model(cfg.get('variant') or 'base',device=cfg['device'],download_root=os.environ['WHISPER_CACHE'])
    elif e =='omnivoice':
        from multilingual import MultilingualRuntime
        model=MultilingualRuntime(cfg)
        model.synthesizer({'language':'vi'})('Xin chào, Quân Voice Studio đã sẵn sàng.',p['output'])
    elif e=='chatterbox':
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        ChatterboxMultilingualTTS.from_pretrained(device=cfg['device'])
    elif e=='index-tts':
        from index_text import prepare_wetext
        prepare_wetext()
        from indextts.infer_v2_5 import IndexTTS2
        d=Path(cfg['checkpoint'])
        IndexTTS2(cfg_path=str(d/'config.yaml'),model_dir=str(d),use_bf16=cfg['device']=='cuda')
    elif e in ('vieneu','vibevoice'):
        import adapter
        if e=='vieneu':
            from vieneu import Vieneu
            model=Vieneu(**({'mode':'v3nano'} if cfg.get('variant')=='v3nano' else {'backend':'onnx'} if cfg['device']=='cpu' else {}))
            out=p['output'];model.save(model.infer('Xin chào, ứng dụng đã chuẩn bị giọng nói.',voice='Minh Quân' if cfg.get('variant')=='v3nano' else 'Hải Đăng'),out)
            model.infer('Đây là giọng nghe thử.',ref_audio=out)
        else:
            p.update(text='Hello. Your voice studio is ready.',language='en',preset='en-carter_man',ref=None)
            Path(sys.argv[1]).write_text(json.dumps(p),encoding='utf-8');adapter.main()
    print('Đã tải và nạp mô hình mặc định.',flush=True)
if __name__=='__main__':main()
