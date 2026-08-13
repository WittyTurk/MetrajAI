from __future__ import annotations

from collections import defaultdict

from .workspace import ProjectWorkspace


def build_report_payload(workspace: ProjectWorkspace) -> dict:
    sources = workspace.list_sources()
    elements = workspace.list_elements()
    quantities = workspace.list_quantities()
    assumptions = workspace.list_assumptions()
    warnings = workspace.list_warnings()
    totals: dict[tuple[str, str, str], float] = defaultdict(float)
    for line in quantities:
        totals[(line.discipline.value, line.category, line.unit)] += line.quantity
    return {
        "schema_version": 1,
        "project": workspace.manifest.model_dump(mode="json"),
        "summary": [
            {
                "discipline": discipline,
                "category": category,
                "unit": unit,
                "quantity": quantity,
            }
            for (discipline, category, unit), quantity in sorted(totals.items())
        ],
        "sources": [item.model_dump(mode="json") for item in sources],
        "elements": [item.model_dump(mode="json") for item in elements],
        "quantities": [item.model_dump(mode="json") for item in quantities],
        "assumptions": [item.model_dump(mode="json") for item in assumptions],
        "warnings": [item.model_dump(mode="json") for item in warnings],
        "review_history": [item.model_dump(mode="json") for item in workspace.list_reviews()],
    }
