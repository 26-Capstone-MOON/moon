package com.moonapp.route.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moonapp.client.PythonServiceClient;
import com.moonapp.common.exception.CustomException;
import com.moonapp.common.exception.ErrorCode;
import com.moonapp.route.dto.request.RouteCreateRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class RouteService {

    private final PythonServiceClient pythonServiceClient;
    private final ObjectMapper objectMapper;

    public JsonNode createRoute(RouteCreateRequest request) {
        String response = pythonServiceClient.createRoute(
            request.getOriginLocation(),
            request.getDestinationLocation(),
            request.getDestinationName()
        );

        return parseJson(response);
    }

    public JsonNode getRoute(String routeId) {
        String response = pythonServiceClient.getRoute(routeId);

        return parseJson(response);
    }

    private JsonNode parseJson(String json) {
        try {
            return objectMapper.readTree(json);
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }
}
