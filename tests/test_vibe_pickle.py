"""Run with a PyTorch environment; optional official files stay outside the ZIP."""
import os,pickle,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))

def test_unknown_pickle_never_uses_full_loader(tmp_path,monkeypatch):
    torch=pytest.importorskip('torch');pytest.importorskip('transformers')
    from vibe_presets import load_voice
    marker=tmp_path/'unexpected-execution'
    class Unexpected:
        def __reduce__(self):return (eval,(f"__import__('pathlib').Path({str(marker)!r}).write_text('unsafe')",))
    file=tmp_path/'untrusted.pt';torch.save(Unexpected(),file)
    with pytest.raises(ValueError,match='không khớp'):load_voice(file)
    assert not marker.exists()

@pytest.mark.skipif(not os.environ.get('QUAN_VOICE_VIBE_FIXTURES'),reason='Official binary presets are not bundled with test source')
def test_all_25_official_presets_reproduce_and_load():
    torch=pytest.importorskip('torch');pytest.importorskip('transformers')
    from transformers.cache_utils import DynamicCache
    from transformers.modeling_outputs import BaseModelOutputWithPast
    from vibe_presets import load_voice
    files=list(Path(os.environ['QUAN_VOICE_VIBE_FIXTURES']).glob('*.pt'));assert len(files)==25
    for file in files:
        with torch.serialization.safe_globals([BaseModelOutputWithPast,DynamicCache]):
            with pytest.raises(pickle.UnpicklingError):torch.load(file,map_location='cpu',weights_only=True)
        result=load_voice(file)
        assert result['lm'].past_key_values is not None
        assert all(k in result for k in ('lm','tts_lm','neg_lm','neg_tts_lm'))
