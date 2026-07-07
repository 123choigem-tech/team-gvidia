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

hero(
    "예보사업부 AI·AX 플랫폼",
    "관심지역 수집, 고수온 분석, 보고서 생성을 한 화면에서 연결하는 운영 대시보드입니다.",
)

section("현재 분석 현황", "📡")
c1, c2, c3, c4 = st.columns(4)
with c1:
    card("수집된 뉴스", f"{s['news_count']:,}건" if s["news_count"] else "없음", s["news_period"], "📰")
with c2:
    card("수집된 수온", f"{s['sst_count']:,}건" if s["sst_count"] else "없음", f"KHOA OPeNDAP · {s['sst_regions']}개 지역", "🌡️")
with c3:
    card("고수온 위험 지역", f"{len(s['hot_regions'])}개" if s["hot_regions"] else "없음", ", ".join(s["hot_regions"]) if s["hot_regions"] else "연속 3일 이상 지역", "⚠️")
with c4:
    card("최신 갱신", s["last_updated"] or "미확인", "분석 데이터 기준", "🔄")

section("분석 데이터 업데이트", "✨")
st.markdown(
    """
<div class="ocean-card" style="padding:24px 28px;">
  <div style="font-size:14px;color:#e8f4f8;margin-bottom:6px;font-weight:700;">최신 뉴스를 수집하고 분석 결과를 갱신합니다</div>
  <div style="font-size:12px;color:#7aacbf;">수집된 데이터는 재난 지역 분석과 수온 현황 페이지에 즉시 반영됩니다.</div>
</div>
""",
    unsafe_allow_html=True,
)

section("서비스 안내", "🧭")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">📰</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">뉴스 수집</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">재난 관련 뉴스를 자동으로 수집하고 지역 정보를 추출합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">🌡️</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">수온 분석</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">관심지역 SST를 모아 일별 추세와 고수온 상태를 확인합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">⚠️</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">경보 판단</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">28℃ 이상 연속 조건을 바탕으로 경보와 주의보를 자동 판정합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
