from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import urllib.error
import urllib.request
import warnings
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.path import make_path

from .analyzers.dxf import DxfAnalyzer
from .analyzers.reference_dxf import REFERENCE_APPID
from .contracts import Discipline, DrawingUnit, ReviewStatus, SourceFile, SourceFormat

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "reference" / "manifest.json"

IFC_CLASS_MAP: dict[str, dict[str, str]] = {
    "architectural": {
        "IfcSpace": "room",
        "IfcWall": "wall",
        "IfcWallStandardCase": "wall",
        "IfcDoor": "door",
        "IfcWindow": "window",
        "IfcSlab": "slab",
        "IfcStair": "stair",
        "IfcStairFlight": "stair",
    },
    "structural": {
        "IfcColumn": "column",
        "IfcBeam": "beam",
        "IfcWall": "shear_wall",
        "IfcWallStandardCase": "shear_wall",
        "IfcSlab": "slab",
        "IfcFooting": "foundation",
    },
}

LAYER_MAP: dict[tuple[str, str], str] = {
    ("architectural", "room"): "A-ROOM",
    ("architectural", "wall"): "A-WALL",
    ("architectural", "door"): "A-DOOR",
    ("architectural", "window"): "A-WINDOW",
    ("architectural", "slab"): "A-SLAB",
    ("architectural", "stair"): "A-STAIR",
    ("structural", "column"): "S-COLUMN",
    ("structural", "beam"): "S-BEAM",
    ("structural", "shear_wall"): "S-WALL",
    ("structural", "slab"): "S-SLAB",
    ("structural", "foundation"): "S-FOOTING",
}

METRIC_FIELDS = (
    "count",
    "length_m",
    "width_m",
    "depth_m",
    "height_m",
    "thickness_m",
    "area_m2",
    "perimeter_m",
    "plan_area_m2",
    "horizontal_run_m",
    "total_rise_m",
    "waist_thickness_m",
    "volume_m3",
)


class ReferenceLabError(RuntimeError):
    """A blocking reference-data validation or reproducibility error."""


def _json_load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReferenceLabError(f"Manifest okunamadı: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReferenceLabError("Referans manifestinin kökü bir JSON nesnesi olmalıdır.")
    return value


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest_path = Path(path).resolve()
    manifest = _json_load(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ReferenceLabError("Desteklenmeyen referans manifesti sürümü.")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ReferenceLabError("Manifest en az bir referans veri seti içermelidir.")
    ids: set[str] = set()
    for dataset in datasets:
        required = ("id", "name", "source_page", "commit", "license", "attribution", "sources")
        missing = [key for key in required if not dataset.get(key)]
        if missing:
            raise ReferenceLabError(
                f"{dataset.get('id', '<isimsiz>')} manifest alanları eksik: {', '.join(missing)}"
            )
        if dataset["id"] in ids:
            raise ReferenceLabError(f"Tekrarlanan veri seti kimliği: {dataset['id']}")
        ids.add(dataset["id"])
        if dataset["license"] != "CC-BY-4.0":
            raise ReferenceLabError(f"{dataset['id']} için beklenen lisans CC-BY-4.0.")
        if len(str(dataset["commit"])) != 40:
            raise ReferenceLabError(f"{dataset['id']} commit değeri sabitlenmemiş.")
        for source in dataset["sources"]:
            for key in ("id", "discipline", "filename", "url", "sha256", "size_bytes"):
                if not source.get(key):
                    raise ReferenceLabError(f"{dataset['id']} kaynağında {key} eksik.")
            if len(str(source["sha256"])) != 64:
                raise ReferenceLabError(f"{source['id']} SHA-256 değeri geçersiz.")
            if str(dataset["commit"]) not in str(source["url"]):
                raise ReferenceLabError(f"{source['id']} URL'si sabit commiti içermiyor.")
    manifest["_path"] = str(manifest_path)
    return manifest


def select_datasets(manifest: dict[str, Any], selected: str) -> list[dict[str, Any]]:
    datasets = list(manifest["datasets"])
    if selected == "all":
        return datasets
    matches = [dataset for dataset in datasets if dataset["id"] == selected]
    if not matches:
        raise ReferenceLabError(f"Bilinmeyen referans veri seti: {selected}")
    return matches


def cache_root(manifest: dict[str, Any], override: str | Path | None = None) -> Path:
    if override is not None:
        return Path(override).resolve()
    manifest_path = Path(manifest["_path"])
    return (manifest_path.parent.parent / str(manifest["cache_directory"])).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified(path: Path, source: dict[str, Any]) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == int(source["size_bytes"])
        and sha256_file(path) == source["sha256"]
    )


def fetch_source(source: dict[str, Any], destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if _verified(destination, source):
        return destination
    if destination.exists():
        raise ReferenceLabError(
            f"Yerel referans kopyasının SHA-256 değeri uyuşmuyor: {destination}"
        )
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        request = urllib.request.Request(
            str(source["url"]),
            headers={"User-Agent": "MetrajAI-reference-lab/1.2"},
        )
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output, length=1024 * 1024)
    except (OSError, urllib.error.URLError) as exc:
        temporary.unlink(missing_ok=True)
        if _verified(destination, source):
            return destination
        raise ReferenceLabError(f"{source['id']} indirilemedi: {exc}") from exc
    if not _verified(temporary, source):
        actual = sha256_file(temporary) if temporary.exists() else "eksik"
        temporary.unlink(missing_ok=True)
        raise ReferenceLabError(
            f"{source['id']} SHA-256 uyuşmazlığı: beklenen {source['sha256']}, alınan {actual}"
        )
    os.replace(temporary, destination)
    return destination


def fetch_references(
    manifest: dict[str, Any],
    *,
    selected: str = "all",
    data_root: str | Path | None = None,
) -> list[Path]:
    root = cache_root(manifest, data_root)
    paths: list[Path] = []
    for dataset in select_datasets(manifest, selected):
        for source in dataset["sources"]:
            target = root / "source" / dataset["id"] / source["filename"]
            paths.append(fetch_source(source, target))
    return paths


def _require_ifc_dependencies():
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import ifcopenshell.util.element
        import ifcopenshell.util.shape
        import ifcopenshell.util.unit
        import ifcopenshell.validate
        from shapely.geometry import Polygon as _Polygon
    except ImportError as exc:
        raise ReferenceLabError(
            "IFC laboratuvarı için isteğe bağlı bağımlılıkları kurun: "
            "pip install -e '.[reference]'"
        ) from exc
    _ = _Polygon
    return ifcopenshell


def inspect_ifc_validation(path: Path) -> tuple[Any | None, dict[str, Any]]:
    ifcopenshell = _require_ifc_dependencies()

    try:
        model = ifcopenshell.open(path)
    except Exception as exc:
        return None, {
            "filename": path.name,
            "schema": "",
            "passed": False,
            "error_count": 1,
            "errors": [f"IFC açılamadı: {type(exc).__name__}: {exc}"],
        }
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger, express_rules=True)
    statements = list(logger.statements)
    return model, {
        "filename": path.name,
        "schema": str(model.schema),
        "passed": not statements,
        "error_count": len(statements),
        "errors": [str(item.get("message", item)) for item in statements[:20]],
        "errors_truncated": max(0, len(statements) - 20),
    }


