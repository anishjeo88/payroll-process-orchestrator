"""Shared visual theme: the gradient/geometric banner used across the
capstone documents (Checkpoints 1-6), plus the global CSS that re-skins
Streamlit's own chrome (sidebar, buttons, cards) to match.

Import `inject_global_css()` once per page and `render_banner(...)` in place
of a plain `st.title()` call.

The banner is built as an SVG but displayed as a rendered PNG via
`st.image()`, not injected as raw HTML. Two other approaches were tried and
both failed silently, worth recording so nobody re-tries them:
- `st.markdown(svg, unsafe_allow_html=True)` - this Streamlit version's
  Markdown renderer ends an HTML block at the first blank line
  (CommonMark's HTML-block rule) and re-enters Markdown text mode for
  everything after it, dropping every tag past that point with no error.
- `st.html(svg)` - sanitised with DOMPurify, which strips the entire <svg>
  (confirmed via devtools: only Streamlit's own icon svgs survive).
`st.image()` sidesteps sanitisation entirely since it's not HTML at all.
Each unique (title, subtitle) combination is rendered once via `qlmanage`
(macOS QuickLook) and cached to disk under interface/assets/banners/ - the
same SVG-to-PNG pipeline used throughout this project's own diagrams.
"""

from __future__ import annotations

import hashlib
import html
import subprocess
import tempfile
from pathlib import Path

import streamlit as st

TEAL = "#2f8f96"
BLUE = "#1c4f8f"
NAVY = "#131d3b"
LIGHT_BLUE = "#4fb0d9"
CREAM = "#f6f1e4"

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "banners"

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Playfair+Display:wght@700;800&family=Inter:wght@400;500;600;700&display=swap');"
)


def inject_global_css() -> None:
    """Re-skins Streamlit's own chrome to match the banner palette. Safe to
    call on every page - repeat <style> tags are harmless. Confirmed working
    via st.html (unlike the banner, a plain <style> tag survives DOMPurify)."""
    st.html(f"""
    <style>
    {_FONT_IMPORT}

    html, body, p, span, div, label, li {{
        font-family: 'Inter', -apple-system, sans-serif;
    }}
    /* Streamlit's own icon glyphs (the sidebar collapse arrow, etc.) are
       ligature text that only renders as an icon under this specific font -
       the broad rule above would otherwise show its literal name
       ("keyboard_double_arrow_left") as plain text instead of an arrow. */
    [data-testid="stIconMaterial"] {{
        font-family: 'Material Symbols Rounded' !important;
    }}
    h1, h2, h3 {{
        font-family: 'Playfair Display', Georgia, serif !important;
        color: {NAVY} !important;
    }}

    /* Tighten the gap st.image's default margin leaves below the banner */
    div[data-testid="stImage"] {{
        margin-bottom: -14px;
    }}

    section[data-testid="stSidebar"] {{
        background: {CREAM};
        border-right: 1px solid #e4dcc8;
    }}
    section[data-testid="stSidebar"] * {{
        color: {NAVY} !important;
    }}

    .stButton > button, .stDownloadButton > button {{
        background: linear-gradient(135deg, {TEAL}, {BLUE});
        color: #ffffff;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: transform 0.08s ease, box-shadow 0.15s ease;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(28, 79, 143, 0.35);
        color: #ffffff;
    }}

    div[data-testid="stMetric"] {{
        background: {CREAM};
        border: 1px solid #e4dcc8;
        border-radius: 10px;
        padding: 12px 16px;
    }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 12px !important;
        border: 1px solid #e4dcc8 !important;
    }}

    details {{
        border-radius: 10px !important;
        border: 1px solid #e4dcc8 !important;
    }}
    </style>
    """)


def _banner_height(subtitle_lines: list[str]) -> int:
    return 150 + 26 * max(len(subtitle_lines) - 1, 0)


