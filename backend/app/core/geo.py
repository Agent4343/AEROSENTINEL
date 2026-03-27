"""Geospatial utilities for drone operations and detection geo-referencing."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

EARTH_RADIUS_M = 6_371_000.0


def _deg2rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _rad2deg(rad: float) -> float:
    return rad * 180.0 / math.pi


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return the great-circle distance in **metres** between two WGS-84 points."""
    rlat1, rlon1, rlat2, rlon2 = map(_deg2rad, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def destination_point(
    lat: float, lon: float, bearing_deg: float, distance_m: float
) -> Tuple[float, float]:
    """Compute the destination point given a start, bearing (degrees), and distance (metres)."""
    rlat = _deg2rad(lat)
    rlon = _deg2rad(lon)
    rb = _deg2rad(bearing_deg)
    angular = distance_m / EARTH_RADIUS_M

    dest_lat = math.asin(
        math.sin(rlat) * math.cos(angular)
        + math.cos(rlat) * math.sin(angular) * math.cos(rb)
    )
    dest_lon = rlon + math.atan2(
        math.sin(rb) * math.sin(angular) * math.cos(rlat),
        math.cos(angular) - math.sin(rlat) * math.sin(dest_lat),
    )
    return _rad2deg(dest_lat), _rad2deg(dest_lon)


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return initial bearing in degrees from point 1 to point 2."""
    rlat1, rlon1, rlat2, rlon2 = map(_deg2rad, (lat1, lon1, lat2, lon2))
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (_rad2deg(math.atan2(x, y)) + 360.0) % 360.0


@dataclass
class GeoPoint:
    lat: float
    lon: float
    altitude: float = 0.0


def generate_expanding_square(
    center_lat: float,
    center_lon: float,
    spacing_m: float,
    legs: int,
) -> List[Tuple[float, float]]:
    """Generate an expanding-square search pattern."""
    points: List[Tuple[float, float]] = [(center_lat, center_lon)]
    bearing = 0.0
    current_lat, current_lon = center_lat, center_lon

    for leg_idx in range(1, legs + 1):
        leg_distance = spacing_m * ((leg_idx + 1) // 2)
        steps = max(1, int(leg_distance / spacing_m))
        for _ in range(steps):
            current_lat, current_lon = destination_point(
                current_lat, current_lon, bearing, spacing_m
            )
            points.append((current_lat, current_lon))
        bearing = (bearing + 90.0) % 360.0

    return points


@dataclass
class GeoBounds:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


def generate_parallel_tracks(
    bounds: GeoBounds,
    spacing_m: float,
    altitude: float,
) -> List[GeoPoint]:
    """Generate parallel east-west tracks covering a bounding box."""
    points: List[GeoPoint] = []
    current_lat = bounds.min_lat
    track_index = 0

    while current_lat <= bounds.max_lat:
        if track_index % 2 == 0:
            points.append(GeoPoint(current_lat, bounds.min_lon, altitude))
            points.append(GeoPoint(current_lat, bounds.max_lon, altitude))
        else:
            points.append(GeoPoint(current_lat, bounds.max_lon, altitude))
            points.append(GeoPoint(current_lat, bounds.min_lon, altitude))

        current_lat, _ = destination_point(current_lat, bounds.min_lon, 0.0, spacing_m)
        track_index += 1

    return points


def generate_sector_search(
    center_lat: float,
    center_lon: float,
    radius_m: float,
    sectors: int = 3,
) -> List[Tuple[float, float]]:
    """Generate a sector-search pattern (radial legs from centre)."""
    points: List[Tuple[float, float]] = []
    sector_angle = 360.0 / sectors

    for i in range(sectors):
        start_bearing = i * sector_angle
        end_bearing = start_bearing + sector_angle

        points.append((center_lat, center_lon))
        edge_lat, edge_lon = destination_point(
            center_lat, center_lon, start_bearing, radius_m
        )
        points.append((edge_lat, edge_lon))

        arc_steps = max(4, int(sector_angle / 10))
        for step in range(1, arc_steps + 1):
            b = start_bearing + (end_bearing - start_bearing) * step / arc_steps
            lat, lon = destination_point(center_lat, center_lon, b, radius_m)
            points.append((lat, lon))

        points.append((center_lat, center_lon))

    return points


def pixel_to_geo(
    pixel_x: float,
    pixel_y: float,
    image_w: int,
    image_h: int,
    drone_lat: float,
    drone_lon: float,
    drone_alt: float,
    gimbal_pitch_deg: float,
    gimbal_yaw_deg: float,
    fov_deg: float = 84.0,
) -> Tuple[float, float]:
    """Project a pixel coordinate to a WGS-84 ground position."""
    if drone_alt <= 0:
        return drone_lat, drone_lon

    norm_x = (pixel_x - image_w / 2.0) / (image_w / 2.0)
    norm_y = (pixel_y - image_h / 2.0) / (image_h / 2.0)

    fov_rad = _deg2rad(fov_deg)
    aspect = image_w / image_h
    vfov_rad = fov_rad / aspect

    off_yaw = norm_x * (fov_rad / 2.0)
    off_pitch = norm_y * (vfov_rad / 2.0)

    total_pitch = _deg2rad(gimbal_pitch_deg) + off_pitch
    total_yaw = _deg2rad(gimbal_yaw_deg) + off_yaw

    if total_pitch >= 0:
        total_pitch = _deg2rad(-1.0)

    ground_dist = drone_alt * math.tan(-total_pitch)
    bearing = _rad2deg(total_yaw) % 360.0
    return destination_point(drone_lat, drone_lon, bearing, ground_dist)