def validate_ifc(path: Path):
    model, report = inspect_ifc_validation(path)
    statements = report["errors"]
    if model is None:
        raise ReferenceLabError(statements[0])
    if statements:
        sample = "; ".join(statements[:3])
        raise ReferenceLabError(
            f"{path.name} IFC şema/EXPRESS doğrulamasını geçemedi "
            f"({report['error_count']} hata): {sample}"
        )
    return model


def _unit_multiplier(symbol: str, dimension: int, project_scale: float) -> float:
    normalized = symbol.lower().replace("²", "2").replace("³", "3").replace(" ", "")
    prefixes = {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0}
    for prefix, multiplier in prefixes.items():
        if normalized in {prefix, f"{prefix}{dimension}"}:
            return multiplier**dimension
    return project_scale**dimension


def _quantity_dimension(quantity) -> int:
    if quantity.is_a("IfcQuantityLength"):
        return 1
    if quantity.is_a("IfcQuantityArea"):
        return 2
    if quantity.is_a("IfcQuantityVolume"):
        return 3
    return 0


def _quantity_value(quantity) -> float | None:
    for key in ("LengthValue", "AreaValue", "VolumeValue", "CountValue", "WeightValue"):
        value = getattr(quantity, key, None)
        if value is not None:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            return number if math.isfinite(number) else None
    return None


def _explicit_quantities(model, element) -> list[dict[str, Any]]:
    import ifcopenshell.util.unit

    project_scale = float(ifcopenshell.util.unit.calculate_unit_scale(model, "LENGTHUNIT"))
    result: list[dict[str, Any]] = []
    for relation in getattr(element, "IsDefinedBy", ()):
        if not relation.is_a("IfcRelDefinesByProperties"):
            continue
        definition = relation.RelatingPropertyDefinition
        if not definition or not definition.is_a("IfcElementQuantity"):
            continue
        for quantity in definition.Quantities:
            value = _quantity_value(quantity)
            dimension = _quantity_dimension(quantity)
            if value is None or dimension == 0:
                continue
            unit = ifcopenshell.util.unit.get_property_unit(quantity, model)
            symbol = ifcopenshell.util.unit.get_unit_symbol(unit) if unit is not None else ""
            si_value = value * _unit_multiplier(symbol, dimension, project_scale)
            result.append(
                {
                    "set": str(definition.Name or ""),
                    "name": str(quantity.Name or ""),
                    "ifc_class": quantity.is_a(),
                    "raw_value": value,
                    "unit": symbol,
                    "si_value": si_value,
                    "si_unit": {1: "m", 2: "m2", 3: "m3"}[dimension],
                }
            )
    return result


def _choose_explicit(quantities: list[dict[str, Any]], dimension: int) -> dict[str, Any] | None:
    wanted_unit = {1: "m", 2: "m2", 3: "m3"}[dimension]
    candidates = [item for item in quantities if item["si_unit"] == wanted_unit]
    priorities = {
        1: ("Length", "Height", "Width", "Thickness", "Perimeter"),
        2: ("NetFloorArea", "NetArea", "Area", "GrossFloorArea", "GrossArea"),
        3: ("NetVolume", "Volume", "GrossVolume"),
    }[dimension]
    for name in priorities:
        for candidate in candidates:
            if str(candidate["name"]).casefold() == name.casefold():
                return candidate
    return candidates[0] if candidates else None


