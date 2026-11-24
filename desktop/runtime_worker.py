"""Private stdin worker, running in one engine's own Python environment."""
import contextlib,json,sys,traceback
from pathlib import Path
from adapter import EngineRuntime

def main():
    runtime=None
    for line in sys.stdin:
        request=json.loads(line);reply=Path(request['reply_path']);log=Path(request['log_path'])
        try:
            payload=json.loads(Path(request['job_path']).read_text(encoding='utf-8'))
            with log.open('a',encoding='utf-8') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
                if runtime is None:
                    print('Nạp mô hình từ dữ liệu trên ổ đĩa...',flush=True);runtime=EngineRuntime(payload)
                else:print('Dùng lại mô hình đang giữ trong RAM.',flush=True)
                if request.get('action')!='warm':runtime.run(payload)
                result={'ok':True,'engine':payload['engine'],'resident':True}
        except Exception:
            result={'ok':False,'error':traceback.format_exc()[-6000:]}
            with log.open('a',encoding='utf-8') as stream:stream.write(result['error'])
        temp=reply.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temp.replace(reply)
        if not result['ok']:break
if __name__=='__main__':main()
