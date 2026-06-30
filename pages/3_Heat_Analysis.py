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
st.caption("실제 수집된 SST CSV를 바탕으로 지역별 추세와 시각자료를 함께 확인합니다.")

DATA_DIR = Path("data")
DEFAULT_THRESHOLD = 28.0
CONSEC_MIN = 3
FREQ_MIN = 2
TS_DIR = Path("data/sst/timeseries")
HOT_IMG_DIR = Path("data/sst/hot/img")


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
        if {"date", "sst", "source"}.issubset(df.columns) and not df.empty:
            if str(df["source"].iloc[0]) == "KHOA_OPeNDAP":
                result[region] = df.sort_values("date").reset_index(drop=True)
    return result


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

tab1, tab2, tab3 = st.tabs(["분석결과", "지역빈도", "시각자료"])

with tab1:
    st.subheader("일별 SST 분석결과")
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

with tab2:
    st.subheader("관심 지역 빈도")
    if not freq_df.empty:
        top_freq = freq_df.sort_values("count", ascending=True).head(12)
        fig2 = px.bar(
            top_freq,
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

with tab3:
    ts_imgs = sorted(TS_DIR.glob("SST_daily_mean_*.png"))
    hot_imgs = sorted(HOT_IMG_DIR.glob("*_HOT28.png"))
    if hot_imgs:
        hot_dates = [img.stem.rsplit("_", 1)[0].replace("KHOA_SST_L4_Z003_D01_WGS001K_U", "") for img in hot_imgs]
        hot_pick = st.select_slider("날짜", options=list(range(len(hot_imgs))), format_func=lambda i: hot_dates[i])
    else:
        hot_pick = None
        st.info("고수온 분석 지도가 없습니다.")

    item1, item2, item3 = st.tabs(["일별 지도", "공간분포", "시계열"])

    with item1:
        if hot_pick is not None:
            st.image(str(hot_imgs[hot_pick]), caption=hot_imgs[hot_pick].stem, width=620)

    with item2:
        if hot_imgs:
            preview = hot_imgs[:4]
            cols = st.columns(2)
            for idx, img in enumerate(preview):
                with cols[idx % 2]:
                    st.image(str(img), caption=img.stem, width=300)
        else:
            st.info("고수온 공간분포 결과가 없습니다.")

    with item3:
        if ts_imgs:
            center1, center2, center3 = st.columns([1, 2, 1])
            with center2:
                st.image(str(ts_imgs[0]), width=620)
        else:
            st.info("일별 시계열 결과가 없습니다.")
