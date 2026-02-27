"""
stamp_generator.py
==================
Core stamp generation logic for StampForge.
All four styles (A-D) are generated as high-resolution PNG images using Pillow.
"""

import os
import math
import uuid
import datetime
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
from config import Config


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _unique_filename(prefix, ext="png"):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    return f"{prefix}_{ts}_{uid}.{ext}"


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _darken(rgb, factor=0.7):
    return tuple(max(0, int(c * factor)) for c in rgb)


def _lighten(rgb, factor=1.4):
    return tuple(min(255, int(c * factor)) for c in rgb)


def _load_font(size, bold=False):
    """Try to load a system font; fall back to default."""
    font_dir = Config.FONTS_FOLDER
    candidates_bold = [
        os.path.join(font_dir, "DejaVuSans-Bold.ttf"),
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    candidates_regular = [
        os.path.join(font_dir, "DejaVuSans.ttf"),
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    candidates = candidates_bold if bold else candidates_regular
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_text_on_arc(draw, text, center, radius, start_angle, font, fill, clockwise=True):
    """Draw text along a circular arc."""
    cx, cy = center
    chars = list(text)
    total_chars = len(chars)
    if total_chars == 0:
        return

    # Estimate angle per character
    char_w = _text_size(draw, "M", font)[0]
    arc_len = 2 * math.pi * radius
    angle_per_char = math.degrees(char_w / radius)
    total_angle = angle_per_char * total_chars
    current_angle = start_angle - total_angle / 2

    for ch in chars:
        rad = math.radians(current_angle)
        if clockwise:
            x = cx + radius * math.cos(rad)
            y = cy + radius * math.sin(rad)
            rotation = current_angle + 90
        else:
            x = cx + radius * math.cos(rad)
            y = cy - radius * math.sin(rad)
            rotation = -(current_angle + 90)

        # Create a small image for each character and rotate it
        cw, ch_h = _text_size(draw, ch, font)
        cw = max(cw, 1); ch_h = max(ch_h, 1)
        char_img = Image.new("RGBA", (cw + 4, ch_h + 4), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((2, 2), ch, font=font, fill=fill)
        char_img = char_img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
        # Paste onto the main image's underlying image
        # We use draw._image which is the underlying PIL image
        try:
            img = draw._image
            img.paste(char_img, (int(x - char_img.width // 2), int(y - char_img.height // 2)), char_img)
        except Exception:
            draw.text((x, y), ch, font=font, fill=fill)
        current_angle += angle_per_char


def _load_logo(logo_path, size):
    """Load and resize an organization logo with a white circular mask."""
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize(size, Image.LANCZOS)
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size[0]-1, size[1]-1), fill=255)
        logo.putalpha(mask)
        return logo
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Style A — Circular Seal
# ---------------------------------------------------------------------------

def generate_style_a(staff, org, color="#1a2b5e", size="medium", options=None):
    """
    Circular seal stamp.
    - Outer ring: org name (top arc) + stamp ID / date (bottom arc)
    - Inner content: staff name + title
    - Optional logo in center
    """
    options = options or {}
    w, h = Config.STAMP_SIZES.get(size, Config.STAMP_SIZES["medium"])
    scale = w / 500  # scale relative to 500px reference

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    primary = _hex_to_rgb(color)
    dark = _darken(primary, 0.75)

    # Ring thicknesses scaled
    outer_r    = int(cx * 0.92)
    ring_thick = int(cx * 0.08)
    inner_r    = outer_r - ring_thick
    gap_r      = inner_r - int(cx * 0.04)
    center_r   = gap_r

    # Draw outer filled circle
    draw.ellipse(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        fill=primary
    )
    # White inner circle (ring space)
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        fill=(255, 255, 255, 255)
    )
    # Thin border inside the ring
    bw = max(2, int(cx * 0.012))
    draw.ellipse(
        [cx - gap_r, cy - gap_r, cx + gap_r, cy + gap_r],
        outline=primary, width=bw
    )

    # ---- Arc text ----
    arc_font_size = max(14, int(24 * scale))
    arc_font = _load_font(arc_font_size, bold=True)

    org_name = org.get("name", "Organization")
    dept = staff.get("department", "")

    # Top arc: org name (upper semicircle)
    _draw_text_on_arc(draw, org_name.upper(), (cx, cy),
                      radius=int((outer_r + inner_r) / 2),
                      start_angle=270, font=arc_font,
                      fill=(255, 255, 255, 255), clockwise=True)

    # Bottom arc: department
    _draw_text_on_arc(draw, dept.upper(), (cx, cy),
                      radius=int((outer_r + inner_r) / 2),
                      start_angle=90, font=arc_font,
                      fill=(255, 255, 255, 255), clockwise=False)

    # ---- Center content ----
    name_font_size  = max(16, int(28 * scale))
    title_font_size = max(12, int(18 * scale))
    small_font_size = max(10, int(14 * scale))

    name_font  = _load_font(name_font_size,  bold=True)
    title_font = _load_font(title_font_size, bold=False)
    small_font = _load_font(small_font_size, bold=False)

    # Optional logo
    logo_path = org.get("logo_path")
    logo_size = int(center_r * 0.55)
    logo_y_offset = -int(center_r * 0.22)

    if logo_path and os.path.exists(logo_path) and options.get("show_logo", True):
        logo = _load_logo(logo_path, (logo_size, logo_size))
        if logo:
            lx = cx - logo_size // 2
            ly = cy + logo_y_offset - logo_size // 2
            img.paste(logo, (lx, ly), logo)
            text_start_y = cy + logo_y_offset + logo_size // 2 + int(4 * scale)
        else:
            text_start_y = cy - int(center_r * 0.35)
    else:
        text_start_y = cy - int(center_r * 0.35)

    # Name
    name_text = staff.get("full_name", "Staff Member")
    nw, nh = _text_size(draw, name_text, name_font)
    draw.text((cx - nw // 2, text_start_y), name_text, font=name_font, fill=primary)

    # Title
    title_text = staff.get("job_title", "")
    tw, th = _text_size(draw, title_text, title_font)
    draw.text((cx - tw // 2, text_start_y + nh + int(4 * scale)),
              title_text, font=title_font, fill=dark)

    # Stamp ID + date
    stamp_id = options.get("stamp_id", f"SF-{uuid.uuid4().hex[:8].upper()}")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if options.get("show_date", True):
        id_text  = f"ID: {stamp_id}"
        date_text = f"Date: {date_str}"
        iy, ih = text_start_y + nh + th + int(16 * scale), 0
        iw, ih = _text_size(draw, id_text, small_font)
        draw.text((cx - iw // 2, iy), id_text, font=small_font, fill=dark)
        dw, dh = _text_size(draw, date_text, small_font)
        draw.text((cx - dw // 2, iy + ih + int(2 * scale)), date_text, font=small_font, fill=dark)

    # Outer border
    draw.ellipse(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        outline=dark, width=max(2, int(cx * 0.008))
    )

    return _save_image(img, "style_a")


# ---------------------------------------------------------------------------
# Style B — Rectangular Approval Stamp
# ---------------------------------------------------------------------------

COLOR_MAP = {
    "green":  ("#1a7a4a", "#e8f5ee"),
    "red":    ("#b91c1c", "#fef2f2"),
    "blue":   ("#1a2b5e", "#eff6ff"),
    "orange": ("#c2550a", "#fff7ed"),
}

LABEL_MAP = {
    "green":  "APPROVED",
    "red":    "REJECTED",
    "blue":   "REVIEWED",
    "orange": "PENDING",
}

def generate_style_b(staff, org, color="green", size="medium", options=None):
    """Rectangular approval stamp with rounded corners."""
    options = options or {}
    color_key = color if color in COLOR_MAP else "green"
    border_hex, bg_hex = COLOR_MAP[color_key]
    border_rgb = _hex_to_rgb(border_hex)
    bg_rgb     = _hex_to_rgb(bg_hex)

    rw, rh = Config.RECT_STAMP_SIZES.get(size, Config.RECT_STAMP_SIZES["medium"])
    scale = rw / 600

    img  = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(rh * 0.12)
    bw     = max(3, int(rh * 0.025))

    # Background
    draw.rounded_rectangle([0, 0, rw - 1, rh - 1], radius=radius, fill=bg_rgb + (255,))
    # Border (drawn as multiple lines for thickness)
    for i in range(bw):
        draw.rounded_rectangle([i, i, rw - 1 - i, rh - 1 - i], radius=radius - i,
                                outline=border_rgb + (255,))

    # Fonts
    label_font = _load_font(max(18, int(34 * scale)), bold=True)
    by_font    = _load_font(max(12, int(18 * scale)), bold=False)
    name_font  = _load_font(max(16, int(26 * scale)), bold=True)
    small_font = _load_font(max(10, int(14 * scale)), bold=False)

    # Layout zones
    pad = int(rw * 0.05)
    y   = int(rh * 0.08)

    # "APPROVED BY" label
    custom_label = options.get("custom_label") or LABEL_MAP[color_key]
    lw, lh = _text_size(draw, custom_label, label_font)
    draw.text(((rw - lw) // 2, y), custom_label, font=label_font, fill=border_rgb + (255,))
    y += lh + int(4 * scale)

    # Separator line
    sx = pad; ex = rw - pad
    draw.line([(sx, y), (ex, y)], fill=border_rgb + (180,), width=max(1, int(1.5 * scale)))
    y += int(10 * scale)

    # "BY:" prefix + staff name
    by_text = "BY:"
    byw, byh = _text_size(draw, by_text, by_font)
    draw.text((pad, y), by_text, font=by_font, fill=border_rgb + (200,))

    name_text = staff.get("full_name", "Staff Member")
    nw, nh = _text_size(draw, name_text, name_font)
    draw.text(((rw - nw) // 2, y), name_text, font=name_font, fill=border_rgb + (255,))
    y += max(nh, byh) + int(6 * scale)

    # Title
    title_text = staff.get("job_title", "")
    tw, th = _text_size(draw, title_text, small_font)
    draw.text(((rw - tw) // 2, y), title_text, font=small_font, fill=border_rgb + (200,))
    y += th + int(4 * scale)

    # Department
    dept_text = staff.get("department", "")
    dw, dh = _text_size(draw, dept_text, small_font)
    draw.text(((rw - dw) // 2, y), dept_text, font=small_font, fill=border_rgb + (180,))
    y += dh + int(6 * scale)

    # Bottom divider
    draw.line([(sx, y), (ex, y)], fill=border_rgb + (120,), width=max(1, int(scale)))
    y += int(8 * scale)

    # Stamp ID + Date
    stamp_id  = options.get("stamp_id", f"SF-{uuid.uuid4().hex[:8].upper()}")
    date_str  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    footer    = f"ID: {stamp_id}   |   {date_str}"
    fw, fh    = _text_size(draw, footer, small_font)
    draw.text(((rw - fw) // 2, y), footer, font=small_font, fill=border_rgb + (160,))

    return _save_image(img, "style_b")


# ---------------------------------------------------------------------------
# Style C — Signature Style
# ---------------------------------------------------------------------------

def generate_style_c(staff, org, color="#1a2b5e", size="medium", options=None):
    """
    Signature-style stamp.
    - If `options['signature_image_path']` is set (drawn e-signature), composites
      the actual hand-drawn signature image onto the stamp.
    - Otherwise falls back to a handwriting-font text rendering.
    """
    options = options or {}
    # Landscape canvas
    sizes = {"small": (450, 180), "medium": (650, 260), "large": (950, 370)}
    sw, sh = sizes.get(size, sizes["medium"])
    scale  = sw / 650

    img  = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    primary = _hex_to_rgb(color)

    pad      = int(sw * 0.05)
    line_end = sw - pad

    # --- Shared footer info ---
    name_font  = _load_font(max(13, int(19 * scale)), bold=False)
    small_font = _load_font(max(10, int(13 * scale)), bold=False)
    title_text = staff.get("job_title",   "")
    dept_text  = staff.get("department",  "")
    date_str   = datetime.datetime.now().strftime("%Y-%m-%d")
    stamp_id   = options.get("stamp_id", f"SF-{uuid.uuid4().hex[:8].upper()}")

    sig_img_path = options.get("signature_image_path")
    # Resolve relative paths
    if sig_img_path and not os.path.isabs(sig_img_path):
        sig_img_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "static",
            sig_img_path.lstrip("/\\")
        )

    # ------------------------------------------------------------------ #
    # Branch A — drawn e-signature exists: composite it                   #
    # ------------------------------------------------------------------ #
    if sig_img_path and os.path.exists(sig_img_path):
        try:
            sig_raw = Image.open(sig_img_path).convert("RGBA")

            # Tint the signature to the chosen color
            # (replaces dark pixels with primary color, keeps transparency)
            r, g, b = primary
            tinted = Image.new("RGBA", sig_raw.size, (0, 0, 0, 0))
            for px_x in range(0, sig_raw.width, 1):
                pass  # handled via pixel operations below — use faster method
            data = sig_raw.getdata()
            new_data = []
            for item in data:
                # Pixels that are dark (drawn strokes) → primary color
                brightness = (item[0] + item[1] + item[2]) / 3
                if item[3] > 10 and brightness < 180:
                    new_data.append((r, g, b, item[3]))
                else:
                    new_data.append((255, 255, 255, 0))  # transparent
            tinted.putdata(new_data)

            # Fit the tinted signature into the upper 60% of the canvas
            max_sig_w = sw - 2 * pad
            max_sig_h = int(sh * 0.58)
            sig_ratio = tinted.width / tinted.height
            if tinted.width > max_sig_w or tinted.height > max_sig_h:
                if tinted.width / max_sig_w > tinted.height / max_sig_h:
                    new_w = max_sig_w
                    new_h = int(max_sig_w / sig_ratio)
                else:
                    new_h = max_sig_h
                    new_w = int(max_sig_h * sig_ratio)
                tinted = tinted.resize((new_w, new_h), Image.LANCZOS)

            sig_x = pad
            sig_y = int(sh * 0.06)
            img.paste(tinted, (sig_x, sig_y), tinted)
            line_y = sig_y + tinted.height + int(8 * scale)

        except Exception:
            line_y = _draw_text_signature(draw, img, staff, primary, scale, sw, sh, pad)

    # ------------------------------------------------------------------ #
    # Branch B — no drawn signature: render name in script font           #
    # ------------------------------------------------------------------ #
    else:
        line_y = _draw_text_signature(draw, img, staff, primary, scale, sw, sh, pad)

    # ---- Signature line ----
    line_w = max(2, int(2.5 * scale))
    draw.line([(pad, line_y), (line_end, line_y)], fill=(*primary, 200), width=line_w)

    # ---- Footer: title | dept ----
    below_y   = line_y + int(8 * scale)
    sub_parts = [p for p in [title_text, dept_text] if p]
    sub_text  = "  |  ".join(sub_parts)
    sw2, sh2  = _text_size(draw, sub_text, name_font)
    draw.text((pad, below_y), sub_text, font=name_font, fill=(*primary, 180))

    if options.get("show_date", True):
        date_text = f"{date_str}   ID: {stamp_id}"
        dw, dh    = _text_size(draw, date_text, small_font)
        draw.text((line_end - dw, below_y + sh2 - dh + int(2 * scale)),
                  date_text, font=small_font, fill=(*primary, 130))

    return _save_image(img, "style_c")


def _draw_text_signature(draw, img, staff, primary, scale, sw, sh, pad):
    """Helper: render the staff name in a script font. Returns the y of the baseline."""
    sig_candidates = [
        os.path.join(Config.FONTS_FOLDER, "GreatVibes-Regular.ttf"),
        os.path.join(Config.FONTS_FOLDER, "Satisfy-Regular.ttf"),
        "C:/Windows/Fonts/BRADHITC.TTF",
        "C:/Windows/Fonts/KUNSTLER.TTF",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrii.ttf",
    ]
    sig_font_size = max(40, int(72 * scale))
    sig_font = None
    for path in sig_candidates:
        if os.path.exists(path):
            try:
                sig_font = ImageFont.truetype(path, sig_font_size)
                break
            except Exception:
                continue
    if sig_font is None:
        sig_font = _load_font(sig_font_size, bold=True)

    name_text = staff.get("full_name", "Staff Member")
    nw, nh = _text_size(draw, name_text, sig_font)
    name_x = pad
    name_y = int(sh * 0.06)
    # Shadow
    draw.text((name_x + 2, name_y + 2), name_text, font=sig_font, fill=(*primary, 55))
    draw.text((name_x, name_y),          name_text, font=sig_font, fill=(*primary, 225))
    return name_y + nh + int(6 * scale)


# ---------------------------------------------------------------------------
# Style D — QR-Verified Stamp
# ---------------------------------------------------------------------------

def generate_style_d(staff, org, color="#1a2b5e", size="medium", options=None):
    """Circular stamp with a QR code center encoding staff verification info."""
    options = options or {}
    w, h = Config.STAMP_SIZES.get(size, Config.STAMP_SIZES["medium"])
    scale = w / 500

    primary = _hex_to_rgb(color)
    dark    = _darken(primary, 0.75)

    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    outer_r  = int(cx * 0.92)
    ring_thk = int(cx * 0.10)
    inner_r  = outer_r - ring_thk
    gap_r    = inner_r - int(cx * 0.03)

    # Outer ring
    draw.ellipse([cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
                 fill=primary)
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                 fill=(255, 255, 255, 255))
    bw = max(2, int(cx * 0.012))
    draw.ellipse([cx - gap_r, cy - gap_r, cx + gap_r, cy + gap_r],
                 outline=primary, width=bw)

    # Arc text
    arc_font_size = max(14, int(22 * scale))
    arc_font = _load_font(arc_font_size, bold=True)
    org_name = org.get("name", "Organization")
    emp_id   = staff.get("employee_id", "")

    _draw_text_on_arc(draw, org_name.upper(), (cx, cy),
                      radius=int((outer_r + inner_r) / 2),
                      start_angle=270, font=arc_font,
                      fill=(255, 255, 255, 255), clockwise=True)
    _draw_text_on_arc(draw, f"ID: {emp_id}", (cx, cy),
                      radius=int((outer_r + inner_r) / 2),
                      start_angle=90, font=arc_font,
                      fill=(255, 255, 255, 255), clockwise=False)

    # QR code
    stamp_id  = options.get("stamp_id", f"SF-{uuid.uuid4().hex[:8].upper()}")
    verify_url = (f"{Config.VERIFICATION_BASE_URL}?"
                  f"id={stamp_id}&staff={emp_id}&ts={datetime.datetime.now().isoformat()}")

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=4, border=1)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    qr_size = int(gap_r * 1.3)
    qr_img  = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    # White circle background for QR
    qr_bg = Image.new("RGBA", (qr_size, qr_size), (255, 255, 255, 0))
    mask  = Image.new("L", (qr_size, qr_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, qr_size - 1, qr_size - 1), fill=255)
    qr_bg.paste(qr_img, (0, 0))

    qx = cx - qr_size // 2
    qy = cy - qr_size // 2
    img.paste(qr_img, (qx, qy))

    # Name below QR (small)
    name_font = _load_font(max(12, int(18 * scale)), bold=True)
    name_text = staff.get("full_name", "")
    nw, nh    = _text_size(draw, name_text, name_font)
    # Place inside circle below QR
    text_y = cy + qr_size // 2 + int(4 * scale)
    if text_y + nh < cy + gap_r - int(8 * scale):
        draw.text((cx - nw // 2, text_y), name_text, font=name_font, fill=primary)

    # Outer border
    draw.ellipse([cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
                 outline=dark, width=max(2, int(cx * 0.008)))

    return _save_image(img, "style_d")


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def _save_image(img, prefix):
    """Save image to the generated folder and return relative URL path."""
    _ensure_dir(Config.GENERATED_FOLDER)
    filename = _unique_filename(prefix)
    full_path = os.path.join(Config.GENERATED_FOLDER, filename)
    # Composite onto white for JPEG-friendly preview, keep PNG for transparency
    final = Image.new("RGBA", img.size, (255, 255, 255, 0))
    final.paste(img, (0, 0), img)
    final.save(full_path, "PNG", dpi=(Config.STAMP_DPI, Config.STAMP_DPI))
    # Return relative path from static folder
    return os.path.join("generated", filename).replace("\\", "/")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

STYLE_FUNCS = {
    "A": generate_style_a,
    "B": generate_style_b,
    "C": generate_style_c,
    "D": generate_style_d,
}

def generate_stamp(staff: dict, org: dict, style: str, color: str = None,
                   size: str = "medium", options: dict = None) -> str:
    """
    Generate a stamp image.

    Returns the relative path (from static/) of the saved PNG.
    Raises ValueError for unknown styles.
    """
    style = style.upper()
    if style not in STYLE_FUNCS:
        raise ValueError(f"Unknown stamp style '{style}'. Choose from A, B, C, D.")

    # Resolve logo path to absolute
    org = dict(org)
    if org.get("logo_path"):
        logo_rel = org["logo_path"]
        if not os.path.isabs(logo_rel):
            org["logo_path"] = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "static", logo_rel.lstrip("/\\")
            )

    defaults = {
        "A": "#1a2b5e",
        "B": "green",
        "C": "#1a2b5e",
        "D": "#1a2b5e",
    }
    if color is None:
        color = defaults[style]

    options = options or {}
    options.setdefault("stamp_id", f"SF-{uuid.uuid4().hex[:8].upper()}")
    options.setdefault("show_date", True)
    options.setdefault("show_logo", True)

    func = STYLE_FUNCS[style]
    return func(staff, org, color=color, size=size, options=options)
