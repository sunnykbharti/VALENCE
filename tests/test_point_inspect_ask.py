"""Unit tests for Point, Inspect, Ask feature (User-selected region inspection)."""

import unittest
from pathlib import Path

from PIL import Image

from contracts import CropInspectionResult
from src.ui.mock_backend import MockBackendService
from src.utils.image_crop import crop_image_region, draw_user_region_overlay


class TestPointInspectAsk(unittest.TestCase):
    def setUp(self):
        self.fixture_image = Path("tests/fixtures/synthetic_plc_leds_normal.png")
        self.blurry_image = Path("tests/fixtures/synthetic_blurry_panel.png")

    def test_crop_image_region_valid(self):
        crop_path, crop_id, coords = crop_image_region(
            self.fixture_image,
            box_pct=(10.0, 20.0, 80.0, 60.0),
        )
        self.assertTrue(crop_path.exists())
        self.assertTrue(crop_id.startswith("img_crop_"))
        px1, py1, px2, py2 = coords
        self.assertLess(px1, px2)
        self.assertLess(py1, py2)

        # Verify cropped image dimensions
        with Image.open(crop_path) as cropped:
            self.assertEqual(cropped.size, (px2 - px1, py2 - py1))

    def test_crop_image_region_invalid_ranges(self):
        # x_min >= x_max
        with self.assertRaises(ValueError):
            crop_image_region(self.fixture_image, (50.0, 10.0, 50.0, 90.0))

        # y_min >= y_max
        with self.assertRaises(ValueError):
            crop_image_region(self.fixture_image, (10.0, 80.0, 50.0, 20.0))

        # Out of bounds (> 100)
        with self.assertRaises(ValueError):
            crop_image_region(self.fixture_image, (10.0, 20.0, 105.0, 80.0))

        # Out of bounds (< 0)
        with self.assertRaises(ValueError):
            crop_image_region(self.fixture_image, (-5.0, 20.0, 50.0, 80.0))

    def test_draw_user_region_overlay(self):
        annotated = draw_user_region_overlay(
            self.fixture_image,
            box_pct=(15.0, 25.0, 75.0, 65.0),
        )
        self.assertIsInstance(annotated, Image.Image)
        with Image.open(self.fixture_image) as orig:
            self.assertEqual(annotated.size, orig.size)

    def test_mock_backend_inspect_crop_normal(self):
        backend = MockBackendService()
        result, crop_path = backend.inspect_crop(
            self.fixture_image,
            box_pct=(10.0, 20.0, 80.0, 50.0),
        )
        self.assertIsInstance(result, CropInspectionResult)
        self.assertTrue(crop_path.exists())
        self.assertTrue(len(result.tentative_observations) > 0)
        self.assertFalse(result.unreadable_text_noted)
        self.assertIn("S7-1200", result.legible_text)

    def test_mock_backend_inspect_crop_blurry_uncertainty(self):
        backend = MockBackendService()
        result, crop_path = backend.inspect_crop(
            self.blurry_image,
            box_pct=(10.0, 10.0, 90.0, 90.0),
        )
        self.assertIsInstance(result, CropInspectionResult)
        self.assertTrue(result.unreadable_text_noted)
        self.assertIsNotNone(result.follow_up_needed)
        self.assertIn("sharper", result.follow_up_needed.lower())


if __name__ == "__main__":
    unittest.main()
