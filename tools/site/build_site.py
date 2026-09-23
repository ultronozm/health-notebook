#!/usr/bin/env python3
"""Build a private static dashboard from the health-notebook Org sources.

The Org files remain the source of truth.  This script parses their tables into
a JSON bundle and generates a static HTML page with daily macro totals, selected
lab trends, and links between meal rows, foods, and cooked batches.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from .org_tables import OrgTable, parse_org_tables
    from .meal_rows import classify_meal_row
except ImportError:  # Direct execution: python3 tools/site/build_site.py
    from org_tables import OrgTable, parse_org_tables
    from meal_rows import classify_meal_row


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SITE_TIMEZONE = "UTC"

MEAL_MACROS = {
    "Wt.": "weight_g",
    "Carb": "carb_g",
    "Cal": "cal",
    "Fat": "fat_g",
    "Prot.": "protein_g",
    "Prot": "protein_g",
    "Sat.": "sat_g",
    "Sat": "sat_g",
}

FOOD_MACROS = {
    "Carb": "carb_g_per_100g",
    "Fat": "fat_g_per_100g",
    "Sat.": "sat_g_per_100g",
    "Fiber": "fiber_g_per_100g",
    "Prot.": "protein_g_per_100g",
    "Prot": "protein_g_per_100g",
    "Cal": "cal_per_100g",
    "Sugar": "sugar_g_per_100g",
    "Salt": "salt_g_per_100g",
}

PACKAGE_MACROS = {
    "Wt.": "weight_g",
    "Wt": "weight_g",
    "Carb": "carb_g",
    "Cal": "cal",
    "Fat": "fat_g",
    "Prot.": "protein_g",
    "Prot": "protein_g",
    "Sat.": "sat_g",
    "Sat": "sat_g",
    "Fiber": "fiber_g",
}

TARGET_METRICS = {
    "cal": "cal",
    "calories": "cal",
    "carb": "carb_g",
    "carbs": "carb_g",
    "fat": "fat_g",
    "protein": "protein_g",
    "prot.": "protein_g",
    "prot": "protein_g",
    "sat.": "sat_g",
    "sat": "sat_g",
    "saturated fat": "sat_g",
}

FOOD_ALIASES: dict[str, tuple[str, str | None]] = {}
COMPOSITE_ITEMS: dict[str, str] = {}

ESTIMATE_KEYWORDS = (
    "photo est",
    "photo estimate",
    "cafeteria",
    "estimate",
    "uncertainty",
    "visible",
    "assortment",
)

def repo_path(repo: Path, *parts: str) -> Path:
    return repo.joinpath(*parts)


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"todo", "todo?", "n/a", "na", "*****", "komm"}:
        return None
    text = text.replace(",", ".").replace("~", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def num_or_none(value: Any) -> int | float | None:
    number = parse_number(value)
    if number is None:
        return None
    if math.isclose(number, round(number), abs_tol=1e-9):
        return int(round(number))
    return round(number, 3)


def apply_numeric_columns(
    entry: dict[str, Any], row: dict[str, str], mapping: dict[str, str]
) -> None:
    for source_col, target_col in mapping.items():
        if source_col not in row:
            continue
        entry[target_col] = num_or_none(row.get(source_col, ""))
        entry[f"{target_col}_text"] = row.get(source_col, "").strip()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "item"


def key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def batch_label(date: str) -> str:
    return f"Batch-{date.replace('-', '')}"


def extract_date(value: str) -> str | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    if match:
        return match.group(1)
    month_match = re.search(r"(\d{4})-(\d{2})(?!-\d{2})", value)
    if month_match:
        return f"{month_match.group(1)}-{month_match.group(2)}-01"
    return None


def fmt_num(value: Any, digits: int = 1) -> str:
    number = parse_number(value)
    if number is None:
        return ""
    if math.isclose(number, round(number), abs_tol=0.05):
        return str(int(round(number)))
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def fmt_int(value: Any) -> str:
    number = parse_number(value)
    if number is None:
        return ""
    return str(int(round(number)))


def parse_products(repo: Path) -> dict[str, Any]:
    foods_path = repo_path(repo, "foods.org")
    tables = parse_org_tables(foods_path, repo)
    product_table = next(
        (table for table in tables if "Food" in table.headers
         and (not table.headings or table.headings[-1] != "Package Shortcuts")),
        OrgTable("foods.org", 0, (), (), ()),
    )
    package_table = next(
        (table for table in tables if table.headings and table.headings[-1] == "Package Shortcuts"),
        OrgTable("foods.org", 0, (), (), ()),
    )

    raw_products: list[dict[str, Any]] = []
    food_counts = Counter(row.get("Food", "").strip() for row in product_table.rows)
    for index, row in enumerate(product_table.rows):
        food = row.get("Food", "").strip()
        if not food:
            continue
        product = row.get("Product", "").strip()
        id_basis = food if food_counts[food] == 1 else f"{food} {product}"
        entry: dict[str, Any] = {
            "id": f"food-{slugify(id_basis)}",
            "food": food,
            "product": product,
            "notes": row.get("Notes", "").strip(),
            "source": row.get("Source", "").strip(),
            "source_line": product_table.start_line + index + 1,
        }
        apply_numeric_columns(entry, row, FOOD_MACROS)
        raw_products.append(entry)

    raw_packages: list[dict[str, Any]] = []
    for index, row in enumerate(package_table.rows):
        food = row.get("Food", "").strip()
        if not food:
            continue
        basis = row.get("Basis", "").strip()
        entry = {
            "id": f"package-{slugify(food + ' ' + basis)}",
            "food": food,
            "basis": basis,
            "notes": row.get("Notes", "").strip(),
            "source_line": package_table.start_line + index + 1,
        }
        apply_numeric_columns(entry, row, PACKAGE_MACROS)
        raw_packages.append(entry)

    return {"products": raw_products, "packages": raw_packages}


def find_food_id(
    products: list[dict[str, Any]], food_name: str, product_hint: str | None
) -> str | None:
    candidates = [
        product
        for product in products
        if key(product["food"]) == key(food_name)
    ]
    if product_hint:
        hinted = [
            product
            for product in candidates
            if key(product_hint) in key(product.get("product", ""))
        ]
        if hinted:
            return hinted[0]["id"]
    if len(candidates) == 1:
        return candidates[0]["id"]
    return None


def build_food_aliases(products: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    food_name_counts = Counter(key(product["food"]) for product in products)

    for product in products:
        food_key = key(product["food"])
        product_key = key(product.get("product", ""))
        if food_name_counts[food_key] == 1:
            aliases[food_key] = product["id"]
        if product_key:
            aliases[key(f"{product['food']}, {product['product']}")] = product["id"]

    for alias, (food_name, product_hint) in FOOD_ALIASES.items():
        food_id = find_food_id(products, food_name, product_hint)
        if food_id:
            aliases[key(alias)] = food_id

    return aliases


def parse_batches(repo: Path) -> dict[str, Any]:
    batches_path = repo_path(repo, "batches.org")
    tables = parse_org_tables(batches_path, repo)
    batches: list[dict[str, Any]] = []
    by_date: dict[str, dict[str, Any]] = {}

    for table in tables:
        batch_heading = next(
            (heading for heading in table.headings if heading.startswith("Batch ")),
            "",
        )
        date = extract_date(batch_heading)
        if not date:
            continue
        batch = by_date.setdefault(
            date,
            {
                "id": f"batch-{date}",
                "date": date,
                "label": batch_label(date),
                "heading": batch_heading,
                "source": table.source,
                "ingredients": [],
                "per_100g": {},
            },
        )

        if table.headings and table.headings[-1].startswith("Ingredients"):
            for row in table.rows:
                if not row.get("Ingredient", "").strip() or row.get("Ingredient") == "Raw total":
                    continue
                ingredient: dict[str, Any] = {
                    "ingredient": row.get("Ingredient", "").strip(),
                    "source": row.get("Source", "").strip(),
                }
                apply_numeric_columns(ingredient, row, PACKAGE_MACROS)
                batch["ingredients"].append(ingredient)

        if table.headings and table.headings[-1] == "Cooked batch":
            for row in table.rows:
                field = row.get("Field", "").strip()
                value = row.get("Value", "").strip()
                if not field:
                    continue
                batch["per_100g"][slugify(field).replace("-", "_")] = {
                    "field": field,
                    "value": num_or_none(value),
                    "text": value,
                    "notes": row.get("Notes", "").strip(),
                }

    for date in sorted(by_date):
        batch = by_date[date]
        per = batch["per_100g"]
        batch["summary"] = {
            "weight_g": value_from_field(per, "cooked_stored_weight"),
            "carb_g_per_100g": value_from_field(per, "carb_per_100_g_net"),
            "cal_per_100g": value_from_field(per, "cal_per_100_g"),
            "fat_g_per_100g": value_from_field(per, "fat_per_100_g"),
            "protein_g_per_100g": value_from_field(per, "prot_per_100_g"),
            "sat_g_per_100g": value_from_field(per, "sat_per_100_g"),
            "fiber_g_per_100g": value_from_field(per, "fiber_per_100_g"),
        }
        batches.append(batch)

    return {"batches": batches, "by_date": by_date}


def parse_targets(repo: Path) -> dict[str, Any]:
    targets_path = repo_path(repo, "nutrition-targets.org")
    result: dict[str, Any] = {"targets": [], "warnings": []}
    if not targets_path.exists():
        return result

    for table in parse_org_tables(targets_path, repo):
        if "Metric" not in table.headers or "Direction" not in table.headers:
            continue
        for index, row in enumerate(table.rows):
            metric = row.get("Metric", "").strip()
            if not metric:
                continue
            metric_key = TARGET_METRICS.get(key(metric))
            if not metric_key:
                result["warnings"].append(
                    {
                        "level": "warning",
                        "kind": "unknown_target_metric",
                        "metric": metric,
                        "source": table.source,
                        "line": table.start_line + index + 1,
                    }
                )
                continue
            result["targets"].append(
                {
                    "metric": metric,
                    "metric_key": metric_key,
                    "lower": num_or_none(row.get("Lower", "")),
                    "target": num_or_none(row.get("Target", "")),
                    "upper": num_or_none(row.get("Upper", "")),
                    "direction": key(row.get("Direction", "")),
                    "units": row.get("Units", "").strip(),
                    "notes": row.get("Notes", "").strip(),
                    "source": table.source,
                    "source_line": table.start_line + index + 1,
                }
            )
    return result


def parse_appointment_notes(repo: Path) -> dict[str, Any]:
    path = repo_path(repo, "appointment-questions.org")
    if not path.exists():
        return {"source": "appointment-questions.org", "body": ""}
    return {
        "source": str(path.relative_to(repo)),
        "body": path.read_text(encoding="utf-8"),
    }


def value_from_field(fields: dict[str, Any], field_key: str) -> int | float | None:
    value = fields.get(field_key, {}).get("value")
    return value if isinstance(value, (int, float)) else None


def resolve_meal_item(
    item: str,
    notes: str,
    food_aliases: dict[str, str],
    batch_dates: set[str],
) -> dict[str, str]:
    item_key = key(item)
    batch_match = re.search(r"batch\s+(\d{4}-\d{2}-\d{2})", item_key)
    if batch_match and batch_match.group(1) in batch_dates:
        batch_id = f"batch-{batch_match.group(1)}"
        return {
            "kind": "batch",
            "target": batch_id,
            "href": f"#{batch_id}",
            "label": batch_label(batch_match.group(1)),
        }

    food_id = food_aliases.get(item_key)
    if food_id:
        return {"kind": "food", "target": food_id, "href": f"#{food_id}", "label": "food"}

    if item_key in COMPOSITE_ITEMS:
        return {
            "kind": "composite",
            "target": "",
            "href": "",
            "label": "composite",
        }

    combined = key(f"{item} {notes}")
    if any(keyword in combined for keyword in ESTIMATE_KEYWORDS):
        return {
            "kind": "estimate",
            "target": "",
            "href": "",
            "label": "estimate",
        }

    return {"kind": "unknown", "target": "", "href": "", "label": "unlinked"}


def parse_meals(
    repo: Path, food_aliases: dict[str, str], batch_dates: set[str]
) -> dict[str, Any]:
    meal_path = repo_path(repo, "meal-log.org")
    tables = parse_org_tables(meal_path, repo)
    days: list[dict[str, Any]] = []
    daily_totals: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for table in tables:
        if "Item" not in table.headers or "Carb" not in table.headers:
            continue
        date = next((extract_date(heading) for heading in table.headings if extract_date(heading)), None)
        if not date:
            continue

        day = {
            "id": f"day-{date}",
            "date": date,
            "source": table.source,
            "source_line": table.start_line,
            "items": [],
            "subtotals": [],
            "day_total": None,
        }
        current_time = ""
        subtotal_index = 0

        for row_index, row in enumerate(table.rows):
            item = row.get("Item", "").strip()
            if not item:
                continue
            if row.get("Time", "").strip():
                current_time = row.get("Time", "").strip()

            record: dict[str, Any] = {
                "date": date,
                "time": current_time,
                "item": item,
                "notes": row.get("Notes", "").strip(),
                "source_line": table.start_line + row_index + 1,
            }
            apply_numeric_columns(record, row, MEAL_MACROS)

            row_kind = classify_meal_row(item)
            if row_kind == "subtotal":
                subtotal_index += 1
                record["kind"] = row_kind
                record["id"] = f"{date}-subtotal-{subtotal_index}"
                day["subtotals"].append(record)
                day["items"].append(record)
                continue

            if row_kind == "day_total":
                record["kind"] = row_kind
                record["id"] = f"{date}-day-total"
                day["day_total"] = record
                day["items"].append(record)
                daily_totals.append(record)
                continue

            if row_kind == "running_total_reported":
                record["kind"] = row_kind
                record["id"] = f"{date}-day-so-far"
                day["reported_running_total"] = record
                day["items"].append(record)
                continue

            link = resolve_meal_item(item, record["notes"], food_aliases, batch_dates)
            record["kind"] = "item"
            record["id"] = f"{date}-item-{len(day['items']) + 1}"
            record["link"] = link
            day["items"].append(record)
            if link["kind"] == "unknown":
                warnings.append(
                    {
                        "level": "warning",
                        "kind": "unlinked_meal_item",
                        "date": date,
                        "item": item,
                        "source": table.source,
                        "line": record["source_line"],
                    }
                )

        running_total = computed_running_total(day)
        day["running_total"] = running_total
        if running_total and not day["day_total"]:
            day["items"].append(running_total)

        days.append(day)

    warnings.extend(validate_day_totals(days))
    return {"days": days, "daily_totals": daily_totals, "warnings": warnings}


def computed_running_total(day: dict[str, Any]) -> dict[str, Any] | None:
    columns = ("weight_g", "carb_g", "cal", "fat_g", "protein_g", "sat_g")
    item_rows = [row for row in day["items"] if row.get("kind") == "item"]
    if not item_rows:
        return None

    total: dict[str, Any] = {
        "date": day["date"],
        "time": "",
        "item": "Running total",
        "notes": "Computed from logged item rows; in-progress until Day total is entered.",
        "source_line": day["source_line"],
        "kind": "running_total",
        "id": f"{day['date']}-running-total",
    }
    any_value = False
    for column in columns:
        values = [row.get(column) for row in item_rows if isinstance(row.get(column), (int, float))]
        if values:
            total[column] = round(sum(values), 1)
            any_value = True
    return total if any_value else None


def validate_day_totals(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    columns = ["weight_g", "carb_g", "cal", "fat_g", "protein_g", "sat_g"]
    tolerances = {"cal": 15.0, "weight_g": 3.0}
    for day in days:
        reported = day.get("day_total")
        if not reported:
            continue
        item_rows = [row for row in day["items"] if row.get("kind") == "item"]
        for column in columns:
            values = [row.get(column) for row in item_rows if isinstance(row.get(column), (int, float))]
            if not values:
                continue
            calculated = round(sum(values), 1)
            actual = reported.get(column)
            if not isinstance(actual, (int, float)):
                continue
            tolerance = tolerances.get(column, 1.0)
            if abs(calculated - actual) > tolerance:
                warnings.append(
                    {
                        "level": "warning",
                        "kind": "day_total_mismatch",
                        "date": day["date"],
                        "column": column,
                        "calculated": calculated,
                        "reported": actual,
                    }
                )
    return warnings


def normalize_test_name(test: str) -> str:
    lowered = test.lower()
    if "a1c" in lowered:
        return "HbA1c"
    if "non-hdl" in lowered:
        return "Non-HDL cholesterol"
    if "ldl" in lowered:
        return "LDL"
    if "hdl" in lowered:
        return "HDL"
    if "triglycerid" in lowered or "triglycerides" in lowered:
        return "Triglycerides"
    if "kolesterol" in lowered or "chol" in lowered:
        return "Total cholesterol"
    if "glukose, middel" in lowered or "mean glucose" in lowered:
        return "Estimated mean glucose"
    if "glukose" in lowered or "glucose" in lowered:
        return "Plasma glucose"
    if "c-peptid" in lowered or "c-peptide" in lowered:
        return "C-peptide"
    if "gfr" in lowered:
        return "eGFR"
    if "kreatinin" in lowered or "creatinine" in lowered:
        return "Creatinine"
    if "b12" in lowered:
        return "Vitamin B12"
    if "kalium" in lowered:
        return "Potassium"
    if "thyrotropin" in lowered or "tsh" in lowered:
        return "TSH"
    return test.strip()


def parse_labs(repo: Path) -> dict[str, Any]:
    lab_path = repo_path(repo, "lab-results.org")
    tables = parse_org_tables(lab_path, repo)
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for table in tables:
        headers = set(table.headers)
        table_date = next(
            (extract_date(heading) for heading in table.headings if extract_date(heading)),
            None,
        )
        heading_test = table.headings[-1] if table.headings else ""

        if "Date" in headers and "Result" in headers:
            for index, row in enumerate(table.rows):
                date = extract_date(row.get("Date", ""))
                if not date:
                    continue
                test = row.get("Test", "").strip() or heading_test
                units = row.get("Units", "").strip()
                result_text = row.get("Result", "").strip()
                add_lab_entry(entries, seen, table, index, date, test, result_text, units, row)
            continue

        if "Test" in headers and "Result" in headers and table_date:
            for index, row in enumerate(table.rows):
                test = row.get("Test", "").strip()
                if not test:
                    continue
                units = row.get("Units", "").strip()
                result_text = row.get("Result", "").strip()
                add_lab_entry(entries, seen, table, index, table_date, test, result_text, units, row)

                mgdl_header = next(
                    (header for header in table.headers if "mg/dL" in header),
                    None,
                )
                if mgdl_header and row.get(mgdl_header, "").strip():
                    add_lab_entry(
                        entries,
                        seen,
                        table,
                        index,
                        table_date,
                        test,
                        row.get(mgdl_header, "").strip(),
                        "mg/dL",
                        row,
                    )

    entries.sort(key=lambda entry: (entry["date"], entry["test_norm"], entry["units"]))
    return {"entries": entries, "trends": build_lab_trends(entries)}


def glucose_raw_dir(repo: Path) -> Path:
    configured = os.environ.get("HEALTH_NOTEBOOK_GLUCOSE_RAW_DIR")
    if configured:
        return Path(configured).expanduser()
    return repo_path(repo, "data", "raw", "librelinkup")


def parse_glucose_raw(raw_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "raw_dir": str(raw_dir),
        "file_count": 0,
        "point_count": 0,
        "latest": None,
        "days": [],
        "warnings": [],
    }
    if not raw_dir.exists():
        result["warnings"].append({"kind": "missing_raw_dir", "path": str(raw_dir)})
        return result
    try:
        files = sorted(raw_dir.glob("*.json"))
    except OSError as exc:
        result["warnings"].append(
            {"kind": "unreadable_raw_dir", "path": str(raw_dir), "error": str(exc)}
        )
        return result

    result["file_count"] = len(files)
    points_by_time: dict[str, dict[str, Any]] = {}
    latest_candidates: list[dict[str, Any]] = []

    for path in files:
        prefix = path.name.split("-", 1)[0]
        if prefix not in {"graph", "latest", "logbook"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result["warnings"].append(
                {"kind": "bad_glucose_file", "path": str(path), "error": str(exc)}
            )
            continue

        measurements = payload if isinstance(payload, list) else [payload]
        for measurement in measurements:
            point = glucose_point(measurement, path.name, prefix)
            if not point:
                continue
            points_by_time[point["timestamp"]] = point
            if prefix == "latest":
                latest_candidates.append(point)

    points = sorted(points_by_time.values(), key=lambda point: point["timestamp"])
    result["point_count"] = len(points)
    latest_pool = latest_candidates or points
    if latest_pool:
        result["latest"] = max(latest_pool, key=lambda point: point["timestamp"])

    days: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        days.setdefault(point["date"], []).append(point)

    result["days"] = [
        {
            "date": day,
            "points": day_points,
            "summary": glucose_summary(day_points),
        }
        for day, day_points in sorted(days.items())
    ]
    return result


def glucose_point(
    measurement: Any, source_file: str, source_kind: str
) -> dict[str, Any] | None:
    if not isinstance(measurement, dict):
        return None
    timestamp = measurement.get("timestamp") or measurement.get("factory_timestamp")
    value = parse_number(measurement.get("value"))
    if not timestamp or value is None:
        return None
    parsed = parse_glucose_datetime(str(timestamp))
    if not parsed:
        return None
    return {
        "timestamp": parsed.isoformat(timespec="seconds"),
        "date": parsed.date().isoformat(),
        "time": parsed.strftime("%H:%M"),
        "minute_of_day": parsed.hour * 60 + parsed.minute + parsed.second / 60,
        "value": round(value, 2),
        "mg_dl": num_or_none(measurement.get("value_in_mg_per_dl")),
        "is_low": bool(measurement.get("is_low")),
        "is_high": bool(measurement.get("is_high")),
        "trend": measurement.get("trend"),
        "source_kind": source_kind,
        "source_file": source_file,
    }


def parse_glucose_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        timezone = ZoneInfo(os.environ.get("HEALTH_NOTEBOOK_TZ", DEFAULT_SITE_TIMEZONE))
        parsed = parsed.astimezone(timezone).replace(tzinfo=None)
    return parsed


def glucose_summary(points: list[dict[str, Any]]) -> dict[str, Any]:
    values = [point["value"] for point in points if isinstance(point.get("value"), (int, float))]
    if not values:
        return {}
    return {
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "avg": round(sum(values) / len(values), 1),
        "count": len(values),
    }


def add_lab_entry(
    entries: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    table: OrgTable,
    row_index: int,
    date: str,
    test: str,
    result_text: str,
    units: str,
    row: dict[str, str],
) -> None:
    if not result_text:
        return
    normalized = normalize_test_name(test)
    dedupe_key = (date, normalized, result_text, units)
    if dedupe_key in seen:
        return
    seen.add(dedupe_key)
    entries.append(
        {
            "id": f"lab-{slugify(date + ' ' + normalized + ' ' + units + ' ' + result_text)}",
            "date": date,
            "test": test,
            "test_norm": normalized,
            "result_text": result_text,
            "value": num_or_none(result_text),
            "units": units,
            "reference_range": row.get("Reference range", "").strip(),
            "flag": row.get("Flag", "").strip(),
            "note": row.get("Note", row.get("Context", "")).strip(),
            "source": table.source,
            "source_line": table.start_line + row_index + 1,
            "source_heading": " / ".join(table.headings),
        }
    )


def build_lab_trends(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    trend_specs = {
        "hba1c_mmol_mol": ("HbA1c", "mmol/mol"),
        "ldl_mmol_l": ("LDL", "mmol/l"),
        "hdl_mmol_l": ("HDL", "mmol/l"),
        "triglycerides_mmol_l": ("Triglycerides", "mmol/l"),
        "total_cholesterol_mmol_l": ("Total cholesterol", "mmol/l"),
        "ldl_mg_dl": ("LDL", "mg/dL"),
        "hdl_mg_dl": ("HDL", "mg/dL"),
        "triglycerides_mg_dl": ("Triglycerides", "mg/dL"),
        "total_cholesterol_mg_dl": ("Total cholesterol", "mg/dL"),
        "vitamin_b12_pmol_l": ("Vitamin B12", "pmol/l"),
        "creatinine_umol_l": ("Creatinine", "umol/l"),
        "egfr": ("eGFR", ""),
    }
    trends: dict[str, list[dict[str, Any]]] = {}
    for trend_key, (test_name, unit) in trend_specs.items():
        points: list[dict[str, Any]] = []
        seen_dates_values: set[tuple[str, Any]] = set()
        # Prefer native target-unit rows, then fill older values from converted
        # rows where only the other unit system is available.
        for native_only in (True, False):
            for entry in entries:
                if entry["test_norm"] != test_name:
                    continue
                if unit and native_only != (entry.get("units") == unit):
                    continue
                value = converted_lab_value(entry, unit)
                if not isinstance(value, (int, float)):
                    continue
                marker = (entry["date"], test_name)
                if marker in seen_dates_values:
                    continue
                seen_dates_values.add(marker)
                points.append(
                    {
                        "date": entry["date"],
                        "value": value,
                        "label": fmt_num(value, 2),
                        "units": unit or entry["units"],
                        "source_units": entry["units"],
                        "source_value": entry["result_text"],
                        "source": entry["source"],
                    }
                )
        trends[trend_key] = sorted(points, key=lambda point: point["date"])
    return trends


def converted_lab_value(entry: dict[str, Any], target_unit: str) -> int | float | None:
    value = entry.get("value")
    if not isinstance(value, (int, float)):
        return None
    source_unit = entry.get("units", "")
    if not target_unit or source_unit == target_unit:
        return value

    test = entry.get("test_norm", "")
    if target_unit == "mmol/l" and source_unit == "mg/dL":
        if test in {"LDL", "HDL", "Total cholesterol", "Non-HDL cholesterol"}:
            return round(value / 38.67, 2)
        if test == "Triglycerides":
            return round(value / 88.57, 2)
    if target_unit == "mg/dL" and source_unit == "mmol/l":
        if test in {"LDL", "HDL", "Total cholesterol", "Non-HDL cholesterol"}:
            return round(value * 38.67)
        if test == "Triglycerides":
            return round(value * 88.57)
    return None


def collect_validation(
    products: dict[str, Any],
    meals: dict[str, Any],
    batches: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, Any]:
    warnings = list(meals["warnings"])
    warnings.extend(targets.get("warnings", []))
    for product in products["products"]:
        if product.get("carb_g_per_100g") is None:
            warnings.append(
                {
                    "level": "warning",
                    "kind": "missing_food_carb",
                    "food": product["food"],
                    "product": product.get("product", ""),
                }
            )
    for batch in batches["batches"]:
        summary = batch.get("summary", {})
        if summary.get("carb_g_per_100g") is None:
            warnings.append(
                {
                    "level": "warning",
                    "kind": "missing_batch_carb",
                    "date": batch["date"],
                }
            )
    return {
        "errors": [],
        "warnings": warnings,
        "summary": {
            "warning_count": len(warnings),
            "error_count": 0,
        },
    }


def current_site_date() -> str:
    timezone = os.environ.get("HEALTH_NOTEBOOK_TZ", DEFAULT_SITE_TIMEZONE)
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def build_data(
    repo: Path = REPO_ROOT,
    today: str | None = None,
    glucose_dir: Path | None = None,
) -> dict[str, Any]:
    products = parse_products(repo)
    food_aliases = build_food_aliases(products["products"])
    batches = parse_batches(repo)
    meals = parse_meals(repo, food_aliases, set(batches["by_date"].keys()))
    labs = parse_labs(repo)
    glucose = parse_glucose_raw(glucose_dir or glucose_raw_dir(repo))
    targets = parse_targets(repo)
    appointments = parse_appointment_notes(repo)
    validation = collect_validation(products, meals, batches, targets)
    site_date = today or current_site_date()

    return {
        "schema_version": 1,
        "generated": {
            "date": site_date,
            "timezone": os.environ.get("HEALTH_NOTEBOOK_TZ", DEFAULT_SITE_TIMEZONE),
        },
        "source_files": [
            "body-weight.org",
            "foods.org",
            "batches.org",
            "meal-log.org",
            "lab-results.org",
            "nutrition-targets.org",
            "appointment-questions.org",
        ],
        "foods": products,
        "batches": {"batches": batches["batches"]},
        "meals": {
            "days": meals["days"],
            "daily_totals": meals["daily_totals"],
        },
        "weight": parse_weight(repo),
        "targets": targets,
        "appointments": appointments,
        "glucose": glucose,
        "labs": labs,
        "validation": validation,
    }


def parse_weight(repo: Path) -> list[dict[str, Any]]:
    entries = []
    for table in parse_org_tables(repo / "body-weight.org", repo):
        for row in table.rows:
            date = extract_date(row.get("Date", ""))
            value = num_or_none(row.get("Weight", ""))
            if date and value is not None:
                entries.append({"date": date, "value": value,
                                "units": row.get("Units", ""), "notes": row.get("Notes", "")})
    return sorted(entries, key=lambda entry: entry["date"])


def render_weight(entries: list[dict[str, Any]]) -> str:
    charts = []
    for unit in sorted({entry["units"] for entry in entries}):
        charts.append(render_line_chart([e for e in entries if e["units"] == unit],
                                       f"Body weight ({unit})", "#2f6f5e"))
    rows = "".join(f"<tr><td>{escape(e['date'])}</td><td>{fmt_num(e['value'])}</td>"
                   f"<td>{escape(e['units'])}</td><td class='text'>{escape(e['notes'])}</td></tr>"
                   for e in entries)
    return ("".join(charts) + "<table><thead><tr><th>Date</th><th>Weight</th>"
            "<th>Units</th><th>Notes</th></tr></thead><tbody>" + rows + "</tbody></table>")


def render_optional_glucose(data: dict[str, Any], today_date: str) -> str:
    if not data["glucose"]["point_count"]:
        return ""
    return ('<section id="glucose"><h2>Glucose And Meals</h2>'
            + render_glucose_days(data["glucose"], data["meals"]["days"], today_date)
            + '</section>')


def macro_value(row: dict[str, Any], column: str) -> str:
    return fmt_num(row.get(column))


def escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def render_site(data: dict[str, Any]) -> str:
    daily_totals = data["meals"]["daily_totals"]
    today_date = data.get("generated", {}).get("date")
    today_total = today_macro_total(data["meals"], today_date)
    embedded_json = json.dumps(data, ensure_ascii=False, sort_keys=True).replace(
        "</", "<\\/"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Health Notebook</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f7f4;
      --ink: #1f2933;
      --muted: #667085;
      --line: #d8ddd2;
      --panel: #ffffff;
      --accent: #2f6f5e;
      --accent-2: #8b5e34;
      --warn: #9a3412;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header, main {{ max-width: 1180px; margin: 0 auto; padding: 18px; }}
    header {{
      display: grid;
      gap: 10px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 26px 0 10px; font-size: 20px; letter-spacing: 0; }}
    h3 {{ margin: 18px 0 8px; font-size: 16px; letter-spacing: 0; }}
    p {{ margin: 0 0 10px; color: var(--muted); max-width: 82ch; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    nav a, .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--ink);
      background: #fff;
      text-decoration: none;
      white-space: nowrap;
    }}
    .pill.warn {{ color: var(--warn); border-color: #fed7aa; background: #fff7ed; }}
    section {{ margin: 0 0 26px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
      align-items: start;
    }}
    .progress-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 0 0 12px;
    }}
    .progress-card {{
      min-height: 108px;
      padding: 10px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .progress-card.good {{ border-color: #9dc7a7; }}
    .progress-card.warn {{ border-color: #f4a261; }}
    .progress-label {{ color: var(--muted); font-size: 12px; font-weight: 650; }}
    .progress-value {{ margin: 4px 0 8px; font-size: 20px; font-weight: 750; }}
    .progress-meter {{
      height: 7px;
      overflow: hidden;
      border-radius: 4px;
      background: #eef2eb;
    }}
    .progress-meter span {{
      display: block;
      height: 100%;
      min-width: 2px;
      max-width: 100%;
      background: var(--accent);
    }}
    .progress-card.warn .progress-meter span {{ background: var(--warn); }}
    figure {{
      margin: 0;
      padding: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow-x: auto;
    }}
    figcaption {{ font-weight: 650; margin-bottom: 8px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      margin: 0 0 12px;
    }}
    th, td {{
      padding: 6px 8px;
      border-bottom: 1px solid var(--line);
      text-align: right;
      vertical-align: top;
    }}
    th:first-child, td:first-child, .text {{ text-align: left; }}
    th {{ font-size: 12px; color: #344054; background: #eef2eb; }}
    tr.subtotal td {{ font-weight: 650; background: #f3f6ef; }}
    tr.day-total td {{ font-weight: 750; background: #e6eee6; }}
    tr.estimate td:first-child::after,
    tr.composite td:first-child::after,
    tr.unknown td:first-child::after {{
      content: attr(data-kind);
      display: inline-block;
      margin-left: 6px;
      font-size: 11px;
      color: var(--muted);
    }}
    a {{ color: var(--accent); }}
    .small {{ font-size: 12px; color: var(--muted); }}
    .meal-markers {{
      margin: 6px 0 16px;
      padding: 0;
      color: var(--muted);
      list-style: none;
    }}
    .meal-markers li {{ margin: 2px 0; }}
    .org-notes {{
      max-width: 920px;
      padding: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .org-notes h3 {{ margin-top: 16px; }}
    .org-notes h4 {{ margin: 14px 0 6px; font-size: 14px; }}
    .org-notes ul {{ margin: 0 0 10px 20px; padding: 0; }}
    .org-notes li {{ margin: 4px 0; }}
    code {{
      padding: 1px 4px;
      border-radius: 4px;
      background: #eef2eb;
      color: #344054;
    }}
    .chart-axis {{ stroke: #98a2b3; stroke-width: 1; }}
    .chart-grid {{ stroke: #e4e7ec; stroke-width: 1; }}
    .chart-line {{ fill: none; stroke-width: 2.5; }}
    .chart-dot {{ stroke: #fff; stroke-width: 2; }}
    @media (max-width: 760px) {{
      header, main {{ padding: 12px; }}
      table {{ font-size: 12px; }}
      th, td {{ padding: 5px 6px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Health Notebook</h1>
    <p>Meals, nutrition, and health observations from your notebook.</p>
    <nav>
      <a href="#daily">Daily macros</a>
      {'<a href="#glucose">Glucose</a>' if data["glucose"]["point_count"] else ""}
      <a href="#weight">Body weight</a>
      <a href="#labs">Lab trends</a>
      <a href="#appointments">Appointments</a>
      <a href="#foods">Foods</a>
      <a href="#batches">Batches</a>
      <a href="#meal-details">Meal details</a>
      <a href="#validation">Validation</a>
    </nav>
  </header>
  <main>
    <section id="daily">
      <h2>Daily Macro Totals</h2>
      {render_today_progress(today_total, data["targets"]["targets"])}
      {render_daily_totals(daily_totals, today_date, today_total)}
      <div class="grid">
        {render_bar_chart(daily_totals, "cal", "Calories by day", "#2f6f5e")}
        {render_bar_chart(daily_totals, "carb_g", "Carbs by day", "#8b5e34")}
        {render_bar_chart(daily_totals, "protein_g", "Protein by day", "#475467")}
        {render_bar_chart(daily_totals, "sat_g", "Saturated fat by day", "#9a3412")}
      </div>
    </section>
    {render_optional_glucose(data, today_date)}
    <section id="weight">
      <h2>Body Weight</h2>
      {render_weight(data["weight"])}
    </section>
    <section id="labs">
      <h2>Lab Trends</h2>
      <div class="grid">
        {render_lab_charts(data["labs"]["entries"])}
      </div>
      {render_lab_table(data["labs"]["entries"])}
    </section>
    <section id="appointments">
      <h2>Appointments</h2>
      {render_appointment_notes(data["appointments"])}
    </section>
    <section id="foods">
      <h2>Foods</h2>
      {render_foods(data["foods"]["products"])}
    </section>
    <section id="batches">
      <h2>Batches</h2>
      {render_batches(data["batches"]["batches"])}
    </section>
    <section id="meal-details">
      <h2>Meal Details</h2>
      {render_meal_details(data["meals"]["days"])}
    </section>
    <section id="validation">
      <h2>Validation</h2>
      {render_validation(data["validation"])}
    </section>
  </main>
  <script type="application/json" id="site-data">{embedded_json}</script>
</body>
</html>
"""


