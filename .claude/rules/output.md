# Output Rules

## File Creation
- Explain what files will be created BEFORE creating them
- One feature = minimum files needed
- Do not create empty placeholder files
- Do not create files "for later"

## Code Output
- Working code only (must run without errors)
- Include all necessary imports
- Include TypeScript types
- No placeholder comments like "// TODO: implement later"
- If something is not implemented, omit it entirely

## Response Format
- Start with what you're building and why
- Show file path before each code block
- Keep explanations brief
- No unnecessary preamble

## Mock Data
- Always provide mock data when building new features
- Mock data must match the TypeScript types exactly
- Mock data should be realistic (Korean addresses, real brand names)
- Place mock data in src/mocks/

## Fallback
- Every guidance display must handle: text missing, landmark missing, DP missing
- Never render empty or broken state
- Default: show basic directional text

## Language
- Code: English
- Comments: English (Korean OK for domain terms like DP, 횡단보도)
- UI text: Korean
- Guidance text: Korean

## What NOT to Output
- Do not output architecture diagrams
- Do not output planning documents
- Do not explain what you "could" build
- Do not suggest features outside MVP scope
- Do not output backend code (unless specifically asked)