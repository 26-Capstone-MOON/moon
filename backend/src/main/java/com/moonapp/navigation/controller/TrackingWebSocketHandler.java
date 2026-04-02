package com.moonapp.navigation.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moonapp.client.PythonServiceClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class TrackingWebSocketHandler extends TextWebSocketHandler {

    private final PythonServiceClient pythonServiceClient;
    private final ObjectMapper objectMapper;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        log.info("WebSocket 연결됨: sessionId={}", session.getId());
    }

    @Override
    protected void handleTextMessage(
            WebSocketSession session, TextMessage message) throws Exception {
        try {
            JsonNode gpsData = objectMapper.readTree(message.getPayload());

            String routeId = gpsData.get("route_id").asText();
            double lat = gpsData.get("latitude").asDouble();
            double lng = gpsData.get("longitude").asDouble();

            String timestamp = gpsData.has("timestamp")
                ? gpsData.get("timestamp").asText() : "";
            double speed = gpsData.has("speed")
                ? gpsData.get("speed").asDouble() : 0.0;

            String pythonResult = pythonServiceClient.checkDeviation(
                routeId, lat, lng, timestamp, speed);

            session.sendMessage(new TextMessage(pythonResult));

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
        log.info("WebSocket 연결 종료: sessionId={}, status={}",
                 session.getId(), status);
    }
}