def today_macro_total(meals: dict[str, Any], today_date: str | None) -> dict[str, Any] | None:
    if not today_date:
        return None
    for day in meals.get("days", []):
        if day.get("date") != today_date:
            continue
        return day.get("day_total") or day.get("running_total")
    return None


def render_daily_totals(
    daily_totals: list[dict[str, Any]],
    today_date: str | None,
    today_total: dict[str, Any] | None,
) -> str:
    totals = sorted(daily_totals, key=lambda row: row["date"])
    today_rows = [today_total] if today_total else []
    previous_rows = [row for row in totals if row.get("date") != today_date]

    chunks: list[str] = []
    if today_rows:
        chunks.append("<h3>Today</h3>")
        chunks.append(render_daily_total_table(today_rows, label_today=True))
        if previous_rows:
            chunks.append("<h3>Previous Days</h3>")
    if previous_rows:
        chunks.append(render_daily_total_table(previous_rows, label_today=False))
    elif not today_rows:
        chunks.append("<p>No daily totals recorded yet.</p>")
    return "".join(chunks)


def render_today_progress(
    today_total: dict[str, Any] | None,
    targets: list[dict[str, Any]],
) -> str:
    if not today_total or not targets:
        return ""

    cards: list[str] = []
    for target in targets:
        metric_key = target.get("metric_key")
        current = today_total.get(metric_key)
        if not isinstance(current, (int, float)):
            continue
        status = target_status(current, target)
        reference = target_reference(target)
        units = target.get("units", "")
        value = fmt_num(current)
        if reference:
            value = f"{value} / {reference}"
        elif units:
            value = f"{value} {units}"
        cards.append(
            f"<div class='progress-card {escape(status['class'])}'>"
            f"<div class='progress-label'>{escape(target.get('metric', ''))}</div>"
            f"<div class='progress-value'>{escape(value)}</div>"
            "<div class='progress-meter'>"
            f"<span style='width:{status['percent']:.0f}%'></span>"
            "</div>"
            f"<div class='small'>{escape(status['message'])}</div>"
            "</div>"
        )
    if not cards:
        return ""
    return "<h3>Today Progress</h3><div class='progress-grid'>" + "".join(cards) + "</div>"


