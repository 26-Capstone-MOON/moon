import pytest

import vision_service
from config import settings
from schemas import ApiResponse
from vision_schemas import VisionAnalysisStatus, VisionAnalyzeRequest


def _request(image_base64=None):
    return VisionAnalyzeRequest(
        route_id="route-1",
        dp_id="dp-1",
        direction="FRONT",
        image_base64=image_base64,
        selected_landmark={"name": "테스트", "category_code": "CE7", "position": "FRONT"},
    )


@pytest.fixture(autouse=True)
def reset_vision_settings(monkeypatch):
    monkeypatch.setattr(settings, "vision_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "vision_model", "gpt-4o")
    vision_service._VISION_CACHE.clear()


@pytest.mark.asyncio
async def test_no_image_returns_no_image():
    result = await vision_service.analyze_panorama(_request())
    assert result.analysis_status == VisionAnalysisStatus.NO_IMAGE
    assert result.scene_description is None
    assert result.visual_cues == []


@pytest.mark.asyncio
async def test_vision_disabled_returns_disabled(monkeypatch):
    monkeypatch.setattr(settings, "vision_enabled", False)
    result = await vision_service.analyze_panorama(_request())
    assert result.analysis_status == VisionAnalysisStatus.VISION_DISABLED


@pytest.mark.asyncio
async def test_openai_failure_returns_model_failed(monkeypatch):
    class FailingClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(vision_service.httpx, "AsyncClient", FailingClient)
    image = "data:image/jpeg;base64," + ("A" * 1200)
    result = await vision_service.analyze_panorama(_request(image))
    assert result.analysis_status == VisionAnalysisStatus.MODEL_FAILED
    assert result.visual_cues == []


@pytest.mark.asyncio
async def test_parses_structured_response_and_limits_cues(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "scene_description": "전방에 횡단보도와 간판이 있습니다.",
                              "visual_cues": [
                                {"type":"CROSSWALK","description":"전방 횡단보도","confidence":0.9},
                                {"type":"SIGN","description":"오른쪽 밝은 간판","confidence":0.7},
                                {"type":"BUILDING","description":"전방 큰 건물","confidence":0.6},
                                {"type":"COLOR","description":"파란색 표지","confidence":0.5}
                              ],
                              "landmark_verification": {"landmark_name":"테스트","visible":true,"confidence":0.8},
                              "has_crosswalk": true,
                              "has_stairs": false
                            }
                            """
                        }
                    }
                ]
            }

    class Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(vision_service.httpx, "AsyncClient", Client)
    image = "data:image/jpeg;base64," + ("A" * 1200)
    result = await vision_service.analyze_panorama(_request(image))
    assert result.analysis_status == VisionAnalysisStatus.ANALYZED
    assert result.scene_description == "전방에 횡단보도와 간판이 있습니다."
    assert len(result.visual_cues) == 3
    assert result.has_crosswalk is True
    assert result.landmark_verification.visible is True


def test_api_response_serializes_vision_data_as_json_object():
    data = ApiResponse(
        data=vision_service.empty_vision_result(VisionAnalysisStatus.NO_IMAGE)
    ).model_dump(mode="json")

    assert isinstance(data["data"], dict)
    assert data["data"]["analysis_status"] == "NO_IMAGE"
    assert data["data"]["visual_cues"] == []
