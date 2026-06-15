"""Guard tests for sharded parallel synthesis (no pytest dependency).

Run:  python tests/test_sharded_synthesis.py

The critical invariant: spine + shards + narrative must own EVERY renderer
top-level dossier key EXACTLY ONCE. A duplicate owner means a section silently
overwrites another at merge time; a missing key means that section renders
empty. Both are silent failures, so they are asserted here.
"""
import collections
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "lib"))

import prompts  # noqa: E402

# The renderer-contract top-level keys: the 18 priority keys enumerated in
# prompts.REQUIRED_DOSSIER_SHAPE plus the Mom Test `data` block.
REQUIRED_TOP_LEVEL_KEYS = {
    "meta", "data_quality", "sources", "full_dossier_markdown", "executive_brief",
    "scoring", "lead", "company", "org_intelligence", "technology", "compliance",
    "budget_analysis", "demo_playbook", "signals", "pre_mortem",
    "rep_readiness_checklist", "recommendations", "recommended_outreach", "data",
}


def test_no_duplicate_owners():
    keys = prompts.all_owned_keys()
    dupes = [k for k, c in collections.Counter(keys).items() if c > 1]
    assert not dupes, f"keys owned by more than one producer: {dupes}"


def test_full_coverage_no_extras():
    owned = set(prompts.all_owned_keys())
    missing = REQUIRED_TOP_LEVEL_KEYS - owned
    extra = owned - REQUIRED_TOP_LEVEL_KEYS
    assert not missing, f"required renderer keys not owned by any producer: {missing}"
    assert not extra, f"producers own keys not in the renderer contract: {extra}"


def test_each_shard_instruction_names_its_keys():
    # Each shard's instruction text should mention every key it owns, so the
    # model is actually told to emit them.
    for spec in prompts.SHARD_SPECS:
        for key in spec["owns"]:
            assert key in spec["instruction"], (
                f"shard {spec['key']} owns {key} but its instruction never names it"
            )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'ALL PASS' if not failures else str(failures) + ' FAILURE(S)'}")
    sys.exit(1 if failures else 0)
