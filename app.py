"""
========================================================
  기능성 포장 필요구간 자동 탐색 플랫폼 — 백엔드 서버 v1.3
========================================================
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx
import ssl
import os
from datetime import datetime, timedelta

# ============================================
#  API 키 (Render 환경변수)
# ============================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "여기에_API_키_입력")
VWORLD_API_KEY    = os.getenv("VWORLD_API_KEY", "")
DATA_GO_KR_KEY    = os.getenv("DATA_GO_KR_KEY", "")
SEOUL_DATA_KEY    = os.getenv("SEOUL_DATA_KEY", "")
ITS_CCTV_KEY      = os.getenv("ITS_CCTV_KEY", "")

app = FastAPI(title="기능성 포장 플랫폼 API", version="1.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# SSL 컨텍스트 생성 (인증서 검증 비활성화)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

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
#  TOPIS 서울시 실시간 교통
# ============================================
@app.get("/api/traffic/realtime")
async def get_realtime_traffic(start_idx: int = 1, end_idx: int = 100):
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
#  ITS CCTV (v1.3 - 타임아웃/SSL 문제 해결)
# ============================================
@app.get("/api/cctv")
async def get_cctv(lat: float = 37.55, lng: float = 126.98, radius: float = 0.15, cctv_type: str = "its"):
    """ITS CCTV 정보 조회 - 타임아웃 시 샘플 데이터 반환"""
    
    # 샘플 데이터 (서울시 주요 지점)
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
        {"name":"사당역","lat":37.478,"lng":126.983,"url":"","format":"image"}
    ]
    
    if not ITS_CCTV_KEY:
        return {"status":"sample","message":"ITS CCTV API 키 미설정","count":len(samples),"data":samples}
    
    try:
        min_x = lng - radius
        max_x = lng + radius
        min_y = lat - radius
        max_y = lat + radius
        
        # 타임아웃을 60초로 늘리고 SSL 검증 비활성화
        async with httpx.AsyncClient(timeout=60.0, verify=ssl_context) as c:
            url = "https://openapi.its.go.kr:9443/cctvInfo"
            params = {
                "apiKey": ITS_CCTV_KEY,
                "type": cctv_type,
                "cctvType": "2",
                "minX": str(min_x),
                "maxX": str(max_x),
                "minY": str(min_y),
                "maxY": str(max_y),
                "getType": "json"
            }
            
            r = await c.get(url, params=params)
            
            if r.status_code != 200:
                return {"status":"sample","message":f"ITS API 응답 오류 ({r.status_code}) - 샘플 사용","count":len(samples),"data":samples}
            
            try:
                data = r.json()
            except:
                return {"status":"sample","message":"JSON 파싱 오류 - 샘플 사용","count":len(samples),"data":samples}
            
            cctvs = []
            response_data = data.get("response", {})
            
            if "data" in response_data:
                items = response_data["data"]
                if items is None:
                    items = []
                elif not isinstance(items, list):
                    items = [items]
                    
                for item in items:
                    try:
                        cctv_info = {
                            "name": item.get("cctvname", "이름없음"),
                            "lat": float(item.get("coordy", 0)),
                            "lng": float(item.get("coordx", 0)),
                            "url": item.get("cctvurl", ""),
                            "format": item.get("cctvformat", ""),
                            "road": item.get("roadsectionid", "")
                        }
                        if cctv_info["lat"] != 0 and cctv_info["lng"] != 0:
                            cctvs.append(cctv_info)
                    except:
                        continue
            
            # 결과 없으면 'ex' (고속도로) 타입으로 재시도
            if len(cctvs) == 0:
                params["type"] = "ex"
                try:
                    r2 = await c.get(url, params=params)
                    if r2.status_code == 200:
                        data2 = r2.json()
                        response_data2 = data2.get("response", {})
                        if "data" in response_data2:
                            items2 = response_data2["data"]
                            if items2 is None:
                                items2 = []
                            elif not isinstance(items2, list):
                                items2 = [items2]
                            for item in items2:
                                try:
                                    cctv_info = {
                                        "name": item.get("cctvname", "이름없음"),
                                        "lat": float(item.get("coordy", 0)),
                                        "lng": float(item.get("coordx", 0)),
                                        "url": item.get("cctvurl", ""),
                                        "format": item.get("cctvformat", ""),
                                        "road": item.get("roadsectionid", "")
                                    }
                                    if cctv_info["lat"] != 0 and cctv_info["lng"] != 0:
                                        cctvs.append(cctv_info)
                                except:
                                    continue
                except:
                    pass
            
            # 여전히 결과 없으면 샘플 반환
            if len(cctvs) == 0:
                return {"status":"sample","message":"해당 영역에 CCTV 없음 - 샘플 사용","count":len(samples),"data":samples}
            
            return {"status":"live","count":len(cctvs),"search_area":{"lat":lat,"lng":lng,"radius":radius},"data":cctvs}
            
    except httpx.TimeoutException:
        # 타임아웃 시 샘플 데이터 반환 (에러 대신)
        return {"status":"sample","message":"ITS API 타임아웃 - 샘플 사용","count":len(samples),"data":samples}
    except Exception as e:
        # 기타 에러 시에도 샘플 데이터 반환
        return {"status":"sample","message":f"연결 오류: {str(e)[:50]} - 샘플 사용","count":len(samples),"data":samples}

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
    uvicorn.run(app, host="0.0.0.0", port=8000)
