# PROGRESS — Retman

Bieżący stan prac. Stan gałęzi, tagów i `origin` sprawdzaj w gicie
(`git status`, `git log`, `git ls-remote --tags origin`), nie w tym dzienniku.
Szablony wpisów: [Szablony](#szablony).

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| Dokumentacja projektowa (PRD, ARCHITECTURE, DEVELOPMENT_STANDARDS) | ✅ Gotowy | szkic 2026-10-11; otwarte kwestie: PRD rozdz. 11, ARCHITECTURE rozdz. 12 |
| Repozytorium (`main`, `develop`, `origin`) | ✅ Gotowy | `origin` = `github.com/Daldek/Retman`, nic nie wypchnięto |
| Lista pierwszych operacji v0.1 | ⏳ Planowany | PRD 7.2 — decyzja autora; blokuje manifesty, handlery i zbiór testowy |
| Szkielet pakietu, `pyproject.toml`, `retman.toml` i `retman init` | ⏳ Planowany | ARCHITECTURE 3.1, 9.1, 9.3; STANDARDS 5–8 |
| Ekstraktory (w tym prawdopodobieństwo) | ⏳ Planowany | ARCHITECTURE 4.4 — w pełni opisane |
| Backendy `basal`, `openai_compatible`, `none`; `FakeDecisionBackend` | ⏳ Planowany | ARCHITECTURE 3.3, 8.3 |
| Rdzeń: pipeline, `Plan`, `dialog`, `Result` | ⏳ Planowany | ARCHITECTURE 2, 6, 7.1, 7.3 |
| Rejestr operacji, wspólny adapter, `kinds`, `retman-scaffold` | ⏳ Planowany | ARCHITECTURE 3.2, 4.1–4.3 |
| Przestrzeń robocza, dziennik projektu, ślad audytowy | ⏳ Planowany | ARCHITECTURE 5 |
| CLI, `retman doctor`, `results`, `log` | ⏳ Planowany | ARCHITECTURE 6.4, 7.1, 7.2 |
| `retman-eval` i zbiór poleceń testowych | ⏳ Planowany | ARCHITECTURE 8 |
| CI (Windows, Linux, macOS; test instalacji; wersje narzędzi) | ⏳ Planowany | ARCHITECTURE 3.2.7, 9.4 |

## Checkpointy

### CP0 — Dokumentacja startowa
- **Data:** 2026-10-11
- **Wersja:** — (przed v0.1.0)
- **Zakres:** PRD, architektura, standardy deweloperskie, szablony DECISIONS/PROGRESS/CHANGELOG, README, CLAUDE.md, licencja MIT, konfiguracja repozytorium; pierwszy commit `70857c0`

## Ostatnia sesja

> **START NASTĘPNEJ SESJI (stan 2026-10-11):** kodu jeszcze nie ma; praca na
> `develop`, `origin` dodany, ale nic nie wypchnięto (push to decyzja
> użytkownika). Najpierw: szkielet pakietu z konfiguracją i ekstraktor
> prawdopodobieństwa (niezależne od listy operacji). Czeka na decyzję
> użytkownika: lista pierwszych operacji (PRD 7.2), rodzaje danych i formaty
> plików (PRD W-09, ARCHITECTURE 12 pkt 7), wartości docelowe (PRD W-01, N-07,
> rozdz. 8). Pełna lista: Backlog niżej.

### Start projektu: dokumentacja i repozytorium (2026-10-11)

- **Zlecenie użytkownika:** zapoznanie z dokumentacją, weryfikacja i aktualizacja
  dokumentów (subagent na modelu z roli `slow`), README, układ dokumentacji
  wg konwencji Kartografa, `CLAUDE.md`, standardy deweloperskie, inicjalizacja gita.
- **Decyzje użytkownika:**
  - liczba prawdopodobieństwa bez „%”, „Q” i okresu w latach zawsze wywołuje
    pytanie (ARCHITECTURE 4.4);
  - wykonanie bez potwierdzenia wykluczone w wersjach 0.x, nie na stałe
    (PRD 7.3, ARCHITECTURE 1.1, 1.2, 6.3, rozdz. 10);
  - `retman-eval` i zbiór poleceń testowych w pakiecie podstawowym
    (ARCHITECTURE 3.1, 8.1, 8.2, 9.3);
  - bez biblioteki do zapisu TOML: odczyt `tomllib`, `retman init` zapisuje
    z szablonu (ARCHITECTURE 9.3);
  - `DESIGN.md` → `docs/ARCHITECTURE.md`; dokumentacja w `docs/` jak w Kartografie;
  - końce linii LF we wszystkich plikach, bez wyjątków (STANDARDS 5.5);
  - repozytorium `github.com/Daldek/Retman`.
- **Zrobione:**
  - weryfikacja PRD i ARCHITECTURE: m.in. W-15 zależne od `journal_commands`,
    progi `"auto"` tylko z backendem `basal` (inaczej błąd konfiguracji,
    ARCHITECTURE 6.2), LM Studio dla decyzji już w 0.1 (9.4),
    `Retman.from_config()` czyta plik centralny (7.1), `Question.type` zamiast
    `Question.kind`, poprawiony przykład „Q1% i Q10%” (4.4), poprawione odsyłacze;
  - nowe pliki: `README.md`, `CLAUDE.md`, `docs/DEVELOPMENT_STANDARDS.md`,
    szablony `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/CHANGELOG.md`,
    `LICENSE`, `.gitignore`, `.gitattributes`, `.editorconfig`;
  - `git init`: commit `70857c0` na `main`, gałąź `develop`, remote `origin`;
    `<github-user>` w ARCHITECTURE zastąpione adresami `github.com/Daldek/…`.
- **Weryfikacja:** odsyłacze `p.`/`rozdz.`/`[W-xx]`/`[N-xx]`/`S-xx` sprawdzone
  skryptem subagenta (brak martwych); brak odwołań do `DESIGN`;
  `git ls-files --eol` bez `w/crlf`.
- **Otwarte:** decyzje z Backlogu; push na `origin`.

## Backlog

#### Do 0.1.0

Decyzje autora (blokują część implementacji):

- [ ] **Lista pierwszych operacji** (3–5, z co najmniej dwóch narzędzi) —
  PRD 7.2, 11 pkt 4.
- [ ] **Rodzaje danych (`kind`) i formaty plików wynikowych** — PRD W-09,
  11 pkt 8; ARCHITECTURE 3.2.6, 12 pkt 7.
- [ ] **Wartości docelowe**: trafność rozpoznania (W-01), czas odpowiedzi (N-07),
  miary sukcesu — PRD rozdz. 8, 11 pkt 5.
- [ ] **Push repozytorium na `origin`** — decyzja użytkownika.

Implementacja (kolejność wg ARCHITECTURE rozdz. 11):

- [ ] **Szkielet pakietu i konfiguracja** — `pyproject.toml`, `retman/`,
  `tests/conftest.py` (izolacja sieci), `retman.toml` i `retman init`
  (ARCHITECTURE 3.1, 9.1, 9.3; STANDARDS 5–8, 10.4).
- [ ] **Ekstraktor prawdopodobieństwa** z testami wszystkich form z ARCHITECTURE 4.4.
- [ ] **Pozostałe ekstraktory** — współrzędne, liczby z jednostkami, daty,
  stacje, ścieżki, numery wyników (ARCHITECTURE 3.1, 6.1).
- [ ] **Backendy** `basal`, `openai_compatible`, `none` i `FakeDecisionBackend`
  (ARCHITECTURE 3.3, 8.3).
- [ ] **Rdzeń** — pipeline, `Plan`, `dialog`, `Result`, `PlanNotConfirmedError`
  (ARCHITECTURE 2, 6, 7.1, 7.3).
- [ ] **Rejestr operacji, wspólny adapter, `kinds`, `retman-scaffold`**
  (ARCHITECTURE 3.2, 4.1–4.3) — po decyzji o liście operacji.
- [ ] **Przestrzeń robocza, dziennik projektu, ślad audytowy** (ARCHITECTURE 5).
- [ ] **CLI, `retman doctor`, `results`, `log`** (ARCHITECTURE 6.4, 7.1, 7.2).
- [ ] **`retman-eval` i zbiór poleceń testowych** (ARCHITECTURE 8).
- [ ] **CI** — Windows, Linux, macOS; test instalacji; testy handlerów na
  wersjach narzędzi; kontrola rozjazdów (ARCHITECTURE 3.2.7, 9.4).
- [ ] **Pomiary czasu odpowiedzi** (ARCHITECTURE 9.2).

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
