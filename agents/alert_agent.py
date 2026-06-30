# -*- coding: utf-8 -*-
"""
alert_agent.py — 고수온 지속 조건 감지 알림 서브에이전트

조건:
  - 🟠 주의: 28°C 이상 누적 2일↑ (persist2)
  - 🔴 위험: 28°C 이상 연속 3일↑ (persist3)

공개 함수:
  check(threshold=28.0) -> list[dict]
    각 지역별 알림 레벨·지속일수 반환

  get_active_alerts(threshold=28.0) -> list[dict]
    주의 이상 지역만 필터링해서 반환
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR   = Path("data")
THRESHOLD  = 28.0
FREQ_MIN   = 2   # 누적 기준 (sst_frequency.py 동일)
CONSEC_MIN = 3   # 연속 기준 (sst_persistence.py 동일)


def _calc(df: pd.DataFrame, threshold: float) -> dict:
    sst  = df["sst"].dropna().values
    hot  = sst >= threshold
    freq = int(hot.sum())

    cur = max_c = 0
    for v in hot:
        cur   = cur + 1 if v else 0
        max_c = max(max_c, cur)

    # 가장 최근 연속 고수온 일수 (현재 진행 중인 streak)
    current_streak = 0
    for v in reversed(hot):
        if v:
            current_streak += 1
        else:
            break

    latest_sst = float(df["sst"].iloc[-1]) if not df.empty else None
    latest_date = str(df["date"].iloc[-1])[:10] if not df.empty else None

    if max_c >= CONSEC_MIN:
        level = "danger"   # 🔴 위험
    elif freq >= FREQ_MIN:
        level = "warning"  # 🟠 주의
    else:
        level = "normal"   # 정상

    return {
        "hot_freq":       freq,
        "max_consec":     max_c,
        "current_streak": current_streak,
        "level":          level,
        "latest_sst":     latest_sst,
        "latest_date":    latest_date,
    }


def check(threshold: float = THRESHOLD) -> list[dict]:
    """전체 지역 고수온 감지 결과 반환."""
    results = []
    for f in sorted(DATA_DIR.glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in ("geocode", "regions", "Tongyeong"):
            continue
        try:
            df = pd.read_csv(f, encoding="utf-8", parse_dates=["date"])
            if "sst" not in df.columns:
                continue
            src = df.get("source", pd.Series([""])).iloc[0]
            if src != "KHOA_OPeNDAP":
                continue
            stat = _calc(df.sort_values("date").reset_index(drop=True), threshold)
            results.append({"region": region, **stat, "threshold": threshold})
        except Exception:
            continue
    return results


def get_active_alerts(threshold: float = THRESHOLD) -> list[dict]:
    """주의(🟠) 이상 지역만 반환, 위험 우선 정렬."""
    all_r = check(threshold)
    active = [r for r in all_r if r["level"] != "normal"]
    active.sort(key=lambda x: (0 if x["level"] == "danger" else 1, -x["max_consec"]))
    return active


if __name__ == "__main__":
    alerts = check()
    for a in alerts:
        icon = "🔴" if a["level"] == "danger" else ("🟠" if a["level"] == "warning" else "✅")
        print(f"{icon} {a['region']}: 누적 {a['hot_freq']}일, 최장연속 {a['max_consec']}일, 현재streak {a['current_streak']}일 | 최근 {a['latest_sst']}°C ({a['latest_date']})")
