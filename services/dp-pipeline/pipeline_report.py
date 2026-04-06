"""Pipeline verification report — Naver Panorama + guidance text comparison.

Usage:
    # 1. Start dp-pipeline server
    uvicorn main:app --port 8000

    # 2. Generate report (--serve required for Naver Panorama)
    python pipeline_report.py 37.497942 127.027621 37.500571 127.036450 "역삼역" --serve
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from datetime import datetime
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import httpx

API_URL = "http://localhost:8000/api/route"
NAVER_CLIENT_ID = "p1w5pdggbh"


def fetch_route(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float, dest_name: str,
) -> dict:
    resp = httpx.post(API_URL, json={
        "origin_lat": origin_lat, "origin_lng": origin_lng,
        "dest_lat": dest_lat, "dest_lng": dest_lng, "dest_name": dest_name,
    }, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "ERROR":
        raise RuntimeError(f"API error: {data.get('error')}")
    return data["data"]


def dp_type_badge(dp_type: str) -> str:
    colors = {
        "DEPARTURE": "#4CAF50", "ARRIVAL": "#F44336", "DIRECTION_CHANGE": "#FF9800",
        "CROSSWALK": "#2196F3", "VERTICAL_MOVE": "#9C27B0", "VIRTUAL": "#607D8B",
    }
    c = colors.get(dp_type, "#999")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold">{dp_type}</span>'


def landmark_info(lm: dict | None) -> str:
    if not lm:
        return '<span style="color:#999">없음 (fallback)</span>'
    sc = {"MATCHED": "#4CAF50", "POI_ONLY": "#FF9800", "VISION_ONLY": "#2196F3"}
    s = lm.get("match_status", "?")
    return (
        f'<strong>{lm["name"]}</strong> '
        f'<span style="background:{sc.get(s,"#999")};color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">{s}</span><br>'
        f'{lm.get("category_code","?")} | {lm.get("position","?")} | '
        f'{lm.get("distance",0):.1f}m | score {lm.get("score",0):.4f} | '
        f'영업 {"O" if lm.get("is_open") else "X"}'
    )


def build_html(route: dict) -> str:
    dps = route.get("decision_points", [])
    coords = route.get("route_line_string", [])
    total_dist = route.get("total_distance", 0)
    total_time = route.get("total_time", 0)
    weather = route.get("weather", "UNKNOWN")
    dest_name = route.get("dest_name", "")
    route_id = route.get("route_id", "")

    type_counts: dict[str, int] = {}
    for dp in dps:
        type_counts[dp["dp_type"]] = type_counts.get(dp["dp_type"], 0) + 1
    type_summary = " | ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))

    dp_cards = []
    for i, dp in enumerate(dps):
        guidance = dp.get("guidance", {})
        pr = dp.get("panorama_request")
        lm = dp.get("selected_landmark")
        tt = dp.get("turn_type")

        def is_primary_dir(label):
            return pr and any(d.get("is_primary") and d.get("label") == label for d in (pr.get("directions") or []))

        card = f"""
        <div class="dp-card" id="dp-{i}">
            <div class="dp-header">
                <span class="dp-index">DP [{i}]</span>
                {dp_type_badge(dp["dp_type"])}
                <span class="turn-type">turnType: {tt if tt is not None else "null"}</span>
                <span class="distance">{dp.get("distance_from_start", 0):.1f}m</span>
            </div>

            <div class="dp-info">
                <div class="info-item">
                    <h4>선택된 랜드마크</h4>
                    <p>{landmark_info(lm)}</p>
                </div>
                <div class="info-item">
                    <h4>안내 문구</h4>
                    <div class="guidance">
                        <div class="guidance-primary">{guidance.get("primary", "-")}</div>
                        {"<div class='guidance-prealert'>Pre-alert: " + guidance.get("pre_alert","") + "</div>" if guidance.get("pre_alert") else ""}
                        {"<div class='guidance-action'>Action: " + guidance.get("action","") + "</div>" if guidance.get("action") else ""}
                    </div>
                </div>
            </div>

            <div class="pano-row">
                <div class="pano-cell">
                    <div class="pano-label{"  pano-primary" if is_primary_dir("FRONT") else ""}">FRONT{"  *" if is_primary_dir("FRONT") else ""}</div>
                    <div class="pano-viewer" id="pano-{i}-front"></div>
                </div>
                <div class="pano-cell">
                    <div class="pano-label{"  pano-primary" if is_primary_dir("LEFT") else ""}">LEFT{"  *" if is_primary_dir("LEFT") else ""}</div>
                    <div class="pano-viewer" id="pano-{i}-left"></div>
                </div>
                <div class="pano-cell">
                    <div class="pano-label{"  pano-primary" if is_primary_dir("RIGHT") else ""}">RIGHT{"  *" if is_primary_dir("RIGHT") else ""}</div>
                    <div class="pano-viewer" id="pano-{i}-right"></div>
                </div>
            </div>
        </div>"""
        dp_cards.append(card)

    dps_json = json.dumps(dps, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pipeline Report — {dest_name or route_id}</title>
    <script src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpClientId={NAVER_CLIENT_ID}&submodules=panorama"></script>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f5f5; color:#333; }}
        .header {{ background:#1a1a2e; color:#fff; padding:24px 32px; }}
        .header h1 {{ font-size:24px; margin-bottom:8px; }}
        .header .meta {{ font-size:14px; color:#aaa; }}
        .summary {{ background:#fff; margin:16px 32px; padding:20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
        .summary h2 {{ font-size:18px; margin-bottom:12px; }}
        .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
        .summary-item {{ background:#f8f9fa; padding:12px; border-radius:6px; }}
        .summary-item .label {{ font-size:12px; color:#666; }}
        .summary-item .value {{ font-size:20px; font-weight:bold; margin-top:4px; }}
        .checklist {{ background:#fff; margin:16px 32px; padding:20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
        .checklist h2 {{ font-size:18px; margin-bottom:12px; }}
        .check-item {{ padding:6px 0; border-bottom:1px solid #f0f0f0; font-size:14px; }}
        .check-ok {{ color:#4CAF50; }} .check-warn {{ color:#FF9800; }} .check-fail {{ color:#F44336; }}
        .dp-list {{ padding:0 32px 32px; }}
        .dp-card {{ background:#fff; margin:16px 0; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); overflow:hidden; }}
        .dp-header {{ background:#f8f9fa; padding:12px 20px; display:flex; align-items:center; gap:12px; border-bottom:1px solid #eee; flex-wrap:wrap; }}
        .dp-index {{ font-weight:bold; font-size:16px; }}
        .turn-type {{ color:#666; font-size:13px; }}
        .distance {{ color:#666; font-size:13px; margin-left:auto; }}
        .dp-info {{ padding:16px 20px; display:flex; gap:20px; }}
        .info-item {{ flex:1; }}
        .info-item h4 {{ font-size:13px; color:#555; margin-bottom:6px; border-bottom:1px solid #eee; padding-bottom:4px; }}
        .info-item p {{ font-size:13px; line-height:1.6; }}
        .guidance {{ background:#f0f7ff; padding:12px; border-radius:6px; border-left:3px solid #2196F3; }}
        .guidance-primary {{ font-size:16px; font-weight:500; }}
        .guidance-prealert {{ font-size:13px; color:#555; margin-top:6px; }}
        .guidance-action {{ font-size:13px; color:#888; margin-top:4px; }}
        .pano-row {{ display:flex; gap:6px; padding:0 20px 16px; }}
        .pano-cell {{ flex:1; }}
        .pano-label {{ font-size:11px; font-weight:bold; text-align:center; background:#555; color:#fff; padding:4px; border-radius:4px 4px 0 0; }}
        .pano-primary {{ background:#E53935; }}
        .pano-viewer {{ width:100%; height:240px; background:#e8e8e8; border:1px solid #ccc; border-radius:0 0 4px 4px; display:flex; align-items:center; justify-content:center; color:#999; font-size:12px; }}
        @media (max-width:768px) {{ .dp-info {{ flex-direction:column; }} .pano-row {{ flex-direction:column; }} .pano-viewer {{ height:200px; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Pipeline Verification Report</h1>
        <div class="meta">Route: {route_id} | {dest_name} | {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
    </div>

    <div class="summary">
        <h2>경로 요약</h2>
        <div class="summary-grid">
            <div class="summary-item"><div class="label">총 거리</div><div class="value">{total_dist:.0f}m</div></div>
            <div class="summary-item"><div class="label">예상 시간</div><div class="value">{total_time/60:.1f}분</div></div>
            <div class="summary-item"><div class="label">날씨</div><div class="value">{weather}</div></div>
            <div class="summary-item"><div class="label">DP 수</div><div class="value">{len(dps)}개</div></div>
            <div class="summary-item"><div class="label">유형별</div><div class="value" style="font-size:13px">{type_summary}</div></div>
        </div>
    </div>

    <div class="checklist">
        <h2>자동 검증</h2>
        <div id="checks"></div>
    </div>

    <div class="dp-list">
        <h2 style="margin:16px 0;font-size:20px">Decision Points</h2>
        {"".join(dp_cards)}
    </div>

    <script>
    const dps = {dps_json};

    function runChecks() {{
        const C=[];
        const hD=dps.some(d=>d.dp_type==='DEPARTURE'), hA=dps.some(d=>d.dp_type==='ARRIVAL');
        C.push({{t:'DEPARTURE+ARRIVAL 존재',ok:hD&&hA,d:hD&&hA?'정상':'누락!'}});
        C.push({{t:'첫 DP=DEPARTURE',ok:dps[0]?.dp_type==='DEPARTURE',d:dps[0]?.dp_type}});
        C.push({{t:'마지막 DP=ARRIVAL',ok:dps[dps.length-1]?.dp_type==='ARRIVAL',d:dps[dps.length-1]?.dp_type}});
        let s=true; for(let i=1;i<dps.length;i++) if(dps[i].distance_from_start<dps[i-1].distance_from_start){{s=false;break;}}
        C.push({{t:'distance_from_start 정렬',ok:s,d:s?'정상':'오류!'}});
        const eG=dps.filter(d=>!d.guidance?.primary);
        C.push({{t:'모든 DP primary 문구',ok:eG.length===0,d:eG.length===0?'정상':`${{eG.length}}개 누락`}});
        const dc=dps.filter(d=>d.dp_type==='DIRECTION_CHANGE'), nA=dc.filter(d=>!d.guidance?.action);
        C.push({{t:'DIRECTION_CHANGE action',ok:nA.length===0,d:dc.length===0?'해당없음':nA.length===0?`${{dc.length}}개 정상`:`${{nA.length}}개 누락`}});
        const el=dps.filter(d=>d.dp_type!=='DEPARTURE'&&d.dp_type!=='ARRIVAL');
        const wL=el.filter(d=>d.selected_landmark);
        const r=el.length>0?(wL.length/el.length*100).toFixed(0):100;
        C.push({{t:'랜드마크 선택률',ok:r>=50,w:r>=30&&r<50,d:`${{wL.length}}/${{el.length}} (${{r}}%)`}});
        let co=false; for(let i=1;i<dps.length;i++){{const p=dps[i-1].selected_landmark?.name,c=dps[i].selected_landmark?.name;if(p&&c&&p===c){{co=true;break;}}}}
        C.push({{t:'연속 같은 랜드마크 없음',ok:!co,d:co?'중복!':'정상'}});
        let pO=true; const lT=new Set([12,16,17,212,214,215]),rT=new Set([13,18,19,213,216,217]);
        for(const dp of dps){{if(!dp.panorama_request?.directions)continue;const pr=dp.panorama_request.directions.find(d=>d.is_primary);if(!pr)continue;if(lT.has(dp.turn_type)&&pr.label!=='LEFT')pO=false;if(rT.has(dp.turn_type)&&pr.label!=='RIGHT')pO=false;}}
        C.push({{t:'isPrimary-turnType 정합성',ok:pO,d:pO?'정상':'불일치!'}});
        const ct=document.getElementById('checks');
        for(const c of C){{const cls=c.ok?'check-ok':(c.w?'check-warn':'check-fail');const ic=c.ok?'OK':(c.w?'!!':'XX');ct.innerHTML+=`<div class="check-item ${{cls}}">[${{ic}}] ${{c.t}} — <em>${{c.d}}</em></div>`;}}
    }}

    runChecks();

    // --- Naver Panorama ---
    dps.forEach((dp,idx)=>{{
        const pr=dp.panorama_request;
        if(!pr||!pr.directions) return;
        const lat=pr.location?.latitude||dp.location?.latitude||0;
        const lng=pr.location?.longitude||dp.location?.longitude||0;
        const position=new naver.maps.LatLng(lat,lng);
        const panMap={{}};
        pr.directions.forEach(d=>{{panMap[d.label.toLowerCase()]=d.pan;}});

        ['front','left','right'].forEach(dir=>{{
            const el=document.getElementById(`pano-${{idx}}-${{dir}}`);
            if(!el) return;
            const pan=panMap[dir]??0;
            try {{
                const pano=new naver.maps.Panorama(el,{{
                    position:position, pov:{{pan:pan,tilt:0,fov:100}},
                    flightSpot:false, aroundControl:true, zoomControl:false
                }});
                naver.maps.Event.addListener(pano,'error',()=>{{
                    el.textContent=`파노라마 없음 (${{lat.toFixed(4)}}, ${{lng.toFixed(4)}})`;
                    el.style.display='flex';
                }});
            }} catch(e) {{ el.textContent='로드 실패'; }}
        }});
    }});
    </script>
</body>
</html>"""