def _footprint_from_shape(shape) -> tuple[Any, dict[str, float]]:
    import ifcopenshell.util.shape
    import shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
    faces = ifcopenshell.util.shape.get_faces(shape.geometry)
    triangles = []
    z_values: list[float] = []
    for face in faces:
        points = [vertices[int(index)] for index in face]
        z_values.extend(float(point[2]) for point in points)
        polygon = Polygon([(float(point[0]), float(point[1])) for point in points])
        if polygon.is_valid and polygon.area > 1e-12:
            triangles.append(polygon)
    if not triangles:
        raise ReferenceLabError("IFC üçgenlerinden yatay izdüşüm üretilemedi.")
    footprint = shapely.set_precision(unary_union(triangles), 1e-9).buffer(0)
    if footprint.is_empty:
        raise ReferenceLabError("IFC yatay izdüşümü boş.")
    volume = abs(float(ifcopenshell.util.shape.get_volume(shape.geometry)))
    metrics = {
        "area_m2": float(footprint.area),
        "perimeter_m": float(footprint.length),
        "height_m": max(z_values) - min(z_values) if z_values else 0.0,
        "volume_m3": volume,
        "min_z_m": min(z_values) if z_values else 0.0,
        "max_z_m": max(z_values) if z_values else 0.0,
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        rectangle = footprint.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords)
    edges = [
        math.dist(coords[index], coords[index + 1])
        for index in range(min(4, len(coords) - 1))
    ]
    positive = [edge for edge in edges if edge > 1e-9]
    if positive:
        metrics["major_m"] = max(positive)
        metrics["minor_m"] = min(positive)
    return footprint, metrics


def _polygon_payload(geometry) -> list[dict[str, Any]]:
    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    payload: list[dict[str, Any]] = []
    for polygon in sorted(polygons, key=lambda item: (-item.area, item.bounds)):
        payload.append(
            {
                "exterior": [
                    [round(float(x), 9), round(float(y), 9)]
                    for x, y in polygon.exterior.coords
                ],
                "holes": [
                    [[round(float(x), 9), round(float(y), 9)] for x, y in ring.coords]
                    for ring in polygon.interiors
                ],
            }
        )
    return payload


def _element_storey(element) -> tuple[str, str]:
    import ifcopenshell.util.element

    container = ifcopenshell.util.element.get_container(
        element,
        ifc_class="IfcBuildingStorey",
    )
    if container is None:
        return "UNASSIGNED", ""
    return str(container.Name or container.LongName or "UNASSIGNED"), str(container.GlobalId or "")


def _element_relationships(element) -> dict[str, list[str]]:
    hosts: set[str] = set()
    spaces: set[str] = set()
    openings: set[str] = set()
    for relation in getattr(element, "FillsVoids", ()):
        opening = relation.RelatingOpeningElement
        openings.add(str(opening.GlobalId))
        for void_relation in getattr(opening, "VoidsElements", ()):
            hosts.add(str(void_relation.RelatingBuildingElement.GlobalId))
    for relation in getattr(element, "HasOpenings", ()):
        opening = relation.RelatedOpeningElement
        openings.add(str(opening.GlobalId))
    for relation in getattr(element, "BoundedBy", ()):
        related = getattr(relation, "RelatedBuildingElement", None)
        if related is not None:
            hosts.add(str(related.GlobalId))
    for relation in getattr(element, "ProvidesBoundaries", ()):
        space = getattr(relation, "RelatingSpace", None)
        if space is not None:
            spaces.add(str(space.GlobalId))
    return {
        "hosts": sorted(hosts),
        "spaces": sorted(spaces),
        "openings": sorted(openings),
    }


def _measurements(element_type: str, geometry: dict[str, float]) -> dict[str, float]:
    major = geometry.get("major_m", 0.0)
    minor = geometry.get("minor_m", 0.0)
    area = geometry.get("area_m2", 0.0)
    height = geometry.get("height_m", 0.0)
    volume = geometry.get("volume_m3", 0.0)
    values: dict[str, float]
    if element_type == "room":
        values = {"area_m2": area, "perimeter_m": geometry.get("perimeter_m", 0.0)}
    elif element_type == "wall":
        values = {"length_m": major, "height_m": height, "volume_m3": volume}
    elif element_type in {"door", "window"}:
        values = {"count": 1.0, "width_m": major, "height_m": height}
    elif element_type == "column":
        values = {"width_m": major, "depth_m": minor, "height_m": height, "volume_m3": volume}
    elif element_type == "beam":
        values = {"length_m": major, "width_m": minor, "height_m": height, "volume_m3": volume}
    elif element_type == "shear_wall":
        values = {
            "length_m": major,
            "thickness_m": minor,
            "height_m": height,
            "volume_m3": volume,
        }
    elif element_type in {"slab", "foundation"}:
        thickness = volume / area if area > 0 and volume > 0 else height
        values = {
            "area_m2": area,
            "perimeter_m": geometry.get("perimeter_m", 0.0),
            "thickness_m": thickness,
            "volume_m3": volume,
        }
    elif element_type == "stair":
        values = {
            "plan_area_m2": area,
            "horizontal_run_m": major,
            "total_rise_m": height,
            "volume_m3": volume,
        }
    else:
        values = {}
    return {key: float(value) for key, value in values.items() if value > 1e-9}


