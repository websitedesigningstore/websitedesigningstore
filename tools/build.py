"""Builds the animated, self-contained profile SVGs in ../assets.

Run:  python tools/build.py
Needs: Pillow, fonttools, brotli.  Everything (fonts, portraits, icons) is
inlined as data URIs, so the SVGs make zero network requests when rendered.
"""
import base64, hashlib, io, math, os, re
from xml.sax.saxutils import escape

from PIL import Image
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
ASSETS = os.path.join(ROOT, "assets")

# ---------------------------------------------------------------- profile
P = {
    "first": "ABHISHEK",
    "last": "KUMAR",
    "user": "websitedesigningstore",
    "roles": ["Web Developer", "IoT & Smart Hardware", "Center Head @ Globalwebify", "IT Professional since 2015"],
    "pitch": "Web platforms, browser tools and ESP32 hardware — built for real users.",
    "company": "Center Head · Globalwebify",
    "city": "Bokaro Steel City, Jharkhand",
    "checked": "06 OCT 2026",
}

NAVY, NAVY2, CARD = "#070b16", "#0b1222", "#0d1528"
BLUE, RED = "#247bff", "#ff354f"
INK, MUTED, FAINT, LINE = "#eef2fb", "#8b97b6", "#4d5878", "#1b2540"

# ---------------------------------------------------------------- fonts
GLYPHS = "".join(chr(c) for c in range(32, 127)) + "·—’…"


def _woff2(path, wght=None):
    f = TTFont(path)
    if wght is not None:
        f = instancer.instantiateVariableFont(f, {"wght": wght})
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(text=GLYPHS)
    sub.subset(f)
    buf = io.BytesIO()
    f.flavor = "woff2"
    f.save(buf)
    return f, base64.b64encode(buf.getvalue()).decode()


FONT_FILES = {
    "display": ("BarlowCondensed-ExtraBold.ttf", None),
    "body": ("Barlow-Medium.ttf", None),
    "mono": ("JetBrainsMono[wght].ttf", 500),
}
FONTS, METRICS = {}, {}
for key, (fn, w) in FONT_FILES.items():
    ft, b64 = _woff2(os.path.join(TOOLS, "fonts", fn), w)
    FONTS[key] = b64
    cmap, hmtx, upm = ft.getBestCmap(), ft["hmtx"], ft["head"].unitsPerEm
    METRICS[key] = (cmap, hmtx, upm)


def tw(text, font, size, spacing=0.0):
    """Measured advance width of text in px."""
    cmap, hmtx, upm = METRICS[font]
    w = 0
    for ch in text:
        g = cmap.get(ord(ch))
        w += hmtx[g][0] if g else upm * 0.5
    return w * size / upm + spacing * max(len(text) - 1, 0)


FONT_CSS = "".join(
    "@font-face{font-family:'P%s';src:url(data:font/woff2;base64,%s) format('woff2');font-display:block}" % (k, v)
    for k, v in FONTS.items()
)

# ---------------------------------------------------------------- images


def png_uri(path, width, crop=None):
    im = Image.open(path).convert("RGBA")
    if crop:
        im = im.crop(crop)
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    q = im.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
    buf = io.BytesIO()
    q.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), im.size


ID_PNG = os.path.join(ROOT, "source", "id.png")
POINT_PNG = os.path.join(ROOT, "source", "right_pointing.png")

# ---------------------------------------------------------------- icons (Simple Icons, CC0)
ICON_HEX = {
    "php": "777BB4", "mysql": "4479A1", "python": "3776AB", "html5": "E34F26", "css": "663399",
    "javascript": "F7DF1E", "typescript": "3178C6", "react": "61DAFB", "cplusplus": "00599C",
    "android": "3DDC84", "kotlin": "7F52FF", "openjdk": "000000", "espressif": "E7352C",
    "mqtt": "660066", "github": "181717", "googlechrome": "4285F4", "googleplay": "414141",
}


def icon_path(name):
    with open(os.path.join(TOOLS, "icons", name + ".svg"), encoding="utf-8") as f:
        return re.search(r'<path d="([^"]+)"', f.read()).group(1)


def icon_color(name):
    h = ICON_HEX[name]
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum < 0.22:  # too dark on navy: lift it, keep the hue
        if max(r, g, b) - min(r, g, b) < 0.08:
            return INK
        return "#%02x%02x%02x" % tuple(int(255 * (c + (1 - c) * 0.45)) for c in (r, g, b))
    return "#" + h


def icon(name, cx, cy, size, color=None):
    s = size / 24
    return '<path transform="translate(%.1f %.1f) scale(%.4f)" fill="%s" d="%s"/>' % (
        cx - size / 2, cy - size / 2, s, color or icon_color(name), icon_path(name))


# ---------------------------------------------------------------- svg helpers


def T(x, y, text, font="body", size=16, fill=INK, anchor="start", extra="", ls=None):
    style = "font-family:'P%s';font-size:%spx" % (font, size)
    if ls is not None:
        style += ";letter-spacing:%spx" % ls
    return '<text x="%s" y="%s" text-anchor="%s" fill="%s" style="%s"%s>%s</text>' % (
        _n(x), _n(y), anchor, fill, style, extra, escape(text))


