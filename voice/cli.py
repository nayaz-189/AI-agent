"""Explicit local push-to-talk CLI. Ordinary VORAK startup never records audio."""
import argparse
from dataclasses import asdict, replace
import ctypes
import importlib.metadata
import json
import os
import sys
from threading import Event, Thread
import time

from voice.settings import VoiceSettings, SettingsStore, initialize_storage, VOICE_ROOT, MODEL_ROOT
from voice.audio import VoiceAudioError


class CliError(RuntimeError):
    """Only fixed, locally authored diagnostics may reach the console."""


def available_memory_mb():
    if os.name != "nt":
        return None
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available",
                                                   "virtual_total", "virtual_available", "extended")]
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        return None
    return value.available // (1024 * 1024)


def _headroom():
    available = available_memory_mb()
    if available is not None and available < 2048:
        raise CliError("At least 2 GiB free RAM is required before loading local speech models.")


def _interactive():
    if not sys.stdin.isatty():
        raise CliError("Voice capture and enrollment require an interactive local console.")


def _interruptible(function, cancel):
    """One worker; Esc stops pending audio, never undoes an executed action."""
    result, failure = [], []
    def run():
        try:
            result.append(function())
        except Exception as error:
            failure.append(error)
    worker = Thread(target=run, daemon=True)
    worker.start()
    interrupted = False
    try:
        while worker.is_alive():
            if os.name == "nt":
                import msvcrt
                if msvcrt.kbhit() and msvcrt.getwch() == "\x1b":
                    cancel.set()
            worker.join(0.05)
    except KeyboardInterrupt:
        interrupted = True
        cancel.set()
        worker.join(timeout=3)
    if interrupted:
        raise KeyboardInterrupt()
    if failure:
        raise failure[0]
    return result[0] if result else None


def _record(audio, settings, prompt, seconds=6):
    _interactive()
    if input(prompt + "\nPress Enter to record, or type cancel: ").strip():
        raise CliError("Recording cancelled.")
    print(f"LISTENING for {seconds} seconds. Esc cancels. Raw audio stays in memory.", flush=True)
    cancel = Event()
    clip = _interruptible(lambda: audio.capture(seconds, settings.microphone_device, cancel), cancel)
    print("Microphone stopped.", flush=True)
    return clip


def _runtime():
    from voice.runtime import VoiceRuntime
    initialize_storage()
    return VoiceRuntime()


def _enroll_or_calibrate(command):
    _interactive()
    _headroom()
    runtime = _runtime()
    from voice.models import verify_model_assets
    from voice.runtime import obtain_confirmation
    verify_model_assets("ecapa")
    verify_model_assets("whisper")
    if command == "enroll" and (VOICE_ROOT / "identity" / "enrollment.json").exists():
        raise CliError("An owner is already enrolled; replacement is intentionally unavailable.")
    runtime.recognizer._load()  # Explicit local preflight, before fresh samples.
    runtime.verifier.warmup()
    phrases = ["The bright morning brings a chance to learn something new",
               "I use this computer to build careful and useful software",
               "Please keep my voice profile private on this machine"]

    def samples(prompts):
        values, transcripts = [], set()
        for phrase in prompts:
            clip = _record(runtime.audio, runtime.settings, "Say: " + phrase)
            # These transcripts are used only to reject repeated/empty enrollment
            # phrases. They are neither printed nor stored with the biometric.
            text = runtime.recognizer.transcribe(clip).text.lower().strip()
            words = " ".join("".join(c if c.isalnum() else " " for c in text).split())
            if len(words.split()) < 4 or words in transcripts:
                raise CliError("Use distinct, clearly spoken enrollment phrases.")
            transcripts.add(words)
            values.append(clip)
        return values

    if command == "enroll":
        clips = samples(phrases)
        request = runtime.verifier.enrollment_request(clips)
        token = obtain_confirmation(runtime.authority, request)
        runtime.verifier.enroll(clips, authority=runtime.authority, confirmation_token=token)
        print("Owner profile created privately. Actions remain disabled until separate calibration succeeds.")
    else:
        print("First the enrolled owner supplies two NEW samples with varied tone.")
        owners = samples(["Today I am checking how accurately this system recognizes my speech",
                          "A careful assistant asks permission and verifies what actually happened"])
        if input("A DIFFERENT consenting adult is needed. Type CONSENT when they agree to two recordings: ") != "CONSENT":
            raise CliError("Non-owner recording cancelled.")
        others = samples(["This is a different speaker helping test the voice recognition boundary",
                          "An unknown voice must never be allowed to authorize a computer action"])
        request = runtime.verifier.calibration_request(owners, others)
        token = obtain_confirmation(runtime.authority, request)
        runtime.verifier.calibrate(owners, others, authority=runtime.authority, confirmation_token=token)
        print("Experimental calibration completed. This small sample is not proof of liveness or anti-spoofing.")


