# 데모 시연 안내 문구 — 서일체육문화센터 → 역삼1문화센터

## 경로 개요

| 항목 | 값 |
|---|---|
| 출발지 | 서일체육문화센터 (서초구 서운로21길 2) |
| 도착지 | 역삼1문화센터 (강남구 역삼로7길 16) |
| 총 거리 | 약 1,650m |
| 예상 소요 시간 | 약 22분 |
| DP 수 | 9개 (출발 + 도착 포함) |

---

## 경로 DP 구성

```
DP0 [DEPARTURE]        서일체육문화센터 앞
 │  150m 직진
DP1 [DIRECTION_CHANGE]  서운로 → 강남대로 방향 우회전
 │  200m 직진
DP2 [CROSSWALK]         강남대로 횡단보도
 │  350m 직진
DP3 [VIRTUAL]           강남대로 직진 구간 중간 확인
 │  250m 직진
DP4 [DIRECTION_CHANGE]  강남대로 → 역삼로 방향 좌회전
 │  180m 직진
DP5 [CROSSWALK]         역삼로 횡단보도
 │  150m 직진
DP6 [VERTICAL_MOVE]     지하보도 계단 하행
 │  120m 직진
DP7 [VIRTUAL]           역삼로7길 진입 확인
 │  100m 직진
DP8 [ARRIVAL]           역삼1문화센터 도착
```

---

## DP별 안내 문구

### DP0 — DEPARTURE (출발)

| 항목 | 값 |
|---|---|
| dpId | `dp-0` |
| dpType | `DEPARTURE` |
| turnType | `200` |
| 위치 | 서일체육문화센터 정문 앞 |
| distanceFromStart | 0m |
| trigger | — (즉시 재생) |
| selectedLandmark | `null` |

| 안내 유형 | 안내 문구 |
|---|---|
| **primary** | "서일체육문화센터에서 출발할게요. 건물을 등지고 앞쪽 도로를 따라 직진하세요." |
| **preAlert** | `null` |
| **action** | `null` |

> **참고**: 출발지에는 랜드마크를 선정하지 않음. 출발 방향만 안내.

---

### DP1 — DIRECTION_CHANGE (우회전)

| 항목 | 값 |
|---|---|
| dpId | `dp-1` |
| dpType | `DIRECTION_CHANGE` |
| turnType | `12` (우회전) |
| 위치 | 서운로 끝 → 강남대로 교차 지점 |
| distanceFromStart | 150m |
| selectedLandmark | 세븐일레븐 서초서운점 |
| categoryCode | `CS2` (편의점) |
| position | `RIGHT` |
| matchStatus | `MATCHED` |
| score | 1.18 |

**3-step 안내 (WebSocket trigger 기반)**

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `PRE_ALERT` | 30m 전 | "곧 오른쪽에 세븐일레븐이 보일 거예요. 거기서 우회전할 준비를 하세요." |
| `ARRIVAL` | 10m 도착 | "오른쪽 세븐일레븐 끼고 우회전하세요." |
| — | — | *(haptic: 진동 1회)* |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **preAlert** | "곧 오른쪽에 세븐일레븐이 보일 거예요. 거기서 우회전할 준비를 하세요." |
| **primary** | "오른쪽 세븐일레븐 끼고 우회전하세요." |
| **action** | `RIGHT_TURN` |

---

### DP2 — CROSSWALK (횡단보도)

| 항목 | 값 |
|---|---|
| dpId | `dp-2` |
| dpType | `CROSSWALK` |
| turnType | `211` |
| 위치 | 강남대로 횡단보도 |
| distanceFromStart | 350m |
| selectedLandmark (건너기 전) | 올리브영 강남대로점 |
| categoryCode | `CS2` |
| position | `RIGHT` |
| matchStatus | `POI_ONLY` |
| score | 1.05 |

**횡단보도 안내 (before + after)**

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `PRE_ALERT` | 30m 전 | "올리브영 앞에 횡단보도가 있어요. 건널 준비를 하세요." |
| `ARRIVAL` | 10m 도착 | "올리브영 앞 횡단보도를 건너세요. 건너면 왼쪽에 하나은행이 보여요. 그쪽으로 쭉 직진하세요." |
| — | — | *(haptic: 진동 1회)* |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **preAlert** | "올리브영 앞에 횡단보도가 있어요. 건널 준비를 하세요." |
| **primary** | "올리브영 앞 횡단보도를 건너세요. 건너면 왼쪽에 하나은행이 보여요. 그쪽으로 쭉 직진하세요." |
| **action** | `CROSSWALK` |

---

### DP3 — VIRTUAL (직진 확인)

