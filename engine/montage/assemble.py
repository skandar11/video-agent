"""Сборка: монтажный лист → mp4 1080×1920 30 к/с, bt709, звук мастера.

Граф одного куска (порядок жёсткий — код-гейт «тонмап-первым»):
    трим исходника → тонмап HDR→SDR (если HLG/PQ) → скорость → 30 к/с → вписать в вертикаль
    (наезд и якорь) → грейд
дальше куски склеиваются (рез или xfade), сверху карточки, субтитры последними, фейд в конце.
Тонмапить после композа нельзя — тёмная подложка надписей уходит в серый.

Вписать в вертикаль (`fit` куска, по умолчанию auto):
    crop   — заполнить кадр и обрезать (с наездом `zoom` и якорем `anchor`)
    blur   — кадр целиком, поля — его же размытая копия (запись экрана, горизонталь)
    solid  — кадр целиком на чёрном поле
    auto   — crop, если обрезка сохраняет ≥ 66 % ширины, иначе blur (порог из прогонов)
Масштаб — lanczos: ужатие 2160→1080 бикубиком мылит, а «спасать» нерезкой маской — каёмки.
"""
import os

from . import config, core, edit as E

ANCHORS = {"c": (0.5, 0.5), "t": (0.5, 0.0), "b": (0.5, 1.0), "l": (0.0, 0.5), "r": (1.0, 0.5),
           "tl": (0.0, 0.0), "tr": (1.0, 0.0), "bl": (0.0, 1.0), "br": (1.0, 1.0)}


def _anchor(a):
    if isinstance(a, (list, tuple)):
        return float(a[0]), float(a[1])
    return ANCHORS.get(a or "c", (0.5, 0.5))


def fit_mode(src, mode):
    if mode and mode != "auto":
        return mode
    keep = (config.FRAME_W / config.FRAME_H) / (src["w"] / src["h"]) if src.get("h") else 1.0
    return "crop" if keep >= 0.66 else "blur"


def fit_chain(src, clip, W, H, i=0):
    """Возвращает (цепочка, нужен_ли_split). Для blur цепочка — подграф с метками."""
    mode = fit_mode(src, clip.get("fit"))
    z = float(clip.get("zoom", 1.0))
    ax, ay = _anchor(clip.get("anchor"))
    cover = f"scale={round(W * z / 2) * 2}:{round(H * z / 2) * 2}:force_original_aspect_ratio=increase:flags=lanczos"
    crop = f"crop={W}:{H}:(iw-{W})*{ax}:(ih-{H})*{ay}"
    contain = f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos"
    if mode == "crop":
        return cover + "," + crop, mode
    if mode == "solid":
        bg = "0x%02x%02x%02x" % config.PAD_COLOR
        return contain + f",pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:{bg}", mode
    if mode == "blur":
        return (f"split=2[bg{i}][fg{i}];[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},gblur=sigma=28,eq=brightness=-0.12[bb{i}];[fg{i}]{contain}[ff{i}];"
                f"[bb{i}][ff{i}]overlay=(W-w)/2:(H-h)/2"), mode
    raise ValueError(f"неизвестный fit: {mode}")


def _source_chain(src, clip, ed):
    """Начало графа куска: время с нуля → тонмап HDR (первым) → скорость → к/с."""
    parts = ["setpts=PTS-STARTPTS"]
    hdr = clip.get("hdr", src.get("hdr"))
    if hdr:
        npl = clip.get("npl", src.get("npl", config.NPL[hdr]))
        parts.append(config.tonemap(npl, clip.get("desat", src.get("desat", config.DESAT[hdr]))))
    sp = float(clip.get("speed", 1.0))
    if abs(sp - 1.0) > 1e-6:
        parts.append(f"setpts=PTS/{sp:.6f}")
    parts.append(f"fps={ed['format']['fps']}")
    return ",".join(parts)


def _tail(clip, ed):
    look = clip.get("look", ed.get("look", "natural"))
    grade = config.LOOK.get(look, look) if look else None    # имя профиля или своя цепочка
    return [g for g in (grade,) if g] + ["format=yuv420p", "setsar=1", f"trim=duration={E.clip_dur(clip):.4f}",
                                         f"settb=1/{ed['format']['fps']}"]


