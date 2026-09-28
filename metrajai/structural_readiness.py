from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import DetectedElement, Discipline


@dataclass(frozen=True)
class CompletionBlocker:
    code: str
    message: str
    source_id: str


def structural_completion_blockers(
    elements: Iterable[DetectedElement],
) -> list[CompletionBlocker]:
    """Report missing structural scope without changing approved line quantities.

    Approved concrete/formwork lines remain traceable partial results. A project
    total cannot be described as complete while unit, foundation thickness or
    rebar evidence is unresolved.
    """
    by_source: dict[str, list[DetectedElement]] = defaultdict(list)
    for element in elements:
        if element.discipline == Discipline.STRUCTURAL and not element.properties.get(
            "evidence_only"
        ):
            by_source[element.source_id].append(element)

    blockers: list[CompletionBlocker] = []
    for source_id, source_elements in sorted(by_source.items()):
        if any(
            "blocking:drawing_unit_evidence_mismatch" in item.issues for item in source_elements
        ):
            blockers.append(
                CompletionBlocker(
                    "STRUCTURAL_UNIT_UNRESOLVED",
                    "Statik çizim birimi yazılı ölçü/geometri kanıtıyla çelişiyor.",
                    source_id,
                )
            )
        missing_rafts = [
            item
            for item in source_elements
            if item.element_type == "raft"
            and item.review_status.value != "rejected"
            and item.measurements.get("thickness_m", 0) <= 0
        ]
        if missing_rafts:
            blockers.append(
                CompletionBlocker(
                    "RAFT_THICKNESS_REQUIRED",
                    f"{len(missing_rafts)} radye temelde kalınlık kanıtı eksik.",
                    source_id,
                )
            )
    all_structural = [item for group in by_source.values() for item in group]
    rebars = [item for item in all_structural if item.element_type == "rebar"]
    if all_structural and not rebars:
        blockers.append(
            CompletionBlocker(
                "REBAR_SOURCE_REQUIRED",
                "Statik donatı detayı veya çizelgesi bulunmadı.",
                sorted(by_source)[0],
            )
        )
    elif (
        rebars
        and any(len(item.properties.get("revision_candidates", [])) > 1 for item in rebars)
        and not any(item.properties.get("revision_selected") is True for item in rebars)
    ):
        blockers.append(
            CompletionBlocker(
                "REBAR_REVISION_REQUIRED",
                "Birden fazla donatı revizyonu var; güncel çizelge seçilmedi.",
                next(
                    item.source_id
                    for item in rebars
                    if len(item.properties.get("revision_candidates", [])) > 1
                ),
            )
        )
    return blockers
