"""Explicit download of fixed public weights. Inference never downloads anything."""
import hashlib
import os
from pathlib import Path
import secrets
import stat
import urllib.request

from execution.device_storage import private_directory
from voice.settings import MODEL_ROOT, initialize_storage


_WHISPER = "https://huggingface.co/Systran/faster-whisper-tiny.en/resolve/0d3d19a32d3338f10357c0889762bd8d64bbdeba/"
_KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
# name, byte count, SHA-256, public URL. No remote Python or YAML is downloaded.
ASSETS = {
    "whisper": (
        ("whisper-tiny.en/config.json", 2317, "14b1b421a90349bc551b881461426b561a874049cb9e4c4864f2ca384f6a7cc5", _WHISPER + "config.json"),
        ("whisper-tiny.en/model.bin", 75537502, "1a5afae06a4db91c975c9a9d78be5cc110ee4ea022ad57d55492e4550e936b2a", _WHISPER + "model.bin"),
        ("whisper-tiny.en/tokenizer.json", 2128466, "929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df", _WHISPER + "tokenizer.json"),
        ("whisper-tiny.en/vocabulary.txt", 422309, "ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf", _WHISPER + "vocabulary.txt"),
    ),
    "ecapa": (("ecapa/embedding_model.ckpt", 83316686,
        "0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2",
        "https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/resolve/1e47a43813bfa3dfebda84fca9620394f74cc55a/embedding_model.ckpt"),),
    "kokoro": (
        ("kokoro-v1.0.onnx", 325505369, "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a", _KOKORO + "kokoro-v1.0.onnx"),
        ("voices-v1.0.bin", 28214398, "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d", _KOKORO + "voices-v1.0.bin"),
    ),
}


def _check(path, size, expected):
    private_directory(path.parent)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise ValueError("Model integrity check failed.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("Model integrity check failed.")
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("Model integrity check failed.")


def verify_model_assets(kind):
    if type(kind) is not str or kind not in ASSETS:
        raise ValueError("Unknown speech model.")
    for name, size, digest, _ in ASSETS[kind]:
        _check(MODEL_ROOT / name, size, digest)


def prepare_models(kinds=("whisper", "ecapa", "kokoro"), progress=None):
    if type(kinds) not in (tuple, list) or not kinds or any(type(k) is not str or k not in ASSETS for k in kinds):
        raise ValueError("Unknown speech model.")
    initialize_storage()
    # No ambient proxy, HF access token, credential helper, model hub cache or local
    # context. HTTPS redirects serve public weights; exact hashes gate use.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for kind in kinds:
        for name, size, digest, url in ASSETS[kind]:
            target = MODEL_ROOT / name
            private_directory(target.parent, create=True)
            if target.exists() or target.is_symlink():
                _check(target, size, digest)  # Never overwrite existing corrupt/unrelated data.
                continue
            temporary = target.parent / ("model-" + secrets.token_hex(12) + ".tmp")
            try:
                descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
                with os.fdopen(descriptor, "wb") as output:
                    request = urllib.request.Request(url, headers={"User-Agent": "VORAK-local-model-setup"})
                    with opener.open(request, timeout=45) as source:
                        if not source.geturl().startswith("https://"):
                            raise ValueError("Unsafe model download.")
                        count = 0
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            count += len(chunk)
                            if count > size:
                                raise ValueError("Model download exceeded its bound.")
                            output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                _check(temporary, size, digest)
                # rename refuses an existing target on Windows; explicit setup is
                # single-writer on this platform, with no reset/overwrite option.
                if target.exists() or target.is_symlink():
                    raise ValueError("Model target already exists.")
                temporary.rename(target)
                if progress is not None:
                    progress(kind, name)
            finally:
                if temporary.exists():
                    temporary.unlink()  # Only this call's own incomplete public download.


if __name__ == "__main__":
    try:
        prepare_models(progress=lambda kind, name: print("Verified public model asset:", name, flush=True))
    except Exception:
        print("Model setup failed; no unverified weights will be used. Retry after checking connectivity/storage.")
        raise SystemExit(1) from None
