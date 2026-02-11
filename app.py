"""
========================================================
  기능성 포장 필요구간 자동 탐색 플랫폼 — 백엔드 서버 v1.1
========================================================
  통합 공공 API:
    - VWorld 배경지도/DEM (국토정보플랫폼)
    - ASOS 기상관측 (기상청, data.go.kr)
    - TAAS 교통사고 (도로교통공단, data.go.kr)
    - TOPIS 실시간 교통 (서울시 열린데이터광장)
    - ITS CCTV (its.go.kr)
    - Claude AI N2B 분석
========================================================
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx
import os
from datetime import datetime, timedelta

# ============================================
#  API 키 (Render 환경변수)
# ============================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "여기에_API_키_입력")
VWORLD_API_KEY    = os.getenv("VWORLD_API_KEY", "")
DATA_GO_KR_KEY    = os.getenv("DATA_GO_KR_KEY", "")      # ASOS + TAAS 공용
SEOUL_DATA_KEY    = os.getenv("SEOUL_DATA_KEY", "")        # 서울 열린데이터광장
ITS_CCTV_KEY      = os.getenv("ITS_CCTV_KEY", "")

app = FastAPI(title="기능성 포장 플랫폼 API", version="1.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============================================
#  VWorld 지도 API
# ============================================
@app.get("/api/vworld/tile-info")
async def get_vworld_tile_info():
    if VWORLD_API_KEY:
        return {
            "status": "live",
            "base": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
            "satellite": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
            "hybrid": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/Hybrid/{{z}}/{{y}}/{{x}}.png",
            "midnight": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/midnight/{{z}}/{{y}}/{{x}}.png",
            "white": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/white/{{z}}/{{y}}/{{x}}.png",
        }
    return {"status": "unavailable"}

@app.get("/api/vworld/geocode")
async def geocode(address: str):
    if not VWORLD_API_KEY: return {"status": "error", "message": "VWorld 키 미설정"}
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("https://api.vworld.kr/req/address", params={"service":"address","request":"getcoord","key":VWORLD_API_KEY,"address":address,"type":"road","format":"json"})
        return r.json()

@app.get("/api/vworld/reverse-geocode")
async def reverse_geocode(lat: float, lng: float):
    if not VWORLD_API_KEY: return {"status": "error", "message": "VWorld 키 미설정"}
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("https://api.vworld.kr/req/address", params={"service":"address","request":"getaddr","key":VWORLD_API_KEY,"point":f"{lng},{lat}","type":"road","format":"json"})
        return r.json()

# ============================================
#  Claude AI 분석
# ============================================
@app.post("/api/analyze")
async def analyze(request: Request):
    body = await request.json()
    if ANTHROPIC_API_KEY == "여기에_API_키_입력":
        return JSONResponse(status_code=400, content={"error": "API 키 미설정"})
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post("https://api.anthropic.com/v1/messages", headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
            json={"model":body.get("model","claude-sonnet-4-20250514"),"max_tokens":body.get("max_tokens",1000),"messages":body.get("messages",[])})
        return r.json()

# ============================================
#  기상청 ASOS (data.go.kr)
# ============================================
@app.get("/api/weather/{station_id}")
async def get_weather(station_id: str, date: str = ""):
    """ASOS 시간자료 - station_id: 108=서울"""
    if DATA_GO_KR_KEY:
        if not date: date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get("http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList",
                    params={"serviceKey":DATA_GO_KR_KEY,"numOfRows":"24","pageNo":"1","dataType":"JSON","dataCd":"ASOS","dateCd":"HR","stnIds":station_id,"startDt":date,"startHh":"00","endDt":date,"endHh":"23"})
                data = r.json()
                items = []
                try:
                    for item in data["response"]["body"]["items"]["item"]:
                        items.append({"time":item.get("tm",""),"temp":item.get("ta",""),"rain":item.get("rn",""),"humidity":item.get("hm",""),"wind_speed":item.get("ws","")})
                except: pass
                return {"status":"live","station_id":station_id,"date":date,"count":len(items),"data":items}
        except Exception as e:
            return {"status":"error","message":str(e)}
    return {"status":"sample","data":{"station_id":station_id,"annual_heavy_rain_days":42,"monthly_rain":[22,28,45,62,88,133,394,348,145,52,35,18]}}

@app.get("/api/weather-daily/{station_id}")
async def get_weather_daily(station_id: str, start_date: str = "", end_date: str = ""):
    """ASOS 일자료"""
    if DATA_GO_KR_KEY:
        if not end_date: end_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        if not start_date: start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get("http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList",
                    params={"serviceKey":DATA_GO_KR_KEY,"numOfRows":"31","pageNo":"1","dataType":"JSON","dataCd":"ASOS","dateCd":"DAY","stnIds":station_id,"startDt":start_date,"endDt":end_date})
                data = r.json()
                items = []
                try:
                    for item in data["response"]["body"]["items"]["item"]:
                        items.append({"date":item.get("tm",""),"avg_temp":item.get("avgTa",""),"max_temp":item.get("maxTa",""),"min_temp":item.get("minTa",""),"rain_total":item.get("sumRn",""),"avg_humidity":item.get("avgRhm","")})
                except: pass
                return {"status":"live","period":f"{start_date}~{end_date}","count":len(items),"data":items}
        except Exception as e:
            return {"status":"error","message":str(e)}
    return {"status":"sample","message":"data.go.kr 키 미설정"}

# ============================================
#  TAAS 교통사고 (data.go.kr)
# ============================================
@app.get("/api/accident/{region_code}")
async def get_accident(region_code: str, year: str = "2024"):
    """사고유형별 교통사고 통계 - region_code: 11=서울"""
    if DATA_GO_KR_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get("http://apis.data.go.kr/B552061/AccidentDeath/getRestTrafficAccidentDeath",
                    params={"serviceKey":DATA_GO_KR_KEY,"searchYearCd":year,"siDo":region_code,"numOfRows":"50","pageNo":"1","type":"json"})
                data = r.json()
                items = []
                try:
                    raw = data.get("items",{}).get("item",[])
                    if isinstance(raw, dict): raw = [raw]
                    for item in raw:
                        items.append({"type":item.get("acc_ty_nm",""),"accidents":item.get("occrrnc_cnt",0),"deaths":item.get("dth_dnv_cnt",0),"injuries":item.get("injpsn_cnt",0)})
                except: pass
                return {"status":"live","region":region_code,"year":year,"count":len(items),"data":items,"raw":data}
        except Exception as e:
            return {"status":"error","message":str(e)}
    return {"status":"sample","data":{"region":region_code,"total_accidents_rainy":847,"fatalities_rainy":23,"wet_road_accident_rate":0.23,
        "top_accident_spots":[{"name":"남산순환로","count":8},{"name":"한남IC","count":9},{"name":"동작대교램프","count":7}]}}

# ============================================
#  TOPIS 서울시 실시간 교통 (열린데이터광장)
# ============================================
@app.get("/api/traffic/realtime")
async def get_realtime_traffic(start_idx: int = 1, end_idx: int = 100):
    """서울시 실시간 도로 소통 정보"""
    if SEOUL_DATA_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(f"http://openapi.seoul.go.kr:8088/{SEOUL_DATA_KEY}/json/TrafficInfo/{start_idx}/{end_idx}/")
                data = r.json()
                items = []
                try:
                    for item in data.get("TrafficInfo",{}).get("row",[]):
                        items.append({"road_name":item.get("road_nm",""),"direction":item.get("road_nm_dir",""),"speed":item.get("spd",0),
                            "travel_time":item.get("travel_time",0),"start_name":item.get("start_nd_nm",""),"end_name":item.get("end_nd_nm","")})
                except: pass
                return {"status":"live","timestamp":datetime.now().isoformat(),"count":len(items),"data":items}
        except Exception as e:
            return {"status":"error","message":str(e)}
    return {"status":"sample","data":[
        {"road_name":"남산순환로","speed":25,"status":"정체"},{"road_name":"올림픽대로","speed":55,"status":"서행"},
        {"road_name":"강남대로","speed":18,"status":"정체"},{"road_name":"내부순환로","speed":42,"status":"서행"},{"road_name":"강변북로","speed":65,"status":"원활"}]}

# ============================================
#  침수 사전 경보 시스템
# ============================================
# 서울시 침수 선행 지표 구간 (과거 침수흔적도 기반 - 가장 먼저 침수되는 구간)
FLOOD_INDICATOR_ZONES = [
    {"id": "FZ001", "name": "신림역 지하차도", "lat": 37.4842, "lng": 126.9293, "priority": 1, "threshold_rain": 30, "history": "2022년, 2020년, 2011년 침수"},
    {"id": "FZ002", "name": "강남역 사거리", "lat": 37.4979, "lng": 127.0276, "priority": 1, "threshold_rain": 35, "history": "2022년, 2011년 침수"},
    {"id": "FZ003", "name": "대림역 일대", "lat": 37.4925, "lng": 126.8958, "priority": 1, "threshold_rain": 30, "history": "2020년, 2011년 침수"},
    {"id": "FZ004", "name": "사당역 지하차도", "lat": 37.4765, "lng": 126.9816, "priority": 2, "threshold_rain": 40, "history": "2011년 침수"},
    {"id": "FZ005", "name": "도림천 광신대교", "lat": 37.4912, "lng": 126.9089, "priority": 1, "threshold_rain": 25, "history": "2022년, 2020년 침수"},
    {"id": "FZ006", "name": "구로디지털단지역", "lat": 37.4854, "lng": 126.9015, "priority": 2, "threshold_rain": 35, "history": "2020년 침수"},
    {"id": "FZ007", "name": "잠원IC 진입로", "lat": 37.5186, "lng": 127.0052, "priority": 2, "threshold_rain": 40, "history": "2022년 침수"},
    {"id": "FZ008", "name": "반포IC 지하차도", "lat": 37.5053, "lng": 127.0108, "priority": 1, "threshold_rain": 30, "history": "2022년, 2011년 침수"},
]

@app.get("/api/flood/zones")
async def get_flood_zones():
    """침수 선행 지표 구간 목록"""
    return {"status": "success", "count": len(FLOOD_INDICATOR_ZONES), "zones": FLOOD_INDICATOR_ZONES}

@app.get("/api/flood/warning")
async def get_flood_warning():
    """침수 사전 경보 - 실시간 강우량 기반"""
    warnings = []
    current_rain = 0
    rain_status = "정상"
    
    # 실시간 강우량 확인 (ASOS)
    if DATA_GO_KR_KEY:
        try:
            today = datetime.now().strftime("%Y%m%d")
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList",
                    params={"serviceKey": DATA_GO_KR_KEY, "numOfRows": "1", "dataType": "JSON",
                            "dataCd": "ASOS", "dateCd": "HR", "startDt": today, "startHh": "00",
                            "endDt": today, "endHh": "23", "stnIds": "108"})
                data = r.json()
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if items:
                    last_item = items[-1] if isinstance(items, list) else items
                    rain_str = last_item.get("rn", "0")
                    current_rain = float(rain_str) if rain_str and rain_str != "" else 0
        except:
            pass
    
    # 경보 레벨 결정
    for zone in FLOOD_INDICATOR_ZONES:
        zone_warning = {
            "zone_id": zone["id"],
            "zone_name": zone["name"],
            "lat": zone["lat"],
            "lng": zone["lng"],
            "priority": zone["priority"],
            "threshold": zone["threshold_rain"],
            "current_rain": current_rain,
            "history": zone["history"],
            "level": "정상",
            "message": ""
        }
        
        if current_rain >= zone["threshold_rain"]:
            zone_warning["level"] = "🚨 위험"
            zone_warning["message"] = f"침수 임박! 즉시 우회 필요"
            rain_status = "위험"
        elif current_rain >= zone["threshold_rain"] * 0.7:
            zone_warning["level"] = "⚠️ 경고"
            zone_warning["message"] = f"침수 가능성 높음, 주의 필요"
            if rain_status != "위험":
                rain_status = "경고"
        elif current_rain >= zone["threshold_rain"] * 0.5:
            zone_warning["level"] = "🔔 주의"
            zone_warning["message"] = f"강우량 증가 중, 모니터링 필요"
            if rain_status not in ["위험", "경고"]:
                rain_status = "주의"
        else:
            zone_warning["level"] = "✅ 정상"
            zone_warning["message"] = "현재 침수 위험 없음"
        
        warnings.append(zone_warning)
    
    # 우선순위 1인 구간 중 위험/경고 상태 필터
    priority1_alerts = [w for w in warnings if w["priority"] == 1 and w["level"] in ["🚨 위험", "⚠️ 경고"]]
    
    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "current_rain_mm": current_rain,
        "overall_status": rain_status,
        "total_zones": len(warnings),
        "alert_zones": len([w for w in warnings if w["level"] != "✅ 정상"]),
        "priority1_alerts": len(priority1_alerts),
        "warnings": warnings,
        "message": f"현재 강우량 {current_rain}mm - " + (
            "🚨 침수 위험 구간 발생! 우회 권장" if rain_status == "위험" else
            "⚠️ 일부 구간 침수 경고" if rain_status == "경고" else
            "🔔 강우량 증가 중, 모니터링 필요" if rain_status == "주의" else
            "✅ 전 구간 정상"
        )
    }

# ============================================
#  ITS CCTV 이미지 프록시
# ============================================
@app.get("/api/cctv-image")
async def get_cctv_image(url: str):
    """CCTV 이미지 프록시 - CORS 우회"""
    import urllib.parse
    try:
        # URL 디코딩 (이중 인코딩 방지)
        decoded_url = urllib.parse.unquote(url)
        async with httpx.AsyncClient(timeout=15.0, verify=False, follow_redirects=True) as c:
            r = await c.get(decoded_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "http://www.its.go.kr/",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
            })
            if r.status_code == 200:
                from fastapi.responses import Response
                content_type = r.headers.get("content-type", "image/jpeg")
                return Response(content=r.content, media_type=content_type)
            return JSONResponse(status_code=r.status_code, content={"error": f"Status {r.status_code}", "url": decoded_url[:100]})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ============================================
#  ITS CCTV
# ============================================
@app.get("/api/cctv")
async def get_cctv(lat: float = 37.55, lng: float = 126.98, radius: float = 0.2):
    if ITS_CCTV_KEY:
        try:
            async with httpx.AsyncClient(timeout=60.0, verify=False) as c:
                r = await c.get("https://openapi.its.go.kr:9443/cctvInfo",
                    params={"apiKey":ITS_CCTV_KEY,"type":"ex","cctvType":"1","minX":str(lng-radius),"maxX":str(lng+radius),"minY":str(lat-radius),"maxY":str(lat+radius),"getType":"json"})
                data = r.json(); cctvs = []
                if "response" in data and "data" in data["response"]:
                    for item in data["response"]["data"]:
                        cctvs.append({"name":item.get("cctvname",""),"lat":float(item.get("coordy",0)),"lng":float(item.get("coordx",0)),"url":item.get("cctvurl",""),"format":item.get("cctvformat","")})
                    return {"status":"live","count":len(cctvs),"data":cctvs}
                return {"status":"live","count":0,"data":[],"raw":data}
        except httpx.TimeoutException:
            pass
        except Exception as e:
            return {"status":"error","message":str(e),"key":ITS_CCTV_KEY[:8]+"..."}
    samples = [{"name":"남산1터널 입구","lat":37.553,"lng":126.985,"url":"","format":"image"},{"name":"강남역 교차로","lat":37.498,"lng":127.028,"url":"","format":"image"},
        {"name":"올림픽대로 잠실대교","lat":37.519,"lng":127.078,"url":"","format":"image"},{"name":"북악터널 입구","lat":37.591,"lng":126.968,"url":"","format":"image"},
        {"name":"신림사거리","lat":37.485,"lng":126.930,"url":"","format":"image"},{"name":"인왕산터널","lat":37.580,"lng":126.959,"url":"","format":"image"},
        {"name":"내부순환 정릉입구","lat":37.604,"lng":127.010,"url":"","format":"image"},{"name":"동작대교 남단","lat":37.506,"lng":126.983,"url":"","format":"image"},
        {"name":"한남IC","lat":37.535,"lng":127.002,"url":"","format":"image"},{"name":"사당역","lat":37.478,"lng":126.983,"url":"","format":"image"}]
    return {"status":"sample","message":"ITS CCTV API 키 미설정 → 샘플","count":len(samples),"data":samples}

# ============================================
#  도로안전시설 점검
# ============================================
@app.get("/api/safety-facilities")
async def get_safety_facilities(lat: float = 37.55, lng: float = 126.98, radius: float = 0.05):
    facilities = [
        {"name":"남산순환로 가드레일","lat":37.552,"lng":126.987,"type":"가드레일","status":"양호","last_check":"2025-09","grade":"B","issue":"부분 녹 발생, 도장 필요","photo":""},
        {"name":"남산순환로 시선유도봉","lat":37.550,"lng":126.990,"type":"시선유도시설","status":"교체필요","last_check":"2025-06","grade":"D","issue":"반사체 마모 심각","photo":""},
        {"name":"북악스카이웨이 가드레일","lat":37.594,"lng":126.966,"type":"가드레일","status":"주의","last_check":"2025-08","grade":"C","issue":"곡선부 높이 부족","photo":""},
        {"name":"동작대교 충격흡수시설","lat":37.506,"lng":126.981,"type":"충격흡수시설","status":"교체필요","last_check":"2025-05","grade":"D","issue":"변형, 즉시 교체 필요","photo":""},
        {"name":"한남IC 합류부 표지","lat":37.535,"lng":127.000,"type":"도로표지","status":"주의","last_check":"2025-07","grade":"C","issue":"반사 성능 저하","photo":""},
        {"name":"강남역 배수구","lat":37.497,"lng":127.028,"type":"배수시설","status":"주의","last_check":"2025-09","grade":"C","issue":"낙엽 퇴적, 배수 용량 부족","photo":""},
        {"name":"올림픽대로 조명시설","lat":37.517,"lng":127.076,"type":"조명시설","status":"교체필요","last_check":"2025-08","grade":"D","issue":"LED 3기 불량","photo":""},
        {"name":"사당역 횡단보도 조명","lat":37.478,"lng":126.981,"type":"조명시설","status":"교체필요","last_check":"2025-07","grade":"D","issue":"조명 2기 불량","photo":""},
        {"name":"우면산터널 배수로","lat":37.474,"lng":126.990,"type":"배수시설","status":"주의","last_check":"2025-08","grade":"C","issue":"토사 퇴적","photo":""},
        {"name":"성산대교 이음장치","lat":37.549,"lng":126.911,"type":"교량시설","status":"주의","last_check":"2025-09","grade":"C","issue":"이음장치 마모","photo":""},
        {"name":"광화문 보도블록","lat":37.573,"lng":126.976,"type":"보행시설","status":"주의","last_check":"2025-09","grade":"C","issue":"블록 들뜸 3개소","photo":""},
    ]
    filtered = [f for f in facilities if abs(f["lat"]-lat)<=radius and abs(f["lng"]-lng)<=radius]
    stats = {"total":len(filtered),"양호":0,"주의":0,"교체필요":0}
    for f in filtered:
        if f["status"] in stats: stats[f["status"]] += 1
    return {"status":"sample","stats":stats,"data":filtered}

# ============================================
#  시스템 상태
# ============================================
@app.get("/api/status")
async def status():
    return {
        "claude_ai": "connected" if ANTHROPIC_API_KEY != "여기에_API_키_입력" else "no_key",
        "vworld": "connected" if VWORLD_API_KEY else "unavailable",
        "weather": "connected" if DATA_GO_KR_KEY else "sample",
        "taas": "connected" if DATA_GO_KR_KEY else "sample",
        "topis": "connected" if SEOUL_DATA_KEY else "sample",
        "cctv": "connected" if ITS_CCTV_KEY else "sample",
        "safety": "sample",
    }

@app.get("/")
async def root():
    if os.path.exists("index.html"): return FileResponse("index.html")
    return {"message": "index.html 필요"}

if __name__ == "__main__":
    import uvicorn
    k = ANTHROPIC_API_KEY != "여기에_API_키_입력"
    print("\n" + "="*55)
    print("  🛣️  기능성 포장 플랫폼 v1.1 — 공공 API 통합")
    print("="*55)
    print(f"\n  📡 Claude AI  : {'✅' if k else '❌'}")
    print(f"  🗺️  VWorld     : {'✅' if VWORLD_API_KEY else '❌'}")
    print(f"  🌧️  ASOS 기상  : {'✅' if DATA_GO_KR_KEY else '⬜'}")
    print(f"  🚗 TAAS 사고  : {'✅' if DATA_GO_KR_KEY else '⬜'}")
    print(f"  🚦 TOPIS 교통 : {'✅' if SEOUL_DATA_KEY else '⬜'}")
    print(f"  📹 ITS CCTV   : {'✅' if ITS_CCTV_KEY else '⬜'}")
    print(f"\n  🌐 http://localhost:8000\n{'='*55}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
