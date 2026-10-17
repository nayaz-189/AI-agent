"""Plain-assertion regressions. Fake consent is confined to these test fixtures."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4
import json

from brain.planner import understand_command
from brain.validator import validate_plan
from desktop.confirmation_authority import ConfirmationAuthority
from desktop.desktop_execution_gate import DesktopExecutionGate
from desktop.document_session import NotepadTestSession, ScopedSemanticController
from desktop.test_file_store import TEST_ROOT, TestFileStore
from execution.document_workflow import DEMO_COMMAND, INTRODUCTION, execute_document_workflow
from execution.execution_history import ExecutionHistory
from execution.runtime import execute_plan, _registered_backend
from tools.tool_registry import execute_tool


class MemoryFiles:
    def __init__(self):
        self.names = ("input_test.txt", "output_test.txt")
        self.data = {}
        self.fail_write = False
        self.fail_read = False
        self.closed = False

    def path(self, name):
        assert name in self.names
        return TEST_ROOT / name

    def create(self, name, text):
        if self.fail_write or name in self.data:
            raise OSError("synthetic-private-path")
        self.data[name] = text

    def verify(self, name, text):
        return not self.fail_read and self.data.get(name) == text

    def close(self):
        self.closed = True


class FakeControl:
    def __init__(self):
        self.handle = 201
        self.element_info = SimpleNamespace(control_type="Document", class_name="Editor",
                                             automation_id="Editor", element=SimpleNamespace(
                                                 CurrentIsPassword=False, GetRuntimeId=lambda: [1, 2]))
        self.iface_value = self
        self.CurrentValue = ""
        self.CurrentIsReadOnly = False
        self.fail_mutation = False
        self.wrong_content = False
        self.writes = 0

    def window_text(self):
        return "Editor accessible name, not its value"

    def is_visible(self):
        return True

    def is_enabled(self):
        return True

    def SetValue(self, value):
        self.writes += 1
        if self.fail_mutation:
            raise OSError("synthetic-private-content")
        self.CurrentValue = "wrong value" if self.wrong_content else value


class FakeSession(NotepadTestSession):
    """Real request/binding validation and semantic controller; fake OS and IO."""
    def __init__(self):
        super().__init__(INTRODUCTION)
        self.files = MemoryFiles()
        self.control = FakeControl()
        self.live_identity = {"session_id": self.session_id, "window_handle": 101,
                              "process_id": 12, "runtime_id": [1, 2], "control_handle": 201,
                              "automation_id": "Editor", "class_name": "Editor",
                              "control_type": "Document"}
        self.correct_window = True
        self.ambiguous = False

    def _window_matches(self, handle):
        return self.correct_window and handle == 101

    def _resolve_editor(self, handle):
        if not self._window_matches(handle) or self.ambiguous:
            raise ValueError("Wrong or ambiguous target")
        return self.control, deepcopy(self.live_identity)

    def open(self, request):
        assert self.validate(request)
        self.files.create(self.files.names[0], "")
        self.binding = deepcopy(self.live_identity)

    def semantic_controller(self):
        controller = ScopedSemanticController(self)
        controller.reacquire_delay = 0
        return controller


def run(session=None, ui=lambda request: True):
    session = session or FakeSession()
    history = ExecutionHistory()
    task = execute_document_workflow(session, history=history, confirmation_ui=ui)
    return task, session, history


def opened():
    session = FakeSession()
    session.open(session.open_request())
    return session


def test_success_through_planner_runtime_router_gate_and_semantic_controller():
    session = FakeSession()
    with patch("brain.planner.ask_llm") as model, \
         patch("desktop.document_session.NotepadTestSession", return_value=session):
        plan = understand_command(DEMO_COMMAND)
        task = execute_plan(DEMO_COMMAND, plan, confirmation_ui=lambda request: True)
    model.assert_not_called()
    assert task.status.value == "completed"
    assert len(task.steps) == 4 and all(s.status.value == "completed" for s in task.steps)
    assert session.control.writes == 1
    assert session.files.data[session.files.names[1]] == INTRODUCTION
    assert session.files.closed


def test_notepad_newlines_prepared_before_consent_and_exact_verification():
    session = NotepadTestSession("first\nsecond\r\nthird\r")
    assert session.content == "first\rsecond\rthird\r"
    fake = opened()
    fake.content = session.content
    request = fake.edit_request()
    assert request["arguments"]["new_value"] == "first\rsecond\rthird\r"
    fake.control.CurrentValue = fake.content
    assert fake.state()["content_matches"] is True
    fake.control.CurrentValue += "\r"
    assert fake.state()["content_matches"] is False
    fake.control.CurrentValue = "first\nsecond\nthird\n"
    assert fake.state()["content_matches"] is False


def test_missing_confirmation_stops_before_launch():
    task, session, _ = run(ui=None)
    assert task.status.value == "failed" and session.binding is None
    assert session.files.data == {} and session.control.writes == 0


def test_declined_or_nonboolean_consent_stops():
    for consent in (False, "yes", 1, {"approved": True}):
        task, session, _ = run(ui=lambda request: consent)
        assert task.status.value == "failed" and session.binding is None


def test_edit_denial_stops_export():
    task, session, _ = run(ui=lambda request: request["action"] == "open_test_document")
    assert task.status.value == "failed" and session.control.writes == 0
    assert session.files.names[1] not in session.files.data


def test_expired_authorization():
    session = opened()
    authority = ConfirmationAuthority(30)
    request = session.edit_request()
    with patch("desktop.confirmation_authority.time.monotonic", return_value=100):
        token = authority.issue(request)
    with patch("desktop.confirmation_authority.time.monotonic", return_value=131):
        outcome = DesktopExecutionGate(authority, document_session=session).execute(request, token.token)
    assert outcome["success"] is False and session.control.writes == 0


def test_reused_authorization():
    session = opened()
    authority = ConfirmationAuthority()
    gate = DesktopExecutionGate(authority, document_session=session)
    request = session.edit_request()
    token = authority.issue(request).token
    assert gate.execute(request, token)["success"] is True
    session.control.CurrentValue = ""  # Even restoring state cannot restore consent.
    assert gate.execute(request, token)["success"] is False
    assert session.control.writes == 1


def test_wrong_target_and_action_do_not_borrow_authorization():
    for field, value in (("window_handle", 999), ("action", "toggle")):
        session = opened()
        authority = ConfirmationAuthority()
        request = session.edit_request()
        token = authority.issue(request).token
        request[field] = value
        assert DesktopExecutionGate(authority, document_session=session).execute(request, token)["success"] is False
        assert session.control.writes == 0


def test_cross_session_authority_is_rejected():
    first, second = opened(), opened()
    authority = ConfirmationAuthority()
    token = authority.issue(first.edit_request()).token
    outcome = DesktopExecutionGate(authority, document_session=second).execute(second.edit_request(), token)
    assert outcome["success"] is False and second.control.writes == 0


def test_wrong_document_or_stale_identity_after_confirmation():
    for change in (lambda s: setattr(s, "correct_window", False),
                   lambda s: s.live_identity.update(runtime_id=[9, 9]),
                   lambda s: setattr(s.control, "CurrentValue", "Unexpected user edit"),
                   lambda s: setattr(s, "ambiguous", True)):
        session = FakeSession()
        def consent(request):
            if request["action"] == "set_value":
                change(session)
            return True
        task, _, _ = run(session, consent)
        assert task.status.value == "failed" and session.control.writes == 0
        assert session.files.names[1] not in session.files.data


def test_semantic_mutation_failure_and_wrong_content():
    for field in ("fail_mutation", "wrong_content"):
        session = FakeSession()
        setattr(session.control, field, True)
        task, _, _ = run(session)
        assert task.status.value == "failed" and session.control.writes == 1
        assert session.files.names[1] not in session.files.data


def test_export_revalidates_after_user_decision():
    session = FakeSession()
    def consent(request):
        if request["action"] == "export_test_document":
            session.control.CurrentValue = "Changed while prompt was open"
        return True
    task, _, _ = run(session, consent)
    assert task.status.value == "failed"
    assert session.files.names[1] not in session.files.data


def test_failed_export_and_independent_readback():
    for field in ("fail_write", "fail_read"):
        session = FakeSession()
        def consent(request):
            if request["action"] == "export_test_document":
                setattr(session.files, field, True)
            return True
        task, _, _ = run(session, consent)
        assert task.status.value == "failed"
        assert task.steps[-1].status.value != "completed"


def test_malformed_gate_result_cannot_complete():
    for outcome in (None, True, {"success": True},
                    {"success": True, "verified": True, "error": "failure"},
                    {"success": "true", "verified": True}):
        with patch("execution.document_workflow.DesktopExecutionGate.execute", return_value=outcome):
            task, session, _ = run()
        assert task.status.value == "failed" and session.control.writes == 0


def test_planner_authority_and_arbitrary_paths_rejected():
    base = {"tool": "write_test_introduction", "arguments": {}}
    assert validate_plan(base)
    for key in ("confirmed", "approved_step_id", "confirmation_token", "confirmation_ui"):
        assert not validate_plan({**base, key: True})
        assert not validate_plan({**base, "arguments": {key: "forged"}})
    for args in ({"path": "C:\\outside.txt"}, {"command": "powershell"}, {"text": "untrusted"}):
        assert not validate_plan({**base, "arguments": args})
    assert not validate_plan({"tool": "export_test_document", "arguments": {}})
    assert not execute_tool("write_test_introduction", {})
    assert not _registered_backend("system")("write_test_introduction", {})["success"]


def test_unbound_gate_and_forged_token_cannot_open_document():
    session = FakeSession()
    authority = ConfirmationAuthority()
    request = session.open_request()
    token = authority.issue(request).token
    assert not DesktopExecutionGate(authority).execute(request, token)["success"]
    assert not DesktopExecutionGate(document_session=session).execute(request, "forged")["success"]
    assert session.files.data == {}


def test_unauthorized_export_destination():
    session = opened()
    session.control.CurrentValue = session.content
    request = session.export_request()
    request["arguments"]["output_file"] = "C:\\outside.txt"
    authority = ConfirmationAuthority()
    token = authority.issue(request).token
    assert not DesktopExecutionGate(authority, document_session=session).execute(request, token)["success"]
    assert session.files.names[1] not in session.files.data


def test_history_and_errors_exclude_content_tokens_paths_and_ui_identity():
    task, session, history = run()
    evidence = json.dumps(history.all_events())
    for forbidden in (INTRODUCTION, "C:\\", "runtime_id", "confirmation_token", "input_test.txt"):
        assert forbidden not in evidence
    session = FakeSession()
    session.control.fail_mutation = True
    task, _, history = run(session)
    assert "synthetic-private" not in json.dumps(history.all_events()) + str(task.error)


def test_path_traversal_and_arbitrary_names_rejected_without_io():
    store = TestFileStore(uuid4().hex)
    with patch("desktop.test_file_store.win32file.CreateFile") as create:
        for name in ("../outside.txt", "C:\\outside.txt", "output.txt", store.names[1] + ":stream"):
            try:
                store.create(name, "test")
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe path accepted")
    create.assert_not_called()


def test_reparse_directory_rejected_and_handle_closed():
    store = TestFileStore(uuid4().hex)
    handle = Mock()
    with patch("desktop.test_file_store.win32file.CreateFile", return_value=handle), \
         patch("desktop.test_file_store.win32file.GetFileInformationByHandle", return_value=(0x400,)):
        try:
            store.lock_root()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Reparse point accepted")
    handle.Close.assert_called_once()


def test_real_confined_file_store_roundtrip_no_overwrite():
    # Only new random test files in the approved root; retain them for inspection.
    store = TestFileStore(uuid4().hex)
    try:
        store.create(store.names[1], "Synthetic UTF-8 test: café\n")
        assert store.verify(store.names[1], "Synthetic UTF-8 test: café\n")
        assert not store.verify(store.names[1], "wrong")
        try:
            store.create(store.names[1], "overwrite")
        except ValueError:
            pass
        else:
            raise AssertionError("Overwrite accepted")
    finally:
        store.close()


def test_existing_path_collision_refused():
    identity = uuid4().hex
    original, second = TestFileStore(identity), TestFileStore(identity)
    try:
        original.create(original.names[1], "original")
        try:
            second.create(second.names[1], "overwrite")
        except Exception:
            pass
        else:
            raise AssertionError("Existing path replaced")
        assert original.verify(original.names[1], "original")
    finally:
        second.close()
        original.close()


def test_real_adapter_rejects_ambiguous_controls_before_value_read():
    session = NotepadTestSession(INTRODUCTION)
    window = Mock()
    window.descendants.return_value = [FakeControl(), FakeControl()]
    with patch.object(session, "_window_matches", return_value=True), \
         patch("desktop.document_session.Desktop") as desktop:
        desktop.return_value.window.return_value.wrapper_object.return_value = window
        try:
            session._resolve_editor(101)
        except ValueError:
            pass
        else:
            raise AssertionError("Ambiguous editor accepted")


def test_real_adapter_rejects_ambiguous_windows():
    session = NotepadTestSession(INTRODUCTION)
    session.files = MemoryFiles()
    with patch("desktop.document_session.subprocess.Popen"), \
         patch("desktop.document_session.get_win32_windows", return_value=[
             {"handle": 101, "visible": True}, {"handle": 102, "visible": True}]), \
         patch.object(session, "_window_matches", return_value=True), \
         patch.object(session, "_resolve_editor") as resolve:
        try:
            session.open(session.open_request())
        except ValueError:
            pass
        else:
            raise AssertionError("Ambiguous windows accepted")
    resolve.assert_not_called()


def test_wrong_window_rejected_before_uia_read():
    session = NotepadTestSession(INTRODUCTION)
    with patch.object(session, "_window_matches", return_value=False), \
         patch("desktop.document_session.Desktop") as desktop:
        try:
            session._resolve_editor(999)
        except ValueError:
            pass
        else:
            raise AssertionError("Wrong window accepted")
    desktop.assert_not_called()


def test_changed_precondition_at_last_semantic_reacquisition():
    session = opened()
    controller = session.semantic_controller()
    original = controller._reacquire_target_for_execution
    def changed(*args, **kwargs):
        session.control.CurrentValue = "User typed just now"
        return original(*args, **kwargs)
    request = session.edit_request()
    with patch.object(controller, "_reacquire_target_for_execution", side_effect=changed):
        result = controller.set_value(request["window_handle"], **request["arguments"])
    assert not result["success"] and session.control.writes == 0


def test_real_dialog_only_explicit_yes_approves():
    from desktop.confirmation_ui import confirm_desktop_request
    dialog = Mock()
    with patch("desktop.confirmation_ui.ctypes.windll") as dll:
        dll.user32.MessageBoxTimeoutW = dialog
        for response in (7, 0, 32000, 6):
            dialog.return_value = response
            assert confirm_desktop_request({"action": "test"}) is (response == 6)
        assert dialog.call_args.args[3] & 0x100  # No is the default.
        assert dialog.call_args.args[-1] == 60000


def test_semantic_error_or_nonboolean_result_never_becomes_success():
    from desktop.action_gate import DesktopActionGate
    valid = {"success": True, "verified": True, "executed": True}
    for result in (None, True, {**valid, "error": "private-detail"},
                   {**valid, "success": "true"}, {**valid, "verified": 1},
                   {**valid, "executed": "true"}):
        outcome = DesktopActionGate()._apply_semantic_execution({"success": False}, result)
        assert outcome["success"] is False
        assert "private-detail" not in outcome["error"]


def test_password_control_is_rejected_before_value_access():
    session = NotepadTestSession(INTRODUCTION)
    control = FakeControl()
    control.element_info.element.CurrentIsPassword = True
    del control.iface_value
    window = Mock()
    window.descendants.return_value = [control]
    with patch.object(session, "_window_matches", return_value=True), \
         patch("desktop.document_session.Desktop") as desktop:
        desktop.return_value.window.return_value.wrapper_object.return_value = window
        try:
            session._resolve_editor(101)
        except ValueError:
            pass
        else:
            raise AssertionError("Password control accepted")


def test_notepad_image_lookalikes_rejected():
    from desktop.document_session import is_notepad_process
    with patch("desktop.document_session.win32api.GetSystemDirectory", return_value=r"C:\Windows\System32"), \
         patch("desktop.document_session._program_files_directory", return_value=r"C:\Program Files"):
        for path, expected in (
            (r"C:\Windows\System32\notepad.exe", True),
            (r"C:\Untrusted\notepad.exe", False),
            (r"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad_11.1.2.3_x64__8wekyb3d8bbwe\Notepad\Notepad.exe", True),
            (r"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad_11.1.2.3_x64__impostor\Notepad.exe", False),
        ):
            with patch("desktop.document_session._process_image", return_value=path):
                assert is_notepad_process(123) is expected


def test_short_file_write_is_rejected():
    store = TestFileStore(uuid4().hex)
    handle = Mock()
    with patch.object(store, "lock_root"), \
         patch("desktop.test_file_store.win32file.CreateFile", return_value=handle), \
         patch("desktop.test_file_store.win32file.WriteFile", return_value=(0, 1)):
        try:
            store.create(store.names[1], "longer")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Short write accepted")
        finally:
            store.close()
    handle.Close.assert_called_once()


def test_file_read_failure_and_changed_identity_fail_verification():
    store = TestFileStore(uuid4().hex)
    store._handles[store.names[1]] = Mock()
    reader = Mock()
    original = (0, 0, 0, 0, 1, 0, 4, 1, 1, 1)
    with patch("desktop.test_file_store.win32file.CreateFile", return_value=reader), \
         patch("desktop.test_file_store.win32file.GetFileInformationByHandle", return_value=original), \
         patch("desktop.test_file_store.win32file.ReadFile", side_effect=OSError("private-detail")):
        assert not store.verify(store.names[1], "test")
    changed = (*original[:-1], 999)
    with patch("desktop.test_file_store.win32file.CreateFile", return_value=reader), \
         patch("desktop.test_file_store.win32file.GetFileInformationByHandle", side_effect=[original, changed]), \
         patch("desktop.test_file_store.win32file.ReadFile") as read:
        assert not store.verify(store.names[1], "test")
    read.assert_not_called()
    store.close()


def test_exact_content_verification_rejects_extra_newline():
    session = FakeSession()
    original = session.control.SetValue
    def changed(value):
        original(value + "\n")
    session.control.SetValue = changed
    task, _, _ = run(session)
    assert task.status.value == "failed"
    assert session.files.names[1] not in session.files.data


def test_bound_gate_cannot_be_used_for_raw_input_or_browser_actions():
    session = opened()
    authority = ConfirmationAuthority()
    gate = DesktopExecutionGate(authority, document_session=session)
    for action in ("type_text", "launch_application", "open_website", "open_calculator"):
        request = {"action": action, "window_handle": 101, "arguments": {"text": "untrusted"}}
        token = authority.issue(request).token
        assert gate.execute(request, token)["success"] is False
    assert session.control.writes == 0


def main():
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Document workflow: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
