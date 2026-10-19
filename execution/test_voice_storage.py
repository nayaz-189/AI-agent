"""Confined synthetic settings/model fixtures; never reads a real voice profile."""
from contextlib import contextmanager, redirect_stdout
from dataclasses import asdict, replace
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from execution.device_storage import private_create, private_directory
from voice.settings import SettingsStore, VoiceSettings, SettingsError, initialize_storage
from voice import models


@contextmanager
def fixture():
    parent = Path(__file__).resolve().parents[1] / "runtime"
    with tempfile.TemporaryDirectory(prefix="voice_storage_tests_", dir=parent) as directory:
        root = Path(directory) / "voice"
        initialize_storage(root)
        yield root


def rejects(function, error_type=SettingsError):
    try:
        function()
    except error_type:
        return
    raise AssertionError("Invalid storage operation was accepted")


def test_cosmetic_settings_persist_with_no_authorization_preferences():
    with fixture() as root:
        store = SettingsStore(root)
        assert store.load() == VoiceSettings()
        updated = replace(store.load(), voice_profile="female", personality_style="professional",
                          profanity_level="off", speech_rate=1.15, volume=0.6,
                          microphone_device=1, speaker_device=2)
        store.save(updated)
        assert SettingsStore(root).load() == updated
        store.save(replace(updated, voice_profile="male"))
        assert store.load().voice_profile == "male"
        assert not list(root.glob("*.tmp"))
        assert set(asdict(store.load())) == {"voice_profile", "personality_style", "profanity_level",
            "speech_rate", "volume", "conversation_timeout_seconds", "microphone_device", "speaker_device"}


def test_settings_reject_unknown_fields_invalid_types_and_ranges():
    defaults = asdict(VoiceSettings())
    for key, value in (("confirmed", True), ("disable_owner_check", True), ("always_listening", True),
                       ("voice_profile", []), ("speech_rate", float("nan")), ("volume", True),
                       ("microphone_device", -1), ("conversation_timeout_seconds", 10000)):
        rejects(lambda: VoiceSettings.from_dict(dict(defaults, **{key: value})))


def test_duplicate_keys_corruption_and_backend_errors_are_sanitized():
    with fixture() as root:
        private_create(root, "settings.json", b'{"voice_profile":"female","voice_profile":"male"}')
        rejects(SettingsStore(root).load)
        before = (root / "settings.json").read_bytes()
        rejects(lambda: SettingsStore(root).save(VoiceSettings()))
        assert (root / "settings.json").read_bytes() == before
        with patch("voice.settings.private_directory", side_effect=OSError("SYNTHETIC_PRIVATE_PATH")):
            try:
                SettingsStore(root).load()
            except SettingsError as error:
                assert "SYNTHETIC_PRIVATE_PATH" not in str(error)
            else:
                raise AssertionError("Storage error not propagated")


def test_settings_hardlink_cannot_read_or_replace_unrelated_data():
    with fixture() as root:
        target = root.parent / "synthetic_unrelated.txt"
        target.write_bytes(b"SYNTHETIC_PRIVATE_DATA")
        os.link(target, root / "settings.json")
        rejects(SettingsStore(root).load)
        rejects(lambda: SettingsStore(root).save(VoiceSettings()))
        assert target.read_bytes() == b"SYNTHETIC_PRIVATE_DATA"


def test_settings_reparse_directory_rejected():
    with fixture() as root:
        link = root.parent / "redirected"
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(root), str(link))
        else:
            link.symlink_to(root, target_is_directory=True)
        rejects(SettingsStore(link).load)
        rejects(lambda: SettingsStore(link).save(VoiceSettings()))
        assert not (root / "settings.json").exists()


def test_model_integrity_size_hash_and_hardlink_checked_without_network():
    with fixture() as root:
        model_root = root / "models"
        data = b"synthetic public model fixture"
        path = model_root / "fixture.bin"
        private_create(model_root, path.name, data)
        digest = hashlib.sha256(data).hexdigest()
        manifest = {"fixture": ((path.name, len(data), digest, "https://example.com/fixture"),)}
        with patch.object(models, "MODEL_ROOT", model_root), patch.object(models, "ASSETS", manifest), \
             patch("socket.socket") as network:
            models.verify_model_assets("fixture")
            rejects(lambda: models.verify_model_assets("unknown"), ValueError)
            path.write_bytes(b"x" * len(data))
            rejects(lambda: models.verify_model_assets("fixture"), ValueError)
            path.write_bytes(data)
            os.link(path, root / "alias.bin")
            rejects(lambda: models.verify_model_assets("fixture"), ValueError)
            network.assert_not_called()


