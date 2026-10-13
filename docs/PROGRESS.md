# PROGRESS — Retman

Bieżący stan prac. Stan gałęzi, tagów i `origin` sprawdzaj w gicie
(`git status`, `git log`, `git ls-remote --tags origin`), nie w tym dzienniku.
Szablony wpisów: [Szablony](#szablony).

## Status projektu

| Element | Status | Uwagi |
|---------|--------|-------|
| Dokumentacja projektowa (PRD, ARCHITECTURE, DEVELOPMENT_STANDARDS, USAGE) | ✅ Gotowy | ADR-001–011; przewodnik `docs/USAGE.md`; otwarte kwestie: PRD rozdz. 11, ARCHITECTURE rozdz. 12 |
| Repozytorium (`main`, `develop`, `origin`) | ✅ Gotowy | `main` i `develop` na `origin` |
| Lista pierwszych operacji v0.1 | 🚧 W toku | Kartograf: 4 operacje (ADR-001); brak operacji drugiego narzędzia (PRD 7.1) |
| Szkielet pakietu, `pyproject.toml`, `retman.toml` i `retman init` | ✅ Gotowy | ARCHITECTURE 3.1, 9.1; Python ≥ 3.12 (ADR-002) |
| Ekstraktory (w tym prawdopodobieństwo) | 🚧 W toku | gotowe: `area`, `crs` (ADR-009), `path`, `result`; brak: prawdopodobieństwo, daty, stacje, liczby z jednostkami |
| Backendy `basal`, `openai_compatible`, `none`; `FakeDecisionBackend` | 🚧 W toku | gotowe: `openai_compatible`, atrapa; `basal` — brak specyfikacji API basal-serve |
| Rdzeń: pipeline, `Plan`, `dialog`, `Result` | ✅ Gotowy | ARCHITECTURE 2, 6, 7.1, 7.3 |
| Rejestr operacji, wspólny adapter, `kinds`, `retman-scaffold` | 🚧 W toku | rejestr, adapter, `kinds` gotowe; `retman-scaffold` nie powstał |
| Przestrzeń robocza, dziennik projektu, ślad audytowy, zbiór poleceń | ✅ Gotowy | ARCHITECTURE 5; dziennik z danymi planu i zbiór za zgodą (ADR-010); `retman collect` — ADR-011, odłożone |
| CLI, `retman doctor`, `results`, `log` | ✅ Gotowy | ARCHITECTURE 6.4, 7.1, 7.2 |
| `retman-eval` i zbiór poleceń testowych | 🚧 W toku | kod gotowy; 83 polecenia (szkic agenta); przebiegi z Bielikiem 11B (`docs/research/2026-10-12-bielik-11b-retman-eval.md`); czeka: przegląd zbioru, progi, strojenie |
| CI (Windows, Linux, macOS; test instalacji; wersje narzędzi) | ⏳ Planowany | ARCHITECTURE 3.2.7, 9.4 |

## Checkpointy

### CP0 — Dokumentacja startowa
- **Data:** 2026-10-11
- **Wersja:** — (przed v0.1.0)
- **Zakres:** PRD, architektura, standardy deweloperskie, szablony DECISIONS/PROGRESS/CHANGELOG, README, CLAUDE.md, licencja MIT, konfiguracja repozytorium; pierwszy commit `70857c0`

## Ostatnia sesja

> **START NASTĘPNEJ SESJI (stan 2026-10-13, koniec sesji):** praca na `develop`
> (na `origin` do `ab8e51d`; commit z 2026-10-13 tylko lokalnie). Ostatni przebieg `retman-eval`
> (Bielik 11B, 83 polecenia): operacja 0,88, W-03 0, W-02 0/189, wartości 0,80, polecenia
> kompletne bez pytań 14/39, mediana planu 10,6 s — `docs/research/2026-10-12-bielik-11b-retman-eval.md`.
> **Do zrobienia, w kolejności:**
> 1. Push `develop` na `origin` — zrobione 2026-10-12.
> 2. Przegląd zbioru `retman/eval/commands.jsonl` przez autora (spec. 10 pkt 2), potem
>    przebieg `--repeat 3` i decyzja o progach (propozycja: operacja ok. 0,70, parametry
>    0,67 — słabo potwierdzone); wpisanie progów do konfiguracji użytkownika.
> 3. Strojenie opisu operacji arkuszy potomnych (6 z 10 błędów operacji) i sprawdzenie
>    przebiegiem.
> 4. Ekstraktor prawdopodobieństwa (ARCHITECTURE 4.4) — wymagany w 0.1.
> 5. `retman-scaffold` (jest w bramce CLAUDE.md, nie istnieje) i CI (Windows/Linux/macOS).
> 6. `retman collect export`/`draft` (ADR-011) — gdy autor zdecyduje o wdrożeniu.
> Decyzje autora: operacja drugiego narzędzia (PRD 7.1), plik geometrii, wartości docelowe
> (PRD W-01, N-07, rozdz. 8), ADR wsteczne dla pierwszej sesji, prefiks „Błąd:” i kod 1
> dla polecenia spoza zakresu w CLI, backend basal (czeka na API basal-serve).
> Do oceny po dodaniu kolejnych narzędzi (nie teraz): łańcuchy jako przepisy autora
> i zastosowania n8n — Backlog, „Do rozważenia”.
> Uwagi: istniejące pliki `retman.toml` wymagają klucza `[privacy] collect_path`; adres
> LM Studio podaje użytkownik — nie zapisywać nigdzie.

### Łańcuchy jako przepisy i miejsce dla n8n — analiza (2026-10-13)

- **Zlecenie użytkownika:** gdzie w Retmanie jest miejsce na n8n i gotowe automatyzacje;
  czy łańcuchy wykonywać deterministycznie (n8n zamiast Retmana lub LLM); przepisy czy
  resolver.
- **Decyzje użytkownika:** bez ADR — przepisy i n8n trafiają do Backlogu („Do
  rozważenia”); ocena po dodaniu kolejnych narzędzi. n8n tylko tam, gdzie Retman nie
  da rady albo własne rozwiązanie byłoby zbyt trudne (także jako nauka technologii).
- **Zrobione:** analiza (ARCHITECTURE 1.2, 4.5, 5.4, 6.3, 7.4–7.5, 10, 11; USAGE 7–12;
  dokumentacja n8n); pozycje Backlogu; otwarta kwestia ARCHITECTURE 12 pkt 14.
  Wnioski: wykonanie i kolejność kroków już są w kodzie (model nie planuje łańcuchów),
  jedyny wpływ modelu na kształt łańcucha to krok 4 resolvera; n8n nie dodaje
  determinizmu, a jako wykonawca rozdzieliłby ślad audytowy (W-15) i zdublował nazwy
  parametrów; W-05 wyklucza wykonanie bez zatwierdzenia przez człowieka.
- **Weryfikacja:** bez zmian w kodzie; nic nie uruchamiano.
- **Otwarte:** ocena przepisów po drugim narzędziu (wszystkie operacje Kartografa mają
  `inputs: []`, więc łańcucha jeszcze nie ma); czy zatwierdzenie planu w innym kanale
  (mail, komunikator przez n8n) spełnia W-05 — decyzja autora.

### Dziennik z danymi planu i zbiór poleceń — ADR-010 (2026-10-12)

- **Zlecenie użytkownika:** uzupełnić dziennik (decyzje modelu dla planów niewykonanych,
  wartości jako dane, zdarzenie „poza zakresem”, zmieniana wartość); `collect_commands`
  jako zbieranie poleceń w jednym miejscu, wyłączone domyślnie, z pytaniem w `retman init`.
- **Zrobione:** zdarzenie `plan` z `values`/`inputs`/`questions`/`decisions`/`changed`,
  zdarzenie `out_of_scope`; `retman/core/collection.py`; `[privacy] collect_path`
  (ścieżka wpisana przez `retman init`, `default_collect_path`); pytanie o zgodę w
  `retman init` (terminal; bez terminala `false`); zbiór pomija `retman-eval`; testy
  (dziennik dla planów niewykonanych, poza zakresem, zbiór wyłączony/włączony, konfiguracja);
  ADR-010, ARCHITECTURE 5.4, 9.1, rozdz. 10, USAGE 1.3 i 6.3–6.4, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 215 passed; ruff, mypy czyste. Smoke CLI:
  `retman init` w terminalu (odpowiedź „t”) → `collect_commands = true` i pełna ścieżka;
  bez terminala → `false`; polecenie z odpowiedzią i odrzuceniem → wpis w zbiorze
  i w dzienniku z decyzjami modelu (format 0,72) i wartościami ze źródłami.
- **Otwarte:** przekazanie zbioru i szkic wpisów `retman-eval` — rozstrzygnięte w ADR-011
  (droga A: eksport i wysyłka ręczna, formularz z uploadem do rozważenia; `retman collect
  export` i `retman collect draft`), wdrożenie odłożone przez autora.

### Układ wyniku rozpoznawany w kodzie — ADR-009 (2026-10-12)

- **Zlecenie użytkownika:** rozpoznawanie układu wyniku w kodzie, droga A (niejasne →
  pytanie, bez modelu); odporność na brak polskich znaków i literówki.
- **Zrobione:** `retman/extractors/crs.py` (`extract_crs` z rolą wzmianki: po prostokącie /
  słowa „wynik”, „do”, „przelicz”… / niezgodność z układem liczb; `read_crs_answer` dla
  odpowiedzi; normalizacja znaków z `ł`; jedna literówka w słowach ≥ 5 liter);
  `ANSWER_EXTRACTORS`; schemat manifestu: `choice` z `extractor` i `option_values`
  (walidacja; teksty modelu niewymagane); pipeline: `_extracted_choice` i odpowiedź
  bez modelu, komunikaty `dialog.several_values`/`unsupported_value`; Kartograf
  `target_crs` z ekstraktorem, usunięte teksty modelu; testy ekstraktora (role, literówki,
  odpowiedzi), pipeline (bez modelu, prostokąt ≠ wynik, nieobsługiwany kod, odpowiedź
  „2180”/„4326”), walidacji; zbiór: `kartograf-cutout-020`–`023`; ADR-009, ARCHITECTURE
  3.1 i 4.3, USAGE, CHANGELOG, raport w `docs/research/`.
- **Weryfikacja:** `pytest -m "not live"` — 209 passed, `crs.py` 96%; ruff, mypy czyste.
  `retman-eval` z Bielikiem 11B (83 polecenia): W-02 0/189, ciche zgadywanie 0,
  `target_crs` 23/23 zgodnie z oczekiwaniem, pokrycie poleceń kompletnych 14/39. Adres
  serwera nie trafił do repo.

### Osobne pytanie dla modelu — ADR-008 (2026-10-12)

- **Zlecenie użytkownika:** wdrożenie pkt 1 z propozycji poprawy rozpoznawania (osobne
  pytanie dla modelu).
- **Zrobione:** `model_question` dla parametrów `choice`/`bool` (walidacja manifestu,
  pipeline: decyzja z polecenia i z odpowiedzi własnymi słowami); teksty w
  `retman/tools/kartograf/pl.toml` i w fixture; testy (pipeline: model dostaje
  `model_question`, użytkownik `question`; walidacja: brak `model_question` = błąd);
  ADR-008, ARCHITECTURE 3.3.1 i 4.2, STANDARDS 17.1, CHANGELOG, raport w `docs/research/`.
- **Weryfikacja:** `pytest -m "not live"` — 179 passed; ruff, mypy czyste. Pełny
  `retman-eval` z Bielikiem 11B: parametry 0,55 → 0,78, pytania zbędne 66 → 30, pokrycie
  poleceń kompletnych 6/36 → 11/36, W-02 2 → 1, `product` 16/33 → 32/33; operacja bez
  zmian (0,89). Adres serwera nie trafił do repo; konfiguracja tymczasowa usunięta.

### Przebieg `retman-eval` z Bielikiem 11B (2026-10-12)

- **Zlecenie użytkownika:** test działania z Bielikiem; przebieg roboczy na szkicu zbioru.
- **Zrobione:**
  - `retman doctor` z LM Studio (`bielik-11b-v3.0-instruct-mlx`): wszystko ✓, pytanie
    testowe pewność 1,00 z logprobs;
  - `retman-eval --target-error 0.01` (79 poleceń, ok. 14 min); analiza
    `docs/research/2026-10-12-bielik-11b-retman-eval.md`, raport narzędzia
    `…-raport.md`;
  - eksperyment z neutralnymi opisami `unspecified` — gorzej dla `product`/`format`,
    teksty przywrócone;
  - `retman/eval/metrics.py`: lista „Błędne przypadki” bez wartości zapytanych i bez
    parametrów zależnych od niezapytanego (miary bez zmian); test zaktualizowany.
- **Wynik:** operacja 0,89, W-03 0 naruszeń, W-02 2/137 (ciche zgadywanie `target_crs`
  z kodu prostokąta wejściowego, pewność 0,93–0,94), `product` 16/33 (model wybiera
  „nie podano” mimo NMT/DSM), pokrycie poleceń kompletnych 6/36, mediana planu 11 s.
  Zalecane progi: operacja 0,70, parametry 0,94 (niepotwierdzone, < 100 decyzji).
- **Weryfikacja:** `pytest -m "not live"` — 179 passed; ruff, mypy czyste; adres serwera
  nie występuje w repo (grep); konfiguracja tymczasowa usunięta.

### Kod EPSG bez prefiksu (2026-10-12)

- **Zlecenie użytkownika:** Retman ma rozpoznawać kod EPSG także jako samą liczbę
  z kontekstu (`2180` zamiast `EPSG:2180`).
- **Ustalenia:** prostokąt (ekstraktor `area`) już wcześniej nie zależał od zapisu
  `EPSG:` — układ wynika z zakresu liczb; same `2180`/`3045` nie są czytane jako TERYT ani
  współrzędna (sprawdzone). Kod EPSG w poleceniu dotyczy więc tylko wyboru `target_crs`,
  który robi model z kontekstu (prostokąt wejściowy vs wynik).
- **Zrobione:** opisy opcji `target_crs` dla modelu z samym kodem (`EPSG:2180, kod 2180 —
  …`), opis `unspecified` odróżnia układ prostokąta wejściowego od układu wyniku, `help`
  pytania mówi, że kod można podać samą liczbą; w zbiorze `retman-eval`
  `kartograf-cutout-016`–`019` (kody bez prefiksu, w tym przypadek dwuznaczny „w układzie
  2180” → pytanie); USAGE 9, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 179 passed (walidacja zbioru z nowymi wpisami).
  Bez przebiegu na modelu — skuteczność zmierzy `retman-eval` na nowych wpisach.
- **Otwarte:** jeśli Bielik nie będzie trafnie wiązał samych kodów, alternatywą jest
  rozpoznawanie kodu w kodzie (ekstraktor z regułami kontekstu „wynik/do/przelicz”) —
  decyzja po przebiegu `retman-eval`.

### Przewodnik `docs/USAGE.md` (2026-10-12)

- **Zlecenie użytkownika:** opis sposobu pracy z Retmanem z przykładami.
- **Zrobione:**
  - `docs/USAGE.md` (przygotowanie, folder projektu, polecenia, pytania, plan i `z`,
    wykonanie, `results`/`log`/`result.json`, sesja, opcje, praca bez terminala, kody
    wyjścia, operacje Kartografa i formy obszaru, API Pythona, `retman doctor`,
    `retman-eval`, ograniczenia); odsyłacze w README i CLAUDE.md, CHANGELOG;
  - poprawki znalezione przy nagrywaniu przykładów: podwójne „np. np.” w podpowiedziach
    (`example` w `retman/tools/kartograf/pl.toml` i `dialog.example_path` bez „np.” — dodaje
    je `cli.example`); `retman results` powtarzał numer wyniku (`cli.results_line` =
    samo podsumowanie).
- **Weryfikacja:** przykłady CLI nagrane prawdziwym `retman.cli.main` z atrapą modelu
  (`FakeDecisionBackend`) w folderze tymczasowym (usunięty); wycinek NMT 100 × 100 m
  pobrany z GUGiK naprawdę (GeoTIFF, `result.json`, `results`, `log`); przykłady API
  Pythona (`plan`/`answer`/`PlanNotConfirmedError`/`to_dict`/`from_dict`/`known`)
  uruchomione; formy obszaru sprawdzone ekstraktorem; `pytest -m "not live"` — 179 passed.

### Nazwy specyfikacji i planów z datą (2026-10-12)

- **Decyzje użytkownika:** specyfikacje i plany (oraz raporty z badań) mają w nazwie datę
  `YYYY-MM-DD` — reguła w STANDARDS 7.1 i mapie dokumentacji w CLAUDE.md.
- **Zrobione:** `docs/specs/retman-eval.md` → `docs/specs/2026-10-11-retman-eval.md`
  (data z nagłówka specyfikacji); odsyłacze w CHANGELOG, DECISIONS (ADR-006), PROGRESS,
  STANDARDS 6.4. `docs/research/` już spełniał regułę; `docs/plans/` jeszcze nie istnieje.

### `retman doctor` (2026-10-12)

- **Zlecenie użytkownika:** przejście do `retman doctor`.
- **Zrobione:**
  - `retman/doctor.py` (`run_doctor` → `DoctorReport`: tekst jak w ARCHITECTURE 7.2 i
    `--json`), polecenie `retman doctor [--json]` w CLI; teksty `[doctor]` w
    `retman/i18n/pl.toml`;
  - sekcje: konfiguracja (plik, projekt, zapis, liczba wyników, nieczytelne `result.json`),
    model decyzyjny (adres, `GET /models`, pytanie testowe NMT vs pogoda, pewność, progi),
    narzędzia (wersja na tle zakresu, liczba operacji, `[adapters] enabled`, polecenie
    doinstalowania), tłumaczenia, model tekstowy;
  - kod 1 tylko przy problemach blokujących: błąd konfiguracji, model niedostępny albo
    pytanie testowe zakończone błędem, brak dostępnych operacji, błędne tłumaczenia;
    błędna odpowiedź na pytanie testowe, model spoza listy serwera, brak pewności,
    nieczytelne wyniki — ostrzeżenia;
  - pole `source` w manifeście (wymagane, walidowane) do podpowiedzi `uv … --with`
    (ARCHITECTURE 4.1); Kartograf: `git+https://github.com/Daldek/Kartograf`;
  - testy `tests/test_doctor.py` (13), CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 179 passed; ruff, mypy czyste. Smoke CLI poza
  repo: konfiguracja z szablonu (`basal`) → backend niedostępny, kod 1; brak pliku →
  podpowiedź `retman init`, kod 1; `openai_compatible` na lokalnym serwerze testowym
  (stdlib HTTP) → model na liście, poprawna odpowiedź, ostrzeżenie o `confidence = "none"`,
  kod 0; po zatrzymaniu serwera → „serwer modelu nie odpowiada” z podpowiedzią, kod 1.
  Bez prawdziwego LM Studio.

### `retman-eval` (2026-10-12)

- **Zlecenie użytkownika:** implementacja `retman-eval` po akceptacji specyfikacji.
- **Decyzje użytkownika:** specyfikacja `docs/specs/2026-10-11-retman-eval.md` przyjęta bez zmian.
- **Zrobione:**
  - `OutOfScopeError(RetmanError)` z `operations` (spec. 7); CLI bez zmian (nadal „Błąd:”
    i kod 1 — decyzja autora);
  - `retman/eval/dataset.py` (wczytanie i walidacja wpisów, spec. 2.2, manifesty wszystkich
    narzędzi z `retman/tools/`), `runner.py` (CLI, izolacja w katalogu tymczasowym, licznik
    zapytań do modelu), `metrics.py` (spec. 5), `report.py` (teksty w `[eval]`
    `retman/i18n/pl.toml`); skrypt `retman-eval` w `pyproject.toml`;
  - szkic zbioru: 4 × 15 poleceń Kartografa, 10 `out_of_scope`, 5 `near_miss`; tagi:
    formal 31, colloquial 20, typo 10, incomplete 23, ambiguous 4, complete 33;
  - testy `tests/eval/` (walidacja zbioru i reguły budowy 2.3, miary, krzywa progów,
    izolacja, brak adresu w rekordach) + test `live`;
  - ARCHITECTURE 3.1 (moduły `eval/`), status specyfikacji, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 166 passed, pokrycie 89% (`eval/` 86–99%);
  ruff, mypy czyste. Smoke: `retman-eval` (`main`) na całym zbiorze z
  `FakeDecisionBackend` wybierającym zawsze NMT dla arkusza → raport z wszystkimi
  sekcjami, 75 rekordów, kod 4 (15 naruszeń W-03), brak plików poza katalogiem
  tymczasowym. Przebiegu na modelu nie było.
- **Do przeglądu w zbiorze:** `kartograf-hierarchy-006/-007` (godła PL-2000 i dostępność
  skali zależą od pokrycia GUGiK), `kartograf-cutout-008/-009/-015`,
  `kartograf-bdot-011` (kolejność osi PL-1992 → pytanie), `kartograf-bdot-015` (pytanie
  o format zostawia go nieokreślonym), `near-005` (przycięcie ortofotomapy do wielokąta).

### Etykiety i opisy opcji (2026-10-12)

- **Zlecenie użytkownika:** stan prac; pytanie, dlaczego `pl.toml` obok NMT wymienia DEM
  i „rzeźbę terenu”.
- **Decyzje użytkownika:** opcje rozdzielone jak operacje — `label` dla użytkownika,
  `description` z synonymami i nazwami angielskimi dla modelu, bo w praktyce używa się
  angielskich nazw i skrótów (ADR-007).
- **Zrobione:**
  - `core/pipeline.py`: pytania i plan pokazują `options.<klucz>.label`; model dostaje
    `options.<klucz>.description` (także `unspecified`) — przy poleceniu i przy odpowiedzi
    własnymi słowami; odpowiedź na pytanie o operację model dopasowuje do `description`
    operacji, nie do `label`;
  - `registry/manifest.py`: walidacja wymaga `label` i `description` każdej opcji
    oraz `unspecified.description`;
  - `retman/tools/kartograf/pl.toml`: krótkie etykiety opcji; w opisach dodane DTM,
    orthophoto, PUWG 1992, UTM 33N, Křovák, poziom odniesienia Amsterdam, GPKG/SHP;
  - testy: `test_choice_options_show_labels_and_offer_descriptions_to_model`, przypadek
    opcji z jednym tekstem w `test_validate_manifest_reports_missing_language_option_and_example`;
    fixture `dummy_tool/pl.toml` w nowym schemacie;
  - dokumentacja: ADR-007, ARCHITECTURE 4.2, STANDARDS 17.1, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 143 passed; `ruff check`, `ruff format
  --check`, `mypy retman/ tests/` czyste. Smoke (skrypt z `FakeDecisionBackend`
  na prawdziwych tekstach Kartografa): pytanie pokazuje „1 m”, „5 m (tylko EVRF2007)”,
  plan „Rozdzielczość NMT: 1 m”, model dostał opisy z „NMT/DEM”. Bez modelu na żywo —
  wpływ synonimów na trafność zmierzy `retman-eval`.
- **Przegląd `pl.toml`:** autor zaakceptował treść Kartografa (etykiety, synonimy,
  pytania, `help`, `example`) bez zmian.

### Pionowy przekrój na Kartografie 0.7.2 (2026-10-11)

- **Zlecenie użytkownika:** kontynuacja prac; Kartograf v0.7.2 jako pierwsze narzędzie
  do testowania możliwości Retmana.
- **Decyzje użytkownika:** operacje Kartografa i formy obszaru (ADR-001); Python ≥ 3.12
  (ADR-002); zakres `>=0.7.2,<0.8` i grupa `tools` z tagiem Git (ADR-003); osobny `kind`
  na produkt (ADR-004); kolejność sesji: szkielet + konfiguracja, potem przekrój
  Kartografa; operacje Kartografa bez wartości domyślnych — Retman dopytuje (ADR-006);
  `retman-eval`: na razie LM Studio (basal-serve niedostępny), zbiór jako szkic agenta,
  kod 0 poza naruszeniem W-03 (kod 4), ARCHITECTURE 8 bez zmian (specyfikacja rozdz. 10).
  Adresu serwera LM Studio i ścieżki przestrzeni roboczej agenta nie wolno zapisywać
  w żadnym pliku.
- **Zrobione:**
  - `pyproject.toml`, `.venv` przez `uv` (zainstalowany w `~/.local/bin`), konfiguracja
    ruff (bez plików `.md` — przykłady „BAD” w dokumentacji), mypy, pytest, coverage;
  - `config.py` + szablon, `exceptions.py`, loader tłumaczeń, izolacja sieci w testach;
  - ekstraktory `area`/`path`/`result`; backend `openai_compatible` + `FakeDecisionBackend`;
    `kinds.py`; `retman/tools/kartograf/` (manifest, handlery, `pl.toml`); rejestr,
    adapter, pipeline, plan, dialog, workspace, journal, CLI (subagenci, integracja
    i poprawki w tej sesji);
  - poprawki po smoke: decyzja z `logprobs` = najbardziej prawdopodobna opcja, nie
    wylosowany token (`27c6864`); niska pewność przy `unspecified` → pytanie zamiast
    wartości domyślnej; `label` operacji dla użytkownika oddzielony od `description`
    dla modelu; plan pokazuje odczyt prostokąta jako N/E;
  - badanie LM Studio: `docs/research/2026-10-11-lm-studio-openai-compatible.md`
    (ARCHITECTURE 12 pkt 9);
  - specyfikacja `docs/specs/2026-10-11-retman-eval.md`; manifest Kartografa bez `default` (ADR-006);
  - dokumentacja: ADR-001–006, PRD 7.2, ARCHITECTURE 3.1, 3.2.6, 4.1–4.3, 9.2–9.3, 12,
    STANDARDS 5.1, 6.1, 8.1, README, CLAUDE.md, CHANGELOG.
- **Weryfikacja:** `pytest -m "not live"` — 142 passed, pokrycie 88% (rdzeń ≥ 84%);
  `pytest -m live` — 6 passed (5 handlerów Kartografa na GUGiK, 1 Bielik 11B);
  `ruff check`, `ruff format --check`, `mypy retman/ tests/` czyste. Smoke CLI
  w folderze projektu poza repo z Bielikiem 11B: NMT 5 m dla N-34-130-D-d-2-4 →
  `ok=False` (GUGiK nie ma 5 m dla arkusza, komunikat Kartografa, exit 1); wycinek NMT dla
  prostokąta WGS84 → GeoTIFF EPSG:2180 1 m, 573×561, 77–90 m (Poznań), exit 0; sesja:
  BDOT10k TERYT 2264 z `z` (zmiana na SHP) → 58 plików `.shp`, `koniec` exit 0;
  polecenie spoza zakresu → lista operacji; bez TTY → exit 2; `results`, `log` działają.
- **Otwarte:**
  - **plik geometrii (SHP/GPKG)**: ekstraktor go rozpoznaje, ale żadna operacja Kartografa
    go nie przyjmuje — `download_pl_cutout(geometry=)` w 0.7.2 jest nieaktywny, a publiczne
    API nie ma funkcji zwracającej prostokąt geometrii (potrzebna np.
    `get_overall_bbox(path, layer=None, target_crs=...)` w `__all__` Kartografa) —
    decyzja autora;
  - backend `basal`: brak specyfikacji API basal-serve i serwera do nagrania fixtur;
    konfiguracja z `backend = "basal"` kończy się komunikatem `backend_unavailable`;
  - Qwen w LM Studio nieprzetestowany (serwer odmówił załadowania — zasoby);
  - `retman-scaffold --check` z bramki (CLAUDE.md) jeszcze nie istnieje;
  - polecenie spoza zakresu jest wypisywane z prefiksem „Błąd:” i kończy się kodem 1 —
    do przemyślenia przy `retman-eval`/UX;
  - Kartograf przy folderze projektu na udziale CIFS zgłasza „database is locked” dla
    cache metadanych w folderze wyniku i pracuje bez cache (zachowanie Kartografa).

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
    `<github-user>` w ARCHITECTURE zastąpione adresami `github.com/Daldek/…`;
  - wpis sesji, CP0 i backlog w PROGRESS, sekcja `[0.1.0] - Unreleased`
    w CHANGELOG (commit `8c7657c`);
  - instrukcja założenia repozytorium (`gh repo create` albo github.com/new
    bez README/licencji) — `gh` nie jest zainstalowany na maszynie agenta;
    repozytorium założył i wypchnął użytkownik.
- **Weryfikacja:** odsyłacze `p.`/`rozdz.`/`[W-xx]`/`[N-xx]`/`S-xx` sprawdzone
  skryptem subagenta (brak martwych); brak odwołań do `DESIGN`;
  `git ls-files --eol` bez `w/crlf`; `git ls-remote --heads origin` —
  tylko `develop` (`8c7657c`).
- **Otwarte:** decyzje z Backlogu; push `main`; czy zapisać decyzje
  z tej sesji jako ADR-001… w `docs/DECISIONS.md` (pytanie bez odpowiedzi).
  Override modelu subagentów (`task` → rola `slow`) był tylko na tę sesję,
  niezapisany.

## Backlog

#### Do 0.1.0

Decyzje autora (blokują część implementacji):

- [ ] **Operacja drugiego narzędzia** (PRD 7.1: z co najmniej dwóch narzędzi) —
  Kartograf ustalony w ADR-001; PRD 7.2, 11 pkt 4.
- [x] **Rodzaje danych dla Kartografa** — ADR-004, ARCHITECTURE 3.2.6; pozostałe
  narzędzia otwarte (PRD 11 pkt 8; ARCHITECTURE 12 pkt 7).
- [ ] **Plik geometrii jako obszar** — potrzebna publiczna funkcja Kartografa
  (prostokąt geometrii) albo inna decyzja autora (wpis sesji 2026-10-11, „Otwarte”).
- [ ] **Wartości docelowe**: trafność rozpoznania (W-01), czas odpowiedzi (N-07),
  miary sukcesu — PRD rozdz. 8, 11 pkt 5.
- [x] **Push `main` na `origin`** — `main` na `origin` (`70857c0`).
- [ ] **ADR dla decyzji z pierwszej sesji 2026-10-11** (lista we wpisie „Start projektu”) —
  czy zapisywać wstecznie w `docs/DECISIONS.md`.

Implementacja (kolejność wg ARCHITECTURE rozdz. 11):

- [x] **Szkielet pakietu i konfiguracja** — `pyproject.toml`, `retman/config.py`,
  `tests/conftest.py`, `retman init` (sesja 2026-10-11, przekrój Kartografa).
- [x] **`retman doctor`** (ARCHITECTURE 7.2) — sesja 2026-10-12.
- [ ] **`retman-eval` i zbiór poleceń testowych** — kod gotowy (sesja 2026-10-12);
  pierwszy przebieg Bielik 11B (2026-10-12, `docs/research/`); czeka przegląd zbioru,
  strojenie opisów i decyzja o progach (ARCHITECTURE 6.2, 8; spec. rozdz. 9).
- [ ] **Ekstraktor prawdopodobieństwa** z testami wszystkich form z ARCHITECTURE 4.4.
- [ ] **Pozostałe ekstraktory** — współrzędne punktu, liczby z jednostkami, daty,
  stacje (ARCHITECTURE 3.1, 6.1); gotowe: `area`, `crs` (ADR-009), `path`, `result`.
- [ ] **Backend `basal`** — po uzyskaniu specyfikacji API basal-serve i serwera do
  nagrania fixtur (ARCHITECTURE 3.3, STANDARDS 10.4).
- [x] **Backend `openai_compatible` i `FakeDecisionBackend`** (ARCHITECTURE 3.3, 8.3).
- [x] **Rdzeń** — pipeline, `Plan`, `dialog`, `Result`, `PlanNotConfirmedError`.
- [x] **Rejestr operacji, wspólny adapter, `kinds`** (ARCHITECTURE 3.2, 4.1–4.3).
- [ ] **`retman-scaffold`** — szkice i kontrola rozjazdów (ARCHITECTURE 3.2.3); jest
  w bramce CLAUDE.md, a jeszcze nie istnieje.
- [ ] **`retman collect export` i `retman collect draft`** (ADR-011) — wdrożenie odłożone
  przez autora; zakres i reguły szkicu w ADR-011.
- [x] **Przestrzeń robocza, dziennik projektu, ślad audytowy** (ARCHITECTURE 5).
- [x] **CLI, `results`, `log`, `init`** (ARCHITECTURE 6.4, 7.1).
- [ ] **CI** — Windows, Linux, macOS; test instalacji; testy handlerów na
  wersjach narzędzi; kontrola rozjazdów (ARCHITECTURE 3.2.7, 9.4).
- [ ] **Pomiary czasu odpowiedzi** (ARCHITECTURE 9.2) — z `retman-eval` (Bielik 11B, LM
  Studio w sieci lokalnej): mediana planu 10,6 s, P90 11,8 s, ok. 3,7 s na zapytanie;
  wartość docelowa N-07 nieustalona.

#### Do rozważenia (ocena po dodaniu kolejnych narzędzi)

Propozycje z sesji 2026-10-13, bez ADR; autor ocenia je, gdy będą łańcuchy do sprawdzenia.

- [ ] **Łańcuchy jako przepisy autora zamiast resolvera w trakcie pracy** (alternatywa
  dla ARCHITECTURE 4.5; PRD W-12, S-05). Przepis pisze autor (kod + wiedza dziedzinowa):
  lista kroków, powiązania wyjście→wejście (`kind`), jawne źródło każdego parametru
  (polecenie, pytanie, wcześniejszy krok, wartość stała widoczna w planie ze źródłem
  `recipe` — nowe źródło w ARCHITECTURE 5.4, wymóg N-11), kontrole między krokami
  (ARCHITECTURE 12 pkt 6); teksty w `pl.toml`. Model wybiera przepis z listy (jak
  operację), pytania z wszystkich kroków naraz, jeden plan do zatwierdzenia (W-05).
  Logika resolvera nie planuje w trakcie pracy, tylko pomaga: `retman recipes draft
  <operacja>` (szkic przepisu), `retman recipes check` (operacje i wersje narzędzi,
  zgodność `kind`, źródło każdego parametru, brak cykli, kolejność wg zależności,
  komplet tłumaczeń — do bramki obok `retman-scaffold --check`), `retman recipes show`
  (opis po polsku i diagram mermaid do przeglądu). Testy: plan z `FakeDecisionBackend`,
  wpisy w `commands.jsonl` z oczekiwanym przepisem, test `live` na małym obszarze.
  Zysk: każdy wykonywany łańcuch przejrzany przez specjalistę, znika wybór modelu
  w kroku 4 resolvera. Koszt: każdy łańcuch trzeba dopisać; polecenie bez przepisu →
  odmowa z listą możliwości (W-03). Przy przyjęciu: ADR, ARCHITECTURE 1.2, 3.1, 4.5,
  5.4, 11; PRD W-12; STANDARDS 17 (checklista „nowy przepis”).
- [ ] **n8n jako otoczenie Retmana, nie wykonawca kroków** — kryterium autora: tylko tam,
  gdzie Retman nie da rady albo własne rozwiązanie byłoby zbyt trudne. Nie dla n8n:
  przepisy, kolejność i wykonanie kroków (ślad audytowy W-15 w jednym miejscu, jedno
  źródło nazw parametrów, testy offline). Możliwe zastosowania (n8n na własnym serwerze —
  ARCHITECTURE 10; licencja Sustainable Use, przepływy poza pakietem, np. `examples/n8n/`):
  1. monitoring `retman doctor --json` z alertem przy kodzie 1 — możliwe już teraz;
  2. kontrola jakości przy nowej wersji narzędzia lub modelu: `retman-eval`, porównanie
     z poprzednim raportem, alert przy kodzie 4 (W-03) — możliwe już teraz;
  3. rejestr obliczeń: `result.json` i `journal.jsonl` do arkusza lub bazy (tylko odczyt;
     treść poleceń przy `journal_commands = true`) — możliwe już teraz;
  4. przyjmowanie zleceń (mail, formularz, Teams) i zatwierdzanie planu w tym samym
     kanale — po API HTTP (v0.4) i decyzji, czy taki kanał spełnia W-05;
  5. partie z listy (godła, TERYT) z wartościami `known` — wymaga decyzji o jednym
     zatwierdzeniu dla wielu planów;
  6. ponowne wykonanie zapisanego planu (`retman rerun #N`, ARCHITECTURE 5.5) — bez
     modelu, z zatwierdzeniem.
  Ułatwienia po stronie Retmana (dla każdego orkiestratora): `--json` dla planu w CLI
  (dziś tylko `doctor`; `plan.to_dict()` istnieje), zapis planu do pliku i wykonanie
  zatwierdzonego planu z wpisem w dzienniku (ARCHITECTURE 7.4, wariant A), API HTTP
  z krokami `plan`/`answer`/`confirm`/`execute` i webhookiem po zakończeniu (v0.4).
  Węzeł Execute Command w n8n od 2.0 jest domyślnie wyłączony — lepsza droga przez HTTP.
  Opcjonalny wykonawca `n8n` (zatwierdzony plan na webhook, kroki wołają Retmana przez
  API HTTP) — tylko jeśli pkt 1–4 pokażą potrzebę.

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
