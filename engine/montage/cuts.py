"""Каты по речи: из слов источника — куски без пауз.

Правило ремесла (video-station §Трек B): резать только там, где тихо И по словам, И по звуку —
на улице silencedetect тонет в эмбиенте, а слова whisper иногда «склеивают» паузу. Поэтому
пауза между словами режется, только если silencedetect тоже видит там тишину (флаг
`confirm`, по умолчанию включён). Края — с запасом: начало слова −0,08 с, хвост +0,15 с,
иначе съедаются согласные.
Смысловой отбор (какие фразы оставить) — не здесь: его делает агент по сценарию, передавая
`keep` — список [нач, кон] в секундах исходника.
"""
import re

from . import core

PRE, POST = 0.08, 0.15


def silences(path, noise_db=-32, min_dur=0.25):
    err = core.ffmpeg("-i", path, "-vn", "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
                      "-f", "null", "-", capture=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends + [1e9] * (len(starts) - len(ends))))


def _silent(gap, sil, share=0.6):
    a, b = gap
    covered = sum(max(0.0, min(b, e) - max(a, s)) for s, e in sil)
    return covered >= share * (b - a)


def speech_islands(words, max_pause=0.45, min_len=0.6, sil=None, src_dur=None):
    """Слова → куски [{in, out}]: новый кусок, где пауза между словами > max_pause
    (и, если дан sil, там действительно тихо)."""
    if not words:
        return []
    isl, cur = [], [words[0]["s"], words[0]["e"]]
    for w in words[1:]:
        gap = (cur[1], w["s"])
        if gap[1] - gap[0] > max_pause and (sil is None or _silent(gap, sil)):
            isl.append(cur)
            cur = [w["s"], w["e"]]
        else:
            cur[1] = max(cur[1], w["e"])
    isl.append(cur)
    out = []
    for a, b in isl:
        a, b = max(0.0, a - PRE), b + POST
        if src_dur:
            b = min(b, src_dur)
        if out and a <= out[-1]["out"]:          # запасы соседей сошлись — один кусок
            out[-1]["out"] = round(b, 3)
            continue
        out.append({"in": round(a, 3), "out": round(b, 3)})
    return [c for c in out if c["out"] - c["in"] >= min_len]


def within(islands, keep):
    """Обрезать куски по смысловому отбору keep=[[a,b],…]."""
    out = []
    for a, b in keep:
        for c in islands:
            s, e = max(a, c["in"]), min(b, c["out"])
            if e - s > 0.2:
                out.append({"in": round(s, 3), "out": round(e, 3)})
    return out


def punch_split(clips, words, every=2.5, zoom=1.07, min_len=1.2, first=1.4):
    """Наезды для ритма без потери речи: кусок длиннее every делится на границах слов
    примерно каждые every секунд, масштаб чередуется 1.0 / zoom (PUNCH 1.07).
    Рез между словами одного дубля — скачок масштаба, а не склейка по смыслу. Первая склейка —
    раньше (first): крючок держит смена плана до 2 с (гейт ритма)."""
    out = []
    for ci, c in enumerate(clips):
        a, b = c["in"], c["out"]
        bounds = [w["e"] for w in words if a < w["e"] < b]
        cuts_at, last = [], a
        for t in bounds:
            need = first if (ci == 0 and not cuts_at) else every
            if t - last >= need and b - t >= min_len:
                cuts_at.append(t)
                last = t
        edges = [a] + cuts_at + [b]
        for x, y in zip(edges[:-1], edges[1:]):
            out.append({**c, "in": round(x, 3), "out": round(y, 3)})
    for i, c in enumerate(out):
        c["zoom"] = zoom if i % 2 else c.get("zoom", 1.0)
    return out


def run(project, sid, max_pause=0.45, keep=None, confirm=True, speed=1.0, append=False, punch=None, **clip_opts):
    from .transcribe import load_words
    words = load_words(project).get(sid)
    if not words:
        raise SystemExit(f"нет расшифровки {sid}: сначала `montage transcribe`")
    src = project.source(sid)
    sil = silences(src["abspath"]) if confirm else None
    isl = speech_islands(words, max_pause, sil=sil, src_dur=src["duration"])
    if keep:
        isl = within(isl, keep)
    clips = [{"src": sid, "in": c["in"], "out": c["out"], "speed": speed, **clip_opts} for c in isl]
    if punch:
        clips = punch_split(clips, words, every=punch)
    ed = project.edit
    ed["clips"] = (ed["clips"] if append else []) + clips
    project.save()
    kept = sum(c["out"] - c["in"] for c in isl)
    core.say(f"каты {sid}: {len(clips)} кусков, {kept:.1f} с из {src['duration']:.1f} с исходника")
    return clips
