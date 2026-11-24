"""Local OmniVoice runtime."""
class MultilingualRuntime:
    def __init__(self, config):
        import torch

        self.device = config.get("device", "cpu")
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in this model environment. Run model setup with GPU selected or select CPU.")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        checkpoint = config.get("checkpoint")
        from omnivoice import OmniVoice

        self.model = OmniVoice.from_pretrained(
            checkpoint or "k2-fsa/OmniVoice", device_map=self.device, dtype=dtype
        )

    def synthesizer(self, payload):
        import soundfile

        reference = payload.get("ref")
        language = {"vi": "Vietnamese", "en": "English", "ja": "Japanese", "ko": "Korean"}[payload.get("language") or "vi"]
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
        return synthesize
