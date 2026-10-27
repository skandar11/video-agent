"""Звук: дорожка ленты → чистка голоса → музыка и SFX → мастер −14 LUFS стерео + гейты.

Три шага, каждый — файл в work/:
    voice-raw.wav   звук кусков по монтажному листу (тот же трим, скорость и переходы, что у кадра)
    mix.wav         голос после чистки (+ полировка) + музыка с приседанием + SFX
    master.wav      усиление до цели → лимитер → loudnorm по замеру (линейный)

Один динамический проход loudnorm в цель не попадает (замер на войсовере: −15,6 LUFS и пик −0,7
при цели −14/−1); при горячих пиках линейный режим ему недоступен и он молча уходит в
динамику — поэтому сначала усиление и лимитер, потом замер.

Цепочки подобраны замером под тембр референса. Порядок жёсткий: хайпасс → шумодав → EQ → де-эссер →
компрессор → пространство → стерео → громкость.
"""
import os

from . import config, core, edit as E

PROFILES = {
    # уличная селфи-голова: RNNoise mix 0.85 (1.0 — «водянистый» голос), afftdn nr 7 (10 — звон)
    "noisy_street": ["highpass=f=100", "@rnnoise", "afftdn=nr=7:nf=-35"],
    # чистая запись (Диктофон в Lossless): только хайпасс
    "clean_vo": ["highpass=f=70"],
    # телефон/мессенджер и повреждённое
    "phone": ["highpass=f=85", "afftdn=nr=7"],
    "damaged": ["highpass=f=85", "anlmdn=s=0.0004", "afftdn=nr=8"],
    "none": [],
}
POLISH_EQ = ["equalizer=f=450:t=q:w=1.2:g=-2.5",    # де-мут
             "equalizer=f=4200:t=q:w=1.0:g=3.5",    # присутствие
             "equalizer=f=6800:t=q:w=1.4:g=-1.5",   # де-харш
             "treble=f=9000:g=4"]                   # воздух
DEESS = ("adynamicequalizer=dfrequency=7000:dqfactor=2:tfrequency=7000:tqfactor=2"
         ":threshold=0.06:ratio=4:range=12:attack=1:release=50:mode=cutabove")
SPACE = {"none": None, "room": "aecho=0.9:0.75:23|31:0.055|0.035",
         "hall": "aecho=0.85:0.75:47|71:0.11|0.075"}


def voice_chain(profile="clean_vo", polish=False, comp=2.6, space="none", rnnoise=config.RNNOISE):
    parts = []
    for p in PROFILES[profile]:
        if p == "@rnnoise":
            if rnnoise and os.path.exists(rnnoise):
                parts.append(f"arnndn=m={core.esc_filter_path(rnnoise)}:mix=0.85")
        else:
            parts.append(p)
    if polish:
        parts += POLISH_EQ + [DEESS]
        if comp:
            parts.append(f"acompressor=threshold=-20dB:ratio={comp:.2f}:attack=8:release=180"
                         f":makeup={1.0 + 0.6 * (comp - 1.0):.2f}")
        if SPACE.get(space):
            parts.append(SPACE[space])
    return ",".join(parts) or "anull"


def _atempo(speed):
    """atempo берёт 0.5…2.0 за звено — дальше каскадом."""
    out, s = [], float(speed)
    while s > 2.0:
        out.append("atempo=2.0"); s /= 2.0
    while s < 0.5:
        out.append("atempo=0.5"); s /= 0.5
    if abs(s - 1.0) > 1e-6:
        out.append(f"atempo={s:.6f}")
    return out


