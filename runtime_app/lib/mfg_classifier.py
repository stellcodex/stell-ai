"""
app/services/mfg_classifier.py

Manufacturing Process Classifier.

Determines the optimal manufacturing process from extracted geometry data.
No external dependencies — pure Python rule engine.

Supported processes (in order of detection confidence):
  - cnc_turning     CNC lathe / turning centre
  - cnc_milling     CNC machining centre (3-axis or 5-axis)
  - sheet_metal     Sheet metal fabrication (laser/plasma cut + bend + weld)
  - laser_cutting   2-D flat profile laser cut (no bending)
  - waterjet        2-D thick plate waterjet cut
  - 3d_printing     Additive manufacturing
  - casting         Die casting or sand casting
  - welding         Structural welded assembly
  - unknown         Insufficient data to classify
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProcessResult:
    process: str                        # primary process (snake_case)
    process_label: str                  # human-readable label
    confidence: float                   # 0.0 – 1.0
    secondary_processes: list[str]      # additional ops (e.g. heat treatment)
    reasons: list[str]                  # why this was chosen
    dfm_notes: list[str]                # design-for-manufacturing observations
    setup_count: int                    # estimated number of CNC setups / operations
    raw_scores: dict[str, float]        # internal scores for each candidate


_PROCESS_LABELS: dict[str, str] = {
    "cnc_turning":   "CNC Turning",
    "cnc_milling":   "CNC Milling",
    "sheet_metal":   "Sheet Metal Fabrication",
    "laser_cutting": "Laser Cutting",
    "waterjet":      "Waterjet Cutting",
    "3d_printing":   "3D Printing",
    "casting":       "Die Casting / Sand Casting",
    "welding":       "Welded Assembly",
    "unknown":       "Unknown — Manual Review Required",
}


# ---------------------------------------------------------------------------
# Heuristic scoring engine
# ---------------------------------------------------------------------------

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def classify_manufacturing_process(
    geometry_meta: dict[str, Any],
    *,
    override_process: str | None = None,
) -> ProcessResult:
    """
    Classify the manufacturing process from geometry_meta dict.

    geometry_meta is the dict returned by StepGeometryResult.to_geometry_meta()
    or the geometry_meta_json field stored in UploadFile.meta.

    Parameters
    ----------
    geometry_meta : dict  — full geometry metadata
    override_process : str | None — if set, skip heuristics and return this process
        (confidence=1.0, reasons=["manual override"])

    Returns
    -------
    ProcessResult
    """
    if override_process and override_process in _PROCESS_LABELS:
        return ProcessResult(
            process=override_process,
            process_label=_PROCESS_LABELS[override_process],
            confidence=1.0,
            secondary_processes=[],
            reasons=["Manual override applied."],
            dfm_notes=[],
            setup_count=1,
            raw_scores={},
        )

    bbox: dict = geometry_meta.get("bbox") or {}
    bx = _safe_float(bbox.get("x"), 1.0)
    by = _safe_float(bbox.get("y"), 1.0)
    bz = _safe_float(bbox.get("z"), 1.0)

    dims = sorted([bx, by, bz])
    dim_min, dim_mid, dim_max = dims
    diagonal = _safe_float(geometry_meta.get("diagonal"), 1.0)
    volume_mm3 = _safe_float(geometry_meta.get("volume"), bx * by * bz)

    surfaces: dict = geometry_meta.get("surfaces") or {}
    n_plane        = _safe_int(surfaces.get("plane", 0))
    n_cyl          = _safe_int(surfaces.get("cylindrical", 0))
    n_con          = _safe_int(surfaces.get("conical", 0))
    n_sph          = _safe_int(surfaces.get("spherical", 0))
    n_tor          = _safe_int(surfaces.get("toroidal", 0))
    n_bspl         = _safe_int(surfaces.get("b_spline", 0))
    n_surf_total   = n_plane + n_cyl + n_con + n_sph + n_tor + n_bspl + 1

    holes: list    = geometry_meta.get("holes") or []
    n_holes        = len(holes)
    has_threads    = bool(geometry_meta.get("has_threads", False))

    complexity_d: dict = geometry_meta.get("complexity") or {}
    face_count     = _safe_int(complexity_d.get("face_count", 0))
    complexity_lbl = str(complexity_d.get("label", "MED")).upper()

    part_count     = _safe_int(geometry_meta.get("part_count", 1))

    # --- Candidate scores ------------------------------------------------
    scores: dict[str, float] = {p: 0.0 for p in _PROCESS_LABELS}

    reasons: list[str] = []
    dfm_notes: list[str] = []

    # ---- CNC TURNING heuristic ----
    # Key signal: one dimension much larger than the other two,
    # high fraction of cylindrical / conical / toroidal surfaces,
    # and/or very large diameter holes along the axis.
    aspect_ratio_long = dim_max / max(dim_mid, 1.0)   # how elongated
    aspect_ratio_flat = dim_mid / max(dim_min, 1.0)   # how round in cross-section

    rot_fraction = (n_cyl + n_con + n_tor) / n_surf_total
    turning_score = 0.0
    if aspect_ratio_long > 2.0:
        turning_score += 0.25
        reasons.append(f"Part is elongated ({aspect_ratio_long:.1f}:1 length ratio).")
    if rot_fraction > 0.25:
        turning_score += min(rot_fraction * 1.5, 0.5)
        reasons.append(f"High rotational surface fraction ({rot_fraction:.0%}).")
    # Check if largest hole diameter ≈ mid cross-section dimension (bore)
    if holes:
        max_hole_dia = max(h.get("diameter_mm", 0) for h in holes)
        if max_hole_dia > 0.4 * dim_mid:
            turning_score += 0.2
            reasons.append(f"Large bore detected (Ø{max_hole_dia:.1f} mm ≈ {max_hole_dia/dim_mid:.0%} of cross-section).")
    scores["cnc_turning"] += turning_score

    # ---- CNC MILLING heuristic ----
    # Box-like shape, mix of planar and cylindrical, holes in various directions
    box_ratio = dim_min / max(dim_max, 1.0)   # how cubic
    milling_score = 0.0
    if box_ratio > 0.1:
        milling_score += 0.2
    plane_fraction = n_plane / n_surf_total
    if plane_fraction > 0.2:
        milling_score += min(plane_fraction, 0.4)
    if n_holes > 0 and aspect_ratio_long < 3.0:
        milling_score += min(n_holes / 20.0, 0.2)
    if complexity_lbl in ("MED", "HIGH"):
        milling_score += 0.1
    scores["cnc_milling"] += milling_score

    # ---- SHEET METAL heuristic ----
    # Very thin in one dimension relative to others (wall << area dimensions)
    wall_mm_min = _safe_float(geometry_meta.get("wall_mm_min"))
    sm_score = 0.0
    if wall_mm_min > 0 and wall_mm_min < 12.0 and dim_min < 20.0:
        ratio = dim_min / max(dim_max, 1.0)
        if ratio < 0.05:
            sm_score += 0.5
            reasons.append(f"Thin-walled geometry detected (thickness ≈ {dim_min:.1f} mm).")
        elif ratio < 0.15:
            sm_score += 0.3
    scores["sheet_metal"] += sm_score

    # ---- LASER CUTTING / WATERJET heuristic ----
    # Very flat (one dim << 5mm) AND no complex 3D features
    lc_score = 0.0
    if dim_min < 6.0 and n_bspl < 5 and n_tor < 5:
        lc_score += 0.4
        if dim_min < 3.0:
            lc_score += 0.2
    scores["laser_cutting"] += lc_score
    scores["waterjet"] += lc_score * 0.7  # waterjet is secondary option

    # ---- 3D PRINTING heuristic ----
    # Small size OR very complex free-form surfaces with no obvious machining setup
    print_score = 0.0
    if diagonal < 100.0:
        print_score += 0.15
    if n_bspl > 20 and n_plane < 5:
        print_score += 0.3
        reasons.append("High free-form surface count — 3D printing may be optimal.")
    if face_count > 200 and rot_fraction < 0.2:
        print_score += 0.1
    scores["3d_printing"] += print_score

    # ---- CASTING heuristic ----
    # Large volume + complex external form
    cast_score = 0.0
    if volume_mm3 > 1_000_000 and part_count == 1:
        cast_score += 0.15
    if n_con > 5 or n_sph > 5:
        cast_score += 0.1
    scores["casting"] += cast_score

    # ---- WELDED ASSEMBLY heuristic ----
    # Multiple parts
    if part_count > 3:
        scores["welding"] += 0.3
        reasons.append(f"Multi-part assembly ({part_count} parts) — welded assembly likely.")

    # --- Determine winner ------------------------------------------------
    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]

    # Normalise confidence
    second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
    gap = best_score - second_best
    confidence = min(0.95, best_score + gap * 0.3) if best_score > 0.05 else 0.1

    if best_score < 0.15:
        best = "unknown"
        confidence = 0.0
        reasons.append("Insufficient geometry signals — manual review required.")

    # --- Secondary processes --------------------------------------------
    secondary: list[str] = []
    if has_threads:
        secondary.append("thread_cutting")
        dfm_notes.append("Thread features detected. Verify thread standard (metric/UNC/BSP).")
    if best == "cnc_milling" and n_holes > 10:
        secondary.append("drilling")
    if face_count > 100:
        dfm_notes.append(f"High face count ({face_count}) may require 5-axis setup.")
    if best == "cnc_turning" and dim_max > 500:
        dfm_notes.append(f"Part length {dim_max:.0f} mm may require steady rest support.")
    if best in ("cnc_milling", "cnc_turning") and complexity_lbl == "HIGH":
        dfm_notes.append("HIGH complexity: verify tool access for all features before quoting.")

    # --- Setup count estimate ------------------------------------------
    if best == "cnc_turning":
        setup_count = 2 if n_holes > 5 else 1
        if dim_max > 300:
            setup_count += 1
    elif best == "cnc_milling":
        setup_count = 2
        if face_count > 150:
            setup_count = 3
    elif best in ("sheet_metal", "laser_cutting", "waterjet"):
        setup_count = 1
    else:
        setup_count = 1

    if not reasons:
        reasons.append(f"Best heuristic match: {_PROCESS_LABELS.get(best, best)}.")

    return ProcessResult(
        process=best,
        process_label=_PROCESS_LABELS.get(best, best),
        confidence=round(confidence, 3),
        secondary_processes=secondary,
        reasons=reasons,
        dfm_notes=dfm_notes,
        setup_count=setup_count,
        raw_scores={k: round(v, 4) for k, v in scores.items()},
    )
