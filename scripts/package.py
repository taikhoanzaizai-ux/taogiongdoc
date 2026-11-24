"""Build the small web download and complete Windows bundle from explicit inputs."""
from pathlib import Path
import argparse, json, zipfile, hashlib
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--mini-only',action='store_true',help='Build the small application/update ZIP without source or installer assets')
parser.add_argument('--upstream',type=Path,default=root/'upstream')
parser.add_argument('--assets',type=Path,default=root/'install-assets')
parser.add_argument('--output',type=Path,default=root.parent/'QuanVoice-Studio-1.5.6-Desktop-Full.zip')
parser.add_argument('--mini-output',type=Path,default=root/'dist/QuanVoice-Studio-Windows.zip')
args=parser.parse_args();mini=args.mini_output;mini.parent.mkdir(parents=True,exist_ok=True);appfiles=[]
for name in ('BAT_DAU.bat','QUAN_VOICE.vbs','CHAN_DOAN.bat','MO_VA_GHI_LOI.cmd','SUA_FISH_WSL.bat','BAT_DAU_NHANH.bat','Start-Windows.bat','Start-GPT-SoVITS.bat','Start-Linux.sh','HUONG_DAN.md','THIRD_PARTY.md'):
    appfiles.append((root/name,'QuanVoice-Studio/'+name))
for directory in ('desktop','windows','scripts','tests'):
    for p in sorted((root/directory).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:appfiles.append((p,'QuanVoice-Studio/'+p.relative_to(root).as_posix()))
for p in sorted((root/'dist').glob('*')):
    if not (root/'desktop/web'/p.name).exists() and p.suffix in ('.html','.js','.css','.json'):appfiles.append((p,'QuanVoice-Studio/desktop/web/'+p.name))
def add(z,p,name):
    z.write(p,name,compress_type=zipfile.ZIP_STORED if p.suffix.lower() in ('.zip','.exe','.whl') else zipfile.ZIP_DEFLATED)
with zipfile.ZipFile(mini,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p,n in appfiles:add(z,p,n)
if args.mini_only:
    print(mini,mini.stat().st_size,'bytes');raise SystemExit(0)
manifest=json.loads((root/'windows/assets-manifest.json').read_text())
assets=[*manifest['assets'],*manifest['wheels']]
for item in assets:
    p=args.assets/item['file']
    assert p.is_file() and p.stat().st_size==item['bytes'],p
    with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==item['sha256'],p
assert args.upstream.is_dir(),'Provide --upstream with all seven pinned source directories'
args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p,n in appfiles:add(z,p,n)
    for item in assets:
        p=args.assets/item['file'];add(z,p,'QuanVoice-Studio/install-assets/'+item['file'])
    for p in sorted(args.upstream.rglob('*')):
        if p.is_file() and '.git' not in p.parts:add(z,p,'QuanVoice-Studio/upstream/'+p.relative_to(args.upstream).as_posix())
with zipfile.ZipFile(args.output) as z:
    assert z.testzip() is None
    for e in json.loads((root/'desktop/web/engines.json').read_text()):
        if e['id'] not in ('omnivoice','moss-tts'):
            assert any(n.startswith('QuanVoice-Studio/upstream/'+e['id']+'/') for n in z.namelist())
    assert 'QuanVoice-Studio/BAT_DAU.bat' in z.namelist()
    print('Full source files:',len(z.namelist()))
for p in (mini,args.output):
    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    print(p,p.stat().st_size,'bytes',digest)
