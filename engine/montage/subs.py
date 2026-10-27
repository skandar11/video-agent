"""Субтитры: слова выходной ленты → ASS. Один генератор, стили — пресеты `styles/*.json`.

Режимы:
    cards — карточки 2–4 слова вербатим (стиль `cards`: тёмная подложка, мягкий вход)
    word  — та же карточка, произносимое слово подсвечено акцентом (стиль `word`)

Карточка рвётся на конце сегмента, на знаке препинания и на паузе > 0,6 с; одиночное слово
не висит, если его можно присоединить. Время — уже по выходной ленте (`edit.words_on_output`),
поэтому каты, скорость и переходы учтены до генерации, а не подгонкой после.
"""
import json
import os

from . import config, core, edit as E

PUNCT = ".,!?…;:"


def load_style(name_or_path, override=None):
    p = name_or_path if os.path.exists(str(name_or_path)) else os.path.join(config.STYLES, f"{name_or_path}.json")
    with open(p, encoding="utf-8") as f:
        st = json.load(f)
    st.update(override or {})
    return st


def ass_color(hexstr, alpha=0):
    """#rrggbb → &HAABBGGRR (alpha 0 — непрозрачно)."""
    h = hexstr.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(t):
    t = max(0.0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def join_particles(words):
    """whisper отрывает частицы через дефис («какая» + «-то») — пришиваем к слову."""
    out = []
    for w in words:
        if out and w["w"].startswith("-") and len(w["w"]) > 1:
            out[-1] = {**out[-1], "w": out[-1]["w"] + w["w"], "e": w["e"]}
        else:
            out.append(dict(w))
    return out


def cards_from_words(words, max_words=4, gap=0.6):
    """[{w,s,e}] → карточки [[слово…]] (каждое слово — dict)."""
    words = join_particles(words)
    cards, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        ends_punct = w["w"][-1] in PUNCT
        gap_next = i + 1 < len(words) and words[i + 1]["s"] - w["e"] > gap
        # карточка не переезжает через склейку разных дублей (наезд внутри дубля — можно)
        src_change = i + 1 < len(words) and words[i + 1].get("src", "") != w.get("src", "")
        last = i + 1 == len(words)
        if len(cur) >= max_words or ends_punct or gap_next or src_change or last:
            cards.append(cur)
            cur = []
    # одиночное слово без знака — к соседу, если влезает
    merged = []
    for c in cards:
        if merged and len(c) == 1 and len(merged[-1]) < max_words and c[0]["s"] - merged[-1][-1]["e"] <= gap \
                and merged[-1][-1]["w"][-1] not in ".!?…":
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return merged


def header(st):
    back = ass_color(st.get("box", "#000000"), st.get("box_alpha", 0)) if st.get("border_style") == 3 \
        else ass_color(st.get("shadow_color", "#000000"), st.get("shadow_alpha", 0))
    outline = ass_color(st.get("outline_color", st.get("box", "#000000")),
                        st.get("box_alpha", 0) if st.get("border_style") == 3 else 0)
    bold = -1 if st.get("bold") else 0
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{st['font']},{st['size']},{ass_color(st['text'])},{ass_color(st['text'])},{outline},{back},"
        f"{bold},0,0,0,100,100,0,0,{st.get('border_style', 1)},{st.get('outline', 0)},{st.get('shadow', 0)},2,"
        f"{st.get('margin_h', 60)},{st.get('margin_h', 60)},{st.get('margin_v', 150)},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


def _text(tokens, st):
    if len(tokens) >= st.get("two_lines_from", 99):
        mid = (len(tokens) + 1) // 2
        return " ".join(tokens[:mid]) + r"\N" + " ".join(tokens[mid:])
    return " ".join(tokens)


HOLD = 1.0      # карточка держится до следующей, если пауза короче (иначе мигает пустой кадр)
LINGER = 0.9    # последнее слово висит не дольше — whisper тянет его конец в тишину


def events(cards, st, accent_words=()):
    acc = "{\\c" + ass_color(st["accent"]) + "&}"
    white = "{\\c" + ass_color(st["text"]) + "&}"
    ev, prev = [], 0.0
    for ci, card in enumerate(cards):
        nxt = cards[ci + 1][0]["s"] if ci + 1 < len(cards) else None
        lw = card[-1]
        tail = min(lw["e"], lw["s"] + LINGER)
        card_end = nxt if (nxt is not None and nxt - tail < HOLD) else tail
        if st["mode"] == "cards":
            toks = [(acc + w["w"] + white) if w["w"].strip(PUNCT).lower() in accent_words else w["w"] for w in card]
            s = max(card[0]["s"], prev)
            ev.append((s, max(card_end, s + 0.3), st.get("pop", "") + white + _text(toks, st)))
            prev = max(card_end, s + 0.3)
        else:  # word — события впритык, без зазоров: зазор в 10 мс попадает на кадр и сабы мигают
            for wi, w in enumerate(card):
                s = max(w["s"], prev)
                e = card[wi + 1]["s"] if wi + 1 < len(card) else max(card_end, s + 0.2)
                toks = [(("{\\c" + ass_color(st["accent"]) + "&" + st.get("word_pop", "") + "}" + x["w"] + "{\\r}")
                         if xi == wi else x["w"]) for xi, x in enumerate(card)]
                lead = st.get("card_fade", "") if wi == 0 else ""
                ev.append((s, e, lead + _text(toks, st)))
                prev = e
    return ev


def write(words, out, style="cards", override=None, accent_words=()):
    st = load_style(style, override)
    cards = cards_from_words(words, st.get("max_words", 4))
    ev = events(cards, st, {a.lower() for a in accent_words})
    with open(out, "w", encoding="utf-8") as f:
        f.write(header(st))
        for s, e, text in ev:
            s, e = round(s, 2), round(e, 2)    # сотые ASS: конец и начало соседей совпадают точно
            f.write(f"Dialogue: 0,{ts(s)},{ts(e)},Cap,,0,0,0,,{text}\n")
    return out, len(cards)


def run(project):
    from .transcribe import load_words
    ed = project.edit
    sub = ed.get("subs") or {}
    out = os.path.join(project.work, "subs.ass")
    if not sub.get("enabled", True):
        return None
    if sub.get("ass"):                       # готовые сабы руками — берём как есть
        return project.abspath(sub["ass"])
    words = E.words_on_output(ed, load_words(project))
    if not words:
        core.say("субтитры: слов нет — сабов не будет")
        return None
    # правки распознавания: {"неверно": "верно"} — whisper путает имена и термины
    fixes = sub.get("fix", {})
    if fixes:
        for w in words:
            w["w"] = fixes.get(w["w"], w["w"])
    path, n = write(words, out, sub.get("style", "cards"), sub.get("override"), sub.get("accent_words", []))
    core.say(f"субтитры: {n} карточек, стиль «{sub.get('style', 'cards')}» → {project.relpath(path)}")
    return path
