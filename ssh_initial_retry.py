"""SSH stdio proxy: retry transport failures only before the server banner.

The real SSH client performs host-key verification, authentication and encryption.
Never reconnect after releasing the server identification to that client.
"""
import argparse
import os
import socket
import sys
import threading
import time


def connect(host, port, client_banner, attempts, timeout, delay):
    for attempt in range(1, attempts + 1):
        sock = None
        try:
            deadline = time.monotonic() + timeout
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            sock.sendall(client_banner)
            # Read only through the identification line; leave KEX bytes queued.
            received = bytearray()
            line = bytearray()
            while len(received) < 8192:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('server identification timed out')
                sock.settimeout(remaining)
                byte = sock.recv(1)
                if not byte:
                    raise ConnectionResetError('closed before server identification')
                received.extend(byte)
                line.extend(byte)
                if byte == b'\n':
                    if line.startswith(b'SSH-'):
                        sock.settimeout(None)
                        return sock, bytes(received)
                    line.clear()
            raise ValueError('server identification exceeds 8192 bytes')
        except OSError as error:
            if sock is not None:
                sock.close()
            if attempt == attempts:
                raise
            code = getattr(error, 'winerror', None) or error.errno
            print(f'[ssh-initial-retry] {host}:{port}: initial connection failed '
                  f'({type(error).__name__}, code={code}); '
                  f'retry {attempt + 1}/{attempts}', file=sys.stderr,
                  flush=True)
            time.sleep(delay)
        except BaseException:
            if sock is not None:
                sock.close()
            raise


def relay(sock, server_banner):
    # From this point onwards there is deliberately no retry path.
    sys.stdout.buffer.write(server_banner)
    sys.stdout.buffer.flush()

    def upload():
        try:
            while True:
                data = sys.stdin.buffer.read1(65536)
                if not data:
                    sock.shutdown(socket.SHUT_WR)
                    return
                sock.sendall(data)
        except OSError:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    threading.Thread(target=upload, daemon=True).start()
    while True:
        data = sock.recv(65536)
        if not data:
            return
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host')
    parser.add_argument('port', type=int)
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=4)
    parser.add_argument('--delay', type=float, default=0.3)
    args = parser.parse_args()
    if args.attempts < 1 or args.timeout <= 0 or args.delay < 0:
        parser.error('invalid retry limits')
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    banner = sys.stdin.buffer.readline(256)
    if not banner.startswith(b'SSH-') or not banner.endswith(b'\n'):
        raise ValueError('expected SSH client identification')
    sock, server_banner = connect(args.host, args.port, banner,
                                 args.attempts, args.timeout, args.delay)
    with sock:
        relay(sock, server_banner)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'[ssh-initial-retry] {error}', file=sys.stderr, flush=True)
        os._exit(1)
    # A daemon may be waiting on stdin: skip buffered-stream finalization.
    os._exit(0)
