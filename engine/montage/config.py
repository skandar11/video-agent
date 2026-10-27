"""Константы тракта — один источник для всех станций пакета.

Числа — из живых прогонов; ремесло и пороги с пояснениями — `video/video-vault/craft.md`.
Расходятся код и ремесло — правда за последним словом владельца, второе место правится тем же
проходом.
"""
import os

# ─── пути ────────────────────────────────────────────────────────────────────
PKG = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(PKG)                         # engine/
ROOT = os.path.dirname(ENGINE)                        # корень репозитория
MODELS = os.path.join(ENGINE, "models")
RNNOISE = os.path.join(MODELS, "bd.rnnn")             # необязательно: нет файла — шаг шумодава пропускается
STYLES = os.path.join(PKG, "styles")
LICENSES = os.path.join(ROOT, "video", "assets", "licenses.md")

# ffmpeg-full (brew, keg-only) — в нём zscale, libass, arnndn; обычный `ffmpeg` из brew их может не иметь.
_FULL = "/opt/homebrew/opt/ffmpeg-full/bin"
FFMPEG = os.environ.get("FFMPEG") or (f"{_FULL}/ffmpeg" if os.path.exists(f"{_FULL}/ffmpeg") else "ffmpeg")
FFPROBE = os.environ.get("FFPROBE") or (f"{_FULL}/ffprobe" if os.path.exists(f"{_FULL}/ffprobe") else "ffprobe")

# ─── шрифты: static TTF в ~/Library/Fonts — их видят и Pillow, и libass ───────
# Ставит `bin/setup` (Inter, OFL). Нет файла — станции берут системный шрифт.
FONTS = os.path.expanduser("~/Library/Fonts")
FONT_DIRS = (FONTS, "/Library/Fonts", "/System/Library/Fonts/Supplemental", "/System/Library/Fonts")
FALLBACK_FONTS = ("Arial Bold.ttf", "Arial.ttf", "Helvetica.ttc")


def font_path(name):
    """Имя файла без .ttf (Inter-ExtraBold) → путь; нет — первый системный запасной."""
    for d in FONT_DIRS:
        for ext in (".ttf", ".otf", ".ttc"):
            p = os.path.join(d, name + ext)
            if os.path.exists(p):
                return p
    for d in FONT_DIRS:
        for fb in FALLBACK_FONTS:
            p = os.path.join(d, fb)
            if os.path.exists(p):
                return p
    return None


# ─── цвет подложки для вписывания `solid` ─────────────────────────────────────
PAD_COLOR = (0, 0, 0)

# ─── кадр ─────────────────────────────────────────────────────────────────────
FRAME_W, FRAME_H, FPS = 1080, 1920, 30

# ─── тонмап HDR → SDR bt709 ───────────────────────────────────────────────────
# npl — параметр материала, не константа. HLG с айфона (говорящая голова) — 100;
# стоп-кадр обложки (судится глазом) — 250; PQ на солнечной улице — 400 + desat 2
# (иначе небо уходит в розовое пятно).
NPL = {"hlg": 100, "pq": 400, "cover": 250}
DESAT = {"hlg": 0, "pq": 2, "cover": 0}
HDR_TRANSFERS = {"arib-std-b67": "hlg", "smpte2084": "pq"}


def tonemap(npl, desat=0):
    """zscale linear → hable → bt709. Ставится ПЕРВЫМ в графе кадра (код-гейт «тонмап-первым»)."""
    return (f"zscale=t=linear:npl={npl},format=gbrpf32le,zscale=p=bt709,"
            f"tonemap=tonemap=hable:desat={desat},zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


# ─── звук (жёсткие гейты) ─────────────────────────────────────────────────────
LUFS_TARGET = -14
TRUE_PEAK = -1
LRA = 11
LUFS_TOLERANCE = 1.0    # гейт: интегральная громкость в пределах ±1 LU от цели
LR_RMS_TOLERANCE = 0.5  # гейт: L/R RMS в пределах 0,5 dB (no one-ear)
LIMIT_MARGIN = 1.5      # потолок лимитера ниже TRUE_PEAK (запас на AAC)
AUDIO_RATE = 48000

# ─── экспорт ──────────────────────────────────────────────────────────────────
# high — по умолчанию: площадка всё равно пережмёт, но из чистого исходника — лучше.
# feed — экономный (crf 22 + потолок под пёструю листву); max — графика и экран.
QUALITY = {
    "feed": {"crf": 22, "maxrate": "7M", "bufsize": "14M"},
    "high": {"crf": 19, "maxrate": "12M", "bufsize": "24M"},
    "max": {"crf": 16, "maxrate": "20M", "bufsize": "40M"},
}
X264_PRESET = "slow"

# ─── грейд ────────────────────────────────────────────────────────────────────
# Подобраны стендом по доле выбитых/задавленных пикселей. alive — поднимает только цвет,
# тон не трогает. Резкости нет: unsharp поверх ужатия 2160→1080 рисует каёмки, детали берёт
# lanczos на масштабе.
LOOK = {
    "natural": None,
    "alive": "vibrance=intensity=0.50",
    "screen": "eq=saturation=1.04:contrast=1.08,unsharp=luma_msize_x=3:luma_msize_y=3:luma_amount=1.1:chroma_amount=0",
    "cinematic": ("colorbalance=bs=0.028:rh=0.014:bh=-0.010,"
                  "curves=all='0/0.012 0.10/0.095 0.30/0.30 0.62/0.665 0.88/0.925 1/1',"
                  "vibrance=intensity=0.85"),
}

# ─── безопасная зона Reels · TikTok · Shorts ──────────────────────────────────
SAFE_W, SAFE_H = 900, 1400
UI_TOP, UI_BOTTOM, UI_RIGHT = 120, 250, 200
IG_HEADER = 260         # верх надписей не выше 260 px — под шапкой Instagram

# ─── ритм ─────────────────────────────────────────────────────────────────────
RHYTHM = {"avg_max": 3.0, "longest_max": 5.0, "first_cut_max": 2.0, "min_shots": 8, "scene": 0.30}
