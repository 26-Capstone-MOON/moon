package com.moonapp.common.exception;

import org.springframework.http.HttpStatus;

public enum ErrorCode {

    INVALID_LOCATION(HttpStatus.BAD_REQUEST, "INVALID_LOCATION", "위치값이 유효하지 않음"),
    INVALID_REQUEST(HttpStatus.BAD_REQUEST, "INVALID_REQUEST", "요청 파라미터 오류"),
    ROUTE_NOT_FOUND(HttpStatus.NOT_FOUND, "ROUTE_NOT_FOUND", "경로를 찾을 수 없음"),
    PIPELINE_SERVICE_ERROR(HttpStatus.BAD_GATEWAY, "PIPELINE_SERVICE_ERROR", "경로 생성 서비스 호출 실패"),
    DEVIATION_SERVICE_ERROR(HttpStatus.BAD_GATEWAY, "DEVIATION_SERVICE_ERROR", "이탈 감지 서비스 호출 실패"),
    VISION_NOT_IMPLEMENTED(HttpStatus.NOT_IMPLEMENTED, "VISION_NOT_IMPLEMENTED", "Vision AI 분석 기능은 현재 production에서 제공하지 않음"),
    VISION_DISABLED(HttpStatus.SERVICE_UNAVAILABLE, "VISION_DISABLED", "현재 환경 분석 기능을 사용할 수 없음"),
    VISION_SERVICE_ERROR(HttpStatus.BAD_GATEWAY, "VISION_SERVICE_ERROR", "Vision 분석 서비스 호출 실패"),
    SERVICE_TIMEOUT(HttpStatus.GATEWAY_TIMEOUT, "SERVICE_TIMEOUT", "서비스 응답 시간 초과"),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", "서버 내부 오류");

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;

    ErrorCode(HttpStatus httpStatus, String code, String message) {
        this.httpStatus = httpStatus;
        this.code = code;
        this.message = message;
    }

    public HttpStatus getHttpStatus() {
        return httpStatus;
    }

    public String getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
