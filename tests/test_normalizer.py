"""Tests for Windows-target path normalization (pure stdlib, no deps)."""

from __future__ import annotations

import unittest

from app.normalizer import (
    ABSOLUTE_PATH,
    DRIVE_LETTER_PATH,
    EMPTY_SEGMENT,
    PARENT_ESCAPE,
    RESERVED_DEVICE_NAME,
    normalize_path,
)


class SeparatorTests(unittest.TestCase):
    def test_forward_and_backslashes_unify(self):
        self.assertEqual(normalize_path("a/b/c.txt").canonical_path, "a\\b\\c.txt")
        self.assertEqual(normalize_path("a\\b\\c.txt").canonical_path, "a\\b\\c.txt")
        self.assertEqual(normalize_path("a/b\\c.txt").canonical_path, "a\\b\\c.txt")

    def test_duplicate_separators_collapse(self):
        self.assertEqual(normalize_path("a//b\\\\c").canonical_path, "a\\b\\c")


class CaseAndUnicodeTests(unittest.TestCase):
    def test_case_is_folded(self):
        self.assertEqual(normalize_path("Foo\\BAR.Txt").canonical_path, "foo\\bar.txt")

    def test_nfc_normalization(self):
        nfd = "café.txt"  # e + combining acute
        nfc = "café.txt"  # precomposed
        self.assertEqual(normalize_path(nfd).canonical_path, normalize_path(nfc).canonical_path)
        self.assertEqual(normalize_path(nfd).canonical_path, nfc.casefold())


class TrailingStripTests(unittest.TestCase):
    def test_trailing_dots_and_spaces_stripped(self):
        self.assertEqual(normalize_path("dir ./file .txt").canonical_path, "dir\\file .txt")
        self.assertEqual(normalize_path("name.../").canonical_path, "name")
        self.assertEqual(normalize_path("a  \\b  ").canonical_path, "a\\b")

    def test_segment_of_only_dots_is_flagged(self):
        result = normalize_path("a/.../b")
        self.assertIn(EMPTY_SEGMENT, result.issues)
        self.assertEqual(result.canonical_path, "a\\b")


class DotSegmentTests(unittest.TestCase):
    def test_current_dir_segments_dropped(self):
        self.assertEqual(normalize_path("./a/./b").canonical_path, "a\\b")

    def test_in_bounds_parent_resolves(self):
        self.assertEqual(normalize_path("a/../b").canonical_path, "b")
        self.assertEqual(normalize_path("a/b/../../c").canonical_path, "c")

    def test_out_of_bounds_parent_is_unsafe(self):
        for raw in ("..", "../a", "a/../../b", "..\\..\\win"):
            with self.subTest(raw=raw):
                result = normalize_path(raw)
                self.assertFalse(result.safe)
                self.assertIn(PARENT_ESCAPE, result.issues)
                self.assertIsNone(result.canonical_path)


class UnsafePrefixTests(unittest.TestCase):
    def test_absolute_paths_are_unsafe(self):
        for raw in ("/etc/passwd", "\\temp\\x", "\\\\server\\share\\f"):
            with self.subTest(raw=raw):
                result = normalize_path(raw)
                self.assertFalse(result.safe)
                self.assertIn(ABSOLUTE_PATH, result.issues)

    def test_absolute_path_still_reports_canonical_remainder(self):
        self.assertEqual(normalize_path("/a/b.txt").canonical_path, "a\\b.txt")
        self.assertEqual(normalize_path("\\\\server\\share").canonical_path, "server\\share")

    def test_drive_letter_paths_are_unsafe(self):
        for raw in ("C:\\Windows\\x", "c:/temp", "D:relative"):
            with self.subTest(raw=raw):
                result = normalize_path(raw)
                self.assertFalse(result.safe)
                self.assertIn(DRIVE_LETTER_PATH, result.issues)

    def test_drive_path_still_reports_canonical_remainder(self):
        self.assertEqual(normalize_path("C:\\a\\B.txt").canonical_path, "a\\b.txt")


class ReservedDeviceNameTests(unittest.TestCase):
    def test_device_names_flagged_in_any_position(self):
        for raw in ("CON", "con.txt", "AUX", "nul .dat", "COM1", "com9.log",
                    "LPT3", "a/NUL/b", "dir/prn/file"):
            with self.subTest(raw=raw):
                result = normalize_path(raw)
                self.assertIn(RESERVED_DEVICE_NAME, result.issues)

    def test_non_device_names_not_flagged(self):
        for raw in ("console.txt", "com10", "lpt0", "auxiliary", "co.txt"):
            with self.subTest(raw=raw):
                self.assertNotIn(RESERVED_DEVICE_NAME, normalize_path(raw).issues)

    def test_device_name_does_not_affect_safe_flag(self):
        # Only absolute/drive/escape paths are unsafe per the contract.
        self.assertTrue(normalize_path("CON").safe)


class SafetyContractTests(unittest.TestCase):
    def test_plain_relative_path_is_safe(self):
        result = normalize_path("folder/sub/file.txt")
        self.assertTrue(result.safe)
        self.assertEqual(result.issues, [])

    def test_safe_is_exactly_the_three_unsafe_categories(self):
        self.assertFalse(normalize_path("/x").safe)
        self.assertFalse(normalize_path("C:/x").safe)
        self.assertFalse(normalize_path("../x").safe)


if __name__ == "__main__":
    unittest.main()
