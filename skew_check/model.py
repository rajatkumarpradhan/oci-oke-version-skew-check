"""Data model + snapshot loading for OKE version skew checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


class SnapshotError(ValueError):
    """Raised when a snapshot file is malformed."""


_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str, what: str) -> tuple:
    m = _VERSION_RE.match(str(value).strip())
    if not m:
        raise SnapshotError(f"invalid version for {what}: {value!r} (expected vX.Y.Z)")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


@dataclass(frozen=True)
class NodePool:
    ocid: str
    display_name: str
    kubernetes_version: tuple
    version_raw: str
    max_surge: int = 0


@dataclass(frozen=True)
class Cluster:
    ocid: str
    display_name: str
    control_plane_version: tuple
    control_plane_raw: str
    node_pools: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class Snapshot:
    clusters: tuple


def load_snapshot(path: str) -> Snapshot:
    with open(path, "r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise SnapshotError(f"{path}: not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("clusters"), list):
        raise SnapshotError(f"{path}: top level must be an object with a 'clusters' list")
    clusters = []
    for i, c in enumerate(raw["clusters"]):
        where = f"clusters[{i}]"
        for req in ("ocid", "display_name", "control_plane_version"):
            if req not in c:
                raise SnapshotError(f"{where}: missing required field {req!r}")
        pools = []
        for j, p in enumerate(c.get("node_pools", [])):
            pwhere = f"{where}.node_pools[{j}]"
            for req in ("ocid", "display_name", "kubernetes_version"):
                if req not in p:
                    raise SnapshotError(f"{pwhere}: missing required field {req!r}")
            surge = p.get("max_surge", 0)
            if not isinstance(surge, int) or surge < 0:
                raise SnapshotError(f"{pwhere}: max_surge must be a non-negative integer")
            pools.append(
                NodePool(
                    ocid=p["ocid"],
                    display_name=p["display_name"],
                    kubernetes_version=parse_version(p["kubernetes_version"], f"{pwhere}.kubernetes_version"),
                    version_raw=p["kubernetes_version"],
                    max_surge=surge,
                )
            )
        clusters.append(
            Cluster(
                ocid=c["ocid"],
                display_name=c["display_name"],
                control_plane_version=parse_version(c["control_plane_version"], f"{where}.control_plane_version"),
                control_plane_raw=c["control_plane_version"],
                node_pools=tuple(pools),
            )
        )
    return Snapshot(clusters=tuple(clusters))
