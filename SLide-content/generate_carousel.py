#!/usr/bin/env python3
"""
Instagram Carousel Generator — Slidez
Slide types:
  hook_cover   → Full-bleed image, huge two-tone bold text, no header (slide 1)
  regular      → Dark/light card with profile header + tweet text
  testimonial  → Review card with avatar, stars, quote
  messaging    → iOS iMessage / Instagram DM conversation (imessage | imessage_dark | dm)
"""

import argparse, json, os, sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
except ImportError:
    print("❌  pip install Pillow"); sys.exit(1)
try:
    import requests
except ImportError:
    print("❌  pip install requests"); sys.exit(1)

# ── Canvas ─────────────────────────────────────────────────────────────────────
W, H = 1080, 1350

# ── Themes ─────────────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#0a0a0a", "text": "#ffffff", "handle": "#888888",
        "divider": "#2a2a2a", "card_bg": "#141414", "card_border": "#2a2a2a",
        "star": "#f5c518", "reviewer_name": "#ffffff", "reviewer_sub": "#888888",
    },
    "light": {
        "bg": "#ffffff", "text": "#0a0a0a", "handle": "#666666",
        "divider": "#e0e0e0", "card_bg": "#f7f7f7", "card_border": "#e0e0e0",
        "star": "#f5a623", "reviewer_name": "#0a0a0a", "reviewer_sub": "#888888",
    },
}

# ── Hook cover accent colours ──────────────────────────────────────────────────
ACCENT_COLORS = {
    "yellow": "#FFD700",
    "cyan":   "#00E5FF",
    "orange": "#FF6B00",
    "pink":   "#FF2D78",
    "green":  "#00FF88",
    "white":  "#FFFFFF",
}

# ── Layout ─────────────────────────────────────────────────────────────────────
PAD           = 72
HEADER_TOP    = 60
HEADER_H      = 130
AV            = 72
AV_BORDER     = 3
NAME_SZ       = 28
HANDLE_SZ     = 22
TWEET_SZ      = 38
DIV_H         = 2
DIV_GAP       = 32
IMG_RADIUS    = 20
MAX_IMG_H     = 480
MAX_TW        = W - PAD * 2
LINE_SP       = 1.45
# Testimonial
RAV           = 110
Q_SZ          = 34
RN_SZ         = 28
RS_SZ         = 21
STAR_SZ       = 34
CARD_R        = 24
CARD_PAD      = 48


# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _fonts_dir():
    return Path(__file__).parent / "fonts"

def _find_font(keywords, exts=(".ttf", ".otf")):
    """
    Recursively search fonts/ and all subfolders.
    Returns the first file whose name contains ALL keywords (case-insensitive).
    """
    fd = _fonts_dir()
    if not fd.exists():
        return None
    kw = [k.lower() for k in keywords]
    for f in sorted(fd.rglob("*")):
        if f.suffix.lower() in exts:
            name = f.name.lower()
            if all(k in name for k in kw):
                return str(f)
    return None

def _find_any(groups, exts=(".ttf", ".otf")):
    """Try each keyword group in order, return first match."""
    for g in groups:
        r = _find_font(g, exts)
        if r:
            return r
    return None

def font(size, bold=False, style="default"):
    """
    Font priority per style:

    hook  → House Sans Condensed Black (your font, ultra-bold condensed)
              → Romana Demi (serif punch — good for mixed caps)
              → Bebas Neue / Anton / Oswald Bold
              → system bold

    sub   → Romana Demi (elegant contrast to the hook)
              → House Sans Condensed Black
              → Oswald Regular / system

    default (tweet cards)
              bold  → Oswald Bold → Montserrat Bold → system bold
              plain → Oswald Regular → Montserrat Regular → system
    """
    if style == "hook":
        path = _find_any([
            ["house", "condensed", "black"],
            ["house", "black"],
            ["housesans", "black"],
            ["house", "condensed"],
            ["house", "sans"],          # any House Sans variant
            ["romana", "demi"],
            ["romana"],
            ["bebas"],
            ["anton"],
            ["oswald", "bold"],
        ])
        fallbacks = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]

    elif style == "sub":
        path = _find_any([
            ["romana", "demi"],
            ["romana"],
            ["house", "condensed", "black"],
            ["house", "sans"],
            ["oswald", "regular"],
            ["oswald"],
            ["montserrat", "regular"],
        ])
        fallbacks = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]

    else:
        if bold:
            path = _find_any([
                ["oswald", "bold"],
                ["montserrat", "bold"],
                ["house", "sans"],
                ["bebas"],
            ])
            fallbacks = [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        else:
            path = _find_any([
                ["oswald", "regular"],
                ["montserrat", "regular"],
                ["oswald"],
                ["montserrat"],
            ])
            fallbacks = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]

    for p in ([path] if path else []) + fallbacks:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def circle_mask(s):
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).ellipse([0, 0, s-1, s-1], fill=255)
    return m

def round_corners(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, *img.size], radius=r, fill=255)
    out = img.convert("RGBA"); out.putalpha(m)
    return out

def dl(url, dst):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        open(dst, "wb").write(r.content)
        return dst
    except Exception as e:
        print(f"  ⚠️  {url}: {e}"); return None

