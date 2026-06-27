package com.moonapp.navigation.controller;

import com.moonapp.client.PythonServiceClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import static org.mockito.ArgumentMatchers.anyString;
import org.mockito.ArgumentCaptor;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@AutoConfigureMockMvc
@SpringBootTest
class NavigationControllerVisionTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private NavigationController navigationController;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private PythonServiceClient pythonServiceClient;

    @Test
    void productionVisionDisabledReturns503WithoutCallingPython() throws Exception {
        ReflectionTestUtils.setField(navigationController, "visionEnabled", false);

        mockMvc.perform(post("/api/route/route-test/panorama-results")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"dp_id\":\"dp-1\",\"direction\":\"FRONT\",\"image_base64\":null}"))
            .andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.status").value("ERROR"))
            .andExpect(jsonPath("$.error.code").value("VISION_DISABLED"));

        verify(pythonServiceClient, never()).uploadPanoramaResult(anyString(), anyString());
    }

    @Test
    void invalidPayloadReturns400() throws Exception {
        ReflectionTestUtils.setField(navigationController, "visionEnabled", true);

        mockMvc.perform(post("/api/route/route-test/panorama-results")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"direction\":\"FRONT\"}"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.status").value("ERROR"))
            .andExpect(jsonPath("$.error.code").value("INVALID_REQUEST"));
    }

    @Test
    void forwardsPythonVisionSuccessResponse() throws Exception {
        ReflectionTestUtils.setField(navigationController, "visionEnabled", true);
        when(pythonServiceClient.uploadPanoramaResult(anyString(), anyString()))
            .thenReturn("""
                {"status":"SUCCESS","data":{"analysis_status":"ANALYZED","scene_description":"전방에 횡단보도가 있습니다.","visual_cues":[],"landmark_verification":null,"has_crosswalk":true,"has_stairs":false,"generated_at":"2026-06-24T00:00:00Z"}}
                """);

        mockMvc.perform(post("/api/route/route-test/panorama-results")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"dp_id\":\"dp-1\",\"direction\":\"FRONT\",\"image_base64\":\"data:image/jpeg;base64,AAAA\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("SUCCESS"))
            .andExpect(jsonPath("$.data.analysis_status").value("ANALYZED"))
            .andExpect(jsonPath("$.data.has_crosswalk").value(true));

        ArgumentCaptor<String> bodyCaptor = ArgumentCaptor.forClass(String.class);
        verify(pythonServiceClient).uploadPanoramaResult(eq("route-test"), bodyCaptor.capture());

        JsonNode forwarded = objectMapper.readTree(bodyCaptor.getValue());
        Assertions.assertEquals("route-test", forwarded.path("route_id").asText());
        Assertions.assertEquals("dp-1", forwarded.path("dp_id").asText());
        Assertions.assertEquals("FRONT", forwarded.path("direction").asText());
        Assertions.assertTrue(forwarded.path("image_base64").asText().startsWith("data:image/jpeg;base64,"));
    }
}
