from __future__ import annotations

# Claim storage and reserve the port before importing the app or touching jobs.
if __name__=='__main__':
    from local_server import run_browser
    run_browser()
    raise SystemExit(0)
import atexit,hashlib, base64, concurrent.futures, json, os, shutil, sqlite3, subprocess, sys, threading, time, uuid, wave
from pathlib import Path
from urllib.parse import urlparse,quote
from typing import Literal
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt
import subtitle_exports

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from preset_catalog import discover, index_sample
import services
from runtime_manager import RuntimeManager
from diagnostics import explain, redact
from setup_policy import selected, fingerprint, reusable
WEB=ROOT/'web'
if not WEB.exists():WEB=ROOT.parent/'dist'
from storage import data_dir, configure_cache, disk_info
DATA=data_dir()
configure_cache(DATA)
for folder in ('voices','preview_refs','outputs','jobs','logs','models','envs','sources','cache'): (DATA/folder).mkdir(parents=True,exist_ok=True)
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','120')
os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','30')
os.environ.setdefault('UV_HTTP_TIMEOUT','120')
os.environ.setdefault('PYTHONUTF8','1')
os.environ.setdefault('PYTHONIOENCODING','utf-8')
os.environ.setdefault('HF_HOME',str(DATA/'cache'/'huggingface'))
os.environ.setdefault('TORCH_HOME',str(DATA/'cache'/'torch'))
os.environ['WHISPER_CACHE']=str(DATA/'cache'/'whisper')
CATALOG=json.loads((WEB/'engines.json').read_text(encoding='utf-8'))
ENGINES={e['id']:e for e in CATALOG}
PRESETS=json.loads((WEB/'presets.json').read_text(encoding='utf-8'))
DB=DATA/'studio.db'
INSTALLED_CACHE={}
ML_LOCK=threading.RLock(); SETUP_POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
LOCK=threading.RLock(); POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1); PROCESSES={}
SHUTTING_DOWN=threading.Event()
RUNTIME=RuntimeManager(ROOT,DATA);atexit.register(RUNTIME.stop);REMOTE_STATE={'engine':None,'state':'idle','loaded':False};WARM_ERROR=''
app=FastAPI(title='QUÂN Voice Studio',docs_url=None,redoc_url=None)

@app.middleware('http')
async def local_only(request:Request,call_next):
    # No cross-origin mutation of this loopback service. UI and API share one origin.
    if request.url.path.startswith('/api/'):
        if request.headers.get('host','').split(':')[0] not in ('localhost','127.0.0.1','testserver'):
            return __import__('fastapi').responses.JSONResponse({'detail':'Host không hợp lệ'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return __import__('fastapi').responses.JSONResponse({'detail':'Hãy dùng giao diện cục bộ tại cùng địa chỉ.'},status_code=403)
    response = await call_next(request)
    if request.url.path in ("/", "/index.html", "/engines.json", "/presets.json"):
        response.headers["Cache-Control"] = "no-store"
    return response

def db():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
with db() as c:
    c.executescript('CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, value TEXT); CREATE TABLE IF NOT EXISTS voices (id TEXT PRIMARY KEY, value TEXT); CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, value TEXT); CREATE TABLE IF NOT EXISTS preview_refs (id TEXT PRIMARY KEY, value TEXT);')
    for row in c.execute('SELECT id,value FROM jobs').fetchall():
        item=json.loads(row['value'])
        if item['status'] in ('queued','running'):
            if item['type']=='setup_engine':c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('setup:'+item['engine'],json.dumps({'state':'failed','stage':'Cài đặt bị gián đoạn · Mở lại để tiếp tục'},ensure_ascii=False)))
            item.update(status='failed',error='Ứng dụng đã đóng trước khi xử lý xong. Hãy tạo lại tác vụ.');c.execute('UPDATE jobs SET value=? WHERE id=?',(json.dumps(item,ensure_ascii=False),row['id']))
def get(table,key,default=None):
    with LOCK,db() as c:r=c.execute(f'SELECT value FROM {table} WHERE id=?',(key,)).fetchone()
    return json.loads(r[0]) if r else default
def put(table,key,value):
    with LOCK,db() as c:c.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))
def rows(table):
    with LOCK,db() as c:return [json.loads(r[0]) for r in c.execute(f'SELECT value FROM {table} ORDER BY rowid DESC')]
def relocate_saved_paths():
    marker=DATA/'migration-from-localappdata.done'
    if not marker.is_file():return
    roots=[marker.read_text(encoding='utf-8-sig').strip().rstrip('\\/')]
    journal=DATA/'migration-source.json'
    if journal.is_file():
        try:
            record=json.loads(journal.read_text(encoding='utf-8-sig'))
            roots.extend(p.rstrip('\\/') for p in record.get('path_roots',[]) if isinstance(p,str) and p)
        except (OSError,ValueError,TypeError):pass
    roots=sorted(set(roots),key=len,reverse=True)
    for engine in ENGINES:
        saved=get('settings',engine)
        if not saved:continue
        before={**saved};changed=False
        for key in ('python','repo','checkpoint'):
            value=saved.get(key,'')
            for old in roots:
                if value.lower().startswith(old.lower()+'\\') or value.lower().startswith(old.lower()+'/'):
                    candidate=str(DATA/value[len(old)+1:].replace('\\','/'))
                    if Path(candidate).exists():saved[key]=candidate;changed=True;break
        if changed:
            put('settings',engine,saved)
            receipt=get('settings','setup:'+engine,{})
            if receipt.get('fingerprint')==fingerprint(before):
                receipt['fingerprint']=fingerprint(saved);put('settings','setup:'+engine,receipt)
relocate_saved_paths()

