"""Exclusive, handle-locked files inside the one approved desktop test root."""

from pathlib import Path
import re

import win32con
import win32file


TEST_ROOT = Path(r"C:\AI-agent\runtime\desktop_tests")


class TestFileStore:
    def __init__(self, session_id):
        if not re.fullmatch(r"[0-9a-f]{32}", session_id):
            raise ValueError("Invalid test session identity.")
        self.names = (f"input_{session_id}.txt", f"ai_introduction_{session_id}.txt")
        self._handles = {}
        self._directories = []

    def path(self, name):
        if name not in self.names:
            raise ValueError("File is outside this test session.")
        return TEST_ROOT / name

    def lock_root(self):
        """Reject junctions/symlinks; deny rename/delete of every ancestor."""
        if self._directories:
            return
        try:
            for directory in reversed((TEST_ROOT, *TEST_ROOT.parents)):
                handle = win32file.CreateFile(
                    str(directory), 0x80,  # FILE_READ_ATTRIBUTES
                    win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                    None, win32con.OPEN_EXISTING,
                    0x02000000 | 0x00200000, None,  # BACKUP_SEMANTICS, OPEN_REPARSE_POINT
                )
                self._directories.append(handle)
                if win32file.GetFileInformationByHandle(handle)[0] & 0x400:
                    raise ValueError("Reparse-point test directories are forbidden.")
        except Exception:
            self.close()
            raise RuntimeError("Approved test directory is unavailable or unsafe.") from None

    def create(self, name, text):
        if not isinstance(text, str) or len(text.encode("utf-8")) > 16384:
            raise ValueError("Invalid test file content.")
        path = self.path(name)
        self.lock_root()
        if name in self._handles:
            raise ValueError("Test file has already been created.")
        # CREATE_NEW refuses existing files, hardlinks and reparse points.
        handle = win32file.CreateFile(
            str(path), win32con.GENERIC_READ | win32con.GENERIC_WRITE,
            win32con.FILE_SHARE_READ, None, win32con.CREATE_NEW,
            win32con.FILE_ATTRIBUTE_NORMAL | 0x00200000, None,
        )
        self._handles[name] = handle
        data = text.encode("utf-8")
        if data:
            status, written = win32file.WriteFile(handle, data)
            if status != 0 or written != len(data):
                raise RuntimeError("Incomplete test file write.")
        win32file.FlushFileBuffers(handle)

    def verify(self, name, text):
        """Reopen independently, compare file identity and exact UTF-8 bytes."""
        if name not in self._handles:
            return False
        expected = text.encode("utf-8")
        if len(expected) > 16384:
            return False
        try:
            reader = win32file.CreateFile(
                str(self.path(name)), win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None, win32con.OPEN_EXISTING, 0x00200000, None,
            )
            try:
                original = win32file.GetFileInformationByHandle(self._handles[name])
                current = win32file.GetFileInformationByHandle(reader)
                if current[0] & 0x400 or current[4:] != original[4:]:
                    return False
                size = (current[5] << 32) | current[6]
                if size != len(expected):
                    return False
                data = win32file.ReadFile(reader, size)[1] if size else b""
                return data == expected
            finally:
                reader.Close()
        except Exception:
            return False

    def close(self):
        for handle in [*self._handles.values(), *reversed(self._directories)]:
            handle.Close()
        self._handles.clear()
        self._directories.clear()
