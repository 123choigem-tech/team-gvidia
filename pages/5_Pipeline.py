"""파이프라인 실행 페이지 — 실제 크롤링→지역추출→수온수집→경보→보고서 전 흐름."""
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.style import apply
from utils.chat_widget import inject
from utils.alert_widget import inject_alerts
from agents.alert_agent import get_active_alerts
import config

st.set_page_config(page_title="Pipeline", page_icon="🔄", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("🔄 파이프라인 실행")
st.caption(
    "뉴스 크롤링 → 관심지역 추출 → 수온 수집 → 경보 판단 → 보고서 생성 "
    "전 단계를 한 번에 실행합니다."
)

# ── API 키 상태 ───────────────────────────────────────────
with st.expander("🔑 API 키 상태 확인", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.metric("네이버 API", "✅ 설정됨" if config.has_naver() else "❌ 미설정")
    c2.metric("공공데이터 API", "✅ 설정됨" if config.has_public_data() else "❌ 미설정")
    c3.metric("KOSC API", "✅ 설정됨" if config._get("KOSC_API_KEY") else "❌ 미설정")
    if not config.has_naver() and not config.has_public_data():
        st.warning("뉴스 API 키 없음 → BigKinds CSV 또는 시드(seed) 파일로 폴백됩니다.")

# ── 파라미터 ──────────────────────────────────────────────
st.subheader("⚙️ 실행 파라미터")
col1, col2, col3 = st.columns(3)
with col1:
    keywords = st.multiselect(
        "크롤링 키워드",
        options=config.DEFAULT_KEYWORDS + ["적조", "냉수"],
        default=["고수온"],
    )
    max_items = st.number_input("기사 최대 수집 건수", 10, 200, 50, step=10)
with col2:
    start = st.date_input("시작일", value=pd.Timestamp("2025-06-01")).strftime("%Y-%m-%d")
    end   = st.date_input("종료일", value=pd.Timestamp("2025-08-31")).strftime("%Y-%m-%d")
with col3:
    threshold       = st.slider("고수온 기준(℃)", 24.0, 32.0, 28.0, 0.5)
    generate_report = st.checkbox("보고서 자동 생성", value=True)

st.markdown("---")

# ── 단계 표시 ─────────────────────────────────────────────
STEPS = [
    ("📰", "뉴스 크롤링",     "crawl"),      # src/news/crawler.py
    ("📍", "관심지역 추출",   "region"),     # utils/region_extractor.py
    ("🛰️", "수온 수집",       "sst"),        # agents/collection_agent.py
    ("⚠️", "경보 판단",       "alert"),      # agents/alert_agent.py
    ("📄", "보고서 생성",     "report"),     # agents/report_agent.py
]

def _badge(state: str) -> str:
    return {"waiting": "⬜", "running": "🔵", "done": "✅", "skip": "⏭️", "error": "❌"}.get(state, "⬜")

step_placeholder = st.empty()

def render_steps(states: dict):
    with step_placeholder.container():
        cols = st.columns(len(STEPS))
        for col, (icon, label, key) in zip(cols, STEPS):
            col.markdown(
                f"<div style='text-align:center;padding:12px;"
                f"background:rgba(0,194,212,0.07);border-radius:8px;"
                f"border:1px solid rgba(0,194,212,0.15);'>"
                f"<div style='font-size:22px;'>{_badge(states.get(key,'waiting'))} {icon}</div>"
                f"<div style='font-size:12px;color:#7aacbf;margin-top:4px;'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

render_steps({})

# ── 실행 ──────────────────────────────────────────────────
if st.button("▶ 파이프라인 전체 실행", type="primary", use_container_width=True):
    states = {k: "waiting" for _, _, k in STEPS}
    logs: list[str] = []

    def upd(key: str, state: str, msg: str = ""):
        states[key] = state
        render_steps(states)
        if msg:
            logs.append(msg)

    try:
        # ── Step 1: 실제 크롤러 ───────────────────────────
        upd("crawl", "running")
        from src.news.crawler import crawl
        from src.news.store import EventStore
        from src.news import parse as news_parse

        store = EventStore(config.EVENTS_DB)
        all_articles = []
        for kw in keywords:
            arts = crawl(kw, max_items=max_items, since=start, until=end)
            all_articles.extend(arts)

        # SQLite에 저장 후 CSV export (disaster_events.csv 갱신)
        from src.news.store import EventRecord
        from datetime import datetime, timezone

        records = []
        for a in all_articles:
            loc_result = news_parse.resolve_location(
                f"{getattr(a,'title','')} {getattr(a,'description','')}"
            )
            records.append(EventRecord(
                disaster_type="고수온",
                event_date=news_parse.extract_event_date(getattr(a, "pub_date", None)),
                raw_location_text=loc_result.get("raw") if loc_result else None,
                normalized_sido=loc_result.get("sido") if loc_result else None,
                normalized_sigungu=loc_result.get("sigungu") if loc_result else None,
                normalized_region=loc_result.get("region") if loc_result else None,
                lat=loc_result.get("lat") if loc_result else None,
                lon=loc_result.get("lon") if loc_result else None,
                geocode_confidence=loc_result.get("confidence", 0.0) if loc_result else 0.0,
                geocode_source=loc_result.get("source", "") if loc_result else "",
                source_title=getattr(a, "title", None),
                source_url=getattr(a, "link", "") or "",
                source_name=getattr(a, "source_name", None),
                pub_date=getattr(a, "pub_date", None),
                origin=getattr(a, "origin", "unknown"),
                crawled_at=datetime.now(timezone.utc).isoformat(),
            ))
        inserted = store.upsert_many(records)

        # CSV export (2_Disaster_Areas.py 가 읽는 파일 갱신)
        _events_csv = config.DATA_DIR / "processed" / "disaster_db" / "disaster_events.csv"
        _events_csv.parent.mkdir(parents=True, exist_ok=True)
        df_export = store.query()
        # 기존 페이지 호환 컬럼명으로 rename
        col_map = {
            "event_date": "date",
            "normalized_region": "location",
            "source_title": "title",
            "source_url": "url",
        }
        df_export = df_export.rename(columns=col_map)
        df_export["keyword"] = "고수온"
        df_export.to_csv(_events_csv, index=False, encoding="utf-8")

        upd("crawl", "done", f"✅ 기사 {len(all_articles)}건 수집 / DB 신규 {inserted}건 / CSV 갱신")

        # ── Step 2: 관심지역 추출 ────────────────────────
        upd("region", "running")
        from utils.region_extractor import load_disaster_events, extract_regions
        ev_df = load_disaster_events()
        freq_df = extract_regions(ev_df)
        regions = freq_df.dropna(subset=["lat", "lon"]).to_dict("records")
        upd("region", "done", f"✅ 관심지역 {len(regions)}개 추출 → region_frequency.csv 갱신")

        # ── Step 3: 수온 수집 ────────────────────────────
        upd("sst", "running")
        from agents.collection_agent import run as run_collection
        col_results = run_collection(regions, start, end)
        ok_n = sum(1 for r in col_results if r.get("success"))
        upd("sst", "done", f"✅ 수온 수집 {ok_n}/{len(col_results)}개 지역 성공")

        # ── Step 4: 경보 판단 ────────────────────────────
        upd("alert", "running")
        alerts = get_active_alerts(threshold=threshold)
        alarm_n    = sum(1 for a in alerts if a["level"] == "alarm")
        advisory_n = sum(1 for a in alerts if a["level"] == "advisory")
        upd("alert", "done", f"✅ 경보 {alarm_n}건 / 주의보 {advisory_n}건")

        # ── Step 5: 보고서 ───────────────────────────────
        if generate_report:
            upd("report", "running")
            from agents.report_agent import run as run_report
            report = run_report(threshold=threshold)
            upd("report", "done", "✅ 보고서 생성 완료")
            st.session_state["pipeline_report"] = report
        else:
            upd("report", "skip")

        st.session_state["pipeline_result"] = {
            "articles":    all_articles,
            "col_results": col_results,
            "alerts":      alerts,
            "freq_df":     freq_df,
        }
        st.success("파이프라인 실행 완료! 2_Disaster_Areas 페이지에서 결과를 확인하세요.")

    except Exception as e:
        for key, state in states.items():
            if state == "running":
                states[key] = "error"
        render_steps(states)
        st.error(f"파이프라인 오류: {e}")
        logs.append(f"❌ {e}")

    if logs:
        st.markdown("---")
        for msg in logs:
            st.write(msg)

# ── 결과 탭 ───────────────────────────────────────────────
if "pipeline_result" in st.session_state:
    res = st.session_state["pipeline_result"]
    st.markdown("---")
    st.subheader("📊 실행 결과")

    tab1, tab2, tab3, tab4 = st.tabs(["수집 기사", "관심지역", "수온 수집", "경보·주의보"])

    with tab1:
        arts = res.get("articles", [])
        if arts:
            rows = [{"제목": getattr(a,"title",""), "출처": getattr(a,"source_name",""),
                     "날짜": getattr(a,"pub_date",""), "링크": getattr(a,"link","")} for a in arts]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("수집된 기사가 없습니다.")

    with tab2:
        freq_df = res.get("freq_df", pd.DataFrame())
        st.dataframe(freq_df, use_container_width=True)

    with tab3:
        col_df = pd.DataFrame(res["col_results"])
        show = [c for c in ["region","success","count","error"] if c in col_df.columns]
        st.dataframe(col_df[show], use_container_width=True)

    with tab4:
        alerts = res["alerts"]
        if alerts:
            adf = pd.DataFrame(alerts)
            adf["단계"] = adf["level"].map({"alarm":"🔴 경보","advisory":"🟡 주의보"})
            show = [c for c in ["region","단계","current_streak","latest_sst","latest_date"] if c in adf.columns]
            st.dataframe(adf[show], use_container_width=True)
        else:
            st.info("현재 경보·주의보 지역 없음")

# ── 보고서 다운로드 ───────────────────────────────────────
if "pipeline_report" in st.session_state:
    report = st.session_state["pipeline_report"]
    st.markdown("---")
    st.subheader("📄 보고서 다운로드")
    stem = report.get("filename_stem", "report")
    d1, d2 = st.columns(2)
    if report.get("docx") and report["docx"].get("bytes"):
        d1.download_button("Word 다운로드", report["docx"]["bytes"],
                           file_name=f"{stem}.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           use_container_width=True)
    if report.get("pdf") and report["pdf"].get("bytes"):
        d2.download_button("PDF 다운로드", report["pdf"]["bytes"],
                           file_name=f"{stem}.pdf",
                           mime="application/pdf",
                           use_container_width=True)
