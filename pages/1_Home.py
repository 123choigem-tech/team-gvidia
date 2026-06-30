import pandas as pd
import streamlit as st
from pathlib import Path
from utils.style import apply, card, section, hero
from utils.chat_widget import inject
from utils.alert_widget import inject_alerts
from agents.alert_agent import get_active_alerts
import config

st.set_page_config(page_title="Home", page_icon="🌊", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

# ── 데이터 로드 ───────────────────────────────────────────
@st.cache_data(ttl=300)
def load_stats():
    stats = {}
    news_path = Path("data/processed/disaster_db/disaster_events.csv")
    if news_path.exists():
        news_df = pd.read_csv(news_path, encoding="utf-8")
        stats["news_count"] = len(news_df)
        dates = pd.to_datetime(news_df["date"], errors="coerce").dropna()
        stats["news_period"] = (
            f"{dates.min().strftime('%Y.%m')} ~ {dates.max().strftime('%Y.%m')}"
            if not dates.empty else "2025.06 ~ 08"
        )
        stats["last_updated"] = (
            dates.max().strftime("%Y-%m-%d") if not dates.empty else None
        )
    else:
        stats["news_count"] = None
        stats["news_period"] = "2025.06 ~ 08"
        stats["last_updated"] = None

    sst_total, sst_regions, hot_regions = 0, 0, []
    for f in sorted(Path("data").glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in ("geocode", "regions", "Tongyeong"):
            continue
        try:
            df = pd.read_csv(f, encoding="utf-8")
            if "sst" in df.columns and df.get("source", pd.Series([""])).iloc[0] == "KHOA_OPeNDAP":
                sst_total += df["sst"].notna().sum()
                sst_regions += 1
                hot = df["sst"] >= 28.0
                cur = max_c = 0
                for v in hot:
                    cur = cur + 1 if v else 0
                    max_c = max(max_c, cur)
                if max_c >= 3:
                    hot_regions.append(region)
        except Exception:
            pass

    stats["sst_count"]   = sst_total if sst_total > 0 else None
    stats["sst_regions"] = sst_regions
    stats["hot_regions"] = hot_regions
    return stats

s = load_stats()

# ── Hero ──────────────────────────────────────────────────
hero(
    "🌊 고수온 연안재해 모니터링",
    "재난 뉴스에서 관심지역을 자동 탐지하고 · 위성 해수면온도를 수집·분석해 · 고수온 경보를 실시간으로 감지합니다",
)

# ── 현황 지표 ─────────────────────────────────────────────
section("현재 분석 현황", "📡")
c1, c2, c3, c4 = st.columns(4)
with c1:
    card(
        "수집된 재난 뉴스",
        f"{s['news_count']:,}건" if s["news_count"] else "—",
        s["news_period"],
        "📰",
    )
with c2:
    card(
        "수온 관측 건수",
        f"{s['sst_count']:,}건" if s["sst_count"] else "—",
        f"KHOA OPeNDAP · {s['sst_regions']}개 연안",
        "🌡️",
    )
with c3:
    card(
        "고수온 위험 지역",
        f"{len(s['hot_regions'])}곳" if s["hot_regions"] else "이상 없음",
        ", ".join(s["hot_regions"]) if s["hot_regions"] else "연속 3일 이상 기준",
        "⚠️",
    )
with c4:
    card(
        "마지막 업데이트",
        s["last_updated"] or "—",
        "뉴스 기준",
        "🕐",
    )

# ── 분석 업데이트 ─────────────────────────────────────────
section("분석 데이터 업데이트", "🔄")

st.markdown("""
<div class="ocean-card" style="padding:24px 28px;">
  <div style="font-size:14px;color:#c8e6f0;margin-bottom:4px;font-weight:600;">최신 뉴스를 수집하고 수온 분석을 업데이트합니다</div>
  <div style="font-size:12px;color:#4a7a8a;">수집된 데이터는 재난 지역 분석과 수온 현황 페이지에 즉시 반영됩니다.</div>
</div>
""", unsafe_allow_html=True)

with st.form("quick_pipeline"):
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        q_keywords = st.multiselect(
            "관심 재난 유형",
            ["고수온", "적조", "냉수"],
            default=["고수온"],
            key="q_kw",
            help="분석할 재난 유형을 선택하세요",
        )
        q_start = st.date_input("분석 시작일", value=pd.Timestamp("2025-06-01"), key="q_start").strftime("%Y-%m-%d")
        q_end   = st.date_input("분석 종료일", value=pd.Timestamp("2025-08-31"), key="q_end").strftime("%Y-%m-%d")
    with fc2:
        q_max = st.slider("뉴스 수집 범위", 10, 200, 50, step=10, key="q_max",
                          help="키워드당 최대 수집 기사 수")
        q_thr = st.slider("고수온 경보 기준 (℃)", 24.0, 32.0, 28.0, 0.5, key="q_thr")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    submitted = st.form_submit_button(
        "🔄  지금 업데이트", type="primary", use_container_width=True
    )

if submitted:
    prog = st.progress(0, text="뉴스 수집 중...")
    result_ph = st.empty()
    try:
        from src.news.crawler import run_pipeline as _crawl
        rep = _crawl(
            disaster_type="고수온",
            keywords=q_keywords,
            max_items=int(q_max),
            since=q_start,
            until=q_end,
        )
        prog.progress(40, text=f"뉴스 {rep.n_fetched}건 수집 완료 · 관심지역 {rep.n_located}곳 탐지")

        freq_csv = config.DATA_DIR / "results" / "frequency" / "region_frequency.csv"
        regions = []
        if freq_csv.exists():
            freq_df = pd.read_csv(freq_csv, encoding="utf-8")
            regions = freq_df.dropna(subset=["lat", "lon"]).to_dict("records")

        prog.progress(50, text=f"수온 데이터 수집 중... ({len(regions)}개 지역)")
        from agents.collection_agent import run as _collect
        col_results = _collect(regions, q_start, q_end)
        ok_n = sum(1 for r in col_results if r.get("success"))
        prog.progress(85, text=f"수온 수집 완료 · {ok_n}/{len(col_results)}개 지역")

        from agents.alert_agent import get_active_alerts as _alerts
        alerts = _alerts(threshold=q_thr)
        alarm_n    = sum(1 for a in alerts if a["level"] == "alarm")
        advisory_n = sum(1 for a in alerts if a["level"] == "advisory")
        prog.progress(100, text="완료")

        result_ph.markdown(f"""
<div class="ocean-card" style="border-color:rgba(0,168,150,0.4);padding:18px 24px;">
  <div style="font-size:13px;font-weight:700;color:#00a896;margin-bottom:10px;">✅ 업데이트 완료</div>
  <div style="display:flex;gap:32px;flex-wrap:wrap;">
    <div><span style="color:#4a7a8a;font-size:11px;">수집 뉴스</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{rep.n_fetched}건</span></div>
    <div><span style="color:#4a7a8a;font-size:11px;">관심지역</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{rep.n_located}곳</span></div>
    <div><span style="color:#4a7a8a;font-size:11px;">수온 수집</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{ok_n}개 지역</span></div>
    <div><span style="color:#4a7a8a;font-size:11px;">경보 현황</span><br><span style="color:#ff6b35;font-weight:700;font-size:18px;">경보 {alarm_n} · 주의보 {advisory_n}</span></div>
  </div>
  <div style="margin-top:12px;font-size:11px;color:#4a7a8a;">왼쪽 메뉴에서 📰 재난 지역 분석 · 🌡️ 수온 현황을 확인하세요.</div>
</div>
""", unsafe_allow_html=True)
        st.cache_data.clear()

    except Exception as e:
        prog.empty()
        result_ph.error(f"업데이트 중 오류가 발생했습니다: {e}")

# ── 서비스 안내 ───────────────────────────────────────────
section("무엇을 분석하나요?", "🔍")
fc1, fc2, fc3 = st.columns(3)

with fc1:
    st.markdown("""
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">📰</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">재난 뉴스 수집</div>
  <div style="font-size:12px;color:#4a7a8a;line-height:1.6;">
    네이버·공공데이터 뉴스에서<br>
    고수온·적조 관련 기사를 자동 수집하고<br>
    관심 연안 지역을 탐지합니다.
  </div>
</div>
""", unsafe_allow_html=True)

with fc2:
    st.markdown("""
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">🛰️</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">위성 수온 분석</div>
  <div style="font-size:12px;color:#4a7a8a;line-height:1.6;">
    국가해양위성센터(KOSC) API로<br>
    관심지역 해수면온도(SST)를 수집해<br>
    고수온 패턴을 분석합니다.
  </div>
</div>
""", unsafe_allow_html=True)

with fc3:
    st.markdown("""
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">⚠️</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">경보 자동 감지</div>
  <div style="font-size:12px;color:#4a7a8a;line-height:1.6;">
    28°C 이상 연속 3일↑ 경보,<br>
    누적 2일↑ 주의보를 자동 판단하고<br>
    보고서를 생성합니다.
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(
    "<div style='margin-top:8px;font-size:11px;color:#2a5a6a;text-align:center;'>"
    "경보 기준: SST 28°C 이상 / 연속 3일 이상 · 주의보 기준: 누적 2일 이상"
    "</div>",
    unsafe_allow_html=True,
)
