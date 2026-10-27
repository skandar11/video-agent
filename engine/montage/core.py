"""Ядро: запуск ffmpeg/ffprobe, замеры, журнал команд. Одна копия на весь пакет.
"""
import json
import os
import re
import shlex
import subprocess
import sys

from . import config

# Журнал команд прогона: каждая команда ffmpeg ложится строкой в commands.sh проекта, чтобы
# ролик можно было пересобрать без памяти агента.
_LOG = None


def set_log(path):
    global _LOG
    _LOG = path
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)


class FFError(RuntimeError):
    pass


def run(cmd, capture=False, check=True, log=True):
    """Запустить команду. capture=True — вернуть stderr (туда ffmpeg пишет замеры)."""
    cmd = [str(c) for c in cmd]
    if log and _LOG and cmd and os.path.basename(cmd[0]) in ("ffmpeg", "ffprobe"):
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(shlex.join(cmd) + "\n")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        tail = "\n".join(r.stderr.strip().splitlines()[-15:])
        raise FFError(f"{os.path.basename(cmd[0])} упал (код {r.returncode}):\n{tail}")
    return r.stderr if capture else r


def ffmpeg(*args, capture=False, check=True):
    return run([config.FFMPEG, "-hide_banner", "-nostdin", *args], capture=capture, check=check)


# ─── probe ───────────────────────────────────────────────────────────────────
def probe(path):
    r = run([config.FFPROBE, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path], log=False)
    return json.loads(r.stdout)


def _rotation(stream):
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(float(sd["rotation"]))
    try:
        return int(float(stream.get("tags", {}).get("rotate", 0)))
    except (TypeError, ValueError):
        return 0


def _rate(s):
    try:
        n, d = s.split("/")
        return round(float(n) / float(d), 3) if float(d) else 0.0
    except (ValueError, AttributeError):
        return 0.0


def media_info(path):
    """Сводка источника: размер КАК ВИДНО (с поворотом — у айфона вертикаль пишется
    горизонтальным кадром + матрицей), fps, длительность, HDR-передача, звук."""
    info = probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    out = {"duration": float(info["format"].get("duration", 0) or 0), "audio": a is not None}
    if v:
        w, h, rot = int(v.get("width", 0)), int(v.get("height", 0)), _rotation(v)
        if abs(rot) % 180 == 90:
            w, h = h, w
        trc = v.get("color_transfer", "")
        out.update({
            "w": w, "h": h, "rotation": rot, "fps": _rate(v.get("avg_frame_rate") or v.get("r_frame_rate")),
            "transfer": trc, "primaries": v.get("color_primaries", ""),
            "hdr": config.HDR_TRANSFERS.get(trc), "pix_fmt": v.get("pix_fmt", ""),
            "codec": v.get("codec_name", ""),
        })
    if a:
        out.update({"channels": int(a.get("channels", 0)), "sample_rate": int(a.get("sample_rate", 0))})
    return out


def duration(path):
    return media_info(path)["duration"]


# ─── замеры звука ─────────────────────────────────────────────────────────────
def loudness(path, af=None):
    """EBU R128 одним проходом: интегральная громкость, LRA, true peak."""
    chain = (af + "," if af else "") + "ebur128=peak=true"
    err = ffmpeg("-i", path, "-af", chain, "-f", "null", "-", capture=True)
    summ = err[err.rfind("Summary:"):]

    def num(pat):
        m = re.search(pat, summ)
        if not m or "inf" in m.group(1):
            return None
        return float(m.group(1))
    return {"I": num(r"I:\s*(-?[\d.]+|-inf) LUFS"), "LRA": num(r"LRA:\s*(-?[\d.]+) LU"),
            "TP": num(r"Peak:\s*(-?[\d.]+|-inf) dBFS")}


def lr_rms(path):
    """RMS по каналам (astats, общая сводка). Для моно — один элемент."""
    err = ffmpeg("-i", path, "-af", "astats=metadata=1:reset=0", "-f", "null", "-", capture=True)
    blocks = re.split(r"Channel: \d+", err)
    vals = []
    for b in blocks[1:]:
        m = re.search(r"RMS level dB:\s*(-?[\d.]+|-?inf)", b)
        if m:
            vals.append(float("-inf") if "inf" in m.group(1) else float(m.group(1)))
    return vals


def loudnorm_stats(path, af):
    """Первый проход loudnorm: JSON замера для линейного второго прохода."""
    err = ffmpeg("-i", path, "-af", af + ",loudnorm=I=%s:TP=%s:LRA=%s:print_format=json"
                 % (config.LUFS_TARGET, config.TRUE_PEAK, config.LRA), "-f", "null", "-", capture=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err)
    if not m:
        raise FFError("loudnorm: замер не вернул JSON")
    return json.loads(m.group(0))


# ─── замеры кадра ─────────────────────────────────────────────────────────────
def scene_cuts(path, thr=0.30):
    """Жёсткие склейки по смене сцены. Мягкие переходы (xfade) детектор не видит — это
    известно и учтено в гейте ритма."""
    err = ffmpeg("-i", path, "-filter:v", f"select='gt(scene,{thr})',showinfo", "-f", "null", "-",
                 capture=True)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", err)]


def grab_frame(path, t, out, vf=None):
    args = ["-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", path]
    if vf:
        args += ["-vf", vf]
    ffmpeg(*args, "-frames:v", "1", "-q:v", "2", out, check=False)
    return os.path.exists(out)


def esc_filter_path(p):
    """Путь внутрь графа ffmpeg (ass=, arnndn=): двоеточия и кавычки экранированы."""
    return os.path.abspath(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def say(*a):
    print(*a, file=sys.stderr if os.environ.get("MONTAGE_QUIET") else sys.stdout)