def _banner_svg(title: str, subtitle_lines: list[str]) -> str:
    # QuickLook's SVG renderer parses strictly as XML - unlike a browser, it
    # won't tolerate a bare '&' in text content, so title/subtitles must be
    # properly escaped, not inserted as raw strings.
    title = html.escape(title)
    subtitle_lines = [html.escape(line) for line in subtitle_lines]

    height = _banner_height(subtitle_lines)
    sub_y_start = 118
    subtitle_svg = "".join(
        f'<text x="56" y="{sub_y_start + i * 26}" font-family="Inter, sans-serif" '
        f'font-size="17" fill="#f2eee2">{line}</text>'
        for i, line in enumerate(subtitle_lines)
    )
    rule_y = 92
    return f"""<svg viewBox="0 0 1200 {height}" xmlns="http://www.w3.org/2000/svg"
     style="width:100%; height:auto; display:block; border-radius:14px;"
     role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bannerGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{TEAL}"/>
      <stop offset="55%" stop-color="#2a86b8"/>
      <stop offset="100%" stop-color="{BLUE}"/>
    </linearGradient>
    <clipPath id="bannerClip">
      <rect x="0" y="0" width="1200" height="{height}" rx="14"/>
    </clipPath>
  </defs>
  <g clip-path="url(#bannerClip)">
    <rect x="0" y="0" width="1200" height="{height}" fill="url(#bannerGrad)"/>
    <polygon points="1060,0 1200,0 1200,130" fill="{NAVY}" opacity="0.9"/>
    <polygon points="965,0 1075,0 965,95" fill="{LIGHT_BLUE}" opacity="0.85"/>
    <path d="M 985,55 A 55,55 0 0 1 1040,0" fill="none" stroke="{CREAM}" stroke-width="16" opacity="0.9"/>
    <circle cx="1140" cy="{height * 0.52:.0f}" r="24" fill="{CREAM}" opacity="0.95"/>
    <path d="M 1055,{height - 10} A 42,42 0 0 1 1097,{height - 52}" fill="none" stroke="{CREAM}" stroke-width="13" opacity="0.85"/>
    <polygon points="1140,{height} 1200,{height - 45} 1200,{height} " fill="{NAVY}" opacity="0.9"/>
    <polygon points="1040,{height} 1105,{height - 38} 1105,{height}" fill="{LIGHT_BLUE}" opacity="0.8"/>
  </g>
  <text x="56" y="60" font-family="'Playfair Display', Georgia, serif" font-weight="800" font-size="40" fill="#fbf8ef">{title}</text>
  <line x1="56" y1="{rule_y}" x2="640" y2="{rule_y}" stroke="#f2eee2" stroke-width="1.5" opacity="0.8"/>
  {subtitle_svg}
</svg>"""


def _build_png(svg_text: str, viewbox_w: int, viewbox_h: int, out_path: Path) -> bool:
    """Renders `svg_text` to `out_path` via macOS QuickLook. Returns False
    (rather than raising) on any failure, so a missing qlmanage on a
    non-macOS machine degrades to no banner rather than a crashed page.

    QuickLook's `-t` thumbnail mode always outputs a *square* canvas,
    letterboxing non-square content inside it rather than cropping to its
    actual aspect ratio - harmless for a source that already fills to its
    own edges, but this banner is wide and short (1200x~150-200), so left
    uncropped the file becomes mostly transparent padding above and below
    a thin strip of actual banner. st.image's use_container_width then
    stretches that square file to the container's full width, forcing an
    equally huge display height. Cropping back to the known content
    region (computed from the source viewBox, not detected from pixels)
    fixes this without guessing."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            svg_path = tmp_dir / "banner.svg"
            svg_path.write_text(svg_text)
            subprocess.run(
                ["qlmanage", "-t", "-s", "1600", "-o", str(tmp_dir), str(svg_path)],
                capture_output=True, timeout=30, check=True,
            )
            produced = tmp_dir / "banner.svg.png"
            if not produced.exists():
                return False

            from PIL import Image

            with Image.open(produced) as img:
                canvas = img.size[0]  # square: width == height
                scale = canvas / max(viewbox_w, viewbox_h)
                content_w = viewbox_w * scale
                content_h = viewbox_h * scale
                # Top-left anchored, not centered - confirmed by inspecting
                # an uncropped thumbnail directly rather than assuming.
                cropped = img.crop((0, 0, round(content_w), round(content_h)))
                out_path.parent.mkdir(parents=True, exist_ok=True)
                cropped.save(out_path)
            return True
    except Exception:
        return False


def render_banner(title: str, subtitle_lines: list[str] | None = None) -> None:
    """Renders the branded gradient banner in place of st.title(). Each
    unique (title, subtitle) text is rendered once and cached to disk -
    keep genuinely dynamic text (a live timestamp, an API-key status line)
    as a plain st.caption() below the banner instead of baking it in here,
    or every value would mint a new cached PNG forever."""
    inject_global_css()
    subtitle_lines = subtitle_lines or []

    key = hashlib.sha1((title + "|" + "|".join(subtitle_lines)).encode()).hexdigest()[:16]
    png_path = ASSETS_DIR / f"{key}.png"

    if not png_path.exists():
        _build_png(_banner_svg(title, subtitle_lines), 1200, _banner_height(subtitle_lines), png_path)

    if png_path.exists():
        st.image(str(png_path), use_container_width=True)
    else:
        st.title(title)
        for line in subtitle_lines:
            st.caption(line)
