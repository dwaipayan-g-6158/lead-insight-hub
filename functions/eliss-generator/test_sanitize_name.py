"""Unit test for _sanitize_name (renderer-hardening). Run: py -3.9 test_sanitize_name.py
Replicates the helper from main.py (which can't be imported without the SDK)."""
import re


def _sanitize_name(s):
    if not s:
        return s
    t = re.sub(r"<[^>]*>", "", str(s))
    t = t.replace("<", " ").replace(">", " ")
    t = re.sub(r"[\x00-\x1f\x7f]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120] or None


cases = [
    # (input, expected)
    ("Gabriel Colon-Atencio", "Gabriel Colon-Atencio"),       # legit untouched
    ("Dwaipayan G.", "Dwaipayan G."),                          # legit untouched
    ("O'Brien, María José", "O'Brien, María José"),            # punctuation/accents kept
    ("QA Audit Probe <img src=x onerror=alert('xss')>", "QA Audit Probe"),  # tag stripped
    ("<script>alert(1)</script>", "alert(1)"),                 # tags stripped; inert text kept
    ("<img src=x onerror=alert(1)>", None),                    # all-markup -> None
    ("A < B > C", "A C"),                                      # '<...>' span removed (fine; names lack brackets)
    ("A > B < C", "A B C"),                                    # unpaired brackets -> spaces
    ("name\x00with\x1fcontrol", "name with control"),          # control chars -> space
    ("  spaced   out  ", "spaced out"),                        # whitespace collapsed
    (None, None),
    ("", ""),
    ("x" * 300, "x" * 120),                                    # clamped to 120
]

passed = 0
for inp, exp in cases:
    got = _sanitize_name(inp)
    assert got == exp, f"FAIL: {inp!r} -> {got!r}, expected {exp!r}"
    passed += 1
    print(f"  OK  {inp!r} -> {got!r}")

print(f"\nAll {passed} _sanitize_name cases passed.")
