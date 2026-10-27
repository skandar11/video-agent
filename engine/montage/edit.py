"""Монтажный лист `edit.json` и проект ролика.

Проект — папка бандла:
    edit.json      монтажный лист: источники, куски, переходы, карточки, субтитры, звук
    work/          промежуточное (слова, звук, сабы, карточки, commands.sh — журнал команд)
    out/           готовое: reel.mp4, look.jpg (контактный лист), qa.json

Все станции читают и пишут лист; сборка по нему повторяема. Время в кусках — по ИСХОДНИКУ
(in/out в секундах файла), всё остальное (карточки, SFX) — по ВЫХОДНОЙ ленте.
"""
import copy
import json
import os

from . import config, core

EDIT = "edit.json"

DEFAULT = {
    "version": 1,
    "title": None,          # название ролика для людей (по умолчанию — имя папки бандла)
    "format": {"w": config.FRAME_W, "h": config.FRAME_H, "fps": config.FPS},
    "sources": {},
    "clips": [],
    # переход по умолчанию между кусками: {"type": "cut"} или {"type": "fade", "dur": 0.3}
    # (любой тип xfade ffmpeg: fade, fadewhite, dissolve, smoothleft, zoomin…); кусок может
    # перебить своим "transition" — переход ПЕРЕД ним.
    "transition": {"type": "cut"},
    "look": "natural",
    "overlays": [],
    "subs": {"style": "cards", "enabled": True},
    "audio": {"profile": "clean_vo", "polish": False, "music": None, "sfx": []},
    "fade_out": 0.4,
    "quality": "high",
}


class Project:
    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.path = os.path.join(self.root, EDIT)
        self.work = os.path.join(self.root, "work")
        self.out = os.path.join(self.root, "out")
        self.edit = None

    # ─── файлы ──────────────────────────────────────────────────────────────
    def init(self, title=None):
        os.makedirs(self.work, exist_ok=True)
        os.makedirs(self.out, exist_ok=True)
        if not os.path.exists(self.path):
            self.edit = copy.deepcopy(DEFAULT)
            self.edit["title"] = title or os.path.basename(self.root)
            self.save()
        return self.load()

    def load(self):
        with open(self.path, encoding="utf-8") as f:
            ed = json.load(f)
        merged = copy.deepcopy(DEFAULT)
        for k, v in ed.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        self.edit = merged
        os.makedirs(self.work, exist_ok=True)
        os.makedirs(self.out, exist_ok=True)
        core.set_log(os.path.join(self.work, "commands.sh"))
        return self.edit

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.edit, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def abspath(self, p):
        if p is None:
            return None
        p = os.path.expanduser(p)
        return p if os.path.isabs(p) else os.path.join(self.root, p)

    def relpath(self, p):
        p = os.path.abspath(os.path.expanduser(p))
        return os.path.relpath(p, self.root) if p.startswith(self.root + os.sep) else p

    @property
    def title(self):
        return self.edit.get("title") or self.edit.get("slug") or os.path.basename(self.root)

    # Имена готового — фиксированные (слово 19.10 «не надо slug что получше придумай»): дата и тема
    # уже в имени папки бандла, у файла имя всегда одно — ни агенту, ни человеку не угадывать.
    @property
    def final(self):
        return os.path.join(self.out, "reel.mp4")

    # ─── источники ──────────────────────────────────────────────────────────
    def add_source(self, path, sid=None):
        info = core.media_info(self.abspath(path))
        sid = sid or os.path.splitext(os.path.basename(path))[0].lower().replace(" ", "-")
        self.edit["sources"][sid] = {"path": self.relpath(self.abspath(path)), **info}
        return sid

    def source(self, sid):
        s = self.edit["sources"][sid]
        return {**s, "abspath": self.abspath(s["path"])}


# ─── лента: исходник → выход ─────────────────────────────────────────────────
def clip_dur(c):
    return (float(c["out"]) - float(c["in"])) / float(c.get("speed", 1.0))


def transition_of(edit, i):
    """Переход ПЕРЕД куском i (у первого — нет)."""
    if i == 0:
        return {"type": "cut", "dur": 0.0}
    t = edit["clips"][i].get("transition") or edit.get("transition") or {"type": "cut"}
    if t.get("type", "cut") == "cut":
        return {"type": "cut", "dur": 0.0}
    return {"type": t["type"], "dur": float(t.get("dur", 0.3))}


def timeline(edit):
    """Старт каждого куска на выходной ленте и общая длина. Переход длины d перекрывает
    соседей: следующий кусок начинается на d раньше конца предыдущего."""
    starts, t = [], 0.0
    for i, c in enumerate(edit["clips"]):
        d = transition_of(edit, i)["dur"]
        if i > 0:
            prev = clip_dur(edit["clips"][i - 1])
            if d >= min(prev, clip_dur(c)):
                raise ValueError(f"переход {d} с длиннее соседнего куска (кусок {i})")
            t -= d
        starts.append(round(t, 4))
        t += clip_dur(c)
    return starts, round(t, 4)


def total_duration(edit):
    return timeline(edit)[1]


def to_output(edit, src, t):
    """Время исходника src → время выходной ленты (список: слово может попасть в
    перекрытие двух кусков одного исходника — берём первый)."""
    starts, _ = timeline(edit)
    for c, st in zip(edit["clips"], starts):
        if c["src"] == src and float(c["in"]) <= t <= float(c["out"]):
            return st + (t - float(c["in"])) / float(c.get("speed", 1.0))
    return None


def words_on_output(edit, words_by_src):
    """Слова источников → слова выходной ленты [{w, s, e}], по порядку кусков.
    Слово, начало которого вырезано, выпадает целиком; конец обрезается по куску."""
    starts, _ = timeline(edit)
    out = []
    for ci, (c, st) in enumerate(zip(edit["clips"], starts)):
        sp = float(c.get("speed", 1.0))
        a, b = float(c["in"]), float(c["out"])
        for w in words_by_src.get(c["src"], []):
            if a - 0.02 <= w["s"] < b:
                s = st + (max(w["s"], a) - a) / sp
                e = st + (min(w["e"], b) - a) / sp
                if e > s:
                    out.append({"w": w["w"], "s": round(s, 3), "e": round(e, 3), "clip": ci, "src": c["src"]})
    out.sort(key=lambda w: w["s"])
    return out