def _n(v):
    return ("%.2f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def doc(prefix, w, h, title, desc, defs, body, css=""):
    p = prefix
    base_css = (
        FONT_CSS
        + ".%s-up{animation:%s-up .9s cubic-bezier(.2,.8,.2,1) both}" % (p, p)
        + ".%s-fade{animation:%s-fade 1s ease both}" % (p, p)
        + "@keyframes %s-up{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}" % p
        + "@keyframes %s-fade{from{opacity:0}to{opacity:1}}" % p
        + ".%s-static{display:none}" % p
        + "@media (prefers-reduced-motion:reduce){"
        + "*{animation:none!important}.%s-motion{display:none!important}.%s-static{display:inline!important}" % (p, p)
        + "}"
    )
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-labelledby="%s-t %s-d">' % (w, h, w, h, p, p),
        '<title id="%s-t">%s</title><desc id="%s-d">%s</desc>' % (p, escape(title), p, escape(desc)),
        "<style>%s%s</style>" % (base_css, css),
        "<defs>",
        '<clipPath id="%s-frame"><rect width="%d" height="%d" rx="28"/></clipPath>' % (p, w, h),
        '<pattern id="%s-dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        '<circle cx="2" cy="2" r="1.1" fill="#19223b"/></pattern>' % p,
        '<linearGradient id="%s-hair" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="%s" stop-opacity=".85"/><stop offset=".5" stop-color="#26324f"/>'
        '<stop offset="1" stop-color="%s" stop-opacity=".75"/></linearGradient>' % (p, BLUE, RED),
        '<radialGradient id="%s-glowb"><stop offset="0" stop-color="%s" stop-opacity=".30"/>'
        '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>' % (p, BLUE, BLUE),
        '<radialGradient id="%s-glowr"><stop offset="0" stop-color="%s" stop-opacity=".24"/>'
        '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>' % (p, RED, RED),
        defs,
        "</defs>",
        '<g clip-path="url(#%s-frame)">' % p,
        '<rect width="%d" height="%d" fill="%s"/>' % (w, h, NAVY),
        '<rect width="%d" height="%d" fill="url(#%s-dots)"/>' % (w, h, p),
        '<rect width="%d" height="6" fill="%s"/><rect x="%d" width="%d" height="6" fill="%s"/>'
        % (w, BLUE, round(w * .7), w - round(w * .7), RED),
        body,
        "</g>",
        '<rect x=".75" y=".75" width="%s" height="%s" rx="27.5" fill="none" stroke="url(#%s-hair)" stroke-width="1.5"/>'
        % (w - 1.5, h - 1.5, p),
        "</svg>",
    ]
    return "".join(out)


def card(p, x, y, w, h, rx=20, fill=CARD, extra=""):
    return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="url(#%s-hair)" stroke-width="1.2"%s/>' % (
        _n(x), _n(y), _n(w), _n(h), rx, fill, p, extra)


def delay(s):
    return ' style="animation-delay:%.2fs"' % s


def label(p, x, y, num, text, d=0):
    return '<g class="%s-up"%s>%s%s</g>' % (
        p, delay(d), T(x, y, num, "mono", 14, BLUE, ls=1.5),
        T(x + tw(num, "mono", 14, 1.5) + 14, y, "/  " + text, "mono", 14, MUTED, ls=1.5))


def kt(*v):
    return ";".join(_n(round(x, 4)) for x in v)


