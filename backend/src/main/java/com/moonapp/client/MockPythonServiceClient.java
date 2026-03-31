package com.moonapp.client;

import com.moonapp.model.vo.Location;
import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component
@Profile("mock")
@Primary
public class MockPythonServiceClient extends PythonServiceClient {

    public MockPythonServiceClient() {
        super(null);
    }

    @Override
    public String createRoute(Location origin, Location destination, String destName) {
        return """
            {
              "route_id": "route_test_001",
              "total_distance": 1200,
              "total_time": 900,
              "weather": {"condition": "CLEAR", "w_mod": 1.0},
              "route_line_string": {
                "type": "LineString",
                "coordinates": [[126.92365, 37.55677], [126.92432, 37.55280]]
              },
              "decision_points": [
                {
                  "dp_id": "dp_001",
                  "dp_type": "DEPARTURE",
                  "location": {"latitude": 37.55677, "longitude": 126.92365},
                  "guidance": {"primary": "출발합니다. 전방으로 직진하세요."}
                },
                {
                  "dp_id": "dp_002",
                  "dp_type": "DIRECTION_CHANGE",
                  "location": {"latitude": 37.55500, "longitude": 126.92400},
                  "guidance": {"primary": "올리브영을 끼고 오른쪽으로 도세요."},
                  "selected_landmark": {"name": "올리브영", "position": "RIGHT"}
                }
              ],
              "cached_at": "2026-03-27T14:30:00Z"
            }
            """;
    }

    @Override
    public String getRoute(String routeId) {
        return createRoute(null, null, null);
    }

    @Override
    public String uploadPanoramaResult(String routeId, String requestBody) {
        return """
            {"status": "ok", "message": "파노라마 결과 저장됨"}
            """;
    }

    @Override
    public String reroute(String routeId, String requestBody) {
        return """
            {"route_id": "route_test_001", "message": "재라우팅 완료", "decision_points": []}
            """;
    }

    @Override
    public String conversation(String routeId, String requestBody) {
        return """
            {"message": "안내를 시작합니다.", "next_action": "CONTINUE"}
            """;
    }
}
