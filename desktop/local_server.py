"""Reserve a loopback socket atomically and share one backend per data folder."""
import json,os,socket,threading,time,urllib.request,webbrowser
from pathlib import Path
VERSION='1.6.4';COMPATIBLE_VERSIONS={VERSION,'1.5.5','1.5.4','1.5.0','1.5.1','1.5.2','1.5.3'};PRODUCT='QuanVoiceStudio';HOST='127.0.0.1';DEFAULT_PORT=8765

def probe_url(url,timeout=.6):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url+'/api/health',timeout=timeout) as response:
            result=json.load(response)
        return result if isinstance(result,dict) else None
    except (OSError,ValueError):return None

def same_data(value,data):
    return not value or os.path.normcase(os.path.realpath(value))==os.path.normcase(os.path.realpath(data))

def existing_url(data,ports=None):
    candidates=[]
    try:
        record=json.loads((Path(data)/'server-instance.json').read_text(encoding='utf-8'))
        port=record['port']
        if isinstance(port,int) and not isinstance(port,bool) and 1024<=port<=65535:candidates.append(port)
    except (OSError,ValueError,KeyError,TypeError):pass
    candidates.extend(ports if ports is not None else [DEFAULT_PORT])
    for port in dict.fromkeys(candidates):
        url=f'http://{HOST}:{port}';status=probe_url(url)
        if not status or status.get('product')!=PRODUCT or not same_data(status.get('data_dir'),data):continue
        if status.get('version') not in COMPATIBLE_VERSIONS:
            raise RuntimeError('Một phiên Studio cũ còn chạy tại '+url+'. Hãy đóng phiên đó trước khi mở bản cập nhật. Nếu không còn thấy cửa sổ, khởi động lại Windows một lần. Giữ nguyên thư mục data và model.')
        return url
    return None

class DataLock:
    def __init__(self,data):self.file=Path(data)/'server.lock';self.stream=None
    def acquire(self):
        self.file.parent.mkdir(parents=True,exist_ok=True)
        stream=self.file.open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                stream.seek(0,2)
                if not stream.tell():stream.write(b'0');stream.flush()
                stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:stream.close();return False
        self.stream=stream;return True
    def close(self):
        if self.stream is None:return
        if os.name=='nt':
            import msvcrt
            self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        self.stream.close();self.stream=None

def reserve_socket(ports):
    errors=[]
    for port in ports:
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            # Do not use SO_REUSEADDR on Windows: it can share a live listener.
            if os.name=='nt':listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            listener.bind((HOST,port));listener.listen(128);listener.setblocking(False)
            return listener
        except OSError as error:errors.append(error);listener.close()
    raise RuntimeError('Không mở được cổng cục bộ cho Studio. Các cổng thử đều đang được dùng hoặc bị Windows chặn. Giữ dữ liệu, đóng phiên Studio cũ rồi mở lại. Chi tiết: '+str(errors[-1] if errors else 'Chưa có cổng để thử.'))

class Session:
    def __init__(self,data,ports=None):
        self.data=Path(data);self.ports=tuple(ports) if ports is not None else tuple(range(DEFAULT_PORT,DEFAULT_PORT+20))+(0,)
        self.lock=DataLock(data);self.socket=None;self.url=None;self.owned=False
    def open(self):
        self.url=existing_url(self.data,self.ports[:1])
        if self.url:return self
        if not self.lock.acquire():
            # The first click may still be starting. Reuse it, never start a
            # second set of model workers against the same studio.db.
            for _ in range(40):
                self.url=existing_url(self.data,self.ports[:1])
                if self.url:return self
                time.sleep(.25)
            raise RuntimeError('Studio đang khởi động hoặc còn chạy trong nền với thư mục data này. Chờ một lát rồi mở lại; không cần cài lại model.')
        try:
            self.url=existing_url(self.data,self.ports[:1])
            if self.url:self.lock.close();return self
            self.socket=reserve_socket(self.ports);port=self.socket.getsockname()[1]
            self.url=f'http://{HOST}:{port}';self.owned=True
            record=self.data/'server-instance.json';temp=record.with_suffix('.tmp')
            temp.write_text(json.dumps({'port':port,'pid':os.getpid(),'version':VERSION,'data_dir':str(self.data)}),encoding='utf-8');temp.replace(record)
            return self
        except BaseException:self.close();raise
    def close(self):
        if self.socket:self.socket.close();self.socket=None
        if self.owned:
            try:
                file=self.data/'server-instance.json';record=json.loads(file.read_text(encoding='utf-8'))
                if record.get('pid')==os.getpid():file.unlink(missing_ok=True)
            except (OSError,ValueError):pass
            self.owned=False
        self.lock.close()

def run_browser():
    from storage import data_dir,configure_cache
    data=data_dir();configure_cache(data);session=Session(data).open()
    try:
        if not session.owned:webbrowser.open(session.url);return
        import server,uvicorn
        server.app.state.local_url=session.url
        host=uvicorn.Server(uvicorn.Config(server.app,host=HOST,port=session.socket.getsockname()[1],access_log=False))
        def open_when_ready():
            for _ in range(300):
                if host.should_exit:return
                if host.started:webbrowser.open(session.url);return
                time.sleep(.1)
        threading.Thread(target=open_when_ready,daemon=True).start()
        host.run(sockets=[session.socket])
    finally:session.close()
