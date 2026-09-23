import json
import tempfile
import unittest
from pathlib import Path

from .build_site import (
    REPO_ROOT,
    build_data,
    local_peak_points,
    parse_meals,
    render_site,
)
from .meal_rows import classify_meal_row
from .org_tables import parse_org_tables


class OrgTableParserTest(unittest.TestCase):
    def test_preserves_heading_context_source_and_line_numbers(self):
        content = "\n".join(
            [
                "* 2026-01-01",
                "** Nutrition",
                "",
                "| Item | Cal |",
                "|------+-----|",
                "| Skyr | 100 |",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "meal-log.org"
            path.write_text(content, encoding="utf-8")
            tables = parse_org_tables(path, root)

        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].source, "meal-log.org")
        self.assertEqual(tables[0].start_line, 4)
        self.assertEqual(tables[0].headings, ("2026-01-01", "Nutrition"))
        self.assertEqual(tables[0].rows, ({"Item": "Skyr", "Cal": "100"},))


class SyntheticRegressionTest(unittest.TestCase):
    def test_meal_row_classification_is_explicit_and_qualifier_safe(self):
        cases = {
            "Skyr": "item",
            "Subtotal": "subtotal",
            "Subtotal (to flight)": "subtotal",
            "Day total": "day_total",
            "Day total (estimated)": "day_total",
            "Day so far": "running_total_reported",
            "Day so far (before dinner)": "running_total_reported",
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(classify_meal_row(label), expected)

    def test_day_so_far_running_total_is_single_counted(self):
        # Synthetic in-progress day (a "Day so far" row plus a qualified
        # "Subtotal (to flight)" marker). Built as a fixture rather than pinned
        # to a live date, whose "Day so far" row becomes "Day total" once the
        # day is closed out. If the parser recounted either marker as a food
        # item, the computed running total would exceed the two real items.
        content = "\n".join(
            [
                "* 2026-01-01",
                "",
                "*** Nutrition accounting",
                "",
                "|  Time | Item | Wt. | Carb | Cal | Fat | Prot. | Sat. | Notes |",
                "|-------+------+-----+------+-----+-----+-------+------+-------|",
                "| 08:00 | Eggs | 100 | 1.0 | 150 | 10.0 | 12.0 | 3.0 | a |",
                "| 09:00 | Toast | 50 | 20.0 | 120 | 2.0 | 4.0 | 0.5 | b |",
                "|-------+------+-----+------+-----+-----+-------+------+-------|",
                "|  | Subtotal | 150 | 21.0 | 270 | 12.0 | 16.0 | 3.5 | c |",
                "|  | Subtotal (to flight) | 150 | 21.0 | 270 | 12.0 | 16.0 | 3.5 | d |",
                "|  | Day so far | 150 | 21.0 | 270 | 12.0 | 16.0 | 3.5 | e |",
                "",
            ]
        )
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            repo = Path(tmp)
            (repo / "meal-log.org").write_text(content, encoding="utf-8")
            parsed = parse_meals(repo, {}, set())

        day = next(d for d in parsed["days"] if d["date"] == "2026-01-01")
        self.assertIsNone(day["day_total"])
        # Only the two real food rows are items; markers are excluded.
        item_names = [r["item"] for r in day["items"] if r.get("kind") == "item"]
        self.assertEqual(item_names, ["Eggs", "Toast"])
        # Computed running total = just Eggs + Toast, not tripled by the markers.
        computed = day["running_total"]
        self.assertAlmostEqual(computed["protein_g"], 16.0, places=1)
        self.assertAlmostEqual(computed["carb_g"], 21.0, places=1)
        # The hand-entered "Day so far" row is captured but not summed as food.
        reported = day.get("reported_running_total")
        self.assertIsNotNone(reported)
        self.assertAlmostEqual(reported["protein_g"], 16.0, places=1)

    def test_local_peak_points_use_leftmost_tied_peak(self):
        points = [
            {"minute_of_day": 600, "value": 7.0},
            {"minute_of_day": 620, "value": 7.0},
            {"minute_of_day": 650, "value": 6.8},
            {"minute_of_day": 700, "value": 7.1},
        ]

        self.assertEqual(local_peak_points(points, window_minutes=60), [points[0], points[3]])

class PortableDashboardTest(unittest.TestCase):
    def test_empty_notebook_builds_without_glucose(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = build_data(Path(tmp))
            page = render_site(data)
        self.assertIn('Health Notebook', page)
        self.assertNotIn('id="glucose"', page)
        self.assertEqual(data['validation']['summary']['warning_count'], 0)

    def test_fictional_notebook_targets_weight_labs_and_links(self):
        data = build_data(REPO_ROOT / 'examples/notebook', today='2026-01-15')
        self.assertEqual(data['validation']['summary']['warning_count'], 0)
        self.assertEqual(data['meals']['days'][-1]['running_total']['protein_g'], 43)
        self.assertEqual(data['weight'][-1]['value'], 71.8)
        self.assertEqual(data['labs']['entries'][0]['reference_range'], '8–20')
        self.assertEqual(data['batches']['batches'][0]['summary']['cal_per_100g'], 100)
        page = render_site(data)
        self.assertIn('47 g to target', page)
        self.assertIn('Example assay', page)
        self.assertIn('Body weight (kg)', page)
        self.assertIn('food-example-yoghurt', page)

    def test_initialized_template_builds(self):
        data = build_data(REPO_ROOT / 'notebook-template')
        self.assertEqual(data['targets']['targets'], [])
        self.assertEqual(data['foods']['products'], [])
        self.assertIn('Health Notebook', render_site(data))

    def test_glucose_archive_adds_optional_section(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'HEALTH_NOTEBOOK_TZ': 'UTC'}):
            raw = Path(tmp)
            (raw / 'graph-20260115T120000Z.json').write_text(json.dumps([
                {'timestamp': '2026-01-15T12:00:00', 'factory_timestamp': '2026-01-15T12:00:00Z',
                 'value': 5.5, 'value_in_mg_per_dl': 99}]))
            data = build_data(REPO_ROOT / 'examples/notebook', today='2026-01-15', glucose_dir=raw)
        self.assertEqual(data['glucose']['point_count'], 1)
        self.assertIn('id="glucose"', render_site(data))

    def test_notes_escape_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / 'appointment-questions.org').write_text('* <script>alert(1)</script>')
            page = render_site(build_data(repo))
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;', page)
