"""Контактный лист: весь ролик одной картинкой — смотреть глазами перед показом владельцу.

Кадры равномерно, каждый подписан секундой; `safe` рисует поверх зону интерфейса Reels/TikTok/
Shorts (верх, низ, правый столбец кнопок) — текст и лицо под ней зритель не увидит.
Первый кадр — почти с нуля (крючок судится по нему), последний — за 0,3 с до конца (быстрый
поиск у хвоста промахивается мимо последнего кадра).
"""
import os
import tempfile

from PIL import Image, ImageDraw, ImageFont

from . import config, core


def draw_safe(im, scale):
    d = ImageDraw.Draw(im, "RGBA")
    w, h = im.size
    d.rectangle([0, 0, w, config.UI_TOP * scale], fill=(255, 0, 0, 46))
    d.rectangle([0, h - config.UI_BOTTOM * scale, w, h], fill=(255, 0, 0, 46))
    d.rectangle([w - config.UI_RIGHT * scale, h * 0.45, w, h], fill=(255, 0, 0, 46))
    sx, sy = (w - config.SAFE_W * scale) / 2, (h - config.SAFE_H * scale) / 2
    d.rectangle([sx, sy, sx + config.SAFE_W * scale, sy + config.SAFE_H * scale],
                outline=(0, 255, 128, 200), width=max(1, int(2 * scale)))
    d.line([0, config.IG_HEADER * scale, w, config.IG_HEADER * scale], fill=(255, 200, 0, 160),
           width=max(1, int(scale * 2)))


def _font(size):
    p = config.font_path("Inter-SemiBold")
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


def _label(im, text, size):
    d = ImageDraw.Draw(im, "RGBA")
    f = _font(size)
    box = d.textbbox((0, 0), text, font=f)
    pad = size // 3
    d.rectangle([0, 0, box[2] + pad * 2, box[3] + pad * 2], fill=(0, 0, 0, 210))
    d.text((pad, pad), text, font=f, fill=(255, 255, 255, 255))


def sheet(video, out, n=12, cols=4, tile=300, safe=True, t0=0.0, t1=None):
    dur = core.duration(video)
    t1 = dur if t1 is None else t1
    last = max(0.0, t1 - 0.3)
    step = (t1 - t0) / max(1, n - 1)
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            t = min(t0 + i * step, last)
            p = os.path.join(tmp, f"{i:02d}.jpg")
            if core.grab_frame(video, t, p):
                frames.append((f"{t:.1f}s", Image.open(p).convert("RGB")))
    if not frames:
        raise SystemExit("кадров не снялось")
    ratio = frames[0][1].height / frames[0][1].width
    th = int(tile * ratio)
    rows = (len(frames) + cols - 1) // cols
    gap = 8
    img = Image.new("RGB", (cols * tile + (cols + 1) * gap, rows * th + (rows + 1) * gap), (24, 24, 24))
    for i, (cap, im) in enumerate(frames):
        t = im.resize((tile, th), Image.LANCZOS)
        if safe:
            draw_safe(t, tile / config.FRAME_W)
        _label(t, cap, max(14, tile // 14))
        img.paste(t, (gap + (i % cols) * (tile + gap), gap + (i // cols) * (th + gap)))
    img.save(out, quality=92)
    return out


def run(project, **kw):
    out = os.path.join(project.out, "look.jpg")
    sheet(project.final, out, **kw)
    core.say(f"контактный лист → {project.relpath(out)}")
    return out