def write(name, svg):
    path = os.path.join(ASSETS, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("%-18s %6.1f KB" % (name, len(svg.encode()) / 1024))


# ================================================================ hero.svg
def hero():
    p, W, H = "hr", 1200, 580
    uri, (iw, ih) = png_uri(ID_PNG, 470)
    pw = 352
    ph = pw * ih / iw
    cx, cy, cw, chh = 772, 96, 372, 430
    defs = (
        '<clipPath id="hr-l1"><rect x="40" y="150" width="720" height="128"/></clipPath>'
        '<clipPath id="hr-l2"><rect x="40" y="278" width="720" height="126"/></clipPath>'
        '<clipPath id="hr-card"><rect x="%d" y="%d" width="%d" height="%d" rx="26"/></clipPath>' % (cx, cy, cw, chh)
        + '<linearGradient id="hr-cardbg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f1a33"/>'
        '<stop offset="1" stop-color="#0a1020"/></linearGradient>'
    )
    greet = "> hello world, I'm"
    gw = tw(greet, "mono", 22)
    steps = len(greet)
    vals = [round(gw * i / steps, 1) for i in range(steps + 1)]
    # typing: 0.25s idle, then one char every 55ms, held after
    t_end = 0.25 + steps * 0.055
    dur = 3.0
    keys = [0] + [(0.25 + i * 0.055) / dur for i in range(1, steps + 1)]
    defs += ('<clipPath id="hr-type"><rect x="60" y="96" height="40" width="%s">'
             '<animate attributeName="width" begin="0s" dur="%ss" fill="freeze" calcMode="discrete" '
             'values="%s" keyTimes="%s"/></rect></clipPath>' % (_n(gw + 4), dur, ";".join(_n(v + 4 if v else 0) for v in vals), kt(*keys)))

    roles = P["roles"]
    n, slot = len(roles), 3.0
    cyc = n * slot
    role_svg = []
    for i, r in enumerate(roles):
        a, b = i * slot / cyc, (i + 1) * slot / cyc
        f = 0.35 / cyc
        if i == 0:
            ov, okt = [1, 1, 0, 0, 1], [0, b - f, b, 1 - f, 1]
            tv = ["0 0", "0 0", "0 -14", "0 14", "0 0"]
        else:
            ov, okt = [0, 0, 1, 1, 0, 0], [0, a, a + f, b - f, b, 1]
            tv = ["0 14", "0 14", "0 0", "0 0", "0 -14", "0 -14"]
        role_svg.append(
            '<g opacity="%d" class="hr-role hr-role%d">'
            '<animate attributeName="opacity" begin="0s" dur="%ss" repeatCount="indefinite" values="%s" keyTimes="%s"/>'
            '<animateTransform attributeName="transform" type="translate" begin="0s" dur="%ss" repeatCount="indefinite" values="%s" keyTimes="%s"/>'
            '%s</g>' % (1 if i == 0 else 0, i, cyc, kt(*ov), kt(*okt), cyc, ";".join(tv), kt(*okt), T(96, 452, r.upper(), "display", 38, RED, ls=1)))

    # info row chips
    chips, x = [], 60
    for i, (txt, dot) in enumerate([(P["city"], BLUE), (P["company"], RED), ("@" + P["user"], None)]):
        w = tw(txt, "mono", 14) + (44 if dot else 28)
        chips.append('<g class="hr-up"%s><rect x="%s" y="520" width="%s" height="34" rx="17" fill="%s" stroke="%s"/>%s%s</g>' % (
            delay(1.9 + i * .12), _n(x), _n(w), NAVY2, LINE,
            '<circle cx="%s" cy="537" r="4" fill="%s"/>' % (_n(x + 18), dot) if dot else "",
            T(x + (32 if dot else 14), 542, txt, "mono", 14, INK)))
        x += w + 12

    first_w = tw(P["first"], "display", 138, 2)
    body = (
        '<circle cx="980" cy="250" r="330" fill="url(#hr-glowb)"/><circle cx="1150" cy="470" r="260" fill="url(#hr-glowr)"/>'
        + '<g class="hr-fade">' + T(60, 58, P["user"].upper(), "body", 15, INK, ls=2.5)
        + T(60 + tw(P["user"].upper(), "body", 15, 2.5) + 26, 58, "/  GITHUB PROFILE", "mono", 13, MUTED, ls=1.5)
        + "".join('<path d="M%d 66 l10 -22 h12 l-10 22z" fill="%s"/>' % (1092 + i * 18, RED) for i in range(3)) + "</g>"
        # typed greeting
        + '<g class="hr-greet" clip-path="url(#hr-type)">' + T(60, 128, greet, "mono", 22, BLUE) + "</g>"
        + '<rect class="hr-cursor" x="%s" y="108" width="11" height="26" fill="%s">' % (_n(64 + gw), RED)
        + '<animate attributeName="opacity" begin="0s" dur="1s" repeatCount="indefinite" calcMode="discrete" values="1;0" keyTimes="0;.5"/></rect>'
        # rising name
        + '<g clip-path="url(#hr-l1)"><g class="hr-rise" style="animation-delay:.9s">' + T(56, 266, P["first"], "display", 138, INK, ls=2) + "</g></g>"
        + '<g clip-path="url(#hr-l2)"><g class="hr-rise" style="animation-delay:1.05s">' + T(56, 392, P["last"] + ".", "display", 138, BLUE, ls=2) + "</g></g>"
        # roles
        + '<g class="hr-up"%s>' % delay(1.5) + '<rect x="60" y="424" width="22" height="22" rx="4" fill="none" stroke="%s" stroke-width="2"/>' % RED
        + '<rect x="66" y="430" width="10" height="10" rx="2" fill="%s"/>' % RED
        + '<g class="hr-motion">' + "".join(role_svg) + "</g>"
        + '<g class="hr-static">' + T(96, 452, roles[0].upper(), "display", 38, RED, ls=1) + "</g></g>"
        + '<g class="hr-up"%s>' % delay(1.7) + T(60, 494, P["pitch"], "body", 21, "#b9c3dc") + "</g>"
        + "".join(chips)
        # portrait card
        + '<g class="hr-port">' + '<rect x="%d" y="%d" width="%d" height="%d" rx="26" fill="url(#hr-cardbg)"/>' % (cx, cy, cw, chh)
        + '<g clip-path="url(#hr-card)"><rect x="%d" y="%d" width="%d" height="%d" fill="url(#hr-dots)"/>' % (cx, cy, cw, chh)
        + '<image x="%s" y="%s" width="%s" height="%s" href="%s" xlink:href="%s"/></g>' % (
            _n(cx + (cw - pw) / 2), _n(cy + chh - ph + 4), pw, _n(ph), uri, uri)
        + card(p, cx, cy, cw, chh, 26, "none") + "</g>"
        + '<g class="hr-up"%s><rect x="920" y="500" width="236" height="44" rx="10" fill="%s"/>' % (delay(1.6), RED)
        + T(940, 528, "BUILD / SHIP / REPEAT", "mono", 14, "#fff", ls=1) + "</g>"
    )
    css = (
        ".hr-rise{animation:hr-rise 1s cubic-bezier(.16,1,.3,1) both}"
        "@keyframes hr-rise{from{transform:translateY(150px)}to{transform:none}}"
        ".hr-port{animation:hr-port 1.2s cubic-bezier(.16,1,.3,1) .3s both}"
        "@keyframes hr-port{from{opacity:0;transform:translateX(40px)}to{opacity:1;transform:none}}"
        "@media (prefers-reduced-motion:reduce){.hr-greet{clip-path:none!important}.hr-cursor{display:none}}"
    )
    write("hero.svg", doc(p, W, H, "Abhishek Kumar — " + " · ".join(roles),
                          P["pitch"] + " " + P["city"] + ". " + P["company"] + ".", defs, body, css))


# ================================================================ about-life.svg
def about():
    p, W, H = "ab", 1200, 560
    caps = [
        ("Web & SaaS platforms", "PHP + MySQL CRMs, news portals, e-commerce"),
        ("IoT & smart hardware", "ESP32, LED matrices, sensors, OTA, live control"),
        ("Browser & developer tools", "Chrome and VS Code extensions people install"),
        ("IT support & operations", "Hardware, networking, training — since 2015"),
    ]
    rows = []
    for i, (t, s) in enumerate(caps):
        y = 222 + i * 76
        rows.append('<g class="ab-up"%s>%s%s%s%s</g>' % (
            delay(.5 + i * .12), card(p, 60, y, 590, 62, 16),
            T(84, y + 39, "%02d" % (i + 1), "mono", 15, BLUE),
            T(128, y + 27, t, "body", 21, INK), T(128, y + 49, s, "body", 15, MUTED)))

    X, Y, CW, CH = 696, 60, 444, 440
    slot, n = 4.0, 3
    cyc = slot * n
    f = 0.35 / cyc
    slides = [
        ("SMART HARDWARE", ["ESP32 digital hourglass with physics-", "simulated sand, flip detection and a", "React remote over WebSocket."], "ESP32 · MAX7219"),
        ("AR & 3D ON THE WEB", ["Cube: a voxel builder with hand", "tracking and WebXR AR modes, plus", "camera-based AR experiments."], "WEBXR · TYPESCRIPT"),
        ("TOOLS THAT SAVE CLICKS", ["Multi-root VS Code workspaces and", "PIN-locked Chrome profiles — small", "tools, used by thousands."], "VS CODE · CHROME"),
    ]

    def art(i):
        cx, cy = X + CW / 2, Y + 232
        if i == 0:  # microchip + wifi
            pins = "".join(
                '<rect x="%s" y="%s" width="8" height="16" rx="2" fill="%s"/>' % (_n(cx - 52 + k * 20), _n(cy - 74 if top else cy + 58), FAINT)
                for k in range(6) for top in (True, False))
            pins += "".join(
                '<rect x="%s" y="%s" width="16" height="8" rx="2" fill="%s"/>' % (_n(cx - 74 if lf else cx + 58), _n(cy - 52 + k * 20), FAINT)
                for k in range(6) for lf in (True, False))
            waves = "".join(
                '<path d="M%s %s a%d %d 0 0 1 %d 0" fill="none" stroke="%s" stroke-width="4" stroke-linecap="round" opacity=".9">'
                '<animate attributeName="opacity" begin="0s" dur="1.6s" repeatCount="indefinite" values=".15;1;.15" keyTimes="0;%s;1"/></path>'
                % (_n(cx + 92 - r), _n(cy - 64), r, r, 2 * r, BLUE, _n(0.2 + k * 0.25)) for k, r in enumerate((10, 22, 34)))
            return (pins + '<rect x="%s" y="%s" width="120" height="120" rx="18" fill="#111c36" stroke="%s" stroke-width="2"/>' % (_n(cx - 60), _n(cy - 60), BLUE)
                    + '<rect x="%s" y="%s" width="76" height="76" rx="10" fill="none" stroke="%s" stroke-dasharray="4 5"/>' % (_n(cx - 38), _n(cy - 38), FAINT)
                    + T(cx, cy + 9, "ESP32", "mono", 22, INK, "middle") + waves)
        if i == 1:  # isometric voxels
            out = ""
            s = 34
            for (gx, gy, gz, c) in [(0, 0, 0, BLUE), (1, 0, 0, BLUE), (0, 1, 0, BLUE), (1, 1, 0, RED), (0, 0, 1, RED), (1, 0, 1, BLUE), (0, 0, 2, BLUE)]:
                ox = cx + (gx - gy) * s * .866
                oy = cy + 40 + (gx + gy) * s * .5 - gz * s
                top = "M%.1f %.1f l%.1f %.1f l%.1f %.1f l%.1f %.1fz" % (ox, oy - s, s * .866, s * .5, -s * .866, s * .5, -s * .866, -s * .5)
                left = "M%.1f %.1f l%.1f %.1f v%.1f l%.1f %.1fz" % (ox - s * .866, oy - s * .5, s * .866, s * .5, s, -s * .866, -s * .5)
                right = "M%.1f %.1f l%.1f %.1f v%.1f l%.1f %.1fz" % (ox, oy, s * .866, -s * .5, s, -s * .866, s * .5)
                out += '<path d="%s" fill="%s"/><path d="%s" fill="%s" opacity=".55"/><path d="%s" fill="%s" opacity=".32"/>' % (top, c, left, c, right, c)
            return out + '<path d="M%s %s h-14 v14 M%s %s h14 v14" fill="none" stroke="%s" stroke-width="3"/>' % (
                _n(cx - 100), _n(cy - 70), _n(cx + 100), _n(cy - 70), MUTED)
        return ('<path d="M%s %s l-34 34 l34 34 M%s %s l34 34 l-34 34" fill="none" stroke="%s" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>'
                % (_n(cx - 46), _n(cy - 34), _n(cx + 46), _n(cy - 34), BLUE)
                + '<path d="M%s %s l-22 84" stroke="%s" stroke-width="10" stroke-linecap="round"/>' % (_n(cx + 11), _n(cy - 42), RED)
                + '<rect x="%s" y="%s" width="12" height="4" fill="%s"><animate attributeName="opacity" begin="0s" dur="1s" repeatCount="indefinite" calcMode="discrete" values="1;0" keyTimes="0;.5"/></rect>'
                % (_n(cx + 80), _n(cy + 50), INK))

    sl = []
    for i, (title, lines, tag) in enumerate(slides):
        a, b = i * slot / cyc, (i + 1) * slot / cyc
        if i == 0:
            ov, okt = [1, 1, 0, 0, 1], [0, b - f, b, 1 - f, 1]
        else:
            ov, okt = [0, 0, 1, 1, 0, 0], [0, a, a + f, b - f, b, 1]
        inner = ('<g transform="translate(%s %s) scale(.78) translate(%s %s)">' % (_n(X + CW / 2), Y + 232, _n(-(X + CW / 2)), -(Y + 232)) + art(i) + '</g>' + T(X + 30, Y + 112, "INTERESTS  ·  0%d / 03" % (i + 1), "mono", 13, MUTED, ls=1.5)
                 + T(X + 30, Y + 338, title, "display", 36, INK, ls=.5)
                 + "".join(T(X + 30, Y + 368 + k * 22, ln, "body", 16, "#aeb8d2") for k, ln in enumerate(lines))
                 + T(X + CW - 30, Y + 112, tag, "mono", 12, BLUE, "end", ls=1))
        sl.append('<g class="ab-slide ab-s%d" opacity="%d"><animate attributeName="opacity" begin="0s" dur="%ss" repeatCount="indefinite" values="%s" keyTimes="%s"/>%s</g>'
                  % (i, 1 if i == 0 else 0, cyc, kt(*ov), kt(*okt), inner))

    bw = (CW - 60 - 2 * 10) / 3
    tracks = "".join('<rect x="%s" y="%d" width="%s" height="5" rx="2.5" fill="%s"/>' % (_n(X + 30 + i * (bw + 10)), Y + 74, _n(bw), LINE) for i in range(3))
    fills = ""
    for i in range(3):
        a, b = i / 3, (i + 1) / 3
        vals, keys = ([0, bw, bw], [0, b, 1]) if i == 0 else ([0, 0, bw, bw], [0, a, b, 1])
        fills += ('<rect x="%s" y="%d" width="%s" height="5" rx="2.5" fill="%s"><animate attributeName="width" begin="0s" dur="%ss" repeatCount="indefinite" values="%s" keyTimes="%s"/></rect>'
                  % (_n(X + 30 + i * (bw + 10)), Y + 74, _n(bw) if i == 0 else 0, BLUE if i != 1 else RED, cyc, kt(*vals), kt(*keys)))
    static_fill = '<rect x="%s" y="%d" width="%s" height="5" rx="2.5" fill="%s"/>' % (_n(X + 30), Y + 74, _n(bw), BLUE)

    body = (
        '<circle cx="930" cy="300" r="320" fill="url(#ab-glowb)"/><circle cx="80" cy="560" r="240" fill="url(#ab-glowr)"/>'
        + label(p, 60, 78, "01", "ABOUT")
        + '<g class="ab-up"%s>' % delay(.15) + T(56, 140, "I SHIP THINGS", "display", 62, INK, ls=1)
        + T(56, 196, "PEOPLE ACTUALLY USE.", "display", 62, BLUE, ls=1) + "</g>"
        + "".join(rows)
        + '<g class="ab-up"%s>' % delay(.3) + card(p, X, Y, CW, CH, 26) + tracks
        + '<g class="ab-motion">' + fills + "".join(sl) + "</g>"
        + '<g class="ab-static">' + static_fill + "</g>"
        + "</g>"
    )
    css = "@media (prefers-reduced-motion:reduce){.ab-s0{opacity:1!important}.ab-s1,.ab-s2{opacity:0!important}.ab-motion{display:inline!important}.ab-motion>rect{display:none}}"
    write("about-life.svg", doc(p, W, H, "About Abhishek Kumar",
                                "Capabilities: web and SaaS platforms, IoT and smart hardware, browser and developer tools, IT support. Interests: smart hardware, AR and 3D, developer tools.",
                                "", body, css))


# ================================================================ stack.svg
def ellipse_pts(cx, cy, rx, ry, rot, n=144):
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    pts = []
    for k in range(n + 1):
        t = 2 * math.pi * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


def at_fraction(pts, frac):
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    target, acc = sum(seg) * frac, 0
    for i, d in enumerate(seg):
        if acc + d >= target:
            u = (target - acc) / d if d else 0
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u)
        acc += d
    return pts[-1]