| 항목 | 값 |
|---|---|
| dpId | `dp-3` |
| dpType | `VIRTUAL` |
| turnType | `null` |
| 위치 | 강남대로 직진 구간 중간 (DP2에서 350m) |
| distanceFromStart | 700m |
| selectedLandmark | 신한은행 강남중앙지점 |
| categoryCode | `BK9` (은행) |
| position | `LEFT` |
| matchStatus | `MATCHED` |
| score | 1.89 |

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `CONFIRMATION` | 도착 시 | "왼쪽에 신한은행이 보이면 잘 가고 있는 거예요. 그대로 쭉 직진하세요." |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **primary** | "왼쪽에 신한은행이 보이면 잘 가고 있는 거예요. 그대로 쭉 직진하세요." |
| **preAlert** | `null` |
| **action** | `null` |

> **참고**: Virtual DP는 PRE_ALERT 없이 CONFIRMATION trigger만 발생.

---

### DP4 — DIRECTION_CHANGE (좌회전)

| 항목 | 값 |
|---|---|
| dpId | `dp-4` |
| dpType | `DIRECTION_CHANGE` |
| turnType | `13` (좌회전) |
| 위치 | 강남대로 → 역삼로 교차로 |
| distanceFromStart | 950m |
| selectedLandmark | 스타벅스 강남역삼로점 |
| categoryCode | `CE7` (카페) |
| position | `LEFT` |
| matchStatus | `MATCHED` |
| score | 1.01 |

**3-step 안내 (WebSocket trigger 기반)**

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `PRE_ALERT` | 30m 전 | "곧 왼쪽에 스타벅스가 보일 거예요. 스타벅스에서 좌회전하세요." |
| `ARRIVAL` | 10m 도착 | "스타벅스 끼고 좌회전하세요. 역삼로 방향이에요." |
| — | — | *(haptic: 진동 1회)* |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **preAlert** | "곧 왼쪽에 스타벅스가 보일 거예요. 스타벅스에서 좌회전하세요." |
| **primary** | "스타벅스 끼고 좌회전하세요. 역삼로 방향이에요." |
| **action** | `LEFT_TURN` |

---

### DP5 — CROSSWALK (횡단보도)

| 항목 | 값 |
|---|---|
| dpId | `dp-5` |
| dpType | `CROSSWALK` |
| turnType | `211` |
| 위치 | 역삼로 횡단보도 |
| distanceFromStart | 1130m |
| selectedLandmark (건너기 전) | GS25 역삼로점 |
| categoryCode | `CS2` (편의점) |
| position | `RIGHT` |
| matchStatus | `MATCHED` |
| score | 1.26 |

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `PRE_ALERT` | 30m 전 | "GS25 앞에 횡단보도가 있어요. 건널 준비를 하세요." |
| `ARRIVAL` | 10m 도착 | "GS25 앞 횡단보도를 건너세요. 건너면 오른쪽에 이디야커피가 보여요. 그쪽으로 직진하세요." |
| — | — | *(haptic: 진동 1회)* |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **preAlert** | "GS25 앞에 횡단보도가 있어요. 건널 준비를 하세요." |
| **primary** | "GS25 앞 횡단보도를 건너세요. 건너면 오른쪽에 이디야커피가 보여요. 그쪽으로 직진하세요." |
| **action** | `CROSSWALK` |

---

### DP6 — VERTICAL_MOVE (지하보도 하행)

| 항목 | 값 |
|---|---|
| dpId | `dp-6` |
| dpType | `VERTICAL_MOVE` |
| turnType | `126` (지하보도) |
| 위치 | 역삼로 지하보도 입구 |
| distanceFromStart | 1280m |
| selectedLandmark | CU 역삼센트럴점 |
| categoryCode | `CS2` (편의점) |
| position | `LEFT` |
| matchStatus | `POI_ONLY` |
| score | 0.88 |

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `PRE_ALERT` | — | `null` |
| `ARRIVAL` | 10m 도착 | "왼쪽에 CU 지나면 바로 지하보도 입구가 나와요. 계단을 내려가세요." |
| — | — | *(haptic: 진동 1회)* |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **preAlert** | `null` |
| **primary** | "왼쪽에 CU 지나면 바로 지하보도 입구가 나와요. 계단을 내려가세요." |
| **action** | `UNDERPASS` |

> **참고**: VERTICAL_MOVE는 preAlert 없이 도착 시 1회 안내. POI + 고정 지시문 조합.

---

### DP7 — VIRTUAL (최종 확인)

| 항목 | 값 |
|---|---|
| dpId | `dp-7` |
| dpType | `VIRTUAL` |
| turnType | `null` |
| 위치 | 역삼로7길 진입 직후 |
| distanceFromStart | 1400m |
| selectedLandmark | 국민은행 역삼지점 |
| categoryCode | `BK9` (은행) |
| position | `RIGHT` |
| matchStatus | `MATCHED` |
| score | 1.94 |

| trigger | 시점 | 안내 문구 |
|---|---|---|
| `CONFIRMATION` | 도착 시 | "오른쪽에 국민은행이 보이면 거의 다 왔어요. 조금만 더 직진하세요." |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **primary** | "오른쪽에 국민은행이 보이면 거의 다 왔어요. 조금만 더 직진하세요." |
| **preAlert** | `null` |
| **action** | `null` |