def test_explicit_download_hash_checks_and_never_overwrites_existing_model():
    with fixture() as root:
        data = b"synthetic public fixture"
        target = root / "models" / "fixture.bin"
        manifest = {"fixture": ((target.name, len(data), hashlib.sha256(data).hexdigest(),
                                 "https://example.com/fixture"),)}
        response = BytesIO(data)
        response.geturl = lambda: "https://example.com/fixture"
        opener = Mock()
        opener.open.return_value = response
        with patch.object(models, "MODEL_ROOT", target.parent), patch.object(models, "ASSETS", manifest), \
             patch.object(models, "initialize_storage"), \
             patch("urllib.request.build_opener", return_value=opener):
            models.prepare_models(("fixture",))
            assert target.read_bytes() == data
            models.prepare_models(("fixture",))
            opener.open.assert_called_once()
            target.write_bytes(b"broken")
            rejects(lambda: models.prepare_models(("fixture",)), ValueError)
            assert target.read_bytes() == b"broken"
            assert not list(target.parent.glob("*.tmp"))


def test_bad_download_leaves_no_usable_model_or_partial_file():
    for kind in ("size", "hash", "insecure"):
        with fixture() as root:
            data = b"fixture"
            target = root / "models" / "fixture.bin"
            manifest = {"fixture": ((target.name, len(data), hashlib.sha256(data).hexdigest(),
                                     "https://example.com/fixture"),)}
            response = BytesIO(data + b"extra" if kind == "size" else b"invalid" if kind == "hash" else data)
            response.geturl = lambda: "http://example.com/fixture" if kind == "insecure" else "https://example.com/fixture"
            opener = Mock()
            opener.open.return_value = response
            with patch.object(models, "MODEL_ROOT", target.parent), patch.object(models, "ASSETS", manifest), \
                 patch.object(models, "initialize_storage"), patch("urllib.request.build_opener", return_value=opener):
                rejects(lambda: models.prepare_models(("fixture",)), ValueError)
                assert not target.exists() and not list(target.parent.glob("*.tmp"))


def test_cli_never_opens_microphone_without_interactive_user_activation():
    from voice import cli
    with patch("sys.stdin.isatty", return_value=False), patch("voice.audio.AudioIO.capture") as capture, \
         redirect_stdout(StringIO()):
        assert cli.main(["enroll"]) == 1
        assert cli.main(["calibrate"]) == 1
        assert cli.main(["listen", "--once"]) == 1
        assert cli.main(["microphone-test"]) == 1
        capture.assert_not_called()


def test_memory_failure_and_backend_errors_are_safe_cli_messages():
    from voice import cli
    output = StringIO()
    with patch.object(cli, "available_memory_mb", return_value=512), redirect_stdout(output):
        assert cli.main(["preview", "--voice", "male"]) == 1
    assert "2 GiB" in output.getvalue()
    output = StringIO()
    with patch("voice.audio.AudioIO.list_devices", side_effect=RuntimeError("SYNTHETIC_PRIVATE_PATH")), \
         redirect_stdout(output):
        assert cli.main(["devices"]) == 1
    assert "SYNTHETIC_PRIVATE_PATH" not in output.getvalue()


def test_cli_audio_failure_reports_only_closed_error_message():
    from voice import cli
    from voice.audio import VoiceAudioError
    output = StringIO()
    with patch.object(cli, "_record", side_effect=VoiceAudioError("capture_failed")), \
         redirect_stdout(output):
        assert cli.main(["microphone-test"]) == 1
    assert output.getvalue().strip() == "Microphone capture failed; check the selected input device."


def test_verification_diagnostic_does_not_expose_biometric_scores():
    from voice import cli
    from voice.identity import Verification, SpeakerOutcome
    for score in (None, 0.95123456789):
        runtime = Mock()
        runtime.verifier.verify.return_value = Verification(
            SpeakerOutcome.OWNER_UNCERTAIN, 1.0, "SYNTHETIC_PRIVATE_DIGEST", score)
        output = StringIO()
        with patch.object(cli, "_interactive"), patch.object(cli, "_headroom"), \
             patch.object(cli, "_runtime", return_value=runtime), patch.object(cli, "_record"), \
             redirect_stdout(output):
            assert cli.main(["verify"]) == 0
        text = output.getvalue()
        assert text.startswith("OWNER_UNCERTAIN reason=")
        assert ("verification_unavailable" if score is None else "similarity_evaluated") in text
        assert "0.95123456789" not in text and "SYNTHETIC_PRIVATE_DIGEST" not in text
        runtime.verifier.warmup.assert_called_once_with()


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"Voice storage/setup: {len(tests)} passed (synthetic fixtures)")
