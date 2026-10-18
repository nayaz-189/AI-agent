"""Explicit local TLS receiver. Import and the ordinary VORAK CLI stay offline."""
import argparse
import base64
import getpass
import hashlib
import hmac
from pathlib import Path
import secrets
import socket
import ssl
import sys
from uuid import uuid4

from execution.device_client import (ProtocolError, REQUEST_DOMAIN, RESPONSE_DOMAIN,
    authenticated, canonical, hex_key, identifier, local_address, receive_frame,
    send_frame, signed, strict_json, validate_profile)
from execution.device_protocol import AuthenticatedTransport, DeviceReceiver, VerifiedDelivery
from execution.device_storage import private_directory, private_create, private_read
from execution.replay_journal import ReplayJournal, DEVICE_STORAGE_ROOT, TEST_STORAGE_ROOT
from execution.safe_failure import ErrorCode


class PairingStore:
    """Exactly one device. No remote enrollment, replacement, reset or rotation."""
    def __init__(self, directory=DEVICE_STORAGE_ROOT):
        self.directory = Path(directory).absolute()
        if self.directory != DEVICE_STORAGE_ROOT and not self.directory.is_relative_to(TEST_STORAGE_ROOT):
            raise ProtocolError()
        private_directory(self.directory)

    def load(self):
        # Any marker, including malformed/link markers, revokes immediately.
        marker = self.directory / "revoked"
        if marker.exists() or marker.is_symlink():
            raise ProtocolError()
        return validate_profile(strict_json(private_read(self.directory, "pairing.json")))

    def pair(self, host, port):
        if (self.directory / "revoked").exists():
            raise ProtocolError()
        profile = {"host": host, "port": port, "peer_id": str(uuid4()),
                   "secret": secrets.token_hex(32), "cert_sha256": certificate_pin(self.directory)}
        validate_profile(profile)
        private_create(self.directory, "pairing.json", canonical(profile))
        return {key: profile[key] for key in ("peer_id", "cert_sha256")}

    def revoke(self):
        # Local irreversible marker; a running action cannot be undone.
        private_create(self.directory, "revoked", b"revoked\n")


def initialize(directory=DEVICE_STORAGE_ROOT):
    directory = Path(directory).absolute()
    if directory != DEVICE_STORAGE_ROOT and not directory.is_relative_to(TEST_STORAGE_ROOT):
        raise ProtocolError()
    if directory.exists() or directory.is_symlink():
        raise ProtocolError()  # Never reset a pairing generation after journal loss.
    private_directory(directory, create=True)
    ReplayJournal.provision(directory / "replay.sqlite3")


def certificate_pin(directory):
    pem = private_read(directory, "server.pem").decode("ascii")
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()


def server_context(store, password=None):
    profile = store.load()
    if not hmac.compare_digest(certificate_pin(store.directory), profile["cert_sha256"]):
        raise ProtocolError()
    private_read(store.directory, "server.key")  # Check private ACL, links and size before OpenSSL opens it.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(store.directory / "server.pem", store.directory / "server.key", password=password)
    return context


class PairedTransport(AuthenticatedTransport):
    """Constructed after TLS, then verifies the complete HMAC-bound request."""
    def __init__(self, store, packet):
        self.store = store
        self.profile = store.load()
        payload = authenticated(packet, hex_key(self.profile["secret"]), REQUEST_DOMAIN)
        if (type(payload) is not dict or set(payload) != {"peer_id", "nonce", "body"}
                or identifier(payload["peer_id"]) != self.profile["peer_id"]):
            raise ProtocolError()
        hex_key(payload["nonce"])
        if type(payload["body"]) is not str:
            raise ProtocolError()
        self.body = base64.b64decode(payload["body"], validate=True)
        if not 0 < len(self.body) <= 8192:
            raise ProtocolError()
        self._consumed = False

    def authorize_dispatch(self, peer_id):
        try:
            current = self.store.load()
            return (peer_id == current["peer_id"] == self.profile["peer_id"]
                    and hmac.compare_digest(current["secret"], self.profile["secret"])
                    and hmac.compare_digest(current["cert_sha256"], self.profile["cert_sha256"]))
        except Exception:
            return False

    def receive_verified(self):
        if self._consumed or not self.authorize_dispatch(self.profile["peer_id"]):
            return None
        self._consumed = True
        return VerifiedDelivery(self.profile["peer_id"], self.body)


def process_packet(store, journal, packet):
    transport = PairedTransport(store, packet)
    receiver = DeviceReceiver(transport, registered_peers=(transport.profile["peer_id"],), journal=journal)
    receipt = receiver.receive()
    if receipt["status"] == "queued":
        receipts = receiver.dispatch_pending(online=True)
        receipt = next((item for item in receipts if item["task_id"] == receipt["task_id"]),
                       DeviceReceiver._denial(code=ErrorCode.BACKEND_UNAVAILABLE))
    return signed({"request_hash": hashlib.sha256(packet).hexdigest(), "receipt": receipt},
                  hex_key(transport.profile["secret"]), RESPONSE_DOMAIN)


def create_listener(bind="127.0.0.1", port=8765, *, allow_lan=False):
    local_address(bind)
    if bind != "127.0.0.1" and allow_lan is not True:
        raise ProtocolError()
    if type(port) is not int or not (port == 0 or 1024 <= port <= 65535):
        raise ProtocolError()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((bind, port))
        listener.listen(4)
        listener.settimeout(1)
        return listener
    except Exception:
        listener.close()
        raise


def handle_connection(raw, context, store, journal):
    # One bounded request per TLS connection. No HTTP routes or peer-controlled paths.
    try:
        with raw:
            raw.settimeout(5)
            with context.wrap_socket(raw, server_side=True) as connection:
                packet = receive_frame(connection)
                send_frame(connection, process_packet(store, journal, packet))
        return True
    except Exception:
        # Invalid authentication, TLS errors and private OS errors are never echoed.
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit local VORAK Calculator receiver")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    pairing = commands.add_parser("pair")
    pairing.add_argument("--host", default="127.0.0.1")
    pairing.add_argument("--port", type=int, default=8765)
    commands.add_parser("revoke")
    server = commands.add_parser("serve")
    server.add_argument("--bind", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--allow-lan", action="store_true")
    server.add_argument("--encrypted-key", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize()
            print("Private device directory and replay journal created. Listener is off.")
            return 0
        store = PairingStore()
        if args.command == "pair":
            if not sys.stdin.isatty() or input("Type PAIR CALCULATOR to grant one device this capability: ") != "PAIR CALCULATOR":
                raise ProtocolError()
            print(canonical(store.pair(args.host, args.port)).decode("ascii"))
            print("Secret retained only in private pairing.json. Transfer it out of band; never log or share it online.")
            return 0
        if args.command == "revoke":
            store.revoke()
            print("Pairing revoked. No new dispatch; already executing actions cannot be undone.")
            return 0
        if args.encrypted_key and not sys.stdin.isatty():
            raise ProtocolError()
        context = server_context(store, getpass.getpass("TLS key password: ") if args.encrypted_key else None)
        journal = ReplayJournal(store.directory / "replay.sqlite3")
        with create_listener(args.bind, args.port, allow_lan=args.allow_lan) as listener:
            print("Local TLS receiver enabled until Ctrl+C. Calculator only.")
            while True:
                try:
                    raw, _ = listener.accept()
                except socket.timeout:
                    continue
                handle_connection(raw, context, store, journal)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Receiver unavailable. Check private storage, pairing, TLS and local configuration.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
