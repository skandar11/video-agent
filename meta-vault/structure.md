---
title: structure — состояние сборки неймспейса
type: status
status: active
sensitivity: normal
scope: all
updated: 2026-10-19
related:
  - vault-template
  - operations/check-links-and-names
  - operations/accept-new-version
---

# Структура — состояние сборки

Состояние **устройства** неймспейса, отдельно от состояния дел (дела — в
`status.md` доменов и `../planning/backlog.md`). Снимок, не журнал.

## Версия

- **Форма шаблона:** 2026-10-10 (первая строка журнала в [[vault-template]]).
- **Собран:** 2026-10-19 — поставка под монтаж: домен `video/` + `engine/`
- **Владелец:** <имя> · **агент:** <имя>

## Здоровье (из прогона `bin/check`, с датой)

2026-10-19: битых связей 0, неуникальных имён 0, секретов в индексе 0; пометок `<настрой>` 6 — имя владельца и агента, ждут первого запуска.

## Расхождения с шаблоном

| Правило шаблона | Как здесь | Почему |
|---|---|---|
| домены-заготовки `project/` и `office/` | не взяты | минимальная поставка под одно дело; образец хребта нового домена — `video/` |
| домен — дверь + vault + записи | ещё `engine/` в корне — код без vault | код рядом с vault, в vault кода нет; дверь `video/` указывает на него |

## Файлы метода (едут из шаблона при [[operations/accept-new-version|новой версии]])

`meta-vault/vault-template.md` · `meta-vault/principles.md` ·
`meta-vault/glossary.md` · `meta-vault/forms/` · `meta-vault/examples/` ·
`meta-vault/harness/` · `meta-vault/operations/build-namespace.md` ·
`new-domain.md` · `check-links-and-names.md` · `accept-new-version.md` ·
`bin/check`. Всё прочее — файлы владельца.

## Журнал сборки

Новое сверху; только устройство.

- 2026-10-19 — собран под монтаж: `video/`, `engine/`, `bin/setup`, навык `montage`.
- 2026-10-10 — шаблон.
