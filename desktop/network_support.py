"""Bounded retries for transient downloads; retain uv/HF partial caches."""
import subprocess, time

def transient(text):
    t=text.lower()
    if any(s in t for s in ('no space left','disk full','winerror 112','401','403','certificate_verify_failed')):return False
    return any(s in t for s in ('dns error','no such host','11001','getaddrinfo failed','nameresolutionerror','connectionerror','connecttimeout','readtimeout','timed out','connection reset','incompleteread','chunkedencodingerror','connection broken','temporary failure in name resolution','failed to fetch','client error (connect)'))

def run_download(args,*,cwd=None,attempts=3):
    for attempt in range(attempts):
        tail=''
        with subprocess.Popen(list(map(str,args)),cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace') as process:
            for line in process.stdout:
                print(line,end='',flush=True);tail=(tail+line)[-16000:]
            code=process.wait()
        if code==0:return
        if attempt+1==attempts or not transient(tail):raise subprocess.CalledProcessError(code,args,output=tail)
        delay=(5,15)[min(attempt,1)]
        print(f'Kết nối tải bị gián đoạn; giữ cache và thử lại sau {delay}s ({attempt+2}/{attempts}).',flush=True)
        time.sleep(delay)
