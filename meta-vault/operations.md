---
title: operations — реестр операций верха
type: registry
status: active
sensitivity: normal
scope: all
axis: vault
updated: 2026-10-10
related:
  - HOME
  - vault-template
---

# Операции верха

Агент действует **по операции, не по памяти**. Форма операции —
[[vault-template]] §Операции. Операции нет, пока нет строки здесь.

| Операция | Вызов | Род | Статус |
|---|---|---|---|
| [[operations/triage-inbox\|разобрать inbox]] | «разбери inbox», «что накидано» | write | possible |
| [[operations/close-session\|закрыть сессию]] | конец сессии, где менялись файлы | write | possible |
| [[operations/how-are-things\|как идут дела]] | «как дела», «что горит» | read | possible |
| [[operations/build-namespace\|собрать неймспейс]] | «собери неймспейс», первый запуск | write | possible |
| [[operations/new-domain\|новый домен]] | «заведи домен под …» | write | possible |
| [[operations/check-links-and-names\|проверить базу]] | «проверь базу», перед передачей | read | live |
| [[operations/accept-new-version\|принять новую версию]] | «обнови метод» | write | possible |

`possible` → `live` — только после живого прогона.
