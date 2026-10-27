"""montage — команда монтажа. Проект = папка бандла с edit.json.

    montage init    <проект> [--title название]
    montage ingest  <проект> <файл…> [--id имя]         источники в лист (размер, к/с, HDR, звук)
    montage transcribe <проект> [--src id…]             слова с таймингами (mlx-whisper)
    montage cuts    <проект> --src id [--pause 0.45]    куски без пауз по словам × тишине
    montage audio   <проект>                            голос → музыка/SFX → мастер −14 LUFS + гейты
    montage subs    <проект>                            субтитры по стилю листа
    montage cards   <проект>                            карточки: крючок, чип, финал (PNG поверх кадра)
    montage build   <проект>                            сборка mp4 (звук и сабы — если нет, делает)
    montage qa      <проект или mp4> [--rhythm]         гейты готового файла
    montage look    <проект или mp4>                    контактный лист
    montage run     <проект> [--rhythm]                 audio → subs → build → qa → look
    montage master  <вход> <выход.wav>                  мастер любого звука: −14 LUFS стерео + гейты
"""
import argparse
import json
import os
import sys

from . import audio, assemble, cards, core, cuts, edit as E, look, qa, subs, transcribe


def _project(path):
    p = E.Project(path)
    if not os.path.exists(p.path):
        sys.exit(f"нет {p.path}: сначала `montage init {path}`")
    p.load()
    return p


def cmd_build(p, force_audio=False):
    master = os.path.join(p.work, "master.wav")
    if force_audio or not os.path.exists(master) or os.path.getmtime(master) < os.path.getmtime(p.path):
        audio.run(p)
    if p.edit.get("cards"):
        cards.run(p)
    sp = subs.run(p)
    return assemble.build(p, master, sp)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="montage", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("project"); s.add_argument("--title")
    s = sub.add_parser("ingest"); s.add_argument("project"); s.add_argument("files", nargs="+")
    s.add_argument("--id", action="append", help="имя источника (по порядку файлов)")
    s = sub.add_parser("transcribe"); s.add_argument("project"); s.add_argument("--src", nargs="*")
    s.add_argument("--model", default=transcribe.MODEL); s.add_argument("--lang", default="ru")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("cuts"); s.add_argument("project"); s.add_argument("--src", required=True)
    s.add_argument("--pause", type=float, default=0.45); s.add_argument("--keep", help='JSON [[a,b],…]')
    s.add_argument("--no-confirm", action="store_true", help="не сверять паузы с silencedetect")
    s.add_argument("--speed", type=float, default=1.0); s.add_argument("--append", action="store_true")
    s.add_argument("--punch", type=float, help="наезды для ритма: делить куски по словам каждые N с")
    for name in ("audio", "subs", "cards"):
        s = sub.add_parser(name); s.add_argument("project")
    s = sub.add_parser("build"); s.add_argument("project"); s.add_argument("--audio", action="store_true",
                                                                           help="пересобрать звук")
    s = sub.add_parser("qa"); s.add_argument("target"); s.add_argument("--rhythm", action="store_true")
    s.add_argument("--expect", type=float)
    s = sub.add_parser("look"); s.add_argument("target"); s.add_argument("-n", type=int, default=12)
    s.add_argument("--no-safe", action="store_true")
    s = sub.add_parser("run"); s.add_argument("project"); s.add_argument("--rhythm", action="store_true")
    s = sub.add_parser("master"); s.add_argument("src"); s.add_argument("out")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "init":
            p = E.Project(a.project); p.init(a.title); core.say(f"проект {p.root} · лист {p.path}")
        elif a.cmd == "ingest":
            p = _project(a.project)
            for k, f in enumerate(a.files):
                sid = p.add_source(os.path.abspath(f), (a.id or [None] * len(a.files))[k] if a.id and k < len(a.id) else None)
                s_ = p.edit["sources"][sid]
                core.say(f"{sid}: {s_.get('w')}×{s_.get('h')} {s_.get('fps')} к/с, {s_['duration']:.1f} с, "
                         f"{'HDR ' + s_['hdr'] if s_.get('hdr') else 'SDR'}, звук {'есть' if s_['audio'] else 'нет'}")
            p.save()
        elif a.cmd == "transcribe":
            transcribe.run(_project(a.project), a.src, a.model, a.lang, a.force)
        elif a.cmd == "cuts":
            cuts.run(_project(a.project), a.src, a.pause, json.loads(a.keep) if a.keep else None,
                     not a.no_confirm, a.speed, a.append, a.punch)
        elif a.cmd == "audio":
            audio.run(_project(a.project))
        elif a.cmd == "subs":
            subs.run(_project(a.project))
        elif a.cmd == "cards":
            cards.run(_project(a.project))
        elif a.cmd == "build":
            cmd_build(_project(a.project), a.audio)
        elif a.cmd == "qa":
            if os.path.isdir(a.target):
                rep = qa.run(_project(a.target), a.rhythm)
            else:
                rep = qa.check(a.target, a.expect, rhythm=a.rhythm); qa.print_report(rep)
            sys.exit(1 if rep["fails"] else 0)
        elif a.cmd == "look":
            if os.path.isdir(a.target):
                look.run(_project(a.target), n=a.n, safe=not a.no_safe)
            else:
                out = os.path.splitext(a.target)[0] + "-look.jpg"
                look.sheet(a.target, out, n=a.n, safe=not a.no_safe); core.say(out)
        elif a.cmd == "master":
            out, gain = audio.master(a.src, a.out)
            fails, m = audio.gates(out)
            core.say(f"мастер: {m['I']} LUFS, пик {m['TP']} dBTP, усиление {gain:+} dB → {a.out}")
            sys.exit(("ГЕЙТ ЗВУКА: " + "; ".join(fails)) if fails else 0)
        elif a.cmd == "run":
            p = _project(a.project)
            cmd_build(p, force_audio=True)
            rep = qa.run(p, a.rhythm)
            look.run(p)
            sys.exit(1 if rep["fails"] else 0)
    except core.FFError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