def config(engine):
    value={'python':str(DATA/'envs'/engine/('Scripts/python.exe' if os.name=='nt' else 'bin/python')),'repo':str(DATA/'sources'/engine),'checkpoint':'','device':'cpu','variant':'base' if engine=='whisper' else 'v3turbo','endpoint':'http://127.0.0.1:'+('9880' if engine=='gpt-sovits' else '8080')}
    value.update(get('settings',engine,{}));return value

def require_engine(engine):
    if engine not in ENGINES:raise HTTPException(404,'Không tìm thấy mô hình')
def engine_status(engine):
    cfg=config(engine);installed=False
    cachekey=(cfg['python'],cfg['repo'],ENGINES[engine]['module'])
    prior=INSTALLED_CACHE.get(cachekey)
    if prior and time.time()-prior[0]<20:installed=prior[1]
    elif Path(cfg['python']).is_file():
        try:
            probe=subprocess.run([cfg['python'],'-c',"import importlib.util,sys;sys.exit(0 if importlib.util.find_spec("+repr(ENGINES[engine]['module'])+") else 1)"],cwd=cfg['repo'] if Path(cfg['repo']).is_dir() else ROOT,capture_output=True,timeout=8)
            installed=probe.returncode==0
        except (OSError,subprocess.TimeoutExpired):pass
        INSTALLED_CACHE[cachekey]=(time.time(),installed)
    if engine=='fish-speech' and cfg.get('wsl_distro')=='QuanVoice-Fish':installed=bool(cfg.get('wsl_setup_complete'))
    ready=installed
    state='dependencies' if installed else 'not_installed'
    if engine=='index-tts' and not (Path(cfg['checkpoint'])/'config.yaml').is_file():ready=False;state='needs_weights' if installed else state
    if engine in ('fish-speech','gpt-sovits'):
        try:
            endpoint=cfg['endpoint'];valid_endpoint(endpoint)
            response=httpx.get(endpoint+('/docs' if engine=='gpt-sovits' else '/v1/health'),timeout=1,trust_env=False)
            ready=response.status_code==200; state='service_ready' if ready else 'service_offline'
        except Exception:ready=False;state='service_offline'
        if not ready and installed and cfg.get('auto_start'):ready=True;state='service_standby'
    receipt=get('settings','setup:'+engine,{})
    if receipt.get('state') in ('queued','running'):ready=False;state='preparing'
    elif receipt.get('state') in ('failed','cancelled'):ready=False;state='needs_setup'
    elif reusable(receipt,cfg,installed):state='ready' if engine not in ('fish-speech','gpt-sovits') else state
    return {**ENGINES[engine],'installed':installed,'available':ready,'state':state,'config':cfg,'setup':receipt}

def valid_endpoint(url):
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.password or parsed.path not in ('','/'):
        raise ValueError('API phải chạy trên cùng máy: http://127.0.0.1:PORT')

@app.get('/api/updates')
def check_updates():
    from updates import latest_release

    try:
        return latest_release()
    except (OSError, ValueError) as error:
        raise HTTPException(502, "Không kiểm tra được bản cập nhật trên GitHub.") from error


UPDATE_LOCK = threading.Lock()


@app.post('/api/updates/install', status_code=202)
def install_update():
    from updates import latest_release, prepare_update

    request_exit = getattr(app.state, 'request_update_exit', None)
    if os.name != 'nt' or not request_exit:
        raise HTTPException(409, 'Mở Studio bằng QUAN_VOICE.vbs để tự cập nhật.')
    if not UPDATE_LOCK.acquire(blocking=False):
        raise HTTPException(409, 'Studio đang chuẩn bị cập nhật.')
    folder = None
    scheduled = False
    try:
        if any(job['status'] in ('queued', 'running') for job in rows('jobs')):
            raise HTTPException(409, 'Chờ các tác vụ đang chạy hoặc đang xếp hàng hoàn tất rồi cập nhật.')
        release = latest_release()
        if not release['available']:
            raise HTTPException(409, 'Chưa có bản mới để cài.')
        root = ROOT.parent.resolve()
        folder = prepare_update(root, release)
        if any(job['status'] in ('queued', 'running') for job in rows('jobs')):
            raise HTTPException(409, 'Có tác vụ mới trong hàng đợi. Hãy cập nhật sau khi tác vụ hoàn tất.')
        subprocess.Popen(
            [sys.executable, str(folder / 'apply_update.py'), str(root), str(folder),
             str(DATA / 'logs' / 'update.log'), str(os.getpid())],
            cwd=root, creationflags=subprocess.DETACHED_PROCESS,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        scheduled = True
        threading.Timer(.8, request_exit).start()
        return {'latest': release['latest']}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, 'Không chuẩn bị được bản cập nhật: ' + str(error)) from error
    finally:
        if not scheduled:
            if folder:
                shutil.rmtree(folder, ignore_errors=True)
            UPDATE_LOCK.release()


@app.get('/api/health')
def health():return {'product':'QuanVoiceStudio','version':'1.6.9','data_dir':str(DATA)}

@app.post('/api/app/exit')
def exit_desktop():
    callback=getattr(app.state,'request_exit',None)
    if callback is None:raise HTTPException(400,'Đóng cửa sổ chạy ứng dụng để thoát bản trình duyệt.')
    threading.Timer(.3,callback).start();return {'ok':True}

@app.get('/api/status')
def status():
    return {'connected':True,'product':'QuanVoiceStudio','version':'1.6.9','local_url':getattr(app.state,'local_url','http://127.0.0.1:8765'),'data_dir':str(DATA),'storage':disk_info(DATA),'ffmpeg':bool(shutil.which('ffmpeg')),'engines':[engine_status(e) for e in ENGINES],'runtime':runtime_status(),'desktop_mode':os.environ.get('QUAN_VOICE_DESKTOP')=='1'}
