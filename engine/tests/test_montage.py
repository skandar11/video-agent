"""Тесты пакета на синтетике: ролики и звук делает ffmpeg из lavfi, модели не нужны.

    .venv/bin/python -m pytest -q        (из engine/)
"""
import json
import os
import subprocess

import pytest

from montage import assemble, audio, config, core, cuts, edit as E, qa, subs


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    land = d / "land.mp4"       # горизонталь SDR со звуком: тон с паузой посередине
    ff("-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=6",
       "-f", "lavfi", "-i", "sine=f=330:sample_rate=48000:d=6",
       "-af", "volume='if(between(t,2.5,3.5),0,1)':eval=frame,volume=-12dB",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "1", "-shortest", str(land))
    hlg = d / "hlg.mp4"         # вертикаль с метками HLG/bt2020, без звука
    tag = "setparams=color_trc=arib-std-b67:color_primaries=bt2020:colorspace=bt2020nc"
    ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=60:d=4", "-vf", tag, "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(hlg))
    mono = d / "mono.mp4"       # неправильный готовый файл: 720p, моно, HLG-метки
    ff("-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=2", "-f", "lavfi", "-i", "sine=f=500:d=2",
       "-vf", tag, "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-ac", "1", "-shortest", str(mono))
    return {"land": str(land), "hlg": str(hlg), "mono": str(mono), "dir": d}


def make_project(tmp_path, media, clips, **edit):
    p = E.Project(tmp_path / "proj")
    p.init("тест")
    p.add_source(media["land"], "land")
    p.add_source(media["hlg"], "hlg")
    p.edit["clips"] = clips
    p.edit.update(edit)
    p.save()
    p.load()
    return p


# ─── лента ───────────────────────────────────────────────────────────────────
def test_timeline_cuts_and_xfade():
    ed = {"clips": [{"src": "a", "in": 0, "out": 2}, {"src": "a", "in": 3, "out": 5, "speed": 2.0},
                    {"src": "b", "in": 0, "out": 1}], "transition": {"type": "cut"}}
    assert E.timeline(ed) == ([0.0, 2.0, 3.0], 4.0)
    ed["transition"] = {"type": "fade", "dur": 0.25}
    starts, total = E.timeline(ed)
    assert starts == [0.0, 1.75, 2.5] and total == 3.5


def test_words_on_output_remap():
    ed = {"clips": [{"src": "a", "in": 1.0, "out": 3.0}, {"src": "a", "in": 5.0, "out": 7.0, "speed": 2.0}],
          "transition": {"type": "cut"}}
    words = {"a": [{"w": "раз", "s": 1.2, "e": 1.5}, {"w": "вырезано", "s": 4.0, "e": 4.5},
                   {"w": "два", "s": 5.5, "e": 6.0}]}
    out = E.words_on_output(ed, words)
    assert [w["w"] for w in out] == ["раз", "два"]
    assert out[1]["s"] == pytest.approx(2.0 + 0.25) and out[1]["e"] == pytest.approx(2.5)


def test_speech_islands_split_on_silent_pause():
    words = [{"w": "а", "s": 0.1, "e": 0.5}, {"w": "б", "s": 0.6, "e": 1.0},
             {"w": "в", "s": 2.0, "e": 2.6}, {"w": "г", "s": 2.7, "e": 3.4}]
    isl = cuts.speech_islands(words, max_pause=0.45, sil=[(1.0, 2.0)])
    assert len(isl) == 2 and isl[0]["out"] == pytest.approx(1.15) and isl[1]["in"] == pytest.approx(1.92)
    # пауза есть по словам, но звук не тихий — не режем
    assert len(cuts.speech_islands(words, max_pause=0.45, sil=[])) == 1


# ─── субтитры ────────────────────────────────────────────────────────────────
def test_subs_cards_and_word_mode(tmp_path):
    words = [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3} for i, w in enumerate("мы это отпустили, идём дальше.".split())]
    cards = subs.cards_from_words(words, 4)
    assert [len(c) for c in cards] == [3, 2]
    out, n = subs.write(words, str(tmp_path / "a.ass"), "word")
    txt = open(out, encoding="utf-8").read()
    assert txt.count("Dialogue:") == 5 and "Inter ExtraBold" in txt and "&H006ED3FF" in txt
    out, n = subs.write(words, str(tmp_path / "b.ass"), "cards")
    assert open(out, encoding="utf-8").read().count("Dialogue:") == 2


# ─── звук ────────────────────────────────────────────────────────────────────
def test_master_hits_target(tmp_path, media):
    src = tmp_path / "quiet.wav"
    ff("-f", "lavfi", "-i", "sine=f=220:d=5", "-af", "volume=-30dB", "-ac", "1", str(src))
    out, gain = audio.master(str(src), str(tmp_path / "m.wav"))
    fails, m = audio.gates(out)
    assert not fails, fails
    assert abs(m["I"] - config.LUFS_TARGET) <= 0.5


