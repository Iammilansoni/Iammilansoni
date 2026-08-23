#!/usr/bin/env python3
"""
Generate assets/stats.svg from the GitHub API.

Committed static SVG rather than a live third-party widget: the public
github-readme-stats instance is paused (HTTP 503 DEPLOYMENT_PAUSED) and
streak-stats intermittently exceeds GitHub's camo fetch timeout. A file in
the repo always renders.

Run: GITHUB_TOKEN=... python scripts/gen_stats.py
"""
import collections
import json
import os
import urllib.request

USER = "Iammilansoni"
ACCENT = "#6C63FF"

# Deliberately omits stars and followers: they are not the signal here.
QUERY = """
{ user(login: "%s") {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
        edges { size node { name color } } } }
    }
    contributionsCollection { totalCommitContributions }
    pullRequests(states: MERGED) { totalCount }
} }
""" % USER

LANG_FALLBACK = {
    "TypeScript": "#3178c6", "Python": "#3572A5", "JavaScript": "#f1e05a",
    "Shell": "#89e051", "CSS": "#663399", "HTML": "#e34c26",
}


def fetch():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY}).encode(),
        headers={"Authorization": "bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit("GraphQL error: %s" % body["errors"])
    return body["data"]["user"]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build(user):
    repos = user["repositories"]
    langs = collections.Counter()
    colors = {}
    for node in repos["nodes"]:
        for edge in node["languages"]["edges"]:
            name = edge["node"]["name"]
            langs[name] += edge["size"]
            colors.setdefault(name, edge["node"]["color"] or LANG_FALLBACK.get(name, "#888"))

    total = sum(langs.values()) or 1
    top = langs.most_common(5)

    tiles = [
        (f'{user["contributionsCollection"]["totalCommitContributions"]:,}', "commits, past year"),
        (str(user["pullRequests"]["totalCount"]), "pull requests merged"),
        (str(repos["totalCount"]), "public repositories"),
    ]

    W, H = 860, 232
    BAR_X, BAR_Y, BAR_W, BAR_H = 34, 92, 792, 15

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="GitHub activity for {USER}">',
        "<style>",
        "  .bg{fill:#ffffff;stroke:#d8dee4}",
        "  .h{fill:#1f2328;font:600 15px -apple-system,Segoe UI,Helvetica,Arial,sans-serif}",
        f"  .n{{fill:{ACCENT};font:700 27px -apple-system,Segoe UI,Helvetica,Arial,sans-serif}}",
        "  .l{fill:#59636e;font:400 12px -apple-system,Segoe UI,Helvetica,Arial,sans-serif}",
        "  .t{fill:#1f2328;font:400 12.5px -apple-system,Segoe UI,Helvetica,Arial,sans-serif}",
        "  .rule{stroke:#d8dee4}",
        "  @media (prefers-color-scheme: dark){",
        "    .bg{fill:#0d1117;stroke:#30363d}",
        "    .h,.t{fill:#e6edf3} .l{fill:#9198a1} .rule{stroke:#30363d}",
        "  }",
        "</style>",
        f'<rect class="bg" x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" stroke-width="1"/>',
        f'<text class="h" x="{BAR_X}" y="40">Language mix</text>',
        f'<text class="l" x="{BAR_X}" y="63">across {repos["totalCount"]} public repositories, weighted by bytes</text>',
    ]

    # Stacked language bar, rounded via a clip path.
    out.append(f'<clipPath id="r"><rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" '
               f'height="{BAR_H}" rx="{BAR_H/2}"/></clipPath>')
    out.append('<g clip-path="url(#r)">')
    x = float(BAR_X)
    for name, size in top:
        w = BAR_W * size / total
        out.append(f'<rect x="{x:.2f}" y="{BAR_Y}" width="{w:.2f}" height="{BAR_H}" '
                   f'fill="{colors.get(name, "#888")}"/>')
        x += w
    if x < BAR_X + BAR_W:  # everything outside the top 5
        out.append(f'<rect x="{x:.2f}" y="{BAR_Y}" width="{BAR_X + BAR_W - x:.2f}" '
                   f'height="{BAR_H}" fill="#8b949e"/>')
    out.append("</g>")

    # Legend
    lx = float(BAR_X)
    for name, size in top:
        pct = 100.0 * size / total
        out.append(f'<circle cx="{lx+5:.1f}" cy="{BAR_Y+40}" r="5" fill="{colors.get(name, "#888")}"/>')
        out.append(f'<text class="t" x="{lx+16:.1f}" y="{BAR_Y+44}">{esc(name)} '
                   f'<tspan class="l">{pct:.1f}%</tspan></text>')
        lx += 34 + 7.1 * len(name) + 34

    out.append(f'<line class="rule" x1="{BAR_X}" y1="176" x2="{W-BAR_X}" y2="176" stroke-width="1"/>')

    for i, (value, label) in enumerate(tiles):
        cx = BAR_X + i * 264
        out.append(f'<text class="n" x="{cx}" y="208">{esc(value)}</text>')
        out.append(f'<text class="l" x="{cx + 12 + 16 * len(value)}" y="208">{esc(label)}</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    svg = build(fetch())
    os.makedirs("assets", exist_ok=True)
    with open("assets/stats.svg", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print("wrote assets/stats.svg (%d bytes)" % len(svg))
