"""Discover published Windows builds on the project's official GitHub Releases."""
import re

import httpx

REPOSITORY = "taikhoanzaizai-ux/taogiongdoc"
CURRENT_VERSION = "1.6.0"
ASSET_NAME = "QuanVoice-Studio-Windows.zip"


def version_tuple(tag):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


def latest_release():
    response = httpx.get(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "QuanVoiceStudio"},
        timeout=8,
    )
    result = {"current": CURRENT_VERSION, "available": False}
    if response.status_code == 404:
        return result
    response.raise_for_status()
    release = response.json()
    tag = release.get("tag_name", "")
    if version_tuple(tag) > version_tuple(CURRENT_VERSION):
        download = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{ASSET_NAME}"
        if any(asset.get("browser_download_url") == download for asset in release.get("assets", [])):
            result.update(available=True, latest=tag, download=download)
    return result
