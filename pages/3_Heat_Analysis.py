import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from agents.alert_agent import get_active_alerts
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply

st.set_page_config(page_title="Heat Analysis", page_icon="🌡️", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("🌡️ 해수면온도 분석")
st.caption("실제 수집된 SST CSV로 지역별 고수온 추세를 비교합니다.")

DATA_DIR = Path("data")
HOT28_DIR = Path("data/results/sst_analysis/sst_over28/img")
TS_MEAN_IMG = Path("data/results/sst_analysis/timeseries/SST_daily_mean_20250701_20250831.png")
DEFAULT_THRESHOLD = 28.0
CONSEC_MIN = 3
FREQ_MIN = 2


@st.cache_data(ttl=300)
def load_region_freq() -> pd.DataFrame:
    freq_path = Path("data/results/frequency/region_frequency.csv")
    return pd.read_csv(freq_path, encoding="utf-8") if freq_path.exists() else pd.DataFrame()


@st.cache_data(ttl=300)
def load_sst_by_region() -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for f in sorted(DATA_DIR.glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in {"geocode", "regions", "Tongyeong"}:
            continue
        df = pd.read_csv(f, encoding="utf-8", parse_dates=["date"])
        if {"date", "sst", "source"}.issubset(df.columns) and df["source"].iloc[0] == "KHOA_OPeNDAP":
            result[region] = df.sort_values("date").reset_index(drop=True)
    return result


@st.cache_data(ttl=300)
def load_hot28_images() -> dict[str, Path]:
    """일자(YYYY-MM-DD) → 28℃ 초과 공간분포 PNG 경로."""
    out: dict[str, Path] = {}
    if not HOT28_DIR.exists():
        return out
    for p in sorted(HOT28_DIR.glob("*_HOT28.png")):
        m = re.search(r"_U(\d{8})_HOT28", p.name)
        if m:
            d = m.group(1)
            out[f"{d[:4]}-{d[4:6]}-{d[6:8]}"] = p
    return out


def calc_hot_stats(df: pd.DataFrame, threshold: float) -> dict:
    sst = df["sst"].values
    hot_mask = sst >= threshold
    hot_freq = int(hot_mask.sum())
    max_consec = 0
    cur = 0
    for v in hot_mask:
        cur = cur + 1 if v else 0
        max_consec = max(max_consec, cur)
    return {
        "avg": float(pd.Series(sst).mean()),
        "max": float(pd.Series(sst).max()),
        "hot_freq": hot_freq,
        "max_consec": max_consec,
        "persist2": hot_freq >= FREQ_MIN,
        "persist3": max_consec >= CONSEC_MIN,
    }


freq_df = load_region_freq()
sst_data = load_sst_by_region()

if not sst_data:
    st.warning("수집된 SST CSV가 없습니다. 먼저 `data/*_2025*.csv` 파일을 생성하세요.")
    st.stop()

regions = sorted(sst_data.keys())
selected = st.multiselect("분석 대상 지역", regions, default=regions[: min(3, len(regions))])
threshold = st.slider("고수온 기준(℃)", 24.0, 32.0, DEFAULT_THRESHOLD, 0.5)

if not selected:
    st.info("분석할 지역을 하나 이상 선택하세요.")
    st.stop()

stats = {r: calc_hot_stats(sst_data[r], threshold) for r in selected}

summary_cols = st.columns(len(selected))
for col, region in zip(summary_cols, selected):
    s = stats[region]
    col.metric(region, f"평균 {s['avg']:.1f}℃", f"최고 {s['max']:.1f}℃")
    col.caption(f"고수온 {s['hot_freq']}일 · 최장 연속 {s['max_consec']}일")

flags = st.columns(2)
flags[0].success(f"누적 {FREQ_MIN}일 이상 지역: {sum(1 for r in selected if stats[r]['persist2'])}개")
flags[1].warning(f"연속 {CONSEC_MIN}일 이상 지역: {sum(1 for r in selected if stats[r]['persist3'])}개")

st.markdown("---")

tab1, tab2, tab_dist, tab3 = st.tabs(["추세", "빈도", "고수온 공간분포", "원본"])

with tab1:
    st.subheader("일별 SST 추이")
    fig = go.Figure()
    for region in selected:
        df = sst_data[region].sort_values("date")
        fig.add_trace(go.Scatter(x=df["date"], y=df["sst"], mode="lines", name=region))
    fig.add_hline(y=threshold, line_dash="dash", line_color="#ff6b35")
    fig.update_layout(
        xaxis_title="날짜",
        yaxis_title="SST (℃)",
        hovermode="x unified",
        height=360,
        margin=dict(t=10, b=20, l=20, r=10),
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("**전체 해역 일평균 SST 시계열** (domain-mean · domain-max)")
    if TS_MEAN_IMG.exists():
        st.image(
            str(TS_MEAN_IMG),
            caption="KHOA SST domain-mean 일별 시계열 (2025-07-01 ~ 2025-08-31)",
            use_container_width=True,
        )
    else:
        st.info("일평균 SST 시계열 이미지가 없습니다. (data/results/sst_analysis/timeseries)")

with tab2:
    st.subheader("관심 지역 언급 빈도")
    if not freq_df.empty:
        fig2 = px.bar(
            freq_df.sort_values("count", ascending=True).head(12),
            x="count",
            y="location",
            orientation="h",
            labels={"count": "언급 수", "location": "지역"},
            color="count",
            color_continuous_scale=["#bfefff", "#00c2d4", "#005f6e"],
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("지역 빈도 파일이 없습니다.")

with tab_dist:
    st.subheader("고수온 공간분포 (28℃ 초과 일별)")
    hot28 = load_hot28_images()
    if not hot28:
        st.info("28℃ 초과 공간분포 이미지가 없습니다. (data/results/sst_analysis/sst_over28/img)")
    else:
        dates = list(hot28.keys())
        default_date = "2025-07-19" if "2025-07-19" in hot28 else dates[len(dates) // 2]
        sel_date = st.select_slider(
            "날짜 선택",
            options=dates,
            value=default_date,
            help="슬라이더를 움직여 일자별 28℃ 초과 해역 분포를 확인하세요.",
        )
        st.image(
            str(hot28[sel_date]),
            caption=f"{sel_date} · SST 28℃ 초과 공간분포",
            use_container_width=True,
        )
        st.caption(f"총 {len(dates)}일 ({dates[0]} ~ {dates[-1]}) · 28℃ 이상 격자를 강조한 일별 지도")

with tab3:
    st.subheader("원본 SST 데이터")
    for region in selected:
        with st.expander(region, expanded=False):
            df = sst_data[region].copy()
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            show_cols = [c for c in ["date", "lat", "lon", "sst", "source"] if c in df.columns]
            st.dataframe(df[show_cols].head(100), use_container_width=True, height=260)
