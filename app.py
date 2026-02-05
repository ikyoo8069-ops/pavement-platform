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
ITS_CCTV_KEY = os.getenv("ITS_CCTV_KEY", "")            # ITS CCTV (its.go.kr)
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY", "")         # VWorld 지도/DEM

app = FastAPI(title="기능성 포장 플랫폼 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "https://ikyoo8069-ops.github.io",
        "https://pavement-platform-1.onrender.com",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
#  0) VWorld 지도 API (배경지도 + DEM)
# ============================================
@app.get("/api/vworld/tile-info")
async def get_vworld_tile_info():
    """VWorld 배경지도 타일 URL 반환 (API 키 숨김)"""
    if VWORLD_API_KEY:
        return {
            "status": "live",
            "base": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
            "satellite": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
            "hybrid": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/Hybrid/{{z}}/{{y}}/{{x}}.png",
            "midnight": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/midnight/{{z}}/{{y}}/{{x}}.png",
            "white": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/white/{{z}}/{{y}}/{{x}}.png",
        }
    else:
        return {
            "status": "unavailable",
            "message": "VWorld API 키 미설정. Render 환경변수에 VWORLD_API_KEY를 추가하세요."
        }


@app.get("/api/vworld/geocode")
async def geocode(address: str):
    """주소 → 좌표 변환"""
    if not VWORLD_API_KEY:
        return {"status": "error", "message": "VWorld API 키 미설정"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.vworld.kr/req/address",
            params={
                "service": "address",
                "request": "getcoord",
                "key": VWORLD_API_KEY,
                "address": address,
                "type": "road",
                "format": "json",
            }
        )
        return resp.json()


@app.get("/api/vworld/reverse-geocode")
async def reverse_geocode(lat: float, lng: float):
    """좌표 → 주소 변환"""
    if not VWORLD_API_KEY:
        return {"status": "error", "message": "VWorld API 키 미설정"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.vworld.kr/req/address",
            params={
                "service": "address",
                "request": "getaddr",
                "key": VWORLD_API_KEY,
                "point": f"{lng},{lat}",
                "type": "road",
                "format": "json",
            }
        )
        return resp.json()


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
#  5) ITS CCTV 실시간 영상 (its.go.kr)
# ============================================
@app.get("/api/cctv")
async def get_cctv(lat: float = 37.55, lng: float = 126.98, radius: float = 0.05):
    """
    ITS 국가교통정보센터 CCTV API
    - 키 발급: its.go.kr → 마이페이지 → 인증키 신청
    - 반환: 인근 CCTV 목록 + 실시간 영상 URL
    """
    if ITS_CCTV_KEY:
        # ★ 실제 API 호출
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://openapi.its.go.kr:9443/cctvInfo",
                params={
                    "apiKey": ITS_CCTV_KEY,
                    "type": "all",        # ex:고속도로, its:국도, all:전체
                    "cctvType": "2",      # 1:실시간스트리밍, 2:정지영상
                    "minX": str(lng - radius),
                    "maxX": str(lng + radius),
                    "minY": str(lat - radius),
                    "maxY": str(lat + radius),
                    "getType": "json",
                }
            )
            data = resp.json()
            # CCTV 목록 정리
            cctvs = []
            if "response" in data and "data" in data["response"]:
                for item in data["response"]["data"]:
                    cctvs.append({
                        "name": item.get("cctvname", ""),
                        "lat": float(item.get("coordy", 0)),
                        "lng": float(item.get("coordx", 0)),
                        "url": item.get("cctvurl", ""),
                        "format": item.get("cctvformat", ""),
                    })
            return {"status": "live", "count": len(cctvs), "data": cctvs}
    else:
        # 샘플 데이터 — 23개 구간 인근 CCTV 위치
        samples = [
            {"name":"남산1터널 입구","lat":37.553,"lng":126.985,"url":"","format":"image"},
            {"name":"강남역 교차로","lat":37.498,"lng":127.028,"url":"","format":"image"},
            {"name":"올림픽대로 잠실대교","lat":37.519,"lng":127.078,"url":"","format":"image"},
            {"name":"북악터널 입구","lat":37.591,"lng":126.968,"url":"","format":"image"},
            {"name":"신림사거리","lat":37.485,"lng":126.930,"url":"","format":"image"},
            {"name":"인왕산터널","lat":37.580,"lng":126.959,"url":"","format":"image"},
            {"name":"내부순환 정릉입구","lat":37.604,"lng":127.010,"url":"","format":"image"},
            {"name":"동작대교 남단","lat":37.506,"lng":126.983,"url":"","format":"image"},
            {"name":"한남IC","lat":37.535,"lng":127.002,"url":"","format":"image"},
            {"name":"사당역","lat":37.478,"lng":126.983,"url":"","format":"image"},
        ]
        return {
            "status": "sample",
            "message": "ITS CCTV API 키 미설정 → 샘플 데이터. its.go.kr에서 인증키 발급 필요",
            "count": len(samples),
            "data": samples
        }


