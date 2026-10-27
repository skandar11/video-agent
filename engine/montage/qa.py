"""Гейты готового ролика — то, что глазом проверять нельзя. Код возврата 1 при провале.

    кадр      1080×1920, 30 к/с, yuv420p
    цвет      метки bt709 (ролик с HLG/bt2020 на телефоне показывает другой цвет)
    звук      стерео, L/R RMS равны (no one-ear), −14 ±1 LUFS, пик не выше −1 dBTP (+0,3 допуск AAC)
    длина     сходится с монтажным листом ±0,15 с (рассинхрон склейки — тихий брак)
    ритм      по запросу: средний план ≤ 3 с, самый длинный ≤ 5 с, первая склейка ≤ 2 с,
              планов ≥ 8 (ремесло монтажа). Мягкие переходы детектор сцен не видит —
              тогда границы берутся из монтажного листа, а не угадываются.

После чисел — глазами: контактный лист `look`. Гейты не видят цвет, крючок и ритм внутри плана.
"""
import json
import math
import os

from . import config, core, edit as E

OK, BAD, WARN = "OK  ", "БРАК", "?   "


def check(path, expect=None, silent=False, rhythm=False, cut_points=None):
    info = core.probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    rows, fails = [], []

    def gate(ok, name, msg, warn=False):
        rows.append({"gate": name, "ok": bool(ok), "msg": msg, "warn": warn})
        if not ok and not warn:
            fails.append(name)

    if not v:
        gate(False, "кадр", "нет видеодорожки")
    else:
        size = (int(v["width"]), int(v["height"]))
        gate(size == (config.FRAME_W, config.FRAME_H), "кадр", f"{size[0]}×{size[1]}")
        fps = core._rate(v.get("avg_frame_rate", "0/1"))
        gate(abs(fps - config.FPS) < 0.05, "к/с", f"{fps} к/с")
        gate(v.get("pix_fmt") == "yuv420p", "пиксели", v.get("pix_fmt"))
        tags = (v.get("color_transfer", "?"), v.get("color_primaries", "?"), v.get("color_space", "?"))
        gate(tags[0] == "bt709" and tags[1] == "bt709", "цвет",
             f"передача {tags[0]}, основные {tags[1]}, матрица {tags[2]} — ждём bt709")

    if silent:
        gate(a is None, "немой", "звука нет" if a is None else "ролик заявлен немым, а дорожка на месте")
    elif not a:
        gate(False, "звук", "звуковой дорожки нет")
    else:
        ch = int(a.get("channels", 0))
        gate(ch == 2, "стерео", f"{ch} канал(а)")
        rms = core.lr_rms(path)
        if ch == 2 and len(rms) >= 2:
            gate(abs(rms[0] - rms[1]) <= config.LR_RMS_TOLERANCE, "L/R", f"Δ {abs(rms[0] - rms[1]):.2f} dB")
        ld = core.loudness(path)
        gate(ld["I"] is not None and abs(ld["I"] - config.LUFS_TARGET) <= config.LUFS_TOLERANCE,
             "громкость", f"{ld['I']} LUFS (цель {config.LUFS_TARGET} ±{config.LUFS_TOLERANCE})")
        if ld["TP"] is not None:
            gate(ld["TP"] <= config.TRUE_PEAK + 0.3, "пик", f"{ld['TP']} dBTP (потолок {config.TRUE_PEAK})",
                 warn=True)

    if expect is not None:
        gate(abs(dur - expect) <= 0.15, "длина", f"{dur:.2f} с, по листу {expect:.2f} с")
    else:
        rows.append({"gate": "длина", "ok": True, "msg": f"{dur:.2f} с — сверить не с чем", "warn": True})

    if rhythm:
        cuts = cut_points if cut_points is not None else core.scene_cuts(path, config.RHYTHM["scene"])
        lens = [round(b - x, 2) for x, b in zip([0.0] + cuts, cuts + [dur])]
        R = config.RHYTHM
        avg = sum(lens) / len(lens)
        gate(avg <= R["avg_max"], "ритм: средний план", f"{avg:.2f} с (≤ {R['avg_max']})")
        gate(max(lens) <= R["longest_max"], "ритм: длинный план", f"{max(lens):.2f} с (≤ {R['longest_max']})")
        gate((cuts[0] if cuts else dur) <= R["first_cut_max"], "ритм: первая склейка",
             f"{(cuts[0] if cuts else dur):.2f} с (≤ {R['first_cut_max']})")
        # норма — 8 планов на 20–30 с; для другой длины — пропорционально (≥ 8 × длина / 25, не меньше 3)
        need = max(3, math.ceil(R["min_shots"] * dur / 25))
        gate(len(lens) >= need, "ритм: планов", f"{len(lens)} (≥ {need} на {dur:.0f} с)")
    return {"file": path, "duration": dur, "gates": rows, "fails": fails}


def print_report(rep):
    for r in rep["gates"]:
        mark = OK if r["ok"] else (WARN if r["warn"] else BAD)
        core.say(f"{mark} {r['gate']}: {r['msg']}")
    if rep["fails"]:
        core.say("НЕ ПРОШЛО: " + ", ".join(rep["fails"]) + ". Владельцу не показывать.")
    else:
        core.say("Гейты пройдены. Теперь глазами: контактный лист.")


def run(project, rhythm=False):
    ed = project.edit
    starts, total = E.timeline(ed)
    rep = check(project.final, expect=total, rhythm=rhythm, cut_points=[round(s, 2) for s in starts[1:]])
    with open(os.path.join(project.out, "qa.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print_report(rep)
    return rep
