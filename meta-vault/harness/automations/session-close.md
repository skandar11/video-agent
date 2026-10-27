---
title: session-close — протокол завершения сессии
type: spec
status: active
sensitivity: normal
scope: all
updated: 2026-10-10
tags: [session-close, discipline, ritual, hooks, harness]
related:
  - ../../harness
  - ../../operations/close-session
  - ../../vault-template
---

# session-close — протокол завершения сессии

Хроническая болезнь любой живой базы: сессия закончилась — записи уровня не
обновлены. `status.md` мёртв неделями, карта не знает о новых файлах, хвосты
не попали в backlog. Правило-основание: **запись без обновления карты =
потерянная работа** — файл, на который ничего не указывает, для следующей
сессии не существует.

## Ритуал (ядро; работает руками)

В конце сессии, **если в ней менялись файлы**, агент закрывает записи уровня,
на котором шла работа:

1. **status.md уровня** — горячее состояние: что сделано, что в работе,
   блокеры видны прямо здесь (контракт —
   [[../../vault-template|vault-template]]). На верхнем уровне `status.md`
   нет — там закрываются `planning/backlog.md` + `planning/inbox.md`.
2. **Карта (HOME.md)** — если появились, переехали или умерли объекты:
   карта обязана про них знать.
3. **Backlog** (`planning/backlog.md` уровня) — новые хвосты одной строкой;
   закрытые — вычеркнуть.
4. **Inbox** — накиданное по ходу сессии разобрано или явно оставлено.
5. **Checkpoint-коммит** в затронутых репозиториях (push — только по слову).
6. **Сказать владельцу, что осталось незакрытым** — одной строкой, без
   приукрашивания.

«Нечего закрывать» — легальный ответ, но **явный**: агент говорит это одной
строкой, а не молчит.

Операция — [[../../operations/close-session|закрыть сессию]]; этот файл —
спека и опциональный хук.

## Закон автоматизации

Не автоматизировать, пока ритуал не работает руками. Хук ниже — усилитель
дисциплины, не её замена: он напоминает, закрывает — агент.

## Приложение: автоматизация хуками (Claude Code) — выключена по умолчанию

Строка в `inventory/automations.md` + слово владельца — тогда включается.

Механика «снапшот-вариант»: харнесс сам напоминает агенту в конце сессии —
но только если дерево файлов реально менялось **в этой сессии**.

- **SessionStart** — снимает хэш `git status --porcelain` рабочего дерева;
  существующий снапшот той же сессии не перезаписывает (устойчивость к
  resume/compact).
- **Stop** — сравнивает текущий хэш со снапшотом; если дерево менялось —
  один раз выходит с кодом 2: агент получает напоминание и запускает ритуал.
- **Один раз за сессию** — штамп `reminded` на session_id; дальше стопы
  проходят молча. `stop_hook_active` → пропуск (защита от зацикливания).

Границы: не-git cwd → пропуск; сессия старше хука (нет снапшота) → пропуск —
старая грязь дерева не должна ныть; автоматизации ставят
`NAMESPACE_AUTOMATION=1` → хук молчит; хук пишет **только** штампы в
`~/.local/state/session-close/` (авточистка старше 7 дней), файлы не правит,
git не трогает. Kill-switch: убрать блок hooks из `~/.claude/settings.json`
и удалить скрипт.

Блок в `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "~/bin/session-close-reminder start" }] }],
    "Stop": [{ "hooks": [{ "type": "command",
      "command": "~/bin/session-close-reminder stop" }] }]
  }
}
```

Скрипт `~/bin/session-close-reminder`:

```zsh
#!/bin/zsh
# session-close-reminder — исполнитель; источник правды:
# meta-vault/harness/automations/session-close.md
set -u
mode="${1:-}"
[ "${NAMESPACE_AUTOMATION:-0}" = "1" ] && exit 0

input=$(cat 2>/dev/null || true)
parsed=$(printf '%s' "$input" | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get("session_id",""))
print(d.get("cwd",""))
print("1" if d.get("stop_hook_active") else "0")
' 2>/dev/null)
sid=$(printf '%s\n' "$parsed" | sed -n 1p)
cwd=$(printf '%s\n' "$parsed" | sed -n 2p)
stop_active=$(printf '%s\n' "$parsed" | sed -n 3p)

STATE="$HOME/.local/state/session-close"; mkdir -p "$STATE"
find "$STATE" -type f -mtime +7 -delete 2>/dev/null
[ -z "$sid" ] && exit 0
[ -n "$cwd" ] || cwd="$PWD"
git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
# macOS: md5; Linux: замените на md5sum
hash=$(git -C "$cwd" status --porcelain 2>/dev/null | md5)

case "$mode" in
  start)
    # не перезаписывать снапшот (resume/compact повторно шлют SessionStart)
    [ -f "$STATE/$sid.snap" ] || printf '%s' "$hash" > "$STATE/$sid.snap"
    ;;
  stop)
    [ "$stop_active" = "1" ] && exit 0
    [ -f "$STATE/$sid.reminded" ] && exit 0
    [ -f "$STATE/$sid.snap" ] || exit 0   # сессия старше хука: не ныть
    snap=$(cat "$STATE/$sid.snap")
    if [ "$hash" != "$snap" ]; then
      : > "$STATE/$sid.reminded"
      cat >&2 <<'MSG'
session-close: рабочее дерево менялось в этой сессии. Перед закрытием выполни
ритуал закрытия уровня по его локальному CLAUDE.md (обнови status / карту /
backlog); если закрывать нечего — скажи это владельцу явно одной строкой.
Напоминание одноразовое (спека: meta-vault/harness/automations/session-close.md).
MSG
      exit 2
    fi
    ;;
esac
exit 0
```

## Лестница ужесточения

Напоминание — первая ступень. Гейт вместо напоминания (стоп не проходит, пока
записи не закрыты) или свои тексты по уровням — только отдельным осознанным
шагом, когда напоминание перестанет хватать.