def load_img(path, cdir):
    if not path: return None
    if path.startswith("http"):
        local = cdir / "reference" / Path(path).name
        path = dl(path, str(local)) or ""
    elif not os.path.isabs(path):
        path = str(cdir / path)
    if not path or not os.path.exists(path):
        print(f"  ⚠️  not found: {path}"); return None
    return Image.open(path).convert("RGBA")

def wrap(text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    d = ImageDraw.Draw(Image.new("RGB", (1,1)))
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def measure(lines, fnt):
    d = ImageDraw.Draw(Image.new("RGB", (1,1)))
    lh = int(fnt.size * LINE_SP)
    mw = max((int(d.textlength(l, font=fnt)) for l in lines), default=0)
    return mw, lh * len(lines)

def draw_block(draw, lines, fnt, color, x, y, align="left", maxw=MAX_TW):
    lh = int(fnt.size * LINE_SP)
    d  = ImageDraw.Draw(Image.new("RGB", (1,1)))
    for line in lines:
        lw = int(d.textlength(line, font=fnt))
        lx = x + (maxw - lw)//2 if align == "center" else x
        draw.text((lx, y), line, font=fnt, fill=color)
        y += lh
    return y

def badge(draw, cx, cy, r=12):
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#1d9bf0")
    draw.line([(cx-r*.45, cy),(cx-r*.1, cy+r*.4),(cx+r*.45, cy-r*.35)], fill="white", width=max(2, r//5))

def brand_header(canvas, draw, profile, theme, cdir, y=None):
    if y is None: y = HEADER_TOP
    tc  = rgb(theme["text"]); hc = rgb(theme["handle"])
    fn  = font(NAME_SZ, bold=True); fh = font(HANDLE_SZ)
    ax, ay = PAD, y
    logo = load_img(profile.get("headshot_path",""), cdir) if profile.get("headshot_path") else None
    if logo:
        logo = ImageOps.fit(logo, (AV, AV), Image.LANCZOS)
        m = circle_mask(AV); bs = AV + AV_BORDER*2
        bi = Image.new("RGB", (bs,bs), tc); bm = circle_mask(bs)
        canvas.paste(bi, (ax-AV_BORDER, ay-AV_BORDER), bm)
        canvas.paste(logo, (ax, ay), m)
    else:
        draw.ellipse([ax, ay, ax+AV, ay+AV], fill="#1d9bf0")
        draw.text((ax+AV//2-9, ay+AV//2-18), "S", font=font(32,True), fill="white")
    # Single-line header: Name (bold)  ✓  @handle — all vertically centred with avatar
    row_y = ay + (AV - NAME_SZ) // 2   # vertically centre text within avatar height
    nx = ax + AV + 20
    name = profile.get("display_name", "Slidez")
    draw.text((nx, row_y), name, font=fn, fill=tc)
    nw = int(draw.textlength(name, font=fn))
    cx = nx + nw + 14
    if profile.get("verified", True):
        badge(draw, cx + 13, row_y + NAME_SZ // 2, r=13)
        cx += 13*2 + 10
    handle_y = row_y + (NAME_SZ - HANDLE_SZ) // 2
    draw.text((cx, handle_y), profile.get("handle", "@slidez"), font=fh, fill=hc)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE TYPE 1 — Hook Cover (magazine style, full-bleed image, huge text)
# Supports:
#   hook_text    : "INSTAGRAM DMs {JUST} CHANGED"  — {} = accent colour
#   subtitle     : "Claude now replies automatically"
#                  first word gets accent colour automatically
#   accent_color : yellow | cyan | orange | pink | green
#   icon_paths   : ["./reference/icon1.png", "./reference/icon2.png"]
#                  floating icons overlaid on the image (like the IG + Claude logos)
# ══════════════════════════════════════════════════════════════════════════════

def _fill_canvas_with_image(canvas, img):
    img = img.convert("RGB")
    ar_c = W / H; ar_i = img.width / img.height
    if ar_i > ar_c: nh = H; nw = int(nh * ar_i)
    else:            nw = W; nh = int(nw / ar_i)
    img = img.resize((nw, nh), Image.LANCZOS)
    ox = (nw - W)//2; oy = (nh - H)//2
    canvas.paste(img.crop((ox, oy, ox+W, oy+H)), (0, 0))
    return canvas

def _parse_segments(raw):
    """Split 'SOME {ACCENT} WORDS' into [(word, is_accent), ...]"""
    import re
    segs = []
    for tok in re.split(r'(\{[^}]+\})', raw):
        if tok.startswith("{") and tok.endswith("}"):
            for w in tok[1:-1].split(): segs.append((w, True))
        else:
            for w in tok.split():
                if w: segs.append((w, False))
    return segs

def _wrap_segments(segs, fnt, maxw):
    """Word-wrap a list of (word, is_accent) into lines, preserving accent flags."""
    d = ImageDraw.Draw(Image.new("RGB", (1,1)))
    sw = int(d.textlength(" ", font=fnt))
    lines, cur, cw = [], [], 0
    for word, acc in segs:
        ww = int(d.textlength(word, font=fnt))
        needed = ww if not cur else ww + sw
        if cur and cw + needed > maxw:
            lines.append(cur); cur = [(word, acc)]; cw = ww
        else:
            cur.append((word, acc)); cw += needed
    if cur: lines.append(cur)
    return lines

def _draw_accent_line(draw, line_words, fnt, accent_color, y, maxw=W):
    """Draw one line of (word, is_accent) pairs, centered."""
    d  = ImageDraw.Draw(Image.new("RGB", (1,1)))
    sw = int(d.textlength(" ", font=fnt))
    lw = sum(int(d.textlength(w, font=fnt)) for w, _ in line_words) + sw*(len(line_words)-1)
    x  = (maxw - lw) // 2
    for i, (word, acc) in enumerate(line_words):
        draw.text((x, y), word, font=fnt, fill=accent_color if acc else (255,255,255))
        x += int(d.textlength(word, font=fnt)) + (sw if i < len(line_words)-1 else 0)

def _draw_subtitle(draw, text, fnt_sub, accent_color, y):
    """Draw subtitle: first word in accent colour, rest in light grey. Centered."""
    d     = ImageDraw.Draw(Image.new("RGB", (1,1)))
    words = text.split()
    if not words: return
    # Build (word, color) list
    pairs = [(words[0], accent_color)] + [(w, (210,210,210)) for w in words[1:]]
    sw    = int(d.textlength(" ", font=fnt_sub))
    total = sum(int(d.textlength(w, font=fnt_sub)) for w, _ in pairs) + sw*(len(pairs)-1)
    x     = (W - total) // 2
    for i, (word, col) in enumerate(pairs):
        draw.text((x, y), word, font=fnt_sub, fill=col)
        x += int(d.textlength(word, font=fnt_sub)) + (sw if i < len(pairs)-1 else 0)

def _overlay_icons(canvas, icon_paths, cdir):
    """
    Overlay up to 3 circular icons on the image area.
    Icons are placed in a row ~30% from top, spread across the canvas.
    """
    icons = [load_img(p, cdir) for p in icon_paths if p]
    icons = [i for i in icons if i is not None]
    if not icons: return canvas

    ICON_SIZE  = 160
    ICON_Y     = int(H * 0.12)
    positions  = {
        1: [W//2 - ICON_SIZE//2],
        2: [int(W*0.28) - ICON_SIZE//2, int(W*0.72) - ICON_SIZE//2],
        3: [int(W*0.18), W//2 - ICON_SIZE//2, int(W*0.82) - ICON_SIZE],
    }
    xs = positions.get(len(icons), positions[2])

    canvas = canvas.convert("RGBA")
    for icon, x in zip(icons, xs):
        icon = icon.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
        # White circle background
        bg = Image.new("RGBA", (ICON_SIZE+16, ICON_SIZE+16), (0,0,0,0))
        ImageDraw.Draw(bg).ellipse([0,0,ICON_SIZE+15,ICON_SIZE+15], fill=(255,255,255,230))
        canvas.paste(bg, (x-8, ICON_Y-8), bg)
        mask = circle_mask(ICON_SIZE)
        canvas.paste(icon, (x, ICON_Y), mask)

    return canvas.convert("RGB")

def render_hook_cover(slide, profile, theme, cdir):
    canvas = Image.new("RGB", (W, H), (10, 10, 10))

    # ── Background image ──────────────────────────────────────────────────────
    bg = load_img(slide.get("image_path"), cdir)
    if bg: canvas = _fill_canvas_with_image(canvas, bg)

    # ── Floating icons (optional) ─────────────────────────────────────────────
    icon_paths = slide.get("icon_paths", [])
    if icon_paths:
        canvas = _overlay_icons(canvas, icon_paths, cdir)

    # ── Dark gradient (bottom 60%) ────────────────────────────────────────────
    grad      = Image.new("RGBA", (W, H), (0,0,0,0))
    gd        = ImageDraw.Draw(grad)
    gstart    = int(H * 0.28)
    for gy in range(gstart, H):
        t = (gy - gstart) / (H - gstart)
        gd.line([(0,gy),(W,gy)], fill=(0,0,0, int(230 * min(t*1.5, 1.0))))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), grad).convert("RGB")

    draw         = ImageDraw.Draw(canvas)
    raw_text     = slide.get("hook_text", "YOUR HOOK HERE")
    subtitle     = slide.get("subtitle", "")
    accent_key   = slide.get("accent_color", "yellow")
    accent_color = rgb(ACCENT_COLORS.get(accent_key, "#FFD700"))

    segs = _parse_segments(raw_text)

    # ── Near-edge text margins (like the reference) ───────────────────────────
    TEXT_PAD = 0
    text_maxw = W - TEXT_PAD * 2

    def line_px(line_words, f):
        d  = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        sp = int(d.textlength(" ", font=f))
        return sum(int(d.textlength(w, font=f)) for w, _ in line_words) + sp * (len(line_words) - 1)

    # ── Size hook font: largest that fits lines within W AND bar within 38% ──
    bar_pad_v = 60
    max_bar_h = int(H * 0.40)

    for fsize in [210, 190, 170, 155, 140, 125, 112, 100, 88, 76]:
        fnt      = font(fsize, style="hook")
        lines_ws = _wrap_segments(segs, fnt, W)
        if any(line_px(l, fnt) > W for l in lines_ws):
            continue
        line_h   = int(fsize * 1.02)
        total_h  = line_h * len(lines_ws)
        if total_h + bar_pad_v * 2 <= max_bar_h:
            break

    lines_ws = _wrap_segments(segs, fnt, W)
    line_h   = int(fsize * 1.02)

    # ── Subtitle: grow font until it fills exactly one full line ─────────────
    if subtitle:
        sub_segs_plain = [(w, False) for w in subtitle.split()]
        for sub_fsize in range(120, 18, -1):
            fnt_sub = font(sub_fsize, style="hook")
            if line_px(sub_segs_plain, fnt_sub) <= W:
                break
        sub_lines = [sub_segs_plain]
    else:
        sub_fsize = 28
        fnt_sub   = font(sub_fsize, style="hook")
        sub_lines = []
    sub_lh = int(sub_fsize * 1.02)
    sub_h  = sub_lh + 12 if sub_lines else 0

    # ── Bar height driven by text ─────────────────────────────────────────────
    total_text_h = line_h * len(lines_ws) + sub_h
    bar_h        = total_text_h + bar_pad_v * 2
    bar_top      = H - bar_h

    # ── Fading overlay: transparent at top, solid black at bottom ────────────
    bar_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fade_draw = ImageDraw.Draw(bar_layer)
    fade_zone = int(bar_h * 0.55)  # top 55% of bar fades in
    for gy in range(bar_top, H):
        rel = gy - bar_top
        if rel < fade_zone:
            alpha = int(230 * (rel / fade_zone))
        else:
            alpha = 230
        fade_draw.line([(0, gy), (W, gy)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), bar_layer).convert("RGB")
    draw   = ImageDraw.Draw(canvas)

    # ── Thin horizontal separator line above the bar ──────────────────────────
    sep_pad = 60
    sep_y   = bar_top
    draw.rectangle([sep_pad, sep_y, W - sep_pad, sep_y + 1], fill=(200, 200, 200))

    # ── Draw text — centered (each line offset so leftover space is balanced) ──
    y = bar_top + bar_pad_v
    for line_words in lines_ws:
        _draw_accent_line(draw, line_words, fnt, accent_color, y, maxw=W)
        y += line_h

    if sub_lines:
        y += 12
        d_s  = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        sp_s = int(d_s.textlength(" ", font=fnt_sub))
        for line_words in sub_lines:
            lw = sum(int(d_s.textlength(w, font=fnt_sub)) for w, _ in line_words) + sp_s * (len(line_words) - 1)
            x  = (W - lw) // 2
            for i, (word, acc) in enumerate(line_words):
                draw.text((x, y), word, font=fnt_sub, fill=accent_color if acc else (200, 200, 200))
                x += int(d_s.textlength(word, font=fnt_sub)) + (sp_s if i < len(line_words) - 1 else 0)
            y += sub_lh

    # ── Watermark top-right ───────────────────────────────────────────────────
    draw.text((W - PAD - 10, 40), "@slidez", font=font(26, style="sub"), fill=(255, 255, 255, 160))

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE TYPE 2 — Regular (tweet card style)
# ══════════════════════════════════════════════════════════════════════════════

def render_regular_slide(slide, profile, theme, cdir):
    canvas = Image.new("RGB", (W, H), rgb(theme["bg"]))
    draw   = ImageDraw.Draw(canvas)

    ft = font(TWEET_SZ, style="default")
    ct = rgb(theme["text"]); cd = rgb(theme["divider"])

    tweets = slide.get("tweets", [])
    ip     = slide.get("image_path")
    ipos   = slide.get("image_position", "below")
    simg   = load_img(ip, cdir) if ip else None

    blocks = [(wrap(t["text"], ft, MAX_TW), 0) for t in tweets]
    blocks = [(l, measure(l, ft)[1]) for l, _ in blocks]

    th = sum(h for _, h in blocks)
    if len(blocks) > 1: th += DIV_GAP * 2 + DIV_H

    ih = iw = ig = 0
    if simg:
        ar = simg.width / simg.height
        iw = MAX_TW; ih = min(int(iw / ar), MAX_IMG_H)
        iw = int(ih * ar)
        if iw > MAX_TW: iw = MAX_TW; ih = int(iw / ar)
        ig = 40

    HEADER_GAP = 8   # gap between header and content
    block_h    = HEADER_H + HEADER_GAP + th + (ih + ig if simg else 0)

    # Center the whole block (header + content) vertically
    start_y = (H - block_h) // 2
    start_y = max(60, start_y)   # never clip top

    # Draw header at start_y
    brand_header(canvas, draw, profile, theme, cdir, y=start_y)

    cy_ = start_y + HEADER_H + HEADER_GAP

    if simg and ipos == "above":
        ix = PAD + (MAX_TW - iw) // 2
        r  = round_corners(simg.resize((iw, ih), Image.LANCZOS), IMG_RADIUS)
        canvas.paste(r, (ix, cy_), r); cy_ += ih + ig

    for i, (lines, _) in enumerate(blocks):
        if i > 0:
            cy_ += DIV_GAP
            draw.rectangle([PAD, cy_, W - PAD, cy_ + DIV_H], fill=cd)
            cy_ += DIV_H + DIV_GAP
        cy_ = draw_block(draw, lines, ft, ct, PAD, cy_)

    if simg and ipos != "above":
        ix = PAD + (MAX_TW - iw) // 2
        r  = round_corners(simg.resize((iw, ih), Image.LANCZOS), IMG_RADIUS)
        canvas.paste(r, (ix, cy_ + ig), r)

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE TYPE — CTA (plain text + centred "App link in bio" line, no header)
# ══════════════════════════════════════════════════════════════════════════════

def render_cta_slide(slide, profile, theme, cdir):
    canvas = Image.new("RGB", (W, H), rgb(theme["bg"]))
    draw   = ImageDraw.Draw(canvas)

    ft      = font(TWEET_SZ, style="default")
    ft_cta  = font(TWEET_SZ, bold=True)
    ct      = rgb(theme["text"])

    body_text = slide.get("text", "")
    cta_text  = slide.get("cta", "")

    body_lines = wrap(body_text, ft, MAX_TW)
    _, body_h  = measure(body_lines, ft)

    cta_lines  = wrap(cta_text, ft_cta, MAX_TW) if cta_text else []
    _, cta_h   = measure(cta_lines, ft_cta) if cta_lines else (0, 0)
    gap        = TWEET_SZ * 2 if cta_lines else 0

    total_h = body_h + gap + cta_h
    cy_     = max(PAD, (H - total_h) // 2)

    # Body — left aligned
    cy_ = draw_block(draw, body_lines, ft, ct, PAD, cy_)
    cy_ += gap

    # CTA — centred
    lh = int(ft_cta.size * 1.45)
    for line in cta_lines:
        lw = int(draw.textlength(line, font=ft_cta))
        draw.text((W // 2 - lw // 2, cy_), line, font=ft_cta, fill=ct)
        cy_ += lh

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE TYPE 3 — Testimonial
# ══════════════════════════════════════════════════════════════════════════════

def render_one_card(draw, canvas, rimg, quote, name, sub, stars, theme, cx_, cy_, cw, cdir):
    ctw  = cw - CARD_PAD*2
    fq   = font(Q_SZ); frn = font(RN_SZ, bold=True); frs = font(RS_SZ); fst = font(STAR_SZ)
    ql   = wrap(f'"{quote}"', fq, ctw); _, qh = measure(ql, fq)
    inner = (RAV+20) + (STAR_SZ+16) + qh + 36 + RN_SZ + 8 + RS_SZ
    ch    = inner + CARD_PAD*2
    draw.rounded_rectangle([cx_, cy_, cx_+cw, cy_+ch], radius=CARD_R,
        fill=rgb(theme["card_bg"]), outline=rgb(theme["card_border"]), width=1)
    y  = cy_ + CARD_PAD
    mx = cx_ + cw//2
    if rimg:
        ri = ImageOps.fit(rimg, (RAV,RAV), Image.LANCZOS)
        m  = circle_mask(RAV); bs = RAV+4
        bi = Image.new("RGB",(bs,bs), rgb(theme["text"])); bm = circle_mask(bs)
        canvas.paste(bi, (mx-RAV//2-2, y-2), bm); canvas.paste(ri, (mx-RAV//2, y), m)
    else:
        draw.ellipse([mx-RAV//2, y, mx+RAV//2, y+RAV], fill=rgb(theme["divider"]))
    y += RAV+20
    ss = "★"*stars
    sw = int(ImageDraw.Draw(Image.new("RGB",(1,1))).textlength(ss, font=fst))
    draw.text((mx-sw//2, y), ss, font=fst, fill=rgb(theme["star"])); y += STAR_SZ+16
    y = draw_block(draw, ql, fq, rgb(theme["text"]), cx_+CARD_PAD, y, align="center", maxw=ctw)
    y += 36
    m2 = ImageDraw.Draw(Image.new("RGB",(1,1)))
    nw = int(m2.textlength(name, font=frn))
    draw.text((mx-nw//2, y), name, font=frn, fill=rgb(theme["reviewer_name"])); y += RN_SZ+8
    sw2= int(m2.textlength(sub, font=frs))
    draw.text((mx-sw2//2, y), sub, font=frs, fill=rgb(theme["reviewer_sub"]))
    return cy_ + ch

def render_testimonial_slide(slide, profile, theme, cdir):
    canvas = Image.new("RGB", (W, H), rgb(theme["bg"]))
    draw   = ImageDraw.Draw(canvas)
    brand_header(canvas, draw, profile, theme, cdir)
    ts  = slide.get("testimonials", [])
    top = HEADER_TOP + HEADER_H + 10
    cw  = W - PAD*2
    if len(ts) == 1:
        t   = ts[0]; img = load_img(t.get("headshot_path",""), cdir)
        render_one_card(draw, canvas, img, t.get("quote",""), t.get("name","Anonymous"),
            t.get("subtitle","Slidez user"), t.get("stars",5), theme, PAD, top+30, cw, cdir)
    elif len(ts) == 2:
        avail = H - top - 60
        hh    = (avail - 30)//2
        for i, t in enumerate(ts):
            img = load_img(t.get("headshot_path",""), cdir)
            render_one_card(draw, canvas, img, t.get("quote",""), t.get("name","Anonymous"),
                t.get("subtitle","Slidez user"), t.get("stars",5), theme, PAD, top+i*(hh+30), cw, cdir)
    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE TYPE 4 — Messaging (iOS iMessage / Instagram DM)
#
# Config format:
# {
#   "slide_number": 2,
#   "type": "messaging",
#   "platform": "imessage" | "imessage_dark" | "dm",
#   "contact_name": "Sofia",
#   "contact_avatar": "./reference/avatar.jpg",   ← optional
#   "messages": [
#     { "from": "them", "text": "omg what app is this??" },
#     { "from": "me",   "text": "it styles you using AI. on your actual photo" },
#     { "from": "them", "text": "WAIT. send me the link rn" }
#   ]
# }
# ══════════════════════════════════════════════════════════════════════════════

MSG_THEMES = {
    # iOS light mode — matches reference exactly
    "imessage": {
        "bg":           "#f2f2f7",
        "status_bg":    "#f2f2f7",
        "status_text":  "#000000",
        "header_bg":    "#f2f2f7",
        "header_sep":   "#c8c8cc",
        "header_text":  "#000000",
        "header_sub":   "#8e8e93",
        "bubble_me":    "#007aff",
        "bubble_them":  "#ffffff",
        "text_me":      "#ffffff",
        "text_them":    "#000000",
        "timestamp":    "#8e8e93",
        "input_bg":     "#f2f2f7",
        "input_border": "#c8c8cc",
        "input_text":   "#8e8e93",
        "read":         "#8e8e93",
        "accent":       "#007aff",
    },
    # iOS dark mode — black bg, dark grey received, blue sent
    "imessage_dark": {
        "bg":           "#000000",
        "status_bg":    "#000000",
        "status_text":  "#ffffff",
        "header_bg":    "#1c1c1e",
        "header_sep":   "#38383a",
        "header_text":  "#ffffff",
        "header_sub":   "#8e8e93",
        "bubble_me":    "#2979ff",
        "bubble_them":  "#2c2c2e",
        "text_me":      "#ffffff",
        "text_them":    "#ffffff",
        "timestamp":    "#8e8e93",
        "input_bg":     "#1c1c1e",
        "input_border": "#38383a",
        "input_text":   "#636366",
        "read":         "#8e8e93",
        "accent":       "#2979ff",
    },
    # Instagram DM — black bg, dark bubbles, blue sent
    "dm": {
        "bg":           "#000000",
        "status_bg":    "#000000",
        "status_text":  "#ffffff",
        "header_bg":    "#000000",
        "header_sep":   "#262626",
        "header_text":  "#ffffff",
        "header_sub":   "#a8a8a8",
        "bubble_me":    "#3797f0",
        "bubble_them":  "#262626",
        "text_me":      "#ffffff",
        "text_them":    "#ffffff",
        "timestamp":    "#a8a8a8",
        "input_bg":     "#1a1a1a",
        "input_border": "#363636",
        "input_text":   "#a8a8a8",
        "read":         "#a8a8a8",
        "accent":       "#3797f0",
    },
}

# Messaging layout constants
BUBBLE_R     = 20
BUBBLE_PX    = 28
BUBBLE_PY    = 16
BUBBLE_MAX_W = int(W * 0.70)
BUBBLE_GAP   = 18
MSG_FS       = 36
TS_FS        = 26
STATUS_H     = 60
HEADER_H_MSG = 108
INPUT_H      = 90


def _draw_ios_status_bar(draw, mt):
    """9:41 left, real signal-bars + wifi-arcs + battery-rect right."""
    try:
        f_time = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 34)
    except Exception:
        f_time = font(34, bold=True)
    tc = rgb(mt["status_text"])
    draw.text((44, 12), "9:41", font=f_time, fill=tc)

    cy  = STATUS_H // 2   # vertical centre = 30
    rx  = W - 44          # rightmost x anchor

    # ── Battery ──────────────────────────────────────────────────────────────
    bw, bh = 40, 20
    bx2 = rx;  bx1 = bx2 - bw
    by1 = cy - bh // 2;  by2 = by1 + bh
    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=5, outline=tc, width=2)
    # nub on right
    draw.rectangle([bx2, cy - 4, bx2 + 3, cy + 4], fill=tc)
    # fill ~80%
    fw = int((bw - 6) * 0.80)
    draw.rounded_rectangle([bx1 + 3, by1 + 3, bx1 + 3 + fw, by2 - 3], radius=3, fill=tc)

    # ── WiFi ─────────────────────────────────────────────────────────────────
    wcx = bx1 - 24
    wcy = cy + 2
    for r, w in [(14, 2), (9, 2), (5, 2)]:
        draw.arc([wcx - r, wcy - r, wcx + r, wcy + r], start=225, end=315, fill=tc, width=w)
    draw.ellipse([wcx - 2, wcy + 6, wcx + 2, wcy + 10], fill=tc)

    # ── Signal bars (4 bars, bottom-aligned) ─────────────────────────────────
    sig_x2 = wcx - 20
    bar_w, bar_gap = 6, 4
    bar_heights = [8, 12, 16, 20]
    for i, bht in enumerate(bar_heights):
        bx = sig_x2 - (3 - i) * (bar_w + bar_gap)
        by_bot = cy + 10
        draw.rounded_rectangle([bx, by_bot - bht, bx + bar_w, by_bot], radius=1, fill=tc)


def _draw_ios_header(draw, canvas, mt, contact_name, avatar_img, cdir, y):
    """Back chevron left, avatar+name center (with > chevron), video icon right."""
    try:
        f_name = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 28)
        f_sub  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
    except Exception:
        f_name = font(28); f_sub = font(24)
    ac = rgb(mt["accent"])
    tc = rgb(mt["header_text"])
    sc = rgb(mt["header_sub"])

    # Back chevron — drawn as two lines forming <
    chev_x, chev_cy = 50, y + HEADER_H_MSG // 2
    arm = 18
    draw.line([(chev_x + arm, chev_cy - arm), (chev_x, chev_cy)], fill=ac, width=3)
    draw.line([(chev_x, chev_cy), (chev_x + arm, chev_cy + arm)], fill=ac, width=3)

    # Avatar circle centered
    av = 72
    ax = W // 2 - av // 2
    ay = y + 14
    if avatar_img:
        ai = ImageOps.fit(avatar_img, (av, av), Image.LANCZOS)
        m  = circle_mask(av)
        canvas.paste(ai, (ax, ay), m)
    else:
        draw.ellipse([ax, ay, ax + av, ay + av], fill="#8e8e93")
        init = contact_name[0].upper() if contact_name else "?"
        try:
            fi = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 30)
        except Exception:
            fi = font(30, bold=True)
        iw = int(draw.textlength(init, font=fi))
        draw.text((ax + av // 2 - iw // 2, ay + av // 2 - 18), init, font=fi, fill="white")

    # Name + > chevron below avatar, centered together
    chevron_txt = " >"
    nw  = int(draw.textlength(contact_name, font=f_name))
    cw  = int(draw.textlength(chevron_txt,  font=f_sub))
    row_w = nw + cw
    nx  = W // 2 - row_w // 2
    ny  = ay + av + 6
    draw.text((nx,      ny), contact_name, font=f_name, fill=tc)
    draw.text((nx + nw, ny + 2), chevron_txt,  font=f_sub,  fill=sc)

    # Video camera icon — rectangle body + triangle lens
    vcx = W - 60;  vcy = y + HEADER_H_MSG // 2
    vbw, vbh = 34, 22
    vbx = vcx - vbw // 2;  vby = vcy - vbh // 2
    draw.rounded_rectangle([vbx, vby, vbx + vbw, vby + vbh], radius=5, outline=ac, width=3)
    tri = [(vbx + vbw + 2, vcy - 8), (vbx + vbw + 16, vcy), (vbx + vbw + 2, vcy + 8)]
    draw.polygon(tri, fill=ac)

    # Separator
    draw.line([(0, y + HEADER_H_MSG), (W, y + HEADER_H_MSG)], fill=rgb(mt["header_sep"]), width=1)


def _draw_bubble(draw, canvas, lines, fnt, is_me, mt, bx, by, bw, bh):
    """Draw one chat bubble with iOS tail."""
    bc = rgb(mt["bubble_me"]) if is_me else rgb(mt["bubble_them"])
    tc = rgb(mt["text_me"])   if is_me else rgb(mt["text_them"])

    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=BUBBLE_R, fill=bc)

    # Tail
    ts = 14
    if is_me:
        pts = [(bx+bw-BUBBLE_R, by+bh), (bx+bw+ts, by+bh+4), (bx+bw-1, by+bh-ts)]
    else:
        pts = [(bx+BUBBLE_R, by+bh), (bx-ts, by+bh+4), (bx+1, by+bh-ts)]
    draw.polygon(pts, fill=bc)

    # Text
    ty = by + BUBBLE_PY
    lh = int(fnt.size * 1.38)
    for line in lines:
        draw.text((bx + BUBBLE_PX, ty), line, font=fnt, fill=tc)
        ty += lh


def render_messaging_slide(slide, profile, theme, cdir):
    platform = slide.get("platform", "imessage")
    mt       = MSG_THEMES.get(platform, MSG_THEMES["imessage"])

    canvas = Image.new("RGB", (W, H), rgb(mt["bg"]))
    draw   = ImageDraw.Draw(canvas)

    try:
        fnt_msg = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", MSG_FS)
        fnt_ts  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", TS_FS)
    except Exception:
        fnt_msg = font(MSG_FS, style="sub")
        fnt_ts  = font(TS_FS)

    # Status bar
    draw.rectangle([0, 0, W, STATUS_H], fill=rgb(mt["status_bg"]))
    _draw_ios_status_bar(draw, mt)

    # Header
    hdr_y = STATUS_H
    draw.rectangle([0, hdr_y, W, hdr_y + HEADER_H_MSG], fill=rgb(mt["header_bg"]))
    avatar = load_img(slide.get("contact_avatar", ""), cdir)
    _draw_ios_header(draw, canvas, mt, slide.get("contact_name", "Friend"), avatar, cdir, hdr_y)

    # Pre-measure bubbles
    messages = slide.get("messages", [])
    bubbles  = []
    for msg in messages:
        is_me  = msg.get("from", "them") == "me"
        lines  = wrap(msg["text"], fnt_msg, BUBBLE_MAX_W - BUBBLE_PX * 2)
        d_tmp  = ImageDraw.Draw(Image.new("RGB", (1,1)))
        lh     = int(fnt_msg.size * 1.38)
        tw     = max(int(d_tmp.textlength(l, font=fnt_msg)) for l in lines)
        bw     = min(tw + BUBBLE_PX * 2, BUBBLE_MAX_W)
        bh     = lh * len(lines) + BUBBLE_PY * 2
        bubbles.append((is_me, lines, bw, bh))

    # Vertical centering
    SIDE_PAD    = 40
    TS_H        = TS_FS + 28
    READ_H      = TS_FS + 8
    content_top = STATUS_H + HEADER_H_MSG + 20
    content_bot = H - INPUT_H - 20
    avail_h     = content_bot - content_top
    total_h     = TS_H + sum(bh for _, _, _, bh in bubbles) + BUBBLE_GAP * (len(bubbles) - 1) + READ_H
    cur_y       = content_top + max(0, (avail_h - total_h) // 2)

    # Timestamp
    ts_txt = "Today 9:41 AM"
    tw     = int(draw.textlength(ts_txt, font=fnt_ts))
    draw.text((W//2 - tw//2, cur_y), ts_txt, font=fnt_ts, fill=rgb(mt["timestamp"]))
    cur_y += TS_H

    # Draw bubbles
    for i, (is_me, lines, bw, bh) in enumerate(bubbles):
        bx = W - SIDE_PAD - bw if is_me else SIDE_PAD
        _draw_bubble(draw, canvas, lines, fnt_msg, is_me, mt, bx, cur_y, bw, bh)
        if is_me and i == len(bubbles) - 1:
            read_txt = "Read"
            rw = int(draw.textlength(read_txt, font=fnt_ts))
            draw.text((bx + bw - rw, cur_y + bh + 6), read_txt, font=fnt_ts, fill=rgb(mt["read"]))
        cur_y += bh + BUBBLE_GAP

    # Input bar
    bar_y = H - INPUT_H - 30
    draw.rectangle([0, bar_y, W, H], fill=rgb(mt["input_bg"]))
    # Top separator
    draw.line([(0, bar_y), (W, bar_y)], fill=rgb(mt["header_sep"]), width=1)
    # Plus circle
    pc = 46; px = 28; py = bar_y + (INPUT_H - pc) // 2
    draw.ellipse([px, py, px + pc, py + pc], fill=rgb(mt["header_sep"]))
    try:
        fp = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 28)
    except Exception:
        fp = font(28, bold=True)
    draw.text((px + 11, py + 7), "+", font=fp, fill=rgb(mt["header_text"]))
    # Input pill — mic icon sits INSIDE on the right
    pill_x1 = px + pc + 16
    pill_x2 = W - 28
    pill_y1 = bar_y + 16
    pill_y2 = bar_y + INPUT_H - 16
    pill_h  = pill_y2 - pill_y1
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2],
                            radius=pill_h // 2, fill="#ffffff",
                            outline=rgb(mt["input_border"]), width=1)
    try:
        fp2 = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
    except Exception:
        fp2 = font(26)
    draw.text((pill_x1 + 24, pill_y1 + (pill_h - 26) // 2), "Message…", font=fp2, fill=rgb(mt["input_text"]))
    # Mic icon inside pill — right side (drawn as simple shape)
    mic_cx = pill_x2 - 32;  mic_cy = pill_y1 + pill_h // 2
    mic_w, mic_h = 14, 20
    # mic body (rounded rect)
    draw.rounded_rectangle([mic_cx - mic_w // 2, mic_cy - mic_h // 2,
                             mic_cx + mic_w // 2, mic_cy + mic_h // 2 - 4],
                            radius=6, fill=rgb(mt["input_text"]))
    # arc at bottom
    draw.arc([mic_cx - mic_w, mic_cy - 2, mic_cx + mic_w, mic_cy + mic_h // 2 + 4],
             start=0, end=180, fill=rgb(mt["input_text"]), width=2)
    # stem line
    draw.line([(mic_cx, mic_cy + mic_h // 2 + 2), (mic_cx, mic_cy + mic_h // 2 + 8)],
              fill=rgb(mt["input_text"]), width=2)
    # Home indicator
    hiw = 140
    draw.rounded_rectangle([W // 2 - hiw // 2, H - 16, W // 2 + hiw // 2, H - 8],
                            radius=4, fill="#000000")

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# Router
# ══════════════════════════════════════════════════════════════════════════════

def render_slide(slide, profile, theme, cdir):
    t = slide.get("type", "regular")
    if t == "hook_cover":  return render_hook_cover(slide, profile, theme, cdir)
    if t == "testimonial": return render_testimonial_slide(slide, profile, theme, cdir)
    if t == "messaging":   return render_messaging_slide(slide, profile, theme, cdir)
    if t == "cta":         return render_cta_slide(slide, profile, theme, cdir)
    return render_regular_slide(slide, profile, theme, cdir)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--slide",  type=int, default=None)
    p.add_argument("--theme",  choices=["light","dark"], default=None)
    args = p.parse_args()

    cfg_path = Path(args.config).resolve()
    with open(cfg_path) as f: cfg = json.load(f)
    cdir    = cfg_path.parent
    profile = cfg.get("profile", {})
    tname   = args.theme or cfg.get("theme", "dark")
    theme   = THEMES.get(tname, THEMES["dark"])
    slides  = cfg.get("slides", [])

    print(f"🎨 {tname}  |  👤 {profile.get('display_name')}  |  📊 {len(slides)} slides\n")
    for slide in slides:
        n = slide.get("slide_number", 1)
        if args.slide is not None and n != args.slide: continue
        out = cdir / f"slide_{n}.png"
        label = slide.get("type","regular")
        print(f"  [{label}] slide {n}...", end=" ", flush=True)
        try:
            img = render_slide(slide, profile, theme, cdir)
            img.save(str(out), "PNG", quality=95)
            print(f"✅  {out.name}")
        except Exception as e:
            print(f"❌  {e}")
            import traceback; traceback.print_exc()
    print(f"\n🎉 Done → {cdir}")

if __name__ == "__main__":
    main()
