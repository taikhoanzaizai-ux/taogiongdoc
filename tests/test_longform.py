import importlib.util, io, json, sys, wave
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
from longform import text_chunks, render, CHUNK_SIZE, chunk_size

def test_cjk_uses_smaller_model_calls():
    for engine in CHUNK_SIZE:
        assert chunk_size(engine,'zh')<=80
        assert chunk_size(engine,'vi')==CHUNK_SIZE[engine]

@pytest.mark.parametrize('text',[
    ('Xin chào Việt Nam. Nội dung không bị cắt!\n\n'*3000),
    '字'*100001,
    ('Đây là dấu tổ hợp.\n'*3000),
    'a'*100003,
    '\n'*20001+'Hello world.   ',
])
def test_chunking_keeps_every_character(text):
    chunks=list(text_chunks(text,240))
    assert ''.join(chunks)==text
    assert all(0<len(c)<=250 for c in chunks)

@pytest.mark.parametrize('engine',CHUNK_SIZE)
def test_streamed_audio_in_order_and_same_synthesizer(tmp_path,engine):
    text='Hello world! '*80;calls=[]
    def synthesize(chunk,path):
        calls.append(chunk)
        with wave.open(path,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
            w.writeframes((len(calls)*100).to_bytes(2,'little',signed=True)*4800)
    output=tmp_path/'raw.wav';render({'engine':engine,'text':text,'output':str(output)},synthesize)
    # Whitespace-only tails do not require a model call or added audio.
    assert ''.join(calls).strip()==text.strip()
    with wave.open(str(output)) as w:
        assert w.getnframes()==4800*len(calls)
        for i in range(len(calls)):
            w.setpos(i*4800+2400)
            assert int.from_bytes(w.readframes(1),'little',signed=True)==(i+1)*100
    progress=json.loads((tmp_path/'progress.json').read_text())
    assert progress['processed_chars']==progress['total_chars']==len(text)
    assert not (tmp_path/'parts').exists()

def test_failure_never_publishes_incomplete_combined_audio(tmp_path):
    output=tmp_path/'raw.wav'
    def bad(chunk,path):raise RuntimeError('SDK failed')
    with pytest.raises(RuntimeError):render({'engine':'vieneu','text':'word '*300,'output':str(output)},bad)
    assert not output.exists() and not (tmp_path/'parts').exists()
