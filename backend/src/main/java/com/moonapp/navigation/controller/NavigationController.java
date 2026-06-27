package com.moonapp.navigation.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.moonapp.client.PythonServiceClient;
import com.moonapp.common.dto.ApiResponse;
import com.moonapp.common.exception.CustomException;
import com.moonapp.common.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/route/{routeId}")
@RequiredArgsConstructor
public class NavigationController {

    private final PythonServiceClient pythonServiceClient;
    private final ObjectMapper objectMapper;

    @Value("${services.vision.enabled:false}")
    private boolean visionEnabled;

    @Value("${services.vision.max-payload-chars:2200000}")
    private int visionMaxPayloadChars;

    // Kept at the historical panorama-results path for client compatibility.
    // The current payload is forwarded to dp-pipeline's Vision analysis endpoint.
    @PostMapping("/panorama-results")
    public ApiResponse<JsonNode> uploadPanoramaResult(@PathVariable String routeId, @RequestBody String rawJson) {
        if (!visionEnabled) {
            throw new CustomException(ErrorCode.VISION_DISABLED);
        }
        if (rawJson == null || rawJson.length() > visionMaxPayloadChars) {
            throw new CustomException(ErrorCode.INVALID_REQUEST);
        }

        ObjectNode body = parseVisionRequest(routeId, rawJson);
        String response = pythonServiceClient.uploadPanoramaResult(routeId, body.toString());
        return ApiResponse.success(parseJson(response));
    }

    @PostMapping("/reroute")
    public ApiResponse<JsonNode> reroute(@PathVariable String routeId, @RequestBody String rawJson) {
        String response = pythonServiceClient.reroute(routeId, rawJson);
        return ApiResponse.success(parseJson(response));
    }

    @PostMapping("/conversation")
    public ApiResponse<JsonNode> conversation(@PathVariable String routeId, @RequestBody String rawJson) {
        String response = pythonServiceClient.conversation(routeId, rawJson);
        return ApiResponse.success(parseJson(response));
    }

    private JsonNode parseJson(String json) {
        try {
            JsonNode root = objectMapper.readTree(json);
            if (root.has("data") && root.has("status")) {
                return root.get("data");
            }
            return root;
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }

    private ObjectNode parseVisionRequest(String routeId, String rawJson) {
        try {
            JsonNode root = objectMapper.readTree(rawJson);
            if (!root.isObject()) {
                throw new CustomException(ErrorCode.INVALID_REQUEST);
            }
            ObjectNode body = (ObjectNode) root;
            body.put("route_id", routeId);
            validateTextField(body, "dp_id");
            validateTextField(body, "direction");
            return body;
        } catch (CustomException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.INVALID_REQUEST);
        }
    }

    private void validateTextField(ObjectNode body, String fieldName) {
        JsonNode value = body.get(fieldName);
        if (value == null || !value.isTextual() || value.asText().isBlank()) {
            throw new CustomException(ErrorCode.INVALID_REQUEST);
        }
    }
}
