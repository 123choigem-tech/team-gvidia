from pathlib import Path

import pandas as pd
import streamlit as st

from agents.alert_agent import get_active_alerts
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply, card, hero, section


st.set_page_config(page_title="Home", page_icon="🌊", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())


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
            if not dates.empty
            else "2025.06 ~ 08"
        )
        stats["last_updated"] = dates.max().strftime("%Y-%m-%d") if not dates.empty else None
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

    stats["sst_count"] = sst_total if sst_total > 0 else None
    stats["sst_regions"] = sst_regions
    stats["hot_regions"] = hot_regions
    return stats


s = load_stats()
news_count = f"{s['news_count']:,}건" if s["news_count"] else "없음"
sst_count = f"{s['sst_count']:,}건" if s["sst_count"] else "없음"
hot_count = f"{len(s['hot_regions'])}개" if s["hot_regions"] else "없음"
last_updated = s["last_updated"] or "미확인"


hero(
    "고수온 연안재해 AI·AX 대시보드",
    "관심지역 수집, 고수온 분석, 보고서 생성을 한 화면에서 연결하는 운영 대시보드입니다.",
)

section("현재 상태", "📊")
left, right = st.columns([1.15, 0.85])
with left:
    c1, c2 = st.columns(2)
    with c1:
        card("수집된 뉴스", news_count, s["news_period"], "📰")
    with c2:
        card("수집된 수온", sst_count, f"KHOA OPeNDAP · {s['sst_regions']}개 지역", "🌡️")
    c3, c4 = st.columns(2)
    with c3:
        card("고수온 위험 지역", hot_count, ", ".join(s["hot_regions"]) if s["hot_regions"] else "연속 3일 이상 지역", "⚠️")
    with c4:
        card("최신 갱신", last_updated, "분석 데이터 기준", "🕒")
with right:
    st.markdown(
        """
<div class="ocean-card" style="height:100%;">
  <div style="font-size:13px;color:#7aacbf;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px;">운영 개요</div>
  <div style="font-size:20px;font-weight:800;color:#00e5ff;margin-bottom:12px;">한눈에 보는 진행 흐름</div>
  <div style="display:grid;gap:14px;">
    <div style="padding:14px 16px;border-radius:14px;background:rgba(0,194,212,0.06);border:1px solid rgba(0,194,212,0.12);">
      <div style="font-weight:700;color:#e8f4f8;margin-bottom:4px;">1. 뉴스 수집</div>
      <div style="font-size:12px;color:#7aacbf;">재난 관련 뉴스를 모아 관심 지역을 자동 추출합니다.</div>
    </div>
    <div style="padding:14px 16px;border-radius:14px;background:rgba(0,168,150,0.06);border:1px solid rgba(0,168,150,0.12);">
      <div style="font-weight:700;color:#e8f4f8;margin-bottom:4px;">2. 수온 분석</div>
      <div style="font-size:12px;color:#7aacbf;">관심 지역 SST를 모아 일별 추세와 고수온 상태를 확인합니다.</div>
    </div>
    <div style="padding:14px 16px;border-radius:14px;background:rgba(42,158,197,0.06);border:1px solid rgba(42,158,197,0.12);">
      <div style="font-weight:700;color:#e8f4f8;margin-bottom:4px;">3. 보고서 생성</div>
      <div style="font-size:12px;color:#7aacbf;">분석 결과를 Word와 PDF 보고서로 정리합니다.</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

section("바로가기", "🧭")
g1, g2, g3 = st.columns(3)
with g1:
    st.markdown('<div class="ocean-card" style="height:190px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:28px;margin-bottom:10px;">📰</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">재난 지역 분석</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#7aacbf;line-height:1.6;margin-bottom:16px;">지역별 기사 분포와 관심 지역을 지도와 표로 확인합니다.</div>', unsafe_allow_html=True)
    st.page_link("pages/2_Disaster_Areas.py", label="열기", icon="➡️")
    st.markdown('</div>', unsafe_allow_html=True)
with g2:
    st.markdown('<div class="ocean-card" style="height:190px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:28px;margin-bottom:10px;">🌡️</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">수온 시계열</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#7aacbf;line-height:1.6;margin-bottom:16px;">지역 SST를 인터랙티브 그래프로 보고 기간별 추세를 비교합니다.</div>', unsafe_allow_html=True)
    st.page_link("pages/5_SST_Timeseries.py", label="열기", icon="➡️")
    st.markdown('</div>', unsafe_allow_html=True)
with g3:
    st.markdown('<div class="ocean-card" style="height:190px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:28px;margin-bottom:10px;">📄</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">보고서</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#7aacbf;line-height:1.6;margin-bottom:16px;">보고서 페이지에서 분석 문서를 생성하고 내려받을 수 있습니다.</div>', unsafe_allow_html=True)
    st.page_link("pages/4_Report.py", label="열기", icon="➡️")
    st.markdown('</div>', unsafe_allow_html=True)

section("운영 팁", "✨")
st.markdown(
    """
<div class="ocean-card" style="padding:22px 26px;">
  <div style="display:grid;gap:10px;">
    <div style="color:#e8f4f8;font-weight:700;">• 파이프라인은 <span style="color:#00e5ff;">Pipeline</span> 페이지에서 실행하는 것이 가장 안정적입니다.</div>
    <div style="color:#e8f4f8;font-weight:700;">• 시계열은 <span style="color:#00e5ff;">SST Timeseries</span> 페이지에서 직접 확대하고 기간을 바꿀 수 있습니다.</div>
    <div style="color:#e8f4f8;font-weight:700;">• 경보는 오른쪽 상단 알림으로 즉시 표시됩니다.</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