def _listen(once=False):
    _interactive()
    _headroom()
    runtime = _runtime()
    from voice.models import verify_model_assets
    for name in ("whisper", "ecapa", "kokoro"):
        verify_model_assets(name)
    if not all((VOICE_ROOT / "identity" / name).is_file() for name in ("enrollment.json", "calibration.json")):
        raise CliError("Enroll the owner and complete separate owner/non-owner calibration before listen.")
    # Do not capture until enrollment/calibration can actually authorize evaluation.
    _, binding = runtime.verifier._profile()
    runtime.verifier._calibration(binding)
    runtime.recognizer._load()
    runtime.verifier.warmup()
    runtime.speech._load()
    print("Push-to-talk only. Esc stops recording/playback; Ctrl+C exits. No background listening.")
    while True:
        clip = _record(runtime.audio, runtime.settings, "Speak a request, for example: Yo Vorak, pull up Calculator.")
        cancel = Event()
        reply = _interruptible(lambda: runtime.process_clip(clip, push_to_talk=True, cancel=cancel), cancel)
        del clip
        print("VORAK:", reply.text)
        try:
            _interruptible(lambda: runtime.speak(reply, cancel=cancel), cancel)
        except Exception:
            print("Speech output unavailable or stopped. The displayed execution result is unchanged.")
        print("Local stage timings:", json.dumps(runtime.diagnostics[-12:]))
        if once:
            break


def main(argv=None):
    parser = argparse.ArgumentParser(description="VORAK local owner-verified voice interface")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("devices", "status", "models", "enroll", "calibrate", "verify", "microphone-test"):
        commands.add_parser(name)
    listen = commands.add_parser("listen")
    listen.add_argument("--once", action="store_true")
    preview = commands.add_parser("preview")
    preview.add_argument("--voice", choices=("male", "female"), required=True)
    settings = commands.add_parser("settings")
    settings.add_argument("--voice", choices=("male", "female"))
    settings.add_argument("--style", choices=("adaptive", "playful", "direct", "professional"))
    settings.add_argument("--profanity", choices=("off", "mild", "natural", "strong"))
    settings.add_argument("--rate", type=float)
    settings.add_argument("--volume", type=float)
    settings.add_argument("--input-device", type=int)
    settings.add_argument("--output-device", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "devices":
            from voice.audio import AudioIO
            print(json.dumps(AudioIO().list_devices(), indent=2))
        elif args.command == "microphone-test":
            from voice.audio import AudioIO
            clip = _record(AudioIO(), SettingsStore().load(), "Say a clear sentence to test the microphone.")
            print("Audio captured and format/level checks passed. Speech and identity were not evaluated.")
            del clip
        elif args.command == "status":
            from voice.models import ASSETS
            from voice.runtime import VOICE_ACTIONS_READY
            packages = {}
            for name in ("sounddevice", "numpy", "faster-whisper", "speechbrain", "torch", "torchaudio", "kokoro-onnx", "onnxruntime"):
                try:
                    packages[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    packages[name] = "not installed"
            print(json.dumps({"packages": packages, "available_memory_mb": available_memory_mb(),
                              "models_present": {kind: all((MODEL_ROOT / a[0]).is_file() for a in assets) for kind, assets in ASSETS.items()},
                              "owner_enrolled": (VOICE_ROOT / "identity" / "enrollment.json").is_file(),
                              "calibration_present": (VOICE_ROOT / "identity" / "calibration.json").is_file(),
                              "voice_actions_ready": VOICE_ACTIONS_READY is True,
                              "input_mode": "explicit_push_to_talk", "anti_spoofing": "not_proven"}, indent=2))
        elif args.command == "models":
            from voice.models import prepare_models
            prepare_models(progress=lambda kind, name: print("Verified public model asset:", name, flush=True))
        elif args.command in {"enroll", "calibrate"}:
            _enroll_or_calibrate(args.command)
        elif args.command == "listen":
            _listen(args.once)
        elif args.command == "verify":
            _interactive()
            _headroom()
            runtime = _runtime()
            runtime.verifier.warmup()
            clip = _record(runtime.audio, runtime.settings, "Owner, non-owner or playback test: speak a fresh sentence. No action will execute.")
            started = time.perf_counter()
            result = runtime.verifier.verify(clip)
            reason = ("similarity_evaluated" if result.score is not None else "verification_unavailable")
            print(result.outcome.value, "reason=", reason,
                  "speaker_ms=", round((time.perf_counter() - started) * 1000, 2))
        elif args.command == "preview":
            _headroom()
            from voice.runtime import VoiceReply
            runtime = _runtime()
            runtime.settings = replace(runtime.settings, voice_profile=args.voice)
            cancel = Event()
            print("Synthesized voice preview. Esc stops playback; no microphone is opened.")
            _interruptible(lambda: runtime.speak(VoiceReply("Hi, I'm VORAK. Clear answers, careful actions, and a little personality.", "preview"), cancel=cancel), cancel)
        else:
            store = SettingsStore()
            updates = {key: value for key, value in {
                "voice_profile": args.voice, "personality_style": args.style, "profanity_level": args.profanity,
                "speech_rate": args.rate, "volume": args.volume, "microphone_device": args.input_device,
                "speaker_device": args.output_device}.items() if value is not None}
            current = replace(store.load(), **updates)
            if updates:
                store.save(current)
            print(json.dumps(asdict(current), indent=2))
        return 0
    except KeyboardInterrupt:
        print("Voice stopped. Any already executed action is unchanged.")
        return 1
    except CliError as error:
        print(str(error))
        return 1
    except VoiceAudioError as error:
        # Closed error vocabulary: never expose driver/model exception text.
        print(str(VoiceAudioError(getattr(error, "code", None))))
        return 1
    except Exception:
        print("Voice operation unavailable. Check private setup, models, memory, devices and enrollment. No success is claimed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
