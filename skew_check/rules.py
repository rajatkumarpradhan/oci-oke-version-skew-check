"""SKEW001-SKEW004 rules.

Skew window follows the upstream Kubernetes version skew policy
(https://kubernetes.io/releases/version-skew-policy/): a kubelet must not be
newer than the API server and may be up to THREE minor versions older
(kubelets older than 1.25 may only be up to TWO minor versions older).
"""

from __future__ import annotations

from dataclasses import dataclass

from .eol import is_eol
from .model import Snapshot

DEFAULT_SKEW_MINORS = 3          # current upstream window for kubelet >= 1.25
LEGACY_SKEW_MINORS = 2           # kubelet < 1.25
LEGACY_KUBELET_MINOR = 25


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


def _allowed_skew(node: tuple) -> int:
    """Upstream-supported trailing minors for this kubelet version."""
    return LEGACY_SKEW_MINORS if node[1] < LEGACY_KUBELET_MINOR else DEFAULT_SKEW_MINORS


def rule_unsupported_skew(snapshot: Snapshot) -> list:
    """SKEW001 HIGH: node pool beyond the upstream-supported skew window."""
    out = []
    for c in snapshot.clusters:
        for p in c.node_pools:
            skew = _minor_skew(c.control_plane_version, p.kubernetes_version)
            allowed = _allowed_skew(p.kubernetes_version)
            if skew > allowed:
                out.append(
                    Finding(
                        rule="SKEW001",
                        severity="HIGH",
                        cluster=c.display_name,
                        subject=p.display_name,
                        detail=(
                            f"node pool {p.version_raw} is {skew} minor version(s) behind control plane "
                            f"{c.control_plane_raw}; upstream supports at most {allowed} for this kubelet"
                        ),
                    )
                )
    return out


def rule_upgrade_due(snapshot: Snapshot) -> list:
    """SKEW002 MEDIUM: node pool 1+ minors behind (still within support)."""
    out = []
    for c in snapshot.clusters:
        for p in c.node_pools:
            skew = _minor_skew(c.control_plane_version, p.kubernetes_version)
            allowed = _allowed_skew(p.kubernetes_version)
            if 1 <= skew <= allowed:
                note = (
                    "at the support edge - it must be upgraded before the next control-plane upgrade"
                    if skew == allowed else "upgrade due"
                )
                out.append(
                    Finding(
                        rule="SKEW002",
                        severity="MEDIUM",
                        cluster=c.display_name,
                        subject=p.display_name,
                        detail=f"node pool {p.version_raw} trails control plane {c.control_plane_raw} by {skew} minor(s); {note}",
                    )
                )
    return out


def rule_eol_control_plane(snapshot: Snapshot) -> list:
    """SKEW003 MEDIUM: control plane on a minor listed in the bundled EOL table."""
    out = []
    for c in snapshot.clusters:
        if is_eol(c.control_plane_version):
            out.append(
                Finding(
                    rule="SKEW003",
                    severity="MEDIUM",
                    cluster=c.display_name,
                    subject=c.display_name,
                    detail=(
                        f"control plane {c.control_plane_raw} is on a minor listed as end-of-life in the "
                        f"bundled (illustrative) EOL table; confirm against the current OKE support "
                        f"calendar before treating it as unpatched"
                    ),
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