def test_timeline_audio_length_matches_edit(tmp_path, media):
    p = make_project(tmp_path, media, [{"src": "land", "in": 0, "out": 2}, {"src": "hlg", "in": 0, "out": 1},
                                       {"src": "land", "in": 4, "out": 6, "speed": 1.25}],
                     transition={"type": "fade", "dur": 0.2})
    out = audio.timeline_audio(p, os.path.join(p.work, "v.wav"))
    assert core.duration(out) == pytest.approx(E.total_duration(p.edit), abs=0.03)


def test_license_gate(tmp_path, monkeypatch):
    stray = tmp_path / "track.mp3"
    stray.write_bytes(b"0")
    reg = tmp_path / "licenses.md"
    reg.write_text("# Лицензии\n\n## Звуки\n\n- click.ogg — CC0, kenney.nl\n", encoding="utf-8")
    monkeypatch.setattr(config, "LICENSES", str(reg))
    with pytest.raises(SystemExit):
        audio.check_license(str(stray))
    assert "CC0" in audio.check_license(str(tmp_path / "click.ogg"))


# ─── сборка и гейты ──────────────────────────────────────────────────────────
def test_build_end_to_end(tmp_path, media):
    p = make_project(tmp_path, media,
                     [{"src": "land", "in": 0.0, "out": 2.4, "fit": "auto"},
                      {"src": "hlg", "in": 0.5, "out": 2.0, "zoom": 1.07},
                      {"src": "land", "in": 3.6, "out": 5.5, "fit": "crop", "speed": 1.1,
                       "transition": {"type": "fade", "dur": 0.3}}],
                     look="alive", audio={"profile": "clean_vo", "polish": True})
    json.dump({"words": [{"w": "проверка", "s": 0.2, "e": 0.8}, {"w": "сборки", "s": 0.9, "e": 1.6}]},
              open(os.path.join(p.work, "words-land.json"), "w"))
    master = audio.run(p)
    sp = subs.run(p)
    out = assemble.build(p, master, sp)
    rep = qa.run(p)
    assert not rep["fails"], rep
    info = core.media_info(out)
    assert (info["w"], info["h"], info["transfer"]) == (1080, 1920, "bt709")
    assert os.path.getsize(os.path.join(p.work, "commands.sh")) > 0   # команды записаны


def test_qa_catches_bad_file(media):
    rep = qa.check(media["mono"], expect=2.0)
    assert {"кадр", "цвет", "стерео"} <= set(rep["fails"])


def test_ingest_detects_hdr(media, tmp_path):
    info = core.media_info(media["hlg"])
    assert info["hdr"] == "hlg" and (info["w"], info["h"]) == (1080, 1920)
    assert assemble.fit_mode(core.media_info(media["land"]), "auto") == "blur"


def test_particles_join():
    w = subs.join_particles([{"w": "какая", "s": 0, "e": 0.3}, {"w": "-то", "s": 0.3, "e": 0.5}, {"w": "-", "s": 0.6, "e": 0.7}])
    assert [x["w"] for x in w] == ["какая-то", "-"] and w[0]["e"] == 0.5


def test_word_events_are_contiguous_and_cards_break_on_source(tmp_path):
    words = [{"w": "тело", "s": 0.0, "e": 0.3, "src": "a"}, {"w": "никогда", "s": 0.31, "e": 0.7, "src": "a"},
             {"w": "игра", "s": 0.8, "e": 1.1, "src": "b"}, {"w": "маяк", "s": 1.2, "e": 4.0, "src": "b"}]
    assert [len(c) for c in subs.cards_from_words(words)] == [2, 2]
    out, _ = subs.write(words, str(tmp_path / "w.ass"), "word")
    ev = [l.split(",")[1:3] for l in open(out, encoding="utf-8") if l.startswith("Dialogue")]
    assert all(ev[i][1] == ev[i + 1][0] for i in range(len(ev) - 1))      # впритык, без зазоров
    assert ev[-1][1] == "0:00:02.10"                                      # хвост «маяк» ≤ 0,9 с


def test_split_layout(tmp_path, media):
    p = make_project(tmp_path, media,
                     [{"src": "land", "in": 0.0, "out": 2.0},
                      {"src": "land", "in": 2.0, "out": 4.0, "gap": 6,
                       "panes": [{"src": "hlg", "in": 0.5, "h": 0.4},
                                 {"src": "self", "h": 0.6, "zoom": 1.1, "anchor": "t"}]}])
    assert assemble.pane_heights(p.edit["clips"][1]["panes"], 1920, 6) == [766, 1148]
    master = audio.run(p)
    out = assemble.build(p, master)
    rep = qa.check(out, expect=E.total_duration(p.edit))
    assert not rep["fails"], rep
    # шов сплита — белая полоса на высоте верхней панели
    f = os.path.join(p.work, "seam.png")
    core.grab_frame(out, 3.0, f)
    from PIL import Image
    px = Image.open(f).convert("RGB").getpixel((540, 768))
    assert min(px) > 230, px
