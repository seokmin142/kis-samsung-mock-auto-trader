# KIS Samsung Mock Auto Trader

한국투자증권 Open API의 **모의투자 REST API만** 사용해 삼성전자(`005930`)를 조회하고 지정가 주문을 관리하는 교육용 프로젝트입니다. 웹소켓·실전투자 URL·실전 TR ID는 사용하지 않습니다.

> 이 코드는 투자 권유가 아니며 실제 자금 거래용이 아닙니다. 실행 전 반드시 모의투자 계좌와 새로 발급한 모의 앱 키인지 확인하세요.

## 핵심 동작

1. 한투 서버의 HTTP `Date` 헤더로 시계를 보정하고 모든 판단을 `Asia/Seoul` 기준으로 수행합니다.
2. 국내휴장일 API를 하루 한 번 확인하고 개장일(`opnd_yn=Y`)에만 진행합니다.
3. 09:10-15:30 KST 밖에서는 주문하지 않습니다.
4. 삼성전자 현재가와 계좌 잔고를 조회합니다.
5. 기본값으로 현재가 - 1,000원에 3주 매수 주문을 제출합니다.
6. 기존 주문 가능 수량이 3주 이상이면 현재가 + 1,000원에 매도 주문을 제출합니다. 보유수량이 없다면 매수 체결 후에만 매도를 제출합니다.
7. 주문 후 체결내역과 잔고를 함께 확인해 JSONL 기록을 남깁니다.
8. 한 매수·매도 사이클이 끝나면 다음 사이클을 계속 시작합니다. 미체결 주문이 있으면 새 주문을 만들지 않아 중복을 방지합니다.

현재 전략의 기본값은 3주, 현재가 기준 ±1,000원, 일일 사이클 제한 없음입니다. `.env`의 `ORDER_QUANTITY`, `PRICE_OFFSET_KRW`, `MAX_ORDER_PAIRS_PER_DAY`로 바꿀 수 있습니다.

## 폴더 구조

```text
.
├── main.py                         # CLI 진입점
├── samsung_trader/
│   ├── config.py                   # 환경변수·모의전용 안전 검증
│   ├── clock.py                    # KIS 서버 시각 기반 KST 보정
│   ├── auth.py                     # 당일 토큰 캐시
│   ├── api_client.py               # 요청 간격·재시도·오류 처리
│   ├── market_data.py              # 현재가·휴장일
│   ├── account.py                  # 잔고·당일 주문체결
│   ├── orders.py                   # 모의 지정가 주문
│   ├── trader.py                   # 거래창·중복방지·체결확인
│   └── persistence.py              # 비밀정보 제거 기록·재시작 상태
├── scripts/                        # 실행·Windows 예약·기록 게시 도구
├── tests/                          # 네트워크 없는 단위 테스트
├── records/                        # 제출 가능한 모의거래 JSONL
├── logs/                           # 로컬 상세 로그(Git 제외)
├── RUNBOOK_KR.md                   # 초보자용 실행 매뉴얼
├── SECURITY.md                     # 키 보안 지침
└── REFERENCES.md                   # 공식 API·수업 참고자료
```

## 빠른 시작

자세한 절차는 [RUNBOOK_KR.md](RUNBOOK_KR.md)를 따르세요.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python main.py --preflight --run-date 2026-06-19
python main.py --run-date 2026-06-19 --wait-for-open
python main.py --execute --run-date 2026-06-19 --wait-for-open
```

마지막 명령에만 모의 주문을 제출하는 `--execute`가 있습니다. 옵션이 없으면 주문 계획만 기록합니다.

## API 호출 절약 설계

| 구간 | 호출 정책 |
|---|---|
| 시계 | 시작 시 한투 호스트 `HEAD` 1회, 이후 최대 시간당 1회 |
| 토큰 | 유효기간과 KST 발급일을 확인해 당일 재사용 |
| 휴장일 | 실행일 1회만 확인 |
| 주문 전 | 당일 미체결 1회, 현재가 1회, 잔고 1회 |
| 주문 후 | 30초 뒤 체결 1회, 상태 변화 시에만 잔고 1회 |
| 모니터링 | 기본 10분 간격 체결조회, 상태가 바뀔 때만 잔고조회 |

GET은 일시적 네트워크 오류에 제한적으로 재시도합니다. POST 주문은 타임아웃 시 실제 접수 여부가 불명확하므로 자동 재시도하지 않습니다.

## 안전장치

- 모의 서버 URL을 코드 상수로 고정
- 모의 TR ID가 아닌 요청 거부
- `--execute` 명시 전 주문 금지
- 미체결 주문 감지 시 신규 주문 금지
- 하루 주문쌍 상한과 재시작 상태 저장
- 계좌번호·키·토큰·Authorization 기록 금지
- `.env`, 토큰 캐시, 로그를 `.gitignore`로 차단
- GitHub Actions에서는 단위 테스트만 실행하며 주문 코드는 실행하지 않음

## 거래 기록

실행 결과는 다음 파일에 JSON Lines 형식으로 저장됩니다.

```text
records/trading_YYYYMMDD.jsonl
```

모의거래 후 내용을 검토하고 다음 명령으로 기록만 추가할 수 있습니다.

```powershell
.\scripts\publish_record.ps1 -DateKst 20260619
```
