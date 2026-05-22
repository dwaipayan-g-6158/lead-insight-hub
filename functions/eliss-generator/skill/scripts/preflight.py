#!/usr/bin/env python3
"""
ELISS preflight (v7.0+) — offline deterministic OSINT harvest.

This script hits a curated set of FREE, publicly queryable intelligence
endpoints via pure HTTP, WITHOUT consuming any of Claude's per-conversation
tool budget. The output is a JSON file (preflight_<domain>.json) that the
ELISS skill reads at Layer 1 via a single Read() call, extracting
~8-15 deterministic signals for zero Claude tool calls.

This is half of the v7.0 bottleneck removal — the other half is the
parallel subagent dispatch pattern documented in SKILL.md STEP 2 →
"Parallel Dispatch Pattern".

Usage:
    python scripts/preflight.py <domain>
    python scripts/preflight.py <domain> --company "Acme Corp"
    python scripts/preflight.py <domain> --output preflight.json

Output contract:
    - Always writes the output JSON, even when every probe fails.
    - Each probe records {checked, _layer, _elapsed_ms, error?}.
    - Probes map 1:1 into data_quality.sources_actually_checked[] with
      access_method="preflight".

Dependencies:
    Python 3.8+. Stdlib only. `dnspython` is used opportunistically for
    richer DNS records (MX, TXT) when importable; otherwise the script
    falls back to socket.getaddrinfo for basic A-record resolution.

Environment variables:
    HIBP_API_KEY   optional — enables haveibeenpwned.com domain breach check
    OTX_API_KEY    optional — enables AlienVault OTX threat-intel probe
                   (free signup at otx.alienvault.com)
    USER_AGENT     optional — overrides the default User-Agent header

Probes (and which research Layer each serves):
    DNS / SPF           Layer 1, 2
    crt.sh              Layer 2 — subdomain enumeration
    Microsoft tenant    Layer 2 — Azure/Entra tenant + federation state
    Web Archive         Layer 2 — historical site snapshots
    SEC EDGAR           Layer 4 — public-company filings
    USAspending         Layer 4, 4b — federal contract footprint
    ransomware.live     Layer 3 — confirmed ransomware victim claims
    GitHub org          Layer 2, 7 — engineering footprint
    HIBP domain         Layer 3 — domain-level breach history (if API key set)
    AlienVault OTX      Layer 3 — domain/IP pulse hits + optional sector
                                  pulse search (if --industry given and key set)
    XposedOrNot         Layer 3 — domain & optional lead-email breach lookup
                                  via free public endpoints (no API key required)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PREFLIGHT_VERSION = '7.5.2'
DEFAULT_TIMEOUT_SECS = 10
DEFAULT_UA = f'ELISS-preflight/{PREFLIGHT_VERSION} (+https://manageengine.com; research@example.com)'


def _reconfigure_stdio_utf8():
    """Match generate_report.py — Windows consoles default to cp1252 and mojibake
    the em-dash / arrows in the log output. Force UTF-8 so output renders cleanly
    across platforms and so subprocess captures with encoding='utf-8' don't fail."""
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


# ============================================================================
#  HTTP helpers — thin wrappers around urllib so they're easy to mock in tests
# ============================================================================

def _http_get_json(url, headers=None, timeout=None, method='GET', data=None):
    """Return parsed JSON. Caller wraps in try/except. Raises urllib errors."""
    req_headers = {'User-Agent': os.environ.get('USER_AGENT', DEFAULT_UA)}
    if headers:
        req_headers.update(headers)
    body = json.dumps(data).encode('utf-8') if data is not None else None
    if body is not None:
        req_headers.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout or DEFAULT_TIMEOUT_SECS) as resp:
        raw = resp.read()
    # Some endpoints return empty body on 2xx — treat as empty dict.
    if not raw.strip():
        return {}
    return json.loads(raw.decode('utf-8', errors='replace'))


def _http_get_text(url, headers=None, timeout=None):
    req_headers = {'User-Agent': os.environ.get('USER_AGENT', DEFAULT_UA)}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout or DEFAULT_TIMEOUT_SECS) as resp:
        return resp.read().decode('utf-8', errors='replace')


# ============================================================================
#  Individual probes
#
#  Contract: each probe is a pure function that takes its inputs and returns
#  a dict. It NEVER raises on network/parse errors — it returns
#  {"checked": False, "error": "..."} instead. This keeps main() a simple
#  sequential runner without defensive wrapping at each call site.
# ============================================================================

