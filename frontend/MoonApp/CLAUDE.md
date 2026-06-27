# CLAUDE.md — MoonApp Frontend

## Project

Pedestrian navigation app that guides users with landmark-based spatial descriptions instead of distance-based directions. Built with React Native (bare workflow) targeting Android.

## Tech Stack

- React Native (bare workflow, no Expo)
- TypeScript (strict)
- Zustand (state management)
- Naver Map SDK (map, polyline, markers)
- React Navigation (screen routing)
- Axios (HTTP client)

## Directory Structure

```
src/
  components/    Reusable UI (DpMarker, RoutePolyline, ChatBubble, VoiceButton, etc.)
  screens/       Screen components (Home, Search, RouteConfirm, Navigation, Progress)
  hooks/         Custom hooks (useLocation, useWebSocket, etc.)
  stores/        Zustand stores (routeStore, navigationStore, settingsStore)
  services/      External integrations (apiClient, ttsService, hapticService, locationService)
  types/         TypeScript type definitions matching API spec
  utils/         Helper functions
  constants/     App-wide constants
```

## Naming Conventions

- Components: PascalCase (`DpMarker.tsx`, `RoutePolyline.tsx`)
- Hooks: camelCase with `use` prefix (`useLocation.ts`, `useWebSocket.ts`)
- Services: camelCase (`ttsService.ts`, `hapticService.ts`)
- Types/Interfaces: PascalCase (`RouteResponse`, `DecisionPoint`)
- Constants: UPPER_SNAKE_CASE (`API_BASE_URL`)
- Files: match their default export name

## State Management

Three Zustand stores. Do not use Redux or Context API.

- `routeStore` — route data, decision points, polyline coordinates
- `navigationStore` — current navigation state, active DP, guidance triggers
- `settingsStore` — user preferences (TTS speed, haptic toggle, etc.)

Keep stores independent. Minimize cross-store dependencies.

## API Communication

### REST (via apiClient)
- `POST /api/route` — create route
- `GET /api/route/{routeId}` — get cached route
- `POST /api/route/{routeId}/reroute` — reroute request
- `POST /api/route/{routeId}/conversation` — chat mode (Mode B)

### WebSocket
- `/api/tracking` — real-time GPS tracking + deviation detection
- Client sends GPS data every second
- Server responds with navigation state, triggers, guidance

### Data Policy
- Production code calls the real Spring Boot server only.
- Landmark candidates are selected server-side from merged Kakao POI, Tmap facility, and OSM spatial-element candidates.
- Test route fixtures, when needed, live outside `src/` and are not imported by production code.
- Route creation failures must surface as errors rather than successful navigation states.

### Response Format
- Server returns snake_case (`route_id`, `total_distance`)
- Frontend converts to camelCase before use
- All responses follow: `{ "status": "SUCCESS", "data": { ... } }`

## Screen Flow

```
Home -> Search -> RouteConfirm -> Navigation -> Progress
                                      |
                                      +-> DeviationScreen (not yet implemented)
```

- Home: origin/destination input
- Search: place search
- RouteConfirm: route preview on map, "Start Navigation" button
- Navigation: map + guidance card + TTS + haptic feedback
- Progress: checkpoint timeline of completed DPs
- DeviationScreen: rerouting UI (F2 scope)

## Services Detail

### ttsService
- Reads guidance text aloud
- Triggers on DP approach (PRE_ALERT at 30m, ARRIVAL at 10m)
- Plays deviation warnings and rerouting notifications

### hapticService
- Vibration feedback on direction changes
- Different patterns for turn, crosswalk, arrival

### locationService (TODO — F2 scope)
- Sends GPS coordinates to server via WebSocket every second
- Receives navigation state (ON_ROUTE, DEVIATION_WARNING, REROUTING, RETURN_DETECTED)
- Updates navigationStore based on server response
- Depends on backend WebSocket being ready

### apiClient
- Axios-based HTTP client with shared config
- Intercepts errors and maps to user-friendly messages
- Calls the real Spring Boot server; production code does not import test fixtures

## Component Guidelines

- Keep components small and focused. One component, one responsibility.
- Extract logic into hooks or services. Components should mostly render.
- Always define TypeScript types. Avoid `any`.
- Use functional components only. No class components.
- Destructure props in function signature.
- Colocate styles with components or use a shared style file per screen.

## Hook Guidelines

- Prefix with `use`. One hook, one concern.
- `useLocation` — GPS watchPosition wrapper
- `useWebSocket` — WebSocket connection lifecycle (connect, send, receive, disconnect)
- Return clean-up functions in useEffect.

## Map Integration

- Naver Map SDK via react-native-nmap or equivalent bridge
- `RoutePolyline` component draws the route path
- `DpMarker` component renders decision point markers with type-specific icons
- Map camera follows user location during navigation

## Current Status

### Done
- Type definitions
- Naver Map + Polyline + DP markers
- GPS watchPosition (useLocation hook)
- TTS trigger + haptic feedback
- 3 Zustand stores
- 5 screen UIs
- Real backend API connection
- GPS deviation detection + rerouting UI path
- Chat mode (Mode B)
- Naver Panorama display
- Design updates

### Server-Driven Vision Context
- The app displays server-provided panorama data and guidance.
- Vision results, when available on the server, are merged into route cache for scoring, guidance appearance, and conversational context.
- Surrounding descriptions use server-provided route context.

### Later
- Error handling + retry logic
- Arrival screen
- WebSocket auto-reconnect
- UI/UX refinements

## Commands

```bash
npx react-native start          # start Metro bundler
npx react-native run-android    # build and run on Android
npm install                     # install dependencies
npx tsc --noEmit                # type check without emit
npx eslint src/                 # lint source files
```

## Do

- Follow existing patterns when creating new files
- Define types for all API responses and component props
- Use Zustand selectors to avoid unnecessary re-renders
- Handle loading and error states in every screen
- Convert snake_case server responses to camelCase at the API layer

## Do Not

- Use `any` type
- Put business logic in components — use hooks or services
- Create new state management patterns — use Zustand
- Import test fixtures from production `src/` code
- Present client-side Vision analysis as implemented
- Skip TypeScript types for "quick fixes"
