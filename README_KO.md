# CRYPTO AI SIGNAL — Bitget Futures

PC와 Android 휴대폰에서 같은 주소로 접속하는 반응형 웹 대시보드입니다.

## 포함 기능
- Bitget USDT 선물 공개시장 데이터 조회 (API 키 불필요)
- 거래대금 상위 코인 스캔, BTC/XRP 우선 포함
- 4시간봉·일봉·주봉 기술 분석
- RSI, MACD, EMA20/50, 거래량
- OI 및 펀딩비 표시(공개 API가 제공하는 경우)
- 롱/숏 관심 신호, 참고용 손절/목표 시나리오
- 클라우드 배포용 로그인 비밀번호 보호

## 클라우드 배포 (가장 쉬운 방법: Streamlit Community Cloud)
이 ZIP만으로 인터넷 공개 주소가 자동 생성되는 것은 아닙니다. 본인 GitHub와 Streamlit 계정으로 한 번 배포해야 합니다.

1. GitHub에 새 저장소를 만듭니다. 예: `crypto-ai-signal`
2. 이 압축파일을 풀고 `app.py`, `requirements.txt`, `.streamlit` 폴더를 저장소 루트에 올립니다.
   - `Dockerfile`은 Streamlit Community Cloud 배포에 필수는 아닙니다.
   - `.streamlit/secrets.toml.example`은 예시 파일이며 실제 비밀번호 파일로 올리지 마세요.
3. Streamlit Community Cloud에 GitHub 계정으로 로그인한 뒤 **Create app**을 선택합니다.
4. 저장소, 브랜치, `app.py`를 선택해 배포합니다.
5. 앱의 **Settings → Secrets**에 다음을 등록합니다. 실제 비밀번호로 바꾸세요.

```toml
APP_PASSWORD = "강력하고_고유한_비밀번호"
```

6. 배포가 끝나면 Streamlit이 제공하는 `https://...streamlit.app` 주소를 PC와 휴대폰에서 엽니다.
7. Android Chrome 메뉴에서 **홈 화면에 추가**를 선택하면 앱처럼 실행할 수 있습니다.

## PC/휴대폰 동시 사용
동일한 클라우드 URL로 접속하면 됩니다. PC가 꺼져 있어도 클라우드 앱은 호스팅 서비스가 실행 중인 동안 계속 동작합니다. 모바일 푸시 알림은 현재 포함되지 않았고, 화면 내 신호 알림만 제공합니다.

## 데이터 및 모델의 한계
- Bitget 공식 공개 API를 사용합니다. 시세·캔들/OI/펀딩 데이터의 실제 제공 여부는 API 응답 및 거래쌍에 따라 달라질 수 있습니다.
- 주봉은 일봉을 주간으로 재집계합니다.
- 0~100 방향성 지수는 지표 점수 환산치이며, 통계적으로 검증된 상승/하락 확률이 아닙니다.
- 현재 버전은 계정 연결, 주문 실행, 자동매매를 하지 않습니다. Bitget API 키/시크릿을 입력하지 마세요.
- 롱·숏 계정비율, 청산 데이터, 전략 백테스트, 텔레그램/푸시 알림은 다음 개발 단계입니다.
- 배포 후 실제 자금 투입 전에 모의 운용과 백테스트를 수행하세요.

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
