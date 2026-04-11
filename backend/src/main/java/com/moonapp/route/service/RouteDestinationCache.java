package com.moonapp.route.service;

import com.moonapp.model.vo.Location;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 경로 생성 시 목적지 정보를 캐시.
 * reroute 시 목적지 좌표를 조회하기 위해 사용.
 */
@Component
public class RouteDestinationCache {

    @Getter
    @RequiredArgsConstructor
    public static class Destination {
        private final double latitude;
        private final double longitude;
        private final String name;
    }

    private final Map<String, Destination> cache = new ConcurrentHashMap<>();

    public void put(String routeId, double lat, double lng, String name) {
        cache.put(routeId, new Destination(lat, lng, name != null ? name : ""));
    }

    public Destination get(String routeId) {
        return cache.get(routeId);
    }

    public void remove(String routeId) {
        cache.remove(routeId);
    }
}
