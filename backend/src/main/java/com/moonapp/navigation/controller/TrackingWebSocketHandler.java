package com.moonapp.navigation.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moonapp.client.PythonServiceClient;
import com.moonapp.route.service.RouteDestinationCache;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Component
@RequiredArgsConstructor
public class TrackingWebSocketHandler extends TextWebSocketHandler {

    private final PythonServiceClient pythonServiceClient;
    private final ObjectMapper objectMapper;
    private final RouteDestinationCache destinationCache;

    // 세션별 현재 유효한 routeId (reroute 시 갱신)
    private final Map<String, String> sessionRouteIdMap = new ConcurrentHashMap<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        log.info("WebSocket 연결됨: sessionId={}", session.getId());
    }

    @Override
    protected void handleTextMessage(
            WebSocketSession session, TextMessage message) throws Exception {
        try {
            JsonNode gpsData = objectMapper.readTree(message.getPayload());

            String clientRouteId = gpsData.get("route_id").asText();
            double lat = gpsData.get("latitude").asDouble();
            double lng = gpsData.get("longitude").asDouble();

            // reroute 후 갱신된 routeId가 있으면 그것을 사용
            String routeId = sessionRouteIdMap.getOrDefault(
                session.getId(), clientRouteId);

            String timestamp = gpsData.has("timestamp")
                ? gpsData.get("timestamp").asText() : "";
            double speed = gpsData.has("speed")
                ? gpsData.get("speed").asDouble() : 0.0;

            log.debug("[TRACK] deviation 호출: routeId={}, lat={}, lng={}, speed={}",
                routeId, lat, lng, speed);

            String pythonResult = pythonServiceClient.checkDeviation(
                routeId, lat, lng, timestamp, speed);

            log.debug("[TRACK] deviation 원본 응답: {}", pythonResult);

            // Python returns { "status": "SUCCESS", "data": { ... } }
            JsonNode root = objectMapper.readTree(pythonResult);
            JsonNode data = (root.has("data") && root.has("status"))
                ? root.get("data") : root;

            // navigationState 파싱 디버그
            boolean hasCamel = data.has("navigationState");
            boolean hasSnake = data.has("navigation_state");
            String navigationState = hasCamel
                ? data.get("navigationState").asText()
                : hasSnake
                    ? data.get("navigation_state").asText() : "";
            log.info("[TRACK] navigationState='{}' (camel={}, snake={}, data keys={})",
                navigationState, hasCamel, hasSnake, data.fieldNames());

            // DEVIATION_CONFIRMED → 자동 reroute 호출
            if ("DEVIATION_CONFIRMED".equals(navigationState)) {
                log.info("[REROUTE] ★ DEVIATION_CONFIRMED 조건 진입! routeId={}", routeId);

                // 먼저 DEVIATION_CONFIRMED 응답을 앱에 전달
                session.sendMessage(new TextMessage(
                    objectMapper.writeValueAsString(data)));

                try {
                    // 목적지 정보 조회 (경로 생성 시 캐시됨)
                    RouteDestinationCache.Destination dest = destinationCache.get(routeId);
                    if (dest == null) {
                        log.error("[REROUTE] ✗ 목적지 캐시 없음! routeId={}", routeId);
                        session.sendMessage(new TextMessage(
                            objectMapper.writeValueAsString(Map.of(
                                "status", "ERROR",
                                "message", "목적지 정보 없음 - 경로를 다시 생성해주세요"))));
                        return;
                    }

                    // reroute 요청: 현재 GPS + 목적지 좌표
                    Map<String, Object> rerouteMap = new java.util.HashMap<>();
                    rerouteMap.put("current_lat", lat);
                    rerouteMap.put("current_lng", lng);
                    rerouteMap.put("dest_lat", dest.getLatitude());
                    rerouteMap.put("dest_lng", dest.getLongitude());
                    rerouteMap.put("dest_name", dest.getName());
                    String rerouteBody = objectMapper.writeValueAsString(rerouteMap);
                    log.info("[REROUTE] reroute 호출 시도: routeId={}, body={}",
                        routeId, rerouteBody);

                    String rerouteResult = pythonServiceClient.reroute(
                        routeId, rerouteBody);
                    log.info("[REROUTE] reroute 응답 수신: {}", rerouteResult);

                    // Python 응답이 두 가지 형태일 수 있음:
                    // 1) 배열: [["success",true],["route_response",{...}]]
                    // 2) 객체: { "status":"SUCCESS", "data": { "route_response": {...} } }
                    JsonNode rerouteRoot = objectMapper.readTree(rerouteResult);
                    log.info("[REROUTE] 응답 타입: isArray={}, isObject={}",
                        rerouteRoot.isArray(), rerouteRoot.isObject());

                    JsonNode routeResponse = null;

                    // 먼저 status/data 래퍼가 있으면 data를 꺼냄
                    JsonNode rerouteData = (rerouteRoot.has("data") && rerouteRoot.has("status"))
                        ? rerouteRoot.get("data") : rerouteRoot;

                    if (rerouteData.isArray()) {
                        // 배열 형태: [["success",true],["route_response",{...}]]
                        for (JsonNode entry : rerouteData) {
                            if (entry.isArray() && entry.size() >= 2
                                    && "route_response".equals(entry.get(0).asText())) {
                                routeResponse = entry.get(1);
                                break;
                            }
                        }
                    } else {
                        // 객체 형태: { "route_response": {...} }
                        routeResponse = rerouteData.has("route_response")
                            ? rerouteData.get("route_response") : rerouteData;
                    }

                    // routeId 추출 (camelCase "routeId" 또는 snake_case "route_id")
                    String newRouteId = null;
                    if (routeResponse != null && !routeResponse.isNull()) {
                        if (routeResponse.has("routeId")) {
                            newRouteId = routeResponse.get("routeId").asText();
                        } else if (routeResponse.has("route_id")) {
                            newRouteId = routeResponse.get("route_id").asText();
                        }
                    }
                    log.info("[REROUTE] 추출: newRouteId={}, route_response={}",
                        newRouteId, routeResponse != null ? "있음" : "없음");

                    if (newRouteId != null) {
                        sessionRouteIdMap.put(session.getId(), newRouteId);
                        destinationCache.put(newRouteId,
                            dest.getLatitude(), dest.getLongitude(), dest.getName());
                        log.info("[REROUTE] 세션 routeId 갱신: {} → {}", routeId, newRouteId);
                    } else {
                        log.warn("[REROUTE] 새 routeId가 null! 응답 구조: {}",
                            rerouteRoot.toString().substring(0, Math.min(200, rerouteRoot.toString().length())));
                    }

                    // 앱에는 route_response (새 경로 데이터)를 전달
                    JsonNode appPayload = routeResponse != null && !routeResponse.isNull()
                        ? routeResponse : rerouteRoot;
                    session.sendMessage(new TextMessage(
                        objectMapper.writeValueAsString(appPayload)));
                    log.info("[REROUTE] 새 경로 앱 전달 완료");

                } catch (Exception rerouteEx) {
                    log.error("[REROUTE] ✗ reroute 호출 실패: {} - {}",
                        rerouteEx.getClass().getSimpleName(), rerouteEx.getMessage(), rerouteEx);
                    session.sendMessage(new TextMessage(
                        objectMapper.writeValueAsString(Map.of(
                            "status", "ERROR",
                            "message", "reroute 실패: " + rerouteEx.getMessage()))));
                }
                return;
            } else {
                log.debug("[TRACK] DEVIATION_CONFIRMED 아님 → 그대로 전달: state='{}'",
                    navigationState);
            }

            session.sendMessage(new TextMessage(
                objectMapper.writeValueAsString(data)));

        } catch (Exception e) {
            log.error("WebSocket 처리 에러: {}", e.getMessage());
            String errorJson = objectMapper.writeValueAsString(
                Map.of("status", "ERROR", "message", e.getMessage()));
            session.sendMessage(new TextMessage(errorJson));
        }
    }

    @Override
    public void afterConnectionClosed(
            WebSocketSession session, CloseStatus status) {
        sessionRouteIdMap.remove(session.getId());
        log.info("WebSocket 연결 종료: sessionId={}, status={}",
                 session.getId(), status);
    }
}