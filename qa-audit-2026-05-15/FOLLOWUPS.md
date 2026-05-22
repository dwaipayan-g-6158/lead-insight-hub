# QA Audit Follow-ups — items not fully fixable in this repo

The 2026-05-15 QA audit produced 23 findings. 20 were patched in the
2026-05-15 fix batch. The 3 below need infrastructure-side changes
outside this repo's source tree.

## P3-05 — Dossier double-escaped smart quotes (upstream generator)

**What we did:** added a render-time cleanup pass in
`app/src/components/LeadDetailPage.tsx::substituteTokens` that collapses
adjacent `""` / `''` / `““` / `””` pairs before the dossier is injected
into the iframe srcdoc, plus a server-side cleanup in
`functions/api/lib/parser.js::fixDoubledQuotes` for extracted signal
detail strings. Both run on existing rows at read time, so no
backfill is needed.

**What's still needed:** the **upstream ELISS dossier generator**
(outside this repo — the pipeline that authors the HTML reports) is
the root cause. It HTML-escapes once during template rendering and a
second time during the final emit pass, producing `&ldquo;&ldquo;…&rdquo;&rdquo;`
that decodes back to `““…””`. The right fix is to audit that
pipeline's escape boundaries and ensure each string crosses at most
one escape pass.

**Where to look:** wherever the dossier generator's objection-handler
and email-template sections build their strings — likely a Jinja /
Handlebars template fed by an LLM response that already contains
encoded entities.

## P3-06 — Modern HTTP not used on all critical assets (~110 ms LCP)

**What we did:** nothing in code — the protocol negotiation happens at
the Catalyst Slate edge, not in our bundle.

**What's still needed:** verify the Slate hosting layer negotiates
HTTP/2 (or HTTP/3) ALPN for all asset MIME types served from
`app/dist/`. To check:

```
curl -sI -v --http2 https://lead-insight-hub-60066539659.development.catalystserverless.in/app/assets/index-*.js 2>&1 | grep -E '^(>|<|\*) '
```

Look for `* ALPN, server accepted to use h2`. If h1.1 wins, raise
with Catalyst support — Slate edge config to force HTTP/2 may need
explicit enablement on the project.

## P3-07 — Cache headers leave ~289 KB on the table (~100 ms LCP)

**What we did:** nothing in code.

**What's still needed:** for assets matching
`app/dist/assets/*-[hash].{js,css}` (which Vite hashes deterministically),
set:

```
Cache-Control: public, max-age=31536000, immutable
```

Catalyst Slate exposes per-route headers via the project console
(Slate → Routes → custom headers) or via a `slate-config.json` /
`_headers` file at the dist root depending on the Slate version
deployed to this project. Try in this order:

1. Open the Catalyst Console for project `31210000000133001` →
   Slate → look for "Headers" or "Cache" config tab.
2. If a `_headers` file is honored, add at `app/dist/_headers`:
   ```
   /assets/*
     Cache-Control: public, max-age=31536000, immutable
   /*.html
     Cache-Control: no-cache
   ```
3. If neither works, file a support request asking Slate to apply
   `immutable` Cache-Control to fingerprinted asset paths.

## P2-11 — Per-widget skeleton on slow connections (partial)

**What we did:** split `loading` into independent `statsLoading` and
`hotLoading` flags so the dashboard no longer waits for the slower
query before showing anything. Added an inline skeleton inside
`WidgetTopOpportunities` for the hotLoading-only state.

**What's still needed (optional, P3 effort):** per-widget skeleton
states for the remaining 15 widgets that read from `stats`. Currently
they all gate behind the same `statsLoading` flag — when that
resolves, they all populate at once. Slicing the stats response into
per-widget pieces (e.g. `/stats/tiers`, `/stats/icp-ladder`, etc.)
would allow staggered loading but is a meaningful refactor.

## P3-09 — Lazy mount below-fold dashboard widgets

**What we did:** nothing in code.

**What's still needed (optional, P3 effort):** the dashboard
eagerly mounts all 17 widgets even though only ~5 are above the fold
on a 1440×900 viewport. An `IntersectionObserver`-based lazy mount
would cut initial DOM size by ~60% and reduce render time on weaker
devices.

Sketch:

```tsx
function LazyMount({ children, rootMargin = "200px" }: { ... }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || visible) return;
    const io = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setVisible(true),
      { rootMargin },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [visible, rootMargin]);
  return <div ref={ref}>{visible ? children : <Skeleton className="h-56 rounded-xl" />}</div>;
}
```

Wrap each widget in `<LazyMount>` inside `DraggableGrid`. Skip the
wrapper for the first 5 widgets so the above-fold experience is
unchanged.