def probe_dns(domain, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 1/2 — A, MX, TXT records. Uses dnspython if available, else socket."""
    result = {'a': [], 'mx': [], 'txt': [], 'spf': None, 'has_dmarc': None, 'resolver': None}
    try:
        import dns.resolver  # type: ignore
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        result['resolver'] = 'dnspython'
        for rtype in ('A', 'MX', 'TXT'):
            try:
                answers = resolver.resolve(domain, rtype)
                if rtype == 'A':
                    result['a'] = [str(a) for a in answers]
                elif rtype == 'MX':
                    result['mx'] = sorted({str(a.exchange).rstrip('.') for a in answers})
                elif rtype == 'TXT':
                    txts = []
                    for a in answers:
                        try:
                            txts.append(b''.join(a.strings).decode('utf-8', errors='replace'))
                        except Exception:
                            txts.append(str(a))
                    result['txt'] = txts
                    for t in txts:
                        if t.lower().startswith('v=spf1'):
                            result['spf'] = t
                            break
            except Exception:
                # individual rtype failure is fine
                pass
        # DMARC: look at _dmarc.<domain> TXT
        try:
            dmarc_answers = resolver.resolve(f'_dmarc.{domain}', 'TXT')
            result['has_dmarc'] = any(
                (b''.join(a.strings) if hasattr(a, 'strings') else str(a).encode()).lower().startswith(b'v=dmarc1')
                for a in dmarc_answers
            )
        except Exception:
            result['has_dmarc'] = False
    except ImportError:
        result['resolver'] = 'socket'
        try:
            addr_info = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
            result['a'] = sorted({ai[4][0] for ai in addr_info if ai[4] and ai[4][0]})
        except Exception as e:
            result['checked'] = False
            result['error'] = f'socket: {e}'[:200]
            return result
    result['checked'] = bool(result['a'] or result['mx'] or result['txt'])
    # Detect email provider from MX records — most useful single DNS signal.
    mx_providers = _classify_mx(result['mx'])
    if mx_providers:
        result['email_provider'] = mx_providers
    return result


_MX_PATTERNS = {
    'microsoft_365': [r'\.mail\.protection\.outlook\.com$', r'\.outlook\.com$'],
    'google_workspace': [r'(^|\.)aspmx\.l\.google\.com$', r'googlemail\.com$'],
    'proofpoint': [r'\.pphosted\.com$'],
    'mimecast': [r'\.mimecast\.com$'],
    'zoho_mail': [r'\.zoho\.(com|eu|in)$'],
    'amazon_ses': [r'\.amazonses\.com$'],
}


def _classify_mx(mx_list):
    """Match MX hostnames against known email-platform patterns. Returns list of providers."""
    providers = []
    for mx in mx_list:
        for provider, patterns in _MX_PATTERNS.items():
            if any(re.search(p, mx, re.IGNORECASE) for p in patterns):
                if provider not in providers:
                    providers.append(provider)
    return providers


def probe_crtsh(domain, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 2 — subdomain enumeration via certificate transparency.

    Any of `adfs.`, `vpn.`, `owa.`, `lync.`, `mail.` is strong evidence of
    an on-prem Microsoft / AD environment.
    """
    try:
        data = _http_get_json(
            f'https://crt.sh/?q=%25.{urllib.parse.quote(domain)}&output=json',
            timeout=timeout,
        )
    except urllib.error.HTTPError as e:
        return {'checked': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    subs = set()
    for entry in data or []:
        for name in (entry.get('name_value') or '').splitlines():
            name = name.strip().lower().lstrip('*.')
            if name and name.endswith(domain) and name != domain:
                subs.add(name)

    ad_signals = [
        s for s in subs
        if any(s.split('.')[0] in ('adfs', 'sts', 'vpn', 'owa', 'lync', 'webmail', 'autodiscover', 'exchange')
               for _ in [0])
    ]
    return {
        'checked': True,
        'count': len(subs),
        'subdomains': sorted(subs)[:100],
        'ad_environment_signals': ad_signals[:20],
        'has_autodiscover': any(s.startswith('autodiscover.') for s in subs),
    }


def probe_microsoft_tenant(domain, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 2 — public getuserrealm endpoint returns federation state + tenant brand.

    NameSpaceType values:
      - Managed     → Azure AD / Entra ID managed tenant (on-prem synced or cloud-only)
      - Federated   → Azure AD + on-prem ADFS federation
      - Unknown     → no Microsoft tenant for this domain
      - (HTTP 404)  → same meaning as Unknown: no tenant exists for this domain.
                      Endpoint returns 404 for many .gov / self-hosted domains.
    """
    url = f'https://login.microsoftonline.com/getuserrealm.srv?login=probe@{urllib.parse.quote(domain)}&xml=1'
    try:
        xml = _http_get_text(url, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Factually useful: the domain has no Microsoft tenant. Record as
            # a successful check (yielded_signal=True for the audit trail)
            # with is_microsoft_tenant=False.
            return {
                'checked': True, 'is_microsoft_tenant': False,
                'namespace_type': None, 'reason': 'endpoint_404_no_tenant',
                'federation_suggests_on_prem_ad': False,
            }
        return {'checked': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    def _extract(tag):
        m = re.search(rf'<{tag}>([^<]*)</{tag}>', xml)
        return m.group(1) if m else None

    namespace = _extract('NameSpaceType')
    is_ms = namespace in ('Managed', 'Federated')
    return {
        'checked': True,
        'is_microsoft_tenant': is_ms,
        'namespace_type': namespace,
        'domain_name': _extract('DomainName'),
        'federation_brand_name': _extract('FederationBrandName'),
        'federation_active_auth_url': _extract('AuthURL') if namespace == 'Federated' else None,
        'cloud_instance_name': _extract('CloudInstanceName'),
        # High-value derived signal:
        'federation_suggests_on_prem_ad': namespace == 'Federated',
    }


def probe_web_archive(domain, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 2 — Wayback Machine snapshot availability + earliest."""
    try:
        data = _http_get_json(
            f'https://archive.org/wayback/available?url={urllib.parse.quote(domain)}',
            timeout=timeout,
        )
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}
    snap = (data.get('archived_snapshots') or {}).get('closest') or {}
    return {
        'checked': True,
        'available': bool(snap.get('available')),
        'closest_timestamp': snap.get('timestamp'),
        'closest_url': snap.get('url'),
    }


def probe_sec_edgar(company, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 4 — full-text search for 10-K / 10-Q filings. US public companies only.

    EDGAR full-text returns any filing that MENTIONS the company name —
    including filings by OTHER entities that happen to reference the name
    (e.g., searching "Coppell" returns 10-Ks by companies HEADQUARTERED in
    Coppell TX, not filings by the city itself). The raw hit_count is
    therefore a poor signal — a city has 100 hits but is not a public
    company. We post-filter: `is_public_company` is True only if at least
    one top hit's `display_names[0]` starts with the company name (case-
    insensitive). Bare hit_count is still reported for transparency.
    """
    if not company:
        return {'checked': False, 'error': 'no_company_name'}
    try:
        data = _http_get_json(
            f'https://efts.sec.gov/LATEST/search-index?q={urllib.parse.quote(company)}&forms=10-K,10-Q',
            headers={'User-Agent': os.environ.get('USER_AGENT', DEFAULT_UA)},
            timeout=timeout,
        )
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    hits = (data.get('hits') or {}).get('hits') or []
    top = [
        {
            'adsh': h.get('_id'),
            'form': (h.get('_source') or {}).get('form'),
            'display_names': (h.get('_source') or {}).get('display_names'),
            'filed_at': (h.get('_source') or {}).get('file_date'),
        }
        for h in hits[:10]  # widen to 10 so the display-name match has room to hit
    ]

    # Post-filter: does any top-10 hit's display_names[0] actually start with
    # the company name? This is the difference between "the string appears in
    # a filing" and "a filing was made BY the company."
    needle = company.strip().lower()
    def _display_match(hit):
        names = hit.get('display_names') or []
        return any(
            (n or '').strip().lower().startswith(needle)
            for n in names
        )
    filer_hits = [h for h in top if _display_match(h)]

    return {
        'checked': True,
        'is_public_company': bool(filer_hits),
        'hit_count_raw': len(hits),         # filings that MENTION the company
        'filer_hit_count': len(filer_hits),  # filings actually BY a company whose display name starts with `company`
        'top_filer_hits': filer_hits[:5],
        'top_hits': top[:5],  # kept for debugging; do NOT use for is_public_company
    }


def probe_usaspending(company, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 4/4b — federal contract awards. High-signal for public-sector prospects.

    Historical note: a `time_period` filter here used to return HTTP 400 when
    the end_date was past USAspending's current-fiscal-year max. We dropped
    the time_period filter entirely — the API's implicit default window
    covers all recorded awards, which is what we want ("has this entity ever
    received federal money?"). Dropping the filter also future-proofs the
    probe against API policy drift on date bounds.
    """
    if not company:
        return {'checked': False, 'error': 'no_company_name'}
    payload = {
        'filters': {
            'award_type_codes': ['A', 'B', 'C', 'D'],
            'recipient_search_text': [company],
        },
        'fields': [
            'Recipient Name', 'Award ID', 'Total Obligated Amount',
            'Description', 'End Date', 'Awarding Agency',
        ],
        # Sort by Award ID — 'Total Obligated Amount' is not in the API's
        # allowed sort field list for contract awards (returns HTTP 400).
        # We still re-rank locally by amount below.
        'page': 1, 'limit': 10, 'sort': 'Award ID', 'order': 'desc',
    }
    try:
        data = _http_get_json(
            'https://api.usaspending.gov/api/v2/search/spending_by_award/',
            timeout=timeout,
            method='POST',
            data=payload,
        )
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    awards = data.get('results') or []
    # Re-rank by Total Obligated Amount locally (API sort is by Award ID, not
    # amount; see comment in the payload above).
    def _amount(a):
        try:
            return float(a.get('Total Obligated Amount') or 0)
        except (TypeError, ValueError):
            return 0.0
    ranked = sorted(awards, key=_amount, reverse=True)
    return {
        'checked': True,
        'has_federal_contracts': len(awards) > 0,
        'top_awards': [
            {
                'id': a.get('Award ID'),
                'amount': a.get('Total Obligated Amount'),
                'description': (a.get('Description') or '')[:200],
                'end_date': a.get('End Date'),
                'awarding_agency': a.get('Awarding Agency'),
            }
            for a in ranked[:5]
        ],
        'top_obligated_total': sum(_amount(a) for a in awards),
    }


def probe_ransomware_live(company, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 3 — cross-check public ransomware-victim feeds.

    Notes: ransomware.live's API has changed shape over time. This probe is
    best-effort; absence of matches does NOT prove the company wasn't hit
    (leak sites get taken down, feeds lag, attribution is incomplete).
    """
    if not company:
        return {'checked': False, 'error': 'no_company_name'}
    try:
        data = _http_get_json('https://api.ransomware.live/v2/recentvictims', timeout=timeout)
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    if not isinstance(data, list):
        return {'checked': False, 'error': 'unexpected_response_shape'}

    needle = company.lower()
    matches = []
    for v in data:
        name = (v.get('victim') or v.get('post_title') or '').lower()
        if needle in name:
            matches.append({
                'group': v.get('group') or v.get('group_name'),
                'victim': v.get('victim') or v.get('post_title'),
                'attackdate': v.get('attackdate') or v.get('discovered'),
                'country': v.get('country'),
            })
    return {
        'checked': True,
        'recent_feed_size': len(data),
        'match_count': len(matches),
        'matches': matches[:5],
    }


def probe_github_org(org_slug, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 2/7 — does the company have a public GitHub organization?

    Unauth'd GitHub API allows ~60 req/hr per source IP — plenty for preflight.
    """
    if not org_slug:
        return {'checked': False, 'error': 'no_org_slug'}
    try:
        data = _http_get_json(f'https://api.github.com/orgs/{urllib.parse.quote(org_slug)}', timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'checked': True, 'exists': False}
        return {'checked': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    return {
        'checked': True,
        'exists': True,
        'slug': org_slug,
        'public_repos': data.get('public_repos'),
        'followers': data.get('followers'),
        'blog': data.get('blog'),
        'created_at': data.get('created_at'),
        'description': data.get('description'),
    }


def probe_hibp_domain(domain, api_key, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 3 — domain-level breach history. Requires HIBP_API_KEY env var."""
    if not api_key:
        return {'checked': False, 'reason': 'no_api_key', 'hint': 'Set HIBP_API_KEY to enable this probe'}
    try:
        data = _http_get_json(
            f'https://haveibeenpwned.com/api/v3/breaches?domain={urllib.parse.quote(domain)}',
            headers={'hibp-api-key': api_key},
            timeout=timeout,
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'checked': True, 'breach_count': 0, 'breaches': []}
        return {'checked': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    if not isinstance(data, list):
        return {'checked': True, 'breach_count': 0, 'breaches': []}

    return {
        'checked': True,
        'breach_count': len(data),
        'breaches': [
            {
                'name': b.get('Name'),
                'date': b.get('BreachDate'),
                'pwn_count': b.get('PwnCount'),
                'domain': b.get('Domain'),
            }
            for b in data[:10]
        ],
    }


def probe_otx(domain, ipv4_list, industry, api_key, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 3 — AlienVault OTX threat intel. Requires OTX_API_KEY env var.

    Fires up to three sub-calls against the free OTX API
    (https://otx.alienvault.com), all gated on `api_key`:

      1. /indicators/domain/{domain}/general
         → does the prospect's own domain appear in any OTX pulse? Direct
           Tier-A Intent signal when count > 0.

      2. /indicators/IPv4/{ip}/general  (capped at the first 3 IPs)
         → for each A/MX IP resolved by the dns probe, check pulse hits.

      3. /search/pulses?q={industry}    (only if --industry was supplied)
         → recent sector-level pulses for the Layer 3 narrative
           ("your industry saw N campaigns in the last 90 days").

    Returns a single dict so the audit trail logs one row per skill source —
    same shape contract as the other probes. HTTP failures are soft-skipped.
    """
    if not api_key:
        return {
            'checked': False,
            'reason': 'no_api_key',
            'hint': 'Set OTX_API_KEY to enable this probe (free signup at otx.alienvault.com)',
        }

    headers = {'X-OTX-API-KEY': api_key}
    out = {
        'checked': False,
        'domain_pulse_count': 0,
        'domain_pulses': [],
        'ip_hits': [],
        'sector_pulses': [],
    }

    # 1. Domain general lookup — the highest-value single signal.
    try:
        d = _http_get_json(
            f'https://otx.alienvault.com/api/v1/indicators/domain/{urllib.parse.quote(domain)}/general',
            headers=headers,
            timeout=timeout,
        )
        pi = d.get('pulse_info') or {}
        out['domain_pulse_count'] = pi.get('count') or 0
        for p in (pi.get('pulses') or [])[:5]:
            out['domain_pulses'].append({
                'name': p.get('name'),
                'created': p.get('created'),
                'malware_families': [
                    (mf.get('display_name') or mf.get('target'))
                    for mf in (p.get('malware_families') or [])
                ][:3],
                'tags': (p.get('tags') or [])[:5],
            })
    except urllib.error.HTTPError as e:
        if e.code != 404:
            out['domain_error'] = f'HTTP {e.code}'
    except Exception as e:
        out['domain_error'] = str(e)[:200]

    # 2. IP general lookup — chains off the DNS A records already in the report.
    # Cap at 3 IPs so this probe stays bounded even when crt.sh returns many.
    for ip in (ipv4_list or [])[:3]:
        try:
            r = _http_get_json(
                f'https://otx.alienvault.com/api/v1/indicators/IPv4/{urllib.parse.quote(ip)}/general',
                headers=headers,
                timeout=timeout,
            )
            pi = (r.get('pulse_info') or {})
            count = pi.get('count') or 0
            if count:
                out['ip_hits'].append({
                    'ip': ip,
                    'pulse_count': count,
                    'asn': r.get('asn'),
                    'country': r.get('country_name'),
                })
        except Exception:
            # Soft-skip individual IP failures (one bad IP shouldn't sink the probe).
            continue

    # 3. Sector pulse search — operator-supplied industry keyword only.
    # No keyword → no search (a bare company-name search would not return
    # sector-scoped pulses and is not a useful default).
    if industry:
        try:
            p = _http_get_json(
                'https://otx.alienvault.com/api/v1/search/pulses?'
                f'q={urllib.parse.quote(industry)}&limit=10&sort=-modified',
                headers=headers,
                timeout=timeout,
            )
            for pu in (p.get('results') or [])[:10]:
                out['sector_pulses'].append({
                    'name': pu.get('name'),
                    'created': pu.get('created'),
                    'modified': pu.get('modified'),
                    'subscriber_count': pu.get('subscriber_count'),
                    'malware_families': [
                        (mf.get('display_name') or mf.get('target'))
                        for mf in (pu.get('malware_families') or [])
                    ][:3],
                    'tags': (pu.get('tags') or [])[:5],
                })
        except Exception as e:
            out['sector_pulses_error'] = str(e)[:200]

    out['checked'] = True
    return out


def probe_xposedornot(domain, lead_email, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 3 — XposedOrNot breach lookup via the free public endpoints
    documented at https://xposedornot.com/api_doc. **No API key required.**

    Fires up to three sub-calls, all unauthenticated:

      1. /v1/breaches?domain={domain}
         → list of breach records affecting the prospect's domain.
           Public-tier substitute for the auth-gated /v1/domain-breaches/
           POST endpoint, which we deliberately skip (no registration burden).

      2. /v1/check-email/{lead_email}   (only if `lead_email` is supplied)
         → list of breach names where this email appears.

      3. /v1/breach-analytics?email={lead_email}   (only if `lead_email` is
         supplied) → richer per-email analytics: yearly breakdown, exposed
         PII categories, paste summaries. We keep only a small slice.

    Same fail-soft contract as the other probes: HTTP errors → soft-skip;
    never raises. The probe always returns `checked: True` once at least
    the domain call has been attempted (even if it 404s — that's a clean
    "no public breaches for this domain" answer, not a probe failure).
    """
    if not domain:
        return {'checked': False, 'error': 'no_domain'}

    out = {
        'checked': False,
        'domain_breaches': [],
        'domain_breach_count': 0,
        'lead_email_breach_names': [],
        'lead_email_breach_count': 0,
        'lead_email_analytics': None,
    }

    # 1. Domain breach catalog — always runs, no auth.
    try:
        d = _http_get_json(
            f'https://api.xposedornot.com/v1/breaches?domain={urllib.parse.quote(domain)}',
            timeout=timeout,
        )
        items = []
        if isinstance(d, dict):
            items = d.get('exposedBreaches') or d.get('breaches') or []
        elif isinstance(d, list):
            items = d
        for b in items[:10]:
            if not isinstance(b, dict):
                continue
            out['domain_breaches'].append({
                'name': b.get('breachID') or b.get('Name') or b.get('name'),
                'date': b.get('breachedDate') or b.get('BreachDate') or b.get('date'),
                'records': b.get('exposedRecords') or b.get('PwnCount') or b.get('records'),
                'industry': b.get('industry') or b.get('Industry'),
                'exposed_data': b.get('exposedData') or b.get('DataClasses') or [],
            })
        out['domain_breach_count'] = len(items)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            out['domain_error'] = f'HTTP {e.code}'
    except Exception as e:
        out['domain_error'] = str(e)[:200]

    # 2. Lead-email breach check — operator-supplied; skip if absent.
    if lead_email:
        try:
            r = _http_get_json(
                f'https://api.xposedornot.com/v1/check-email/{urllib.parse.quote(lead_email)}',
                timeout=timeout,
            )
            breaches = []
            if isinstance(r, dict):
                br = r.get('breaches') or []
                if br and isinstance(br[0], list):
                    breaches = br[0]
                elif isinstance(br, list):
                    breaches = br
            out['lead_email_breach_names'] = [b for b in breaches if isinstance(b, str)][:20]
            out['lead_email_breach_count'] = len(out['lead_email_breach_names'])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pass
            else:
                out['lead_email_check_error'] = f'HTTP {e.code}'
        except Exception as e:
            out['lead_email_check_error'] = str(e)[:200]

        # 3. Per-email analytics.
        try:
            a = _http_get_json(
                f'https://api.xposedornot.com/v1/breach-analytics?email={urllib.parse.quote(lead_email)}',
                timeout=timeout,
            )
            if isinstance(a, dict):
                bm = (a.get('BreachMetrics') or {})
                out['lead_email_analytics'] = {
                    'yearly_metrics': bm.get('yearly_metrics') or bm.get('yearwise_details') or {},
                    'risk_score': bm.get('risk') or bm.get('risk_score'),
                    'industries': (bm.get('industry') or [])[:10],
                    'passwords_strength': bm.get('passwords_strength'),
                    'exposed_data_categories': (bm.get('xposed_data') or [])[:10],
                }
        except urllib.error.HTTPError as e:
            if e.code != 404:
                out['lead_email_analytics_error'] = f'HTTP {e.code}'
        except Exception as e:
            out['lead_email_analytics_error'] = str(e)[:200]

    out['checked'] = True
    return out


# ============================================================================
#  v7.5 probes — web fingerprint + security.txt + Wikidata
#  Each is zero Claude tokens: pure HTTP via stdlib; runs once per dossier.
# ============================================================================

WEB_FINGERPRINT_RULES = {
    'cdn': {
        'Cloudflare':         ['header:Server:cloudflare', 'header:CF-Ray:'],
        'Akamai':             ['header:Server:AkamaiGHost', 'cookie:_abck'],
        'Fastly':             ['header:Via:fastly', 'header:X-Served-By:cache-'],
        'Amazon CloudFront':  ['header:Server:CloudFront', 'header:Via:cloudfront', 'header:X-Amz-Cf-Id:'],
        'Azure CDN':          ['header:Server:AzureCDN'],
    },
    'framework': {
        'ASP.NET':            ['header:X-AspNet-Version:', 'header:X-Powered-By:ASP.NET', 'body:__VIEWSTATE'],
        'Express (Node.js)':  ['header:X-Powered-By:Express'],
        'Next.js':            ['body:__NEXT_DATA__', 'body:_next/static'],
        'Django':             ['header:X-Powered-By:Django', 'cookie:csrftoken'],
        'Ruby on Rails':      ['header:X-Powered-By:Phusion Passenger', 'cookie:_session_id'],
        'Java EE':            ['cookie:JSESSIONID'],
        'PHP':                ['header:X-Powered-By:PHP', 'cookie:PHPSESSID'],
    },
    'cms': {
        'WordPress':                  ['body:wp-content/', 'body:wp-includes/', 'body:meta name="generator" content="WordPress'],
        'Drupal':                     ['body:Drupal.settings', 'body:meta name="Generator" content="Drupal'],
        'Adobe Experience Manager':   ['body:clientlibs/', 'body:/etc.clientlibs/', 'body:cq-html'],
        'Salesforce Commerce Cloud':  ['body:demandware.static', 'body:dwsharedimages'],
        'Sitecore':                   ['body:sitecore', 'cookie:SC_ANALYTICS_GLOBAL_COOKIE'],
        'Wix':                        ['body:_wix_', 'body:wixstatic.com'],
        'Squarespace':                ['body:squarespace-cdn.com', 'header:Server:Squarespace'],
    },
    'analytics': {
        'Google Analytics':   ['body:google-analytics.com', 'body:googletagmanager.com', 'body:gtag('],
        'Adobe Analytics':    ['body:omtrdc.net', 'body:2o7.net', 'body:s_code.js'],
        'Mixpanel':           ['body:cdn.mxpnl.com'],
        'Segment':            ['body:cdn.segment.com'],
        'Heap':               ['body:heap.io'],
        'Hotjar':             ['body:static.hotjar.com'],
    },
    'chat': {
        'Drift':              ['body:js.driftt.com', 'body:widget.drift.com'],
        'Intercom':           ['body:widget.intercom.io'],
        'Zendesk Chat':       ['body:static.zdassets.com'],
        'LiveChat':           ['body:cdn.livechatinc.com'],
    },
    'email_marketing': {
        'Marketo':            ['body:mktoresp.com', 'body:munchkin.marketo.net'],
        'HubSpot':            ['body:js.hs-scripts.com', 'body:hsforms.net'],
        'Pardot':             ['body:pi.pardot.com'],
        'Mailchimp':          ['body:list-manage.com'],
        'Eloqua':             ['body:img.en25.com', 'body:elqcfg.com'],
    },
    'frontend': {
        'React':              ['body:react-root', 'body:data-reactid', 'body:_reactRootContainer'],
        'Vue.js':             ['body:vue.js', 'body:data-v-'],
        'Angular':            ['body:ng-version', 'body:ng-app'],
        'Svelte':             ['body:svelte-'],
        'Webpack':            ['body:webpackJsonp', 'body:webpack-runtime'],
        'jQuery':             ['body:jquery'],
    },
}


def _check_signature(headers_lc, body_lc, set_cookie_lc, sig):
    """Match one rule like 'header:Server:cloudflare', 'cookie:_abck', 'body:wp-content/'."""
    kind, _, rest = sig.partition(':')
    if kind == 'header':
        hdr_name, _, needle = rest.partition(':')
        return needle.lower() in (headers_lc.get(hdr_name.lower()) or '')
    if kind == 'cookie':
        return rest.lower() in set_cookie_lc
    if kind == 'body':
        return rest.lower() in body_lc
    return False


def _detect_brands(headers, body):
    """Return {category: [brand, ...]} given response headers and body sample."""
    headers_lc = {k.lower(): (v or '').lower() for k, v in (headers or {}).items()}
    body_lc = (body or '').lower()
    set_cookie_lc = headers_lc.get('set-cookie') or ''
    detected = {}
    for category, brands in WEB_FINGERPRINT_RULES.items():
        hits = []
        for brand, sigs in brands.items():
            if any(_check_signature(headers_lc, body_lc, set_cookie_lc, s) for s in sigs):
                hits.append(brand)
        detected[category] = hits
    return detected


def probe_web_fingerprint(domain, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 2 — fetch homepage, derive Web Tech Fingerprint badges from
    response headers + first 64 KB of HTML. ZERO Claude tokens."""
    if not domain:
        return {'checked': False, 'error': 'no_domain'}
    candidates = [f'https://www.{domain}', f'https://{domain}']
    last_err = None
    headers = {}
    body = ''
    final_url = None
    for url in candidates:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': os.environ.get('USER_AGENT', DEFAULT_UA)})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                headers = dict(resp.headers.items())
                body = resp.read(64 * 1024).decode('utf-8', errors='replace')
                final_url = resp.geturl()
            break
        except Exception as e:
            last_err = str(e)[:200]
            continue
    else:
        return {'checked': False, 'error': last_err or 'all_candidates_failed'}

    detected = _detect_brands(headers, body)
    return {
        'checked': True,
        'final_url': final_url,
        'server_header': headers.get('Server'),
        'x_powered_by': headers.get('X-Powered-By'),
        'detected': detected,
        'detected_count': sum(len(v) for v in detected.values()),
    }


def probe_security_txt(domain, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 2 — RFC 9116 security.txt presence. Published file = mature
    CISO function (positive intent signal). Absent = no signal."""
    if not domain:
        return {'checked': False, 'error': 'no_domain'}
    candidates = [
        f'https://{domain}/.well-known/security.txt',
        f'https://www.{domain}/.well-known/security.txt',
        f'https://{domain}/security.txt',
        f'https://www.{domain}/security.txt',
    ]
    for url in candidates:
        try:
            txt = _http_get_text(url, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            continue
        except Exception:
            continue
        fields = {}
        for line in (txt or '').splitlines()[:200]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line:
                k, _, v = line.partition(':')
                fields.setdefault(k.strip().lower(), []).append(v.strip())
        if 'contact' in fields:
            return {
                'checked': True,
                'published': True,
                'url': url,
                'contact': fields.get('contact', [])[:3],
                'expires': (fields.get('expires') or [None])[0],
                'policy': (fields.get('policy') or [None])[0],
                'preferred_languages': (fields.get('preferred-languages') or [None])[0],
            }
    return {'checked': True, 'published': False}


def probe_wikidata(company, timeout=DEFAULT_TIMEOUT_SECS):
    """Layer 4 — Wikidata company entity lookup. Surfaces founding date,
    parent org, HQ country, industry — useful when SEC EDGAR fuzzy-match
    fails (as it did for AIG)."""
    if not company:
        return {'checked': False, 'error': 'no_company'}
    try:
        search = _http_get_json(
            'https://www.wikidata.org/w/api.php?'
            f'action=wbsearchentities&search={urllib.parse.quote(company)}'
            '&language=en&format=json&type=item&limit=5',
            timeout=timeout,
        )
    except Exception as e:
        return {'checked': False, 'error': str(e)[:200]}

    matches = search.get('search') or []
    if not matches:
        return {'checked': True, 'qid': None, 'matches_count': 0}

    org_keywords = ('company', 'corporation', 'organization', 'organisation', 'group', 'bank',
                    'insurer', 'retailer', 'manufacturer', 'firm', 'holding', 'enterprise',
                    'agency', 'business', 'subsidiary', 'multinational')
    pick = None
    for m in matches:
        desc = (m.get('description') or '').lower()
        if any(k in desc for k in org_keywords):
            pick = m
            break
    pick = pick or matches[0]
    qid = pick.get('id')

    summary = {
        'qid': qid,
        'label': pick.get('label'),
        'description': pick.get('description'),
        'wikidata_url': pick.get('concepturi'),
        'matches_count': len(matches),
    }

    # Pull entity details for inception/parent/HQ/industry.
    try:
        ent = _http_get_json(
            'https://www.wikidata.org/w/api.php?'
            f'action=wbgetentities&ids={qid}'
            '&props=claims|labels&languages=en&format=json',
            timeout=timeout,
        )
        e = (ent.get('entities') or {}).get(qid) or {}
        claims = e.get('claims') or {}

        def _claim(prop_id):
            arr = claims.get(prop_id) or []
            for c in arr[:1]:
                mainsnak = c.get('mainsnak', {}).get('datavalue', {}).get('value')
                if isinstance(mainsnak, dict):
                    if 'time' in mainsnak:
                        return mainsnak['time'].lstrip('+').split('T')[0]
                    if 'id' in mainsnak:
                        return mainsnak['id']
                elif mainsnak is not None:
                    return mainsnak
            return None

        summary['inception']         = _claim('P571')
        summary['parent_org_qid']    = _claim('P749')
        summary['owned_by_qid']      = _claim('P127')
        summary['hq_qid']            = _claim('P159')
        summary['industry_qid']      = _claim('P452')
        summary['opencorporates_id'] = _claim('P1320')
    except Exception as e:
        summary['claims_error'] = str(e)[:200]

    return {'checked': True, **summary}


# ============================================================================
#  Orchestration
# ============================================================================

# Each step: (key, callable, layer_number_for_audit_trail, human_label_for_log)
def _steps(domain, company, github_slug, hibp_key, timeout):
    return [
        ('dns',              lambda: probe_dns(domain, timeout=timeout),                     1, 'DNS / SPF'),
        ('crtsh',            lambda: probe_crtsh(domain, timeout=timeout),                   2, 'crt.sh (subdomains)'),
        ('microsoft_tenant', lambda: probe_microsoft_tenant(domain, timeout=timeout),        2, 'Microsoft tenant'),
        ('web_archive',      lambda: probe_web_archive(domain, timeout=timeout),             2, 'Web Archive'),
        ('sec_edgar',        lambda: probe_sec_edgar(company, timeout=timeout),              4, 'SEC EDGAR'),
        ('usaspending',      lambda: probe_usaspending(company, timeout=timeout),            4, 'USAspending'),
        ('ransomware_live',  lambda: probe_ransomware_live(company, timeout=timeout),        3, 'ransomware.live'),
        ('github_org',       lambda: probe_github_org(github_slug, timeout=timeout),         2, 'GitHub org'),
        ('hibp',             lambda: probe_hibp_domain(domain, hibp_key, timeout=timeout),   3, 'HIBP domain breaches'),
        # v7.5 additions — three free probes to fill gaps the original 9 left open
        ('web_fingerprint',  lambda: probe_web_fingerprint(domain, timeout=timeout),         2, 'Web tech fingerprint'),
        ('security_txt',     lambda: probe_security_txt(domain, timeout=timeout),            2, 'security.txt (RFC 9116)'),
        ('wikidata',         lambda: probe_wikidata(company, timeout=timeout),               4, 'Wikidata entity lookup'),
    ]


def _derive_summary(report):
    """One-glance summary for Claude to read at Layer 1. Only factual rollups —
    no scoring or tier calls (that's the skill's job)."""
    ms = report.get('microsoft_tenant') or {}
    edgar = report.get('sec_edgar') or {}
    spending = report.get('usaspending') or {}
    ransom = report.get('ransomware_live') or {}
    github = report.get('github_org') or {}
    crtsh = report.get('crtsh') or {}
    dns = report.get('dns') or {}
    hibp = report.get('hibp') or {}
    web_fp = report.get('web_fingerprint') or {}
    sec_txt = report.get('security_txt') or {}
    wikidata = report.get('wikidata') or {}
    otx = report.get('otx') or {}
    xon = report.get('xposedornot') or {}

    email_provider = dns.get('email_provider') or []

    # XposedOrNot yearly-trend rollup: largest single-year breach count
    # from the lead-email analytics, if available.
    xon_yearly = ((xon.get('lead_email_analytics') or {}).get('yearly_metrics') or {})
    xon_yearly_max = 0
    if isinstance(xon_yearly, dict):
        try:
            xon_yearly_max = max((int(v) for v in xon_yearly.values() if isinstance(v, (int, float))), default=0)
        except (TypeError, ValueError):
            xon_yearly_max = 0

    return {
        'is_microsoft_tenant': bool(ms.get('is_microsoft_tenant')),
        'microsoft_namespace_type': ms.get('namespace_type'),
        'on_prem_ad_likely': bool(
            ms.get('federation_suggests_on_prem_ad')
            or crtsh.get('has_autodiscover')
            or any('adfs' in (s or '').split('.')[0] for s in (crtsh.get('ad_environment_signals') or []))
        ),
        'public_company': bool(edgar.get('is_public_company')),
        'federal_contractor': bool(spending.get('has_federal_contracts')),
        'ransomware_victim_confirmed': bool(ransom.get('match_count', 0)),
        'breach_count_hibp': hibp.get('breach_count'),
        'github_presence': bool(github.get('exists')),
        'subdomain_count': crtsh.get('count'),
        'email_provider': email_provider,
        # v7.5 additions
        'web_fingerprint': web_fp.get('detected') or {},
        'web_fingerprint_count': web_fp.get('detected_count') or 0,
        'security_txt_published': bool(sec_txt.get('published')),
        'wikidata_qid': wikidata.get('qid'),
        'wikidata_inception': wikidata.get('inception'),
        'wikidata_parent_qid': wikidata.get('parent_org_qid') or wikidata.get('owned_by_qid'),
        # v7.5.1 additions — AlienVault OTX threat intel
        'otx_domain_pulse_count': otx.get('domain_pulse_count') or 0,
        'otx_ip_hit_count': len(otx.get('ip_hits') or []),
        'otx_sector_pulse_count': len(otx.get('sector_pulses') or []),
        # v7.5.2 additions — XposedOrNot breach lookup (free public endpoints, no key)
        'xposedornot_domain_breach_count': xon.get('domain_breach_count') or 0,
        'xposedornot_lead_email_breach_count': xon.get('lead_email_breach_count') or 0,
        'xposedornot_yearly_breach_max': xon_yearly_max,
        'probes_yielded_signal': sum(
            1 for key in ('dns', 'crtsh', 'microsoft_tenant', 'web_archive',
                          'sec_edgar', 'usaspending', 'ransomware_live',
                          'github_org', 'hibp',
                          'web_fingerprint', 'security_txt', 'wikidata',
                          'otx', 'xposedornot')
            if (report.get(key) or {}).get('checked') is True
        ),
    }


def _default_github_slug(company, domain):
    """Guess an org slug. Not guaranteed to be right — GitHub orgs rarely
    match either the company name or domain exactly. The probe falls back
    gracefully to {'exists': False} on 404, so a wrong guess is cheap."""
    if company:
        slug = re.sub(r'[^a-zA-Z0-9-]', '', company.lower().replace(' ', '-'))
        if slug:
            return slug
    return domain.split('.')[0]


def run_preflight(domain, company=None, github_slug=None, industry=None, lead_email=None, timeout=DEFAULT_TIMEOUT_SECS, log=None):
    """Execute all probes serially. Returns the full report dict.

    Never raises for probe failures. Logs a one-liner per probe to `log`
    (defaults to sys.stderr).

    `industry` is an optional keyword (e.g., 'financial services', 'healthcare')
    used by the OTX probe's sector pulse search. When omitted, OTX still runs
    domain + IP lookups but skips the sector search.

    `lead_email` is an optional contact email used by the XposedOrNot probe's
    lead-email breach check + analytics endpoints (both public, no key needed).
    When omitted, only the domain-level XposedOrNot lookup runs.
    """
    log = log if log is not None else sys.stderr
    domain = _normalize_domain(domain)
    company = (company or '').strip() or _domain_to_company_guess(domain)
    github_slug = github_slug or _default_github_slug(company, domain)
    hibp_key = os.environ.get('HIBP_API_KEY')
    otx_key = os.environ.get('OTX_API_KEY')

    report = {
        'meta': {
            'preflight_version': PREFLIGHT_VERSION,
            'domain': domain,
            'company_search_term': company,
            'github_slug_tried': github_slug,
            'industry_hint': industry or None,
            'lead_email': lead_email or None,
            'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'elapsed_seconds': None,
            'timeout_per_probe': timeout,
        },
    }

    t_start = time.time()
    print(f'[preflight v{PREFLIGHT_VERSION}] {domain} — starting deterministic OSINT harvest', file=log)

    for key, fn, layer, label in _steps(domain, company, github_slug, hibp_key, timeout):
        t0 = time.time()
        try:
            out = fn()
            if not isinstance(out, dict):
                out = {'checked': False, 'error': 'probe_returned_non_dict'}
        except Exception as e:
            out = {'checked': False, 'error': f'unhandled: {e}'[:200]}
        out['_layer'] = layer
        out['_elapsed_ms'] = int((time.time() - t0) * 1000)
        report[key] = out
        status = 'OK' if out.get('checked') else 'SKIP/ERR'
        print(f'  [{status}] {label:<24} ({out["_elapsed_ms"]}ms)', file=log)

    # OTX runs in a second phase so it can reuse IPs the DNS probe just resolved.
    t0 = time.time()
    ipv4_list = (report.get('dns') or {}).get('a') or []
    try:
        otx_out = probe_otx(domain, ipv4_list, industry, otx_key, timeout=timeout)
        if not isinstance(otx_out, dict):
            otx_out = {'checked': False, 'error': 'probe_returned_non_dict'}
    except Exception as e:
        otx_out = {'checked': False, 'error': f'unhandled: {e}'[:200]}
    otx_out['_layer'] = 3
    otx_out['_elapsed_ms'] = int((time.time() - t0) * 1000)
    report['otx'] = otx_out
    status = 'OK' if otx_out.get('checked') else 'SKIP/ERR'
    print(f'  [{status}] {"AlienVault OTX":<24} ({otx_out["_elapsed_ms"]}ms)', file=log)

    # XposedOrNot — free public endpoints, no key. Runs unconditionally on the
    # domain; lead-email sub-calls fire only when the operator supplies one.
    t0 = time.time()
    try:
        xon_out = probe_xposedornot(domain, lead_email, timeout=timeout)
        if not isinstance(xon_out, dict):
            xon_out = {'checked': False, 'error': 'probe_returned_non_dict'}
    except Exception as e:
        xon_out = {'checked': False, 'error': f'unhandled: {e}'[:200]}
    xon_out['_layer'] = 3
    xon_out['_elapsed_ms'] = int((time.time() - t0) * 1000)
    report['xposedornot'] = xon_out
    status = 'OK' if xon_out.get('checked') else 'SKIP/ERR'
    print(f'  [{status}] {"XposedOrNot":<24} ({xon_out["_elapsed_ms"]}ms)', file=log)

    report['summary'] = _derive_summary(report)
    report['meta']['elapsed_seconds'] = round(time.time() - t_start, 2)

    # Audit-trail entries ready to drop into data_quality.sources_actually_checked[]
    report['sources_actually_checked_entries'] = _build_source_entries(report)
    return report


def _build_source_entries(report):
    """Shape probe results as sources_actually_checked[] entries. The skill
    reads this list at Layer 1 and merges it into the dossier's
    data_quality.sources_actually_checked[] before adding any Claude-side
    probes. This closes the audit-trail loop."""
    label_map = {
        'dns': 'DNS records (A/MX/TXT/SPF/DMARC)',
        'crtsh': 'crt.sh Certificate Transparency',
        'microsoft_tenant': 'Microsoft getuserrealm (Azure/Entra tenant resolution)',
        'web_archive': 'archive.org Wayback availability',
        'sec_edgar': 'SEC EDGAR full-text search',
        'usaspending': 'USAspending.gov federal awards',
        'ransomware_live': 'ransomware.live recent-victim feed',
        'github_org': 'GitHub organization API',
        'hibp': 'haveibeenpwned.com domain breach check',
        'web_fingerprint': 'Homepage HTTP-headers + body fingerprint (CDN/CMS/framework/analytics)',
        'security_txt': 'RFC 9116 security.txt presence (CISO governance signal)',
        'wikidata': 'Wikidata wbsearchentities + claims (founding/parent/HQ/industry)',
        'otx': 'AlienVault OTX (domain/IP pulse hits + optional sector pulses)',
        'xposedornot': 'XposedOrNot (free public API — domain & lead-email breach lookup)',
    }
    entries = []
    for key, label in label_map.items():
        probe = report.get(key) or {}
        entries.append({
            'source': label,
            'access_method': 'preflight',
            'layer': probe.get('_layer'),
            'yielded_signal': bool(probe.get('checked')),
        })
    return entries


def _normalize_domain(raw):
    """Strip scheme, www., trailing slash, path; lowercase."""
    s = raw.strip().lower()
    s = re.sub(r'^https?://', '', s)
    s = s.split('/', 1)[0]
    s = re.sub(r'^www\.', '', s)
    return s


def _domain_to_company_guess(domain):
    """Fallback company name when caller didn't provide one — use the
    registrable label capitalized (e.g., acme.com → Acme)."""
    label = domain.split('.')[0]
    return label.capitalize() if label else domain


# ============================================================================
#  CLI
# ============================================================================

def main(argv=None):
    _reconfigure_stdio_utf8()
    ap = argparse.ArgumentParser(
        description=f'ELISS preflight v{PREFLIGHT_VERSION} — deterministic OSINT harvest',
    )
    ap.add_argument('domain', help='Prospect domain (e.g., acme.com). Scheme and www. are stripped.')
    ap.add_argument('--company', help='Company legal name for SEC/USAspending search. Inferred from domain if omitted.')
    ap.add_argument('--github-org', help='Explicit GitHub org slug. Guessed from company/domain if omitted.')
    ap.add_argument('--industry',
                    help='Industry keyword (e.g., "financial services", "healthcare") used by the OTX '
                         'sector pulse search. When omitted, OTX still runs domain + IP lookups but skips '
                         'the sector search. Ignored if OTX_API_KEY is not set.')
    ap.add_argument('--lead-email',
                    help='Lead contact email (e.g., "founder@acme.com"). When supplied, the XposedOrNot '
                         'probe runs the per-email breach check + analytics against free public endpoints '
                         '(no API key needed). The domain-level XposedOrNot lookup runs regardless.')
    ap.add_argument('--output', '-o', help='Output JSON path. Default: preflight_<domain>.json in cwd.')
    ap.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_SECS,
                    help=f'Per-probe timeout in seconds. Default: {DEFAULT_TIMEOUT_SECS}')
    ap.add_argument('--quiet', '-q', action='store_true', help='Suppress per-probe stderr log.')
    args = ap.parse_args(argv)

    log = open(os.devnull, 'w') if args.quiet else sys.stderr
    try:
        report = run_preflight(
            args.domain,
            company=args.company,
            github_slug=args.github_org,
            industry=args.industry,
            lead_email=args.lead_email,
            timeout=args.timeout,
            log=log,
        )
    finally:
        if args.quiet:
            log.close()

    domain = report['meta']['domain']
    out_path = Path(args.output) if args.output else Path(f'preflight_{domain.replace(".", "_")}.json')
    out_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    if not args.quiet:
        summary = report['summary']
        print(
            f'[preflight] wrote {out_path} — {summary["probes_yielded_signal"]}/14 probes yielded signal '
            f'in {report["meta"]["elapsed_seconds"]}s',
            file=sys.stderr,
        )

    # Print the path on stdout so shell callers can capture it.
    print(str(out_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
