"""Apply a staged Windows update after the Studio process exits."""
import ctypes
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import traceback
import zipfile

ROOT_FILES = {
    "BAT_DAU.bat", "BAT_DAU_NHANH.bat", "CHAN_DOAN.bat", "HUONG_DAN.md",
    "MO_VA_GHI_LOI.cmd", "QUAN_VOICE.vbs", "SUA_FISH_WSL.bat",
    "Start-GPT-SoVITS.bat", "Start-Linux.sh", "Start-Windows.bat", "THIRD_PARTY.md",
}
APP_DIRS = {"desktop", "windows", "scripts", "tests"}


def stage_archive(archive, destination):
    entries = set()
    total = 0
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            if item.is_dir():
                continue
            parts = item.filename.split("/")
            if (len(parts) < 2 or parts[0] != "QuanVoice-Studio"
                    or any(not piece or piece in (".", "..") or piece[-1] in ". "
                           or any(c in piece for c in "\\:*?<>|\"") for piece in parts)
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError("Invalid update archive path")
            relative = Path(*parts[1:])
            if (len(relative.parts) == 1 and relative.name not in ROOT_FILES
                    or len(relative.parts) > 1 and relative.parts[0] not in APP_DIRS):
                raise ValueError("Unexpected file in update archive")
            key = relative.as_posix().casefold()
            total += item.file_size
            if key in entries or total > 64 * 1024 * 1024:
                raise ValueError("Invalid update archive size or duplicate path")
            entries.add(key)
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with package.open(item) as source, output.open("xb") as target:
                shutil.copyfileobj(source, target)
    if not {"quan_voice.vbs", "desktop/desktop_app.py", "desktop/server.py",
            "windows/setup-windows.ps1"}.issubset(entries):
        raise ValueError("Incomplete update archive")


def replace_application(root, staged, backup):
    plans = []
    for source in sorted(staged.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(staged)
        target = root / relative
        if target.resolve() != target or any(
            part.is_symlink() or getattr(part.lstat(), "st_file_attributes", 0) & 1024
            for part in (target, *target.parents) if part != root and root in part.parents and part.exists()
        ):
            raise OSError(f"Update target contains a link: {target}")
        plans.append((source, target, backup / relative))
    completed = []
    try:
        for source, target, saved in plans:
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            if existed:
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            os.replace(source, target)
            completed.append((target, saved, existed))
    except Exception:
        for target, saved, existed in reversed(completed):
            if existed:
                os.replace(saved, target)
            else:
                target.unlink()
        raise


def wait_for_studio(pid):
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(handle, 60000) != 0:
            raise TimeoutError("Studio did not exit within 60 seconds")
    finally:
        kernel.CloseHandle(handle)


def main():
    root, folder, log = map(Path, sys.argv[1:4])
    try:
        wait_for_studio(int(sys.argv[4]))
        replace_application(root, folder / "staged", folder / "backup")
        wscript = Path(os.environ["SystemRoot"]) / "System32" / "wscript.exe"
        subprocess.Popen([str(wscript), str(root / "QUAN_VOICE.vbs")], cwd=root)
    except Exception:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(
            None, f"Cập nhật chưa hoàn tất. Xem nhật ký: {log}", "QUAN Voice Studio", 16
        )
        return
    shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