def stack():
    p, W, H = "st", 1200, 760
    OX, OY = 352, 452
    orbits = [
        (142, 82, -16, 20, [("php", "PHP"), ("mysql", "MySQL"), ("python", "Python")]),
        (232, 136, -9, 32, [("html5", "HTML5"), ("css", "CSS"), ("javascript", "JavaScript"), ("typescript", "TypeScript"), ("react", "React")]),
        (312, 196, -4, 48, [("cplusplus", "C++"), ("android", "Android"), ("kotlin", "Kotlin"), ("openjdk", "Java"),
                            ("espressif", "ESP32"), ("mqtt", "MQTT"), ("github", "GitHub"), ("googlechrome", "Chrome")]),
    ]
    rings, moving, static = "", "", ""
    for oi, (rx, ry, rot, dur, items) in enumerate(orbits):
        pts = ellipse_pts(OX, OY, rx, ry, rot)
        d = "M" + " L".join("%.1f %.1f" % q for q in pts) + "Z"
        rings += '<path d="%s" fill="none" stroke="%s" stroke-opacity=".55" stroke-width="1.4" stroke-dasharray="%s"/>' % (
            d, [BLUE, "#3a4a78", RED][oi], ["5 7", "2 6", "8 8"][oi])
        for k, (ic, name) in enumerate(items):
            fr = (k / len(items) + [0.08, 0.1, 0.04][oi]) % 1
            sx, sy = at_fraction(pts, fr)
            rel = "M" + " L".join("%.1f %.1f" % (q[0] - sx, q[1] - sy) for q in pts) + "Z"
            badge = ('<circle r="22" fill="#0f1830" stroke="%s" stroke-opacity=".7" stroke-width="1.5"/>' % icon_color(ic)
                     + icon(ic, 0, 0, 22) + T(0, 38, name, "mono", 12, "#c3cbe0", "middle"))
            moving += ('<g transform="translate(%.1f %.1f)"><g><animateMotion begin="0s" dur="%ds" repeatCount="indefinite" calcMode="linear" '
                       'keyPoints="%s" keyTimes="%s" path="%s"/>%s</g></g>' % (
                           sx, sy, dur, kt(fr, 1, 0, fr), kt(0, 1 - fr, 1 - fr, 1), rel, badge))
            static += '<g transform="translate(%.1f %.1f)">%s</g>' % (sx, sy, badge)

    core = ('<defs><linearGradient id="st-core" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>' % (BLUE, RED)
            + '<circle cx="%d" cy="%d" r="44" fill="none" stroke="%s" stroke-opacity=".5"><animate attributeName="r" begin="0s" dur="3s" repeatCount="indefinite" values="44;70" keyTimes="0;1"/>'
              '<animate attributeName="stroke-opacity" begin="0s" dur="3s" repeatCount="indefinite" values=".5;0" keyTimes="0;1"/></circle>' % (OX, OY, BLUE)
            + '<circle cx="%d" cy="%d" r="44" fill="url(#st-core)"/>' % (OX, OY)
            + T(OX, OY + 15, "AK", "display", 42, "#fff", "middle", ls=1))

    groups = [
        ("LANGUAGES", ["C", "C++", "PHP", "Python", "JavaScript", "TypeScript", "Java", "Kotlin"]),
        ("WEB & DATA", ["HTML", "CSS", "React", "REST APIs", "MySQL", "MS Access"]),
        ("IOT & HARDWARE", ["ESP32", "MQTT", "WebSocket", "OTA Updates", "LED Matrices", "Sensors"]),
        ("APPS & TOOLS", ["Android", "Chrome Extensions", "VS Code Extensions", "Git", "GitHub"]),
        ("SYSTEMS & SECURITY", ["Windows", "Linux", "Networking", "Hardware Repair", "CEH — EC-Council"]),
    ]
    chips, y, gi = "", 186, 0
    X0, XMAX = 716, 1160
    for g, items in groups:
        out = T(X0, y, g, "mono", 13, [BLUE, RED][gi % 2], ls=1.5)
        x, y = X0, y + 13
        for it in items:
            w = tw(it, "mono", 13) + 22
            if x + w > XMAX:
                x, y = X0, y + 38
            out += '<rect x="%s" y="%d" width="%s" height="30" rx="9" fill="%s" stroke="%s"/>' % (_n(x), y, _n(w), NAVY2, LINE)
            out += T(x + 11, y + 20, it, "mono", 13, INK)
            x += w + 8
        chips += '<g class="st-up"%s>%s</g>' % (delay(.4 + gi * .12), out)
        y += 66
        gi += 1
    H = max(H, y - 66 + 30 + 44)  # grow the canvas to fit the last chip row

    body = (
        '<circle cx="%d" cy="%d" r="340" fill="url(#st-glowb)"/><circle cx="1150" cy="80" r="240" fill="url(#st-glowr)"/>' % (OX, OY)
        + label(p, 60, 78, "02", "STACK")
        + '<g class="st-up"%s>' % delay(.15) + T(56, 142, "TOOLS OF THE TRADE.", "display", 62, INK, ls=1) + "</g>"
        + '<g class="st-fade"%s>' % delay(.3) + rings + core
        + '<g class="st-motion">' + moving + '</g><g class="st-static">' + static + "</g></g>"
        + chips
    )
    write("stack.svg", doc(p, W, H, "Tech stack",
                           "Languages: C, C++, PHP, Python, JavaScript, TypeScript, Java, Kotlin. Web: HTML, CSS, React, MySQL. IoT: ESP32, MQTT, WebSocket, OTA. Tools: Android, Chrome and VS Code extensions, Git, GitHub. Systems: Windows, Linux, networking, CEH.",
                           "", body))


