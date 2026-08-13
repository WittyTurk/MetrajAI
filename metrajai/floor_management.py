from __future__ import annotations

import hashlib
import unicodedata

from .contracts import (
    AnalysisWarning,
    DetectedElement,
    FloorDefinition,
    FloorKind,
    RepeatAssignment,
    RepeatScope,
    ReviewStatus,
    SheetKind,
    SourceFile,
)

REPEATABLE_STRUCTURAL_TYPES = {"column", "beam", "slab", "shear_wall", "stair"}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(character for character in text if not unicodedata.combining(character)).upper()


def infer_floor_kind(floor: str, original_name: str = "", role: str = "") -> FloorKind:
    value = _normalize(" ".join((floor, original_name, role)))
    if "TEMEL" in value or "RADYE" in value:
        return FloorKind.FOUNDATION
    if "BODRUM" in value:
        return FloorKind.BASEMENT
    if "ZEMIN" in value:
        return FloorKind.GROUND
    if "CATI" in value:
        return FloorKind.ROOF
    if "TIP KAT" in value or "NORMAL KAT" in value:
        return FloorKind.TYPICAL
    if "DETAY" in value:
        return FloorKind.DETAIL
    return FloorKind.GENERAL


def infer_sheet_kind(original_name: str, role: str = "") -> SheetKind:
    value = _normalize(" ".join((original_name, role)))
    if "KOLON" in value and "APLIKASYON" in value:
        return SheetKind.COLUMN_APPLICATION
    if "DONATI" in value and "KALIP" not in value:
        return SheetKind.REBAR_PLAN
    if "TEMEL" in value or "RADYE" in value:
        return SheetKind.FOUNDATION
    if "DETAY" in value:
        return SheetKind.DETAIL
    if "CIZELGE" in value or "LISTE" in value:
        return SheetKind.SCHEDULE
    if "KESIT" in value:
        return SheetKind.SECTION
    if "GORUNUS" in value:
        return SheetKind.ELEVATION
    if any(token in value for token in ("KALIP", "PLAN", "APLIKASYON")):
        return SheetKind.PLAN
    return SheetKind.UNSPECIFIED


