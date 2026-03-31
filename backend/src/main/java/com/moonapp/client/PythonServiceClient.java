package com.moonapp.client;

import com.moonapp.common.exception.CustomException;
import com.moonapp.common.exception.ErrorCode;
import com.moonapp.model.vo.Location;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.HashMap;
import java.util.Map;

@Component
@RequiredArgsConstructor
public class PythonServiceClient {

    private final WebClient webClient;

    @Value("${services.python.base-url}")
    private String baseUrl;

    public String createRoute(Location origin, Location destination, String destName) {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("origin_lat", origin.getLatitude());
        requestBody.put("origin_lng", origin.getLongitude());
        requestBody.put("dest_lat", destination.getLatitude());
        requestBody.put("dest_lng", destination.getLongitude());
        requestBody.put("dest_name", destName);

        try {
            return webClient.post()
                .uri(baseUrl + "/api/route")
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(String.class)
                .block();
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }
    }

    public String getRoute(String routeId) {
        try {
            return webClient.get()
                .uri(baseUrl + "/api/route/{routeId}", routeId)
                .retrieve()
                .bodyToMono(String.class)
                .block();
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }
    }

    public String uploadPanoramaResult(String routeId, String requestBody) {
        return postJson("/api/route/{routeId}/panorama-results", routeId, requestBody);
    }

    public String reroute(String routeId, String requestBody) {
        return postJson("/api/route/{routeId}/reroute", routeId, requestBody);
    }

    public String conversation(String routeId, String requestBody) {
        return postJson("/api/route/{routeId}/conversation", routeId, requestBody);
    }

    private String postJson(String uri, String routeId, String requestBody) {
        try {
            return webClient.post()
                .uri(baseUrl + uri, routeId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(String.class)
                .block();
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }
    }
}