class EngineConfig(BaseModel):
    python:str='';repo:str='';checkpoint:str='';device:str='cpu';variant:str='';endpoint:str='';auto_start:bool=False;wsl_distro:str='';wsl_setup_complete:bool=False
@app.put('/api/engines/{engine}')
def save_config(engine:str,value:EngineConfig):
    require_engine(engine)
    if value.device not in ('cpu','cuda','mps'):raise HTTPException(400,'Thiết bị không hợp lệ')
    payload=value.model_dump()
    prior=config(engine)
    # Retain managed service metadata when the ordinary configuration form omits it.
    for key in ('auto_start','wsl_distro','wsl_setup_complete'):
        if key not in value.model_fields_set:payload[key]=prior.get(key,value.model_dump()[key])
    if engine in ('fish-speech','gpt-sovits'):
        try:valid_endpoint(value.endpoint)
        except ValueError as e:raise HTTPException(400,str(e))
    put('settings',engine,payload);INSTALLED_CACHE.clear();return engine_status(engine)

def preset_bank(engine):
    cfg=config(engine)
    if engine=='fish-speech':
        try:valid_endpoint(cfg['endpoint'])
        except ValueError:return PRESETS[engine]
    return discover(engine,cfg,PRESETS)
@app.get('/api/presets')
def presets():return {e:preset_bank(e) for e in ENGINES}
@app.get('/api/engines/{engine}/presets/{preset}/audio')
def preset_audio(engine:str,preset:str):
    require_engine(engine)
    if engine!='index-tts':raise HTTPException(400,'Giọng này cần tạo mẫu nghe bằng mô hình trước')
    try:
        repo=Path(config(engine)['repo'])
        sample_root=repo if (repo/'pyproject.toml').is_file() else DATA/'cache'/'index-samples'
        path=index_sample(sample_root,preset,PRESETS['index-tts'])
    except (ValueError,httpx.HTTPError) as error:raise HTTPException(400,str(error))
    return FileResponse(path,media_type='audio/wav')
@app.post('/api/presets/vibevoice/download',status_code=202)
def download_vibe_presets():
    if not Path(config('vibevoice')['repo'],'demo/download_experimental_voices.sh').is_file():raise HTTPException(400,'Cài mô hình VibeVoice trước khi tải giọng mở rộng')
    if any(j['type']=='preset_install' and j['status'] in ('queued','running') for j in rows('jobs')):raise HTTPException(409,'Giọng mở rộng đang được tải')
    identifier=uuid.uuid4().hex;j={'id':identifier,'engine':'vibevoice','type':'preset_install','title':'Tải giọng mở rộng VibeVoice','status':'queued','created':time.time()}
    put('jobs',identifier,j);POOL.submit(run_job,identifier);return j