def apply_sheet_ownership(
    elements: list[DetectedElement],
    source: SourceFile,
    project_sources: list[SourceFile],
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    """Prevent the same discipline quantities from competing across sheet roles."""
    if source.sheet_kind == SheetKind.COLUMN_APPLICATION:
        kept = [item for item in elements if item.element_type == "column"]
        discarded = len(elements) - len(kept)
        if not discarded:
            return kept, []
        return kept, [
            AnalysisWarning(
                code="COLUMN_APPLICATION_ROLE_FILTERED",
                message=(
                    f"Kolon aplikasyon paftasında kolon dışındaki {discarded} geometri "
                    "fiziksel miktar adaylarına eklenmedi."
                ),
                source_id=source.id,
                severity="info",
            )
        ]
    if source.sheet_kind == SheetKind.REBAR_PLAN:
        kept = [item for item in elements if item.element_type == "rebar"]
        discarded = len(elements) - len(kept)
        return kept, [
            AnalysisWarning(
                code="REBAR_PLAN_ROLE_FILTERED",
                message=(
                    f"Saf donatı planındaki {discarded} betonarme kontur adetlere yeniden "
                    "eklenmedi; yalnız açık donatı çizelgesi/pozları tutuldu."
                ),
                source_id=source.id,
                severity="info",
            )
        ] if discarded else []
    if source.sheet_kind != SheetKind.PLAN:
        return elements, []

    has_column_application = any(
        other.id != source.id
        and other.discipline == source.discipline
        and other.sheet_kind == SheetKind.COLUMN_APPLICATION
        and (other.floor == source.floor or "GENEL" in {other.floor.upper(), source.floor.upper()})
        for other in project_sources
    )
    if not has_column_application:
        return elements, []
    kept = [item for item in elements if item.element_type != "column"]
    discarded = len(elements) - len(kept)
    if not discarded:
        return kept, []
    return kept, [
        AnalysisWarning(
            code="COLUMNS_DEFERRED_TO_APPLICATION_SHEET",
            message=(
                f"Aynı kat için kolon aplikasyon paftası bulunduğundan kalıp planındaki "
                f"{discarded} kolon ikinci kez aday yapılmadı."
            ),
            source_id=source.id,
            severity="info",
        )
    ]


def normalize_repeat_floors(base_floor: str, floors: list[str]) -> list[str]:
    base = base_floor.strip().casefold()
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in floors:
        value = raw_value.strip()
        key = value.casefold()
        if not value or key == base or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def expand_explicit_floor_repeats(
    elements: list[DetectedElement],
    source: SourceFile,
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    """Repeat only physical plan elements for explicitly named target floors."""
    targets = normalize_repeat_floors(source.floor, source.repeat_floors)
    if not targets:
        return elements, []
    if source.floor_kind != FloorKind.TYPICAL or source.sheet_kind != SheetKind.PLAN:
        return elements, [
            AnalysisWarning(
                code="FLOOR_REPEAT_MAPPING_INVALID",
                message=(
                    "Kat tekrarı yalnız 'normal/tip kat' ve 'plan' olarak eşlenen "
                    "paftalarda uygulanabilir; hiçbir eleman çoğaltılmadı."
                ),
                source_id=source.id,
                severity="error",
            )
        ]

    repeatable = [item for item in elements if item.element_type in REPEATABLE_STRUCTURAL_TYPES]
    expanded = list(elements)
    for target_floor in targets:
        for original in repeatable:
            clone = original.model_copy(deep=True)
            identity = f"{original.id}|explicit-floor-repeat|{target_floor.casefold()}"
            clone.id = "elm_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
            clone.floor = target_floor
            clone.properties["explicit_floor_repeat"] = True
            clone.properties["repeated_from_element_id"] = original.id
            clone.properties["repeated_from_floor"] = source.floor
            clone.properties["repeat_mapping_source_id"] = source.id
            clone.review_status = (
                ReviewStatus.NEEDS_REVIEW if clone.missing_inputs() else ReviewStatus.PENDING
            )
            clone.issues = [
                issue
                for issue in clone.issues
                if issue not in {"previous_acceptance_invalid_after_reanalysis"}
            ]
            expanded.append(clone)

    skipped_types = sorted(
        {
            item.element_type
            for item in elements
            if item.element_type not in REPEATABLE_STRUCTURAL_TYPES
        }
    )
    warnings = [
        AnalysisWarning(
            code="EXPLICIT_FLOOR_REPETITION_APPLIED",
            message=(
                f"{len(repeatable)} fiziksel plan elemanı, kullanıcı tarafından tanımlanan "
                f"{len(targets)} kata ({', '.join(targets)}) tekrarlandı."
            ),
            source_id=source.id,
            severity="info",
        )
    ]
    if skipped_types:
        warnings.append(
            AnalysisWarning(
                code="NON_PHYSICAL_ITEMS_NOT_REPEATED",
                message=(
                    "Kat tekrarında çizelge/detay kaynaklı türler çoğaltılmadı: "
                    + ", ".join(skipped_types)
                    + "."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    return expanded, warnings


def expand_approved_repeat_assignments(
    elements: list[DetectedElement],
    source: SourceFile,
    assignments: list[RepeatAssignment],
    floors: list[FloorDefinition],
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    """Apply only approved source/element/template repeat decisions.

    The original source-level repeat field remains a compatibility fallback, but once
    a project has explicit repeat assignments it never participates in expansion.
    """
    relevant = [item for item in assignments if item.source_id == source.id]
    if not relevant:
        return expand_explicit_floor_repeats(elements, source)
    floor_by_id = {floor.id: floor for floor in floors}
    expanded = list(elements)
    warnings: list[AnalysisWarning] = []
    created = 0
    pending = [item for item in relevant if not item.approved]
    for assignment in [item for item in relevant if item.approved]:
        if assignment.scope == RepeatScope.SOURCE:
            selected = [
                item for item in elements if item.element_type in REPEATABLE_STRUCTURAL_TYPES
            ]
        elif assignment.scope == RepeatScope.ELEMENT:
            selected_ids = set(assignment.element_ids)
            selected = [item for item in elements if item.id in selected_ids]
        else:
            label = assignment.template_label.strip().casefold()
            selected = [
                item
                for item in elements
                if str(item.properties.get("element_label", "")).strip().casefold() == label
            ]
        if not selected:
            warnings.append(
                AnalysisWarning(
                    code="REPEAT_ASSIGNMENT_MATCH_EMPTY",
                    message=(
                        f"{assignment.template_label or assignment.id} tekrar kararı hiçbir "
                        "fiziksel elemanla eşleşmedi."
                    ),
                    source_id=source.id,
                    severity="error",
                )
            )
            continue
        for floor_id in assignment.target_floor_ids:
            floor = floor_by_id.get(floor_id)
            if floor is None:
                warnings.append(
                    AnalysisWarning(
                        code="REPEAT_TARGET_FLOOR_MISSING",
                        message=f"Tekrar hedef katı bulunamadı: {floor_id}",
                        source_id=source.id,
                        severity="error",
                    )
                )
                continue
            for original in selected:
                identity = f"{original.id}|repeat-assignment|{assignment.id}|{floor.id}"
                clone = original.model_copy(deep=True)
                clone.id = "elm_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
                clone.floor = floor.name
                clone.properties.update(
                    {
                        "explicit_floor_repeat": True,
                        "repeat_assignment_id": assignment.id,
                        "repeated_from_element_id": original.id,
                        "repeated_from_floor": source.floor,
                        "repeat_target_floor_id": floor.id,
                        "repeat_reviewer": assignment.reviewer,
                        "repeat_reason": assignment.reason,
                    }
                )
                clone.issues = [
                    issue
                    for issue in clone.issues
                    if issue
                    not in {
                        "blocking:stair_floor_repeat_required",
                        "previous_acceptance_invalid_after_reanalysis",
                        "previous_acceptance_blocked_after_reanalysis",
                    }
                ]
                clone.review_status = (
                    ReviewStatus.NEEDS_REVIEW if clone.missing_inputs() else ReviewStatus.PENDING
                )
                expanded.append(clone)
                created += 1
    if created:
        warnings.append(
            AnalysisWarning(
                code="APPROVED_ELEMENT_REPETITION_APPLIED",
                message=(
                    f"Mühendis onaylı {len(relevant) - len(pending)} tekrar kararıyla "
                    f"{created} kat elemanı oluşturuldu."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if pending:
        warnings.append(
            AnalysisWarning(
                code="UNAPPROVED_REPEATS_NOT_APPLIED",
                message=f"Onay bekleyen {len(pending)} tekrar kararı metraja uygulanmadı.",
                source_id=source.id,
                severity="warning",
            )
        )
    return expanded, warnings
