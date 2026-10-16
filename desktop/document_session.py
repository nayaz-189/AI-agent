"""Owned Notepad test session and a scoped adapter for existing semantic controls.

No arbitrary executables, keystrokes, file paths, screenshots or private tabs.
"""

from copy import deepcopy
import hashlib
import ntpath
import re
import subprocess
import time
from uuid import uuid4

from pywinauto import Desktop
import win32api
import win32gui
import win32process

from desktop.application_observer import _process_image, _program_files_directory
from desktop.semantic_controller import SemanticController
from desktop.semantic_target_resolver import SemanticTargetResolver
from desktop.test_file_store import TestFileStore
from desktop.window_manager import get_win32_windows


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_notepad_process(pid):
    image = _process_image(pid)
    if not image:
        return False
    image = ntpath.normcase(ntpath.normpath(image))
    if image == ntpath.normcase(ntpath.join(win32api.GetSystemDirectory(), "notepad.exe")):
        return True
    root = ntpath.normcase(ntpath.join(_program_files_directory(), "WindowsApps")) + "\\"
    if not image.startswith(root):
        return False
    parts = image[len(root):].split("\\")
    return bool(re.fullmatch(
        r"microsoft\.windowsnotepad_\d+\.\d+\.\d+\.\d+_(?:x64|x86|arm64)_.*_8wekyb3d8bbwe",
        parts[0],
    )) and ntpath.basename(image) == "notepad.exe"


class ScopedResolver(SemanticTargetResolver):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def inspect_targets(self, window_handle):
        control, _ = self.session.editor()
        if window_handle != self.session.binding["window_handle"]:
            raise ValueError("Wrong session window.")
        descriptor = self._build_target_descriptor(window_handle, 0, control)
        descriptor["value"] = str(control.iface_value.CurrentValue)
        return {"success": True, "targets": [descriptor], "error": None}


class ScopedSemanticController(SemanticController):
    """Reuses set_value/select/toggle; only the session's bound control is visible."""
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.target_resolver = ScopedResolver(session)

    def _connect_window(self, window_handle):
        session = self.session
        if window_handle != session.binding["window_handle"]:
            raise ValueError("Wrong session window.")

        class Scope:
            def descendants(self, control_type=None):
                control, _ = session.editor()
                return [control] if control.element_info.control_type == control_type else []
        return Scope()


