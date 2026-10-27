---
type: reference
status: active
sensitivity: normal
scope: all
tags: [home, index, vault, map]
updated: 2026-10-10
---

# meta-vault — карта

meta-vault верха: vault *о самом неймспейсе* — **только знание** (канон,
метод, решения, формы, описания папок записей). То, что сделано и что есть, —
в папках записей рядом (`../planning/`, `../inventory/`, `../people/`).
Конвенции — [[principles]]. Дверь — `../CLAUDE.md`.

## Владелец и агент

- [[owner]] — кто владелец, как обращаться.
- [[preferences]] — правила владельца агенту: инвариант, стиль, язык.
- [[for-owner]] — полка объяснялок: агент пишет, владелец читает.

## Папки записей верха (описание здесь, записи рядом)

- [[planning]] → `../planning/` — план верха: `backlog.md` (реестр живого),
  `inbox.md` (захват). Операции: [[operations/triage-inbox|разобрать inbox]],
  [[operations/close-session|закрыть сессию]].
- [[harness]] → `../inventory/` — руки агента: исполнители, автоматизации;
  спеки — `harness/`.
- [[people]] → `../people/` — карточки людей поперёк доменов.

## Конструктор — как собирается база

- [[operations/build-namespace|собрать неймспейс]] — главный рецепт: разговор →
  верх → домены → записи → операции → приватность → проверка → передача.
- [[operations/new-domain|новый домен]] · [[operations/check-links-and-names|проверить базу]]
  · [[operations/accept-new-version|принять новую версию шаблона]].
- Формы: [[forms/domain-door-form|дверь домена]] · [[forms/zone-form|зона и
  папка записей]] · [[forms/operation-form|операция]] ·
  [[forms/process-form|процесс]] · [[forms/tool-form|инструмент]] ·
  [[forms/handover-door-form|передача]].
- Пример связки: [[examples/marketplace|вывести товар на маркетплейс]].
- [[structure]] — состояние сборки: версия формы, здоровье, расхождения.

## Знание

- [[decisions]] → `decisions/` — датированные решения, дословные слова
  владельца. Папка рождается с первым решением.
- [[ideas]] → `ideas/` — предложения, ещё не решения.
- [[operations]] — реестр операций верха; файлы — `operations/`.
- [[glossary]] — канон терминов.
- [[vault-template]] — база-баз: форма уровня, vault, папок записей; журнал
  формы.
- [[principles]] — правила письма.
- [[secrets-map]] — где живут доступы (без значений) + контракт `secrets/`.

## Домены (связи вниз)

- `../video/` — монтаж снятого. Дверь + `video-vault/` + `planning/` + `inbox/` +
  `projects/` + `assets/`. Код — `../engine/`.

Сток — `../archive/INDEX.md`.
