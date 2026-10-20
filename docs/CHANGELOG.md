# Changelog

Wszystkie istotne zmiany w projekcie są dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
Szablon wydania — nowe wydanie dodawaj nad poprzednimi; puste podsekcje pomijaj.
Zmiany w trakcie cyklu trafiają do sekcji `## [X.Y.Z] - Unreleased`, która przy
wydaniu dostaje datę. Każda pozycja: co się zmieniło z punktu widzenia użytkownika,
z odsyłaczem (ADR-XXX, PRD W-xx, ARCHITECTURE p. X.Y).

## [X.Y.Z] - RRRR-MM-DD

### Zmiany łamiące (BREAKING)

- ...

### Dodane

- ...

### Zmienione

- ...

### Usunięte

- ...

### Naprawione

- ...

### Przejście z X.Y.Z

- ...

Linki porównań na końcu pliku, od najnowszego:

[X.Y.Z]: https://github.com/Daldek/Retman/compare/vX.Y.W...vX.Y.Z
[0.1.0]: https://github.com/Daldek/Retman/releases/tag/v0.1.0
-->

## [0.1.0] - Unreleased

### Dodane

- Dokumentacja projektu: wymagania produktowe (`docs/PRD.md`), architektura
  (`docs/ARCHITECTURE.md`), standardy deweloperskie
  (`docs/DEVELOPMENT_STANDARDS.md`), rejestr decyzji, dziennik postępu
  i ten changelog; `README.md`, `CLAUDE.md`, licencja MIT.
- Pakiet `retman` (Python ≥ 3.12, ADR-002) z zależnością podstawową `httpx` (ADR-005).
- Plik centralny `retman.toml`: szablon z komentarzami, `retman init`, walidacja
  wszystkich ustawień naraz; progi `"auto"` odrzucane poza backendem basal
  (ARCHITECTURE 6.2, 9.1).
- Cztery operacje Kartografa 0.8.0 (ADR-001, ADR-012, ADR-013): NMT dla arkusza albo pliku
  geometrii (wszystkie siatki ASC: 0,15; 0,5; 0,6; 1; 5; 10 m oraz 100 m jako ZIP
  województwa), arkusze potomne NMT/NMPT/ortofotomapy (NMPT 0,5; 0,6; 1 m z układem
  wysokościowym; ortofotomapa RGB, CIR albo B-W), wycinek NMT/NMPT 1 m dla prostokąta albo
  pliku geometrii, BDOT10k dla powiatu, arkusza, prostokąta albo pliku geometrii, w
  GeoPackage albo Shapefile.
- Wszystkie operacje IMGWTools 3.0.0 z ČHMÚ — 26 operacji w 6 kategoriach: wyszukiwanie
  i katalog stacji, dane bieżące i ostrzeżenia, PMAXTP, szeregi stacji, archiwa i magazyn,
  projekty danych (ADR-017, PRD 7.2).
- Rozpoznawanie dwustopniowe (kategoria, potem operacja), gdy operacji jest więcej niż 9
  (ADR-017, ARCHITECTURE 3.4).
- Ekstraktory: stacja (offline z katalogu magazynu IMGW), lata, okres, rodzaj roku
  (kalendarzowy/hydrologiczny — zawsze pytanie, gdy niepodany), punkt (WGS84 i PL-1992),
  komórka siatki PMAXTP, prawdopodobieństwo, czas trwania, zmienne, nazwa zadania; plik
  geometrii SHP/GPKG jako obszar z pytaniem o warstwę GeoPackage (ADR-016, ADR-017).
- Rodzaje danych `dem`, `dsm`, `orthophoto`, `topographic_vector`, `dem_archive`,
  `area_geometry` i 13 rodzajów IMGWTools, z walidacją per rodzaj (ADR-004, ARCHITECTURE
  3.2.6).
- Podgląd planu offline: każde wywołanie sprawdza walidacja narzędzia przed potwierdzeniem,
  a odrzucona wartość wraca jako pytanie; wiersze podglądu (np. liczba arkuszy) w planie
  (ADR-014, PRD N-12).
