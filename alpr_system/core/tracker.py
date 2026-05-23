"""
Centroid-based vehicle tracker.

Responsibility: Maintain consistent numeric IDs across video frames by
associating each new detection with an existing track (or spawning a new
one) based on Euclidean distance between centroids.

This is a classic "Hungarian-free" tracker suitable for sparse,
well-separated objects such as vehicles passing through a camera
field-of-view. For dense or occluded scenarios a full IoU/Hungarian
tracker (e.g. SORT) should be substituted here without any changes
to the rest of the pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np
from scipy.spatial import distance as dist

from config.settings import TrackerConfig, DEFAULT_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)

Centroid = Tuple[int, int]


@dataclass
class Track:
    """
    Runtime state associated with a single tracked vehicle.

    Attributes:
        car_id: Unique integer identifier assigned at track creation.
        centroid: Most recent (cx, cy) position.
        ttl: Time-to-live counter in frames. Decremented each frame;
             the track is removed when it reaches zero.
    """
    car_id: int
    centroid: Centroid
    ttl: int


class CentroidTracker:
    """
    Associates detections across frames using minimum-distance matching.

    Matching algorithm:
      1. Compute pairwise Euclidean distances between all active track
         centroids and the new detection centroid.
      2. If the nearest track is within ``max_centroid_distance`` pixels,
         update that track.
      3. Otherwise, create a new track.

    TTL management:
      Tracks that are not updated in a given frame have their TTL
      decremented. Tracks whose TTL reaches zero are pruned.

    Args:
        config: Tracker hyperparameters. Defaults to system defaults.
    """

    def __init__(self, config: TrackerConfig = DEFAULT_CONFIG.tracker):
        self._cfg = config
        self._tracks: Dict[int, Track] = {}
        self._next_id: int = 1
        logger.debug("CentroidTracker initialised with config: %s", config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, centroid: Centroid) -> int:
        """
        Register a new detection centroid and return a stable track ID.

        Args:
            centroid: (cx, cy) pixel position of the detected region.

        Returns:
            The integer car_id of the matched or newly created track.
        """
        matched_id = self._match_to_existing(centroid)
        if matched_id is not None:
            self._tracks[matched_id].centroid = centroid
            self._tracks[matched_id].ttl = self._cfg.ttl_frames
            return matched_id

        return self._create_track(centroid)

    def tick(self) -> None:
        """
        Advance one frame: decrement TTL counters and prune expired tracks.

        Must be called exactly once per processed frame, before calling
        ``update`` for any detections in that frame.
        """
        expired = [
            tid for tid, t in self._tracks.items() if t.ttl <= 0
        ]
        for tid in expired:
            logger.debug("Track %d expired — removing.", tid)
            del self._tracks[tid]

        for track in self._tracks.values():
            track.ttl -= 1

    @property
    def active_tracks(self) -> Dict[int, Track]:
        """Read-only view of all currently active tracks."""
        return dict(self._tracks)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _match_to_existing(self, centroid: Centroid) -> Optional[int]:
        """
        Find the nearest existing track within the max-distance threshold.

        Returns the track id on success, None if no suitable match exists.
        """
        if not self._tracks:
            return None

        track_ids = list(self._tracks.keys())
        existing_centroids = np.array(
            [self._tracks[tid].centroid for tid in track_ids]
        )
        distances = dist.cdist(existing_centroids, [centroid])
        nearest_idx = int(distances.argmin())
        nearest_dist = float(distances[nearest_idx][0])

        if nearest_dist < self._cfg.max_centroid_distance:
            return track_ids[nearest_idx]
        return None

    def _create_track(self, centroid: Centroid) -> int:
        """Spawn a new track and return its id."""
        new_id = self._next_id
        self._tracks[new_id] = Track(
            car_id=new_id,
            centroid=centroid,
            ttl=self._cfg.ttl_frames,
        )
        self._next_id += 1
        logger.info("New track created — ID %d at centroid %s.", new_id, centroid)
        return new_id