# ============================================
#  6) 도로안전시설 점검 데이터
# ============================================
@app.get("/api/safety-facilities")
async def get_safety_facilities(lat: float = 37.55, lng: float = 126.98, radius: float = 0.05):
    """
    도로안전시설 점검 현황
    - 가드레일, 충격흡수시설, 도로표지, 시선유도시설, 조명시설, 과속방지턱
    - 향후 data.go.kr 연동 가능 (국토교통부_도로시설물현황)
    """
    # 23개 구간 인근 안전시설 점검 데이터 (샘플)
    facilities = [
        {"name":"남산순환로 가드레일","lat":37.552,"lng":126.987,"type":"가드레일","status":"양호","last_check":"2025-09","grade":"B","issue":"부분 녹 발생, 도장 필요","photo":""},
        {"name":"남산순환로 시선유도봉","lat":37.550,"lng":126.990,"type":"시선유도시설","status":"교체필요","last_check":"2025-06","grade":"D","issue":"반사체 마모 심각, 야간 시인성 불량","photo":""},
        {"name":"북악스카이웨이 가드레일","lat":37.594,"lng":126.966,"type":"가드레일","status":"주의","last_check":"2025-08","grade":"C","issue":"곡선부 가드레일 높이 부족, 차량 이탈 위험","photo":""},
        {"name":"북악스카이웨이 도로반사경","lat":37.592,"lng":126.968,"type":"도로반사경","status":"양호","last_check":"2025-10","grade":"A","issue":"정상","photo":""},
        {"name":"동작대교 램프 충격흡수시설","lat":37.506,"lng":126.981,"type":"충격흡수시설","status":"교체필요","last_check":"2025-05","grade":"D","issue":"충격흡수시설 변형, 즉시 교체 필요","photo":""},
        {"name":"한남IC 합류부 표지","lat":37.535,"lng":127.000,"type":"도로표지","status":"주의","last_check":"2025-07","grade":"C","issue":"반사 성능 저하, 야간 판독 곤란","photo":""},
        {"name":"강남역 보행자신호등","lat":37.498,"lng":127.027,"type":"신호등","status":"양호","last_check":"2025-11","grade":"A","issue":"정상 작동","photo":""},
        {"name":"강남역 배수구","lat":37.497,"lng":127.028,"type":"배수시설","status":"주의","last_check":"2025-09","grade":"C","issue":"낙엽·쓰레기 퇴적, 침수 시 배수 용량 부족 우려","photo":""},
        {"name":"올림픽대로 방음벽","lat":37.519,"lng":127.074,"type":"방음벽","status":"양호","last_check":"2025-10","grade":"B","issue":"일부 패널 변색, 구조 안전성 이상 없음","photo":""},
        {"name":"올림픽대로 조명시설","lat":37.517,"lng":127.076,"type":"조명시설","status":"교체필요","last_check":"2025-08","grade":"D","issue":"LED 3기 불량, 야간 조도 기준 미달","photo":""},
        {"name":"인왕산터널 소화기함","lat":37.580,"lng":126.959,"type":"소방시설","status":"양호","last_check":"2025-11","grade":"A","issue":"정상","photo":""},
        {"name":"인왕산터널 유도등","lat":37.581,"lng":126.957,"type":"조명시설","status":"주의","last_check":"2025-09","grade":"C","issue":"비상유도등 2기 휘도 저하","photo":""},
        {"name":"신림역 과속방지턱","lat":37.485,"lng":126.928,"type":"과속방지시설","status":"양호","last_check":"2025-10","grade":"B","issue":"도색 마모, 재도색 권고","photo":""},
        {"name":"사당역 횡단보도 조명","lat":37.478,"lng":126.981,"type":"조명시설","status":"교체필요","last_check":"2025-07","grade":"D","issue":"횡단보도 조명 2기 불량, 야간 보행자 안전 위협","photo":""},
        {"name":"우면산터널 배수로","lat":37.474,"lng":126.990,"type":"배수시설","status":"주의","last_check":"2025-08","grade":"C","issue":"2011 산사태 이후 배수로 토사 퇴적 확인","photo":""},
        {"name":"성산대교 이음장치","lat":37.549,"lng":126.911,"type":"교량시설","status":"주의","last_check":"2025-09","grade":"C","issue":"신축이음장치 마모, 우천 시 소음·진동 발생","photo":""},
        {"name":"내부순환 정릉 방음벽","lat":37.604,"lng":127.009,"type":"방음벽","status":"양호","last_check":"2025-10","grade":"B","issue":"기능 정상, 청소 필요","photo":""},
        {"name":"광화문 보도블록","lat":37.573,"lng":126.976,"type":"보행시설","status":"주의","last_check":"2025-09","grade":"C","issue":"블록 들뜸 3개소, 보행자 전도 위험","photo":""},
    ]
    
    # 반경 필터링
    filtered = []
    for f in facilities:
        dlat = abs(f["lat"] - lat)
        dlng = abs(f["lng"] - lng)
        if dlat <= radius and dlng <= radius:
            filtered.append(f)
    
    # 통계
    stats = {"total":len(filtered),"양호":0,"주의":0,"교체필요":0}
    for f in filtered:
        if f["status"] in stats: stats[f["status"]] += 1
    
    return {
        "status": "sample",
        "message": "도로안전시설 점검 데이터 (샘플). data.go.kr 국토교통부_도로시설물현황 API 연동 가능",
        "stats": stats,
        "data": filtered
    }


