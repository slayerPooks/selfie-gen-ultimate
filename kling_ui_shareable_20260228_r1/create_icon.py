"""
Kling UI Icon Generator
Generates a professional multi-size .ico file for the app.

Design:
- Dark navy/charcoal rounded-square background
- Vibrant blue/indigo gradient circle
- Bold white play triangle
- Subtle "K" text at bottom-right
"""

import sys
import math
from pathlib import Path


def draw_rounded_rect(draw, box, radius, fill, outline=None, outline_width=1):
    """Draw a filled rounded rectangle."""
    x0, y0, x1, y1 = box
    r = max(2, int(radius))

    # Fill
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    draw.ellipse([x0, y0, x0 + 2*r, y0 + 2*r], fill=fill)
    draw.ellipse([x1 - 2*r, y0, x1, y0 + 2*r], fill=fill)
    draw.ellipse([x0, y1 - 2*r, x0 + 2*r, y1], fill=fill)
    draw.ellipse([x1 - 2*r, y1 - 2*r, x1, y1], fill=fill)

    if outline:
        draw.arc([x0, y0, x0 + 2*r, y0 + 2*r], 180, 270, fill=outline, width=outline_width)
        draw.arc([x1 - 2*r, y0, x1, y0 + 2*r], 270, 360, fill=outline, width=outline_width)
        draw.arc([x0, y1 - 2*r, x0 + 2*r, y1], 90, 180, fill=outline, width=outline_width)
        draw.arc([x1 - 2*r, y1 - 2*r, x1, y1], 0, 90, fill=outline, width=outline_width)
        draw.line([x0 + r, y0, x1 - r, y0], fill=outline, width=outline_width)
        draw.line([x0 + r, y1, x1 - r, y1], fill=outline, width=outline_width)
        draw.line([x0, y0 + r, x0, y1 - r], fill=outline, width=outline_width)
        draw.line([x1, y0 + r, x1, y1 - r], fill=outline, width=outline_width)


def lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB(A) colors."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def draw_gradient_circle(img, cx, cy, radius, color_inner, color_outer):
    """Draw a radial gradient circle using pixel-level manipulation."""
    from PIL import Image
    # Create gradient overlay
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    pixels = overlay.load()

    r2 = radius * radius
    x0 = max(0, int(cx - radius))
    x1 = min(img.size[0], int(cx + radius + 1))
    y0 = max(0, int(cy - radius))
    y1 = min(img.size[1], int(cy + radius + 1))

    for py in range(y0, y1):
        for px in range(x0, x1):
            dx = px - cx
            dy = py - cy
            dist2 = dx * dx + dy * dy
            if dist2 <= r2:
                t = math.sqrt(dist2) / radius
                # Smooth falloff
                t_smooth = t * t * (3 - 2 * t)
                color = lerp_color(color_inner, color_outer, t_smooth)
                pixels[px, py] = color

    return overlay


