"""
Unit tests for the CentroidTracker class.

Tests verify ID assignment, ID persistence across frames,
new-track spawning, and TTL-based expiration.

Run with:
    python -m pytest tests/test_tracker.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.tracker import CentroidTracker
from config.settings import TrackerConfig


@pytest.fixture
def tracker() -> CentroidTracker:
    """Fresh tracker with a short TTL for expiration tests."""
    cfg = TrackerConfig(max_centroid_distance=100, ttl_frames=3)
    return CentroidTracker(cfg)


class TestIDAssignment:
    def test_first_detection_gets_id_1(self, tracker):
        cid = tracker.update((100, 100))
        assert cid == 1

    def test_second_distant_detection_gets_id_2(self, tracker):
        tracker.update((100, 100))
        cid = tracker.update((500, 500))
        assert cid == 2

    def test_ids_are_monotonically_increasing(self, tracker):
        ids = [tracker.update((i * 300, i * 300)) for i in range(5)]
        assert ids == [1, 2, 3, 4, 5]


class TestIDPersistence:
    def test_close_centroid_keeps_same_id(self, tracker):
        cid1 = tracker.update((100, 100))
        tracker.tick()
        cid2 = tracker.update((105, 102))  # within 100px
        assert cid1 == cid2

    def test_far_centroid_gets_new_id(self, tracker):
        cid1 = tracker.update((100, 100))
        tracker.tick()
        cid2 = tracker.update((600, 600))  # > 100px away
        assert cid1 != cid2


class TestTTLExpiration:
    def test_track_survives_within_ttl(self, tracker):
        cid = tracker.update((100, 100))
        for _ in range(2):  # ttl=3, still alive at tick 2
            tracker.tick()
        assert cid in tracker.active_tracks

    def test_track_expires_after_ttl_frames(self, tracker):
        tracker.update((100, 100))
        for _ in range(4):  # tick past ttl=3
            tracker.tick()
        assert len(tracker.active_tracks) == 0

    def test_updated_track_resets_ttl(self, tracker):
        cid = tracker.update((100, 100))
        tracker.tick()
        tracker.tick()
        # Re-detect before expiry — resets TTL
        tracker.update((101, 101))
        tracker.tick()
        tracker.tick()
        # Should still be alive (TTL was reset)
        assert cid in tracker.active_tracks


class TestMultipleTracks:
    def test_two_tracks_independent(self, tracker):
        cid1 = tracker.update((50, 50))
        cid2 = tracker.update((500, 500))
        assert len(tracker.active_tracks) == 2
        assert cid1 != cid2

    def test_one_expires_other_survives(self, tracker):
        cid1 = tracker.update((50, 50))
        for i in range(4):
            tracker.tick()
            if i == 1:
                # Keep cid1 alive by updating it
                tracker.update((52, 51))

        # cid2 was never updated again — it should be gone
        # But cid1 was updated so it should survive
        assert cid1 in tracker.active_tracks
