# Instrukcje dla Claude Code

Retman to warstwa poleceń w języku naturalnym (po polsku) dla narzędzi hydrologicznych
(Hydrograf, Kartograf, IMGWTools, Hydrolog, BasicHydraulics): rozpoznaje operację,
dopytuje o braki, pokazuje plan do potwierdzenia i wywołuje publiczne API narzędzia.
Działa jako CLI `retman` i biblioteka Python; model językowy jest osobną usługą
(basal-serve albo serwer zgodny z API OpenAI). Wprowadzenie: `README.md`.

**Stan:** przed v0.1.0 — rdzeń z warstwą komend (podgląd offline planu, sprawdzenie dostępności
na życzenie), jedno CLI `retman <grupa> <czasownik>` (`plan run`, `config`, `doctor check`, `results list`, `journal show`, `commands`, `eval run`, `scaffold`),
backend `openai_compatible` (sprawdzony z Bielikiem 11B w LM Studio) oraz adaptery Kartografa 0.8.0
(4 operacje) i IMGWTools 3.0.0 (26 operacji, rozpoznawanie dwustopniowe); decyzje ADR-001–019;
bieżący stan i backlog w `docs/PROGRESS.md`. Obowiązują `docs/PRD.md` i `docs/ARCHITECTURE.md`.

## Zasady pracy (krytyczne)

Główne źródło konwencji i procesu: `docs/DEVELOPMENT_STANDARDS.md`.

- **Narzędzia nic nie wiedzą o Retmanie** (PRD N-03, ARCHITECTURE 3.2.1): nie edytuj
  repozytoriów Hydrografa, Kartografa, IMGWTools, Hydrologa ani innych narzędzi; Retman
  korzysta wyłącznie z ich publicznego API Pythona (nie przez ich serwery MCP, ADR-018),
  a manifesty, wywołania, klienty, handlery i tłumaczenia mieszkają w `src/retman/tools/<narzędzie>/`.
- **Retman nie zawiera modelu** (N-10, ARCHITECTURE 3.3, 9.3): żadnych bibliotek ML, SDK
  dostawców ani pakietu `basal` w zależnościach; backendy to własne zapytania HTTP.
  Zależności podstawowe: klient HTTP i `platformdirs` (foldery użytkownika).
- **Zawsze potwierdzenie przed wykonaniem** w wersjach 0.x (W-05, ARCHITECTURE 6.3) —
  nie dodawaj ścieżki wykonania bez `plan.confirm()`; `Plan.from_dict` nigdy nie odtwarza
  potwierdzenia.
- **Bez sieci przed potwierdzeniem** (N-12, ARCHITECTURE 3.2.4, 6.5): narzędzia wołamy
  z siecią dopiero po `plan.confirm()`; planowanie (buildery wywołań, podgląd, ekstraktory)
  widzi tylko `PlanView`. Jedyny wyjątek: `retman.check()` po osobnej zgodzie
  `plan.confirm_check()`.
- **Nie zgadywać po cichu** (W-02, ARCHITECTURE 1.1, 5.3, 6.1): liczby wyciąga kod
  (ekstraktory), model wybiera tylko z list; przy niejednoznaczności Retman pyta.
- **Brak ukrytych wartości domyślnych** (N-11, ARCHITECTURE 9.1): `retman config show` pokazuje
  każde ustawienie z wartością i źródłem; model decyzyjny nie ma wartości domyślnych.
- Język (ARCHITECTURE 1.3): kod, identyfikatory, komentarze i docstringi po angielsku;
  teksty dla użytkownika i modelu wyłącznie w plikach tłumaczeń (`pl.toml`);
  dokumentacja po polsku.
- Środowisko przez `uv` (`uv sync --locked --all-extras` instaluje też grupę `tools` z narzędziami
  do testów handlerów), Python ≥ 3.12 (ADR-002), wyłącznie z `.venv` (STANDARDS 6.1); ręczne
  uruchomienia CLI poza repo, testy nie dotykają prawdziwego `nogat.toml` (fixture `user_environment`).
- Testy offline bez GPU i bez serwera modelu: `FakeDecisionBackend`, `FakeToolClient`,
  `-m "not live"` (STANDARDS 6.3, 10.4); bez `conftest.py` w podfolderach `tests/`.
- Bramka przed każdym commitem: `scripts/gate.sh` (uv sync --locked, `ruff format --check`,
  `ruff check`, mypy, pytest offline z pokryciem — razem z zgodnością manifestów z zainstalowanymi
  narzędziami — i kontrola commitów; DEV-7.6). Nie commituj, gdy któryś krok nie przechodzi.
