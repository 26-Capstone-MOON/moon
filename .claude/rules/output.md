# Output Rules

## General
- One feature = minimum files needed. No placeholder files, no files "for later".
- Working code only. Include all imports. No `// TODO` comments.
- Include TypeScript types (frontend) / Java + Lombok (backend) / Python type hints (services)

---

## Frontend Output Rules

### Route Data
- Use real server responses that match API spec v0.1.0 response types exactly
- Route data should preserve Korean addresses, real POI names, and server-provided DP ordering
- Keep route fixtures in test-only locations when tests need static input
- RouteResponse and TrackingResponse structure must match CLAUDE.md §8

### Fallback
- Every guidance display must handle: text missing, landmark missing, DP missing
- Never render empty or broken state
- Default: show basic directional text
- Handle all `trigger` values including `null` (no trigger = no TTS/haptic)
- Handle all `navigationState` values (show appropriate UI per state)
- Handle WebSocket disconnection gracefully (reconnect + fallback UI)

### Language
- Code: English
- Comments: English (Korean OK for domain terms)
- UI text: Korean
- Guidance text: Korean

### What NOT to Output (Frontend)
- Do not output architecture diagrams or planning documents
- Do not suggest features outside MVP scope
- Do not output backend or Python code (unless specifically asked)

---

## Backend Output Rules (Spring Boot — API Gateway)

For code patterns (Controller, Service, Client, WebSocket handler), see `coding.md` backend section.

### What NOT to Do (Backend)
- No business logic — Python handles all pipeline/scoring/detection
- No direct external API calls (Tmap, Kakao, Google)
- No fields in response not in API spec
- No API keys in Spring Boot (Python manages them)

---

## Shared Output Rules

### API Spec is the Source of Truth
- Field names, types, enum values must match API spec v0.1.0
- Frontend types and backend responses must share identical structure
- Do not add fields not in the spec
- Python returns snake_case → Spring Boot converts to camelCase for app

### Enum Values
All enum definitions with values and meanings are in `domain.md`.
Frontend, backend, and Python must use identical enum values.

Key enums: DpType, NavigationState, MatchStatus, Position, GuidanceAction, Trigger
