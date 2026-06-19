# 실행 매뉴얼 (한국시간 기준)

이 문서는 2026-06-19 장에서 모의거래 기록을 만드는 절차를 처음부터 설명합니다.

## 0. 먼저 해야 하는 보안 조치

채팅에 입력한 기존 앱 키와 앱 시크릿은 노출된 것으로 간주해야 합니다. 한국투자증권 개발자 포털에서 기존 키를 폐기하고 **모의투자용 키를 새로 발급**하세요. 기존 값을 이 저장소나 `.env`에 재사용하지 마세요.

계좌번호·키·시크릿은 GitHub Issue, README, 코드, 커밋 메시지에 적지 않습니다.

## 1. 준비 사항

- Python 3.11 이상
- 한국투자증권 모의투자 계좌
- 새 모의 앱 키와 앱 시크릿
- 2026-06-19 09:05-15:30 동안 켜져 있고 인터넷에 연결된 PC

GitHub Codespaces는 유휴 상태에서 중지될 수 있어 장시간 무인 실행에는 권장하지 않습니다. 로컬 VS Code 터미널이나 켜진 Windows PC가 더 안정적입니다.

## 2. 설치

저장소 폴더의 PowerShell에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

`.env`에는 새 모의투자 값만 입력합니다.

```dotenv
GH_ACCOUNT=계좌앞8자리-계좌뒤2자리
GH_APPKEY=새_모의_AppKey
GH_APPSECRET=새_모의_AppSecret
```

저장 후 메모장을 닫습니다. `.env`는 Git에서 자동 제외됩니다.

### Codespaces를 쓰는 경우

[GitHub Codespaces secrets](https://github.com/settings/codespaces)에 `GH_ACCOUNT`, `GH_APPKEY`, `GH_APPSECRET` 세 개를 만들고 이 저장소 접근을 허용합니다. Codespace를 다시 시작한 뒤 다음 명령으로 **값이 아닌 존재 여부만** 확인합니다.

```bash
python -c "import os; print({k: bool(os.getenv(k)) for k in ('GH_ACCOUNT','GH_APPKEY','GH_APPSECRET')})"
```

## 3. 오늘 사전 점검

주문 없이 서버 시각, 토큰, 2026-06-19 개장일, 현재가, 잔고를 확인합니다.

```powershell
python main.py --preflight --run-date 2026-06-19
```

정상 로그 예시:

```text
KIS server clock synchronized
preflight OK | target=2026-06-19 open_day=True ...
```

`open_day=False`이면 주문 실행을 예약하지 마세요. 키나 계좌 오류가 나오면 한투 포털의 모의투자 앱과 계좌번호를 다시 확인합니다.

## 4. 주문 없는 예행연습

```powershell
python main.py --run-date 2026-06-19 --wait-for-open
```

09:10 이전이면 서버 보정 KST로 기다린 뒤 매수·매도 예정가격만 기록하고 종료합니다. 주문은 제출하지 않습니다.

## 5. 내일 모의주문 실행 명령

2026-06-19 09:05 전후에 아래 명령을 실행합니다.

```powershell
python main.py --execute --run-date 2026-06-19 --wait-for-open
```

- 정확한 판단 기준은 PC 표시 시각이 아니라 한투 서버로 보정한 `Asia/Seoul` 시각입니다.
- 09:10 전에는 기다리고, 15:30 이후에는 새 주문을 내지 않고 종료합니다.
- 중단하려면 `Ctrl+C`를 한 번 누릅니다.
- 노트북 절전·재부팅·인터넷 단절 시 실행이 멈출 수 있습니다.

## 6. Windows 예약 실행 (선택)

사전 점검이 성공한 뒤에만 등록하세요. 관리자 PowerShell은 필요하지 않습니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\register_windows_task.ps1 -RunDate 2026-06-19 -Execute
```

이 스크립트는 `09:05 KST`를 Windows 로컬 시각으로 변환해 작업 스케줄러에 등록합니다. PC가 켜져 있고 사용자가 로그인한 상태여야 합니다. 예약 확인:

```powershell
Get-ScheduledTask -TaskName "KIS-Samsung-Mock-20260619"
```

예약 취소:

```powershell
Unregister-ScheduledTask -TaskName "KIS-Samsung-Mock-20260619" -Confirm:$false
```

## 7. 거래 기록 확인과 GitHub 게시

장중 로그:

```text
logs/trader_20260619.log
```

제출용 기록:

```text
records/trading_20260619.jsonl
```

기록에 앱 키·시크릿·계좌번호가 없는지 눈으로 확인한 뒤 실행합니다.

```powershell
.\scripts\publish_record.ps1 -DateKst 20260619
```

이 명령은 해당 기록만 커밋하고 현재 GitHub 저장소로 푸시합니다.

## 8. 예상되는 주문 동작

- 삼성전자 주문 가능 수량이 3주 이상: 매수 지정가와 매도 지정가를 각각 제출합니다.
- 보유수량이 0주: 매수를 먼저 제출하고 실제 체결로 주문가능수량이 생긴 후에만 매도를 제출합니다.
- 현재가보다 1,000원 낮은 3주 매수는 장중 체결되지 않을 수 있습니다. 그 경우 기록에는 `remaining_quantity`가 남습니다.
- 매수·매도 한 쌍이 모두 끝난 뒤에만 다음 사이클을 시작하므로 활성 주문은 중복되지 않습니다.
- `MAX_ORDER_PAIRS_PER_DAY=0`은 장중 사이클 횟수를 제한하지 않는다는 뜻입니다.
- 주문 응답 타임아웃은 중복 주문 방지를 위해 자동 재시도하지 않습니다.

## 9. 자주 생기는 오류

| 증상 | 확인할 것 |
|---|---|
| Missing environment variables | `.env` 이름과 세 변수 확인 |
| token request failed | 새 키가 모의투자용인지 확인 |
| open_day=False | 휴장일이므로 실행 중지 |
| insufficient mock cash | 모의계좌 예수금 확인 |
| existing open order detected | 한투 앱에서 미체결 주문 확인 |
| `EGW00201` | 호출 제한; 간격을 줄이지 말고 더 늘리기 |
