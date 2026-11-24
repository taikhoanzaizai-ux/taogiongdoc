"""Discover published Windows builds on the project's official GitHub Releases."""
import re

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY = "taikhoanzaizai-ux/taogiongdoc"
CURRENT_VERSION = "1.6.3"
ASSET_NAME = "QuanVoice-Studio-Windows.zip"


def version_tuple(tag):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


def latest_release():
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "QuanVoiceStudio"},
    )
    result = {"current": CURRENT_VERSION, "available": False}
    try:
        with urlopen(request, timeout=8) as response:
            release = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return result
        raise
    tag = release.get("tag_name", "")
    if version_tuple(tag) > version_tuple(CURRENT_VERSION):
        download = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{ASSET_NAME}"
        if any(asset.get("browser_download_url") == download for asset in release.get("assets", [])):
            result.update(available=True, latest=tag, download=download)
    return result
