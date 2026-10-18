"""Private local device state. No remote path inputs or general file capability."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import stat


class StorageError(RuntimeError):
    def __init__(self):
        super().__init__("Private device storage unavailable.")


def _windows_security(path, *, create=False):
    """Create an owner/SYSTEM-only directory, or verify its effective ACL.

    Do not rewrite permissions on existing directories. Fail closed instead.
    Administrators and malicious code running as this user remain trusted.
    """
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [pointer]
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, pointer, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD)]
    adv.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(pointer)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                                                        ctypes.POINTER(pointer), pointer]
    adv.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
                                        ctypes.POINTER(pointer), pointer, ctypes.POINTER(pointer),
                                        pointer, ctypes.POINTER(pointer)]
    adv.GetNamedSecurityInfoW.restype = wintypes.DWORD
    adv.GetAce.argtypes = [pointer, wintypes.DWORD, ctypes.POINTER(pointer)]

    def sid_text(sid):
        value = pointer()
        if not adv.ConvertSidToStringSidW(sid, ctypes.byref(value)):
            raise StorageError()
        try:
            return ctypes.wstring_at(value)
        finally:
            kernel.LocalFree(value)

    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise StorageError()
    try:
        size = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(8192)
        if not adv.GetTokenInformation(token, 1, buffer, len(buffer), ctypes.byref(size)):
            raise StorageError()
        user = sid_text(pointer.from_buffer(buffer).value)
    finally:
        kernel.CloseHandle(token)

    if create:
        descriptor = pointer()
        sddl = f"O:{user}D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{user})"
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
            raise StorageError()

        class Attributes(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("descriptor", pointer), ("inherit", wintypes.BOOL)]

        attributes = Attributes(ctypes.sizeof(Attributes), descriptor, False)
        kernel.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(Attributes)]
        try:
            if not kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                raise StorageError()
        finally:
            kernel.LocalFree(descriptor)

    owner, acl, descriptor = pointer(), pointer(), pointer()
    if adv.GetNamedSecurityInfoW(str(path), 1, 5, ctypes.byref(owner), None,
                                 ctypes.byref(acl), None, ctypes.byref(descriptor)) != 0:
        raise StorageError()
    try:
        if not acl.value or sid_text(owner) != user:
            raise StorageError()
        # ACL header: revision, reserved, size, ACE count, reserved.
        count = ctypes.c_ushort.from_address(acl.value + 4).value
        own_access = False
        for index in range(count):
            ace = pointer()
            if not adv.GetAce(acl, index, ctypes.byref(ace)):
                raise StorageError()
            ace_type = ctypes.c_ubyte.from_address(ace.value).value
            flags = ctypes.c_ubyte.from_address(ace.value + 1).value
            mask = ctypes.c_uint32.from_address(ace.value + 4).value
            if ace_type != 0:  # Only simple ACCESS_ALLOWED_ACE entries are supported.
                raise StorageError()
            identity = sid_text(ace.value + 8)
            if identity not in {user, "S-1-5-18"}:
                raise StorageError()
            own_access |= identity == user and not flags & 8 and mask & 0x1F01FF == 0x1F01FF
        if not own_access:
            raise StorageError()
    finally:
        kernel.LocalFree(descriptor)


def _plain(path, *, directory=False):
    info = path.lstat()
    if (getattr(info, "st_file_attributes", 0) & 0x400
            or (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise StorageError()
    return info


def private_directory(path, *, create=False):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise StorageError()
    for parent in path.parents:
        _plain(parent, directory=True)
    if create and not path.exists():
        if os.name == "nt":
            _windows_security(path, create=True)
        else:
            path.mkdir(mode=0o700)
    info = _plain(path, directory=True)
    if os.name == "nt":
        _windows_security(path)
    elif info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise StorageError()
    return path


def private_read(directory, name, limit=16384):
    if type(name) is not str or name in {".", ".."} or re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None:
        raise StorageError()
    path = private_directory(directory) / name
    info = _plain(path)
    if info.st_size > limit:
        raise StorageError()
    if os.name == "nt":
        _windows_security(path)
    elif info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise StorageError()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "rb") as source:
        current = os.fstat(source.fileno())
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise StorageError()
        data = source.read(limit + 1)
    if len(data) > limit:
        raise StorageError()
    return data


def private_create(directory, name, data):
    directory = private_directory(directory)
    if (type(name) is not str or name in {".", ".."} or re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None
            or type(data) is not bytes or len(data) > 16384):
        raise StorageError()
    descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
    if os.name != "nt":
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
