"""Keep one SDK worker resident; model switches release its RAM deliberately."""
import hashlib,json,os,signal,subprocess,threading,time,uuid
from pathlib import Path

class RuntimeManager:
    def __init__(self,root,data):
        self.root=Path(root);self.data=Path(data);self.process=None;self.key=None;self.engine=None;self.state='idle';self.loaded=False;self.error='';self.loads=0;self.lock=threading.RLock()
    def describe(self):
        with self.lock:
            alive=self.process is not None and self.process.poll() is None
            return {'engine':self.engine if alive else None,'state':self.state if alive else 'idle','loaded':bool(alive and self.loaded),'loads':self.loads,'error':self.error}
    def stop(self):
        with self.lock:
            p=self.process;self.process=None;self.key=None;self.loaded=False;self.state='idle';self.engine=None
            if p is None:return
            if p.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
                else:
                    try:os.killpg(p.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill();p.wait(timeout=5)
            if p.stdin:p.stdin.close()
    def run(self,engine,cfg,path,identifier,cancelled=lambda:False,warm=False):
        key=hashlib.sha256(json.dumps({'engine':engine,'config':cfg,'emotion_model':json.loads(Path(path).read_text(encoding='utf-8')).get('auto_emotion',False) if engine=='index-tts' else False},sort_keys=True).encode()).hexdigest()
        reply=self.data/'jobs'/(identifier+'.runtime.json');reply.unlink(missing_ok=True)
        log=self.data/'logs'/(identifier+'.log')
        with self.lock:
            if self.process is None or self.process.poll() is not None or self.key!=key:
                self.stop();env=os.environ.copy()
                if cfg.get('_cached_only'):env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
                env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
                runtime_log=self.data/'logs'/('runtime-'+engine+'.log')
                with runtime_log.open('a',encoding='utf-8') as stream:
                    self.process=subprocess.Popen([cfg['python'],str(self.root/'runtime_worker.py')],cwd=cfg['repo'] if Path(cfg['repo']).is_dir() else self.root,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True,encoding='utf-8',env=env,start_new_session=os.name!='nt')
                self.key=key;self.engine=engine;self.loads+=1;self.error=''
            p=self.process;self.state='loading' if not self.loaded else 'ready' if warm else 'running'
            p.stdin.write(json.dumps({'action':'warm' if warm else 'run','job_path':str(path),'reply_path':str(reply),'log_path':str(log)})+'\n');p.stdin.flush()
        try:
            while not reply.exists():
                if cancelled():raise RuntimeError('Đã hủy tác vụ')
                if p.poll() is not None:
                    extra=self.data/'logs'/('runtime-'+engine+'.log')
                    raise RuntimeError('Bộ xử lý đã dừng. '+(extra.read_text(encoding='utf-8',errors='replace')[-3000:] if extra.exists() else ''))
                time.sleep(.05)
            result=json.loads(reply.read_text(encoding='utf-8'))
            if not result.get('ok'):raise RuntimeError(result.get('error','Không nạp được mô hình'))
            with self.lock:self.loaded=True;self.state='ready'
        except Exception as error:
            self.stop();self.error=str(error)[-3000:];raise
        finally:reply.unlink(missing_ok=True)
