"""STEP 4: Sequence optimization — name dedup + direction consistency.

After scoring selects the best landmark per DP, this module optimizes the
full-route sequence to avoid confusing consecutive guidance.

Phase 1 (forward greedy): no consecutive same NAME landmarks. Category
        duplicates are allowed (U already penalizes density, and brand
        colors/signs differ visually).
Phase 2 (direction consistency): detect LEFT→RIGHT→LEFT (or reverse)
        zigzag and swap the middle slot to a same-side candidate when
        score drop is within tolerance.

Both phases consider only the top-k candidates per DP and require a
swap candidate to stay within SWAP_SCORE_TOLERANCE of the original Top-1.
"""

from __future__ import annotations

from dataclasses import dataclass

from scoring_service import ScoredPoi

# Maximum score drop (fraction) allowed when swapping a candidate
SWAP_SCORE_TOLERANCE = 0.20

# Number of top-ranked candidates per DP considered for swaps
TOP_K_CANDIDATES = 5


@dataclass
class DpLandmarkSlot:
    """A DP paired with its ranked POI candidates and selected landmark.

    Attributes:
        dp_index: Position of this DP in the route sequence.
        candidates: All scored POIs for this DP, sorted by s_final desc.
        selected_idx: Index into candidates for the current selection.
    """

    dp_index: int
    candidates: list[ScoredPoi]
    selected_idx: int = 0

    @property
    def selected(self) -> ScoredPoi | None:
        """Currently selected landmark, or None if no candidates."""
        if not self.candidates:
            return None
        return self.candidates[self.selected_idx]

    @property
    def place_name(self) -> str | None:
        sel = self.selected
        return sel.poi.place_name if sel else None

    @property
    def category_code(self) -> str | None:
        sel = self.selected
        return sel.poi.category_group_code if sel else None

    @property
    def position(self) -> str | None:
        sel = self.selected
        return sel.poi.position if sel else None

    @property
    def score(self) -> float:
        sel = self.selected
        return sel.s_final if sel else 0.0


# ---------------------------------------------------------------------------
# Phase 1: Forward greedy — eliminate consecutive same-name landmarks
# ---------------------------------------------------------------------------

def _phase1_dedup(slots: list[DpLandmarkSlot]) -> None:
    """Eliminate consecutive same-NAME landmarks (category dups allowed).

    Walks forward through the sequence. When a slot's selected landmark
    shares the same name as the previous slot, scan up to TOP_K_CANDIDATES
    ranked candidates for an alternative whose name differs and whose
    score stays within SWAP_SCORE_TOLERANCE of the original Top-1.
    If no qualifying alternative exists, keep the original (better to
    repeat than leave empty).

    Mutates slots in-place by updating selected_idx.
    """
    for i in range(1, len(slots)):
        prev = slots[i - 1]
        curr = slots[i]

        if not curr.candidates or not prev.selected:
            continue

        if not _name_conflict(prev, curr):
            continue

        alt = _find_alternative_name(curr, prev.place_name)
        if alt is not None:
            curr.selected_idx = alt


def _name_conflict(a: DpLandmarkSlot, b: DpLandmarkSlot) -> bool:
    """Two slots conflict only when their landmark names are identical."""
    if a.place_name is None or b.place_name is None:
        return False
    return a.place_name == b.place_name


def _find_alternative_name(
    slot: DpLandmarkSlot,
    blocked_name: str | None,
) -> int | None:
    """Find an alternative candidate whose name differs from blocked_name.

    Considers up to TOP_K_CANDIDATES candidates and only returns indices
    whose score is within SWAP_SCORE_TOLERANCE of the original Top-1.

    Args:
        slot: DP slot to search alternatives for.
        blocked_name: Name to avoid (typically the previous DP's landmark).

    Returns:
        Candidate index, or None if no qualifying alternative exists.
    """
    if not slot.candidates or blocked_name is None:
        return None

    original_score = slot.candidates[0].s_final
    if original_score <= 0:
        return None

    min_score = original_score * (1.0 - SWAP_SCORE_TOLERANCE)
    limit = min(TOP_K_CANDIDATES, len(slot.candidates))

    for idx in range(limit):
        if idx == slot.selected_idx:
            continue
        candidate = slot.candidates[idx]
        if candidate.poi.place_name == blocked_name:
            continue
        if candidate.s_final < min_score:
            continue
        return idx

    return None


# ---------------------------------------------------------------------------
# Phase 2: Direction consistency — fix left-right-left zigzag
# ---------------------------------------------------------------------------

def _phase2_direction_consistency(slots: list[DpLandmarkSlot]) -> None:
    """Detect and fix left→right→left (or right→left→right) zigzag patterns.

    Scans triplets of consecutive slots. When positions form a zigzag
    (e.g. LEFT→RIGHT→LEFT), tries to swap the middle slot's landmark
    to match one of the neighbors' sides, within 20% score tolerance.

    Mutates slots in-place.
    """
    if len(slots) < 3:
        return

    for i in range(1, len(slots) - 1):
        prev_slot = slots[i - 1]
        curr_slot = slots[i]
        next_slot = slots[i + 1]

        prev_pos = prev_slot.position
        curr_pos = curr_slot.position
        next_pos = next_slot.position

        # Skip if any slot has no landmark
        if not all([prev_pos, curr_pos, next_pos]):
            continue

        # Detect zigzag: prev and next same side, current is opposite
        if prev_pos == next_pos and curr_pos != prev_pos and curr_pos != "FRONT":
            target_side = prev_pos
            _try_swap_to_side(curr_slot, target_side)


def _try_swap_to_side(
    slot: DpLandmarkSlot,
    target_side: str,
) -> None:
    """Try to swap slot's landmark to one on target_side within tolerance.

    Only swaps if the replacement is among the top-k candidates and its
    score stays within SWAP_SCORE_TOLERANCE of the original Top-1.

    Args:
        slot: The slot to potentially swap.
        target_side: Desired position ("LEFT" or "RIGHT").
    """
    if not slot.candidates:
        return

    original_score = slot.candidates[0].s_final
    if original_score <= 0:
        return

    min_score = original_score * (1.0 - SWAP_SCORE_TOLERANCE)
    limit = min(TOP_K_CANDIDATES, len(slot.candidates))

    for idx in range(limit):
        if idx == slot.selected_idx:
            continue
        candidate = slot.candidates[idx]
        if candidate.poi.position == target_side and candidate.s_final >= min_score:
            slot.selected_idx = idx
            return


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def optimize_sequence(
    dp_candidates: list[list[ScoredPoi]],
) -> list[ScoredPoi | None]:
    """Optimize landmark sequence across all DPs.

    Takes per-DP ranked candidate lists (from scoring_service.rank_pois)
    and returns the optimized selection for each DP.

    Args:
        dp_candidates: List of ranked ScoredPoi lists, one per DP.
                       Each inner list is sorted by s_final descending.

    Returns:
        List of selected ScoredPoi (or None) for each DP, in order.
    """
    slots = [
        DpLandmarkSlot(dp_index=i, candidates=candidates)
        for i, candidates in enumerate(dp_candidates)
    ]

    _phase1_dedup(slots)
    _phase2_direction_consistency(slots)

    return [slot.selected for slot in slots]