def render_icon(size):
    """Render a single icon at the given size."""
    from PIL import Image, ImageDraw

    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Background ---
    bg_color = (28, 28, 38, 255)          # Deep dark navy
    border_color = (55, 55, 75, 255)       # Subtle border
    pad = max(0, size // 20)
    radius = max(3, size // 5)
    draw_rounded_rect(draw, [pad, pad, size - 1 - pad, size - 1 - pad],
                      radius, bg_color, border_color, max(1, size // 64))

    # --- Gradient circle (glow behind play button) ---
    cx = size * 0.50
    cy = size * 0.47
    circle_r = size * 0.34

    # Draw glow using gradient circle
    color_inner = (80, 130, 255, 220)      # Bright blue center
    color_outer = (50, 70, 160, 0)         # Fade to transparent
    glow = draw_gradient_circle(img, cx, cy, circle_r * 1.4,
                                color_inner, color_outer)
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Solid circle background
    circ_x0 = cx - circle_r
    circ_y0 = cy - circle_r
    circ_x1 = cx + circle_r
    circ_y1 = cy + circle_r
    draw.ellipse([circ_x0, circ_y0, circ_x1, circ_y1],
                 fill=(55, 95, 200, 230))

    # Inner circle highlight (top-left sheen)
    sheen_r = circle_r * 0.65
    draw.ellipse([cx - sheen_r, cy - sheen_r - circle_r * 0.08,
                  cx + sheen_r * 0.1, cy + sheen_r * 0.5],
                 fill=(100, 150, 255, 60))

    # --- Play triangle ---
    tri_scale = circle_r * 0.52
    # Center the triangle (slightly right for optical balance)
    tx = cx + tri_scale * 0.08
    ty = cy

    pts = [
        (tx - tri_scale * 0.45, ty - tri_scale * 0.72),  # top-left
        (tx - tri_scale * 0.45, ty + tri_scale * 0.72),  # bottom-left
        (tx + tri_scale * 0.80, ty),                      # right tip
    ]
    draw.polygon(pts, fill=(240, 245, 255, 255))

    # Play triangle subtle inner highlight
    inner_scale = tri_scale * 0.6
    inner_pts = [
        (tx - inner_scale * 0.42, ty - inner_scale * 0.55),
        (tx - inner_scale * 0.42, ty - inner_scale * 0.05),
        (tx + inner_scale * 0.20, ty - inner_scale * 0.28),
    ]
    draw.polygon(inner_pts, fill=(255, 255, 255, 50))

    # --- Film strip notches (left & right of circle, only at larger sizes) ---
    if size >= 48:
        notch_w = max(2, size // 20)
        notch_h = max(2, size // 14)
        notch_gap = size // 10
        notch_x_left = pad + size // 14
        notch_x_right = size - pad - size // 14 - notch_w

        strip_y_positions = [
            int(cy - notch_gap),
            int(cy),
            int(cy + notch_gap),
        ]
        notch_color = (80, 110, 200, 180)
        for sy in strip_y_positions:
            # Left notch
            draw.rectangle(
                [notch_x_left, sy - notch_h//2,
                 notch_x_left + notch_w, sy + notch_h//2],
                fill=notch_color
            )
            # Right notch
            draw.rectangle(
                [notch_x_right, sy - notch_h//2,
                 notch_x_right + notch_w, sy + notch_h//2],
                fill=notch_color
            )

    # --- "K" branding text (only at larger sizes) ---
    if size >= 64:
        try:
            from PIL import ImageFont
            font_size = max(8, size // 7)
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
            except Exception:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()

            # Draw "K" at bottom-right with semi-transparent blue
            k_x = size - pad - font_size - size // 12
            k_y = size - pad - font_size - size // 14
            # Shadow
            draw.text((k_x + 1, k_y + 1), "K", font=font, fill=(0, 0, 0, 120))
            # Main text
            draw.text((k_x, k_y), "K", font=font, fill=(180, 210, 255, 200))
        except Exception:
            pass

    return img


def create_ico(output_path: str = "kling_ui.ico"):
    """Create the multi-size .ico file."""
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is not installed. Run: pip install Pillow")
        sys.exit(1)

    print("Generating Kling UI icon...")
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        print(f"  Rendering {size}x{size}...")
        img = render_icon(size)
        images.append(img)

    print(f"  Saving {output_path}...")
    # Save largest image as base; append all others.
    # Do NOT pass sizes= — that makes Pillow rescale from source instead of
    # preserving our per-size renders.
    base = images[-1]   # 256x256 is the base
    rest = images[:-1]  # [16, 32, 48, 64, 128]
    base.save(
        output_path,
        format='ICO',
        append_images=rest,
    )
    print(f"  Done! Icon saved to: {output_path}")
    # Quick sanity check
    size_bytes = Path(output_path).stat().st_size
    print(f"  File size: {size_bytes:,} bytes")

    # Also save a PNG preview (256x256)
    preview_path = output_path.replace('.ico', '_preview.png')
    images[-1].save(preview_path, format='PNG')
    print(f"  Preview saved to: {preview_path}")

    return output_path


if __name__ == "__main__":
    import os
    # Output next to this script
    script_dir = Path(__file__).parent
    ico_path = str(script_dir / "kling_ui.ico")
    create_ico(ico_path)
    print("\nIcon generation complete!")
