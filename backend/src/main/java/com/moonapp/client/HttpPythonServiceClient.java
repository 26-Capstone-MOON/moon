package com.moonapp.client;

import com.moonapp.common.exception.CustomException;
import com.moonapp.common.exception.ErrorCode;
import com.moonapp.model.vo.Location;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

@Component
public class HttpPythonServiceClient implements PythonServiceClient {

    private final WebClient webClient;
    private final String baseUrl;
    private final String deviationBaseUrl;

    public HttpPythonServiceClient(
        @NonNull WebClient webClient,
        @Value("${services.python.base-url}") @NonNull String baseUrl,
        @Value("${services.deviation.base-url}") @NonNull String deviationBaseUrl
    ) {
        this.webClient = webClient;
        this.baseUrl = baseUrl;
        this.deviationBaseUrl = deviationBaseUrl;
    }

    @Override
    public String createRoute(@NonNull Location origin, @NonNull Location destination, @Nullable String destName) {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("origin_lat", origin.getLatitude());
        requestBody.put("origin_lng", origin.getLongitude());
        requestBody.put("dest_lat", destination.getLatitude());
        requestBody.put("dest_lng", destination.getLongitude());
        requestBody.put("dest_name", destName);

        try {
            return requireResponseBody(
                webClient.post()
                    .uri(baseUrl + "/api/route")
                    .bodyValue(requestBody)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block()
            );
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }
    }

    @Override
    public String getRoute(@NonNull String routeId) {
        try {
            return requireResponseBody(
                webClient.get()
                    .uri(baseUrl + "/api/route/{routeId}", routeId)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block()
            );
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }
    }

    @Override
    public String checkDeviation(
        @NonNull String routeId,
        double lat,
        double lng,
        @Nullable String timestamp,
        double speed
    ) {
        return callPost(
            deviationBaseUrl,
            "/api/deviation",
            Map.of(
                "route_id", routeId,
                "latitude", lat,
                "longitude", lng,
                "timestamp", timestamp != null ? timestamp : "",
                "speed", speed
            ),
            ErrorCode.DEVIATION_SERVICE_ERROR
        );
    }

    @Override
    public String uploadPanoramaResult(@NonNull String routeId, @NonNull String requestBody) {
        return postJson("/api/route/{routeId}/panorama-results", routeId, requestBody);
    }

    @Override
    public String reroute(@NonNull String routeId, @NonNull String requestBody) {
        return postJson("/api/route/{routeId}/reroute", routeId, requestBody);
    }

    @Override
    public String conversation(@NonNull String routeId, @NonNull String requestBody) {
        return postJson("/api/route/{routeId}/conversation", routeId, requestBody);
    }

    private String postJson(@NonNull String uri, @NonNull String routeId, @NonNull String requestBody) {
        try {
            return requireResponseBody(
                webClient.post()
                    .uri(baseUrl + uri, routeId)
                    .contentType(Objects.requireNonNull(MediaType.APPLICATION_JSON))
                    .bodyValue(Objects.requireNonNull(requestBody))
                    .retrieve()
                    .bodyToMono(String.class)
                    .block()
            );
        } catch (Exception exception) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }
    }

    private String callPost(
        @NonNull String serviceBaseUrl,
        @NonNull String uri,
        @NonNull Map<String, Object> requestBody,
        @NonNull ErrorCode errorCode
    ) {
        try {
            return requireResponseBody(
                webClient.post()
                    .uri(serviceBaseUrl + uri)
                    .bodyValue(requestBody)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block()
            );
        } catch (Exception exception) {
            throw new CustomException(errorCode);
        }
    }

    private String requireResponseBody(@Nullable String responseBody) {
        if (responseBody == null) {
            throw new CustomException(ErrorCode.PIPELINE_SERVICE_ERROR);
        }

        return responseBody;
    }
}
