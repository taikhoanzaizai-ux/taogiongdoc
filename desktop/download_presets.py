"""Install the optional voice packs linked in Microsoft's pinned download script."""
import json,re,sys,tarfile,urllib.request,tempfile
from pathlib import Path
cfg=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));repo=Path(cfg['repo'])
script=repo/'demo/download_experimental_voices.sh'
if not script.is_file():raise SystemExit('Chưa cài mã nguồn VibeVoice. Hãy cài mô hình trước.')
target=repo/'demo/voices/streaming_model/experimental_voices';target.mkdir(parents=True,exist_ok=True)
urls=re.findall(r'https://github\.com/user-attachments/files/\d+/[A-Za-z0-9_-]+\.tar\.gz',script.read_text())
if not urls:raise SystemExit('Không tìm thấy gói giọng mở rộng trong mã nguồn Microsoft.')
with tempfile.TemporaryDirectory() as folder:
    for i,url in enumerate(urls):
        print(f'Tải gói {i+1}/{len(urls)}: {url.rsplit("/",1)[-1]}',flush=True)
        archive=Path(folder)/'pack.tar.gz';urllib.request.urlretrieve(url,archive)
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not member.isfile() or not member.name.lower().endswith('.pt'):continue
                if not (target/member.name).resolve().is_relative_to(target.resolve()):raise ValueError('Invalid archive path')
                dest=target/member.name;dest.parent.mkdir(parents=True,exist_ok=True)
                with tf.extractfile(member) as source,dest.open('wb') as output:
                    import shutil
                    shutil.copyfileobj(source,output)
print('Đã tải giọng mở rộng. Mở Thư viện giọng → Làm mới danh sách.',flush=True)
