# Workflow Rules

---

## Frontend Development Order

Always follow this sequence:
1. Types first (define interfaces — API spec v0.1.0)
2. Mock data (matching types)
3. Basic screen (renders mock data)
4. Core logic (hooks, services)
5. Connect logic to screen
6. Enhancement (TTS, haptic, polish)
7. Replace mock → real API integration (REST + WebSocket)
8. Naver Map SDK + GPS location tracking
9. End-to-end test with real route data

Step 1~6: complete frontend flow with mock data
Step 7~9: real API integration when server is ready

Never skip steps. Mock first → flow works → then connect real API.

### Frontend Phases

**Phase F1: Core infra + map**
- Refactor mock data to API spec structure + redefine types
- Naver Map integration + Polyline + DP markers
- GPS watchPosition + current location marker
- TTS trigger (30m → preAlert, 10m → primary) + haptic
- Zustand (useRouteStore, useNavigationStore)
- API client + mock mode flag (USE_MOCK)
- **Done when: NavigationScreen shows map + route line + GPS + TTS working**

**Phase F2: Server integration + WebSocket + deviation**
- POST /route real server integration
- WebSocket /tracking connection → send GPS every 1s → trigger-based TTS/haptic
- POST /route/{routeId}/reroute deviation UI + re-routing flow
- POST /route/{routeId}/conversation STT → server → TTS
- ProgressScreen implementation
- **Done when: REST + WebSocket integrated + deviation/conversation working**

**Phase F3: Polish + demo prep**
- Loading/error handling, WebSocket reconnection, UI consistency
- Demo route rehearsal (real device)
- Demo fallback (mock mode switch if server down)
- **Done when: demo-ready state**

### Frontend Priority

| Priority | Items | Demo Required |
|---|---|---|
| P0 | TTS, Naver Map, Polyline, GPS, TTS connection | Required |
| P1 | Type redefinition, Zustand, REST API + WebSocket integration, deviation UI | Required |
| P2 | ProgressScreen, conversational (Mode B), panorama | Nice to have |
| P3 | Lock screen widget, voice search | After midterm |

---

## Backend Development Order (Spring Boot — API Gateway)

**Phase B1: Skeleton**
- Package structure, ApiResponse, ErrorCode, GlobalExceptionHandler
- All Enums, Location VO, application.yml
- WebClientConfig (for Python HTTP calls), CorsConfig
- **Done when: project runs without errors**

**Phase B2: Route REST APIs**
- RouteController + RouteService → PipelineClient
- POST /route, GET /route/{routeId}
- Mock Python response if Hyewon's service not ready
- **Done when: `POST /route` returns response (real or mock Python)**

**Phase B3: Remaining REST APIs**
- NavigationController → panorama-results, reroute, conversation
- PipelineClient methods for each endpoint
- ConversationService
- **Done when: all 5 REST endpoints working**

**Phase B4: WebSocket GPS tracking**
- WebSocketConfig + TrackingWebSocketHandler
- DeviationClient → POST localhost:8001/deviation/check
- Receive GPS JSON → call Python → send response via WebSocket
- **Done when: WebSocket /tracking sends and receives JSON correctly**

**Phase B5: Integration + testing**
- Full flow: app → Spring Boot → Python → response
- Error handling for Python service failures
- **Done when: all endpoints + WebSocket working end-to-end**

### Backend Endpoint → Python Service Mapping

| App Endpoint | Python Service | Python URL |
|---|---|---|
| `POST /route` | dp-pipeline | `POST :8000/pipeline/route` |
| `GET /route/{routeId}` | dp-pipeline | `GET :8000/pipeline/route/{routeId}` |
| `POST /route/{routeId}/panorama-results` | dp-pipeline | `POST :8000/pipeline/panorama` |
| `POST /route/{routeId}/reroute` | dp-pipeline | `POST :8000/pipeline/reroute` |
| `POST /route/{routeId}/conversation` | dp-pipeline | `POST :8000/pipeline/conversation` |
| `WebSocket /tracking` | deviation | `POST :8001/deviation/check` |

---

## Python Services — Hyewon (8 days)

**dp-pipeline (port 8000):** route creation pipeline STEP 1~6, external API calls
**deviation (port 8001):** off-route detection + rerouting

### Python Endpoints (delivered to backend)

| Endpoint | Role | Input | Output |
|---|---|---|---|
| `POST /api/route` | Route + landmark + guidance | origin/dest coords | DP list + landmarks + guidance + panorama |
| `POST /api/deviation` | Off-route detection | GPS + route data | normal/warning/confirmed/returning |
| `POST /api/reroute` | Re-routing | GPS + destination | new DP list + guidance |
| `POST /api/chat` | Conversational guidance | question + context | LLM response text |

### Python Development Phases

**Day 1~2:** Foundation + DP extraction + Midpoint + POI + panorama
**Day 3:** Scoring + cross-validation + sequence optimization
**Day 4~5:** Vision prompts + guidance generation (Mode A + B)
**Day 6:** Off-route detection + rerouting
**Day 7~8:** Endpoint integration + full testing

Interface agreements (JSON shape) needed before backend integration.

---

## Frontend ↔ Backend ↔ Python Sync

```
  [Frontend]  F1 (mock)  →  F2 (server + WS)  →  F3 (polish)
  [Backend]   B1~B2 (skeleton+route) → B3 (REST) → B4 (WebSocket) → B5 (test)
  [Python]    Day 1~5 (dp-pipeline)  → Day 6 (deviation) → Day 7~8 (integration)
```

### Integration Order

| Backend Phase | Endpoint Provided | Frontend Integration |
|---|---|---|
| B2 done | `POST /route` (DP + routeLineString) | During F2 |
| B3 done | panorama-results, reroute, conversation | During F2 |
| B4 done | `WebSocket /tracking` (trigger + guidance) | During F2 |

### Server Delay Contingency

- Mock mode flag (`USE_MOCK=true`) enables demo without server
- Frontend self-calculates DP proximity for TTS/haptic trigger as fallback
- Spring Boot can mock Python responses if Python services not ready
- Demo can show full flow using mock data even if server is unavailable

---

## Build Strategy (shared)
- One feature at a time
- Each feature must work before moving to next
- Test after each step (frontend: real device, backend: Postman, Python: pytest)
- Real API integration comes last

## Change Rules
- Do not restructure project without explicit request
- Do not rename existing files without reason
- If modifying existing file: show what changes and why

## When Stuck
- Simplify the approach
- Use hardcoded values to unblock
- Get it working first, improve later
- Ask for clarification rather than assume

## Absolute Rules
- MVP only. No future features.
- Mock first. Real API later.
- Working > perfect.
- Simple > clever.
- API spec is the source of truth.