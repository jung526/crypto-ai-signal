
import time
import requests
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timezone

BASE = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
TIMEFRAMES = {"4시간": "4H", "일봉": "1D", "주봉": "1W"}
DEFAULT_SYMBOLS = ["BTCUSDT", "XRPUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
                   "DOGEUSDT", "ADAUSDT", "SUIUSDT", "LINKUSDT", "AVAXUSDT",
                   "LTCUSDT", "BCHUSDT", "TRXUSDT", "DOTUSDT", "AAVEUSDT"]

st.set_page_config(page_title="CRYPTO AI SIGNAL", page_icon="📈", layout="wide")

# Cloud safety: protect the dashboard with an app password.
# Set APP_PASSWORD in Streamlit Cloud -> App settings -> Secrets.
try:
    APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
except Exception:
    APP_PASSWORD = ""

if not APP_PASSWORD:
    st.error("앱 비밀번호가 아직 설정되지 않았습니다. 배포 설정의 Secrets에 APP_PASSWORD를 등록하세요.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 CRYPTO AI SIGNAL 로그인")
    entered = st.text_input("앱 비밀번호", type="password")
    if st.button("로그인", type="primary"):
        if entered == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


def api_get(path, params):
    r = requests.get(BASE + path, params=params, timeout=12)
    r.raise_for_status()
    j = r.json()
    if str(j.get("code", "00000")) != "00000":
        raise RuntimeError(j.get("msg", "Bitget API error"))
    return j.get("data")

@st.cache_data(ttl=25, show_spinner=False)
def get_tickers():
    data = api_get("/api/v3/market/tickers", {"category": CATEGORY})
    if isinstance(data, dict):
        data = data.get("list", [])
    return data or []

