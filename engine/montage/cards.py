"""Карточки поверх кадра: крючок, чип, финальная карточка. Полнокадровый PNG 1080×1920 с альфой.

Лист держит `cards`: [{"id", "t0", "t1", "lines": [{"t", "color", "size", "font"}], "font", "size",
"bg", "bg_alpha", "radius", "pad", "y" | "center", "dim", "fade"}]:
    pill   — строки на скруглённой подложке (bg), по центру по горизонтали, верх на y
    dim    — затемнить весь кадр (0–255) под карточкой — для финала
Шрифт — имя файла без .ttf (Inter-ExtraBold…): ~/Library/Fonts, затем системные; нет — системный запасной.
Верх карточки не выше 260 px (шапка IG), низ — не ниже безопасной зоны; нарушение — предупреждение.
"""
import os

from PIL import Image, ImageDraw, ImageFont

from . import config, core


def _font(name, size):
    p = config.font_path(name)
    if not p:
        raise SystemExit(f"нет шрифта {name} и системного запасного")
    return ImageFont.truetype(p, size)


def _rgba(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def render(spec, out):
    W, H = config.FRAME_W, config.FRAME_H
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if spec.get("dim"):
        img.paste(Image.new("RGBA", (W, H), (0, 0, 0, int(spec["dim"]))), (0, 0))
        d = ImageDraw.Draw(img)
    font_name, size = spec.get("font", "Inter-ExtraBold"), int(spec.get("size", 44))
    lines = []
    for ln in spec["lines"]:
        f = _font(ln.get("font", font_name), int(ln.get("size", size)))
        box = d.textbbox((0, 0), ln["t"], font=f)
        lines.append((ln, f, box[2] - box[0], box[3] - box[1], box))
    gap = int(spec.get("gap", size * 0.25))
    pad_x, pad_y = spec.get("pad", [40, 26])
    tw = max(l[2] for l in lines)
    th = sum(l[3] for l in lines) + gap * (len(lines) - 1)
    bw, bh = tw + 2 * pad_x, th + 2 * pad_y
    y0 = int(spec["y"]) if "y" in spec else (H - bh) // 2
    x0 = (W - bw) // 2
    if y0 < config.IG_HEADER and not spec.get("dim"):
        core.say(f"! карточка {spec.get('id')}: верх {y0} px выше шапки IG ({config.IG_HEADER})")
    if spec.get("bg"):
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(spec.get("radius", 36)),
                            fill=_rgba(spec["bg"], int(spec.get("bg_alpha", 235))))
    y = y0 + pad_y
    for ln, f, w, h, box in lines:
        d.text(((W - w) // 2 - box[0], y - box[1]), ln["t"], font=f, fill=_rgba(ln.get("color", "#ffffff")))
        y += h + gap
    img.save(out)
    return out


def run(project):
    ed = project.edit
    specs = ed.get("cards") or []
    cdir = os.path.join(project.work, "cards")
    os.makedirs(cdir, exist_ok=True)
    ovs = [o for o in ed.get("overlays", []) if o.get("from") != "cards"]
    for sp in specs:
        png = render(sp, os.path.join(cdir, f"card_{sp['id']}.png"))
        ovs.append({"from": "cards", "id": sp["id"], "png": project.relpath(png), "t0": sp["t0"], "t1": sp["t1"],
                    "x": 0, "y": 0, "fade": sp.get("fade", 0.25)})
    ed["overlays"] = ovs
    project.save()
    if specs:
        core.say(f"карточки: {len(specs)} шт. → {project.relpath(cdir)}")
    return ovs
