from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd
import streamlit as st

import config
from agents.alert_agent import get_active_alerts
from agents.report_agent import run as run_report
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply, card, hero, section


st.set_page_config(page_title="Pipeline", page_icon="🔗", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())


def _load_crawler_articles(keyword: str, limit: int) -> list[dict]:
    from agents.crawler_collection_agent import _live_crawl

    return _live_crawl(keyword, limit)


def _load_local_articles(limit: int) -> list[dict]:
    from utils.region_extractor import load_disaster_events

    df = load_disaster_events().copy()
    if "date" in df.columns:
        df = df.sort_values("date", ascending=False)
    df = df.head(limit)
    records: list[dict] = []
    for _, row in df.iterrows():
        records.append(
            {
                "title": str(row.get("title", "")),
                "body": str(row.get("title", "")),
                "keyword": str(row.get("keyword", "")),
                "location": str(row.get("location", "")),
                "published": str(row.get("date", "")),
                "url": str(row.get("url", "")),
            }
        )
    return records


def _build_download_bundle(report_result: dict | None, context: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        summary_lines = [
            "# Pipeline Run Summary",
            f"- keyword: {context['keyword']}",
            f"- article_limit: {context['article_limit']}",
            f"- threshold: {context['threshold']}",
            f"- crawl_source: {context.get('source', 'unknown')}",
            f"- news_rows: {context.get('news_rows', 0)}",
            f"- located_regions: {context.get('located_regions', 0)}",
            f"- saved_sst_regions: {context.get('saved_regions', 0)}",
            f"- alert_count: {context.get('alert_count', 0)}",
        ]
        zf.writestr("summary.md", "\n".join(summary_lines))

        news_df = context.get("news_df")
        if isinstance(news_df, pd.DataFrame) and not news_df.empty:
            zf.writestr("news_events.csv", news_df.to_csv(index=False, encoding="utf-8-sig"))

        freq_df = context.get("freq_df")
        if isinstance(freq_df, pd.DataFrame) and not freq_df.empty:
            zf.writestr("region_frequency.csv", freq_df.to_csv(index=False, encoding="utf-8-sig"))

        if report_result:
            for key in ("docx", "pdf"):
                entry = report_result.get(key)
                if entry and entry.get("bytes"):
                    filename = f"{report_result.get('filename_stem', 'report')}.{key}"
                    zf.writestr(filename, entry["bytes"])

    buffer.seek(0)
    return buffer.read()


hero(
    "파이프라인 실행",
    "뉴스 크롤링 → 관심지역 추출 → SST 수집 → 경보 판단 → 보고서 생성까지 한 번에 수행합니다.",
)

section("실행 설정", "⚙️")
with st.container():
    left, right = st.columns([1.15, 0.85])
    with left:
        st.markdown('<div class="ocean-card">', unsafe_allow_html=True)
        st.markdown("#### 실행 범위")
        st.caption("프로토타입에서는 SST 수집을 상위 5개 지역만 수행합니다.")
        keyword = st.selectbox(
            "관심 키워드",
            options=["고수온"],
            index=0,
            disabled=True,
            help="현재 파이프라인은 고수온 키워드로 고정 실행됩니다.",
        )
        article_limit = st.selectbox(
            "기사 수",
            options=[10, 12, 14, 16, 18, 20],
            index=5,
            help="10~20개 범위의 고정 선택만 남겼습니다.",
        )
        threshold = st.slider("고수온 기준(°C)", 24.0, 32.0, 28.0, 0.5)
        generate_report = st.checkbox("보고서 자동 생성", value=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="ocean-card">', unsafe_allow_html=True)
        st.markdown("#### 실행 흐름")
        card("1. 크롤링", "고수온", "관심 키워드 기사 수집", "📰")
        card("2. API", "SST", "관심지역에 대해 수온 데이터 수집", "🌊")
        card("3. 다운로드", "ZIP", "결과 파일을 한 번에 묶어 받기", "⬇️")
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

run_clicked = st.button("파이프라인 실행", type="primary", use_container_width=True)

if run_clicked:
    progress = st.progress(0, text="실행 준비 중...")
    log_box = st.empty()
    result_box = st.empty()

    def _log(message: str, pct: int | None = None):
        log_box.markdown(f"<div class='ocean-card' style='padding:14px 18px;'><b>{message}</b></div>", unsafe_allow_html=True)
        if pct is not None:
            progress.progress(pct, text=message)

    try:
        _log("[1/5] 뉴스 크롤링 시작", 10)
        source = "crawl"
        try:
            articles = _load_crawler_articles(keyword, article_limit)
        except Exception as exc:
            source = "local"
            st.warning(f"실시간 크롤링 실패, 로컬 데이터로 진행합니다: {exc}")
            articles = _load_local_articles(article_limit)

        from agents.crawler_collection_agent import extract_regions_from_articles

        _log("[2/5] 관심지역 추출", 30)
        regions = extract_regions_from_articles(articles)
        freq_df = pd.DataFrame(regions)
        news_df = pd.DataFrame(articles)
        news_rows = len(news_df)
        located_regions = int(freq_df.dropna(subset=["lat", "lon"]).shape[0]) if not freq_df.empty else 0
        top_regions_df = freq_df.dropna(subset=["lat", "lon"]).head(5).copy()

        _log(f"[3/5] SST 수집 ({len(top_regions_df)}개 지역)", 55)
        from scripts.collect_sst_by_region import collect_region

        saved_regions: list[str] = []
        failed_regions: list[str] = []
        if not top_regions_df.empty:
            for _, row in top_regions_df.iterrows():
                try:
                    collect_region(
                        region=row["location"],
                        lat=float(row["lat"]),
                        lon=float(row["lon"]),
                        start=date(2025, 6, 1),
                        end=date(2025, 8, 31),
                        out_dir=config.DATA_DIR,
                    )
                    saved_regions.append(row["location"])
                except Exception as exc:
                    failed_regions.append(f"{row['location']}({exc})")

        _log("[4/5] 경보 판단", 75)
        alerts = get_active_alerts(threshold=threshold)

        report_result = None
        if generate_report:
            _log("[5/5] 보고서 생성", 90)
            report_result = run_report(threshold=threshold, top_n_regions=min(article_limit, 5), use_ai=False)
        else:
            _log("[5/5] 보고서 생략", 90)

        download_context = {
            "keyword": keyword,
            "article_limit": article_limit,
            "threshold": threshold,
            "source": source,
            "news_df": news_df,
            "freq_df": freq_df,
            "news_rows": news_rows,
            "located_regions": located_regions,
            "saved_regions": len(saved_regions),
            "alert_count": len(alerts),
        }
        bundle = _build_download_bundle(report_result, download_context)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("수집 기사", f"{news_rows}건")
        c2.metric("지역 추출", f"{located_regions}개")
        c3.metric("SST 저장", f"{len(saved_regions)}개")
        c4.metric("경보", f"{len(alerts)}건")

        if failed_regions:
            st.warning(f"일부 SST 수집 실패: {', '.join(failed_regions[:5])}")

        result_box.success("파이프라인 실행이 완료되었습니다.")
        st.download_button(
            "결과 ZIP 다운로드",
            data=bundle,
            file_name=f"pipeline_{keyword}_{article_limit}.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.session_state["pipeline_report"] = report_result
        st.session_state["pipeline_download"] = bundle
        progress.progress(100, text="완료")
    except Exception as exc:
        st.error(f"실행 중 오류가 발생했습니다: {exc}")
    finally:
        progress.empty()
