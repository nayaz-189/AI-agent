"""Synthetic indexing/export regressions; no canonical knowledge is read or written."""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from knowledge import source_indexer as indexer
from knowledge import external_context_exporter as exporter
from knowledge import publication_manager as publication

PRIVATE = "SYNTHETIC_PRIVATE_SOURCE_4427"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@contextmanager
def fixture_root():
    runtime = PROJECT_ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source_security_", dir=runtime) as directory:
        yield Path(directory)


def put(root, relative, contents="def legitimate():\n    return 1\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def public_fixture():
    internal = {"project_state": {"project": {"name": PRIVATE, "version": "0.015", "current_day": 15,
                                                "status": "completed"}},
                "repository": {"branch": PRIVATE, "short_commit": "a" * 7},
                "canonical_knowledge": {"decisions": [PRIVATE], "events": [PRIVATE]},
                "source_index": {"modules": [{"path": "main.py", "parse_success": True,
                    "functions": [{"signature": PRIVATE}], "classes": []},
                    {"path": ".kilo/worktree/main.py", "functions": [PRIVATE]}]},
                "runtime": PRIVATE, "skills": [{"description": PRIVATE}]}
    with patch.object(exporter, "build_project_context", return_value=internal):
        return exporter.build_external_context()


def test_explicit_source_roots_exclude_all_temporary_worktrees():
    with fixture_root() as root:
        expected = {"main.py", "execution/valid.py", "skills/installed/hello_skill/main.py"}
        for path in expected:
            put(root, path)
        for excluded in (".kilo", ".codex", ".claude", ".cursor", ".opencode", ".git", ".venv",
                         "runtime", "build", "temp", "unknown_worktree", "execution/worktree"):
            put(root, excluded + "/main.py", "raise RuntimeError('must never execute')\n")
        with patch.object(indexer, "PROJECT_ROOT", root):
            paths = [indexer.relative_path(p) for p in indexer.discover_python_files()]
            assert set(paths) == expected and len(paths) == len(expected)


def test_indexing_never_executes_code_or_exports_default_literals():
    with fixture_root() as root:
        path = put(root, "main.py", "raise RuntimeError('never execute')\ndef sample(value='" + PRIVATE + "'):\n    pass\n")
        with patch.object(indexer, "PROJECT_ROOT", root):
            record = indexer.inspect_python_file(path)
        assert record["parse_success"] is True
        assert record["functions"][0]["signature"] == "sample(value=<default>)"
        assert PRIVATE not in json.dumps(record)


def test_real_hardlinked_source_is_not_read():
    with fixture_root() as root:
        target = put(root, "runtime/private.py", PRIVATE)
        os.link(target, root / "main.py")
        with patch.object(indexer, "PROJECT_ROOT", root):
            record = indexer.inspect_python_file(root / "main.py")
        assert record["parse_success"] is False and record["error"] == "Source read failed."
        assert PRIVATE not in json.dumps(record)


def test_real_directory_link_is_not_traversed():
    with fixture_root() as root:
        target = put(root, "runtime/target/private.py", PRIVATE).parent
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(root / "execution"))
        else:
            (root / "execution").symlink_to(target, target_is_directory=True)
        with patch.object(indexer, "PROJECT_ROOT", root):
            assert indexer.discover_python_files() == []


def test_changed_final_path_is_rejected_before_read():
    with fixture_root() as root:
        path = put(root, "main.py")
        with patch.object(indexer, "PROJECT_ROOT", root), \
             patch("win32file.GetFinalPathNameByHandle", return_value="C:\\synthetic\\outside.py"), \
             patch("win32file.ReadFile") as read:
            assert indexer.inspect_python_file(path)["parse_success"] is False
        read.assert_not_called()


def test_all_tracked_legitimate_python_sources_remain_indexed():
    tracked = subprocess.check_output(["git", "ls-files", "--", "*.py"], cwd=PROJECT_ROOT,
                                      text=True).splitlines()
    indexed = {indexer.relative_path(p) for p in indexer.discover_python_files()}
    assert tracked and set(tracked) <= indexed, sorted(set(tracked) - indexed)
    assert len(indexed) == len(indexer.discover_python_files())


def test_unsafe_and_noncanonical_source_paths_rejected():
    for path in ("../main.py", "C:/private.py", "execution/../main.py", "execution//a.py",
                 "execution\\a.py", "/main.py", "execution/.codex/a.py", "unrelated.py"):
        assert indexer.source_path_allowed(path) is False


def test_external_context_contains_only_structural_metadata():
    context = public_fixture()
    assert PRIVATE not in json.dumps(context)
    assert context["source_interfaces"]["statistics"]["python_files"] == 1
    assert exporter.security_scan(context) == {"safe": True, "findings": []}
    bad = copy.deepcopy(context)
    bad[PRIVATE] = PRIVATE
    result = exporter.security_scan(bad)
    assert result["safe"] is False and PRIVATE not in json.dumps(result)
    bad = copy.deepcopy(context)
    bad["source_interfaces"]["modules"].append(copy.deepcopy(bad["source_interfaces"]["modules"][0]))
    assert exporter.security_scan(bad)["safe"] is False


