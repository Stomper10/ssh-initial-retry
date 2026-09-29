# ssh-initial-retry

**English** | [한국어](README.ko.md)

[![Tests](https://github.com/Stomper10/ssh-initial-retry/actions/workflows/tests.yml/badge.svg)](https://github.com/Stomper10/ssh-initial-retry/actions/workflows/tests.yml)

**SSH fails once, then works when you try again? Automate that initial retry.**

A small Python `ProxyCommand` helper for OpenSSH. It retries transport failures
**only before the server's SSH identification line arrives**, then relays the
connection normally. Python standard library only. No server changes.

## The problem

You open a terminal or a VS Code Remote-SSH window and see:

```text
kex_exchange_identification: read: Connection reset
Connection reset by <server> port <port>
```

Trying again works. This helper automates that step when the failure happens
during the initial TCP connection or SSH identification exchange.

This is a workaround for a specific failure stage, **not a fix for every SSH
error**. It does not establish the cause of a reset or bypass authentication or
access controls. No particular institution or network policy is assumed.

## How it works

```text
OpenSSH / VS Code Remote-SSH
  -> local Python helper
      -> connect and send the client's SSH identification line
          -> reset / EOF / timeout? retry, up to the configured limit
          -> server identification received?
              relay bytes; NEVER reconnect this session
```

The real SSH client still checks host keys, authenticates and encrypts traffic.
Only the client's public identification line can be replayed. The helper never
replays authentication, remote commands, terminal input or file-transfer data.
It does not store credentials or traffic.

## Quick start

Requires OpenSSH and **Python 3.10+**. No `pip install` is needed.

Clone this repository into a normal project directory. **Do not initialize or
publish a repository from your existing `.ssh` directory.**

```sh
git clone https://github.com/Stomper10/ssh-initial-retry.git
```

### Windows

Find your Python executable in PowerShell:

```powershell
python -c "import sys; print(sys.executable)"
```

Add a `ProxyCommand` to the relevant existing host in
`%USERPROFILE%\.ssh\config`. Replace both example paths with your actual
absolute paths; use forward slashes and quote paths containing spaces.

```sshconfig
Host research-server
    HostName server.example.org
    User your-user
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ProxyCommand "C:/path/to/python.exe" -I -u "C:/path/to/ssh-initial-retry/ssh_initial_retry.py" %h %p
```

Keep your existing address, username, port and key. Only the `ProxyCommand`
line is new. Keep the script at that location after configuring it.

### macOS / Linux

Find Python with `command -v python3`, then use its absolute path:

```sshconfig
Host research-server
    HostName server.example.org
    User your-user
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ProxyCommand /absolute/path/to/python3 -I -u /absolute/path/to/ssh_initial_retry.py %h %p
```

The same implementation is exercised by the cross-platform test workflow.
Local mock tests do not by themselves establish real-server compatibility on
every operating system.

### Connect normally

```sh
ssh research-server
```

In VS Code, use **Remote-SSH: Connect to Host...** and choose that same host.
The extension must use the SSH config file you edited. This helper does not
require changing `remote.SSH.path`.

If a retry is needed, stderr shows a message such as:

```text
[ssh-initial-retry] server.example.org:22: initial connection failed (ConnectionResetError, code=10054); retry 2/3
```

OpenSSH keeps stdin/stdout for its protocol; diagnostics use stderr.

## Options

Append options after `%h %p` in `ProxyCommand`:

```text
... ssh_initial_retry.py %h %p --attempts 3 --timeout 4 --delay 0.3
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--attempts` | `3` | Total attempts, including the first |
| `--timeout` | `4` | Seconds allowed for each initial connection and identification exchange |
| `--delay` | `0.3` | Seconds between failed attempts |

Name resolution is controlled by the operating system; the timeout is not a
strict wall-clock bound on DNS lookup or trying multiple resolved addresses.
OpenSSH's `ConnectTimeout` and VS Code's connection timeout can end the overall
attempt earlier. Increase the helper timeout if your initial connection is
normally slow; allow enough time in the caller for the retry budget.

## Scope and limitations

- Retried: socket-level errors, closure and timeout **before server
  identification**. Retries are bounded; an unavailable server will still fail.
- Not retried: errors after server identification, including later key-exchange
  errors, host-key rejection, bad credentials or a disconnected active session.
- A generic `Connection reset` after login is outside this helper's scope.
- It replaces the host's transport `ProxyCommand`; do not overwrite an existing
  proxy command blindly. `ProxyJump` and `ProxyCommand` compete for the same
  host. For a bastion setup, put this helper on the **bastion's host entry** and
  keep `ProxyJump` on the internal destination.
- OpenSSH still verifies the host key using the destination hostname. As with
  other `ProxyCommand` transports, the separate `CheckHostIP` check is not
  available. Do not disable normal host-key verification.
- The helper is a local byte relay, not an external proxy service.

### Why not just retry the entire SSH command?

Retrying a whole process can replay a remote command whose execution status is
unknown. This helper stops retrying before authentication or commands can occur.
Session supervisors such as autossh address a broader, different lifecycle.

## Verification

Development testing confirmed an initial reset followed by an automatic
successful retry against a real SSH server on Windows. Other real-server
connections and a VS Code-style `-T -D` plus stdin-script transport also passed.
That transport test is **not an end-to-end test of the VS Code UI**.

Run the local mock-server suite from the repository root:

```sh
python -B -m unittest discover -s tests -v
```

Tests cover retry limits, connection resets/closure/timeouts, binary transport,
server preambles, and the no-retry boundary after identification. GitHub Actions
runs the suite on Windows, macOS and Linux with Python 3.10 and 3.13; see the
badge for actual results. The tests need no remote server or credentials.

## Disable / uninstall

Remove the `ProxyCommand` line you added, or restore the previous line if there
was one. New SSH connections then use the previous transport.

For one direct-connection check:

```sh
ssh -o ProxyCommand=none research-server
```

Use this only for a directly reachable host; it disables its configured proxy.

## Reporting a problem

Include OS, Python/OpenSSH versions, whether normal SSH also fails, and
sanitized logs around the first failure. Do not post passwords, private keys,
connection tokens, or your entire SSH config. Korean and English issues welcome.

## License

[MIT](LICENSE).

## References

- [OpenSSH ProxyCommand documentation](https://man.openbsd.org/ssh_config#ProxyCommand)
- [VS Code Remote-SSH documentation](https://code.visualstudio.com/docs/remote/ssh)
