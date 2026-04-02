package com.moonapp.client;

import com.moonapp.model.vo.Location;
import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Component;

@Component
@Profile("mock")
@Primary
public class MockPythonServiceClient implements PythonServiceClient {

    @Override
    public String createRoute(@NonNull Location origin, @NonNull Location destination, @Nullable String destName) {
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
    public String checkDeviation(
        @NonNull String routeId,
        double lat,
        double lng,
        @Nullable String timestamp,
        double speed
    ) {
        // GPS 오류
        if (speed > 15.0) {
            return """
                {
                  "navigation_state": "ON_ROUTE",
                  "trigger": null,
                  "guidance": null,
                  "progress": {"distance_remaining": 800, "time_remaining": 600}
                }
                """;
        }

        // 심한 이탈: 위도가 37.553 미만이면 재라우팅
        if (lat < 37.553) {
            return """
                {
                  "navigation_state": "DEVIATED",
                  "trigger": "REROUTING",
                  "guidance": {"primary": "경로를 다시 찾고 있어요."},
                  "progress": {"distance_remaining": 1100, "time_remaining": 800}
                }
                """;
        }

        // 이탈 경고: 위도가 37.554 미만이면 이탈 경고
        if (lat < 37.554) {
            return """
                {
                  "navigation_state": "DEVIATION_WARNING",
                  "trigger": "DEVIATION_WARNING",
                  "guidance": {"primary": "경로를 벗어난 것 같아요. 확인해주세요."},
                  "progress": {"distance_remaining": 900, "time_remaining": 680}
                }
                """;
        }

        // 기본: 정상 경로
        return """
            {
              "navigation_state": "ON_ROUTE",
              "current_dp_id": "dp_002",
              "distance_to_dp": 28.5,
              "trigger": "PRE_ALERT",
              "guidance": {"primary": "조금 있으면 올리브영이 보일 거예요.", "action": "RIGHT_TURN"},
              "progress": {"distance_remaining": 1000, "time_remaining": 750}
            }
            """;
    }

    @Override
    public String getRoute(@NonNull String routeId) {
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
    public String uploadPanoramaResult(@NonNull String routeId, @NonNull String requestBody) {
        return """
            {"status": "ok", "message": "파노라마 결과 저장됨"}
            """;
    }

    @Override
    public String reroute(@NonNull String routeId, @NonNull String requestBody) {
        return """
            {"route_id": "route_test_001", "message": "재라우팅 완료", "decision_points": []}
            """;
    }

    @Override
    public String conversation(@NonNull String routeId, @NonNull String requestBody) {
        return """
            {"message": "안내를 시작합니다.", "next_action": "CONTINUE"}
            """;
    }
}