def serve_report(directory: str, port: int = 8080) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    server = HTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}/report.html"
    print(f"Serving at {url}")
    print("   Ctrl+C to stop.")
    threading.Timer(0.5, webbrowser.open, args=[url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


def main():
    args = [a for a in sys.argv[1:] if a != "--serve"]
    do_serve = "--serve" in sys.argv
    if len(args) < 4:
        print('Usage: python pipeline_report.py <lat> <lng> <lat> <lng> [name] [--serve]')
        print('  python pipeline_report.py 37.497942 127.027621 37.500571 127.036450 "역삼역" --serve')
        sys.exit(1)

    o_lat, o_lng = float(args[0]), float(args[1])
    d_lat, d_lng = float(args[2]), float(args[3])
    d_name = args[4] if len(args) > 4 else ""

    print(f"Fetching route: ({o_lat},{o_lng}) -> ({d_lat},{d_lng}) [{d_name}]")
    route = fetch_route(o_lat, o_lng, d_lat, d_lng, d_name)

    html = build_html(route)
    out = Path("report.html")
    out.write_text(html, encoding="utf-8")
    print(f"Report saved: {out.resolve()}")
    print(f"   DPs: {len(route.get('decision_points',[]))}, Distance: {route.get('total_distance',0):.0f}m")

    if do_serve:
        serve_report(str(out.parent), port=8080)
    else:
        print("   --serve 추가하면 파노라마가 표시됩니다.")


if __name__ == "__main__":
    main()
