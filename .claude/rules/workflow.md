# Workflow Rules

## Development Order

Always follow this sequence:
1. Types first (define interfaces)
2. Mock data (matching types)
3. Basic screen (renders mock data)
4. Core logic (hooks, services)
5. Connect logic to screen
6. Enhancement (TTS, haptic, polish)
7. Replace mock → real API integration
8. Naver Map SDK + GPS location tracking
9. End-to-end test with real route data

Step 1~6: mock data로 프론트 플로우 완성
Step 7~9: 중간발표 전까지 실제 API 연동

Never skip steps. Never jump to step 5 before step 3 works.
Mock first → flow works → then connect real API.

## Build Strategy
- One feature at a time
- Each feature must work before moving to next
- Test with mock data first
- Real API integration comes last

## Screen Priority
Build in this order:
1. NavigationScreen (guidance + TTS + haptic)
2. HomeScreen (search + quick actions + recent)
3. ProgressScreen (checkpoint list)

## Change Rules
- Do not restructure project without explicit request
- Do not rename existing files without reason
- Do not move files between folders without reason
- If modifying existing file: show what changes and why

## When Stuck
- Simplify the approach
- Use hardcoded values to unblock
- Get it working first, improve later
- Ask for clarification rather than assume

## Integration Order (Phase 2)
1. Location tracking (GPS)
2. DP proximity detection
3. Backend API connection
4. Map SDK (basic)
5. Panorama display
6. Off-route detection
7. Lock screen widget

Do not start Phase 2 until Phase 1 works end-to-end with mock data.

## Absolute Rules
- MVP only. No future features.
- Mock first. Real API later.
- Working > perfect.
- Simple > clever.