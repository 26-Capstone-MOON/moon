package com.moonapp.route.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.moonapp.common.dto.ApiResponse;
import com.moonapp.route.dto.request.RouteCreateRequest;
import com.moonapp.route.service.RouteService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class RouteController {

    private final RouteService routeService;

    @PostMapping("/route")
    public ApiResponse<JsonNode> createRoute(@RequestBody @Valid RouteCreateRequest request) {
        JsonNode route = routeService.createRoute(request);
        return ApiResponse.success(route);
    }

    @GetMapping("/route/{routeId}")
    public ApiResponse<JsonNode> getRoute(@PathVariable String routeId) {
        JsonNode route = routeService.getRoute(routeId);
        return ApiResponse.success(route);
    }
}