def target_reference(target: dict[str, Any]) -> str:
    units = target.get("units", "")
    direction = target.get("direction", "")
    lower = target.get("lower")
    upper = target.get("upper")
    target_value = target.get("target")

    if direction == "range" and isinstance(lower, (int, float)) and isinstance(upper, (int, float)):
        return f"{fmt_num(lower)}-{fmt_num(upper)} {units}".strip()
    if direction == "minimum":
        threshold = target_value if isinstance(target_value, (int, float)) else lower
        if isinstance(threshold, (int, float)):
            return f">= {fmt_num(threshold)} {units}".strip()
    if direction == "maximum":
        threshold = target_value if isinstance(target_value, (int, float)) else upper
        if isinstance(threshold, (int, float)):
            return f"<= {fmt_num(threshold)} {units}".strip()
    if isinstance(target_value, (int, float)):
        return f"{fmt_num(target_value)} {units}".strip()
    return ""


def target_status(current: int | float, target: dict[str, Any]) -> dict[str, Any]:
    direction = target.get("direction", "")
    units = target.get("units", "")
    lower = target.get("lower")
    upper = target.get("upper")
    target_value = target.get("target")

    def message(text: str, css_class: str, scale: int | float | None) -> dict[str, Any]:
        if isinstance(scale, (int, float)) and scale > 0:
            percent = max(0.0, min(100.0, 100.0 * float(current) / float(scale)))
        else:
            percent = 100.0
        return {"message": text, "class": css_class, "percent": percent}

    if direction == "range" and isinstance(lower, (int, float)) and isinstance(upper, (int, float)):
        if current < lower:
            return message(
                f"{fmt_num(lower - current)} {units} below lower range".strip(),
                "warn",
                upper,
            )
        if current > upper:
            return message(
                f"{fmt_num(current - upper)} {units} over upper range".strip(),
                "warn",
                upper,
            )
        return message("In range", "good", upper)

    if direction == "minimum":
        threshold = target_value if isinstance(target_value, (int, float)) else lower
        if isinstance(threshold, (int, float)):
            if current < threshold:
                return message(
                    f"{fmt_num(threshold - current)} {units} to target".strip(),
                    "warn",
                    threshold,
                )
            return message("Target met", "good", threshold)

    if direction == "maximum":
        threshold = target_value if isinstance(target_value, (int, float)) else upper
        if isinstance(threshold, (int, float)):
            if current > threshold:
                return message(
                    f"{fmt_num(current - threshold)} {units} over target".strip(),
                    "warn",
                    threshold,
                )
            return message(
                f"{fmt_num(threshold - current)} {units} left".strip(),
                "good",
                threshold,
            )

    note = target.get("notes") or "Tracked"
    return message(str(note), "", target_value)


