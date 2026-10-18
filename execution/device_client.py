"""Minimal Termux client and bounded wire helpers; standard library only.

Copy this file and device_storage.py into Termux's private home, not shared storage.
No socket is opened at import. Pairing is out of band; there is no remote pairing API.
"""
import argparse
import base64
from datetime import datetime, timezone
import getpass
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import re
import secrets
import socket
import ssl
import struct
import sys
import time
from uuid import UUID, uuid4

if __package__:
    from execution.device_storage import private_directory, private_read, private_create
else:
    from device_storage import private_directory, private_read, private_create


MAX_FRAME = 16384
REQUEST_DOMAIN = b"VORAK-request-v1\0"
RESPONSE_DOMAIN = b"VORAK-response-v1\0"


class ProtocolError(RuntimeError):
    def __init__(self):
        super().__init__("Device request unavailable or unverified.")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError()
            result[key] = value
        return result
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_FRAME:
        raise ProtocolError()
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError()))


def identifier(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ProtocolError()
    return value


def hex_key(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ProtocolError()
    return bytes.fromhex(value)


def local_address(host):
    try:
        address = ipaddress.IPv4Address(host)
    except ValueError:
        raise ProtocolError() from None

    allowed_networks = (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",  # Tailscale address range
    )

    if str(address) != host or not (
        host == "127.0.0.1"
        or any(
            address in ipaddress.IPv4Network(network)
            for network in allowed_networks
        )
    ):
        raise ProtocolError()

    return host

def validate_profile(profile):
    if type(profile) is not dict or set(profile) != {"peer_id", "secret", "cert_sha256", "host", "port"}:
        raise ProtocolError()
    identifier(profile["peer_id"])
    hex_key(profile["secret"])
    hex_key(profile["cert_sha256"])
    local_address(profile["host"])
    if type(profile["port"]) is not int or not 1024 <= profile["port"] <= 65535:
        raise ProtocolError()
    return profile


def signed(payload, key, domain):
    return canonical({"payload": payload, "mac": hmac.digest(key, domain + canonical(payload), "sha256").hex()})


def authenticated(raw, key, domain):
    envelope = strict_json(raw)
    if type(envelope) is not dict or set(envelope) != {"payload", "mac"}:
        raise ProtocolError()
    supplied = hex_key(envelope["mac"])
    expected = hmac.digest(key, domain + canonical(envelope["payload"]), "sha256")
    if not hmac.compare_digest(supplied, expected):
        raise ProtocolError()
    return envelope["payload"]


def request_packet(profile, body):
    validate_profile(profile)
    if type(body) is not bytes or not 0 < len(body) <= 8192:
        raise ProtocolError()
    return signed({"peer_id": profile["peer_id"], "nonce": secrets.token_hex(32),
                   "body": base64.b64encode(body).decode("ascii")},
                  hex_key(profile["secret"]), REQUEST_DOMAIN)


def receive_frame(connection, timeout=8):
    deadline = time.monotonic() + timeout

    def exact(size):
        result = bytearray()
        while len(result) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProtocolError()
            connection.settimeout(remaining)
            part = connection.recv(size - len(result))
            if not part:
                raise ProtocolError()
            result.extend(part)
        return bytes(result)

    size = struct.unpack("!I", exact(4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ProtocolError()
    return exact(size)


def send_frame(connection, raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_FRAME:
        raise ProtocolError()
    connection.settimeout(5)
    connection.sendall(struct.pack("!I", len(raw)) + raw)


def verify_response(profile, packet, raw, task_id):
    result = authenticated(raw, hex_key(profile["secret"]), RESPONSE_DOMAIN)
    if (type(result) is not dict or set(result) != {"request_hash", "receipt"}
            or result["request_hash"] != hashlib.sha256(packet).hexdigest()):
        raise ProtocolError()
    receipt = result["receipt"]
    if (type(receipt) is not dict or set(receipt) != {"task_id", "status", "verified", "error_code"}
            or receipt["task_id"] not in {None, task_id} or type(receipt["verified"]) is not bool):
        raise ProtocolError()
    state, verified, error = receipt["status"], receipt["verified"], receipt["error_code"]
    if state == "completed":
        valid = verified is True and error is None and receipt["task_id"] == task_id
    elif state in {"queued", "waiting"}:
        valid = verified is False and error is None and receipt["task_id"] == task_id
    elif state == "failed":
        valid = verified is False and error in {"permission_denied", "precondition_failed",
                                                "verification_failed", "backend_unavailable"}
    else:
        valid = False
    if not valid:
        raise ProtocolError()
    return receipt


def exchange(profile, body):
    """One attempt. Pin is checked BEFORE sending any credential-bound request."""
    packet = request_packet(profile, body)
    task_id = identifier(strict_json(body)["task_id"])
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # Exact out-of-band certificate pin replaces CA/hostname trust, never TOFU.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((local_address(profile["host"]), profile["port"]), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname=profile["host"]) as connection:
            certificate = connection.getpeercert(binary_form=True)
            if not certificate or not hmac.compare_digest(hashlib.sha256(certificate).digest(),
                                                          hex_key(profile["cert_sha256"])):
                raise ProtocolError()
            send_frame(connection, packet)
            response = receive_frame(connection, timeout=45)
    return verify_response(profile, packet, response, task_id)


def calculator_request(peer):
    return canonical({"protocol_version": 1, "task_id": str(uuid4()), "source_device": identifier(peer),
                      "target_device": "windows", "operation": "open_calculator", "arguments": {},
                      "expires_at": datetime.fromtimestamp(time.time() + 120, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "requires_approval": False})


def main(argv=None):
    parser = argparse.ArgumentParser(description="VORAK paired Calculator client; no background service")
    parser.add_argument("command", choices=("pair", "open-calculator"))
    args = parser.parse_args(argv)
    directory = Path.home().resolve(strict=True) / ".vorak-device"
    try:
        if args.command == "pair":
            if not sys.stdin.isatty():
                raise ProtocolError()
            profile = {"host": input("Windows private IPv4 address: ").strip(),
                       "port": int(input("Port (e.g. 8765): ")),
                       "peer_id": input("Peer UUID from local Windows pairing: ").strip(),
                       "cert_sha256": input("Certificate SHA-256 from local Windows pairing: ").strip(),
                       "secret": getpass.getpass("64-character secret, transferred out of band: ").strip()}
            validate_profile(profile)
            private_directory(directory, create=True)
            private_create(directory, "pairing.json", canonical(profile))
            print("Pairing saved privately. No connection opened.")
            return 0
        profile = validate_profile(strict_json(private_read(directory, "pairing.json")))
        # Keep the exact request across failures/restarts. This minimal demo has
        # no automatic retry, reset, new-ID-on-timeout or pending-file deletion.
        if not (directory / "pending.json").exists():
            private_create(directory, "pending.json", calculator_request(profile["peer_id"]))
        body = private_read(directory, "pending.json", 8192)
        receipt = exchange(profile, body)
        print(canonical(receipt).decode("ascii"))
        return 0 if receipt["verified"] else 1
    except Exception:
        print("Request unverified or unavailable. Retain pending.json; do not create a new ID to retry.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
