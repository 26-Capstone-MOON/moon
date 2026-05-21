import type { DecisionPoint } from '../types/route';

const NCP_KEY_ID = '4gswjhkwyh';

export function buildPanoramaHtml(
  lat: number, lng: number, pan: number,
  landmarkName?: string | null,
  landmarkLat?: number | null, landmarkLng?: number | null,
): string {
  const markerJs = (landmarkName && landmarkLat != null && landmarkLng != null) ? `
var markerPos=new naver.maps.LatLng(${landmarkLat},${landmarkLng});
var marker=new naver.maps.Marker({
  position:markerPos,
  map:pano,
  icon:{
    content:'<div style="display:flex;flex-direction:column;align-items:center;pointer-events:none">'
      +'<div style="background:#f2d202;color:#000;font-size:11px;font-weight:700;padding:3px 8px;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,0.35);white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis">${landmarkName.replace(/'/g, "\\'")}</div>'
      +'<div style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:7px solid #f2d202"></div>'
      +'<div style="width:7px;height:7px;border-radius:50%;background:#f2d202;margin-top:1px;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>'
      +'</div>',
    anchor:new naver.maps.Point(0,60)
  }
});` : '';
  return `<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<script src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${NCP_KEY_ID}&submodules=panorama"></script>
<style>*{margin:0;padding:0}html,body,#pano{width:100%;height:100%;overflow:hidden}</style>
</head><body>
<div id="pano"></div>
<script>
var pos=new naver.maps.LatLng(${lat},${lng});
var targetPan=${pan};
var pano=new naver.maps.Panorama('pano',{
  position:pos,
  pov:{pan:targetPan,tilt:0,fov:100},
  flightSpot:false,
  aroundControl:true,
  zoomControl:false
});
naver.maps.Event.addListener(pano,'init',function(){
  pano.setPov({pan:targetPan,tilt:0,fov:100});
  window.ReactNativeWebView.postMessage(JSON.stringify({type:'pov_init',pan:targetPan}));
});
naver.maps.Event.addListener(pano,'pano_changed',function(){
  pano.setPov({pan:targetPan,tilt:0,fov:100});
  window.ReactNativeWebView.postMessage(JSON.stringify({type:'pov_reset',pan:targetPan}));
});
naver.maps.Event.addListener(pano,'error',function(){
  document.getElementById('pano').innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:13px">파노라마 없음</div>';
});
naver.maps.Event.addListener(pano,'pov_changed',function(){
  var pov=pano.getPov();
  window.ReactNativeWebView.postMessage(JSON.stringify({type:'pov',pan:pov.pan}));
});
${markerJs}
</script>
</body></html>`;
}

/** Bearing (degrees 0-360) from point A to point B. */
function bearingTo(
  lat1: number, lng1: number,
  lat2: number, lng2: number,
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const toDeg = (r: number) => (r * 180) / Math.PI;
  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);
  const dλ = toRad(lng2 - lng1);
  const y = Math.sin(dλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(dλ);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

export function getPrimaryPan(dp: DecisionPoint): number | null {
  if (!dp.panoramaRequest?.directions) { return null; }
  const primary = dp.panoramaRequest.directions.find(d => d.isPrimary);
  if (!primary) { return null; }

  // Priority 1: server-supplied panOverride (hand-tuned value)
  const override = dp.panoramaRequest.panOverride;
  if (override != null) {
    console.log(`[PANO] dpId=${dp.dpId}, panOverride=${override}, originalPan=${primary.pan}`);
    return override;
  }

  // Priority 2: bearing toward POI location
  const lmLoc = dp.selectedLandmark?.location;
  if (lmLoc) {
    const panoLoc = dp.panoramaRequest.location;
    const bearing = bearingTo(panoLoc.latitude, panoLoc.longitude, lmLoc.latitude, lmLoc.longitude);
    console.log(`[PANO] dpId=${dp.dpId}, bearing=${bearing.toFixed(1)}, originalPan=${primary.pan}`);
    return bearing;
  }

  // Priority 3: default pan from panoramaRequest
  console.log(`[PANO] dpId=${dp.dpId}, defaultPan=${primary.pan}`);
  return primary.pan;
}