- Sprawdzenie dostępności jako osobny krok: odpowiedź `s` w planie, własna zgoda, raport
  bez pobierania i bez numeru wyniku; `Retman.check()`, `plan.confirm_check()` (ADR-014,
  PRD W-17, ARCHITECTURE 6.5).
- Magazyny narzędzi w `[tools.kartograf]` i `[tools.imgwtools]`; `retman init` tworzy
  sąsiednie foldery, sprawdza dowiązania twarde i za zgodą inicjuje magazyn IMGW; wyniki
  wskazują pliki magazynu ścieżką i SHA-256 (ADR-015).
- `retman doctor`: magazyny, dowiązania twarde w obu magazynach, sonda zapisu IMGW
  (`--deep`), lekka kontrola zgodności manifestów z zainstalowanymi narzędziami.
- `retman-scaffold list | draft | --check`: szkice manifestów z katalogów narzędzi i
  kontrola rozjazdów przez walidację narzędzia offline, z kontrolą pokrycia opcji (ADR-019).
- Zbiór `retman/eval/commands.jsonl`: 614 poleceń (Kartograf, IMGWTools, spoza zakresu
  i bliskie zakresowi), z walidacją wpisów na tym samym kodzie ekstraktorów co planowanie;
  pliki geometrii zastępcze i katalog stacji offline przy planowaniu zbioru (ARCHITECTURE 8.1).
- Parametry nieobowiązkowe, których polecenie nie podało, mają w planie wiersz z tym, co oznacza
  ich brak (np. „wszystkie rodzaje stacji”), można je zmienić odpowiedzią `z`, a `result.json`
  zapisuje je w `unset` (N-11, ARCHITECTURE 6.3).
- Wiele uwag narzędzia o tym samym kodzie w jednym wywołaniu: wynik pokazuje pierwsze trzy
  i liczbę pozostałych; pełna lista zostaje w `tool_*.json` (ARCHITECTURE 4.2).
- Ekstraktory obszaru (godło PL-1992/PL-2000, prostokąt z rozpoznaniem układu i kolejności
  osi, kod TERYT, plik geometrii), ścieżek i numerów wyników; zapisy niejednoznaczne
  wywołują pytanie (ARCHITECTURE 6.1).
- Backend decyzyjny `openai_compatible` (np. LM Studio): wymuszony format odpowiedzi,
  pewność z `logprobs` albo ze zgodności kilku odpowiedzi (ARCHITECTURE 3.3.3).
- Rdzeń: rozpoznanie operacji, dopytywanie (jedno pytanie naraz, odpowiedź numerem albo
  własnymi słowami), plan ze źródłem każdej wartości, obowiązkowe potwierdzenie
  (`PlanNotConfirmedError`), numerowane wyniki z `result.json` i danymi audytowymi,
  dziennik `journal.jsonl` (ARCHITECTURE 5–7).
- CLI: `retman "…"`, sesja `retman`, `--plan-only`, `--explain`, `--config`,
  `retman init`, `retman results`, `retman log`; kody wyjścia 0–3 (ARCHITECTURE 6.4).
- Specyfikacja `retman-eval` (`docs/specs/2026-10-11-retman-eval.md`).
- `retman-eval --config PATH`: planuje zbiór poleceń testowych (bez wykonywania operacji),
  zapisuje surowe rekordy i raport Markdown z miarami (trafność, błąd przy pewności W-02,
  ciche zgadywanie, naruszenia W-03, czasy), krzywą progów i zalecanymi progami
  (`--target-error`); kod 4 przy naruszeniu W-03 (ARCHITECTURE 8).
