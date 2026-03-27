# Coding Rules

---

## Frontend (React Native + TypeScript)

### General Rules
- Functional components only, props must be typed (no `any`)
- Local state first (useState). Global only when needed → Zustand
- Keep files short (< 150 lines preferred)
- Components: PascalCase / Hooks: use- prefix camelCase

### Project Structure

```
src/
├── app/                          # App entry point
│   ├── App.tsx                   # Root component (Navigation setup)
│   └── navigation/
│       └── AppNavigator.tsx      # Stack Navigator screen definitions
├── screens/                      # Screen-level components
│   ├── HomeScreen.tsx
│   ├── NavigationScreen.tsx
│   ├── ProgressScreen.tsx
│   └── DeviationScreen.tsx
├── components/                   # Reusable UI pieces
│   ├── map/                      # MapView, RoutePolyline, DpMarker
│   ├── guidance/                 # GuidanceCard, PanoramaViewer, ProgressBar
│   ├── checkpoint/               # CheckpointList
│   └── common/                   # SearchInput, LoadingOverlay
├── services/                     # Server communication + device APIs
│   ├── api/                      # apiClient.ts, routeApi.ts, conversationApi.ts
│   ├── websocket/                # trackingSocket.ts (WebSocket /tracking)
│   ├── location/                 # locationService.ts (GPS tracking)
│   ├── audio/                    # ttsService.ts, sttService.ts
│   ├── haptic/                   # hapticService.ts
│   └── panorama/                 # panoramaService.ts (Naver + Vision)
├── stores/                       # Zustand global state
│   ├── useRouteStore.ts          # Route data (routeId, DPs, polyline)
│   ├── useNavigationStore.ts     # Nav state (current DP, trigger, progress)
│   └── useConversationStore.ts   # Conversation history
├── types/                        # TypeScript type definitions
│   ├── route.ts                  # Route, DP, Landmark types
│   ├── navigation.ts             # NavigationState, Trigger types
│   ├── api.ts                    # Common API response types
│   └── enums.ts                  # DpType, NavigationState, etc.
├── hooks/                        # Custom hooks
│   ├── useLocationTracking.ts    # GPS tracking + WebSocket send
│   ├── useGuidanceTrigger.ts     # Trigger → TTS + haptic
│   └── useConversation.ts        # STT → server → TTS flow
├── utils/
│   ├── geo.ts                    # Coordinate math (distance, bearing)
│   └── format.ts                 # Time/distance formatting
└── constants/
    ├── api.ts                    # BASE_URL, endpoint paths, WebSocket URL
    └── config.ts                 # Settings (GPS interval, deviation distance)
```

### TypeScript
- All API response types must match API spec v0.1.0 (see CLAUDE.md §8)

### API Integration Rules
- REST endpoints use `/route` prefix (NOT `/v1/routes`)
- GPS tracking uses **WebSocket `/tracking`** (NOT REST POST)
- All location objects: `{ latitude: number; longitude: number }` (WGS84)
- Trigger: `'PRE_ALERT' | 'ARRIVAL' | 'CONFIRMATION' | 'DEVIATION_WARNING' | 'REROUTING' | 'RETURN_DETECTED' | null`
- TTS/haptic triggered by server's `trigger` value — client does NOT self-determine

### Discipline
- Rule of three: only abstract after the same pattern appears 3+ times
- Do not add files, abstractions, or architecture that aren't immediately used
- Working first, optimize later

---

## Backend — Spring Boot (API Gateway)

**Spring Boot does NOT execute business logic.** It relays requests between the app and Python services.

### Package Structure

```
src/main/java/com/moonapp/
├── MoonAppApplication.java
├── common/
│   ├── dto/          ApiResponse, ErrorResponse
│   ├── exception/    CustomException, ErrorCode(Enum), GlobalExceptionHandler
│   └── config/       WebClientConfig, WebSocketConfig, CorsConfig
├── route/
│   ├── controller/   RouteController (POST /route, GET /route/{id})
│   ├── dto/          request/ + response/
│   └── service/      RouteService (calls Python dp-pipeline)
├── navigation/
│   ├── controller/   NavigationController (panorama-results, reroute, conversation)
│   │                 TrackingWebSocketHandler (WebSocket /tracking)
│   ├── dto/          request/ + response/
│   └── service/      NavigationService (calls Python deviation)
│                     ConversationService (calls Python LLM)
├── client/                         # Python service HTTP clients
│   ├── PipelineClient.java        # dp-pipeline (port 8000)
│   └── DeviationClient.java       # deviation (port 8001)
└── model/
    ├── enums/        DpType, NavigationState, MatchStatus, Position, GuidanceAction, WeatherCondition
    └── vo/           Location, Weather
```

### Layer Rules

| Layer | Role | Business Logic |
|---|---|---|
| Controller | HTTP/WebSocket request mapping | **None** |
| Service | Call Python service + assemble response | **Relay only** |
| DTO | Data exchange. 1:1 with API spec fields | None |
| Client | HTTP calls to Python FastAPI services | None |

