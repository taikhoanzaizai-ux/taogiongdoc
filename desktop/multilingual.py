"""Local adapters for OmniVoice and MOSS-TTS Local Transformer v1.5."""
class MultilingualRuntime:
    def __init__(self, engine, config):
        import torch

        self.torch = torch
        self.engine = engine
        self.device = config.get("device", "cpu")
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in this model environment. Run model setup with GPU selected or select CPU.")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        checkpoint = config.get("checkpoint")
        if engine == "omnivoice":
            from omnivoice import OmniVoice

            self.model = OmniVoice.from_pretrained(
                checkpoint or "k2-fsa/OmniVoice", device_map=self.device, dtype=dtype
            )
        else:
            from transformers import AutoModel, AutoProcessor

            checkpoint = checkpoint or "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5"
            self.processor = AutoProcessor.from_pretrained(checkpoint, trust_remote_code=True)
            self.processor.audio_tokenizer = self.processor.audio_tokenizer.to(self.device)
            self.model = AutoModel.from_pretrained(
                checkpoint, trust_remote_code=True, dtype=dtype,
                attn_implementation="sdpa" if self.device == "cuda" else "eager",
            ).to(self.device).eval()

    def synthesizer(self, payload):
        import soundfile

        reference = payload.get("ref")
        language = {"vi": "Vietnamese", "en": "English", "ja": "Japanese", "ko": "Korean"}[payload.get("language") or "vi"]
        if self.engine == "omnivoice":
            prompt = None
            if reference:
                transcript = payload.get("reference_transcript", "").strip()
                if not transcript:
                    raise ValueError("OmniVoice needs an accurate transcript of the reference audio.")
                prompt = self.model.create_voice_clone_prompt(ref_audio=reference, ref_text=transcript)

            def synthesize(text, path):
                options = {"voice_clone_prompt": prompt} if prompt is not None else {}
                audio = self.model.generate(text=text, language=language, **options)
                soundfile.write(path, audio[0], 24000)
        else:
            def synthesize(text, path):
                options = {"reference": [reference]} if reference else {}
                message = self.processor.build_user_message(text=text, language=language, **options)
                batch = self.processor([[message]], mode="generation")
                with self.torch.inference_mode():
                    output = self.model.generate(
                        input_ids=batch["input_ids"].to(self.device),
                        attention_mask=batch["attention_mask"].to(self.device),
                        max_new_tokens=1024,
                    )
                    decoded = next((item for item in self.processor.decode(output) if item is not None), None)
                if decoded is None or not decoded.audio_codes_list:
                    raise RuntimeError("MOSS-TTS did not produce audio.")
                audio = decoded.audio_codes_list[0].detach().float().cpu().numpy()
                soundfile.write(path, audio.T, self.processor.model_config.sampling_rate)
        return synthesize
