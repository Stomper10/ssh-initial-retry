# ssh-initial-retry

[English](README.md) | **한국어**

[![Tests](https://github.com/Stomper10/ssh-initial-retry/actions/workflows/tests.yml/badge.svg)](https://github.com/Stomper10/ssh-initial-retry/actions/workflows/tests.yml)

**SSH가 처음에는 실패하고 다시 접속하면 되나요? 초기 재시도를 자동화합니다.**

OpenSSH의 `ProxyCommand`에 연결하는 작은 Python 도우미입니다.
**서버의 SSH 식별 정보를 받기 전까지만** 연결 실패를 재시도하고,
그 이후에는 통신을 그대로 전달합니다. Python 표준 라이브러리만 사용하며
서버 설정을 변경할 필요가 없습니다.

## 어떤 불편을 해결하나요?

터미널이나 VS Code Remote-SSH에서 처음 접속하면 다음 오류가 발생하지만,
다시 시도하면 접속되는 경우가 있습니다.

```text
kex_exchange_identification: read: Connection reset
Connection reset by <server> port <port>
```

이 도우미는 TCP 연결 또는 SSH 초기 식별 정보 교환 단계에서 실패했을 때
수동으로 하던 재시도를 자동으로 수행합니다.

특정 실패 단계에 대한 대응 도구이며 **모든 SSH 오류를 해결하지는 않습니다.**
연결이 끊기는 원인을 진단하거나 인증·접근 제어를 우회하는 도구가 아닙니다.
특정 기관이나 네트워크 정책이 원인이라고 가정하지 않습니다.

## 동작 원리

```text
OpenSSH / VS Code Remote-SSH
  → 로컬 Python 도우미
      → 연결 후 SSH 클라이언트 식별 정보 전송
          → 연결 초기화 / 종료 / 시간 초과? 정해진 횟수까지 재시도
          → 서버 식별 정보 수신?
              이후 데이터만 전달하며 이 세션을 다시 연결하지 않음
```

호스트 키 검증, 인증, 암호화는 기존 SSH 클라이언트가 수행합니다.
재전송하는 것은 클라이언트의 공개된 프로토콜 식별 정보 한 줄뿐입니다.
인증 정보, 원격 명령, 터미널 입력, 파일 전송 데이터를 재실행하지 않으며,
인증 정보나 통신 내용을 저장하지 않습니다.

## 빠른 시작

OpenSSH와 **Python 3.10 이상**이 필요합니다. `pip install`은 필요 없습니다.

일반 프로젝트 폴더에 이 저장소를 복제하세요.
**기존 `.ssh` 폴더 자체를 Git 저장소로 만들거나 공개하지 마세요.**

```sh
git clone https://github.com/Stomper10/ssh-initial-retry.git
```

### Windows

PowerShell에서 Python 실행 파일의 경로를 확인합니다.

```powershell
python -c "import sys; print(sys.executable)"
```

`%USERPROFILE%\.ssh\config`에서 적용할 기존 호스트에 `ProxyCommand`를
추가합니다. 아래 두 예시 경로를 실제 절대 경로로 바꾸세요.
슬래시(`/`)를 사용하고, 공백이 있는 경로는 따옴표로 감쌉니다.

```sshconfig
Host research-server
    HostName server.example.org
    User your-user
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ProxyCommand "C:/path/to/python.exe" -I -u "C:/path/to/ssh-initial-retry/ssh_initial_retry.py" %h %p
```

서버 주소, 사용자명, 포트, 키는 기존 값을 유지합니다.
새로 필요한 것은 `ProxyCommand` 한 줄입니다. 설정 후에는 스크립트를 해당
경로에 계속 보관해야 합니다.

### macOS / Linux

`command -v python3`로 Python 위치를 확인한 뒤 절대 경로를 사용합니다.

```sshconfig
Host research-server
    HostName server.example.org
    User your-user
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ProxyCommand /absolute/path/to/python3 -I -u /absolute/path/to/ssh_initial_retry.py %h %p
```

같은 구현을 여러 운영체제의 자동 테스트에서 검사합니다.
로컬 모의 테스트만으로 모든 운영체제의 실제 서버 호환성이 검증되는 것은 아닙니다.

### 평소처럼 접속

```sh
ssh research-server
```

VS Code에서는 **Remote-SSH: Connect to Host...**에서 같은 호스트를 선택합니다.
확장 프로그램이 수정한 SSH config를 읽어야 합니다.
이 도우미를 위해 `remote.SSH.path`를 바꿀 필요는 없습니다.

재시도가 필요하면 표준 오류(stderr)에 다음과 같은 메시지가 표시됩니다.

```text
[ssh-initial-retry] server.example.org:22: initial connection failed (ConnectionResetError, code=10054); retry 2/3
```

SSH 프로토콜은 표준입출력을 사용하고, 진단 메시지는 표준 오류로 분리됩니다.

## 옵션

`ProxyCommand`의 `%h %p` 뒤에 옵션을 추가할 수 있습니다.

```text
... ssh_initial_retry.py %h %p --attempts 3 --timeout 4 --delay 0.3
```

| 옵션 | 기본값 | 의미 |
| --- | --- | --- |
| `--attempts` | `3` | 첫 시도를 포함한 총 시도 횟수 |
| `--timeout` | `4` | 시도별 초기 연결 및 식별 정보 교환 제한 시간(초) |
| `--delay` | `0.3` | 실패 후 다음 시도까지 대기 시간(초) |

이름 해석은 운영체제가 처리합니다. DNS 조회나 여러 IP 주소의 연결 시도를
포함한 전체 시간이 이 제한 안에 끝난다는 보장은 없습니다.
OpenSSH의 `ConnectTimeout`이나 VS Code의 연결 제한 시간이 더 먼저 종료시킬
수도 있습니다. 원래 초기 연결이 느린 환경에서는 도우미의 제한 시간을 늘리고,
호출하는 쪽에도 재시도에 필요한 시간을 허용하세요.

## 적용 범위와 한계

- **서버 식별 정보 수신 전** 소켓 오류, 연결 종료, 시간 초과를 정해진 횟수까지
  재시도합니다. 서버가 계속 응답하지 않으면 최종적으로 실패합니다.
- 식별 정보 수신 이후의 키 교환 오류, 호스트 키 거절, 잘못된 인증 정보,
  사용 중인 세션의 연결 끊김은 재시도하지 않습니다.
- 로그인 후 발생하는 일반적인 `Connection reset`은 이 도구의 범위가 아닙니다.
- 해당 호스트의 전송용 `ProxyCommand`를 대체합니다. 기존 프록시 명령을 무작정
  덮어쓰면 안 됩니다. 동일 호스트에서 `ProxyJump`와 `ProxyCommand`는 경합합니다.
  점프 서버를 거친다면 **점프 서버의 호스트 항목에** 도우미를 적용하고,
  내부 목적지의 `ProxyJump`는 유지하세요.
- SSH의 목적지 호스트명 기반 호스트 키 검증은 유지됩니다. 다른
  `ProxyCommand` 연결과 마찬가지로 별도 IP 검사인 `CheckHostIP`는 사용할 수
  없습니다. 일반 호스트 키 검증은 끄지 마세요.
- 로컬에서 데이터를 전달하는 프로그램이며 외부 프록시 서비스를 사용하지 않습니다.

### SSH 명령 전체를 반복하면 안 되나요?

명령 전체를 다시 실행하면 이전 명령이 서버에서 실행됐는지 모르는 상태에서
같은 명령을 중복 실행할 수 있습니다. 이 도우미는 인증이나 원격 명령 실행이
가능해지기 전에 재시도를 종료합니다.
autossh 같은 세션 관리 도구는 더 넓은 범위의 연결 수명 관리를 다룹니다.

## 검증

개발 중 Windows에서 실제 SSH 서버의 첫 연결 실패를 자동 재시도로 복구했습니다.
다른 실제 서버 접속과 VS Code 방식의 `-T -D` 및 표준입력 스크립트 전달도
확인했습니다. 이 전송 테스트는 **VS Code 화면까지 포함한 종단 간 테스트는
아닙니다.**

저장소 루트에서 로컬 모의 서버 테스트를 실행합니다.

```sh
python -B -m unittest discover -s tests -v
```

테스트는 최대 시도 횟수, 연결 초기화·종료·시간 초과, 바이너리 전달,
서버 안내문, 식별 정보 수신 이후 재시도 금지를 검사합니다.
GitHub Actions는 Windows·macOS·Linux와 Python 3.10·3.13 조합에서 실행합니다.
실제 결과는 상단 배지를 확인하세요. 원격 서버나 인증 정보는 필요 없습니다.

## 비활성화 / 제거

추가한 `ProxyCommand` 줄을 제거하거나, 기존 프록시 설정이 있었다면 해당
줄을 복원하세요. 새 SSH 연결부터 기존 전송 방식을 사용합니다.

한 번만 직접 접속을 비교하려면 다음과 같이 실행합니다.

```sh
ssh -o ProxyCommand=none research-server
```

설정된 프록시를 끄는 명령이므로 직접 접근 가능한 호스트에만 사용하세요.

## 문제 제보

운영체제, Python/OpenSSH 버전, 일반 SSH에서도 발생하는지 여부,
첫 실패 주변의 비식별화한 로그를 알려주세요.
비밀번호, 개인키, 연결 토큰, 전체 SSH config는 올리지 마세요.
한국어와 영어 이슈 모두 환영합니다.

## 라이선스

[MIT](LICENSE).

## 참고 문서

- [OpenSSH ProxyCommand 문서](https://man.openbsd.org/ssh_config#ProxyCommand)
- [VS Code Remote-SSH 문서](https://code.visualstudio.com/docs/remote/ssh)