- Końce linii LF we wszystkich plikach, bez wyjątków (STANDARDS 5.5).
- Nie rozstrzygaj sam miejsc `[DO UZUPEŁNIENIA]` ani otwartych kwestii (PRD 11,
  ARCHITECTURE 12) — to decyzje autora; zgłoś je i zapytaj.
- Praca na `develop` (albo gałęzi krótkotrwałej z `develop`); Conventional Commits
  z opisem po polsku (STANDARDS 1–2, 9.4).
- Commity bez stopki `Co-Authored-By`. Autor: `Daldek <git@debever.pl>`.
- Na koniec sesji OBOWIĄZKOWO zaktualizuj `docs/PROGRESS.md` (STANDARDS 15); zmiany dopisuj na bieżąco
  do `docs/CHANGELOG.md`; decyzje projektowe zapisuj w `docs/DECISIONS.md` — każdy plik
  ma na końcu szablon wpisu.
- Zmiana wymagań lub architektury = aktualizacja `docs/PRD.md` / `docs/ARCHITECTURE.md`
  razem z odsyłaczami (`p. X.Y`, `rozdz. N`, `[W-xx]`, `[N-xx]`) w obu plikach.

## Mapa dokumentacji

| Czego szukasz | Gdzie |
|---|---|
| Stan prac, ostatnia sesja, backlog | `docs/PROGRESS.md` |
| Jak się pracuje z Retmanem (CLI, Python, przykłady) | `docs/USAGE.md` |
| Specyfikacje komponentów (np. `retman eval run`), plany, raporty z badań (nazwy `YYYY-MM-DD-<temat>.md`, STANDARDS 7.1) | `docs/specs/`, `docs/plans/`, `docs/research/` |
| Workflow sesji, kolejność lektury | `docs/DEVELOPMENT_STANDARDS.md` 15 |
| Środowisko, komendy testów/lint/mypy/eval, gdzie uruchamiać CLI | STANDARDS 6 |
| Git, commity, język, testy, wyjątki, logging, bezpieczeństwo (zasady) | STANDARDS 1–2, 9–12, 14 |
| Nowa operacja, nowy `kind`, nowy backend (checklisty) | STANDARDS 17 |
| Problem, użytkownicy, scenariusze S-xx | `docs/PRD.md` 1–4 |
| Wymagania funkcjonalne W-xx i niefunkcjonalne N-xx | `docs/PRD.md` 5–6 |
| Zakres wersji, wydania, ryzyka, otwarte kwestie produktowe | `docs/PRD.md` 7, 9–11 |
| Zasady projektowe, język kodu i tekstów | `docs/ARCHITECTURE.md` 1 |
| Przebieg polecenia (kroki ①–⑥) | ARCHITECTURE 2 |
| Moduły pakietu | ARCHITECTURE 3.1 |
| Adaptery narzędzi: manifest, warstwa komend (`calls`, klient, podgląd, sprawdzenie), handler, wspólny adapter, `kind`, wersje, `retman scaffold` | ARCHITECTURE 3.2 |
| Modele: `DecisionBackend`/`TextBackend`, backendy, pewność, ograniczenia basala | ARCHITECTURE 3.3–3.4 |
| Manifest, tłumaczenia, typy parametrów, prawdopodobieństwo, łańcuchy | ARCHITECTURE 4 |
| Przestrzeń robocza, numery wyników, dziennik i ślad audytowy | ARCHITECTURE 5 |
| Dopytywanie, progi pewności, plan, rozmowa w terminalu, kody wyjścia, sprawdzenie dostępności | ARCHITECTURE 6 |
| CLI, API Pythona, `retman doctor check`, `Result`, GUI | ARCHITECTURE 7 |
| Zbiór testowy, miary jakości, `retman eval run`, testy | ARCHITECTURE 8 |
| `nogat.toml` (`[retman]`), zmienne `RETMAN_*`, sprzęt, pakiet, instalacja | ARCHITECTURE 9, ADR-021 |
| Bezpieczeństwo i prywatność | ARCHITECTURE 10 |
| Komponenty w wersjach, otwarte kwestie techniczne | ARCHITECTURE 11–12 |
| Decyzje i ich erraty (indeks na początku pliku) | `docs/DECISIONS.md` |
| Historia zmian per wydanie | `docs/CHANGELOG.md` |

## Odstępstwa od standardu Nogat 2.1 (Deviations)

- **DEV-7.3** — mypy działa w trybie `strict` na `src/` i `tests/`; 36 modułów testowych
  (lista w `[[tool.mypy.overrides]]` w `pyproject.toml`) nie ma adnotacji pomocników i fixtur
  (`disallow_untyped_defs` i pokrewne wyłączone). Nowy moduł testowy jest ścisły; moduł
  schodzi z listy, gdy dostanie adnotacje.
