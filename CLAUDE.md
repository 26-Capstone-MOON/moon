# CLAUDE.md
## 1. Project Overview

Landmark-based spatial description pedestrian navigation system.

The goal is NOT to eliminate the map.
The goal is to **reduce screen dependency** by adding multiple guidance channels
so users can navigate even when they can't actively watch the screen.

Guidance channels: map (base layer) + spatial description + voice TTS + haptic vibration + panorama view.

---

## 2. Core Concept

Navigation is based on **Decision Points (DP)**.

At each DP, the backend:
1. Selects the best landmark via scoring model: `S_final = P(h) × (D(w) + U + C_bonus)`
2. Generates spatial description guidance per DP type
3. Sends complete guidance package to frontend

DP types: Direction change (3-step), Crosswalk (before+after), Virtual (confirmation), Vertical move (fixed+POI).
See `domain.md` for detailed guidance patterns and examples.

**Frontend does NOT select landmarks or generate guidance.**
Backend decides everything. Frontend renders and executes.

---

## 3. Architecture

### Monorepo structure
```
MOON/
├── frontend/       React Native + Android Studio, TypeScript
├── backend/        Spring Boot 3 + Java 17 — API Gateway (no business logic)
├── services/       Python FastAPI — core pipeline + deviation detection
│   ├── dp-pipeline/   (port 8000) route creation pipeline STEP 1~6
│   └── deviation/     (port 8001) off-route detection + rerouting
├── docs/           Design docs, API spec, screen specs
└── .claude/rules/  coding.md, domain.md, output.md, workflow.md
```

### Request flow
```
[React Native App]
    |
    |  REST API (JSON) / WebSocket
    v
[Spring Boot]  ── API Gateway (Jihyun)
    |
    |  Internal HTTP calls
    v
[Python FastAPI]  ── Core logic (Hyewon)
    |
    +-- dp-pipeline  → route pipeline STEP 1~6 + external APIs
    +-- deviation    → off-route detection logic
```

**Spring Boot does NOT execute business logic.** It receives requests from the app, forwards to Python services, and returns Python's response to the app.

### Role assignment

| Layer | Owner | Role |
|---|---|---|
| React Native | Minwoo | UI, GPS collection, TTS/STT, Naver Panorama capture |
| Spring Boot | Jihyun | REST API / WebSocket endpoints, Python service relay |
| Python dp-pipeline | Hyewon | Route creation, DP extraction, POI, scoring, guidance generation |
| Python deviation | Hyewon | Off-route detection (speed→distance→duration→continuity) |

### Commands

**Frontend:**
```bash
cd frontend
npm install
npx react-native run-android
npx react-native start
```

**Backend (Spring Boot):**
```bash
cd backend
./gradlew bootRun                    # port 8080
./gradlew build
./gradlew test
```

**Python services (Hyewon):**
```bash
cd services/dp-pipeline && uvicorn main:app --port 8000
cd services/deviation && uvicorn main:app --port 8001
```

---

## 4. Frontend Role

