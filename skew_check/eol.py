"""Example end-of-life table for Kubernetes minor versions.

ILLUSTRATIVE SAMPLE DATA - refresh from Oracle's OKE support calendar before
relying on SKEW003 operationally.
"""

# Minor versions (major.minor) considered end-of-life: no more patches.
EOL_MINORS = ("1.24", "1.25", "1.26")


def is_eol(version: tuple) -> bool:
    """version is a (major, minor, patch) tuple."""
    return f"{version[0]}.{version[1]}" in EOL_MINORS