def timeline_audio(project, out):
    """Звук ленты по монтажному листу. Кусок без звука — тишина той же длины."""
    ed = project.edit
    ins, parts, labels = [], [], []
    for i, c in enumerate(ed["clips"]):
        src = project.source(c["src"])
        d = E.clip_dur(c)
        if src.get("audio"):
            ins += ["-ss", f"{c['in']:.3f}", "-to", f"{c['out']:.3f}", "-i", src["abspath"]]
            chain = ["asetpts=PTS-STARTPTS", "aresample=48000", "aformat=channel_layouts=mono"] \
                + _atempo(c.get("speed", 1.0)) + [f"apad,atrim=0:{d:.4f}"]
        else:
            ins += ["-f", "lavfi", "-t", f"{d:.4f}", "-i", "anullsrc=r=48000:cl=mono"]
            chain = ["anull"]
        parts.append(f"[{i}:a]{','.join(chain)}[a{i}]")
        labels.append(f"[a{i}]")
    cur = labels[0]
    for i in range(1, len(labels)):
        tr = E.transition_of(ed, i)
        nxt = f"[x{i}]"
        if tr["dur"] > 0:
            parts.append(f"{cur}{labels[i]}acrossfade=d={tr['dur']:.4f}:c1=tri:c2=tri{nxt}")
        else:
            parts.append(f"{cur}{labels[i]}concat=n=2:v=0:a=1{nxt}")
        cur = nxt
    graph = ";".join(parts) + (f";{cur}anull[out]" if len(labels) > 1 else f";{labels[0]}anull[out]")
    core.ffmpeg("-loglevel", "error", "-y", *ins, "-filter_complex", graph, "-map", "[out]",
                "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", out)
    return out


# ─── лицензии ─────────────────────────────────────────────────────────────────
def check_license(path):
    """Трек без строки в реестре лицензий в работу не идёт: защищает лицензия, не эквалайзер.
    Принимается: имя файла в реестре или папка пака (с License.txt внутри), названная в реестре."""
    path = os.path.abspath(path)
    name = os.path.basename(path)
    packs, d = [], os.path.dirname(path)
    while d and d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, "License.txt")):
            packs.append(os.path.basename(d))
        d = os.path.dirname(d)
    for reg in (config.LICENSES,):
        if not os.path.exists(reg):
            continue
        with open(reg, encoding="utf-8") as f:
            text = f.read()
        for sec in text.split("\n## "):
            if name in sec or any(f"{p}/License.txt" in sec for p in packs):
                lic = next((ln for ln in sec.splitlines() if name in ln), None) or \
                    next((ln for ln in sec.splitlines() if ln.lstrip("- ").lower().startswith("licen")), sec.splitlines()[0])
                if "CC-BY" in lic.upper():
                    core.say(f"! {name}: CC-BY — в подписи к посту нужна кредит-строка")
                return lic.strip()
    raise SystemExit(f"«{name}» нет в реестре лицензий ({config.LICENSES}) — "
                     "внеси строку с лицензией и источником или возьми другой трек")


def mix(project, voice_wav, out, chain):
    """Голос (+ музыка с вырезом полосы речи и приседанием) (+ SFX по ленте) → mix.wav."""
    ed, au = project.edit, project.edit["audio"]
    total = E.total_duration(ed)
    ins = ["-i", voice_wav]
    g = [f"[0:a]{chain},pan=stereo|c0=c0|c1=c0,aresample=48000[v]"]
    layers = ["[v]"]
    music = au.get("music")
    if music:
        mp = project.abspath(music["path"])
        check_license(mp)
        ins += ["-stream_loop", "-1", "-i", mp]
        under = float(music.get("under", 16))
        fin, fout = float(music.get("intro", 1.0)), float(music.get("outro", 1.5))
        g[0] = g[0].replace("[v]", "[vv]")
        g.append("[vv]asplit=2[v][vsc]")
        mchain = (f"[1:a]atrim=0:{total:.3f},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=stereo,"
                  f"equalizer=f=800:t=q:w=1.4:g=-3,equalizer=f=2500:t=q:w=1.2:g=-2,volume=-{under:.1f}dB,"
                  f"afade=t=in:st=0:d={fin:.2f},afade=t=out:st={max(0, total - fout):.3f}:d={fout:.2f}")
        if music.get("duck", True):
            g.append(mchain + "[m0]")
            g.append("[m0][vsc]sidechaincompress=threshold=0.05:ratio=6:attack=15:release=350:makeup=1[m]")
        else:
            g.append(mchain + "[m]")
            g.append("[vsc]anullsink")
        layers.append("[m]")
    for k, s in enumerate(au.get("sfx", [])):
        sp = project.abspath(s["path"])
        check_license(sp)
        idx = len(ins) // 2
        ins += ["-i", sp]
        ms = int(float(s["t"]) * 1000)
        g.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={float(s.get('gain', -10)):.1f}dB,"
                 f"adelay={ms}|{ms}[s{k}]")
        layers.append(f"[s{k}]")
    if len(layers) > 1:
        g.append("".join(layers) + f"amix=inputs={len(layers)}:duration=first:normalize=0[out]")
    else:
        g.append("[v]anull[out]")
    core.ffmpeg("-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(g), "-map", "[out]",
                "-t", f"{total:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", out)
    return out


