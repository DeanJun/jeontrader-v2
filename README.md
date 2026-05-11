# JEONtrader

TradingView 알림 → ngrok → FastAPI → Upbit / 한국투자증권(KIS) 자동매매 + Telegram 알림

---

## 구조

```
TradingView 알림
    └── ngrok (터널)
            └── FastAPI 서버
                    ├── 코인 심볼 (BTCUSDT 등) → Upbit 매매
                    └── 주식 심볼 (005930 등)  → KIS 매매
                            └── Telegram 알림
```

---

## 사전 준비

### 1. Python 패키지 설치

```bash
pip install -r requirements.txt
```

---

### 2. ngrok 설치 및 인증

1. [https://ngrok.com](https://ngrok.com) 회원가입
2. [https://dashboard.ngrok.com/get-started/setup](https://dashboard.ngrok.com/get-started/setup) 에서 설치파일 다운로드
3. 인증토큰 발급 후 등록:
```bash
ngrok config add-authtoken <your_token>
```

---

### 3. Telegram 봇 생성

1. 텔레그램에서 **@BotFather** 검색
2. `/newbot` 입력 → 봇 이름 설정
3. 발급된 **Bot Token** 복사 → `.env`의 `TELEGRAM_BOT_TOKEN`에 입력

**내 텔레그램 Chat ID 확인:**

아래 URL을 브라우저에서 열고 봇에게 아무 메시지 보낸 뒤 접속:
```
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```
`"chat":{"id": 123456789}` 부분의 숫자가 Chat ID → `.env`의 `TELEGRAM_ALLOWED_CHAT_ID`에 입력

---

### 4. Upbit API 키 발급

1. [https://upbit.com](https://upbit.com) 로그인
2. **마이페이지 → Open API 관리** → API 키 발급
3. 허용 IP에 본인 IP 추가 (또는 전체 허용)
4. Access Key / Secret Key → `.env`에 입력

---

### 5. 한국투자증권 KIS API 키 발급

1. [https://apiportal.koreainvestment.com](https://apiportal.koreainvestment.com) 로그인
2. **앱 관리 → 실전투자** 앱 생성
3. App Key / App Secret / 계좌번호 → `.env`에 입력
4. KIS 안 쓸 경우 `KIS_MODE=paper` 로 두고 텔레그램에서 `/stop kis`

---

### 6. .env 설정

`.env_example`을 복사해서 `.env` 생성 후 값 입력:

```bash
cp .env_example .env
```

```env
KIS_MODE=real               # real | paper (KIS 안 쓰면 paper)

KIS_REAL_APP_KEY=
KIS_REAL_APP_SECRET=
KIS_REAL_ACCOUNT_NO=00000000-01

TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_ID=

UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=
```

---

## 실행

터미널 1 — 서버:
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

터미널 2 — ngrok:
```bash
ngrok http 8000
```

ngrok 실행 후 출력되는 `https://xxxx.ngrok-free.app` 주소를 TradingView Webhook URL로 사용.

---

## TradingView Webhook 설정

**URL:**
```
https://<ngrok주소>/webhook/tradingview
```

**Alert Message (JSON):**
```json
{"action":"buy","symbol":"{{ticker}}","price":"{{close}}","time":"{{timenow}}"}
{"action":"sell","symbol":"{{ticker}}","price":"{{close}}","time":"{{timenow}}"}
```

**심볼 규칙:**

| 심볼 예시 | 라우팅 |
|-----------|--------|
| BTCUSDT, ETHUSDT | Upbit |
| 005930, 006340 (숫자 6자리) | KIS 국내주식 |
| AAPL, TSLA + `"exchange":"NASD"` | KIS 해외주식 |

---

## Telegram 봇 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | Upbit + KIS 매매 시작 |
| `/start ubt` | Upbit만 시작 |
| `/start kis` | KIS만 시작 |
| `/stop` | Upbit + KIS 매매 중지 |
| `/stop ubt` | Upbit만 중지 |
| `/stop kis` | KIS만 중지 |
| `/status` | 현재 상태 (ON/OFF, 포지션) |
| `/balance` | Upbit 잔고 조회 |
| `/kisbalance` | KIS 잔고 조회 |
| `/help` | 명령어 목록 |
