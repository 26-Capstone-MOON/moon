package com.moonapp.client;

import com.moonapp.model.vo.Location;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;

public interface PythonServiceClient {

    String createRoute(@NonNull Location origin, @NonNull Location destination, @Nullable String destName);

    String getRoute(@NonNull String routeId);

    String checkDeviation(
        @NonNull String routeId,
        double lat,
        double lng,
        @Nullable String timestamp,
        double speed
    );

    String uploadPanoramaResult(@NonNull String routeId, @NonNull String requestBody);

    String reroute(@NonNull String routeId, @NonNull String requestBody);

    String conversation(@NonNull String routeId, @NonNull String requestBody);
}