class NotepadTestSession:
    def __init__(self, content):
        if not isinstance(content, str) or not content or len(content) > 4096:
            raise ValueError("Invalid introduction content.")
        self.session_id = uuid4().hex
        self.content = content
        self.files = TestFileStore(self.session_id)
        self.binding = None
        self.saved = False

    def semantic_controller(self):
        return ScopedSemanticController(self)

    def open_request(self):
        return {"action": "open_test_document", "arguments": {
            "session_id": self.session_id,
            "application": "notepad",
            "input_file": str(self.files.path(self.files.names[0])),
            "output_file": str(self.files.path(self.files.names[1])),
        }}

    def _window_matches(self, handle):
        if not win32gui.IsWindow(handle) or not win32gui.IsWindowVisible(handle) or win32gui.IsIconic(handle):
            return False
        pid = win32process.GetWindowThreadProcessId(handle)[1]
        if not is_notepad_process(pid):
            return False
        # Only now read the title of an identified Notepad process. Never read
        # editor content until its title matches our unpredictable owned file.
        title = win32gui.GetWindowText(handle).lstrip("* ")
        stem = self.files.path(self.files.names[0]).stem
        return title.startswith(stem + " - ") or title.startswith(stem + ".txt - ")

    def _resolve_editor(self, handle):
        if not self._window_matches(handle):
            raise ValueError("Wrong or stale document window.")
        window = Desktop(backend="uia").window(handle=handle).wrapper_object()
        # Scope enumeration by type. Do not inspect tabs, browsers or screenshots.
        candidates = window.descendants(control_type="Document")
        if not candidates:
            candidates = window.descendants(control_type="Edit")
        candidates = [c for c in candidates if c.is_visible() and c.is_enabled()]
        if len(candidates) != 1:
            raise ValueError("Document control is absent or ambiguous.")
        control = candidates[0]
        if control.element_info.element.CurrentIsPassword:
            raise ValueError("Password controls are forbidden.")
        value = control.iface_value
        if value.CurrentIsReadOnly:
            raise ValueError("Document is read-only.")
        info = control.element_info
        runtime_id = list(info.element.GetRuntimeId())
        if not runtime_id:
            raise ValueError("Stable UI Automation identity unavailable.")
        identity = {
            "session_id": self.session_id, "window_handle": handle,
            "process_id": win32process.GetWindowThreadProcessId(handle)[1],
            "runtime_id": runtime_id, "control_handle": control.handle,
            "automation_id": info.automation_id or "", "class_name": info.class_name or "",
            "control_type": info.control_type,
        }
        return control, identity

    def editor(self):
        if self.binding is None:
            raise ValueError("No owned document is bound.")
        control, identity = self._resolve_editor(self.binding["window_handle"])
        if identity != self.binding:
            raise ValueError("Document control identity changed.")
        if not self._window_matches(self.binding["window_handle"]):
            raise ValueError("Document changed during observation.")
        return control, str(control.iface_value.CurrentValue)

    def open(self, request):
        if request != self.open_request() or self.binding is not None:
            raise ValueError("Invalid launch request.")
        self.files.create(self.files.names[0], "")
        subprocess.Popen([
            ntpath.join(win32api.GetSystemDirectory(), "notepad.exe"),
            str(self.files.path(self.files.names[0])),
        ], shell=False)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            matches = [w["handle"] for w in get_win32_windows(include_titles=False)
                       if w.get("visible") and self._window_matches(w["handle"])]
            if len(matches) > 1:
                raise ValueError("Ambiguous document windows.")
            if len(matches) == 1:
                control, binding = self._resolve_editor(matches[0])
                if str(control.iface_value.CurrentValue) != "":
                    raise ValueError("New test document was not empty.")
                self.binding = binding
                return
            time.sleep(0.1)
        raise RuntimeError("Owned Notepad window was not verified.")

    def edit_request(self):
        control, before = self.editor()
        if before != "":
            raise ValueError("Expected an empty owned document.")
        return {"action": "set_value", "window_handle": self.binding["window_handle"],
                "binding": deepcopy(self.binding), "arguments": {
                    "target": {"role": "document" if self.binding["control_type"] == "Document" else "text_field",
                               "automation_id": self.binding["automation_id"], "class_name": self.binding["class_name"]},
                    "expected_before": "", "new_value": self.content,
                }}

    def export_request(self):
        _, text = self.editor()
        if text != self.content:
            raise ValueError("Document content does not match the proposal.")
        return {"action": "export_test_document", "window_handle": self.binding["window_handle"],
                "binding": deepcopy(self.binding), "arguments": {
                    "output_file": str(self.files.path(self.files.names[1])),
                    "content_digest": digest(text), "save_mode": "exclusive_utf8_buffer_export",
                }}

    def validate(self, request):
        action = request.get("action")
        if action == "open_test_document":
            return self.binding is None and request == self.open_request()
        if action == "set_value":
            return request == self.edit_request()
        if action == "export_test_document":
            return not self.saved and request == self.export_request()
        return False

    def export(self, request):
        if not self.validate(request):
            raise ValueError("Export target or state changed.")
        _, text = self.editor()  # fresh UI read, never the planned string as save source
        if text != self.content or digest(text) != request["arguments"]["content_digest"]:
            raise ValueError("Export content changed.")
        self.files.create(self.files.names[1], text)
        self.saved = True

    def state(self):
        state = {"document_ready": False, "document_empty": False,
                 "content_matches": False, "file_matches": False}
        if self.binding is not None:
            try:
                _, text = self.editor()
                state.update(document_ready=True, document_empty=text == "", content_matches=text == self.content)
            except Exception:
                pass
        if self.saved:
            state["file_matches"] = self.files.verify(self.files.names[1], self.content)
        return state

    def close(self):
        self.files.close()
