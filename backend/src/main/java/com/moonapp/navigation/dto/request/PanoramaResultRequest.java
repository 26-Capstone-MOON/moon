package com.moonapp.navigation.dto.request;

import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class PanoramaResultRequest {

    private String dpId;

    private List<Object> panoramaImages;
}