# ================================================================ id-dashboard.svg
def id_dashboard():
    p, W, H = "id", 1200, 740
    PX, PY = 290, -30  # lanyard pivot (above the frame)
    CX, CY, CW, CH = 130, 226, 320, 486
    uri, _ = png_uri(ID_PNG, 480, crop=(32, 40, 800, 744))
    seed = hashlib.sha256(P["user"].encode()).digest()
    bars, bx = "", CX + 34
    for byte in seed * 2:
        w = 1 + byte % 3
        if bx + w > CX + CW - 34:
            break
        if byte & 8:
            bars += '<rect x="%d" y="%d" width="%d" height="34" fill="%s"/>' % (bx, CY + 404, w, INK)
        bx += w + 1 + (byte >> 6)

    defs = (
        '<clipPath id="id-cardc"><rect x="%d" y="%d" width="%d" height="%d" rx="22"/></clipPath>' % (CX, CY, CW, CH)
        + '<clipPath id="id-photo"><rect x="%d" y="%d" width="240" height="220" rx="16"/></clipPath>' % (CX + 40, CY + 72)
        + '<linearGradient id="id-strap" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1748a8"/><stop offset=".5" stop-color="%s"/><stop offset="1" stop-color="#1748a8"/></linearGradient>' % BLUE
        + '<linearGradient id="id-metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f6fb"/><stop offset=".45" stop-color="#8d96aa"/><stop offset=".6" stop-color="#cfd5e2"/><stop offset="1" stop-color="#5d6579"/></linearGradient>'
        + '<linearGradient id="id-head" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>' % (BLUE, RED)
        + '<linearGradient id="id-photobg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#14254d"/><stop offset="1" stop-color="#2a1424"/></linearGradient>'
        + '<linearGradient id="id-sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        + '<linearGradient id="id-foil" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7cf"/><stop offset=".35" stop-color="#c9f"/><stop offset=".7" stop-color="#ff8fa3"/><stop offset="1" stop-color="#9fe"/></linearGradient>'
    )
    cxm = CX + CW / 2
    card_svg = (
        # straps (behind clasp)
        '<path d="M%d %d L%s %d L%s %d L%d %d Z" fill="url(#id-strap)"/>' % (PX - 70, PY, _n(PX - 12), CY - 52, _n(PX - 2), CY - 52, PX - 40, PY)
        + '<path d="M%d %d L%s %d L%s %d L%d %d Z" fill="url(#id-strap)"/>' % (PX + 70, PY, _n(PX + 12), CY - 52, _n(PX + 2), CY - 52, PX + 40, PY)
        + '<path d="M%d %d L%d %d M%d %d L%d %d" stroke="%s" stroke-width="1.5" stroke-dasharray="4 4" opacity=".8"/>' % (PX - 56, PY, PX - 8, CY - 56, PX + 56, PY, PX + 8, CY - 56, RED)
        # clasp
        + '<rect x="%d" y="%d" width="28" height="22" rx="5" fill="url(#id-metal)"/>' % (PX - 14, CY - 60)
        + '<circle cx="%d" cy="%d" r="11" fill="none" stroke="url(#id-metal)" stroke-width="5"/>' % (PX, CY - 28)
        + '<rect x="%d" y="%d" width="16" height="22" rx="4" fill="url(#id-metal)"/>' % (PX - 8, CY - 18)
        # card
        + '<rect x="%d" y="%d" width="%d" height="%d" rx="22" fill="#0e1730"/>' % (CX, CY, CW, CH)
        + '<g clip-path="url(#id-cardc)">'
        + '<rect x="%d" y="%d" width="%d" height="56" fill="url(#id-head)"/>' % (CX, CY, CW)
        + '<rect x="%s" y="%d" width="64" height="10" rx="5" fill="%s"/>' % (_n(cxm - 32), CY + 12, NAVY)
        + T(CX + 22, CY + 46, "GLOBALWEBIFY", "mono", 12, "#fff", ls=1.5) + T(CX + CW - 22, CY + 46, "BUILDER ID", "mono", 12, "#fff", "end", ls=1.5)
        + '<rect x="%d" y="%d" width="240" height="220" rx="16" fill="url(#id-photobg)"/>' % (CX + 40, CY + 72)
        + '<g clip-path="url(#id-photo)"><image x="%d" y="%d" width="240" height="220" preserveAspectRatio="xMidYMin slice" href="%s" xlink:href="%s"/></g>' % (CX + 40, CY + 80, uri, uri)
        + '<circle cx="%d" cy="%d" r="15" fill="url(#id-foil)" opacity=".85"/>' % (CX + CW - 54, CY + 268)
        + T(cxm, CY + 334, "ABHISHEK KUMAR", "display", 38, INK, "middle", ls=1)
        + T(cxm, CY + 358, "WEB · IOT · IT OPERATIONS", "mono", 12, BLUE, "middle", ls=1.5)
        + '<path d="M%d %d h%d" stroke="%s"/>' % (CX + 30, CY + 374, CW - 60, LINE)
        + T(CX + 34, CY + 394, "IN IT SINCE 2015", "mono", 10, MUTED, ls=1) + T(CX + CW - 34, CY + 394, "CEH · EC-COUNCIL", "mono", 10, MUTED, "end", ls=1)
        + bars
        + T(cxm, CY + 466, "@" + P["user"].upper(), "mono", 11, MUTED, "middle", ls=1.5)
        + '<rect class="id-sweep" x="%d" y="%d" width="120" height="%d" fill="url(#id-sweep)" transform="rotate(18 %d %d)">' % (CX - 260, CY - 80, CH + 160, CX, CY)
        + '<animateTransform attributeName="transform" type="translate" additive="sum" begin="0s" dur="7s" repeatCount="indefinite" values="0 0;0 0;640 0;640 0" keyTimes="0;.3;.62;1"/></rect>'
        + "</g>"
        + '<rect x="%d" y="%d" width="%d" height="%d" rx="22" fill="none" stroke="url(#id-hair)" stroke-width="1.5"/>' % (CX, CY, CW, CH)
    )
    sp = "0.42 0 0.58 1"
    lanyard = (
        '<g class="id-drop"><g class="id-swing">'
        '<animateTransform attributeName="transform" type="rotate" begin="0s" dur="5s" fill="freeze" calcMode="spline" '
        'values="0 %d %d;0 %d %d;7 %d %d;-4.8 %d %d;3.1 %d %d;-1.9 %d %d;0 %d %d" keyTimes="0;.2;.34;.5;.66;.82;1" keySplines="%s"/>'
        % ((PX, PY) * 7 + (";".join([sp] * 6),))
        + '<g class="id-swing">'
        '<animateTransform attributeName="transform" type="rotate" begin="0s" dur="4.4s" repeatCount="indefinite" calcMode="spline" '
        'values="0 %d %d;1.7 %d %d;0 %d %d;-1.7 %d %d;0 %d %d" keyTimes="0;.25;.5;.75;1" keySplines="%s"/>'
        % ((PX, PY) * 5 + (";".join([sp] * 4),))
        + card_svg + "</g></g></g>"
    )

    MX = 548
    metrics = [
        ("3,000", "USERS", "Chrome Profile Lock (Secure)", "Chrome Web Store"),
        ("4.2", "RATING", "11 ratings · Profile Lock", "Chrome Web Store"),
        ("948", "DOWNLOADS", "Multi Folder Workspace Opener", "Open VSX · +77 on VS Marketplace"),
        ("5", "ANDROID APPS", "Published as Global Webify", "Google Play"),
    ]
    mc = ""
    for i, (num, lab, cap, src) in enumerate(metrics):
        x, y = MX + (i % 2) * 306, 214 + (i // 2) * 150
        star = ""
        if lab == "RATING":
            sx = x + 26 + tw(num, "display", 58) + 22
            star = '<path transform="translate(%s %d) scale(1.5)" fill="%s" d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7L12 17.2 5.8 20.9l1.6-7L2 9.2l7.1-.6z"/>' % (_n(sx - 14), y + 32, RED)
        mc += '<g class="id-up"%s>%s%s%s%s%s%s</g>' % (
            delay(.9 + i * .12), card(p, x, y, 290, 134, 18),
            T(x + 24, y + 88, num, "display", 58, INK), star,
            T(x + 290 - 22, y + 34, lab, "mono", 12, BLUE if i % 3 == 0 else RED, "end", ls=1.5),
            T(x + 24, y + 110, cap, "body", 15, "#c3cbe0"), T(x + 24, y + 126, src, "mono", 10.5, MUTED, ls=.5))

    repos = [
        ("Cube", "3D voxel builder · hand tracking + WebXR AR", "TypeScript", "#3178C6"),
        ("leadsyncpro", "SaaS CRM in core PHP + MySQL", "PHP", "#777BB4"),
        ("multi-folder-workspace-opener", "Multi-root VS Code workspaces", "TypeScript", "#3178C6"),
    ]
    rp = '<g class="id-up"%s>' % delay(1.4) + T(MX, 538, "PUBLIC REPOSITORIES  ·  4", "mono", 13, MUTED, ls=1.5)
    for i, (n, dsc, lang, col) in enumerate(repos):
        y = 556 + i * 54
        rp += card(p, MX, y, 596, 44, 12) + T(MX + 18, y + 28, n, "mono", 14, INK)
        dx = MX + 18 + tw(n, "mono", 14) + 16
        dot = MX + 596 - 22 - tw(lang, "mono", 12) - 12
        while tw(dsc, "body", 14) > dot - 18 - dx:
            dsc = dsc[:-2].rstrip() + "…"
        rp += T(dx, y + 28, dsc, "body", 14, MUTED)
        rp += '<circle cx="%s" cy="%d" r="5" fill="%s"/>' % (_n(dot), y + 23, col)
        rp += T(MX + 596 - 18, y + 27, lang, "mono", 12, "#c3cbe0", "end")
    rp += "</g>"

    body = (
        '<circle cx="290" cy="440" r="330" fill="url(#id-glowb)"/><circle cx="1100" cy="680" r="260" fill="url(#id-glowr)"/>'
        + lanyard
        + label(p, MX, 78, "03", "ID & DASHBOARD", .5)
        + '<g class="id-up"%s>' % delay(.65) + T(MX - 3, 142, "BUILT. SHIPPED. USED.", "display", 62, INK, ls=1) + "</g>"
        + '<g class="id-up"%s>' % delay(.75) + T(MX, 178, "PUBLIC STORE + GITHUB DATA  ·  CHECKED " + P["checked"], "mono", 13, MUTED, ls=1.2) + "</g>"
        + mc + rp
    )
    css = (
        ".id-drop{animation:id-drop 1.15s cubic-bezier(.3,0,.25,1) both}"
        "@keyframes id-drop{0%{transform:translateY(-780px)}62%{transform:translateY(14px)}80%{transform:translateY(-5px)}100%{transform:none}}"
        "@media (prefers-reduced-motion:reduce){.id-swing{transform:none!important}.id-sweep{display:none}}"
    )
    write("id-dashboard.svg", doc(p, W, H, "Builder ID and verified metrics",
                                  "Chrome Profile Lock: 3,000 users, 4.2 rating from 11 ratings. Multi Folder Workspace Opener: 948 Open VSX downloads plus 77 VS Marketplace installs. 5 Android apps on Google Play. 4 public GitHub repositories. Checked " + P["checked"] + ".",
                                  defs, body, css))


# ================================================================ connect.svg
def connect():
    p, W, H = "cn", 1200, 660
    uri, (iw, ih) = png_uri(POINT_PNG, 600)
    dw = 540
    dh = dw * ih / iw
    globe = ('<circle r="11" fill="none" stroke="{c}" stroke-width="2"/><ellipse rx="5" ry="11" fill="none" stroke="{c}" stroke-width="2"/>'
             '<path d="M-11 0h22M-9 -6h18M-9 6h18" stroke="{c}" stroke-width="1.6"/>')
    puzzle = ('<path fill="{c}" d="M-10 -10h7a3.5 3.5 0 1 1 6 0h7v7a3.5 3.5 0 1 1 0 6v7h-7a3.5 3.5 0 1 0 -6 0h-7v-7a3.5 3.5 0 1 0 0 -6z"/>')
    news = ('<rect x="-11" y="-9" width="22" height="18" rx="3" fill="none" stroke="{c}" stroke-width="2"/>'
            '<path d="M-7 -4h8M-7 0h14M-7 4h14" stroke="{c}" stroke-width="2"/>')
    links = [
        ("GitHub", "github.com/" + P["user"], ("si", "github"), INK),
        ("The News MPCG", "thenewsmpcg.com  ·  latest project", ("raw", news), RED),
        ("Google Play", "5 apps  ·  Global Webify", ("si", "googleplay"), "#3DDC84"),
        ("Chrome Web Store", "Chrome Profile Lock (Secure)", ("si", "googlechrome"), "#4285F4"),
        ("VS Code Marketplace", "Multi Folder Workspace Opener", ("raw", puzzle), BLUE),
        ("Website", "mydaystory.in", ("raw", globe), "#c3cbe0"),
    ]
    X, Y0, CW, CHh, GAP = 584, 214, 566, 62, 12
    cards = ""
    for i, (t, sub, (kind, ic), col) in enumerate(links):
        y = Y0 + i * (CHh + GAP)
        cy = y + CHh / 2
        glyph = icon(ic, 0, 0, 22, col) if kind == "si" else ic.format(c=col)
        cards += ('<g class="cn-up"%s>%s<circle cx="%d" cy="%s" r="20" fill="#121c38"/>'
                  '<g transform="translate(%d %s)">%s</g>%s%s'
                  '<g class="cn-nudge" style="animation-delay:%.2fs"><path d="M%d %s h18 m-7 -7 l7 7 l-7 7" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></g></g>') % (
            delay(.6 + i * .1), card(p, X, y, CW, CHh, 16), X + 34, _n(cy), X + 34, _n(cy), glyph,
            T(X + 70, y + 27, t, "body", 19, INK), T(X + 70, y + 47, sub, "mono", 12.5, MUTED),
            i * .18, X + CW - 46, _n(cy), BLUE if i % 2 == 0 else RED)
    chev = "".join('<path class="cn-chev" style="animation-delay:%.2fs" d="M%d 368 l9 9 l-9 9" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
                   % (k * .18, 548 + k * 12, RED) for k in range(2))
    body = (
        '<circle cx="250" cy="420" r="330" fill="url(#cn-glowb)"/><circle cx="520" cy="560" r="240" fill="url(#cn-glowr)"/>'
        + '<g class="cn-char"><image x="-6" y="%s" width="%d" height="%s" href="%s" xlink:href="%s"/></g>' % (_n(H - dh + 18), dw, _n(dh), uri, uri)
        + chev
        + label(p, X, 78, "04", "CONNECT", .2)
        + '<g class="cn-up"%s>' % delay(.3) + T(X - 3, 144, "LET'S BUILD SOMETHING.", "display", 62, INK, ls=1) + "</g>"
        + '<g class="cn-up"%s>' % delay(.4) + T(X, 182, "Products, code and the latest launch — clickable links are just below.", "body", 17, MUTED) + "</g>"
        + cards
    )
    css = (
        ".cn-char{animation:cn-char 1.1s cubic-bezier(.16,1,.3,1) both}"
        "@keyframes cn-char{from{opacity:0;transform:translateX(-60px)}to{opacity:1;transform:none}}"
        ".cn-nudge,.cn-chev{animation:cn-nudge 1.6s ease-in-out 1.2s infinite both}"
        "@keyframes cn-nudge{0%,100%{transform:none}50%{transform:translateX(6px)}}"
    )
    write("connect.svg", doc(p, W, H, "Connect with Abhishek Kumar",
                             "GitHub, The News MPCG, Google Play, Chrome Web Store, VS Code Marketplace and website. Clickable links are in the README below this image.",
                             "", body, css))


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    hero()
    about()
    stack()
    id_dashboard()
    connect()
