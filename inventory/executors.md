---
title: executors — руки агента
type: registry
status: active
sensitivity: normal
scope: all
updated: 2026-10-19
related:
  - ../meta-vault/harness
  - automations
---

# Executors — руки агента

Агент один (`../CLAUDE.md` §Агент). Всё остальное — исполнители: делают шаг,
суждения не несут. Исполнитель не существует, пока его нет здесь. Закон —
`meta-vault/harness.md`.

| Исполнитель | Род | Где живёт | Что делает | Кто зовёт | Статус |
|---|---|---|---|---|---|
| `montage` | script | `engine/montage/` (Python 3.12 + ffmpeg-full), команда `engine/.venv/bin/montage` | монтаж и проверка роликов по `edit.json` | [[../video/video-vault/operations/montage-reel\|смонтировать]] · [[../video/video-vault/operations/check-reel\|проверить]] | in-dev |
| `bin/setup` | script | `bin/setup` (zsh) | установка движка: ffmpeg-full, Python, `engine/.venv`, Inter | первый запуск (`../CLAUDE.md`) | live |
| `montage` (навык) | skill | `.claude/skills/montage/SKILL.md` | указатель на операции `video/` | фразы «смонтируй», «проверь ролик» | live |
| `bin/check` | script | `bin/check` (python3, stdlib) | прогон: связи, имена, таблицы, секреты в индексе; только читает | [[../meta-vault/operations/check-links-and-names\|проверить базу]] | live |

_(строка на каждый скилл, скрипт, суб-агент, MCP-сервер, канал; род:
skill · script · subagent · mcp · channel · cron; статус: possible · live · off)_
