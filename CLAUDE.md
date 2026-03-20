# CLAUDE.md
## 1. Project Overview

Landmark-based spatial description pedestrian navigation system.
**지형지물 기반 공간 설명 길 안내 시스템**

The goal is NOT to eliminate the map.
The goal is to **reduce screen dependency** by adding multiple guidance channels
so users can navigate even when they can't actively watch the screen.

### Core Channels (multi-channel guidance)

| Channel | Role | When Used |
|---|---|---|
| **Map + location** | Route polyline + current position on map | Always visible (base layer) |
| **Spatial description** | Landmark-based text instruction | Always (primary guidance) |
| **Voice (TTS)** | Spoken guidance | Always (primary guidance) |
| **Haptic (vibration)** | Directional vibration patterns | DP approach + direction change |
| **Panorama view** | Street view image of next DP | Always visible (supplementary) |

The map is always visible as the base layer — like existing navigation apps.
What we ADD on top: spatial description, voice, haptic, and panorama.
The user can navigate by listening + feeling vibration alone,
but the map is always there when they glance at the screen.

---

## 2. Target Scenario

NOT only for "both hands occupied" situations.
Designed to be **universally useful** for any pedestrian:

**High restriction:**
- Holding an umbrella
- Carrying heavy bags with both hands
- Pushing a stroller

**Medium restriction:**
- Walking in crowded areas
- Rainy/snowy weather
- Running or fast walking

**Low restriction (still beneficial):**
- Unfamiliar area (spatial descriptions more intuitive than map lines)
- Elderly users (prefer voice over complex map UI)
- General walking (reduce cognitive load from constant screen checking)

---

## 3. What We're Solving

### Problem with existing navigation
- Relies on: 2D map + route line + distance numbers
- User must: constantly look at screen → match position → interpret direction
- Causes: cognitive load, attention split, missed turns, safety issues
- No real-time voice guidance for walking (unlike car navigation)
- No automatic re-routing when walking off-path

### Our approach
- **Spatial description**: "노란 건물 스타벅스에서 우회전"
- **Voice guidance**: TTS reads instruction before each DP
- **Haptic feedback**: vibration pattern indicates upcoming turn
- **Panorama preview**: see what the next DP looks like (optional)
- **Map as background**: route overview still available
- **Auto re-route**: detect off-route and regenerate guidance

---

## 4. Core Concept

Navigation is based on **Decision Points (DP)**.

At each DP, the backend:
1. Selects the best landmark nearby
2. Generates a spatial description
3. Sends guidance text to frontend

Frontend then:
1. Shows the instruction
2. Speaks it (TTS)
3. Vibrates (haptic)
4. Optionally shows panorama of the DP location

Example:
"스타벅스를 지나서 우회전하세요. 94m 직진 후 횡단보도를 건너세요."

**Frontend does NOT select landmarks or generate guidance.**
Backend decides everything. Frontend renders and executes.

---

## 5. Tech Stack

**Frontend:** React Native (Android-first), TypeScript
**Backend:** Spring Boot (main server) + FastAPI (AI/scoring pipeline)

**Planned APIs (not all needed for MVP):**
- Tmap Pedestrian Route API — route + DP extraction
- Kakao Local API — POI search around DPs
- Naver Panorama API — street view images (supplementary)
- Naver Map SDK — map rendering (background)
- Google Places API — business hours (isOpen)
- OpenAI Vision API — panorama image analysis
- OpenAI LLM API — guidance text generation
- Weather API — environment adjustment for scoring

**Device APIs:**
- Android TTS, Vibration API, Fused Location Provider

**Cache:** Redis (optional)

Start with mock data. Integrate real APIs incrementally.

---

## 6. Team

- **Minwoo (오민우)** — React Native frontend, UI/UX, TTS/haptic, location
- **Jihyun (김지현)** — Spring Boot backend, route handling, API orchestration
- **Hyewon (홍혜원)** — FastAPI AI pipeline, scoring model, Vision/LLM

---

## 7. Frontend Role

### DOES:
- Render guidance text (spatial description)
- Play TTS (voice)
- Trigger haptic feedback (vibration)
- Show panorama image (on-demand, supplementary)
- Show map with route (background, supplementary)
- Manage DP progression
- Detect basic off-route state

### MUST NOT:
- Calculate routes
- Select landmarks
- Perform scoring
- Generate guidance text

Backend provides the complete instruction. Frontend executes it.

---

## 8. Backend Pipeline (Reference Only)

Frontend does not implement this. For context:
```
1. Tmap API → extract DPs (turnType filtering)
2. Insert Virtual DPs on long straight segments (~200m)
3. Parallel: Panorama image + POI data collection
4. Vision API analyzes panorama → structured JSON
5. Cross-validate Vision vs POI → score + select landmark
6. LLM generates guidance sentence (does NOT pick landmark)
7. Package as EnhancedRoute → cache → send to client
```

Key rules:
- Scoring model selects landmark. LLM only writes the sentence.
- MATCHED (Vision+POI) > POI_ONLY > VISION_ONLY
- Fallback: no landmark → basic direction instruction

---

