---
title: montage — памятка движка монтажа
type: tool
status: active
sensitivity: normal
scope: work
updated: 2026-10-19
related:
  - ../craft
  - ../operations/montage-reel
  - ../operations/check-reel
---

# Инструмент — движок `montage`

Код — `../../../engine/montage/` (Python 3.12 + ffmpeg-full). Установка —
`../../../bin/setup`. Команда (от корня репозитория):

```sh
M=engine/.venv/bin/montage
```

**Что умеет:** приём исходников (размер с поворотом, к/с, HDR по метке, звук) · расшифровка
со словами (mlx-whisper large-v3-turbo, кэш по файлу) · каты по паузам речи · наезды для
ритма · скорость · переходы · вписывание в вертикаль · сплит двух источников · грейд ·
карточки поверх кадра · субтитры · звук до −14 LUFS стерео с музыкой и SFX · гейты
качества · контактный лист.

## Команды

| Команда | Что делает |
|---|---|
| `$M init <проект> [--title …]` | папка проекта + пустой `edit.json` |
| `$M ingest <проект> <файлы…> --id a --id b` | источники в лист; печатает размер, к/с, HDR, звук |
| `$M transcribe <проект> [--src a] [--lang ru]` | слова с таймингами → `work/words-<src>.json` |
| `$M cuts <проект> --src a [--keep '[[3.8,13.4]]'] [--punch 2.5] [--append]` | куски без пауз внутри `keep`; `--punch` — наезды каждые N с |
| `$M audio` · `subs` · `cards <проект>` | отдельные станции (обычно не нужны — их зовёт `run`) |
| `$M run <проект> [--rhythm]` | звук → карточки → сабы → сборка → гейты → контактный лист |
| `$M qa <проект или mp4> [--rhythm]` | гейты готового файла; код 1, если не прошли |
| `$M look <проект или mp4>` | контактный лист с безопасной зоной Reels/TikTok/Shorts |
| `$M master <вход> <выход.wav>` | любой звук в −14 LUFS стерео + гейты |

Первый `transcribe` скачивает модель (~1,6 ГБ) — один раз.

## Монтажный лист `edit.json`

Время кусков — **по исходнику** (in/out в секундах файла); всё остальное (карточки, SFX) —
**по выходной ленте**.

- `clips[]`: `src`, `in`, `out`, `speed` (≤ 1,1 на живой речи), `zoom` (1.07 — наезд),
  `anchor` (`c` `t` `b` `l` `r` `tl` `tr` `bl` `br` или `[x, y]`), `fit` (`auto` · `crop` ·
  `blur` — горизонталь/экран с размытыми полями · `solid` — на чёрном),
  `transition` (переход ПЕРЕД куском: `{"type": "fade", "dur": 0.3}` — любой тип xfade),
  `panes` + `gap` (сплит: панели разных источников одна над другой).
- `transition` — переход по умолчанию (`{"type": "cut"}`).
- `look`: `natural` (по умолчанию) · `alive` · `screen` · `cinematic`.
- `subs`: `style` (`cards` · `word` · путь к своему JSON), `fix` (`{"неверно": "верно"}`),
  `accent_words`, `enabled`, `ass` (готовый файл сабов — взять как есть).
- `cards[]`: `id`, `t0`, `t1`, `lines[{t, color, size, font}]`, `bg`, `bg_alpha`, `radius`,
  `pad`, `y` (иначе по центру), `dim` (затемнить кадр под финалом, 0–255), `fade`.
- `audio`: `profile` (`clean_vo` · `noisy_street` · `phone` · `damaged` · `none`),
  `polish`, `music` (`{"path", "under": 16, "intro", "outro", "duck": true}`),
  `sfx[]` (`{"path", "t", "gain": -10}`).
- `fade_out` (с) · `quality` (`high` · `feed` · `max`).

## Выход

`out/reel.mp4` · `out/look.jpg` · `out/qa.json`; журнал команд — `work/commands.sh`,
граф — `work/graph.txt`.

## Лимиты и грабли

- Только Mac на Apple Silicon: расшифровка — mlx-whisper на Metal.
- Шумодав RNNoise (`noisy_street`) — по файлу `engine/models/bd.rnnn`, в поставку он не
  входит (лицензия модели не сверена); без файла шаг пропускается, остальная чистка
  работает. Как добавить — `../../../engine/models/README.md`.
- Музыка и SFX без строки в `../../assets/licenses.md` — отказ сборки, это намеренно.
- Шрифт Inter ставит `bin/setup`; нет шрифта — карточки и лист берут системный.

**Доступ:** ключей не нужно, всё локально.
