CLAUDE.md를 읽고 Phase 1의 2단계(폴더 만들기)부터 8단계(서버 실행 확인)까지 순서대로 수행해.

각 단계별 구현 내용은 아래와 같아. 코드는 로드맵 PDF 원문 기준으로 작성해.

## 2단계: 폴더 만들기
CLAUDE.md의 패키지 구조대로 src/main/java/com/moonapp/ 아래에 패키지를 모두 생성해.

## 3단계: 공통 응답 래퍼
common/dto/ApiResponse.java:
- 제네릭 클래스 ApiResponse<T>
- 필드: String status, T data, ErrorResponse error
- @AllArgsConstructor(access = AccessLevel.PRIVATE)
- static 메서드: success(T data), error(String code, String message)

common/dto/ErrorResponse.java:
- 필드: String code, String message, String timestamp

## 4단계: 에러 처리
common/exception/ErrorCode.java (enum):
- INVALID_LOCATION(400, "INVALID_LOCATION", "위치값이 유효하지 않음")
- INVALID_REQUEST(400, "INVALID_REQUEST", "요청 파라미터 오류")
- ROUTE_NOT_FOUND(404, "ROUTE_NOT_FOUND", "경로를 찾을 수 없음")
- PIPELINE_SERVICE_ERROR(502, "PIPELINE_SERVICE_ERROR", "경로 생성 서비스 호출 실패")
- DEVIATION_SERVICE_ERROR(502, "DEVIATION_SERVICE_ERROR", "이탈 감지 서비스 호출 실패")
- SERVICE_TIMEOUT(504, "SERVICE_TIMEOUT", "서비스 응답 시간 초과")
- INTERNAL_SERVER_ERROR(500, "INTERNAL_SERVER_ERROR", "서버 내부 오류")
- 필드: int httpStatus, String code, String message

common/exception/CustomException.java:
- RuntimeException 상속
- 필드: ErrorCode errorCode

common/exception/GlobalExceptionHandler.java:
- @RestControllerAdvice
- CustomException → ErrorCode 기반 응답
- MethodArgumentNotValidException → 400 INVALID_REQUEST
- Exception → 500 INTERNAL_SERVER_ERROR

## 5단계: Enum + VO
model/enums/ 에 4개 Enum:
- DpType: DEPARTURE, ARRIVAL, DIRECTION_CHANGE, CROSSWALK, VERTICAL_MOVE, VIRTUAL
- NavigationState: ON_ROUTE, DEVIATION_SUSPECTED, DEVIATION_WARNING, DEVIATION_CONFIRMED, RETURNING, REROUTING, ARRIVED
- Position: LEFT, RIGHT, FRONT
- GuidanceAction: RIGHT_TURN, LEFT_TURN, U_TURN, CROSSWALK, STAIRS_UP, STAIRS_DOWN, OVERPASS, UNDERPASS, ELEVATOR

model/vo/Location.java:
- 필드: Double latitude, Double longitude
- @Getter @NoArgsConstructor @AllArgsConstructor

## 6단계: 설정 파일
src/main/resources/application.yml:
```yaml
server:
  port: 8080

services:
  python:
    base-url: ${PYTHON_SERVICE_URL:http://localhost:8000}
  deviation:
    base-url: ${PYTHON_SERVICE_URL:http://localhost:8000}
```

## 7단계: Config 클래스
common/config/WebClientConfig.java:
- @Configuration, @Bean WebClient
- maxInMemorySize 10MB

common/config/CorsConfig.java:
- WebMvcConfigurer 구현
- addCorsMappings: "/**", allowedOrigins("*"), allowedMethods("GET","POST","PUT","DELETE")

## 8단계: 확인
모든 파일 작성 후 컴파일 에러가 없는지 확인해. 완료되면 각 파일 목록과 함께 Phase 1 완료 체크리스트를 보여줘:
- 모든 패키지가 생성되었는가
- 모든 Java 파일이 컴파일 에러 없이 존재하는가
- application.yml이 올바른 형식인가22