def render_daily_total_table(
    daily_totals: list[dict[str, Any]], label_today: bool
) -> str:
    rows = []
    for total in daily_totals:
        date_label = "Today" if label_today else total["date"]
        target_id = total.get("id") or f"{total['date']}-day-total"
        rows.append(
            "<tr>"
            f"<td class='text'><a href='#{escape(target_id)}'>{escape(date_label)}</a></td>"
            f"<td>{macro_value(total, 'weight_g')}</td>"
            f"<td>{macro_value(total, 'carb_g')}</td>"
            f"<td>{macro_value(total, 'cal')}</td>"
            f"<td>{macro_value(total, 'fat_g')}</td>"
            f"<td>{macro_value(total, 'protein_g')}</td>"
            f"<td>{macro_value(total, 'sat_g')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Date</th><th>Wt.</th><th>Carb</th><th>Cal</th>"
        "<th>Fat</th><th>Prot.</th><th>Sat.</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_foods(products: list[dict[str, Any]]) -> str:
    rows = []
    for product in products:
        rows.append(
            f"<tr id='{escape(product['id'])}'>"
            f"<td class='text'>{escape(product['food'])}</td>"
            f"<td class='text'>{escape(product.get('product', ''))}</td>"
            f"<td>{fmt_num(product.get('carb_g_per_100g'))}</td>"
            f"<td>{fmt_num(product.get('cal_per_100g'))}</td>"
            f"<td>{fmt_num(product.get('fat_g_per_100g'))}</td>"
            f"<td>{fmt_num(product.get('protein_g_per_100g'))}</td>"
            f"<td>{fmt_num(product.get('sat_g_per_100g'))}</td>"
            f"<td>{fmt_num(product.get('fiber_g_per_100g'))}</td>"
            f"<td class='text small'>{escape(product.get('notes', ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Food</th><th>Product</th><th>Carb</th><th>Cal</th>"
        "<th>Fat</th><th>Prot.</th><th>Sat.</th><th>Fiber</th><th>Notes</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_batches(batches: list[dict[str, Any]]) -> str:
    rows = []
    for batch in batches:
        summary = batch.get("summary", {})
        rows.append(
            f"<tr id='{escape(batch['id'])}'>"
            f"<td class='text'>{escape(batch.get('label', batch['date']))}</td>"
            f"<td class='text'>{escape(batch['date'])}</td>"
            f"<td>{fmt_num(summary.get('weight_g'))}</td>"
            f"<td>{fmt_num(summary.get('carb_g_per_100g'))}</td>"
            f"<td>{fmt_num(summary.get('cal_per_100g'))}</td>"
            f"<td>{fmt_num(summary.get('fat_g_per_100g'))}</td>"
            f"<td>{fmt_num(summary.get('protein_g_per_100g'))}</td>"
            f"<td>{fmt_num(summary.get('sat_g_per_100g'))}</td>"
            f"<td>{fmt_num(summary.get('fiber_g_per_100g'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Batch</th><th>Date</th><th>Cooked wt.</th><th>Carb/100g</th>"
        "<th>Cal/100g</th><th>Fat/100g</th><th>Prot./100g</th><th>Sat./100g</th>"
        "<th>Fiber/100g</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_meal_details(days: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for day in sorted(days, key=lambda item: item["date"]):
        rows: list[str] = []
        for row in day["items"]:
            kind = row.get("kind", "")
            classes = {
                "subtotal": "subtotal",
                "day_total": "day-total",
                "running_total": "day-total",
                "running_total_reported": "day-total",
                "item": row.get("link", {}).get("kind", ""),
            }
            class_attr = classes.get(kind, "")
            display_item = meal_item_html(row)
            rows.append(
                f"<tr id='{escape(row['id'])}' class='{escape(class_attr)}'>"
                f"<td class='text'>{escape(row.get('time', ''))}</td>"
                f"<td class='text' data-kind='{escape(row.get('link', {}).get('label', ''))}'>{display_item}</td>"
                f"<td>{macro_value(row, 'weight_g')}</td>"
                f"<td>{macro_value(row, 'carb_g')}</td>"
                f"<td>{macro_value(row, 'cal')}</td>"
                f"<td>{macro_value(row, 'fat_g')}</td>"
                f"<td>{macro_value(row, 'protein_g')}</td>"
                f"<td>{macro_value(row, 'sat_g')}</td>"
                f"<td class='text small'>{escape(row.get('notes', ''))}</td>"
                "</tr>"
            )
        chunks.append(
            f"<h3 id='day-{escape(day['date'])}'>{escape(day['date'])}</h3>"
            "<table><thead><tr><th>Time</th><th>Item</th><th>Wt.</th><th>Carb</th>"
            "<th>Cal</th><th>Fat</th><th>Prot.</th><th>Sat.</th><th>Notes</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    return "".join(chunks)


# How many recent days to draw as individual CGM charts. Each day is an inline
# SVG, so this caps page weight (phone-loadable), not the parsed data -- all
# days remain in the data bundle. Bump freely; ~60 covers two months.
GLUCOSE_CHART_DAYS = 60


def render_glucose_days(
    glucose: dict[str, Any],
    meal_days: list[dict[str, Any]],
    today_date: str | None,
) -> str:
    glucose_days = {day["date"]: day for day in glucose.get("days", [])}
    meals_by_date = {day["date"]: day for day in meal_days}
    relevant_dates = sorted(set(glucose_days) | set(meals_by_date), reverse=True)
    if not relevant_dates:
        return "<p>No glucose or meal data available.</p>"

    chunks: list[str] = []
    latest = glucose.get("latest")
    if latest:
        chunks.append(
            "<p class='small'>"
            f"Latest raw CGM point: {escape(latest['date'])} {escape(latest['time'])}, "
            f"{fmt_num(latest['value'])} mmol/l. "
            f"Parsed {escape(glucose.get('point_count', 0))} unique points from "
            f"{escape(glucose.get('file_count', 0))} raw files."
            "</p>"
        )
    else:
        chunks.append(
            "<p>No LibreLinkUp raw files were readable for this build. Set "
            "<code>HEALTH_NOTEBOOK_GLUCOSE_RAW_DIR</code> when building to enable charts.</p>"
        )

    # Always keep the "today" date in view: in production it is the most recent
    # date (so this is a no-op), but it stops a fixed "today" from being pushed
    # out of the recent-window by a growing meal log.
    ordered_dates = relevant_dates
    if today_date and (today_date in glucose_days or today_date in meals_by_date):
        ordered_dates = [today_date, *(d for d in relevant_dates if d != today_date)]

    for date in ordered_dates[:GLUCOSE_CHART_DAYS]:
        points = glucose_days.get(date, {}).get("points", [])
        meal_groups = meal_groups_for_day(meals_by_date.get(date, {}))
        if not points and not meal_groups:
            continue
        title = "Today" if date == today_date else date
        chunks.append(f"<h3>{escape(title)}</h3>")
        chunks.append(render_glucose_chart(points, meal_groups, f"CGM and meals for {date}"))
        chunks.append(render_meal_marker_list(meal_groups))
    return "".join(chunks)


def meal_groups_for_day(day: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current_items: list[dict[str, Any]] = []
    current_time = ""

    def finish(label: str = "") -> None:
        nonlocal current_items, current_time
        if not current_items:
            return
        group = summarize_meal_group(current_items, len(groups) + 1, current_time, label)
        groups.append(group)
        current_items = []
        current_time = ""

    for row in day.get("items", []):
        kind = row.get("kind")
        if kind == "day_total":
            finish()
            continue
        if kind == "subtotal":
            if current_items:
                subtotal_group = summarize_meal_group(
                    current_items,
                    len(groups) + 1,
                    current_time,
                    row.get("notes", ""),
                )
                for source, target in (
                    ("carb_g", "carb_g"),
                    ("cal", "cal"),
                    ("protein_g", "protein_g"),
                    ("sat_g", "sat_g"),
                ):
                    if isinstance(row.get(source), (int, float)):
                        subtotal_group[target] = row[source]
                groups.append(subtotal_group)
                current_items = []
                current_time = ""
            continue
        if kind != "item":
            continue
        row_time = row.get("time", "")
        if current_items and row_time and row_time != current_time:
            finish()
        if row_time and not current_time:
            current_time = row_time
        current_items.append(row)
    finish()
    return groups


def summarize_meal_group(
    rows: list[dict[str, Any]], number: int, time: str, label: str
) -> dict[str, Any]:
    def group_sum(column: str) -> float:
        return round(
            sum(row.get(column, 0) for row in rows if isinstance(row.get(column), (int, float))),
            1,
        )

    minute = minute_from_time(time)
    items = [row.get("item", "") for row in rows if row.get("item")]
    return {
        "number": number,
        "time": time,
        "minute_of_day": minute,
        "label": label or ", ".join(items[:2]),
        "items": items,
        "carb_g": group_sum("carb_g"),
        "cal": group_sum("cal"),
        "protein_g": group_sum("protein_g"),
        "sat_g": group_sum("sat_g"),
    }


def minute_from_time(value: str) -> int | None:
    match = re.match(r"^(\d{1,2}):(\d{2})", value or "")
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def estimate_svg_text_width(text: str, font_size: int) -> float:
    return max(10.0, len(text) * font_size * 0.58 + 6)


def svg_rects_overlap(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> bool:
    return not (
        first[1] < second[0]
        or second[1] < first[0]
        or first[3] < second[2]
        or second[3] < first[2]
    )


def place_svg_label(
    text: str,
    ideal_x: float,
    y_lanes: list[float],
    min_x: float,
    max_x: float,
    occupied: list[tuple[float, float, float, float]],
    font_size: int = 11,
) -> tuple[float, float] | None:
    width = estimate_svg_text_width(text, font_size)
    x = min(max(ideal_x, min_x + width / 2), max_x - width / 2)
    for y in y_lanes:
        candidate = (x - width / 2, x + width / 2, y - font_size, y + 3)
        if not any(svg_rects_overlap(candidate, other) for other in occupied):
            occupied.append(candidate)
            return x, y
    return None


def local_peak_points(
    points: list[dict[str, Any]],
    window_minutes: int = 60,
    min_value: float = 6.0,
) -> list[dict[str, Any]]:
    peaks: list[dict[str, Any]] = []
    for point in points:
        point_value = parse_number(point.get("value"))
        point_minute = parse_number(point.get("minute_of_day"))
        if point_value is None or point_minute is None or point_value < min_value:
            continue
        blocked = False
        for other in points:
            if other is point:
                continue
            other_minute = parse_number(other.get("minute_of_day"))
            other_value = parse_number(other.get("value"))
            if other_minute is None or other_value is None:
                continue
            minutes_after_point = other_minute - point_minute
            if -window_minutes <= minutes_after_point < 0 and other_value >= point_value:
                blocked = True
                break
            if 0 < minutes_after_point <= window_minutes and other_value > point_value:
                blocked = True
                break
        if not blocked:
            peaks.append(point)
    return peaks


def render_meal_marker_list(meal_groups: list[dict[str, Any]]) -> str:
    if not meal_groups:
        return "<p class='small'>No logged meals for this day.</p>"
    items = []
    for group in meal_groups:
        items.append(
            "<li>"
            f"{escape(group.get('time', ''))} · "
            f"{fmt_int(group.get('carb_g'))} g carb · "
            f"{fmt_num(group.get('cal'))} cal"
            + (f" · {escape(group.get('label', ''))}" if group.get("label") else "")
            + "</li>"
        )
    return "<ul class='meal-markers'>" + "".join(items) + "</ul>"


def render_glucose_chart(
    points: list[dict[str, Any]], meal_groups: list[dict[str, Any]], title: str
) -> str:
    if not points:
        return f"<figure><figcaption>{escape(title)}</figcaption><p>No CGM points for this day.</p></figure>"

    width, height = 760, 270
    margin_left, margin_bottom, margin_top, margin_right = 44, 34, 20, 18
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    values = [float(point["value"]) for point in points]
    min_y = min(min(values), 3.9)
    max_y = max(max(values), 10.0)
    padding = max((max_y - min_y) * 0.08, 0.3)
    min_y -= padding
    max_y += padding

    def x_for_minute(minute: float) -> float:
        return margin_left + minute * plot_w / (24 * 60)

    def y_for(value: float) -> float:
        return margin_top + (max_y - value) * plot_h / (max_y - min_y)

    coords = [
        (x_for_minute(float(point["minute_of_day"])), y_for(float(point["value"])))
        for point in points
    ]
    path = " ".join(
        ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
        for index, (x, y) in enumerate(coords)
    )
    dots = "".join(
        f"<circle class='chart-dot' cx='{x:.1f}' cy='{y:.1f}' r='3' fill='#2f6f5e' />"
        for x, y in coords
    )
    target_top = y_for(10.0)
    target_bottom = y_for(3.9)
    occupied_labels: list[tuple[float, float, float, float]] = []
    peak_labels = []
    for point in local_peak_points(points):
        value = float(point["value"])
        x = x_for_minute(float(point["minute_of_day"]))
        y = y_for(value)
        peak_lanes = [
            max(margin_top + 12, y - 10),
            max(margin_top + 12, y - 24),
            min(margin_top + plot_h - 8, y + 18),
        ]
        label = fmt_num(value)
        placement = place_svg_label(
            label,
            x,
            peak_lanes,
            margin_left,
            width - margin_right,
            occupied_labels,
            font_size=11,
        )
        if placement:
            label_x, label_y = placement
            peak_labels.append(
                f"<text x='{label_x:.1f}' y='{label_y:.1f}' text-anchor='middle' font-size='11' fill='#1f2933' paint-order='stroke' stroke='#fff' stroke-width='3'>{escape(label)}</text>"
            )

    marker_lines = []
    meal_label_lanes = [margin_top + 12 + lane * 14 for lane in range(5)]
    for group in meal_groups:
        minute = group.get("minute_of_day")
        if minute is None:
            continue
        x = x_for_minute(float(minute))
        marker_lines.append(
            f"<line x1='{x:.1f}' y1='{margin_top}' x2='{x:.1f}' y2='{margin_top + plot_h}' stroke='#8b5e34' stroke-width='1.2' stroke-dasharray='4 4' />"
        )
        label = fmt_int(group.get("carb_g"))
        if label and label != "0":
            placement = place_svg_label(
                label,
                x,
                meal_label_lanes,
                margin_left,
                width - margin_right,
                occupied_labels,
            )
            if placement:
                label_x, label_y = placement
                marker_lines.append(
                    f"<text x='{label_x:.1f}' y='{label_y:.1f}' text-anchor='middle' font-size='11' fill='#8b5e34' paint-order='stroke' stroke='#fff' stroke-width='3'>{escape(label)}</text>"
                )
    hour_labels = []
    for hour in (0, 6, 12, 18, 24):
        x = x_for_minute(hour * 60)
        hour_labels.append(
            f"<text x='{x:.1f}' y='{height - 10}' text-anchor='middle' font-size='10'>{hour:02d}:00</text>"
        )
    return (
        f"<figure><figcaption>{escape(title)}</figcaption>"
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"
        f"<rect x='{margin_left}' y='{target_top:.1f}' width='{plot_w}' height='{target_bottom - target_top:.1f}' fill='#edf7ee' />"
        f"<line class='chart-axis' x1='{margin_left}' y1='{margin_top + plot_h}' x2='{width - margin_right}' y2='{margin_top + plot_h}' />"
        f"<line class='chart-axis' x1='{margin_left}' y1='{margin_top}' x2='{margin_left}' y2='{margin_top + plot_h}' />"
        f"<text x='8' y='{margin_top + 6}' font-size='10'>{fmt_num(max_y)}</text>"
        f"<text x='8' y='{margin_top + plot_h}' font-size='10'>{fmt_num(min_y)}</text>"
        + "".join(marker_lines)
        + f"<path class='chart-line' d='{path}' stroke='#2f6f5e' />"
        + dots
        + "".join(peak_labels)
        + "".join(hour_labels)
        + "</svg></figure>"
    )


def meal_item_html(row: dict[str, Any]) -> str:
    if row.get("kind") != "item":
        return escape(row.get("item", ""))
    link = row.get("link", {})
    if link.get("href"):
        label = link.get("label") if link.get("kind") == "batch" else row.get("item", "")
        return f"<a href='{escape(link['href'])}'>{escape(label)}</a>"
    return escape(row.get("item", ""))


def render_lab_charts(entries: list[dict[str, Any]]) -> str:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        # Inequalities and qualitative results remain in the table, not plotted as exact values.
        if not re.fullmatch(r"-?\d+(?:[.,]\d+)?", entry["result_text"].strip()):
            continue
        groups.setdefault((entry["test_norm"], entry["units"]), []).append(entry)
    return "".join(render_line_chart(points, f"{test} ({unit})", "#2f6f5e")
                   for (test, unit), points in sorted(groups.items()))


def render_lab_table(entries: list[dict[str, Any]]) -> str:
    selected = entries
    rows = []
    for entry in selected:
        rows.append(
            f"<tr id='{escape(entry['id'])}'>"
            f"<td class='text'>{escape(entry['date'])}</td>"
            f"<td class='text'>{escape(entry['test_norm'])}</td>"
            f"<td>{escape(entry['result_text'])}</td>"
            f"<td class='text'>{escape(entry['units'])}</td>"
            f"<td class='text'>{escape(entry.get('reference_range', ''))}</td>"
            f"<td class='text'>{escape(entry.get('flag', ''))}</td>"
            f"<td class='text small'>{escape(entry.get('note', ''))}</td>"
            "</tr>"
        )
    return (
        "<h3>Lab Values</h3>"
        "<table><thead><tr><th>Date</th><th>Test</th><th>Result</th><th>Units</th>"
        "<th>Reference range</th><th>Flag</th><th>Note</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_appointment_notes(appointments: dict[str, Any]) -> str:
    body = appointments.get("body", "")
    if not body:
        return "<p>No appointment notes found.</p>"

    chunks: list[str] = []
    in_list = False
    in_item = False

    def close_item() -> None:
        nonlocal in_item
        if in_item:
            chunks.append("</li>")
            in_item = False

    def close_list() -> None:
        nonlocal in_list
        close_item()
        if in_list:
            chunks.append("</ul>")
            in_list = False

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if line.startswith("#+"):
            continue
        if not stripped:
            close_list()
            continue

        heading = re.match(r"^(\*+)\s+(.*)$", line)
        if heading:
            close_list()
            level = len(heading.group(1))
            tag = "h3" if level == 1 else "h4" if level == 2 else "h5"
            chunks.append(f"<{tag}>{render_org_inline(heading.group(2).strip())}</{tag}>")
            continue

        if line.startswith("- "):
            if not in_list:
                chunks.append("<ul>")
                in_list = True
            close_item()
            chunks.append(f"<li>{render_org_inline(line[2:].strip())}")
            in_item = True
            continue

        if in_item and raw_line.startswith("  "):
            chunks.append(" " + render_org_inline(stripped))
            continue

        close_list()
        chunks.append(f"<p>{render_org_inline(stripped)}</p>")

    close_list()
    return "<div class='org-notes'>" + "".join(chunks) + "</div>"


def render_org_inline(value: str) -> str:
    escaped = escape(value)
    return re.sub(r"=([^=]+)=", r"<code>\1</code>", escaped)


def render_validation(validation: dict[str, Any]) -> str:
    warnings = validation.get("warnings", [])
    if not warnings:
        return "<p>No validation warnings.</p>"
    rows = []
    for warning in warnings:
        rows.append(
            "<tr>"
            f"<td class='text'>{escape(warning.get('kind', 'warning'))}</td>"
            f"<td class='text'>{escape(warning.get('date', warning.get('food', '')))}</td>"
            f"<td class='text'>{escape(warning.get('item', warning.get('product', '')))}</td>"
            f"<td class='text small'>{escape(json.dumps(warning, sort_keys=True))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Kind</th><th>Date/Food</th><th>Item/Product</th>"
        "<th>Detail</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_bar_chart(
    daily_totals: list[dict[str, Any]], metric: str, title: str, color: str
) -> str:
    points = [
        {"date": row["date"], "value": parse_number(row.get(metric))}
        for row in sorted(daily_totals, key=lambda item: item["date"])
    ]
    points = [point for point in points if point["value"] is not None]
    if not points:
        return f"<figure><figcaption>{escape(title)}</figcaption><p>No data.</p></figure>"

    width, height = 520, 210
    margin_left, margin_bottom, margin_top, margin_right = 42, 34, 16, 14
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    max_value = max(point["value"] for point in points) or 1
    bar_gap = 10
    bar_w = max(18, (plot_w - bar_gap * (len(points) - 1)) / len(points))
    bars = []
    labels = []
    for index, point in enumerate(points):
        x = margin_left + index * (bar_w + bar_gap)
        h = plot_h * point["value"] / max_value
        y = margin_top + plot_h - h
        bars.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{h:.1f}' fill='{color}' rx='3' />"
            f"<text x='{x + bar_w / 2:.1f}' y='{y - 5:.1f}' text-anchor='middle' font-size='11'>{fmt_num(point['value'])}</text>"
        )
        label_x = inset_label_x(index, len(points), x + bar_w / 2, width)
        labels.append(
            f"<text x='{label_x:.1f}' y='{height - 10}' text-anchor='middle' font-size='10'>{escape(point['date'][5:])}</text>"
        )
    return (
        f"<figure><figcaption>{escape(title)}</figcaption>"
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"
        f"<line class='chart-axis' x1='{margin_left}' y1='{margin_top + plot_h}' x2='{width - margin_right}' y2='{margin_top + plot_h}' />"
        f"<line class='chart-axis' x1='{margin_left}' y1='{margin_top}' x2='{margin_left}' y2='{margin_top + plot_h}' />"
        + "".join(bars)
        + "".join(labels)
        + "</svg></figure>"
    )


def render_line_chart(points: list[dict[str, Any]], title: str, color: str) -> str:
    if not points:
        return f"<figure><figcaption>{escape(title)}</figcaption><p>No data.</p></figure>"

    width, height = 520, 230
    margin_left, margin_bottom, margin_top, margin_right = 46, 36, 18, 18
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    values = [float(point["value"]) for point in points]
    min_y, max_y = min(values), max(values)
    if math.isclose(min_y, max_y):
        min_y -= 1
        max_y += 1
    padding = (max_y - min_y) * 0.12
    min_y -= padding
    max_y += padding

    def x_for(index: int) -> float:
        if len(points) == 1:
            return margin_left + plot_w / 2
        return margin_left + index * plot_w / (len(points) - 1)

    def y_for(value: float) -> float:
        return margin_top + (max_y - value) * plot_h / (max_y - min_y)

    coords = [(x_for(index), y_for(float(point["value"]))) for index, point in enumerate(points)]
    path = " ".join(
        ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
        for index, (x, y) in enumerate(coords)
    )
    dots = []
    labels = []
    for index, ((x, y), point) in enumerate(zip(coords, points)):
        dots.append(
            f"<circle class='chart-dot' cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{color}' />"
            f"<text x='{x:.1f}' y='{y - 8:.1f}' text-anchor='middle' font-size='11'>{fmt_num(point['value'])}</text>"
        )
        label_x = inset_label_x(index, len(points), x, width)
        labels.append(
            f"<text x='{label_x:.1f}' y='{height - 10}' text-anchor='middle' font-size='10'>{escape(point['date'][2:])}</text>"
        )
    return (
        f"<figure><figcaption>{escape(title)}</figcaption>"
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"
        f"<line class='chart-axis' x1='{margin_left}' y1='{margin_top + plot_h}' x2='{width - margin_right}' y2='{margin_top + plot_h}' />"
        f"<line class='chart-axis' x1='{margin_left}' y1='{margin_top}' x2='{margin_left}' y2='{margin_top + plot_h}' />"
        f"<text x='8' y='{margin_top + 6}' font-size='10'>{fmt_num(max_y)}</text>"
        f"<text x='8' y='{margin_top + plot_h}' font-size='10'>{fmt_num(min_y)}</text>"
        f"<path class='chart-line' d='{path}' stroke='{color}' />"
        + "".join(dots)
        + "".join(labels)
        + "</svg></figure>"
    )


def inset_label_x(index: int, count: int, x: float, width: int) -> float:
    # iOS Quick Look has been unreliable with edge-anchored SVG text. Keep
    # labels visibly inside the viewbox even if text-anchor is rendered oddly.
    edge_inset = 66
    if count <= 1:
        return x
    if index == 0:
        return max(x, edge_inset)
    if index == count - 1:
        return min(x, width - edge_inset)
    return x


def write_outputs(data: dict[str, Any], repo: Path) -> tuple[Path, Path]:
    json_path = repo_path(repo, "data", "processed", "site-data.json")
    site_dir = repo_path(repo, "exports", "site")
    site_path = site_dir / "index.html"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    site_path.write_text(render_site(data), encoding="utf-8")
    return json_path, site_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.home() / "health-notebook")
    parser.add_argument("--strict", action="store_true", help="exit nonzero on validation warnings")
    parser.add_argument("--today", help="Override today (YYYY-MM-DD) for reproducible demos")
    args = parser.parse_args(argv)

    data = build_data(args.repo, today=args.today)
    json_path, site_path = write_outputs(data, args.repo)
    warning_count = data["validation"]["summary"]["warning_count"]
    print(f"Wrote {json_path.relative_to(args.repo)}")
    print(f"Wrote {site_path.relative_to(args.repo)}")
    print(f"Validation warnings: {warning_count}")
    if args.strict and warning_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
