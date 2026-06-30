# 재사용 스크립트 모음

이 문서는 반복 작업에 바로 붙여 넣어 실행할 수 있는 명령을 모아둔 것이다.

## 1) Streamlit 앱 실행
```powershell
streamlit run app.py
```

## 2) 뉴스 수집 및 CSV 반영
```powershell
python src\app.py
python src\news_crawler.py
python scripts\run_crawl.py
```

## 3) 지역 추출 및 지오코딩
```powershell
python scripts\geocode.py --regions 통영,거제,포항
python scripts\geocode.py --text "통영과 거제 연안에서 적조가 관측됐다"
```

## 4) SST 수집
```powershell
python src\download_khoa_sst.py --start 2025-07-01 --end 2025-08-31 --out .\data\input\khoa_sst
python src\download_lss.py --start 2025-07-01 --end 2025-08-31 --out .\data\input\lss
```

## 5) 고수온 분석
```powershell
python src\sst_processing.py --in-dir .\data\input\khoa_sst --out-dir .\data\results\sst_analysis\sst_over28
python src\sst_timeseries.py --src-dir .\data\input\khoa_sst --out-dir .\data\results\sst_analysis\timeseries
python src\hot_lowsal.py --sst-dir .\data\results\sst_analysis\sst_over28 --lss-dir .\data\input\lss
```

## 6) 보고서 생성
```powershell
python scripts\build_hwpx_report.py
python -c "from agents.report_agent import run; print(run())"
```

## 7) 제출 전 점검
```powershell
Get-ChildItem -Recurse submit | Select-Object FullName,Length,LastWriteTime
Get-Content submit\CHECKLIST.md
```

## 8) 타임스탬프 기록
```powershell
Get-ChildItem -Recurse -File .\app.py, .\src, .\pages, .\agents, .\utils, .\scripts, .\submit |
  Select-Object FullName,LastWriteTime |
  Format-Table -AutoSize
```