def master(src, out, fade_out=None, total=None):
    """Мастер −14 LUFS / TP −1, стерео 48 кГц: усиление → лимитер → линейный loudnorm."""
    pre = []
    if core.media_info(src).get("channels", 2) == 1:
        # моно → в оба канала ДО замера: иначе −ac 2 на выходе добавит ~3 LU сверх цели
        pre.append("pan=stereo|c0=c0|c1=c0")
    if fade_out and total:
        pre.append(f"afade=t=out:st={max(0.0, total - fade_out):.3f}:d={fade_out:.2f}")
    base = ",".join(pre) or "anull"
    st = core.loudnorm_stats(src, base)
    if st["input_i"] in ("-inf", None) or float(st["input_i"]) < -70:
        raise SystemExit("звук пустой: интегральная громкость ниже −70 LUFS")
    gain = round(config.LUFS_TARGET - float(st["input_i"]), 2)
    limit = round(10 ** ((config.TRUE_PEAK - config.LIMIT_MARGIN) / 20), 4)
    chain = base + f",volume={gain}dB,alimiter=limit={limit}:level=false:attack=5:release=50"
    st2 = core.loudnorm_stats(src, chain)
    chain += (f",loudnorm=I={config.LUFS_TARGET}:TP={config.TRUE_PEAK}:LRA={config.LRA}"
              f":measured_I={st2['input_i']}:measured_TP={st2['input_tp']}:measured_LRA={st2['input_lra']}"
              f":measured_thresh={st2['input_thresh']}:offset={st2['target_offset']}:linear=true")
    core.ffmpeg("-loglevel", "error", "-y", "-i", src, "-af", chain, "-ar", str(config.AUDIO_RATE),
                "-ac", "2", "-c:a", "pcm_s24le", out)
    return out, gain


def gates(path):
    """Гейты звука: стерео, L/R RMS равны, громкость в цели. Возвращает (провалы, замер)."""
    info = core.media_info(path)
    fails = []
    if info.get("channels") != 2:
        fails.append(f"каналов {info.get('channels')} — на телефоне заиграет в одно ухо")
    rms = core.lr_rms(path)
    if len(rms) >= 2 and abs(rms[0] - rms[1]) > config.LR_RMS_TOLERANCE:
        fails.append(f"L/R расходятся на {abs(rms[0] - rms[1]):.2f} dB — one-ear")
    ld = core.loudness(path)
    if ld["I"] is None or abs(ld["I"] - config.LUFS_TARGET) > config.LUFS_TOLERANCE:
        fails.append(f"громкость {ld['I']} LUFS, цель {config.LUFS_TARGET} ±{config.LUFS_TOLERANCE}")
    return fails, {**ld, "rms": rms}


def run(project):
    ed, au = project.edit, project.edit["audio"]
    w = project.work
    raw = timeline_audio(project, os.path.join(w, "voice-raw.wav"))
    chain = voice_chain(au.get("profile", "clean_vo"), au.get("polish", False),
                        au.get("comp", 2.6), au.get("space", "none"))
    mixed = mix(project, raw, os.path.join(w, "mix.wav"), chain)
    total = E.total_duration(ed)
    out, gain = master(mixed, os.path.join(w, "master.wav"), ed.get("fade_out"), total)
    fails, m = gates(out)
    core.say(f"звук: {m['I']} LUFS, LRA {m['LRA']}, пик {m['TP']} dBTP, усиление {gain:+} dB, "
             f"цепочка голоса «{au.get('profile')}»{' + полировка' if au.get('polish') else ''}")
    if m["TP"] is not None and m["TP"] > config.TRUE_PEAK + 0.3:
        core.say(f"! пик {m['TP']} dBTP выше {config.TRUE_PEAK} — послушать один раз")
    if fails:
        raise SystemExit("ГЕЙТ ЗВУКА: " + "; ".join(fails))
    return out
