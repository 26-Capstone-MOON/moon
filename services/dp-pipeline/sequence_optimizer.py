"""STEP 4.5: Sequence optimization — greedy dedup + direction consistency.

After scoring selects the best landmark per DP, this module optimizes the
full-route sequence to avoid confusing consecutive guidance.

Phase 1 (forward greedy): no consecutive same name or category.
Phase 2 (direction consistency): detect left→right→left zigzag and swap
        within 20% score tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass

from poi_service import PoiResult
from scoring_service import ScoredPoi, score_poi

# Maximum score drop (%) allowed when swapping to fix zigzag
SWAP_SCORE_TOLERANCE = 0.20


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
# Phase 1: Forward greedy — eliminate consecutive same name/category
# ---------------------------------------------------------------------------

def _phase1_dedup(slots: list[DpLandmarkSlot]) -> None:
    """Eliminate consecutive same-name or same-category landmarks.

    Walks forward through the sequence. When a slot's selected landmark
    shares name or category with the previous slot, try the next-best
    candidate. If no alternative exists, keep the original (better to
    repeat than leave empty).

    Mutates slots in-place by updating selected_idx.
    """
    for i in range(1, len(slots)):
        prev = slots[i - 1]
        curr = slots[i]

        if not curr.candidates or not prev.selected:
            continue

        # Check conflict with previous
        if not _conflicts(prev, curr):
            continue

        # Try alternative candidates
        best_alt = _find_non_conflicting(curr, prev)
        if best_alt is not None:
            curr.selected_idx = best_alt


def _conflicts(a: DpLandmarkSlot, b: DpLandmarkSlot) -> bool:
    """Check if two slots have conflicting (same name or category) landmarks."""
    if a.place_name is None or b.place_name is None:
        return False
    if a.place_name == b.place_name:
        return True
    if a.category_code == b.category_code:
        return True
    return False


def _find_non_conflicting(
    slot: DpLandmarkSlot,
    prev: DpLandmarkSlot,
) -> int | None:
    """Find the best non-conflicting candidate index for a slot.

    Returns:
        Candidate index, or None if all candidates conflict.
    """
    for idx in range(len(slot.candidates)):
        if idx == slot.selected_idx:
            continue

        original = slot.candidates[slot.selected_idx]
        candidate = slot.candidates[idx]

        # Check conflict
        if prev.place_name and candidate.poi.place_name == prev.place_name:
            continue
        if prev.category_code and candidate.poi.category_group_code == prev.category_code:
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

    Only swaps if the replacement score is within 20% of the current score.

    Args:
        slot: The slot to potentially swap.
        target_side: Desired position ("LEFT" or "RIGHT").
    """
    if not slot.candidates or slot.score == 0:
        return

    min_score = slot.score * (1.0 - SWAP_SCORE_TOLERANCE)

    for idx, candidate in enumerate(slot.candidates):
        if idx == slot.selected_idx:
            continue
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