def extract_ifc_golden(
    model,
    dataset: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    import ifcopenshell.geom

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    class_map = IFC_CLASS_MAP[source["discipline"]]
    candidates: dict[str, Any] = {}
    for ifc_class in class_map:
        for element in model.by_type(ifc_class):
            guid = str(getattr(element, "GlobalId", "") or "")
            if guid:
                candidates[guid] = element
    records: list[dict[str, Any]] = []
    for guid, element in sorted(candidates.items()):
        element_type = class_map.get(element.is_a())
        if not element_type:
            continue
        record: dict[str, Any] = {
            "global_id": guid,
            "ifc_class": element.is_a(),
            "name": str(getattr(element, "Name", "") or ""),
            "type": element_type,
            "discipline": source["discipline"],
            "source_id": source["id"],
            "storey": "UNASSIGNED",
            "storey_guid": "",
            "unit": "SI",
            "relationships": _element_relationships(element),
            "explicit_quantities": _explicit_quantities(model, element),
            "reference_status": "supported",
            "reference_reason": "",
            "geometry": [],
            "geometry_metrics": {},
            "measurements": {},
        }
        record["storey"], record["storey_guid"] = _element_storey(element)
        try:
            shape = ifcopenshell.geom.create_shape(settings, element)
            footprint, geometry_metrics = _footprint_from_shape(shape)
            record["geometry"] = _polygon_payload(footprint)
            record["geometry_metrics"] = {
                key: round(float(value), 9) for key, value in sorted(geometry_metrics.items())
            }
            record["measurements"] = {
                key: round(value, 9)
                for key, value in sorted(_measurements(element_type, geometry_metrics).items())
            }
        except Exception as exc:
            record["reference_status"] = "reference_only"
            record["reference_reason"] = f"geometry_unavailable:{type(exc).__name__}"
        if element_type == "stair":
            record["reference_status"] = "reference_only"
            record["reference_reason"] = "stair_requires_flight_and_landing_decomposition"
        for dimension, key in ((1, "length"), (2, "area"), (3, "volume")):
            quantity = _choose_explicit(record["explicit_quantities"], dimension)
            if quantity:
                record[f"preferred_{key}"] = {
                    "value": round(float(quantity["si_value"]), 9),
                    "unit": quantity["si_unit"],
                    "source": "ifc_quantity",
                    "name": quantity["name"],
                }
            else:
                geometry_key = {1: "major_m", 2: "area_m2", 3: "volume_m3"}[dimension]
                if geometry_key in record["geometry_metrics"]:
                    record[f"preferred_{key}"] = {
                        "value": record["geometry_metrics"][geometry_key],
                        "unit": {1: "m", 2: "m2", 3: "m3"}[dimension],
                        "source": "geometry",
                    }
        comparisons: list[dict[str, Any]] = []
        for key, geometry_key in (
            ("length", "major_m"),
            ("area", "area_m2"),
            ("volume", "volume_m3"),
        ):
            preferred = record.get(f"preferred_{key}")
            geometry_value = record["geometry_metrics"].get(geometry_key)
            if preferred and preferred["source"] == "ifc_quantity" and geometry_value is not None:
                denominator = max(abs(float(preferred["value"])), 1e-9)
                comparisons.append(
                    {
                        "kind": key,
                        "explicit_value": preferred["value"],
                        "geometry_value": geometry_value,
                        "unit": preferred["unit"],
                        "difference_ratio": round(
                            abs(float(preferred["value"]) - float(geometry_value)) / denominator,
                            9,
                        ),
                    }
                )
        record["quantity_comparisons"] = comparisons
        records.append(record)
    return {
        "schema_version": 1,
        "dataset_id": dataset["id"],
        "dataset_name": dataset["name"],
        "source_id": source["id"],
        "discipline": source["discipline"],
        "source_sha256": source["sha256"],
        "source_commit": dataset["commit"],
        "license": dataset["license"],
        "attribution": dataset["attribution"],
        "elements": records,
    }


def _safe_name(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "unassigned"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")


def _xdata(
    record: dict[str, Any],
    dataset: dict[str, Any],
    source: dict[str, Any],
) -> list[tuple[int, str]]:
    metadata = {
        "guid": record["global_id"],
        "type": record["type"],
        "discipline": record["discipline"],
        "dataset": dataset["id"],
        "source": source["id"],
        "storey": record["storey"],
        "ifc_class": record["ifc_class"],
        "name": record["name"][:80],
        "dxf_unit": "mm",
    }
    metadata.update({key: f"{value:.9f}" for key, value in record["measurements"].items()})
    return [(1000, f"{key}={value}") for key, value in metadata.items()]


def _add_element_block(
    document,
    modelspace,
    record: dict[str, Any],
    dataset: dict[str, Any],
    source: dict[str, Any],
    origin: tuple[float, float],
    index: int,
    *,
    hard: bool,
):
    layer = LAYER_MAP[(source["discipline"], record["type"])]
    polygons = record["geometry"]
    all_points = [point for polygon in polygons for point in polygon["exterior"]]
    center_x = sum(point[0] for point in all_points) / len(all_points)
    center_y = sum(point[1] for point in all_points) / len(all_points)
    block_name = f"REF_{hashlib.sha1(record['global_id'].encode()).hexdigest()[:12].upper()}"
    block = document.blocks.new(name=block_name)
    for polygon in polygons:
        exterior = [
            ((point[0] - center_x) * 1000.0, (point[1] - center_y) * 1000.0)
            for point in polygon["exterior"][:-1]
        ]
        if len(exterior) >= 3:
            block.add_lwpolyline(exterior, close=True, dxfattribs={"layer": "0"})
        for hole in polygon["holes"]:
            ring = [
                ((point[0] - center_x) * 1000.0, (point[1] - center_y) * 1000.0)
                for point in hole[:-1]
            ]
            if len(ring) >= 3:
                block.add_lwpolyline(ring, close=True, dxfattribs={"layer": "0"})
    insert_at = ((center_x - origin[0]) * 1000.0, (center_y - origin[1]) * 1000.0)
    rotation = float((index % 4) * 90) if hard else 0.0
    xscale = -1.0 if hard and index % 3 == 1 else 1.0
    inserted_block_name = block_name
    if hard:
        wrapper_name = f"NESTED_{block_name}"
        wrapper = document.blocks.new(name=wrapper_name)
        wrapper.add_blockref(block_name, (0, 0), dxfattribs={"layer": "0"})
        inserted_block_name = wrapper_name
    entity = modelspace.add_blockref(
        inserted_block_name,
        insert_at,
        dxfattribs={"layer": layer, "rotation": rotation, "xscale": xscale},
    )
    entity.set_xdata(REFERENCE_APPID, _xdata(record, dataset, source))
    entity.add_attrib(
        "IFC_GUID",
        record["global_id"],
        insert=insert_at,
        dxfattribs={"layer": layer},
    )
    return entity


def _dxf_filename(source: dict[str, Any], storey: str, variant: str) -> str:
    return f"{source['id']}__{_safe_name(storey)}__{variant}.dxf"


def _write_dxf(
    records: list[dict[str, Any]],
    output: Path,
    dataset: dict[str, Any],
    source: dict[str, Any],
    *,
    variant: str,
    sheet_name: str,
) -> dict[str, Any]:
    fixed_metadata = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    document = ezdxf.new("R2018", setup=True)
    document.header["$INSUNITS"] = {
        "hard_unitless": 0,
        "hard_wrong_unit": 5,
    }.get(variant, 4)
    if REFERENCE_APPID not in document.appids:
        document.appids.add(REFERENCE_APPID)
    for layer in sorted(set(LAYER_MAP.values()) | {"REF-NOISE", "REF-DETAIL"}):
        if layer not in document.layers:
            document.layers.add(layer)
    modelspace = document.modelspace()
    bounds = [
        point
        for record in records
        for polygon in record["geometry"]
        for point in polygon["exterior"]
    ]
    origin = (
        min(point[0] for point in bounds) if bounds else 0.0,
        min(point[1] for point in bounds) if bounds else 0.0,
    )
    entities = [
        _add_element_block(
            document,
            modelspace,
            record,
            dataset,
            source,
            origin,
            index,
            hard=variant == "hard_geometry",
        )
        for index, record in enumerate(records)
    ]
    mutations: list[dict[str, str]] = []
    if variant == "hard_geometry":
        for entity in entities:
            duplicate = entity.copy()
            duplicate.dxf.insert = (entity.dxf.insert.x + 100000.0, entity.dxf.insert.y + 100000.0)
            modelspace.add_entity(duplicate)
        modelspace.add_lwpolyline(
            [(0, -20000), (12000, -20000), (12000, -12000)],
            dxfattribs={"layer": "REF-DETAIL"},
        )
        modelspace.add_lwpolyline(
            [(15000, -20000, 0.5), (18000, -20000, 0.0)],
            format="xyb",
            dxfattribs={"layer": "REF-DETAIL"},
        )
        hatch = modelspace.add_hatch(dxfattribs={"layer": "REF-DETAIL"})
        hatch.paths.add_polyline_path(
            [(20000, -20000), (24000, -20000), (24000, -16000), (20000, -16000)],
            is_closed=True,
            flags=1,
        )
        hatch.paths.add_polyline_path(
            [(21500, -18500), (22500, -18500), (22500, -17500), (21500, -17500)],
            is_closed=True,
            flags=0,
        )
        modelspace.add_circle(
            (10_000_000, 10_000_000),
            radius=250,
            dxfattribs={"layer": "REF-NOISE"},
        )
        modelspace.add_text(
            "KESIT / GORUNUS / ACIKLAMA",
            dxfattribs={"layer": "REF-DETAIL", "height": 250},
        ).set_placement((0, -22000))
        mutations.extend(
            [
                {"id": "rotated_mirrored_blocks", "expected": "quantity_unchanged"},
                {"id": "duplicate_plan", "expected": "deduplicated_by_global_id"},
                {"id": "detail_region", "expected": "excluded_without_reference_xdata"},
                {"id": "open_polyline", "expected": "excluded_without_reference_xdata"},
                {"id": "bulge_arc", "expected": "excluded_without_reference_xdata"},
                {"id": "hatch_with_hole", "expected": "excluded_without_reference_xdata"},
                {"id": "far_annotation", "expected": "excluded_without_reference_xdata"},
            ]
        )
    elif variant == "hard_unitless":
        mutations.append({"id": "missing_insunits", "expected": "needs_review"})
    elif variant == "hard_wrong_unit":
        mutations.append({"id": "wrong_insunits_cm", "expected": "needs_review"})
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        document.saveas(output)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = fixed_metadata
    return {
        "path": str(output),
        "filename": output.name,
        "sha256": sha256_file(output),
        "variant": variant,
        "source_id": source["id"],
        "discipline": source["discipline"],
        "storey": sheet_name,
        "reference_guids": sorted(record["global_id"] for record in records),
        "expected": (
            "needs_review"
            if variant in {"hard_unitless", "hard_wrong_unit"}
            else "quantities"
        ),
        "mutations": mutations,
    }


def _write_totals_csv(path: Path, golden_sources: Sequence[dict[str, Any]]) -> None:
    rows: dict[tuple[str, str, str, str], dict[str, float]] = {}
    for golden in golden_sources:
        for record in golden["elements"]:
            if record["reference_status"] != "supported":
                continue
            key = (
                golden["dataset_id"],
                golden["source_id"],
                record["storey"],
                record["type"],
            )
            row = rows.setdefault(key, {field: 0.0 for field in METRIC_FIELDS})
            row["count"] += 1.0
            for field, value in record["measurements"].items():
                if field != "count":
                    row[field] += float(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = ["dataset_id", "source_id", "storey", "type", *METRIC_FIELDS]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for key, metrics in sorted(rows.items()):
            writer.writerow(
                {
                    "dataset_id": key[0],
                    "source_id": key[1],
                    "storey": key[2],
                    "type": key[3],
                    **{field: f"{metrics[field]:.9f}" for field in METRIC_FIELDS},
                }
            )


def build_references(
    manifest: dict[str, Any],
    *,
    selected: str = "all",
    data_root: str | Path | None = None,
) -> list[Path]:
    root = cache_root(manifest, data_root)
    outputs: list[Path] = []
    for dataset in select_datasets(manifest, selected):
        golden_sources: list[dict[str, Any]] = []
        dxf_files: list[dict[str, Any]] = []
        validated_models: dict[str, Any] = {}
        validation_sources: list[dict[str, Any]] = []
        for source in dataset["sources"]:
            source_path = root / "source" / dataset["id"] / source["filename"]
            if not _verified(source_path, source):
                raise ReferenceLabError(
                    f"{source['id']} yerel ve doğrulanmış değil; önce fetch çalıştırın."
                )
            model, validation = inspect_ifc_validation(source_path)
            validation["source_id"] = source["id"]
            validation["sha256"] = source["sha256"]
            validation_sources.append(validation)
            if model is not None:
                validated_models[source["id"]] = model
        validation_report = {
            "schema_version": 1,
            "dataset_id": dataset["id"],
            "passed": all(item["passed"] for item in validation_sources),
            "express_rules": True,
            "sources": validation_sources,
        }
        validation_path = root / "generated" / dataset["id"] / "ifc-validation.json"
        _write_json(validation_path, validation_report)
        outputs.append(validation_path)
        if not validation_report["passed"]:
            summary = ", ".join(
                f"{item['source_id']}={item['error_count']} hata"
                for item in validation_sources
                if not item["passed"]
            )
            raise ReferenceLabError(
                f"{dataset['id']} IFC şema/EXPRESS kapısı geçilemedi ({summary}); "
                f"rapor: {validation_path}"
            )
        for source in dataset["sources"]:
            source_path = root / "source" / dataset["id"] / source["filename"]
            model = validated_models[source["id"]]
            golden = extract_ifc_golden(model, dataset, source)
            golden_path = root / "generated" / dataset["id"] / "golden" / f"{source['id']}.json"
            _write_json(golden_path, golden)
            outputs.append(golden_path)
            golden_sources.append(golden)
            grouped: dict[str, list[dict[str, Any]]] = {}
            for record in golden["elements"]:
                if record["reference_reason"].startswith("geometry_unavailable"):
                    raise ReferenceLabError(
                        f"{source['id']} zorunlu {record['ifc_class']} geometrisi "
                        f"üretilemedi: {record['global_id']}"
                    )
                if record["reference_status"] == "supported" and record["geometry"]:
                    sheet_name = (
                        "FOUNDATION" if record["type"] == "foundation" else record["storey"]
                    )
                    grouped.setdefault(sheet_name, []).append(record)
            for sheet_name, records in sorted(grouped.items()):
                for variant in (
                    "clean",
                    "hard_geometry",
                    "hard_unitless",
                    "hard_wrong_unit",
                ):
                    output = (
                        root
                        / "generated"
                        / dataset["id"]
                        / "dxf"
                        / _dxf_filename(source, sheet_name, variant)
                    )
                    dxf_files.append(
                        _write_dxf(
                            records,
                            output,
                            dataset,
                            source,
                            variant=variant,
                            sheet_name=sheet_name,
                        )
                    )
                    outputs.append(output)
        totals = root / "generated" / dataset["id"] / "golden" / "totals.csv"
        _write_totals_csv(totals, golden_sources)
        outputs.append(totals)
        generated_manifest = {
            "schema_version": 1,
            "dataset_id": dataset["id"],
            "source_commit": dataset["commit"],
            "license": dataset["license"],
            "attribution": dataset["attribution"],
            "files": sorted(dxf_files, key=lambda item: item["filename"]),
        }
        generated_path = root / "generated" / dataset["id"] / "generated-manifest.json"
        _write_json(generated_path, generated_manifest)
        outputs.append(generated_path)
    return outputs


def _source_for_dxf(file_record: dict[str, Any], path: Path) -> SourceFile:
    discipline = Discipline(file_record["discipline"])
    needs_unit_review = file_record["variant"] in {"hard_unitless", "hard_wrong_unit"}
    return SourceFile(
        id=f"ref_{hashlib.sha256(path.name.encode()).hexdigest()[:20]}",
        project_id=f"reference_{file_record['source_id']}",
        original_name=path.name,
        stored_path=str(path),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.DXF,
        discipline=discipline,
        role="reference_validation",
        floor=file_record["storey"],
        drawing_unit=DrawingUnit.UNKNOWN if needs_unit_review else DrawingUnit.MM,
        detected_unit=DrawingUnit.UNKNOWN if needs_unit_review else DrawingUnit.MM,
        unit_confirmed=not needs_unit_review,
    )


def _reference_metadata(entity) -> dict[str, str]:
    try:
        tags = entity.get_xdata(REFERENCE_APPID)
    except Exception:
        return {}
    values: dict[str, str] = {}
    for tag in tags:
        if tag.code != 1000:
            continue
        key, separator, value = str(tag.value).partition("=")
        if separator:
            values[key] = value
    return values


def _virtual_polylines(entities: Iterable[Any], depth: int = 0) -> list[list[tuple[float, float]]]:
    if depth > 8:
        return []
    rings: list[list[tuple[float, float]]] = []
    for entity in entities:
        if entity.dxftype() == "INSERT":
            try:
                rings.extend(_virtual_polylines(entity.virtual_entities(), depth + 1))
            except Exception:
                continue
        elif entity.dxftype() == "LWPOLYLINE" and bool(entity.closed):
            try:
                points = [
                    (float(point.x), float(point.y))
                    for point in make_path(entity).flattening(distance=0.1)
                ]
            except Exception:
                continue
            if len(points) >= 3:
                rings.append(points)
    return rings


def _plan_metrics_for_insert(entity) -> dict[str, float]:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    polygons = []
    for ring in _virtual_polylines([entity]):
        polygon = Polygon(ring).buffer(0)
        if not polygon.is_empty and polygon.area > 1e-6:
            polygons.append(polygon)
    if not polygons:
        return {}
    ordered = sorted(polygons, key=lambda item: -item.area)
    positive: list[Any] = []
    negative: list[Any] = []
    for index, polygon in enumerate(ordered):
        point = polygon.representative_point()
        depth = sum(parent.contains(point) for parent in ordered[:index])
        (negative if depth % 2 else positive).append(polygon)
    geometry = unary_union(positive)
    if negative:
        geometry = geometry.difference(unary_union(negative))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        rectangle = geometry.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords)
    edges = [
        math.dist(coords[index], coords[index + 1]) / 1000.0
        for index in range(min(4, len(coords) - 1))
    ]
    return {
        "area_m2": float(geometry.area) / 1_000_000.0,
        "perimeter_m": float(geometry.length) / 1000.0,
        "major_m": max(edges) if edges else 0.0,
        "minor_m": min(edges) if edges else 0.0,
    }


def _reference_plan_metrics(path: Path) -> dict[str, dict[str, float]]:
    document = ezdxf.readfile(path)
    result: dict[str, dict[str, float]] = {}
    for entity in document.modelspace().query("INSERT"):
        metadata = _reference_metadata(entity)
        guid = metadata.get("guid")
        if guid and guid not in result:
            result[guid] = _plan_metrics_for_insert(entity)
    return result


def _geometry_fields(element_type: str) -> tuple[str, ...]:
    if element_type in {"room", "slab", "foundation", "stair"}:
        return ("area_m2", "perimeter_m")
    return ("major_m", "minor_m")


def _compare_file(
    file_record: dict[str, Any],
    golden_by_guid: dict[str, dict[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    path = Path(file_record["path"])
    source = _source_for_dxf(file_record, path)
    elements, warnings, _ = DxfAnalyzer().analyze(source, path)
    detected_by_guid = {
        str(element.properties.get("reference_guid")): element
        for element in elements
        if element.properties.get("reference_guid")
    }
    expected_guids = set(file_record["reference_guids"])
    detected_guids = set(detected_by_guid)
    missing = sorted(expected_guids - detected_guids)
    extra = sorted(detected_guids - expected_guids)
    wrong_type: list[dict[str, str]] = []
    differences: list[dict[str, Any]] = []
    geometry_differences: list[dict[str, Any]] = []
    plan_metrics = (
        _reference_plan_metrics(path)
        if file_record["variant"] in {"clean", "hard_geometry"}
        else {}
    )
    for guid in sorted(expected_guids & detected_guids):
        expected = golden_by_guid[guid]
        actual = detected_by_guid[guid]
        if actual.element_type != expected["type"]:
            wrong_type.append(
                {"guid": guid, "expected": expected["type"], "actual": actual.element_type}
            )
        for field, expected_value in expected["measurements"].items():
            actual_value = actual.measurements.get(field)
            if actual_value is None:
                differences.append(
                    {"guid": guid, "field": field, "expected": expected_value, "actual": None}
                )
                continue
            denominator = max(abs(float(expected_value)), 1e-9)
            ratio = abs(float(actual_value) - float(expected_value)) / denominator
            if ratio > tolerance:
                differences.append(
                    {
                        "guid": guid,
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value,
                        "difference_ratio": ratio,
                    }
                )
        for field in _geometry_fields(expected["type"]):
            expected_value = expected["geometry_metrics"].get(field)
            actual_value = plan_metrics.get(guid, {}).get(field)
            if expected_value is None or actual_value is None:
                geometry_differences.append(
                    {
                        "guid": guid,
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )
                continue
            denominator = max(abs(float(expected_value)), 1e-9)
            ratio = abs(float(actual_value) - float(expected_value)) / denominator
            if ratio > tolerance:
                geometry_differences.append(
                    {
                        "guid": guid,
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value,
                        "difference_ratio": ratio,
                    }
                )
    if file_record["variant"] in {"hard_unitless", "hard_wrong_unit"}:
        expected_warning = (
            "REFERENCE_DXF_UNIT_CONFIRMATION_REQUIRED"
            if file_record["variant"] == "hard_unitless"
            else "REFERENCE_DXF_UNIT_EVIDENCE_MISMATCH"
        )
        gate_ok = (
            not missing
            and not extra
            and not wrong_type
            and all(element.review_status == ReviewStatus.NEEDS_REVIEW for element in elements)
            and any(warning.code == expected_warning for warning in warnings)
        )
    else:
        gate_ok = (
            not missing
            and not extra
            and not wrong_type
            and not differences
            and not geometry_differences
        )
    return {
        "file": path.name,
        "variant": file_record["variant"],
        "expected_count": len(expected_guids),
        "detected_count": len(detected_guids),
        "missing": missing,
        "extra": extra,
        "wrong_type": wrong_type,
        "measurement_differences": differences,
        "geometry_differences": geometry_differences,
        "warning_codes": sorted({warning.code for warning in warnings}),
        "passed": gate_ok,
    }


def validate_references(
    manifest: dict[str, Any],
    *,
    selected: str = "all",
    data_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    root = cache_root(manifest, data_root)
    reports: list[dict[str, Any]] = []
    prior_passed = True
    for dataset in select_datasets(manifest, selected):
        if dataset["id"] == "clinic" and selected == "all" and not prior_passed:
            raise ReferenceLabError("PCERT kapısı geçmeden Clinic doğrulaması çalıştırılamaz.")
        generated_path = root / "generated" / dataset["id"] / "generated-manifest.json"
        if not generated_path.exists():
            raise ReferenceLabError(
                f"Üretilmiş manifest yok: {generated_path}; önce build çalıştırın."
            )
        generated = _json_load(generated_path)
        golden_by_guid: dict[str, dict[str, Any]] = {}
        for source in dataset["sources"]:
            golden_path = root / "generated" / dataset["id"] / "golden" / f"{source['id']}.json"
            golden = _json_load(golden_path)
            golden_by_guid.update({record["global_id"]: record for record in golden["elements"]})
        file_reports = [
            _compare_file(file_record, golden_by_guid, float(dataset["clean_tolerance_ratio"]))
            for file_record in generated["files"]
        ]
        passed = bool(file_reports) and all(report["passed"] for report in file_reports)
        report = {
            "schema_version": 1,
            "dataset_id": dataset["id"],
            "passed": passed,
            "tolerance_ratio": dataset["clean_tolerance_ratio"],
            "files": file_reports,
        }
        report_path = root / "generated" / dataset["id"] / "validation.json"
        _write_json(report_path, report)
        reports.append(report)
        prior_passed = passed
        if not passed:
            raise ReferenceLabError(f"{dataset['id']} doğrulama kapısı geçilemedi: {report_path}")
    return reports


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MetrajAI IFC/DXF doğrulama laboratuvarı")
    parser.add_argument("command", choices=("fetch", "build", "validate", "all"))
    parser.add_argument("--dataset", choices=("pcert", "clinic", "all"), default="all")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    if (
        argv is None
        and raw_args
        and raw_args[0] in {"build", "all"}
        and os.environ.get("PYTHONHASHSEED") != "0"
    ):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = "0"
        os.execve(
            sys.executable,
            [sys.executable, "-m", "metrajai.reference_lab", *raw_args],
            environment,
        )
    args = _parser().parse_args(raw_args)
    try:
        manifest = load_manifest(args.manifest)
        if args.command in {"fetch", "all"}:
            paths = fetch_references(manifest, selected=args.dataset, data_root=args.data_root)
            print(f"Doğrulandı/indirildi: {len(paths)} IFC")
        if args.command in {"build", "all"}:
            outputs = build_references(manifest, selected=args.dataset, data_root=args.data_root)
            print(f"Üretildi: {len(outputs)} referans çıktısı")
        if args.command in {"validate", "all"}:
            reports = validate_references(manifest, selected=args.dataset, data_root=args.data_root)
            for report in reports:
                print(f"{report['dataset_id']}: PASS ({len(report['files'])} DXF)")
    except ReferenceLabError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