def test_publication_rejects_private_content_even_with_matching_hash():
    with fixture_root() as root:
        context_path, manifest_path = root / "context.json", root / "manifest.json"
        with patch.object(publication, "EXPORT_PATH", context_path), \
             patch.object(publication, "MANIFEST_PATH", manifest_path), \
             patch.object(publication, "export_external_context", return_value={"exported": True}):
            context_path.write_text(json.dumps(public_fixture()), encoding="utf-8")
            assert publication.create_publication_package()["published"] is True
            assert publication.verify_publication_package()["valid"] is True
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context["runtime"] = PRIVATE
            context_path.write_text(json.dumps(context), encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["external_project_context"]["sha256"] = hashlib.sha256(context_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = publication.verify_publication_package()
            assert result["valid"] is False and PRIVATE not in json.dumps(result)


def test_manifest_cannot_carry_private_prose_or_leak_read_errors():
    with fixture_root() as root:
        context_path, manifest_path = root / "context.json", root / "manifest.json"
        with patch.object(publication, "EXPORT_PATH", context_path), \
             patch.object(publication, "MANIFEST_PATH", manifest_path), \
             patch.object(publication, "export_external_context", return_value={"exported": True}):
            context_path.write_text(json.dumps(public_fixture()), encoding="utf-8")
            publication.create_publication_package()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["notes"] = PRIVATE
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            assert publication.verify_publication_package()["valid"] is False
            with patch.object(Path, "read_text", side_effect=OSError(PRIVATE)):
                result = publication.verify_publication_package()
            assert result["valid"] is False and PRIVATE not in json.dumps(result)


@contextmanager
def publication_fixture():
    from knowledge import context_repo_publisher as copier
    with fixture_root() as root:
        source, destination = root / "exports", root / "AI-agent-context"
        source.mkdir()
        destination.mkdir()
        (destination / ".git").mkdir()
        context = source / "external_project_context.json"
        manifest = source / "external_manifest.json"
        context.write_text(json.dumps(public_fixture()), encoding="utf-8")
        with patch.object(publication, "EXPORT_PATH", context), \
             patch.object(publication, "MANIFEST_PATH", manifest), \
             patch.object(publication, "export_external_context", return_value={"exported": True}):
            assert publication.create_publication_package()["published"]
        with patch.object(copier, "EXPORT_DIRECTORY", source), \
             patch.object(copier, "CONTEXT_REPOSITORY", destination):
            yield copier, source, destination


def test_locked_publication_roundtrip_and_existing_file_replacement():
    with publication_fixture() as (copier, source, destination):
        for _ in range(2):
            assert copier.publish_to_context_repository()["published"] is True
            for name in copier.ALLOWED_ARTIFACTS:
                assert (source / name).read_bytes() == (destination / name).read_bytes()


def test_publication_source_change_is_blocked_during_validation():
    with publication_fixture() as (copier, source, destination):
        validate = copier._validate_publication_bytes
        def attack(artifacts):
            for operation in (
                    lambda: (source / "external_project_context.json").write_text(PRIVATE),
                    lambda: source.rename(source.parent / "redirected")):
                try:
                    operation()
                except OSError:
                    pass
                else:
                    raise AssertionError("Publication source was not locked")
            return validate(artifacts)
        with patch.object(copier, "_validate_publication_bytes", side_effect=attack):
            assert copier.publish_to_context_repository()["published"] is True


def test_publication_destination_hardlink_cannot_modify_unrelated_fixture():
    with publication_fixture() as (copier, source, destination):
        private = source.parent / "synthetic_private.txt"
        private.write_text(PRIVATE, encoding="utf-8")
        os.link(private, destination / "external_manifest.json")
        result = copier.publish_to_context_repository()
        assert result["published"] is False
        assert private.read_text(encoding="utf-8") == PRIVATE
        assert PRIVATE not in json.dumps(result)


def test_publication_junction_and_failed_readback_fail_closed():
    with publication_fixture() as (copier, source, destination):
        import _winapi
        redirected = source.parent / "redirected"
        _winapi.CreateJunction(str(destination), str(redirected))
        with patch.object(copier, "CONTEXT_REPOSITORY", redirected):
            assert copier.publish_to_context_repository()["published"] is False
        read = copier._read_publication_handle
        calls = []
        def corrupted(handle):
            calls.append(True)
            return read(handle) if len(calls) <= 2 else b"incorrect content"
        with patch.object(copier, "_read_publication_handle", side_effect=corrupted):
            assert copier.publish_to_context_repository()["published"] is False


def test_duplicate_json_keys_cannot_hide_private_values_in_publication_bytes():
    for filename, key in (("external_project_context.json", "purpose"),
                          ("external_manifest.json", "publication_type")):
        with publication_fixture() as (copier, source, destination):
            path = source / filename
            original = path.read_text(encoding="utf-8")
            path.write_text('{"' + key + '": "' + PRIVATE + '",' + original[1:], encoding="utf-8")
            # Matching digest is deliberately recomputed: schema validation must
            # reject bytes hidden by the ordinary json.loads last-key-wins rule.
            manifest_path = source / "external_manifest.json"
            if filename == "external_project_context.json":
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["artifacts"]["external_project_context"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = copier.publish_to_context_repository()
            assert result["published"] is False and PRIVATE not in json.dumps(result)
            assert not (destination / "external_project_context.json").exists()
            with patch.object(publication, "EXPORT_PATH", source / "external_project_context.json"), \
                 patch.object(publication, "MANIFEST_PATH", manifest_path):
                assert publication.verify_publication_package()["valid"] is False


def main():
    tests = [f for name, f in globals().items() if name.startswith("test_") and callable(f)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Source/export security: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