### DOES:
- Render guidance text, play TTS (Mode A: auto / Mode B: conversational)
- Trigger haptic feedback
- Show panorama (execute Naver Panorama using server's panoramaRequest data)
- Show map with route polyline
- Connect WebSocket `/tracking` and send GPS every 1s
- Process server trigger responses (PRE_ALERT, ARRIVAL, DEVIATION_WARNING, etc.)
- Upload panorama Vision results via `POST /route/{routeId}/panorama-results`

### MUST NOT:
- Calculate routes, select landmarks, perform scoring, generate guidance text
- Detect route deviation (server handles via WebSocket response)

---

## 5. Backend Pipeline (Reference Only)

Python dp-pipeline executes STEP 0~6 (Weather → DP extraction → Virtual DP → POI → Panorama → Scoring → Sequence optimization → Guidance → Cache). See `domain.md` for full details.

---

## 6. Navigation Flow (API-driven)
```
1. POST /route → Spring Boot → Python dp-pipeline → RouteResponse
2. Client executes panorama → Vision → POST /route/{routeId}/panorama-results
3. Navigation loop (WebSocket):
   - Client connects WebSocket /tracking
   - Client sends GPS every 1s as JSON
   - Spring Boot → Python deviation → response via WebSocket
   - Client acts on trigger:
     PRE_ALERT (30m) → TTS preAlert
     ARRIVAL (10m)   → TTS primary + haptic
     CONFIRMATION    → TTS confirmation (Virtual DP)
     DEVIATION_WARNING → "Seems like you've gone off route"
     REROUTING       → "Finding a new route, one moment"
     RETURN_DETECTED → "You're coming back on track"
4. Mode B: earphone → STT → POST /route/{routeId}/conversation → TTS
5. Off-route → DEVIATION_CONFIRMED → POST /route/{routeId}/reroute → new route
6. ARRIVED → done
```

---

## 7. App Screens

See `docs/screens.md` for screen specs (Home, RouteConfirm, Navigation, Progress, Off-Route).

---

## 8. Key Types (API spec v0.1.0)

### DecisionPoint (core type)
```ts
interface DecisionPoint {
  dpId: string;
  dpType: 'DEPARTURE' | 'ARRIVAL' | 'DIRECTION_CHANGE' | 'CROSSWALK' | 'VERTICAL_MOVE' | 'VIRTUAL';
  turnType: number | null;
  location: { latitude: number; longitude: number };
  distanceFromStart: number;
  guidance: {
    primary: string;
    preAlert: string | null;
    action: 'RIGHT_TURN' | 'LEFT_TURN' | 'U_TURN' | 'CROSSWALK' | 'STAIRS_UP' | 'STAIRS_DOWN' | 'OVERPASS' | 'UNDERPASS' | 'ELEVATOR' | null;
  };
  selectedLandmark: {
    name: string; categoryCode: string; position: 'LEFT' | 'RIGHT' | 'FRONT';
    distance: number; score: number; matchStatus: 'MATCHED' | 'POI_ONLY' | 'VISION_ONLY'; isOpen: boolean;
  } | null;
  panoramaRequest: {
    location: { latitude: number; longitude: number };
    directions: { pan: number; label: 'FRONT' | 'LEFT' | 'RIGHT'; isPrimary: boolean }[];
  } | null;
}
```

### WebSocket Tracking Response (navigation loop)
```ts
interface TrackingResponse {
  navigationState: 'ON_ROUTE' | 'DEVIATION_SUSPECTED' | 'DEVIATION_WARNING' | 'DEVIATION_CONFIRMED' | 'RETURNING' | 'REROUTING' | 'ARRIVED';
  currentDpId: string;
  distanceToDp: number;
  trigger: 'PRE_ALERT' | 'ARRIVAL' | 'CONFIRMATION' | 'DEVIATION_WARNING' | 'REROUTING' | 'RETURN_DETECTED' | null;
  guidance: { primary: string; preAlert: string | null; action: string | null } | null;
  progress: {
    completedDps: string[]; currentDpId: string; remainingDps: string[];
    distanceRemaining: number; timeRemaining: number;
  };
}
```

For full RouteResponse and ConversationResponse types, see API spec document.

---

## 9. API Endpoints

**REST API**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/route` | Create route (pipeline STEP 1~6) |
| `GET` | `/route/{routeId}` | Get cached route |
| `POST` | `/route/{routeId}/panorama-results` | Upload Vision results |
| `POST` | `/route/{routeId}/reroute` | Re-route |
| `POST` | `/route/{routeId}/conversation` | Mode B conversational |

**WebSocket**

| Endpoint | Description |
|---|---|
| `/tracking` | Real-time GPS tracking + guidance triggers + deviation detection |

**Common response:** `{ "status": "SUCCESS"|"ERROR", "data"|"error": { ... } }`
**Base URL:** `https://api.moon-app.dev/v1`

---

## 10. MVP Scope

See `workflow.md` for phase details (F1~F3 frontend, B1~B5 backend, Python Day 1~8).
**NOT in MVP**: 3D map, auth, iOS, offline mode.

---

## 11. Rules

All detailed rules are in:
- `.claude/rules/coding.md` — code conventions (frontend + backend + Python)
- `.claude/rules/domain.md` — scoring, DP types, off-route detection
- `.claude/rules/output.md` — code output format, mock data, fallback
- `.claude/rules/workflow.md` — phases, priorities, sync timeline

**These rules override general preferences.**