### Endpoint → Controller → Python Service

| App Endpoint | Controller | Python Call |
|---|---|---|
| `POST /route` | RouteController | `POST localhost:8000/pipeline/route` |
| `GET /route/{routeId}` | RouteController | `GET localhost:8000/pipeline/route/{routeId}` |
| `POST /route/{routeId}/panorama-results` | NavigationController | `POST localhost:8000/pipeline/panorama` |
| `POST /route/{routeId}/reroute` | NavigationController | `POST localhost:8000/pipeline/reroute` |
| `POST /route/{routeId}/conversation` | NavigationController | `POST localhost:8000/pipeline/conversation` |
| `WebSocket /tracking` | TrackingWebSocketHandler | `POST localhost:8001/deviation/check` |

### Java / Spring Boot Style
- Lombok: `@Getter`, `@Builder`, `@RequiredArgsConstructor`
- Controller: `@RestController` + `@RequestMapping("/route")`
- WebSocket: `TextWebSocketHandler` + `WebSocketConfig`
- Python calls: WebClient + `.block()` (synchronous OK for prototype)
- Error handling: `throw new CustomException(ErrorCode.XXX)` → GlobalExceptionHandler
- DTOs are immutable: `@Getter` + `@Builder` only, no setters
- Python returns snake_case → Spring Boot converts or frontend handles

### Config (application.yml)

```yaml
server:
  port: 8080
python:
  dp-pipeline:
    base-url: http://localhost:8000
  deviation:
    base-url: http://localhost:8001
```

API keys are managed by Python services, NOT Spring Boot.

### What NOT to Do (Backend)
- No business logic in Spring Boot — Python handles all pipeline/scoring/detection
- No direct external API calls (Tmap, Kakao, Google) — Python does this
- No Domain objects exposed to client (DTO conversion required)
- No fields in response not in API spec

---

## Python Services — FastAPI (Hyewon)

**Python executes ALL business logic.** Spring Boot only relays.

### Project Structure

```
services/
├── dp-pipeline/                    # Route creation pipeline (port 8000)
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # API keys, settings
│   ├── constants.py               # turnType mapping, P values, w_mod, isOpen coefficients
│   ├── schemas.py                 # Pydantic models (request/response)
│   ├── geo.py                     # Haversine, bearing, point-segment distance, LineString interpolation
│   ├── tmap_service.py            # Tmap API call + GeoJSON parsing
│   ├── dp_extractor.py            # turnType-based DP extraction
│   ├── poi_service.py             # Kakao Local API + adaptive radius + left/right judgment
│   ├── panorama_service.py        # Multi-direction pan calculation + isPrimary
│   ├── scoring_service.py         # S_final = P(h) × (D(w) + U + C_bonus)
│   ├── cross_validator.py         # POI vs Vision matching (exact → partial → category)
│   ├── sequence_optimizer.py      # Greedy + direction consistency
│   ├── guidance_generator.py      # DP type templates + LLM prompt
│   └── route_cache.py             # Cache management
└── deviation/                     # Off-route detection (port 8001)
    ├── main.py                    # FastAPI app entry
    ├── config.py
    ├── schemas.py
    ├── geo.py                     # Shared geo functions
    └── deviation_service.py       # Speed filter → distance → duration → continuity
```

### Python Style
- FastAPI + Pydantic for request/response validation
- Type hints on all functions
- snake_case for all Python code (Spring Boot converts to camelCase for app)
- API keys via `.env` + `config.py`
- Each service file = one pipeline STEP or one responsibility

### Python Endpoints

| Endpoint | Role |
|---|---|
| `POST /api/route` | Route creation + landmark + guidance |
| `POST /api/deviation` | Off-route detection |
| `POST /api/reroute` | Re-routing (new pipeline run) |
| `POST /api/chat` | Conversational guidance (LLM) |

### Key Modules

| Module | Functions | Used By |
|---|---|---|
| `geo.py` | Haversine distance, bearing, point-segment distance, LineString interpolation | Everywhere |
| `constants.py` | turnType mapping, P(h) category values, w_mod table, isOpen coefficients | Scoring, DP extraction |
| `schemas.py` | Pydantic models for all request/response types | All endpoints |

### What NOT to Do (Python)
- No direct app-facing endpoints — Spring Boot handles app communication
- No frontend logic or UI concerns
- Response JSON must match API spec (Spring Boot passes through)

---

## Shared Rules (Frontend + Backend + Python)

### API Spec is the Source of Truth
- Field names, types, enum values must match API spec v0.1.0
- Do not add fields not in the spec
- When spec changes, sync all layers

### Common Conventions
- Location: `{ latitude, longitude }` (WGS84)
- Position: `LEFT`, `RIGHT`, `FRONT`
- REST responses: `{ status: "SUCCESS", data: { ... } }` or `{ status: "ERROR", error: { ... } }`
- Python uses snake_case internally; app-facing JSON uses camelCase
- Content-Type: `application/json`