## 9. Navigation Flow
```
1. User inputs destination (Home Screen)
2. Backend generates route → DPs → guidance
3. Frontend loads EnhancedRoute (or mock JSON for MVP)
4. Navigation starts:
   a. Show current DP instruction (text)
   b. TTS speaks the instruction
   c. Haptic vibrates on approach / direction change
   d. Panorama available on-demand (tap to see)
   e. Map shows position in background
5. User progresses to next DP
6. Repeat until destination
7. If off-route → re-route → new DPs → new guidance
```

---

## 10. App Screens

### Home Screen
Layout (top to bottom):
- **Header**: App name (MOON) + settings icon
- **Greeting**: "안녕하세요" + "어디로 모실까요?"
- **Search section**:
  - 현재 위치 (auto-filled, blue dot)
  - 도착지 입력 field + voice input icon (mic)
- **Quick actions** (two cards, side by side):
  - 바로가기 우리집 (saved home shortcut)
  - 길을 잃었다면 → 잃어버렸어요 (re-route from current position)
- **Recent destinations**:
  - 최근에 간 곳 label
  - List: name + address + distance (tappable → starts navigation)

Behavior:
- Destination input → route API (or mock) → NavigationScreen
- 우리집 tap → instant navigation to saved home
- 잃어버렸어요 tap → current GPS → re-route to last destination
- Recent item tap → starts navigation to that place

### Navigation Screen 
Layout (top to bottom):
- **Top bar**: direction indicator to next DP (arrow + label)
- **Center (main area)**: Naver Map SDK
  - Route polyline displayed
  - User's current position marker (real-time)
  - SDK built-in compass (rotates with map orientation)
  - Looks like a normal map app at first glance
- **Bottom card 1**: Panorama image (거리뷰) of next DP
- **Bottom card 2**: Guidance text + speaker icon (tap to replay TTS)

Key difference from existing map apps:
- Map shows WHERE you are (same as existing apps)
- Bottom cards show WHAT to do next (our addition)
- TTS TELLS you what to do (our addition)
- Haptic ALERTS you when to act (our addition)

### Progress Screen (swipe from navigation)
Layout:
- **Top bar**: progress percentage (진행 상황 %)
- **Right panel**:
  - Current direction to next DP
  - 구조 단서 설명 (structural cue description)
  - Checkpoint list with ✓ marks for passed DPs (vertical scroll)
- **Bottom**: Map SDK with route

### Lock Screen Widget 
Layout:
- **Top**: current time
- **Bottom**: compact compass + direction arrow + short guidance text

### Off-Route Screen 
- Same as Navigation Screen BUT:
- Map area: **red overlay** + "경로를 이탈했습니다"
- TTS announces off-route

### Re-Route Screen 
- Same as Navigation Screen BUT:
- Map area: "다시 경로를 안내합니다"
- New route polyline + new 거리뷰 + new guidance text loaded

### Screen Flow
```
Home → Navigation 
         ↕ swipe
       Progress 

Navigation → [off-route] → Off-Route 
Off-Route → [re-route done] → Re-Route → Navigation
```

---

## 11. Key Types
```ts
interface DecisionPoint {
  id: string;
  coordinate: { lat: number; lng: number };
  turnType: number;
  category: string;
  isVirtual: boolean;
  guidanceText: string;
  landmark?: {
    name: string;
    position: string;
    matchStatus: string;
  };
  panoramaUrl?: string;
  distanceFromPrev: number;
}

interface EnhancedRoute {
  routeId: string;
  polyline: { lat: number; lng: number }[];
  decisionPoints: DecisionPoint[];
  totalDistance: number;
  estimatedTime: number;
}

interface GuidanceState {
  currentDPIndex: number;
  nextDP: DecisionPoint | null;
  distanceToNextDP: number;
  isOffRoute: boolean;
  isNavigating: boolean;
}
```

---

## 12. API Endpoints (Backend)
```
POST  /api/route          → EnhancedRoute (origin, destination)
GET   /api/route/:id      → cached route
POST  /api/route/reroute  → re-route from current position
```

---

## 13. MVP Scope

### Phase 1 (mock data only)
- Home screen (search + quick actions + recent)
- Navigation screen (guidance card + TTS + haptic)
- Progress screen (checkpoint list)
- Mock JSON route data
- DP progression (manual or distance-based)
- TTS on DP change
- Basic haptic feedback

### Phase 2 (after Phase 1 works)
- Real GPS location tracking
- DP proximity trigger
- Panorama image display
- Off-route detection UI
- Backend API integration
- Map rendering (Naver Map SDK)
- Lock screen widget

### NOT in MVP
- 3D map, auth, AI chat, iOS, offline mode

---

## 14. Rules

All detailed rules are in:
- `.claude/rules/coding.md`
- `.claude/rules/domain.md`
- `.claude/rules/output.md`
- `.claude/rules/workflow.md`

**These rules override general preferences.**

---

## 15. Key Constraint

This project is NOT about replacing the map.
It is about **adding channels** — voice, haptic, spatial description, panorama —
so that the map becomes one of many ways to navigate, not the only way.

The user should be able to reach their destination
with minimal screen interaction.
