"""Native Windows window, durable WebView profile, owned local server lifecycle."""
import ctypes,json,os,subprocess,sys,threading,time,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from storage import data_dir, configure_cache
DATA=data_dir()
configure_cache(DATA)
URL='http://127.0.0.1:8765';TITLE='QUÂN Voice Studio';VERSION='1.6.5'

def probe():
    from local_server import probe_url
    return probe_url(URL)

def browser_command():
    candidates=[Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe']
    browser=next((p for p in candidates if p.is_file()),None)
    return [str(browser),'--app='+URL,'--user-data-dir='+str(DATA/'desktop-browser'),'--no-first-run','--start-maximized'] if browser else None

def main():
    DATA.mkdir(parents=True,exist_ok=True);(DATA/'logs').mkdir(exist_ok=True)
    global URL
    mutex=None;host=None;thread=None;native=False;session=None;startup_errors=[]
    if os.name=='nt':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('QuanVoice.Studio')
        ctypes.windll.kernel32.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Local\\QuanVoiceStudioDesktop')
        if ctypes.windll.kernel32.GetLastError()==183:
            window=ctypes.windll.user32.FindWindowW(None,TITLE)
            if window:ctypes.windll.user32.ShowWindow(window,9);ctypes.windll.user32.SetForegroundWindow(window)
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex));return
    try:
        from local_server import same_data,COMPATIBLE_VERSIONS
        status=probe()
        if status and (status.get('product')!='QuanVoiceStudio' or not same_data(status.get('data_dir'),DATA)):status=None
        if status and status.get('version') not in COMPATIBLE_VERSIONS:raise RuntimeError('Một phiên Studio cũ còn chạy. Hãy đóng phiên cũ trước khi mở bản cập nhật. Nếu không thấy cửa sổ, khởi động lại Windows một lần. Giữ nguyên thư mục data và model.')
        if not status:
            from local_server import Session
            session=Session(DATA).open();URL=session.url
        if not status and session.owned:
            os.environ['QUAN_VOICE_DESKTOP']='1'
            import server,uvicorn
            server.app.state.local_url=URL
            host=uvicorn.Server(uvicorn.Config(server.app,host='127.0.0.1',port=session.socket.getsockname()[1],access_log=False,log_config=None,timeout_graceful_shutdown=3))
            server.app.state.request_exit=lambda:setattr(host,'should_exit',True)
            def serve():
                try:host.run(sockets=[session.socket])
                except BaseException as error:startup_errors.append(error)
            thread=threading.Thread(target=serve,daemon=True);thread.start()
            for _ in range(300):
                if host.started:break
                if not thread.is_alive():raise RuntimeError('Không khởi động được bộ xử lý cục bộ. '+str(startup_errors[-1] if startup_errors else 'Xem logs/desktop.log.'))
                time.sleep(.1)
            else:raise RuntimeError('Bộ xử lý khởi động chậm. Xem logs/desktop.log.')
        try:
            import webview
            webview.settings['ALLOW_DOWNLOADS']=True
            webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER']=True
            window=webview.create_window(TITLE,URL,width=1360,height=900,maximized=True,min_size=(980,650),text_select=True,confirm_close=True,background_color='#f4f6fa')
            if host:
                def quit_window():
                    try:window.destroy()
                    finally:host.should_exit=True
                server.app.state.request_exit=quit_window
                def quit_for_update():
                    window.confirm_close = False
                    quit_window()
                server.app.state.request_update_exit=quit_for_update
            native=True
            webview.start(gui='edgechromium' if os.name=='nt' else None,private_mode=False,storage_path=str(DATA/'desktop-profile'),icon=str(ROOT/'app.ico'))
        except Exception as error:
            print('Cửa sổ WebView chưa khả dụng: '+str(error),flush=True);native=False
            command=browser_command()
            if command:
                process=subprocess.Popen(command)
                # Dedicated browser profile gives app mode its own lifecycle.
                # If Chromium delegates to an existing process, keep the local
                # backend until the explicit Quit button is used.
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.wait();return
            else:webbrowser.open(URL)
            if thread:
                while thread.is_alive():thread.join(timeout=1)
    finally:
        if host:
            host.should_exit=True
            if thread:thread.join(timeout=10)
        # Keep the data lock/socket until all backend workers have stopped.
        if session and (not thread or not thread.is_alive()):session.close()
        if mutex:ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        log=DATA/'logs/desktop.log';log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('a',encoding='utf-8') as f:f.write(traceback.format_exc())
        if os.name=='nt':ctypes.windll.user32.MessageBoxW(None,str(error)+'\n\nNhật ký: '+str(log),TITLE,16)
        else:raise
