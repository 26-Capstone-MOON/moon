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

    private int requestCount = 0;

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
        requestCount++;

        // GPS 오류: 비현실적 속도 무시
        if (speed > 15.0) {
            return mockResponse("ON_ROUTE", "dp_001", 100.0, null, null, 1200, 900);
        }

        // 1~5: 정상 이동
        if (requestCount <= 5) {
            return mockResponse("ON_ROUTE", "dp_001",
                150.0 - (requestCount * 20), null, null,
                1200 - (requestCount * 50), 900 - (requestCount * 40));
        }

        // 6~8: DP 접근 → PRE_ALERT
        if (requestCount <= 8) {
            return mockResponse("ON_ROUTE", "dp_001",
                30.0 - ((requestCount - 5) * 8), "PRE_ALERT",
                "{\"primary\": \"오른쪽에 GS25 보이시죠? 조금 있으면 올리브영이 보일 거예요.\", \"action\": \"RIGHT_TURN\"}",
                1000 - (requestCount * 30), 750 - (requestCount * 25));
        }

        // 9~10: DP 도착
        if (requestCount <= 10) {
            return mockResponse("ON_ROUTE", "dp_001",
                5.0, "ARRIVAL",
                "{\"primary\": \"올리브영을 끼고 오른쪽으로 도세요.\", \"action\": \"RIGHT_TURN\"}",
                900, 680);
        }

        // 11~15: 다음 DP로 이동
        if (requestCount <= 15) {
            return mockResponse("ON_ROUTE", "dp_002",
                120.0 - ((requestCount - 10) * 20), null, null,
                800 - ((requestCount - 10) * 40), 600 - ((requestCount - 10) * 30));
        }

        // 16~18: 두 번째 DP 접근 → PRE_ALERT
        if (requestCount <= 18) {
            return mockResponse("ON_ROUTE", "dp_002",
                25.0 - ((requestCount - 15) * 7), "PRE_ALERT",
                "{\"primary\": \"왼쪽에 국민은행 보이면 맞는 길이에요. 계속 직진하세요.\", \"action\": \"STRAIGHT\"}",
                500, 380);
        }

        // 19~20: 두 번째 DP 도착
        if (requestCount <= 20) {
            return mockResponse("ON_ROUTE", "dp_002",
                3.0, "ARRIVAL",
                "{\"primary\": \"횡단보도를 건너세요.\", \"action\": \"CROSSWALK\"}",
                400, 300);
        }

        // 21~25: 직진 확인
        if (requestCount <= 25) {
            return mockResponse("ON_ROUTE", "dp_003",
                80.0 - ((requestCount - 20) * 15), "CONFIRMATION",
                "{\"primary\": \"잘 가고 있어요. 계속 직진하세요.\"}",
                300 - ((requestCount - 20) * 30), 230 - ((requestCount - 20) * 20));
        }

        // 26~28: 경로 이탈 경고
        if (requestCount <= 28) {
            return mockResponse("DEVIATION_WARNING", "dp_003",
                80.0, "DEVIATION_WARNING",
                "{\"primary\": \"경로를 벗어난 것 같아요.\"}",
                350, 270);
        }

        // 29~30: 이탈 확정 → 재라우팅
        if (requestCount <= 30) {
            return mockResponse("DEVIATION_CONFIRMED", "dp_003",
                80.0, "REROUTING",
                "{\"primary\": \"경로를 다시 찾고 있어요.\"}",
                400, 300);
        }

        // 31~33: 복귀 감지
        if (requestCount <= 33) {
            return mockResponse("ON_ROUTE", "dp_003",
                60.0, "RETURN_DETECTED",
                "{\"primary\": \"다시 돌아오고 있어요. 잘하고 있어요.\"}",
                250, 190);
        }

        // 34~38: 도착지 접근
        if (requestCount <= 38) {
            return mockResponse("ON_ROUTE", "dp_004",
                50.0 - ((requestCount - 33) * 10), "PRE_ALERT",
                "{\"primary\": \"곧 목적지에 도착해요. 오른쪽에 교보문고 건물이 보일 거예요.\", \"action\": \"STRAIGHT\"}",
                100 - ((requestCount - 33) * 20), 80 - ((requestCount - 33) * 15));
        }

        // 39~40: 도착
        if (requestCount <= 40) {
            requestCount = 0;
            return mockResponse("ARRIVED", "dp_004",
                0.0, "ARRIVAL",
                "{\"primary\": \"목적지에 도착했습니다.\"}",
                0, 0);
        }

        // 41+: 리셋
        requestCount = 0;
        return mockResponse("ON_ROUTE", "dp_001", 150.0, null, null, 1200, 900);
    }

    private String mockResponse(
            String navState, String dpId, double distToDp,
            String trigger, String guidanceJson,
            int distRemaining, int timeRemaining) {

        String triggerStr = trigger != null ? "\"" + trigger + "\"" : "null";
        String guidanceStr = guidanceJson != null ? guidanceJson.trim() : "null";

        return """
            {
              "navigation_state": "%s",
              "current_dp_id": "%s",
              "distance_to_dp": %.1f,
              "trigger": %s,
              "guidance": %s,
              "progress": {
                "distance_remaining": %d,
                "time_remaining": %d
              }
            }
            """.formatted(navState, dpId, distToDp, triggerStr, guidanceStr,
                          distRemaining, timeRemaining);
    }

    @Override
    public String getRoute(@NonNull String routeId) {
        return createRoute(null, null, null);
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