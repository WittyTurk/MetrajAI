from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal

from .commercial import calculate_offer
from .structural_readiness import structural_completion_blockers
from .workspace import ProjectWorkspace


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def build_report_payload(workspace: ProjectWorkspace) -> dict:
    sources = workspace.list_sources()
    elements = workspace.list_elements()
    completion_blockers = structural_completion_blockers(elements)
    quantities = workspace.list_quantities()
    assumptions = workspace.list_assumptions()
    warnings = workspace.list_warnings()
    price_items = workspace.list_price_items()
    price_mappings = workspace.list_price_mappings()
    offer_scenarios = workspace.list_offer_scenarios()
    offers: list[dict] = []
    for scenario in offer_scenarios:
        lines, offer_totals = calculate_offer(
            scenario,
            quantities,
            price_mappings,
            price_items,
        )
        offers.append(
            {
                "scenario": scenario.model_dump(mode="json"),
                "cost_lines": [item.model_dump(mode="json") for item in lines],
                "totals": _json_value(offer_totals),
            }
        )
    totals: dict[tuple[str, str, str], float] = defaultdict(float)
    for line in quantities:
        totals[(line.discipline.value, line.category, line.unit)] += line.quantity
    return {
        "schema_version": 3,
        "project": workspace.manifest.model_dump(mode="json"),
        "summary": [
            {
                "discipline": discipline,
                "category": category,
                "unit": unit,
                "quantity": quantity,
                "status": "partial"
                if discipline == "structural" and completion_blockers
                else "approved",
            }
            for (discipline, category, unit), quantity in sorted(totals.items())
        ],
        "sources": [item.model_dump(mode="json") for item in sources],
        "elements": [item.model_dump(mode="json") for item in elements],
        "quantities": [item.model_dump(mode="json") for item in quantities],
        "assumptions": [item.model_dump(mode="json") for item in assumptions],
        "warnings": [item.model_dump(mode="json") for item in warnings],
        "completion": {
            "structural_complete": not completion_blockers,
            "blockers": [asdict(item) for item in completion_blockers],
        },
        "review_history": [item.model_dump(mode="json") for item in workspace.list_reviews()],
        "floors": [item.model_dump(mode="json") for item in workspace.list_floors()],
        "sheet_assignments": [
            item.model_dump(mode="json") for item in workspace.list_sheet_assignments()
        ],
        "repeat_assignments": [
            item.model_dump(mode="json") for item in workspace.list_repeat_assignments()
        ],
        "architectural_assignments": [
            item.model_dump(mode="json") for item in workspace.list_architectural_assignments()
        ],
        "element_evidence": [
            item.model_dump(mode="json") for item in workspace.list_element_evidence()
        ],
        "manual_overrides": [
            item.model_dump(mode="json") for item in workspace.list_manual_overrides()
        ],
        "price_catalogs": [
            item.model_dump(mode="json") for item in workspace.list_price_catalogs()
        ],
        "price_items": [item.model_dump(mode="json") for item in price_items],
        "price_mappings": [item.model_dump(mode="json") for item in price_mappings],
        "offers": offers,
        "validation_gates": [
            item.model_dump(mode="json") for item in workspace.list_validation_gates()
        ],
    }
