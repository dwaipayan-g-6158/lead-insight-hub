"""Regression test for the render_source_entry None-URL crash. Run: py -3.9 test_render_sources.py

Repro: a source dict with an explicit "url": null (emitted by rr_degraded /
OSINT-only synthesis) crashed generate_report.py with
  TypeError: object of type 'NoneType' has no len()
because entry.get('url', '') returns the default only for an ABSENT key, not a
present-but-null value. This replicates the fixed helper in isolation."""

def escape_html(s):  # minimal stand-in
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

TIER_BADGE = {'A': {'bg': 'b', 'color': 'c', 'label': 'A'},
              'B': {'bg': 'b', 'color': 'c', 'label': 'B'},
              'C': {'bg': 'b', 'color': 'c', 'label': 'C'}}


def render_source_entry(entry):  # mirrors the fixed main-copy logic
    if isinstance(entry, dict):
        u = entry.get('url') or ''
        tier = entry.get('tier', 'C')
        tb = TIER_BADGE.get(tier, TIER_BADGE['C'])
        tier_html = f'<span>{tb["label"]}</span>'
    else:
        u = str(entry) if entry is not None else ''
        tier_html = ''
    if not u:
        return ''
    u_disp = u if len(u) <= 60 else u[:57] + '…'
    return f'{tier_html}<a href="{escape_html(u)}" target="_blank">{escape_html(u_disp)}</a>'


def render_sources(sources):
    out = ''
    for cat, urls in sources.items():
        if urls:
            rendered = [s for s in (render_source_entry(e) for e in urls) if s]
            if rendered:
                out += f'<div><strong>{cat.title()}:</strong> ' + ', '.join(rendered) + '</div>'
    return out


passed = 0


def _assert(cond):
    assert cond


def check(name, fn):
    global passed
    fn(); passed += 1; print('  OK', name)


# 1. The exact crash repro: dict with url=None must NOT raise.
check('dict url=None does not crash and is skipped', lambda: (
    _assert(render_source_entry({'url': None, 'tier': 'C'}) == '')))

# 2. Plain None entry skipped.
check('None entry skipped', lambda: _assert(render_source_entry(None) == ''))

# 3. Missing url key skipped (was already ok via default '').
check('dict without url skipped', lambda: _assert(render_source_entry({'tier': 'A'}) == ''))

# 4. Valid url renders a link.
check('valid dict url renders', lambda: _assert(
    'href="https://x.io"' in render_source_entry({'url': 'https://x.io', 'tier': 'B'})))

# 5. Legacy flat string still works.
check('legacy string url renders', lambda: _assert(
    'href="https://y.io"' in render_source_entry('https://y.io')))

# 6. Mixed list incl. null url: only the good one renders, no crash, no empty join.
check('mixed sources skip nulls cleanly', lambda: _assert(
    render_sources({'web': [{'url': None}, {'url': 'https://ok.io', 'tier': 'A'}, None]})
    == '<div><strong>Web:</strong> <span>A</span><a href="https://ok.io" target="_blank">https://ok.io</a></div>'))

# 7. All-null category renders nothing (no empty "Web:" header).
check('all-null category omitted', lambda: _assert(
    render_sources({'web': [{'url': None}, None]}) == ''))


print(f'\nAll {passed} render_source_entry cases passed.')