@st.cache_data(ttl=25, show_spinner=False)
def get_candles(symbol, interval, limit=240):
    # Weekly is assembled from daily candles because the documented v3 kline
    # intervals include 1D but do not list 1W.
    actual_interval = "1D" if interval == "1W" else interval
    data = api_get("/api/v3/market/candles", {
        "category": CATEGORY, "symbol": symbol,
        "interval": actual_interval, "limit": str(limit)
    })
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=["ts","open","high","low","close","volume","turnover"])
    for c in ["open","high","low","close","volume","turnover"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ts"] = pd.to_datetime(pd.to_numeric(df["ts"]), unit="ms", utc=True)
    df = df.dropna().sort_values("ts").set_index("ts")
    if interval == "1W":
        df = df.resample("W-SUN").agg({
            "open":"first", "high":"max", "low":"min",
            "close":"last", "volume":"sum", "turnover":"sum"
        }).dropna()
    return df

@st.cache_data(ttl=25, show_spinner=False)
def get_oi(symbol):
    try:
        d = api_get("/api/v3/market/open-interest", {"category": CATEGORY, "symbol": symbol})
        if isinstance(d, dict):
            rows = d.get("list", [])
            return float(rows[0]["openInterest"]) if rows else np.nan
    except Exception:
        pass
    return np.nan

@st.cache_data(ttl=25, show_spinner=False)
def get_funding(symbol):
    try:
        d = api_get("/api/v3/market/current-fund-rate", {"category": CATEGORY, "symbol": symbol})
        if isinstance(d, list) and d:
            return float(d[0].get("fundingRate", "nan")) * 100
    except Exception:
        pass
    return np.nan

def indicators(df):
    x = df.copy()
    close = x.close
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi"] = 100 - 100/(1+rs)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    x["macd"] = ema12 - ema26
    x["signal"] = x.macd.ewm(span=9, adjust=False).mean()
    x["ema20"] = close.ewm(span=20, adjust=False).mean()
    x["ema50"] = close.ewm(span=50, adjust=False).mean()
    x["ema200"] = close.ewm(span=200, adjust=False).mean()
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    x["bb_up"] = mid + 2*std
    x["bb_low"] = mid - 2*std
    x["vol_ma"] = x.volume.rolling(20).mean()
    return x

def score_frame(df):
    if len(df) < 60:
        return None
    x = indicators(df).dropna()
    if x.empty:
        return None
    r = x.iloc[-1]
    score, reasons = 0, []
    if r.close > r.ema20:
        score += 1; reasons.append("종가 > EMA20")
    else:
        score -= 1; reasons.append("종가 < EMA20")
    if r.ema20 > r.ema50:
        score += 1; reasons.append("EMA20 > EMA50")
    else:
        score -= 1; reasons.append("EMA20 < EMA50")
    if r.macd > r.signal:
        score += 1; reasons.append("MACD 골든 우위")
    else:
        score -= 1; reasons.append("MACD 데드 우위")
    if r.rsi >= 55:
        score += 1; reasons.append("RSI 강세")
    elif r.rsi <= 45:
        score -= 1; reasons.append("RSI 약세")
    if r.volume > r.vol_ma:
        reasons.append("거래량 20봉 평균 상회")
    # Score maps to a transparent technical-bias index, not a calibrated probability.
    bias = int(round(50 + score * 10))
    bias = max(10, min(90, bias))
    direction = "롱 우세" if score >= 2 else ("숏 우세" if score <= -2 else "중립")
    return {
        "price": float(r.close), "rsi": float(r.rsi),
        "score": score, "bias": bias, "direction": direction,
        "ema20": float(r.ema20), "ema50": float(r.ema50),
        "macd": float(r.macd), "signal": float(r.signal),
        "reasons": reasons, "high": float(x.high.tail(20).max()),
        "low": float(x.low.tail(20).min())
    }

def analyze(symbol, label):
    rows = []
    for tf_name, interval in TIMEFRAMES.items():
        df = get_candles(symbol, interval)
        result = score_frame(df)
        if result:
            rows.append((tf_name, result))
    if not rows:
        return None
    weights = {"4시간": 0.5, "일봉": 0.3, "주봉": 0.2}
    total = sum(v["score"] * weights[k] for k, v in rows)
    # Directional score is explicitly not a statistically validated probability.
    strength = int(round(max(0, min(100, 50 + total * 10))))
    if total >= 1.0:
        signal = "롱 관심"
    elif total <= -1.0:
        signal = "숏 관심"
    else:
        signal = "관망"
    oi, funding = get_oi(symbol), get_funding(symbol)
    latest = rows[0][1]
    # Illustrative levels based on recent 20-bar range and ATR-like proxy.
    stop_long = latest["price"] * 0.985
    target_long = latest["price"] * 1.025
    stop_short = latest["price"] * 1.015
    target_short = latest["price"] * 0.975
    return {
        "symbol": symbol, "name": label, "price": latest["price"],
        "signal": signal, "bias": strength, "oi": oi, "funding": funding,
        "timeframes": rows, "stop_long": stop_long, "target_long": target_long,
        "stop_short": stop_short, "target_short": target_short
    }

st.title("📈 CRYPTO AI SIGNAL")
st.caption("Bitget USDT 무기한 선물 · 4시간/일봉/주봉 기술적 분석 · 주문 실행 기능 없음")

with st.sidebar:
    st.header("설정")
    scan_top = st.slider("자동 스캔 종목 수", 5, 40, 15)
    custom = st.text_input("추가 심볼 (쉼표 구분)", "NEARUSDT, OPUSDT, SEIUSDT")
    refresh = st.button("🔄 데이터 새로고침", use_container_width=True)
    st.caption("데이터는 Bitget 공개 API에서 조회합니다. API 키 불필요.")
    if refresh:
        st.cache_data.clear()

try:
    tickers = get_tickers()
    valid = {x.get("symbol"): x for x in tickers if x.get("symbol")}
    # Prefer the liquid top symbols by quote turnover; always include BTC/XRP.
    ranked = sorted(
        [x for x in tickers if x.get("symbol","").endswith("USDT")],
        key=lambda x: float(x.get("turnover24h") or 0), reverse=True
    )
    chosen = ["BTCUSDT", "XRPUSDT"]
    for item in ranked:
        s = item["symbol"]
        if s not in chosen and len(chosen) < scan_top:
            chosen.append(s)
    extra = [s.strip().upper() for s in custom.split(",") if s.strip()]
    for s in extra:
        if s.endswith("USDT") and s not in chosen:
            chosen.append(s)
    st.caption(f"조회 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (한국 기기 시간)")
    st.info("상승/하락 수치는 백테스트로 검증된 확률이 아니라 지표 점수를 0~100으로 환산한 방향성 지수입니다.")
    results = []
    progress = st.progress(0)
    status = st.empty()
    for i, sym in enumerate(chosen):
        status.write(f"분석 중: {sym} ({i+1}/{len(chosen)})")
        try:
            res = analyze(sym, sym.replace("USDT",""))
            if res:
                results.append(res)
        except Exception as e:
            st.warning(f"{sym}: 데이터 조회 실패 ({e})")
        progress.progress((i+1)/len(chosen))
        time.sleep(0.06)
    progress.empty(); status.empty()

    if results:
        dfout = pd.DataFrame([{
            "코인": r["name"], "현재가": r["price"], "신호": r["signal"],
            "방향성 지수": r["bias"], "OI": r["oi"],
            "펀딩비(%)": r["funding"]
        } for r in results]).sort_values("방향성 지수", ascending=False)
        st.subheader("전체 스캔 결과")
        st.dataframe(dfout, use_container_width=True, hide_index=True)
        alerts = [r for r in results if r["signal"] != "관망"]
        st.subheader("🚨 진입 관심 알림")
        if alerts:
            for r in sorted(alerts, key=lambda z: abs(z["bias"]-50), reverse=True):
                color = "success" if r["signal"] == "롱 관심" else "error"
                st.markdown(f":{color}[**{r['name']} — {r['signal']} · 방향성 지수 {r['bias']}/100**]")
        else:
            st.write("현재 설정한 기준을 충족한 진입 관심 신호가 없습니다. 관망이 우선입니다.")

        st.subheader("종목별 상세 분석")
        names = [f'{r["name"]} ({r["symbol"]})' for r in results]
        selected = st.selectbox("분석할 코인", names)
        r = results[names.index(selected)]
        a,b,c,d = st.columns(4)
        a.metric("현재가", f'{r["price"]:,.6g}')
        b.metric("방향성 지수", f'{r["bias"]}/100')
        c.metric("OI", f'{r["oi"]:,.4g}' if np.isfinite(r["oi"]) else "데이터 없음")
        d.metric("펀딩비", f'{r["funding"]:.5f}%' if np.isfinite(r["funding"]) else "데이터 없음")
        detail = []
        for tf, x in r["timeframes"]:
            detail.append({
                "시간봉": tf, "방향": x["direction"], "방향성 지수": x["bias"],
                "RSI": round(x["rsi"],2), "EMA20": x["ema20"],
                "EMA50": x["ema50"], "MACD": x["macd"],
                "최근 20봉 고점": x["high"], "최근 20봉 저점": x["low"],
                "근거": ", ".join(x["reasons"])
            })
        st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)
        st.markdown("**참고용 가격 시나리오 (현재가 대비 고정 폭, 지지·저항 확정값 아님)**")
        p1,p2 = st.columns(2)
        p1.success(f"롱 관찰: 손절 참고 {r['stop_long']:,.6g} · 목표 참고 {r['target_long']:,.6g}")
        p2.error(f"숏 관찰: 손절 참고 {r['stop_short']:,.6g} · 목표 참고 {r['target_short']:,.6g}")
        st.caption("진입 알림은 화면 내 신호 목록입니다. 백그라운드 푸시/텔레그램 알림은 별도 설정이 필요합니다.")
    else:
        st.error("분석할 데이터가 없습니다. 잠시 후 새로고침하거나 Bitget API 상태를 확인하세요.")
except Exception as e:
    st.error(f"Bitget 데이터 연결 실패: {e}")
    st.write("네트워크에서 api.bitget.com 접속이 가능한지 확인하고 다시 실행하세요.")

st.divider()
st.caption("주의: 투자 조언이 아니며, 레버리지 선물은 원금 전액 손실 및 강제청산 위험이 있습니다. 신호만으로 진입하지 말고 별도 손절·포지션 크기 관리가 필요합니다.")