---

### DP8 — ARRIVAL (도착)

| 항목 | 값 |
|---|---|
| dpId | `dp-8` |
| dpType | `ARRIVAL` |
| turnType | `201` |
| 위치 | 역삼1문화센터 정문 |
| distanceFromStart | 1650m |
| selectedLandmark | 역삼1문화센터 |
| categoryCode | `PO3` (공공기관) |
| position | `FRONT` |
| matchStatus | `MATCHED` |
| score | 2.14 |

| trigger | 시점 | 안내 문구 |
|---|---|---|
| — | 도착 시 | "목적지 역삼1문화센터에 도착했어요! 안내를 종료합니다." |

| 안내 유형 | 안내 문구 (JSON용) |
|---|---|
| **primary** | "목적지 역삼1문화센터에 도착했어요! 안내를 종료합니다." |
| **preAlert** | `null` |
| **action** | `null` |

---

## 이탈 시나리오 안내 문구 (데모용)

데모 영상에서 경로 이탈 → 복귀 시나리오를 보여줄 경우:

| navigationState | trigger | 안내 문구 |
|---|---|---|
| `DEVIATION_WARNING` | `DEVIATION_WARNING` | "경로에서 벗어난 것 같아요." |
| `DEVIATION_CONFIRMED` | `REROUTING` | "새로운 경로를 찾고 있어요. 잠시만 기다려주세요." |
| `RETURNING` | `RETURN_DETECTED` | "다시 경로로 돌아오고 있어요. 잘하고 있어요!" |

---

## TTS 재생 순서 요약 (시연 시나리오)

| 순서 | DP | trigger | TTS 재생 내용 |
|---|---|---|---|
| 1 | DP0 | 즉시 | "서일체육문화센터에서 출발할게요. 건물을 등지고..." |
| 2 | DP1 | PRE_ALERT (30m) | "곧 오른쪽에 세븐일레븐이 보일 거예요..." |
| 3 | DP1 | ARRIVAL (10m) | "오른쪽 세븐일레븐 끼고 우회전하세요." + 진동 |
| 4 | DP2 | PRE_ALERT (30m) | "올리브영 앞에 횡단보도가 있어요..." |
| 5 | DP2 | ARRIVAL (10m) | "올리브영 앞 횡단보도를 건너세요. 건너면 왼쪽에 하나은행이..." + 진동 |
| 6 | DP3 | CONFIRMATION | "왼쪽에 신한은행이 보이면 잘 가고 있는 거예요..." |
| 7 | DP4 | PRE_ALERT (30m) | "곧 왼쪽에 스타벅스가 보일 거예요..." |
| 8 | DP4 | ARRIVAL (10m) | "스타벅스 끼고 좌회전하세요. 역삼로 방향이에요." + 진동 |
| 9 | DP5 | PRE_ALERT (30m) | "GS25 앞에 횡단보도가 있어요..." |
| 10 | DP5 | ARRIVAL (10m) | "GS25 앞 횡단보도를 건너세요. 건너면 오른쪽에 이디야커피가..." + 진동 |
| 11 | DP6 | ARRIVAL (10m) | "왼쪽에 CU 지나면 바로 지하보도 입구가..." + 진동 |
| 12 | DP7 | CONFIRMATION | "오른쪽에 국민은행이 보이면 거의 다 왔어요..." |
| 13 | DP8 | 도착 | "목적지 역삼1문화센터에 도착했어요!" |

**총 TTS 재생 횟수: 13회** (preAlert 4회 + primary/arrival 6회 + confirmation 2회 + departure 1회)

---

## 랜드마크 요약

| DP | 랜드마크 | 카테고리 | 위치 | matchStatus | score |
|---|---|---|---|---|---|
| DP0 | — | — | — | — | — |
| DP1 | 세븐일레븐 서초서운점 | CS2 (편의점) | RIGHT | MATCHED | 1.18 |
| DP2 | 올리브영 강남대로점 | CS2 | RIGHT | POI_ONLY | 1.05 |
| DP3 | 신한은행 강남중앙지점 | BK9 (은행) | LEFT | MATCHED | 1.89 |
| DP4 | 스타벅스 강남역삼로점 | CE7 (카페) | LEFT | MATCHED | 1.01 |
| DP5 | GS25 역삼로점 | CS2 (편의점) | RIGHT | MATCHED | 1.26 |
| DP6 | CU 역삼센트럴점 | CS2 (편의점) | LEFT | POI_ONLY | 0.88 |
| DP7 | 국민은행 역삼지점 | BK9 (은행) | RIGHT | MATCHED | 1.94 |
| DP8 | 역삼1문화센터 | PO3 (공공기관) | FRONT | MATCHED | 2.14 |

> **편의점 연속 방지**: DP2(올리브영→CS2) → DP3(은행→BK9) → DP4(카페→CE7) — 같은 카테고리 연속 없음 (sequence optimization 준수)