# ============================================
#  7) 시스템 상태 확인
# ============================================
@app.get("/api/status")
async def status():
    """API 연결 상태 확인"""
    return {
        "claude_ai": "connected" if ANTHROPIC_API_KEY != "여기에_API_키_입력" else "no_key",
        "weather": "connected" if WEATHER_API_KEY else "sample",
        "taas": "connected" if TAAS_API_KEY else "sample",
        "dem": "connected" if DEM_API_KEY else "sample",
        "cctv": "connected" if ITS_CCTV_KEY else "sample",
        "vworld": "connected" if VWORLD_API_KEY else "unavailable",
        "safety": "sample",
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
    print(f"  🗺️  VWorld 지도 : {'✅ 연결됨' if VWORLD_API_KEY else '❌ API 키 필요'}")
    print(f"  🌧️  기상청 ASOS : {'✅ 연결됨' if WEATHER_API_KEY else '⬜ 샘플 데이터'}")
    print(f"  🚗 TAAS 사고   : {'✅ 연결됨' if TAAS_API_KEY else '⬜ 샘플 데이터'}")
    print(f"  ⛰️  국토정보 DEM: {'✅ 연결됨' if DEM_API_KEY else '⬜ 샘플 데이터'}")
    print(f"  📹 ITS CCTV    : {'✅ 연결됨' if ITS_CCTV_KEY else '⬜ 샘플 데이터'}")
    print(f"  🔧 안전시설 점검: ⬜ 샘플 데이터 (data.go.kr 연동 예정)")
    print()
    if not key_ok:
        print("  ⚠️  app.py에서 ANTHROPIC_API_KEY를 설정하세요!")
        print()
    print("  🌐 http://localhost:8000 에서 실행")
    print("=" * 55)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
