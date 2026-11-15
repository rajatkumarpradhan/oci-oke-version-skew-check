"""SKEW001-SKEW004 rules."""

from __future__ import annotations

from dataclasses import dataclass

from .eol import is_eol
from .model import Snapshot

MAX_SUPPORTED_SKEW_MINORS = 2  # Kubernetes version skew support window


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # HIGH | MEDIUM | LOW
    cluster: str
    subject: str
    detail: str


def _minor_skew(control_plane: tuple, node: tuple) -> int:
    """Minor versions the node pool trails the control plane (negative if ahead)."""
    return (control_plane[0] - node[0]) * 100 + (control_plane[1] - node[1])


def rule_unsupported_skew(snapshot: Snapshot) -> list:
    """SKEW001 HIGH: node pool more than MAX_SUPPORTED_SKEW_MINORS behind."""
    out = []
    for c in snapshot.clusters:
        for p in c.node_pools:
            skew = _minor_skew(c.control_plane_version, p.kubernetes_version)
            if skew > MAX_SUPPORTED_SKEW_MINORS:
                out.append(
                    Finding(
                        rule="SKEW001",
                        severity="HIGH",
                        cluster=c.display_name,
                        subject=p.display_name,
                        detail=(
                            f"node pool {p.version_raw} is {skew} minor version(s) behind control plane "
                            f"{c.control_plane_raw} (> {MAX_SUPPORTED_SKEW_MINORS}); outside the supported skew window"
                        ),
                    )
                )
    return out


def rule_upgrade_due(snapshot: Snapshot) -> list:
    """SKEW002 MEDIUM: node pool 1-2 minors behind."""
    out = []
    for c in snapshot.clusters:
        for p in c.node_pools:
            skew = _minor_skew(c.control_plane_version, p.kubernetes_version)
            if 1 <= skew <= MAX_SUPPORTED_SKEW_MINORS:
                out.append(
                    Finding(
                        rule="SKEW002",
                        severity="MEDIUM",
                        cluster=c.display_name,
                        subject=p.display_name,
                        detail=f"node pool {p.version_raw} trails control plane {c.control_plane_raw} by {skew} minor(s); upgrade due",
                    )
                )
    return out


def rule_eol_control_plane(snapshot: Snapshot) -> list:
    """SKEW003 MEDIUM: control plane on an end-of-life minor (bundled table)."""
    out = []
    for c in snapshot.clusters:
        if is_eol(c.control_plane_version):
            out.append(
                Finding(
                    rule="SKEW003",
                    severity="MEDIUM",
                    cluster=c.display_name,
                    subject=c.display_name,
                    detail=f"control plane {c.control_plane_raw} is on an end-of-life minor; no more upstream patches",
                )
            )
    return out


def rule_no_surge(snapshot: Snapshot) -> list:
    """SKEW004 LOW: node pool with no surge capacity for upgrades."""
    out = []
    for c in snapshot.clusters:
        for p in c.node_pools:
            if p.max_surge == 0:
                out.append(
                    Finding(
                        rule="SKEW004",
                        severity="LOW",
                        cluster=c.display_name,
                        subject=p.display_name,
                        detail="max_surge is 0; in-place upgrades must evict nodes before replacements exist",
                    )
                )
    return out


ALL_RULES = (
    rule_unsupported_skew,
    rule_upgrade_due,
    rule_eol_control_plane,
    rule_no_surge,
)

_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def run_all(snapshot: Snapshot) -> list:
    findings = []
    for rule in ALL_RULES:
        findings.extend(rule(snapshot))
    findings.sort(key=lambda f: (_SEVERITY_RANK[f.severity], f.rule, f.cluster, f.subject))
    return findings


def exit_code(findings: list) -> int:
    if any(f.severity == "HIGH" for f in findings):
        return 2
    if findings:
        return 1
    return 0
