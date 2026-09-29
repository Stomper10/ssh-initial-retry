"""Local-only checks of retry boundaries, deadlines and binary transport."""
import os
import pathlib
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'ssh_initial_retry.py'
CLIENT = b'SSH-2.0-test-client\r\n'
SERVER = b'SSH-2.0-test-server\r\n'


class RetryTests(unittest.TestCase):
    def run_case(self, failures, attempts=3, invalid=False, after_banner=False,
                 mode='close', preamble=b'', server_tail=b''):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(2)
        port = listener.getsockname()[1]
        seen = []
        payloads = []
        errors = []
        payload = bytes(range(256)) * 16

        def serve():
            try:
                while True:
                    try:
                        conn, _ = listener.accept()
                    except socket.timeout:
                        return
                    with conn:
                        conn.settimeout(2)
                        banner = bytearray()
                        while not banner.endswith(b'\n'):
                            part = conn.recv(1)
                            if not part:
                                break
                            banner.extend(part)
                        seen.append(bytes(banner))
                        if len(seen) <= failures:
                            if mode == 'reset':
                                layout = 'hh' if os.name == 'nt' else 'ii'
                                conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                                struct.pack(layout, 1, 0))
                            elif mode == 'timeout':
                                time.sleep(0.45)
                            continue
                        if invalid:
                            conn.sendall(b'x' * 8192)
                            continue
                        conn.sendall(preamble + SERVER + server_tail)
                        if after_banner:
                            continue
                        data = bytearray()
                        while True:
                            part = conn.recv(65536)
                            if not part:
                                break
                            data.extend(part)
                        payloads.append(bytes(data))
                        conn.sendall(bytes(data))
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=serve)
        worker.start()
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), '127.0.0.1', str(port),
                 '--attempts', str(attempts),
                 '--timeout', '0.3' if mode == 'timeout' else '2',
                 '--delay', '0.01'],
                input=CLIENT + (b'' if after_banner or invalid else payload),
                capture_output=True, timeout=12)
            worker.join(4)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(all(item == CLIENT for item in seen))
            return result, seen, payloads, payload
        finally:
            listener.close()
            worker.join(3)

    def test_first_connection_closed_then_binary_transfer(self):
        result, seen, payloads, payload = self.run_case(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(seen), 2)
        self.assertEqual(payloads, [payload])
        self.assertEqual(result.stdout, SERVER + payload)

    def test_connection_reset_then_success(self):
        result, seen, payloads, payload = self.run_case(1, mode='reset')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(seen), 2)
        self.assertEqual(payloads, [payload])
        self.assertEqual(result.stdout, SERVER + payload)

    def test_banner_timeout_then_success(self):
        result, seen, _, payload = self.run_case(1, mode='timeout')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(seen), 2)
        self.assertEqual(result.stdout, SERVER + payload)

    def test_no_retry_needed(self):
        result, seen, _, payload = self.run_case(0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result.stdout, SERVER + payload)
        self.assertEqual(result.stderr, b'')

    def test_success_on_last_attempt(self):
        result, seen, payloads, payload = self.run_case(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(seen), 3)
        self.assertEqual(payloads, [payload])

    def test_retry_limit(self):
        result, seen, _, _ = self.run_case(9)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(seen), 3)
        self.assertEqual(result.stdout, b'')

    def test_no_retry_after_server_banner(self):
        result, seen, _, _ = self.run_case(0, after_banner=True)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result.stdout, SERVER)

    def test_no_retry_on_oversized_identification(self):
        result, seen, _, _ = self.run_case(0, invalid=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(seen), 1)

    def test_preamble_and_bytes_after_banner_are_preserved(self):
        preamble = b'Welcome to the test server\r\n'
        tail = b'\x00\xff\r\n'
        result, seen, _, payload = self.run_case(
            0, preamble=preamble, server_tail=tail)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result.stdout, preamble + SERVER + tail + payload)


if __name__ == '__main__':
    unittest.main()
