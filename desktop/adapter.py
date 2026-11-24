"""SDK runtime. One instance can serve multiple jobs without reloading weights."""
import copy, json, os, sys
from pathlib import Path
from longform import render

class EngineRuntime:
    def __init__(self,p):
        self.engine=p['engine'];self.cfg=p['config'];cfg=self.cfg
        if cfg['repo'] not in sys.path:sys.path.insert(0,cfg['repo'])
        engine=self.engine
        if engine=='whisper':
            import whisper
            self.model=whisper.load_model(cfg.get('variant','base'),download_root=os.environ['WHISPER_CACHE'],device=cfg.get('device','cpu'))
        elif engine=='vieneu':
            from vieneu import Vieneu
            kw={'mode':'v3nano'} if cfg.get('variant')=='v3nano' else {'backend':'onnx'} if cfg.get('device')=='cpu' else {}
            self.model=Vieneu(**kw)
        elif engine in ('omnivoice','moss-tts'):
            from multilingual import MultilingualRuntime
            self.model=MultilingualRuntime(engine,cfg)
        elif engine=='chatterbox':
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            self.model=ChatterboxMultilingualTTS.from_pretrained(device=cfg.get('device','cpu'))
            # A clone may change model.conds. Preserve the native default for a
            # later request that returns to the built-in voice.
            self.default_conditions=copy.deepcopy(self.model.conds)
        elif engine=='index-tts':
            from indextts.infer_v2_5 import IndexTTS2
            checkpoints=Path(cfg['checkpoint'])
            self.model=IndexTTS2(cfg_path=str(checkpoints/'config.yaml'),model_dir=str(checkpoints),use_bf16=cfg.get('device')=='cuda',use_qwen_emo=p.get('auto_emotion',False))
        elif engine=='vibevoice':
            from vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference
            from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
            import torch
            model_path=cfg.get('checkpoint') or 'microsoft/VibeVoice-Realtime-0.5B'
            self.processor=VibeVoiceStreamingProcessor.from_pretrained(model_path)
            self.model=VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(model_path,torch_dtype=torch.bfloat16 if cfg.get('device')=='cuda' else torch.float32,device_map=cfg.get('device','cpu'),attn_implementation='sdpa')
            self.model.eval();self.model.set_ddpm_inference_steps(num_steps=5);self.voice_cache={}
        else:raise ValueError('Unknown engine: '+engine)

    def run(self,p):
        cfg=self.cfg;engine=self.engine;model=self.model;ref=p.get('ref');lang=p.get('language','en');out=p['output']
        if engine=='whisper':
            result=model.transcribe(ref,language=None if lang=='auto' else lang,fp16=cfg.get('device')=='cuda')
            Path(out).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');return
        if engine=='vieneu':
            args={'ref_audio':ref} if ref else ({'voice':p['preset']} if p.get('preset') else {})
            def synthesize(text,path):model.save(model.infer(text,**args),path)
        elif engine in ('omnivoice','moss-tts'):
            synthesize=model.synthesizer(p)
        elif engine=='chatterbox':
            import soundfile as sf
            # Restore before every job, so clone A cannot leak into clone B or
            # the native voice. generate() can set conditionals for this ref.
            model.conds=copy.deepcopy(self.default_conditions)
            args={'audio_prompt_path':ref} if ref else {}
            def synthesize(text,path):
                audio=model.generate(text,language_id=lang,exaggeration=p.get('emotion',0.5),**args)
                sf.write(path,audio.detach().cpu().numpy().squeeze(),model.sr)
        elif engine=='index-tts':
            def synthesize(text,path):model.infer(spk_audio_prompt=ref,text=text,lang=lang.upper(),output_path=path,use_emo_text=p.get('auto_emotion',False),emo_alpha=p.get('emotion',0.5),verbose=True)
        else:
            import torch
            from vibe_presets import load_voice
            chosen=p.get('preset') or 'en-carter_man'
            voice=next((v for v in (Path(cfg['repo'])/'demo/voices/streaming_model').rglob('*.pt') if v.stem.lower()==chosen.lower()),None)
            if voice is None:raise ValueError('Giọng VibeVoice chưa được cài: '+chosen)
            if str(voice) not in self.voice_cache:
                self.voice_cache[str(voice)]=load_voice(voice,cfg.get('device','cpu'))
            cached=self.voice_cache[str(voice)];processor=self.processor
            def synthesize(text,path):
                # The decoder updates its KV cache; every chunk needs a fresh
                # copy of the selected voice's cached prompt.
                prompt=copy.deepcopy(cached)
                inputs=processor.process_input_with_cached_prompt(text=text,cached_prompt=prompt,padding=True,return_tensors='pt',return_attention_mask=True)
                inputs={k:v.to(cfg.get('device','cpu')) if torch.is_tensor(v) else v for k,v in inputs.items()}
                with torch.inference_mode():
                    result=model.generate(**inputs,max_new_tokens=None,cfg_scale=1.5,tokenizer=processor.tokenizer,generation_config={'do_sample':False},verbose=True,all_prefilled_outputs=copy.deepcopy(prompt))
                if not result.speech_outputs or result.speech_outputs[0] is None:raise RuntimeError('VibeVoice không trả âm thanh')
                processor.save_audio(result.speech_outputs[0],output_path=path)
        render(p,synthesize)

def main():
    p=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));EngineRuntime(p).run(p)
if __name__=='__main__':main()
