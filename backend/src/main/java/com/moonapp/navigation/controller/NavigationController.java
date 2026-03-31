package com.moonapp.navigation.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moonapp.client.PythonServiceClient;
import com.moonapp.common.dto.ApiResponse;
import com.moonapp.common.exception.CustomException;
import com.moonapp.common.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
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

    @PostMapping("/panorama-results")
    public ApiResponse<JsonNode> uploadPanoramaResult(@PathVariable String routeId, @RequestBody String rawJson) {
        String response = pythonServiceClient.uploadPanoramaResult(routeId, rawJson);
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
            return objectMapper.readTree(json);
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }
}
