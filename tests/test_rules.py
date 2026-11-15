import unittest

from skew_check.model import Cluster, NodePool, Snapshot, parse_version, SnapshotError
from skew_check.rules import (
    exit_code,
    rule_eol_control_plane,
    rule_no_surge,
    rule_unsupported_skew,
    rule_upgrade_due,
    run_all,
)


def pool(name="p1", version="v1.30.1", surge=1):
    return NodePool(ocid="oc1.np." + name, display_name=name,
                    kubernetes_version=parse_version(version, "test"),
                    version_raw=version, max_surge=surge)


def cluster(cp="v1.30.1", pools=(), name="c1"):
    return Cluster(ocid="oc1.c." + name, display_name=name,
                   control_plane_version=parse_version(cp, "test"),
                   control_plane_raw=cp, node_pools=tuple(pools))


class TestVersionParsing(unittest.TestCase):
    def test_parses_with_v_prefix(self):
        self.assertEqual(parse_version("v1.30.1", "t"), (1, 30, 1))

    def test_parses_without_v(self):
        self.assertEqual(parse_version("1.29.0", "t"), (1, 29, 0))

    def test_rejects_garbage(self):
        with self.assertRaises(SnapshotError):
            parse_version("latest", "t")


class TestSkew001(unittest.TestCase):
    def test_fires_beyond_three_minors(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(version="v1.26.2")]),))
        out = rule_unsupported_skew(snap)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].severity, "HIGH")

    def test_boundary_three_minors_quiet(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(version="v1.27.0")]),))
        self.assertEqual(rule_unsupported_skew(snap), [])

    def test_pre_1_25_kubelet_window_is_two(self):
        # kubelet < 1.25 only supports n-2: a 3-behind 1.24 pool is unsupported
        snap = Snapshot(clusters=(cluster(cp="v1.27.1", pools=[pool(version="v1.24.5")]),))
        self.assertEqual(len(rule_unsupported_skew(snap)), 1)

    def test_pool_ahead_of_control_plane_quiet(self):
        snap = Snapshot(clusters=(cluster(cp="v1.29.1", pools=[pool(version="v1.30.1")]),))
        self.assertEqual(rule_unsupported_skew(snap), [])


class TestSkew002(unittest.TestCase):
    def test_fires_one_minor_behind(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(version="v1.29.4")]),))
        out = rule_upgrade_due(snap)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].severity, "MEDIUM")

    def test_same_version_quiet(self):
        snap = Snapshot(clusters=(cluster(pools=[pool()]),))
        self.assertEqual(rule_upgrade_due(snap), [])


class TestSkew003Eol(unittest.TestCase):
    def test_fires_on_eol_minor(self):
        snap = Snapshot(clusters=(cluster(cp="v1.26.2"),))
        out = rule_eol_control_plane(snap)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].severity, "MEDIUM")

    def test_quiet_on_supported_minor(self):
        snap = Snapshot(clusters=(cluster(),))
        self.assertEqual(rule_eol_control_plane(snap), [])


class TestSkew004Surge(unittest.TestCase):
    def test_fires_on_zero_surge(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(surge=0)]),))
        self.assertEqual(len(rule_no_surge(snap)), 1)

    def test_quiet_with_surge(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(surge=2)]),))
        self.assertEqual(rule_no_surge(snap), [])


class TestAggregation(unittest.TestCase):
    def test_exit_code_2_on_high(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(version="v1.26.0")]),))
        self.assertEqual(exit_code(run_all(snap)), 2)

    def test_exit_code_1_on_medium_only(self):
        snap = Snapshot(clusters=(cluster(pools=[pool(version="v1.29.0")]),))
        self.assertEqual(exit_code(run_all(snap)), 1)

    def test_exit_code_0_when_clean(self):
        snap = Snapshot(clusters=(cluster(pools=[pool()]),))
        self.assertEqual(exit_code(run_all(snap)), 0)


if __name__ == "__main__":
    unittest.main()
