package com.moonapp.route.dto.request;

import com.moonapp.model.vo.Location;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class RouteCreateRequest {

    @NotNull(message = "출발지 위치는 필수입니다")
    private Location originLocation;

    @NotNull(message = "목적지 위치는 필수입니다")
    private Location destinationLocation;

    private String destinationName;

    public void setOriginLocation(Location originLocation) {
        this.originLocation = originLocation;
    }

    public void setDestinationLocation(Location destinationLocation) {
        this.destinationLocation = destinationLocation;
    }

    public void setDestinationName(String destinationName) {
        this.destinationName = destinationName;
    }
}
