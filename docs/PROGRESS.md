# PROGRESS — Retman

Bieżący stan prac. Stan gałęzi, tagów i `origin` sprawdzaj w gicie
(`git status`, `git log`, `git ls-remote --tags origin`), nie w tym dzienniku.
Szablony wpisów: [Szablony](#szablony).

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|

## Checkpointy

## Ostatnia sesja

## Backlog

---

## Szablony

**Status elementu** — wiersz tabeli „Status projektu”; status: `✅ Gotowy`,
`🚧 W toku`, `⏳ Planowany`, `❌ Wstrzymany`:

```markdown
| Element | ✅ Gotowy | wersja, odsyłacze (ADR-XXX, ARCHITECTURE p. X.Y), uwagi |
```

**Checkpoint** — po każdym wydaniu, od najstarszego:

```markdown
### CPN — Tytuł
- **Data:** RRRR-MM-DD
- **Wersja:** vX.Y.Z
- **Zakres:** najważniejsze zmiany; pełna lista: `docs/CHANGELOG.md` [X.Y.Z]
```

**Sesja** — na początku sekcji „Ostatnia sesja” (od najnowszej); stan do
podjęcia w następnej sesji w bloku `START NASTĘPNEJ SESJI` nad wpisami:

```markdown
> **START NASTĘPNEJ SESJI (stan RRRR-MM-DD):** co jest w toku, co zrobić
> najpierw, jakie decyzje czekają na użytkownika.

### Tytuł sesji (RRRR-MM-DD)

- **Zlecenie użytkownika:** czego dotyczyła sesja.
- **Decyzje użytkownika:** ustalenia (ADR-XXX, jeśli powstał).
- **Zrobione:** zmiany z odsyłaczami (pliki, commity, raporty).
- **Weryfikacja:** co uruchomiono i z jakim wynikiem.
- **Otwarte:** co zostało i dlaczego.
```

**Pozycja backlogu** — w podsekcji wersji docelowej; `[x]` po zakończeniu,
z odsyłaczem do miejsca realizacji:

```markdown
#### Do X.Y.Z

- [ ] **Tytuł** — opis, źródło (PRD W-xx / ARCHITECTURE p. X.Y / ADR-XXX).
```