- `OutOfScopeError` dla poleceń spoza zakresu, z listą dostępnych operacji (W-03).
- `retman doctor` (i `--json`): plik centralny, folder projektu i zapis wyników, czytelność
  `result.json`, adres modelu decyzyjnego, lista modeli serwera, pytanie testowe, metoda
  pewności i progi, wersje narzędzi na tle obsługiwanego zakresu z poleceniem doinstalowania,
  komplet tłumaczeń, model tekstowy; każdy problem z podpowiedzią, kod 1 gdy coś blokuje pracę
  (ARCHITECTURE 7.2). Manifest narzędzia ma pole `source` do podpowiedzi `uv … --with`
  (ARCHITECTURE 4.1).
- Przewodnik użytkownika `docs/USAGE.md`: przygotowanie, polecenia, pytania, plan,
  wyniki i dziennik, sesja i opcje, kody wyjścia, API Pythona, `retman doctor`,
  `retman-eval`, z przykładami przebiegów.
- Raporty badań z 2026-10-19 w `docs/research/` (wpływ wydań narzędzi, integracja,
  sprawdzanie dostępności, plik geometrii, migracja Kartografa, operacje IMGWTools, MCP)
  i ADR-012–019.

### Zmienione

- Operacje Kartografa nie mają wartości domyślnych: Retman dopytuje o rozdzielczość,
  układ wysokościowy i format, jeśli polecenie ich nie podaje (ADR-006).
- Opcje parametrów mają osobną etykietę dla użytkownika i opis dla modelu, jak operacje:
  plan i pytania pokazują krótkie nazwy („NMT (numeryczny model terenu)”, „1 m”), a model
  dopasowuje polecenie i odpowiedzi do opisów z synonymami i nazwami angielskimi (DEM, DTM,
  DSM, orthophoto, GPKG, SHP) (ADR-007, ARCHITECTURE 4.2).
- Dziennik projektu zapisuje przy każdym planie wartości ze źródłami, decyzje modelu
  z pewnością i nazwę zmienianej wartości, a polecenie spoza zakresu — jako osobne zdarzenie
  z decyzją modelu (ARCHITECTURE 5.4, ADR-010).
- Zbiór poleceń ze wszystkich projektów w jednym pliku (`[privacy] collect_commands`,
  `collect_path`), tylko po wyraźnej zgodzie — `retman init` pyta o nią w terminalu
  (ADR-010, ARCHITECTURE 5.4, rozdz. 10). Nowy klucz `collect_path` jest wymagany w
  `retman.toml`.
- Układ wyniku wycinka rozpoznaje kod, nie model: kod EPSG z prefiksem lub bez, nazwa
  (PL-1992, S-JTSK, ETRS89/TM33 …), rola z kontekstu („wynik”, „do”, „przelicz” — wynik;
  zaraz po współrzędnych — prostokąt), bez polskich znaków i z jedną literówką w słowach;
  niejasny zapis kończy się pytaniem (ADR-009, ARCHITECTURE 4.3).
- Model decyzyjny dostaje osobne pytanie o to, co wymienia polecenie (`model_question`),
  zamiast pytania dla użytkownika „czy X, czy Y?”; z Bielikiem 11B trafność wartości
  parametrów wzrosła z 0,55 do 0,78, a rodzaju danych z 16/33 do 32/33 (ADR-008,
  ARCHITECTURE 4.2).
- Narzędzia są wołane przez ich warstwę komend (`validate_command`/`run_command`); handler
  dostaje kontekst narzędzia (`handler(params, inputs, output_dir, ctx)`); komunikaty błędów
  narzędzi mają teksty Retmana wg kodu błędu (ADR-013, ARCHITECTURE 3.2.4).
- Wymagane sekcje `[tools.kartograf]` i `[tools.imgwtools]` w `retman.toml` — starsze pliki
  trzeba wygenerować od nowa (`retman init`) albo uzupełnić (ADR-015).
- CLI pokazuje ostrzeżenia wyniku („Uwaga: …”), w tym warunki licencji danych.
- Wczytany plan (`Plan.from_dict`) nigdy nie przywraca potwierdzenia (W-05).

[0.1.0]: https://github.com/Daldek/Retman/commits/develop
