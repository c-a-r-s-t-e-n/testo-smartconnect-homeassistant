"""Build original community branding; Pillow is only needed to regenerate assets."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components/testo_smartconnect/brand"
ASSETS = ROOT / "docs/assets"
NAVY = "#10283D"
ORANGE = "#FF782D"
TEAL = "#32D6C5"


def emblem(size):
    scale = 4
    im = Image.new("RGBA", (size * scale, size * scale))
    d = ImageDraw.Draw(im)

    def box(coords):
        return tuple(round(v * size * scale / 256) for v in coords)

    d.rounded_rectangle(box((8, 8, 248, 248)), radius=size * scale * 0.22, fill=NAVY)
    # Distinctive cloud outline, thermometer and an uninterrupted telemetry trace.
    d.arc(box((119, 48, 194, 123)), 180, 340, fill=TEAL, width=round(size * scale * 0.03125))
    d.arc(box((170, 76, 221, 127)), 230, 90, fill=TEAL, width=round(size * scale * 0.03125))
    d.line([box((148, 127)), box((196, 127))], fill=TEAL, width=round(size * scale * 0.03125))
    d.rounded_rectangle(box((65, 47, 106, 170)), radius=round(size * scale * 0.08), fill="white")
    d.ellipse(box((51, 143, 120, 212)), fill="white")
    d.rounded_rectangle(box((78, 74, 93, 178)), radius=round(size * scale * 0.03), fill=ORANGE)
    d.ellipse(box((66, 158, 105, 197)), fill=ORANGE)
    d.line(
        [box((128, 182)), box((149, 182)), box((162, 157)), box((178, 194)), box((193, 169)), box((215, 169))],
        fill=TEAL,
        width=round(size * scale * 0.025),
        joint="curve",
    )
    return im.resize((size, size), Image.Resampling.LANCZOS)


def font(size, bold=False):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans" + ("-Bold" if bold else "") + ".ttf", size)


def main():
    BRAND.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for factor in (1, 2):
        suffix = "@2x" if factor == 2 else ""
        icon = emblem(256 * factor)
        for prefix in ("", "dark_"):
            icon.save(BRAND / f"{prefix}icon{suffix}.png", optimize=True)
        for dark in (False, True):
            logo = Image.new("RGBA", (1000 * factor, 256 * factor))
            logo.alpha_composite(icon, (0, 0))
            d = ImageDraw.Draw(logo)
            d.text(
                (286 * factor, 52 * factor),
                "Testo Smart Connect",
                font=font(48 * factor, True),
                fill="white" if dark else NAVY,
            )
            d.text(
                (289 * factor, 124 * factor),
                "HOME ASSISTANT  /  COMMUNITY",
                font=font(24 * factor),
                fill=TEAL if dark else "#35546B",
            )
            logo.save(BRAND / f"{'dark_' if dark else ''}logo{suffix}.png", optimize=True)
    banner = Image.new("RGB", (1600, 480), NAVY)
    d = ImageDraw.Draw(banner)
    d.rounded_rectangle((1130, -170, 1690, 390), radius=150, outline="#1B3A50", width=3)
    d.rounded_rectangle((1240, 140, 1790, 690), radius=150, outline="#1B3A50", width=3)
    banner.paste(emblem(290), (70, 80), emblem(290))
    d.text((405, 89), "TESTO SMART CONNECT", font=font(52, True), fill="white")
    d.text((408, 169), "Your cold chain. Clearly connected.", font=font(32), fill="#C8DAE5")
    d.text((409, 235), "Measurements  ·  Logger health  ·  Alarm insight", font=font(23), fill=TEAL)
    d.rounded_rectangle((410, 315, 890, 365), radius=25, fill="#213F53")
    d.text((433, 325), "HOME ASSISTANT  /  COMMUNITY", font=font(21, True), fill="white")
    banner.save(ASSETS / "header.png", optimize=True)


if __name__ == "__main__":
    main()
