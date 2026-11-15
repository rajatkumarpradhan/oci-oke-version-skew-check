# oci-oke-version-skew-check

**Category: custom portfolio tool.** Pure Python command-line checker. It does **not** wire any
built-in OCI services together - it is the *custom* project in its daily pair (the built-in
services project is `oci-ootb-notifications-fanout-check`).

## The problem

On OCI Container Engine (OKE), the Kubernetes version skew policy only tolerates node pools so
far behind their control plane. Drift past that window and kubectl calls, webhooks and upgrades
start breaking in ways that look unrelated - and a control plane on an end-of-life minor version
stops getting patches at all. The drift is silent: nothing pages you when a pool crosses the
line. This tool reads an **offline cluster snapshot** and flags exactly which pools crossed it.

## What it does

Reads a JSON snapshot (schema below, synthetic samples included) and applies four rules:

| Rule | Severity | Fires when |
| ---- | -------- | ---------- |
| SKEW001 | HIGH | A node pool is more than 2 minor versions behind its control plane - outside the Kubernetes version skew support window. |
| SKEW002 | MEDIUM | A node pool is 1-2 minors behind (upgrade due before the next control-plane bump). |
| SKEW003 | MEDIUM | The control plane runs a minor version marked end-of-life in the bundled EOL table. |
| SKEW004 | LOW | A node pool has no surge capacity configured (`max_surge` = 0) - upgrades must kill nodes before replacing them. |

Exit code: `2` if any HIGH finding, `1` if only MEDIUM/LOW, `0` when clean.

## Run it

```bash
python -m skew_check.cli samples/clusters_messy.json   # exits 2, all 4 rules fire
python -m skew_check.cli samples/clusters_clean.json   # exits 0
```

## Test it

```bash
python -m unittest discover -s tests -v   # 19 tests, stdlib only
```

## Snapshot schema

```json
{
  "clusters": [
    {
      "ocid": "ocid1.cluster.oc1..c1",
      "display_name": "prod-oke",
      "control_plane_version": "v1.30.1",
      "node_pools": [
        {"ocid": "ocid1.nodepool.oc1..np1", "display_name": "workers",
         "kubernetes_version": "v1.28.2", "max_surge": 1}
      ]
    }
  ]
}
```

The bundled EOL table (`skew_check/eol.py`) carries example end-of-life minors for illustration;
swap in Oracle's current support calendar before relying on SKEW003 operationally.

## Honest limits

- **Offline only**: the snapshot is synthetic; nothing calls the OKE API or lists real clusters.
- Skew math compares minor versions only (Kubernetes' published skew window); patch drift and
  image-tag currency are not modeled.
- The EOL table is illustrative sample data, not Oracle's live support calendar - treat SKEW003
  as a wiring demo until the table is refreshed from the source.
- `max_surge` semantics are simplified to "0 means no surge"; real OKE supports both surge and
  unavailable settings with more nuance.
- SKEW001/SKEW002 are upgrade candidates, not proof anything is broken today.

## Project status

Built as a daily portfolio project. 19 unit tests, all green locally and in CI
(`.github/workflows/ci.yml`, Python 3.10/3.11/3.12). No paid services, no live cloud calls.
