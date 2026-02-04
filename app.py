"""
========================================================
  기능성 포장 필요구간 자동 탐색 플랫폼 — 백엔드 서버
========================================================
  실행 방법:
    1) pip install fastapi uvicorn httpx
    2) 아래 ANTHROPIC_API_KEY 설정
    3) python app.py
    4) 브라우저에서 http://localhost:8000 접속
========================================================
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx
import os
import json

# ★★★ API 키 설정 (둘 중 하나) ★★★
# 방법1: 직접 입력
ANTHROPIC_API_KEY = "여기에_API_키_입력"
# 방법2: 환경변수 (터미널에서: export ANTHROPIC_API_KEY=sk-ant-...)
if os.getenv("ANTHROPIC_API_KEY"):
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 공공 API 키 (나중에 data.go.kr에서 발급)
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")      # 기상청 ASOS
TAAS_API_KEY = os.getenv("TAAS_API_KEY", "")            # 교통사고분석
DEM_API_KEY = os.getenv("DEM_API_KEY", "")              # 국토정보 DEM

app = FastAPI(title="기능성 포장 플랫폼 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
#  1) Claude AI 분석 (핵심! 지금 바로 작동)
# ============================================
@app.post("/api/analyze")
async def analyze(request: Request):
    """Claude AI N2B 분석 — 브라우저 CORS 우회 프록시"""
    body = await request.json()

    if ANTHROPIC_API_KEY == "여기에_API_키_입력":
        return JSONResponse(
            status_code=400,
            content={"error": "API 키를 설정해주세요. app.py의 ANTHROPIC_API_KEY 변수를 수정하세요."}
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": body.get("model", "claude-sonnet-4-20250514"),
                "max_tokens": body.get("max_tokens", 1000),
                "messages": body.get("messages", []),
            }
        )
        return resp.json()


# ============================================
#  2) 기상청 API (샘플 데이터 / 실제 API 전환)
# ============================================
@app.get("/api/weather/{station_id}")
async def get_weather(station_id: str):
    """기상청 ASOS 데이터 — API 키 있으면 실제 호출, 없으면 샘플"""
    if WEATHER_API_KEY:
        # ★ 실제 API 호출 (키 발급 후 활성화)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList",
                params={
                    "serviceKey": WEATHER_API_KEY,
                    "numOfRows": "24",
                    "pageNo": "1",
                    "dataType": "JSON",
                    "dataCd": "ASOS",
                    "dateCd": "HR",
                    "stnIds": station_id,
                }
            )
            return resp.json()
    else:
        # 샘플 데이터
        return {
            "status": "sample",
            "message": "기상청 API 키 미설정 → 샘플 데이터 반환",
            "data": {
                "station_id": station_id,
                "annual_heavy_rain_days": 42,
                "avg_hourly_max_rain_mm": 38.5,
                "rain_days_per_year": 108,
                "monthly_rain": [22,28,45,62,88,133,394,348,145,52,35,18],
                "note": "data.go.kr → 기상청 종관기상관측(ASOS) API 키 발급 필요"
            }
        }


# ============================================
#  3) TAAS 사고 데이터 (샘플)
# ============================================
@app.get("/api/accident/{region_code}")
async def get_accident(region_code: str):
    """TAAS 교통사고 데이터"""
    if TAAS_API_KEY:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "http://apis.data.go.kr/B552061/AccidentDeath/getRestTrafficAccidentDeath",
                params={
                    "serviceKey": TAAS_API_KEY,
                    "searchYearCd": "2024",
                    "siDo": region_code,
                    "numOfRows": "50",
                    "pageNo": "1",
                    "type": "json",
                }
            )
            return resp.json()
    else:
        return {
            "status": "sample",
            "message": "TAAS API 키 미설정 → 샘플 데이터 반환",
            "data": {
                "region": region_code,
                "total_accidents_rainy": 847,
                "fatalities_rainy": 23,
                "injuries_rainy": 1205,
                "wet_road_accident_rate": 0.23,
                "top_accident_spots": [
                    {"name": "남산순환로", "count": 8, "type": "경사+수막"},
                    {"name": "한남IC", "count": 9, "type": "합류부"},
                    {"name": "동작대교램프", "count": 7, "type": "교량접속"}
                ],
                "note": "data.go.kr → 도로교통공단 TAAS API 키 발급 필요"
            }
        }


# ============================================
#  4) DEM 경사도 데이터 (샘플)
# ============================================
@app.get("/api/slope")
async def get_slope(lat: float = 37.55, lng: float = 126.98):
    """국토정보 DEM 경사도 데이터"""
    if DEM_API_KEY:
        # 실제 API 호출 로직
        pass
    
    return {
        "status": "sample",
        "message": "국토정보 DEM API 키 미설정 → 샘플 데이터 반환",
        "data": {
            "lat": lat,
            "lng": lng,
            "elevation_m": 85.3,
            "slope_percent": 6.2,
            "slope_direction": "SW",
            "terrain_type": "hillside",
            "note": "data.go.kr → 국토지리정보원 수치표고모델(DEM) API 키 발급 필요"
        }
    }


# ============================================
#  5) 시스템 상태 확인
# ============================================
@app.get("/api/status")
async def status():
    """API 연결 상태 확인"""
    return {
        "claude_ai": "connected" if ANTHROPIC_API_KEY != "여기에_API_키_입력" else "no_key",
        "weather": "connected" if WEATHER_API_KEY else "sample",
        "taas": "connected" if TAAS_API_KEY else "sample",
        "dem": "connected" if DEM_API_KEY else "sample",
    }


# ============================================
#  정적 파일 서빙 (index.html)
# ============================================
@app.get("/")
async def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "index.html 파일을 같은 폴더에 넣어주세요"}


# ============================================
#  실행
# ============================================
if __name__ == "__main__":
    import uvicorn

    key_ok = ANTHROPIC_API_KEY != "여기에_API_키_입력"
    
    print()
    print("=" * 55)
    print("  🛣️  기능성 포장 필요구간 자동 탐색 플랫폼")
    print("=" * 55)
    print()
    print(f"  📡 Claude AI   : {'✅ 연결됨' if key_ok else '❌ API 키 필요'}")
    print(f"  🌧️  기상청 ASOS : {'✅ 연결됨' if WEATHER_API_KEY else '⬜ 샘플 데이터'}")
    print(f"  🚗 TAAS 사고   : {'✅ 연결됨' if TAAS_API_KEY else '⬜ 샘플 데이터'}")
    print(f"  ⛰️  국토정보 DEM: {'✅ 연결됨' if DEM_API_KEY else '⬜ 샘플 데이터'}")
    print()
    if not key_ok:
        print("  ⚠️  app.py에서 ANTHROPIC_API_KEY를 설정하세요!")
        print()
    print("  🌐 http://localhost:8000 에서 실행")
    print("=" * 55)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
