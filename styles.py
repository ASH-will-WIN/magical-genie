"""Central CSS + small visual-component helpers for the signal-detection
theme. Colors here must match .streamlit/config.toml (native theming covers
fonts/panel colors; this module covers what config.toml can't reach: the
signal-strength bar and the Venn diagram)."""
import streamlit as st

_BUCKET_COLORS = {
    "approved": "#4FA88A",
    "needs_review": "#E8AA4C",
    "rejected": "#C4634B",
    "dropped_at_prefilter": "#C4634B",
}

_TRACK_COLOR = "#242A38"

_BASE_CSS = """
<style>
.gs-mono {
    font-family: 'JetBrains Mono', monospace;
}
.gs-signal-track {
    width: 100%%;
    height: 8px;
    background: %(track)s;
    border-radius: 999px;
    overflow: hidden;
}
.gs-signal-fill {
    height: 100%%;
    border-radius: 999px;
}
</style>
""" % {"track": _TRACK_COLOR}


def inject_base_styles() -> None:
    """Call once, from the app entrypoint, before any page renders."""
    st.html(_BASE_CSS)


def signal_bar_html(score: int, bucket: str) -> str:
    """A filled horizontal 0-100 signal-strength bar, colored by bucket."""
    clamped = max(0, min(100, score))
    color = _BUCKET_COLORS.get(bucket, _TRACK_COLOR)
    return (
        f'<div class="gs-signal-track">'
        f'<div class="gs-signal-fill" style="width:{clamped}%; background:{color};"></div>'
        f'</div>'
        f'<span class="gs-mono" style="font-size:0.8rem; color:{color};">{clamped}/100</span>'
    )


def venn_svg(article_only: int, icp_only: int, blended: int, width: int = 360, height: int = 200) -> str:
    """Two overlapping circles: Article Theme (left) ∩ Reinvent ICP (right),
    labeled with candidate counts per region -- article-only, icp-only,
    blended (the overlap, i.e. approved-relevant candidates)."""
    left_cx, right_cx, cy, r = width * 0.38, width * 0.62, height * 0.55, width * 0.24
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <circle cx="{left_cx}" cy="{cy}" r="{r}" fill="#E8AA4C" fill-opacity="0.28" stroke="#E8AA4C" stroke-width="1.5" />
  <circle cx="{right_cx}" cy="{cy}" r="{r}" fill="#4FA88A" fill-opacity="0.28" stroke="#4FA88A" stroke-width="1.5" />
  <text x="{left_cx - r * 0.55}" y="{cy}" fill="#F2F3F5" font-family="'JetBrains Mono', monospace" font-size="20" text-anchor="middle">{article_only}</text>
  <text x="{right_cx + r * 0.55}" y="{cy}" fill="#F2F3F5" font-family="'JetBrains Mono', monospace" font-size="20" text-anchor="middle">{icp_only}</text>
  <text x="{(left_cx + right_cx) / 2}" y="{cy}" fill="#F2F3F5" font-family="'JetBrains Mono', monospace" font-size="20" text-anchor="middle">{blended}</text>
  <text x="{left_cx - r * 0.55}" y="{cy + 22}" fill="#8B93A7" font-family="Inter, sans-serif" font-size="11" text-anchor="middle">article-only</text>
  <text x="{right_cx + r * 0.55}" y="{cy + 22}" fill="#8B93A7" font-family="Inter, sans-serif" font-size="11" text-anchor="middle">icp-only</text>
  <text x="{(left_cx + right_cx) / 2}" y="{cy + r + 20}" fill="#8B93A7" font-family="Inter, sans-serif" font-size="11" text-anchor="middle">blended</text>
</svg>
"""


def mono(value) -> str:
    """Wrap an ad-hoc numeric/data value in the monospace class, for use
    inside st.markdown(..., unsafe_allow_html=True) contexts that
    config.toml's codeFont doesn't reach (e.g. st.metric values)."""
    return f'<span class="gs-mono">{value}</span>'