def clip_chain(i, src, clip, ed, inp):
    W, H = ed["format"]["w"], ed["format"]["h"]
    pre = _source_chain(src, clip, ed)
    fit, mode = fit_chain(src, clip, W, H, i)
    tail = ",".join(_tail(clip, ed))
    if mode == "blur":
        return f"[{inp}:v]{pre},{fit}[fit{i}];[fit{i}]{tail}[v{i}]"
    return f"[{inp}:v]{pre},{fit},{tail}[v{i}]"


# ─── сплит: панели разных источников одна над другой ─────────────────────────
# Кусок с "panes": [{"src": "self"|id, "in": сек (для чужого источника), "h": доля высоты,
# "zoom", "anchor"}…], "gap": px, "gap_color": "#rrggbb". Звук и время — от самого куска
# (src/in/out), каждая панель идёт ту же длину с той же скоростью. Раскладка из прогона:
# слайд сверху, лицо снизу (слово 19.10 «раскладку делай»).
def pane_heights(panes, H, gap):
    n = len(panes)
    free = H - gap * (n - 1)
    fr = [float(p.get("h", 1.0 / n)) for p in panes]
    tot = sum(fr)
    hs = [int(round(free * f / tot / 2) * 2) for f in fr]
    hs[-1] = free - sum(hs[:-1])
    return hs


def pane_source(project, clip, pane):
    if pane.get("src", "self") == "self":
        return project.source(clip["src"]), float(clip["in"])
    return project.source(pane["src"]), float(pane["in"])


def split_chain(i, project, clip, ed, inps):
    W, H, fps = ed["format"]["w"], ed["format"]["h"], ed["format"]["fps"]
    panes, gap = clip["panes"], int(clip.get("gap", 6))
    hs = pane_heights(panes, H, gap)
    d = E.clip_dur(clip)
    g, labels = [], []
    for k, (pane, ph, inp) in enumerate(zip(panes, hs, inps)):
        src, _ = pane_source(project, clip, pane)
        sub = {**clip, **{x: pane[x] for x in ("zoom", "anchor", "npl", "desat", "look") if x in pane},
               "fit": "crop"}
        sub.pop("panes", None)
        fit, _ = fit_chain(src, sub, W, ph, f"{i}_{k}")
        g.append(f"[{inp}:v]{_source_chain(src, sub, ed)},{fit},{','.join(_tail(sub, ed))}[p{i}_{k}]")
        labels.append(f"[p{i}_{k}]")
        if k < len(panes) - 1 and gap > 0:
            col = clip.get("gap_color", "#ffffff").lstrip("#")
            g.append(f"color=c=0x{col}:s={W}x{gap}:r={fps}:d={d:.4f},format=yuv420p,settb=1/{fps}[g{i}_{k}]")
            labels.append(f"[g{i}_{k}]")
    g.append(f"{''.join(labels)}vstack=inputs={len(labels)},setsar=1,settb=1/{fps}[v{i}]")
    return ";".join(g)


def input_plan(project):
    """Входы ffmpeg: по входу на кусок, на каждую панель сплита, на карточку, звук последним."""
    ed = project.edit
    args, clip_in, pane_in = [], {}, {}

    n = 0
    for i, c in enumerate(ed["clips"]):
        span = float(c["out"]) - float(c["in"])
        if c.get("panes"):
            pane_in[i] = []
            for pane in c["panes"]:
                src, start = pane_source(project, c, pane)
                args.extend(["-ss", f"{start:.3f}", "-to", f"{start + span:.3f}", "-i", src["abspath"]])
                pane_in[i].append(n); n += 1
        else:
            src = project.source(c["src"])
            # -ss/-to на входе: точный поиск при перекодировании; лишнего не декодируем
            args.extend(["-ss", f"{float(c['in']):.3f}", "-to", f"{float(c['out']):.3f}", "-i", src["abspath"]])
            clip_in[i] = n; n += 1
    ov_in = []
    for ov in ed.get("overlays", []):
        args.extend(["-loop", "1", "-t", f"{float(ov['t1']) - float(ov['t0']):.3f}", "-i", project.abspath(ov["png"])])
        ov_in.append(n); n += 1
    return args, clip_in, pane_in, ov_in, n


