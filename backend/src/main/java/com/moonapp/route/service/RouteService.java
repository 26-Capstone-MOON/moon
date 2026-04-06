package com.moonapp.route.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moonapp.client.PythonServiceClient;
import com.moonapp.common.exception.CustomException;
import com.moonapp.common.exception.ErrorCode;
import com.moonapp.route.dto.request.RouteCreateRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class RouteService {

    private final PythonServiceClient pythonServiceClient;
    private final ObjectMapper objectMapper;

    public JsonNode createRoute(RouteCreateRequest request) {
        log.info("[DEBUG] createRoute 요청 - origin=({}, {}), dest=({}, {}), name={}",
            request.getOriginLocation().getLatitude(),
            request.getOriginLocation().getLongitude(),
            request.getDestinationLocation().getLatitude(),
            request.getDestinationLocation().getLongitude(),
            request.getDestinationName());

        String response = pythonServiceClient.createRoute(
            request.getOriginLocation(),
            request.getDestinationLocation(),
            request.getDestinationName()
        );

        log.info("[DEBUG] Python 원본 응답 (앞 500자): {}",
            response.length() > 500 ? response.substring(0, 500) + "..." : response);

        JsonNode result = parseJson(response);

        log.info("[DEBUG] 언래핑 후 필드 확인 - has route_id={}, has decision_points={}, has total_distance={}, has route_line_string={}",
            result.has("route_id"),
            result.has("decision_points"),
            result.has("total_distance"),
            result.has("route_line_string"));

        if (result.has("decision_points")) {
            log.info("[DEBUG] decision_points 개수: {}", result.get("decision_points").size());
        }

        return result;
    }

    public JsonNode getRoute(String routeId) {
        log.info("[DEBUG] getRoute 요청 - routeId={}", routeId);
        String response = pythonServiceClient.getRoute(routeId);
        log.info("[DEBUG] getRoute Python 응답 (앞 500자): {}",
            response.length() > 500 ? response.substring(0, 500) + "..." : response);
        return parseJson(response);
    }

    /**
     * Parse Python response and extract inner "data" field to avoid double wrapping.
     * Python returns { "status": "SUCCESS", "data": { ... } }.
     * Spring Boot wraps again via ApiResponse.success(), so we must unwrap first.
     */
    private JsonNode parseJson(String json) {
        try {
            JsonNode root = objectMapper.readTree(json);
            log.info("[DEBUG] parseJson - root 최상위 키: {}", root.fieldNames());
            if (root.has("data") && root.has("status")) {
                String status = root.get("status").asText();
                log.info("[DEBUG] Python status={}, data 언래핑 수행", status);
                return root.get("data");
            }
            log.info("[DEBUG] data/status 구조 아님 → root 그대로 반환");
            return root;
        } catch (Exception exception) {
            log.error("[DEBUG] JSON 파싱 실패: {}", exception.getMessage());
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }
}
