package com.moonapp.common.exception;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@AutoConfigureMockMvc
@SpringBootTest
class GlobalExceptionHandlerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void returnsJsonWhenUrlDoesNotExist() throws Exception {
        mockMvc.perform(get("/api/test"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.status").value("ERROR"))
            .andExpect(jsonPath("$.error.code").value("ENDPOINT_NOT_FOUND"))
            .andExpect(jsonPath("$.error.message").value("요청한 URL을 찾을 수 없음"));
    }
}
