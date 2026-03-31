package com.moonapp.common.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> {

    private final String status;
    private final T data;
    private final ErrorResponse error;

    private ApiResponse(String status, T data, ErrorResponse error) {
        this.status = status;
        this.data = data;
        this.error = error;
    }

    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>("SUCCESS", data, null);
    }

    public static ApiResponse<Void> success() {
        return new ApiResponse<>("SUCCESS", null, null);
    }

    public static ApiResponse<Void> error(String code, String message) {
        return new ApiResponse<>("ERROR", null, ErrorResponse.of(code, message));
    }

    public String getStatus() {
        return status;
    }

    public T getData() {
        return data;
    }

    public ErrorResponse getError() {
        return error;
    }
}
