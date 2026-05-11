# JEONtrader v2

TradingView 알림 → FastAPI → 한국투자증권(KIS) 자동매매 + Telegram 알림  
멀티유저 SaaS 구조 — 초대코드 기반 가입, 유저별 독립 KIS 키 & 텔레그램 연동

---

## 구조

```
TradingView Alert
    └── POST /webhook/{user_id}
            └── FastAPI (Naver Cloud, jeontrader.kro.kr)
                    ├── PostgreSQL (유저 정보 / 주문 내역)
                    ├── KIS REST API (유저별 독립 인스턴스)
                    └── Telegram Bot (알림 / 명령어)
```

---

## 온보딩 플로우

```
초대코드 입력 → 회원가입 → KIS API 설정 → 텔레그램 연동 → 대시보드
```

1. `/invite` — 초대코드 확인
2. `/register` — 이메일 / 비밀번호 가입
3. `/kis-setup` — KIS App Key / Secret / 계좌번호 입력
4. `/telegram-link` — 봇에 6자리 코드 전송 (`/start 123456`)
5. `/dashboard` — KIS ON/OFF, 분할매수 설정, Webhook URL 확인

---

## TradingView Webhook

**URL (유저별 고유):**
```
https://jeontrader.kro.kr/webhook/{user_id}
```
> `user_id`는 대시보드에서 확인

**Alert Message (JSON):**
```json
{"action":"buy","symbol":"{{ticker}}","price":"{{close}}","time":"{{timenow}}"}
{"action":"sell","symbol":"{{ticker}}","price":"{{close}}","time":"{{timenow}}"}
```

---

## Telegram 봇 명령어

| 명령어 | 설명 |
|--------|------|
| `/start CODE` | 텔레그램 계정 연동 (코드는 웹에서 확인) |
| `/start kis` | KIS 매매 시작 |
| `/stop kis` | KIS 매매 중지 |
| `/status` | 현재 상태 (ON/OFF, 포지션, 분할횟수) |
| `/kisbalance` | KIS 잔고 조회 |
| `/split 1\|2\|4` | 분할매수 횟수 설정 |
| `/help` | 명령어 목록 |

---

## 로컬 개발 환경

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. `.env` 설정

```env
DATABASE_URL=postgresql+asyncpg://jeontrader:PASSWORD@localhost:5432/jeontrader
TELEGRAM_BOT_TOKEN=
INVITE_CODE=dnt1!
SECRET_KEY=change-me-in-production
```

### 3. DB 마이그레이션

```bash
alembic upgrade head
```

### 4. 서버 실행

```bash
uvicorn app.server:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

---

## 서버 배포 (Naver Cloud)

- **OS:** Ubuntu 22.04
- **스펙:** vCPU 2 / RAM 8GB / SSD 40GB
- **도메인:** jeontrader.kro.kr (SSL — Let's Encrypt 자동갱신)
- **프로세스:** systemd (`jeontrader.service`)
- **리버스 프록시:** nginx (443/80 → 8000)

```bash
# 서비스 관리
systemctl start jeontrader
systemctl stop jeontrader
systemctl restart jeontrader
systemctl status jeontrader

# 로그 확인
journalctl -u jeontrader -f
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI + Jinja2 |
| DB | PostgreSQL + SQLAlchemy async + Alembic |
| 인증 | bcrypt + itsdangerous (서명 쿠키) |
| 텔레그램 | python-telegram-bot |
| KIS API | 한국투자증권 REST API |
| 배포 | nginx + systemd + certbot |
