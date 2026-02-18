# 서버 설정 가이드

이 문서는 서버에 Lyra를 배포할 때 필요한 필수 단계만 정리한 안내서입니다.

## 1) `.env` 준비

```bash
cp .env.sample .env
```

필수 값을 설정하세요:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=CHANGE_THIS_DB_PASSWORD
POSTGRES_DB=lyra

DATABASE_URL=postgresql+asyncpg://postgres:CHANGE_THIS_DB_PASSWORD@db/lyra
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

APP_SECRET_KEY=REPLACE_WITH_VALID_FERNET_KEY
ALLOW_ORIGINS=http://YOUR_SERVER_IP,https://YOUR_DOMAIN
SSH_HOST_KEY_POLICY=reject
SSH_KNOWN_HOSTS_PATH=/root/.ssh/known_hosts
```

주의:
- `APP_SECRET_KEY`는 유효한 Fernet 키여야 합니다.
- `ALLOW_ORIGINS`는 Lyra 접속에 사용하는 브라우저 Origin과 정확히 일치해야 합니다.
- `POSTGRES_PASSWORD`와 `DATABASE_URL` 비밀번호는 반드시 동일해야 합니다.
- `APP_SECRET_KEY` 생성:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `SSH_HOST_KEY_POLICY` 허용값:
  - `reject` (권장)
  - `accept-new`

## 2) 서비스 실행

CPU 환경:

```bash
docker compose up -d --build
```

GPU 환경:

```bash
docker compose -f docker-compose.gpu.yml up -d --build
```

## 3) 배포 확인

```bash
docker compose ps
```

## 4) SSH 신뢰 초기화 (`SSH_HOST_KEY_POLICY=reject`인 경우 필수)

백엔드 컨테이너에 호스트 키를 등록합니다:

```bash
docker compose exec backend sh -lc 'mkdir -p /root/.ssh && ssh-keyscan -H <SSH_HOST> >> /root/.ssh/known_hosts'
```

예시:

```bash
docker compose exec backend sh -lc 'mkdir -p /root/.ssh && ssh-keyscan -H host.docker.internal >> /root/.ssh/known_hosts'
```

선택 사항: 지문 고정(fingerprint pinning)
1. 지문 확인:
```bash
ssh-keyscan <SSH_HOST> | ssh-keygen -lf -
```
2. SHA256 지문을 설정 키 `ssh_host_fingerprint`에 저장 (예: `SHA256:...`).

## 5) 호스트에 `tmux` 설치 (권장)

Lyra 터미널 탭은 SSH 대상 호스트에 `tmux`가 있을 때 탭별 셸 컨텍스트를 복구할 수 있습니다.

`tmux`가 없어도 터미널은 동작하지만, 새로고침/재접속 후 세션 유지 기능은 비활성화됩니다.

호스트 OS별 설치:

```bash
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y tmux

# RHEL/CentOS/Fedora
sudo dnf install -y tmux || sudo yum install -y tmux

# Alpine
sudo apk add --no-cache tmux
```

## 6) 호스트 경로 탐색 사전 조건 (프로비저닝 볼륨 마운트)

프로비저닝에서 `Browse`로 호스트 경로를 선택하기 전에:

- `설정 > Host Server Connection`에서 SSH를 구성:
  - `ssh_host`, `ssh_port`, `ssh_username`, `ssh_auth_method`
  - 비밀번호 인증이면 `ssh_password`도 필요
- 신뢰 정책 일치:
  - `SSH_HOST_KEY_POLICY=reject`인 경우 `SSH_KNOWN_HOSTS_PATH`에 신뢰된 키가 있거나 지문이 설정되어 있어야 함

UI에서 표시되는 실패 유형:
- 설정/연결: 설정 누락, 인증 실패, 호스트 키 검증 실패, 연결 검증 실패
- 경로: 권한 거부, 경로 없음, 탐색 실패

성능 참고:
- 호스트 파일시스템 탐색 API는 요청당 최대 500개 항목만 반환합니다.
- 디렉터리 항목이 제한을 넘으면 UI에 부분 표시(`truncated`) 안내가 표시됩니다.

## 7) 빠른 QA (호스트 경로 탐색)

- [ ] SSH 설정 없음 -> 인라인 경고 + 설정 이동 버튼 표시
- [ ] SSH 설정 정상 -> 탐색 모달 열림, 디렉터리 선택 시 호스트 경로 입력 반영
- [ ] 권한 없는 경로 -> 인라인 경로 오류 표시
- [ ] 존재하지 않는 경로 -> 인라인 경로 오류 표시
- [ ] 큰 디렉터리 -> truncated 안내 표시

## 8) 워커 노드 배포 (별도 서버)

메인 Lyra 인스턴스에서 추가 워커 서버를 등록하려는 경우 사용합니다.

1. env 준비:
```bash
cp .env.sample .env
```

2. 워커 필수 env 값:
```env
LYRA_NODE_ROLE=worker
```

DB/Redis/app 관련 값은 1번 섹션과 동일하게 설정하세요.
워커 백엔드는 시작 시 API 토큰을 생성하고 Docker named volume `worker_runtime_data`에 저장하며, 로그에 평문으로 출력합니다.
권장:
- `APP_SECRET_KEY`는 메인 호스트와 동일하게 사용하세요.
- `ALLOW_ORIGINS`도 메인 호스트와 동일한 값으로 맞추세요.

3. 워커 스택 실행 (프론트 제외):
```bash
docker compose -f docker-compose.worker.yml up -d --build
```

GPU 워커 서버:
```bash
docker compose -f docker-compose.worker.gpu.yml up -d --build
```

4. 워커 서버에서 API 헬스 체크:
```bash
curl -H "Authorization: Bearer <TOKEN_FROM_LOG>" http://127.0.0.1:8000/api/worker/health
```

워커 토큰 확인:
```bash
docker compose -f docker-compose.worker.yml logs backend | rg "Token:"
```

`rg`가 없는 환경에서는:
```bash
docker compose -f docker-compose.worker.yml logs backend | grep "Token:"
```

정상 응답:
```json
{"status":"ok","role":"worker"}
```

5. 메인 Lyra에서 워커 등록:
- `Settings > Worker Servers` 이동
- 아래 값 입력:
  - Worker name
  - Worker base URL (예: `http://10.0.0.25:8000`)
  - 동일한 워커 API 토큰 (`TOKEN_FROM_LOG`)
- UI에서 헬스 체크 실행

참고:
- 워커 서버는 메인 Lyra 백엔드에서 네트워크로 접근 가능해야 합니다.
- 워커가 unreachable이면 대시보드에서 해당 환경은 `Error`로 표시되며 `?`에서 워커 사유를 확인할 수 있습니다.
- 토큰을 의도적으로 교체하려면 `worker_runtime_data`를 제거하고 워커 백엔드를 재시작한 뒤, 메인 서버에 토큰을 다시 업데이트하세요.
