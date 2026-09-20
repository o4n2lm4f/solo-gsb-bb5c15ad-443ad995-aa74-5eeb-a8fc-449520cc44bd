"""Tests for collision groups and hierarchy conflicts (pure stdlib)."""

from __future__ import annotations

import unittest

from app.analysis import find_collisions, find_hierarchy_conflicts
from app.normalizer import normalize_path


def _canonical(raw_paths):
    """Normalize raw paths the way the API does before analysis."""
    return [normalize_path(p).canonical_path for p in raw_paths]


class CollisionTests(unittest.TestCase):
    def test_case_and_separator_variants_collide(self):
        paths = _canonical(["Foo\\bar.txt", "foo/BAR.txt", "other.txt"])
        collisions = find_collisions(paths)
        self.assertEqual(
            collisions,
            [{"canonical_path": "foo\\bar.txt", "indices": [0, 1]}],
        )

    def test_no_collisions(self):
        self.assertEqual(find_collisions(_canonical(["a", "b", "c"])), [])

    def test_multiple_groups_ordered_by_first_occurrence(self):
        paths = _canonical(["b", "A", "a", "B", "c"])
        collisions = find_collisions(paths)
        self.assertEqual(
            collisions,
            [
                {"canonical_path": "b", "indices": [0, 3]},
                {"canonical_path": "a", "indices": [1, 2]},
            ],
        )

    def test_none_paths_never_collide(self):
        self.assertEqual(find_collisions([None, None, "a"]), [])


class HierarchyConflictTests(unittest.TestCase):
    def test_file_blocking_descendants(self):
        types = ["file", "file", "directory"]
        paths = ["a", "a\\b.txt", "a\\sub"]
        conflicts = find_hierarchy_conflicts(types, paths)
        self.assertEqual(
            conflicts,
            [{"file_index": 0, "canonical_path": "a", "blocked_indices": [1, 2]}],
        )

    def test_directory_ancestor_is_not_a_conflict(self):
        types = ["directory", "file"]
        paths = ["a", "a\\b.txt"]
        self.assertEqual(find_hierarchy_conflicts(types, paths), [])

    def test_same_path_is_collision_not_hierarchy(self):
        types = ["file", "file"]
        paths = ["a", "a"]
        self.assertEqual(find_hierarchy_conflicts(types, paths), [])

    def test_prefix_must_match_segment_boundary(self):
        types = ["file", "file"]
        paths = ["ab", "ab-c\\d.txt"]
        self.assertEqual(find_hierarchy_conflicts(types, paths), [])

    def test_multiple_blocking_files_in_input_order(self):
        types = ["file", "file", "file"]
        paths = ["x", "y", "x\\z"]
        conflicts = find_hierarchy_conflicts(types, paths)
        self.assertEqual(
            conflicts,
            [{"file_index": 0, "canonical_path": "x", "blocked_indices": [2]}],
        )

    def test_none_canonical_paths_ignored(self):
        types = ["file", "file"]
        paths = [None, "a\\b"]
        self.assertEqual(find_hierarchy_conflicts(types, paths), [])


if __name__ == "__main__":
    unittest.main()
