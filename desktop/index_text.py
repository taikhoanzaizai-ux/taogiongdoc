"""Load WeText resources on Windows without passing Unicode paths to Kaldi."""
import importlib
import importlib.resources
import importlib.util
import os
from pathlib import Path


def prepare_wetext():
    if os.name != "nt":
        return
    spec = importlib.util.find_spec("wetext")
    if spec is None or spec.origin is None:
        return
    package = Path(spec.origin).parent
    if str(package).isascii():
        return

    # Kaldi's native file reader can open relative ASCII filenames even
    # when Windows has a Unicode path for the process's current directory.
    original_files = importlib.resources.files
    original_directory = Path.cwd()

    def relative_fsts(anchor, *args, **kwargs):
        if anchor == "wetext.fsts":
            return Path(".")
        return original_files(anchor, *args, **kwargs)

    try:
        os.chdir(package / "fsts")
        importlib.resources.files = relative_fsts
        importlib.import_module("wetext")
    finally:
        importlib.resources.files = original_files
        os.chdir(original_directory)