@app.get('/api/voices')
def voices():return rows('voices')
async def normalize_upload(file:UploadFile,folder:str):
    if not shutil.which('ffmpeg'):raise HTTPException(400,'Chưa cài FFmpeg. Xem phần Hướng dẫn cài đặt.')
    identifier=uuid.uuid4().hex;temp=DATA/folder/(identifier+'.input');dest=DATA/folder/(identifier+'.wav');size=0
    try:
        with temp.open('wb') as output:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>100*1024*1024:raise HTTPException(413,'Tối đa 100 MB mỗi file')
                output.write(chunk)
        result=subprocess.run(['ffmpeg','-y','-v','error','-i',str(temp),'-vn','-ac','1','-ar','24000',str(dest)],capture_output=True,timeout=180)
        if result.returncode:raise HTTPException(400,'Không đọc được file âm thanh. Thử WAV, MP3, M4A hoặc WebM hợp lệ.')
        with wave.open(str(dest)) as w:duration=w.getnframes()/w.getframerate()
        if duration<0.5:raise HTTPException(400,'File quá ngắn, cần ít nhất 0,5 giây')
        return {'id':identifier,'duration':round(duration,2),'created':time.time(),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
    except Exception:
        dest.unlink(missing_ok=True);raise
    finally:temp.unlink(missing_ok=True)

@app.post('/api/voices')
async def add_voice(file:UploadFile=File(...),name:str=Form(...),transcript:str=Form(''),language:str=Form('vi'),kind:str=Form('voice'),preferred_engine:str=Form('vieneu')):
    if not name.strip():raise HTTPException(400,'Nhập tên giọng / file')
    if kind=='voice' and (preferred_engine not in ENGINES or not ENGINES[preferred_engine]['clone']):raise HTTPException(400,'Mô hình đã chọn không hỗ trợ clone giọng')
    audio=await normalize_upload(file,'voices')
    value={**audio,'name':name.strip()[:120],'transcript':transcript,'language':language,'kind':kind,'preferred_engine':preferred_engine}
    put('voices',audio['id'],value);return value

@app.post('/api/preview-references')
async def add_preview_reference(file:UploadFile=File(...),transcript:str=Form(''),language:str=Form('vi')):
    audio=await normalize_upload(file,'preview_refs')
    if audio['duration']>120:
        (DATA/'preview_refs'/(audio['id']+'.wav')).unlink(missing_ok=True);raise HTTPException(400,'Giọng tham chiếu nghe thử tối đa 120 giây. Nên dùng đoạn 3–15 giây.')
    value={**audio,'transcript':transcript,'language':language,'name':'Mẫu nghe thử chưa lưu'}
    put('preview_refs',audio['id'],value);return value

@app.delete('/api/voices/{identifier}')
def delete_voice(identifier:str):
    if not get('voices',identifier):raise HTTPException(404,'Không tìm thấy giọng')
    if any(j.get('voice_id')==identifier and j['status'] in ('running','queued') for j in rows('jobs')):raise HTTPException(409,'Giọng đang được dùng trong hàng đợi')
    with LOCK,db() as c:c.execute('DELETE FROM voices WHERE id=?',(identifier,))
    (DATA/'voices'/(identifier+'.wav')).unlink(missing_ok=True);return {'ok':True}
@app.get('/api/voices/{identifier}/audio')
def voice_audio(identifier:str):
    if not get('voices',identifier):raise HTTPException(404,'Không tìm thấy giọng')
    path=DATA/'voices'/(identifier+'.wav')
    if not path.is_file():raise HTTPException(404,'Thiếu tệp âm thanh của giọng đã lưu. Nhập lại giọng tham chiếu từ file gốc.')
    return FileResponse(path,media_type='audio/wav')

class JobInput(BaseModel):
    engine:str; text:str='';language:str='vi';voice_id:str|None=None;preset:str='';speed:float=Field(1,ge=0.5,le=2);format:str='wav';emotion:float=Field(0.5,ge=0,le=1);auto_emotion:bool=False;title:str='Bản thu mới'
@app.post('/api/jobs',status_code=202)
def create_job(value:JobInput):return queue_job(value)

def queue_job(value:JobInput,*,preview=False,preview_ref_id=None,preview_key=None):
    require_engine(value.engine);e=ENGINES[value.engine]
    if value.language not in e['languages']:raise HTTPException(400,'Mô hình chưa hỗ trợ ngôn ngữ này')
    if value.format not in ('wav','mp3'):raise HTTPException(400,'Định dạng không hợp lệ')
    if e['kind']=='tts' and not value.text.strip():raise HTTPException(400,'Nhập nội dung cần đọc')
    if value.engine in ('gpt-sovits','whisper') and not (value.voice_id or preview_ref_id):raise HTTPException(400,'Cần chọn file âm thanh tham chiếu / nguồn')
    voice=get('voices',value.voice_id) if value.voice_id else (get('preview_refs',preview_ref_id) if preview_ref_id else None)
    if value.voice_id and not voice:raise HTTPException(404,'File giọng mẫu không còn tồn tại')
    if voice:
        path=DATA/('voices' if value.voice_id else 'preview_refs')/((value.voice_id or preview_ref_id)+'.wav')
        if not path.is_file():raise HTTPException(400,'Thiếu tệp âm thanh của giọng đã lưu. Nhập lại giọng tham chiếu từ file gốc.')
    if value.engine=='vibevoice' and voice:raise HTTPException(400,'VibeVoice Realtime dùng preset, không hỗ trợ clone file tùy ý')
    if value.engine=='omnivoice' and voice and not voice.get('transcript','').strip():raise HTTPException(400,'OmniVoice cần lời đọc khớp với audio mẫu')
    if value.engine=='gpt-sovits' and voice and not voice.get('transcript','').strip():raise HTTPException(400,'GPT-SoVITS cần lời thoại của giọng mẫu')
    if voice and value.engine=='gpt-sovits' and voice.get('language') not in e['languages']:raise HTTPException(400,'Ngôn ngữ giọng mẫu chưa được GPT-SoVITS hỗ trợ')
    if not voice and e['kind']=='tts':
        bank=preset_bank(value.engine)
        chosen=value.preset or bank.get('default','')
        if chosen:
            item=next((p for p in bank['voices'] if p['id']==chosen),None)
            if not item:raise HTTPException(400,'Giọng không có trong danh sách hiện tại. Hãy làm mới danh sách và chọn lại.')
            if value.engine=='vibevoice' and item.get('language')!=value.language:raise HTTPException(400,'Chọn giọng VibeVoice đúng ngôn ngữ đang đọc')
            value.preset=chosen
        if value.engine=='index-tts' and not chosen:raise HTTPException(400,'Chọn giọng mẫu hoặc tải giọng tham chiếu')
    if not engine_status(value.engine)['available']:raise HTTPException(400,'Mô hình chưa sẵn sàng. Mở Kho mô hình để cài đặt / khởi động API.')
    identifier=uuid.uuid4().hex;job={**value.model_dump(),'id':identifier,'type':'preview' if preview else ('asr' if e['kind']=='asr' else 'tts'),'status':'queued','created':time.time(),'error':None}
    job['config_snapshot']=config(value.engine)
    if preview:job.update(preview_ref_id=preview_ref_id,preview_key=preview_key)
    put('jobs',identifier,job);POOL.submit(run_job,identifier);return job

class PreviewInput(JobInput):
    text:str=Field(...,min_length=1)
    preview_ref_id:str|None=None

@app.post('/api/previews',status_code=202)
def create_preview(value:PreviewInput):
    require_engine(value.engine)
    if ENGINES[value.engine]['kind']!='tts':raise HTTPException(400,'Whisper không tạo giọng nói để nghe thử')
    if value.voice_id and value.preview_ref_id:raise HTTPException(400,'Chỉ chọn một giọng tham chiếu')
    ref=get('preview_refs',value.preview_ref_id) if value.preview_ref_id else (get('voices',value.voice_id) if value.voice_id else None)
    if (value.voice_id or value.preview_ref_id) and not ref:raise HTTPException(404,'Giọng tham chiếu nghe thử không còn tồn tại')
    if value.preview_ref_id and not ENGINES[value.engine]['clone']:raise HTTPException(400,'Mô hình này không hỗ trợ clone từ file')
    data=value.model_dump(exclude={'preview_ref_id','title'});data['format']='wav'
    key_data={**data,'ref':{k:ref.get(k) for k in ('id','sha256','language','transcript')} if ref else None,'config':config(value.engine)}
    key=hashlib.sha256(json.dumps(key_data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    with LOCK:
        for job in rows('jobs'):
            if job.get('preview_key')==key and job['status'] in ('queued','running','done'):
                if job['status']!='done' or (DATA/'outputs'/job['id']/job.get('file','missing')).is_file():return {**job,'cached':job['status']=='done'}
        return queue_job(JobInput(**data,title='Nghe thử giọng'),preview=True,preview_ref_id=value.preview_ref_id,preview_key=key)

@app.get('/api/previews/{identifier}')
def read_preview(identifier:str):
    job=get('jobs',identifier)
    if not job or job['type']!='preview':raise HTTPException(404,'Không tìm thấy mẫu nghe thử')
    return present_job(job)

def patch_job(identifier,**values):
    with LOCK:
        j=get('jobs',identifier);j.update(values);put('jobs',identifier,j);return j

def run_process(identifier,args,cwd=None):
    log=DATA/'logs'/(identifier+'.log')
    with log.open('a',encoding='utf-8') as f:
        with LOCK:
            if get('jobs',identifier)['status']=='cancelled':raise RuntimeError('Tác vụ đã hủy')
            p=subprocess.Popen(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,env=os.environ.copy());PROCESSES[identifier]=p
        try:
            code=p.wait(timeout=None if get('jobs',identifier)['type'] in ('tts','preview') else 7200)
            if code:raise RuntimeError('Xử lý thất bại. '+log.read_text(encoding='utf-8',errors='replace')[-1800:])
        except subprocess.TimeoutExpired:
            kill_tree(p);raise RuntimeError('Hết thời gian chờ sau 2 giờ. Xem log và kiểm tra phần cứng.')
        finally:PROCESSES.pop(identifier,None)

def kill_tree(p):
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
    else:p.kill()

def run_job(identifier):
    j=get('jobs',identifier)
    if j['type'] in ('install','preset_install'):_run_job(identifier)
    else:
        with ML_LOCK:_run_job(identifier)

def _run_job(identifier):
    with LOCK:
        j=get('jobs',identifier)
        if j['status']=='cancelled':return
        patch_job(identifier,status='running',started=time.time())
    try:
        if j['type']=='preset_install':
            path=DATA/'jobs'/(identifier+'.json');path.write_text(json.dumps(config('vibevoice')),encoding='utf-8')
            run_process(identifier,[sys.executable,str(ROOT/'download_presets.py'),str(path)])
        elif j['type']=='install':
            run_process(identifier,[sys.executable,str(ROOT/'install_engine.py'),j['engine'],str(DATA)])
            cfg=config(j['engine']);envroot=DATA/'envs'/j['engine'];repo=DATA/'sources'/j['engine']
            if j['engine'] in ('index-tts','fish-speech'):envroot=repo/'.venv'
            cfg.update(python=str(envroot/('Scripts/python.exe' if os.name=='nt' else 'bin/python')),repo=str(repo))
            if j['engine']=='index-tts':cfg['checkpoint']=str(repo/'checkpoints')
            put('settings',j['engine'],cfg);INSTALLED_CACHE.clear()
        else:
            engine=j['engine'];cfg=j.get('config_snapshot') or config(engine)
            cfg={**cfg,'_cached_only':preferences().get('cached_only',True)}
            if engine in ('gpt-sovits','fish-speech'):
                RUNTIME.stop();REMOTE_STATE.update(engine=engine,state='loading',loaded=False)
                services.ensure(engine,cfg,DATA,cancelled=lambda:get('jobs',identifier)['status']=='cancelled')
                REMOTE_STATE.update(state='ready',loaded=True)
            else:
                services.stop_all();REMOTE_STATE.update(engine=None,state='idle',loaded=False)
            voice=get('voices',j.get('voice_id')) if j.get('voice_id') else (get('preview_refs',j['preview_ref_id']) if j.get('preview_ref_id') else None)
            ref=str(DATA/('preview_refs' if j.get('preview_ref_id') else 'voices')/(voice['id']+'.wav')) if voice else None
            directory=DATA/'outputs'/identifier;directory.mkdir(exist_ok=True)
            raw=directory/('transcript.json' if engine=='whisper' else 'raw.wav')
            if engine=='index-tts' and not ref:
                ref=str(index_sample(cfg['repo'],j['preset'],PRESETS['index-tts']))
            payload={**j,'config':cfg,'ref':ref,'output':str(raw)}
            path=DATA/'jobs'/(identifier+'.json');path.write_text(json.dumps({**payload,'reference_transcript':voice.get('transcript','') if voice else '', 'reference_language':voice.get('language','en') if voice else 'en'},ensure_ascii=False),encoding='utf-8')
            repo=Path(cfg['repo']);cwd=str(repo) if repo.exists() else str(ROOT)
            if engine in ('gpt-sovits','fish-speech'):
                run_process(identifier,[sys.executable,str(ROOT/'remote_adapter.py'),str(path)],cwd)
            else:
                RUNTIME.run(engine,cfg,path,identifier,cancelled=lambda:get('jobs',identifier)['status']=='cancelled')
            if engine=='whisper':
                result=json.loads(raw.read_text(encoding='utf-8'));(directory/'transcript.txt').write_text(result['text'],encoding='utf-8')
                srt='\n\n'.join(f"{i+1}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['text'].strip()}" for i,s in enumerate(result['segments']))
                (directory/'transcript.srt').write_text(srt,encoding='utf-8');patch_job(identifier,text_result=result['text'],file='transcript.txt',srt='transcript.srt')
            else:
                final=directory/('voice.'+j['format'])
                run_process(identifier,['ffmpeg','-y','-v','error','-i',str(raw),'-af',f"atempo={j['speed']}",*(['-rf64','auto'] if j['format']=='wav' else []),str(final)])
                patch_job(identifier,file=final.name)
                raw.unlink(missing_ok=True)
        if get('jobs',identifier)['status']!='cancelled':patch_job(identifier,status='done',finished=time.time())
    except Exception as e:
        if get('jobs',identifier)['status']!='cancelled':patch_job(identifier,status='failed',error=str(e)[-3000:],finished=time.time())

def stamp(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
def present_job(job):
    path=DATA/'outputs'/job['id']/'progress.json'
    try:
        value=json.loads(path.read_text(encoding='utf-8'));done=value['processed_chars'];total=value['total_chars']
        stage=f"Đã xử lý {done:,}/{total:,} ký tự · phần {value['part']}"
        if done==total and job['status']=='running':stage+=' · Đang ghép / xuất âm thanh'
        return {**job,**value,'stage':stage}
    except (OSError,ValueError,KeyError):return job

@app.get('/api/jobs')
def list_jobs():return [present_job(j) for j in rows('jobs') if j['type']!='preview']
def job_log(job):
    p=DATA/'logs'/(job['id']+'.log')
    text=p.read_text(encoding='utf-8',errors='replace')[-24000:] if p.exists() else ''
    if job.get('error'):text+='\n\nThông báo tác vụ:\n'+job['error']
    if job.get('engine') in ('gpt-sovits','fish-speech'):
        service=DATA/'logs'/('service-'+job['engine']+'.log')
        if service.exists():text+='\n\nNhật ký API '+job['engine']+':\n'+service.read_text(encoding='utf-8',errors='replace')[-12000:]
    return redact(text or 'Chưa có nhật ký. Tác vụ có thể đang chờ bộ xử lý.')

@app.get('/api/jobs/{identifier}/log')
def logs(identifier:str):
    job=get('jobs',identifier)
    if not job:raise HTTPException(404,'Không tìm thấy tác vụ')
    return {'text':job_log(job)}

@app.get('/api/engines/{engine}/diagnostics')
def engine_diagnostics(engine:str):
    require_engine(engine)
    receipt=get('settings','setup:'+engine,{})
    job=get('jobs',receipt.get('job_id',''))
    if not job:job=next((j for j in rows('jobs') if j.get('engine')==engine and j['type'] in ('setup_engine','install')),None)
    text=job_log(job) if job else redact(receipt.get('error') or 'Chưa có tác vụ cài đặt cho mô hình này.')
    summary,hint=explain(engine,text)
    return {'engine':engine,'name':ENGINES[engine]['name'],'state':receipt.get('state','not_installed'),'summary':summary,'hint':hint,'log':text,'job_id':job['id'] if job else None}

@app.get('/api/diagnostics/download')
def download_diagnostics():
    import platform
    lines=['QUAN Voice Studio 1.6.9 - Nhật ký chẩn đoán',platform.platform(),'Python ứng dụng: '+sys.version.split()[0],'Không thêm file giọng hoặc trường kịch bản từ dự án.','Bộ xử lý: '+json.dumps(runtime_status(),ensure_ascii=False)]
    for engine in ENGINES:
        item=engine_diagnostics(engine)
        lines+=['','=== '+item['name']+' · '+item['state']+' ===',item['summary'],item['hint'],item['log']]
    return Response('\n'.join(lines),media_type='text/plain; charset=utf-8',headers={'Content-Disposition':'attachment; filename="QuanVoice-ChanDoan.txt"'})

@app.post('/api/jobs/{identifier}/cancel')
def cancel(identifier:str):
    j=get('jobs',identifier)
    if not j:raise HTTPException(404,'Không tìm thấy tác vụ')
    if j['status'] not in ('queued','running'):raise HTTPException(409,'Tác vụ đã kết thúc')
    patch_job(identifier,status='cancelled',finished=time.time())
    if j['type']=='setup_engine':put('settings','setup:'+j['engine'],{'state':'cancelled','stage':'Đã hủy','job_id':identifier})
    p=PROCESSES.get(identifier)
    if p:kill_tree(p)
    return get('jobs',identifier)
def export_job(identifier):
    job=get('jobs',identifier)
    if not job or job['status']!='done' or job['type'] not in ('tts','asr'):
        raise HTTPException(404,'Chỉ xuất văn bản/phụ đề của tác vụ đã hoàn tất.')
    return job,DATA/'outputs'/identifier

class ExportInput(BaseModel):
    format:Literal['txt','srt']='srt'
    scope:Literal['full','parts']='full'
    parts:list[StrictInt]|None=None
    timeline:Literal['local','global']='local'

ExportInput.model_rebuild(_types_namespace=globals())

def export_response(identifier,value):
    job,folder=export_job(identifier)
    try:name,mime,content=subtitle_exports.export(job,folder,value.format,value.scope,value.parts,value.timeline)
    except FileNotFoundError:raise HTTPException(404,'Không còn tệp âm thanh hoặc mốc thời gian của tác vụ này.')
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise HTTPException(400,str(error))
    return Response(content,media_type=mime,headers={'Content-Disposition':"attachment; filename=export."+name.rsplit('.',1)[-1]+"; filename*=UTF-8''"+quote(name)})

@app.get('/api/jobs/{identifier}/exports')
def export_manifest(identifier:str):
    job,folder=export_job(identifier)
    try:doc=subtitle_exports.document(job,folder)
    except FileNotFoundError:raise HTTPException(404,'Không còn tệp âm thanh hoặc mốc thời gian của tác vụ này.')
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise HTTPException(400,str(error))
    return {'title':job.get('title','Bản thu'), 'timing':doc['timing'],'timing_note':doc['timing_note'],'parts':[{'id':p['id'],'start_ms':p['start_ms'],'end_ms':p['end_ms'],'text':p['text'][:200],'characters':len(p['text'])} for p in doc['parts']]}

@app.post('/api/jobs/{identifier}/exports')
def create_export(identifier:str,value:ExportInput):return export_response(identifier,value)

@app.get('/api/jobs/{identifier}/download')
def download(identifier:str,kind:Literal['audio','txt','srt']='audio',part:int|None=None,timeline:Literal['local','global']='local'):
    if kind in ('txt','srt'):
        return export_response(identifier,ExportInput(format=kind,scope='parts' if part is not None else 'full',parts=[part] if part is not None else None,timeline=timeline))
    job=get('jobs',identifier)
    if not job or job['status']!='done' or not job.get('file'):raise HTTPException(404,'Chưa có kết quả')
    file=DATA/'outputs'/identifier/job['file']
    if not file.is_file():raise HTTPException(404,'Không còn tệp kết quả.')
    return FileResponse(file,filename=job['file'])
@app.post('/api/install/{engine}',status_code=202)
def install(engine:str):
    require_engine(engine)
    j=schedule_setup(engine)
    return j or {'engine':engine,'status':'done','type':'setup_engine','title':'Mô hình đã chuẩn bị'}
class SetupInput(BaseModel):
    profile:str='all'

@app.get('/api/setup')
def setup_status():
    return {e:get('settings','setup:'+e,{}) for e in ENGINES}

def schedule_setup(engine):
    require_engine(engine)
    with LOCK:
        active=next((j for j in rows('jobs') if j.get('engine')==engine and j['type'] in ('setup_engine','install') and j['status'] in ('queued','running')),None)
        if active:return active
        cfg=config(engine);receipt=get('settings','setup:'+engine,{})
        if reusable(receipt,cfg,engine_status(engine)['installed']):return None
        identifier=uuid.uuid4().hex
        j={'id':identifier,'engine':engine,'type':'setup_engine','title':'Chuẩn bị '+ENGINES[engine]['name'],'status':'queued','created':time.time(),'stage':'Chờ cài tự động'}
        put('jobs',identifier,j);put('settings','setup:'+engine,{'state':'queued','stage':j['stage'],'job_id':identifier})
        SETUP_POOL.submit(run_setup_job,identifier);return j

@app.post('/api/setup/start',status_code=202)
def start_setup(value:SetupInput):
    try:engines=selected(value.profile)
    except ValueError as error:raise HTTPException(400,str(error))
    return {'scheduled':[j for e in engines if (j:=schedule_setup(e))]}

@app.post('/api/setup/engine/{engine}',status_code=202)
def setup_one(engine:str):return {'scheduled':[j] if (j:=schedule_setup(engine)) else []}

def run_setup_job(identifier):
    j=get('jobs',identifier);engine=j['engine']
    if j['status']=='cancelled':return
    def stage(text):
        if get('jobs',identifier)['status']=='cancelled':raise RuntimeError('Đã hủy')
        patch_job(identifier,status='running',stage=text,started=j.get('started',time.time()))
        put('settings','setup:'+engine,{'state':'running','stage':text,'job_id':identifier})
    try:
        stage('Cài mã nguồn và thư viện riêng')
        if engine=='fish-speech' and os.name=='nt':
            run_process(identifier,[sys.executable,str(ROOT/'setup_fish_wsl.py'),str(DATA)])
            cfg=config(engine);cfg.update(wsl_distro='QuanVoice-Fish',wsl_setup_complete=True,auto_start=True,device='cpu')
        else:
            run_process(identifier,[sys.executable,str(ROOT/'install_engine.py'),engine,str(DATA),config(engine)['device']])
            cfg=config(engine);repo=DATA/'sources'/engine;envroot=repo/'.venv' if engine in ('index-tts','fish-speech') else DATA/'envs'/engine
            cfg.update(repo=str(repo),python=str(envroot/('Scripts/python.exe' if os.name=='nt' else 'bin/python')))
            if engine=='index-tts':cfg['checkpoint']=str(repo/'checkpoints')
            if engine in ('gpt-sovits','fish-speech'):cfg['auto_start']=True
        put('settings',engine,cfg);INSTALLED_CACHE.clear()
        stage('Tải trọng số và kiểm tra nạp mô hình')
        with ML_LOCK:
            RUNTIME.stop();REMOTE_STATE.update(engine=None,state='idle',loaded=False)
            services.stop_all()
            if engine in ('gpt-sovits','fish-speech'):
                try:services.ensure(engine,cfg,DATA,cancelled=lambda:get('jobs',identifier)['status']=='cancelled')
                finally:services.stop_all()
            else:
                payload={'engine':engine,'config':cfg,'output':str(DATA/'models'/(engine+'-setup.wav'))}
                path=DATA/'jobs'/(identifier+'.json');path.write_text(json.dumps(payload),encoding='utf-8')
                run_process(identifier,[cfg['python'],str(ROOT/'prepare_model.py'),str(path)],cfg['repo'])
        if get('jobs',identifier)['status']=='cancelled':raise RuntimeError('Đã hủy')
        put('settings','setup:'+engine,{'state':'ready','stage':'Đã chuẩn bị mô hình mặc định','job_id':identifier,'fingerprint':fingerprint(cfg)})
        patch_job(identifier,status='done',stage='Đã chuẩn bị mô hình mặc định',finished=time.time())
    except Exception as error:
        cancelled=get('jobs',identifier)['status']=='cancelled';state='cancelled' if cancelled else 'failed'
        put('settings','setup:'+engine,{'state':state,'stage':'Đã hủy' if cancelled else 'Cần thử lại','error':str(error)[-3000:],'job_id':identifier})
        if not cancelled:patch_job(identifier,status='failed',error=str(error)[-3000:],finished=time.time())

@app.on_event('shutdown')
def shutdown_workers():
    SHUTTING_DOWN.set()
    for job in rows('jobs'):
        if job['status'] in ('queued','running'):
            patch_job(job['id'],status='cancelled',finished=time.time())
            if job['type']=='setup_engine':put('settings','setup:'+job['engine'],{'state':'cancelled','stage':'Ứng dụng đã đóng · Có thể cài tiếp'})
    for process in list(PROCESSES.values()):
        try:kill_tree(process)
        except OSError:pass
    RUNTIME.stop();services.stop_all()
    SETUP_POOL.shutdown(wait=False,cancel_futures=True);POOL.shutdown(wait=False,cancel_futures=True)

class PreferencesInput(BaseModel):
    engine:str='vieneu';language:str='vi';voice:str='';preset:str='';text:str='';speed:float=Field(1,ge=.5,le=2);format:str='wav';emotion:float=Field(.5,ge=0,le=1);cloneEngine:str='vieneu';warm_on_start:bool=True;cached_only:bool=True;theme:dict={}

def preferences():
    defaults={'engine':'vieneu','language':'vi','warm_on_start':True,'cached_only':True}
    saved=get('settings','ui_preferences',{})
    if not saved:
        voice=next((v for v in rows('voices') if v.get('kind')!='source'),None)
        if voice:
            engine=voice.get('preferred_engine','vieneu')
            if engine in ENGINES and ENGINES[engine]['kind']=='tts':defaults.update(engine=engine,voice=voice['id'],preset='',language=voice.get('language') if voice.get('language') in ENGINES[engine]['languages'] else ENGINES[engine]['languages'][0])
    return {**defaults,**saved}


@app.get('/api/preferences')
def read_preferences():return {**preferences(),'has_saved':bool(get('settings','ui_preferences',{}))}

@app.put('/api/preferences')
@app.post('/api/preferences')
def save_preferences(value:PreferencesInput):
    payload=value.model_dump(exclude_unset=True)
    if 'engine' in payload:
        require_engine(payload['engine'])
        if ENGINES[payload['engine']]['kind']!='tts':raise HTTPException(400,'Chọn mô hình tạo giọng cho màn Studio')
    if payload.get('format','wav') not in ('wav','mp3'):raise HTTPException(400,'Định dạng không hợp lệ')
    old=get('settings','ui_preferences',{});old.update(payload);put('settings','ui_preferences',old);return preferences()

def runtime_status():
    if REMOTE_STATE.get('engine'):return {**REMOTE_STATE,'error':WARM_ERROR}
    return {**RUNTIME.describe(),'warm_error':WARM_ERROR}

@app.get('/api/runtime')
def read_runtime():return runtime_status()

class WarmInput(BaseModel):
    engine:str

@app.post('/api/runtime/warm',status_code=202)
def warm_request(value:WarmInput):
    require_engine(value.engine)
    if not engine_status(value.engine)['available']:raise HTTPException(400,'Chuẩn bị mô hình trong Kho mô hình trước. Dữ liệu đã tải vẫn được giữ.')
    POOL.submit(warm_engine,value.engine);return {'queued':True,'engine':value.engine}

def warm_engine(engine):
    global WARM_ERROR
    with ML_LOCK:
        try:
            WARM_ERROR='';cfg={**config(engine),'_cached_only':preferences().get('cached_only',True)}
            if engine in ('gpt-sovits','fish-speech'):
                RUNTIME.stop();REMOTE_STATE.update(engine=engine,state='loading',loaded=False)
                services.ensure(engine,cfg,DATA,cancelled=SHUTTING_DOWN.is_set);REMOTE_STATE.update(state='ready',loaded=True)
            else:
                services.stop_all();REMOTE_STATE.update(engine=None,state='idle',loaded=False)
                identifier='warm-'+uuid.uuid4().hex;path=DATA/'jobs'/(identifier+'.json')
                path.write_text(json.dumps({'engine':engine,'config':cfg,'auto_emotion':False}),encoding='utf-8')
                try:RUNTIME.run(engine,cfg,path,identifier,warm=True,cancelled=SHUTTING_DOWN.is_set)
                finally:path.unlink(missing_ok=True)
        except Exception as error:
            WARM_ERROR=str(error)[-3000:];REMOTE_STATE.update(engine=None,state='idle',loaded=False)

@app.post('/api/runtime/release')
def release_runtime():
    if not ML_LOCK.acquire(blocking=False):raise HTTPException(409,'Đang tạo hoặc nạp giọng. Chờ xong hoặc hủy tác vụ trước.')
    try:RUNTIME.stop();services.stop_all();REMOTE_STATE.update(engine=None,state='idle',loaded=False)
    finally:ML_LOCK.release()
    return runtime_status()

@app.on_event('startup')
def automatic_setup():
    profile=os.environ.get('QUAN_VOICE_SETUP_PROFILE','none')
    # Updating/reopening an installed studio must not reinstall models. Explicit
    # retries remain in the model library.
    first_request=not get('settings','automatic_setup_requested',False)
    has_saved_models=any(get('settings','setup:'+e,{}).get('state')=='ready' for e in ENGINES)
    if profile!='none' and first_request:
        put('settings','automatic_setup_requested',True)
        if not has_saved_models:
            for engine in selected(profile):schedule_setup(engine)
    pref=preferences();engine=pref.get('engine','vieneu')
    if pref.get('warm_on_start') and engine in ENGINES and engine_status(engine)['available']:
        POOL.submit(warm_engine,engine)

@app.get('/api/settings/export')
def export_settings():return {'engines':{e:config(e) for e in ENGINES},'data_dir':str(DATA)}
app.mount('/',StaticFiles(directory=WEB,html=True),name='web')
