# Coding Rules

## Component Rules
- Functional components only (no class components)
- One component = one responsibility
- Props must be typed (no `any`)

## State Rules
- Local state first (useState)
- No global state unless genuinely needed
- If global needed → zustand or context (minimal)

## Style Rules
- Keep files short (< 150 lines preferred)
- Flat imports, no deep nesting
- No barrel exports unless project grows large

## Naming
- Components: PascalCase (GuidanceCard.tsx)
- Hooks: camelCase with use- prefix (useGuidance.ts)
- Types: PascalCase (DecisionPoint)
- Files match export name

## TypeScript
- Always type props, state, return values
- No `any` unless truly unavoidable
- Prefer interface over type for objects

## Libraries
- Do not add libraries without clear need
- Prefer built-in React Native APIs
- TTS: react-native-tts or expo-speech
- Vibration: React Native Vibration API

## No Over-Engineering
- Do not create wrapper functions for single-use logic
- Do not build generic utility classes "for reuse"
- Do not add abstraction layers before there is duplication
- Do not create separate config files for things used once
- Do not introduce design patterns (factory, observer, etc.) unless clearly needed
- If you're writing more infrastructure than feature code, stop
- Rule of three: only abstract after the same pattern appears 3+ times

## What NOT to Do
- Do not create unused abstractions
- Do not build "just in case" architecture
- Do not add files that aren't immediately used
- Do not optimize before it works
- Do not use class components