def graph(project, subs_path, clip_in, pane_in, ov_in):
    ed = project.edit
    starts, total = E.timeline(ed)
    g = []
    for i, c in enumerate(ed["clips"]):
        if c.get("panes"):
            g.append(split_chain(i, project, c, ed, pane_in[i]))
        else:
            g.append(clip_chain(i, project.source(c["src"]), c, ed, clip_in[i]))
    cur = "[v0]"
    for i in range(1, len(ed["clips"])):
        tr = E.transition_of(ed, i)
        nxt = f"[j{i}]"
        if tr["dur"] > 0:
            g.append(f"{cur}[v{i}]xfade=transition={tr['type']}:duration={tr['dur']:.4f}:offset={starts[i]:.4f}{nxt}")
        else:
            g.append(f"{cur}[v{i}]concat=n=2:v=1:a=0,settb=1/{ed['format']['fps']}{nxt}")
        cur = nxt
    # карточки: PNG с альфой, вход/выход прозрачностью, окно по выходной ленте
    for k, (ov, idx) in enumerate(zip(ed.get("overlays", []), ov_in)):
        t0, t1 = float(ov["t0"]), float(ov["t1"])
        fd = float(ov.get("fade", 0.25))
        g.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d={fd}:alpha=1,"
                 f"fade=t=out:st={max(0.0, t1 - t0 - fd):.3f}:d={fd}:alpha=1,setpts=PTS+{t0:.3f}/TB[o{k}]")
        g.append(f"{cur}[o{k}]overlay=x={ov.get('x', 0)}:y={ov.get('y', 0)}:"
                 f"enable='between(t,{t0:.3f},{t1:.3f})':eof_action=pass[ov{k}]")
        cur = f"[ov{k}]"
    if subs_path:
        g.append(f"{cur}ass='{core.esc_filter_path(subs_path)}':fontsdir='{core.esc_filter_path(config.FONTS)}'[sub]")
        cur = "[sub]"
    fo = float(ed.get("fade_out") or 0)
    if fo > 0:
        g.append(f"{cur}fade=t=out:st={max(0.0, total - fo):.3f}:d={fo:.2f}[fin]")
        cur = "[fin]"
    # метки цвета ставятся в графе: флаги -color_trc на выходе libx264 не доходят до потока
    # (поймано гейтом «цвет» 19.10 — файл уходил без меток, телефон гадал бы сам)
    g.append(f"{cur}setparams=color_trc=bt709:color_primaries=bt709:colorspace=bt709:range=tv,format=yuv420p[vout]")
    return ";".join(g), total


def build(project, audio_path, subs_path=None, out=None):
    ed = project.edit
    if not ed["clips"]:
        raise SystemExit("в монтажном листе нет кусков: `montage cuts` или руками в edit.json")
    out = out or project.final
    ins, clip_in, pane_in, ov_in, audio_idx = input_plan(project)
    ins += ["-i", audio_path]
    fg, total = graph(project, subs_path, clip_in, pane_in, ov_in)
    with open(os.path.join(project.work, "graph.txt"), "w", encoding="utf-8") as f:
        f.write(fg.replace(";", ";\n") + "\n")
    q = config.QUALITY[ed.get("quality", "high")]
    core.ffmpeg("-loglevel", "error", "-y", *ins, "-filter_complex", fg,
                "-map", "[vout]", "-map", f"{audio_idx}:a", "-t", f"{total:.3f}",
                "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", str(q["crf"]),
                "-maxrate", q["maxrate"], "-bufsize", q["bufsize"], "-pix_fmt", "yuv420p",
                "-r", str(ed["format"]["fps"]),
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(config.AUDIO_RATE), "-ac", "2",
                "-movflags", "+faststart", out)
    splits = sum(1 for c in ed["clips"] if c.get("panes"))
    core.say(f"сборка: {len(ed['clips'])} кусков ({splits} сплит), {len(ed.get('overlays', []))} карточек, "
             f"{total:.2f} с → {project.relpath(out)}")
    return out
