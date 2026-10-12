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
- Cztery operacje Kartografa 0.7.2 (ADR-001, ADR-003): NMT dla arkusza, arkusze potomne
  NMT/NMPT/ortofotomapy, wycinek NMT/NMPT dla prostokąta (PL-1992 albo WGS84), BDOT10k
  dla powiatu (TERYT), arkusza albo prostokąta, w GeoPackage albo Shapefile.
- Rodzaje danych `dem`, `dsm`, `orthophoto`, `topographic_vector` z walidacją nagłówków
  plików (ADR-004, ARCHITECTURE 3.2.6).
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
- Zbiór `retman/eval/commands.jsonl`: 60 poleceń dla czterech operacji Kartografa
  i 15 spoza zakresu lub bliskich zakresowi, z walidacją wpisów na tym samym kodzie
  ekstraktorów co planowanie (ARCHITECTURE 8.1).
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

### Zmienione

- Operacje Kartografa nie mają wartości domyślnych: Retman dopytuje o rozdzielczość,
  układ wysokościowy i format, jeśli polecenie ich nie podaje (ADR-006).
- Opcje parametrów mają osobną etykietę dla użytkownika i opis dla modelu, jak operacje:
  plan i pytania pokazują krótkie nazwy („NMT (numeryczny model terenu)”, „1 m”), a model
  dopasowuje polecenie i odpowiedzi do opisów z synonymami i nazwami angielskimi (DEM, DTM,
  DSM, orthophoto, GPKG, SHP) (ADR-007, ARCHITECTURE 4.2).
- Układ wyniku wycinka rozpoznaje kod, nie model: kod EPSG z prefiksem lub bez, nazwa
  (PL-1992, S-JTSK, ETRS89/TM33 …), rola z kontekstu („wynik”, „do”, „przelicz” — wynik;
  zaraz po współrzędnych — prostokąt), bez polskich znaków i z jedną literówką w słowach;
  niejasny zapis kończy się pytaniem (ADR-009, ARCHITECTURE 4.3).
- Model decyzyjny dostaje osobne pytanie o to, co wymienia polecenie (`model_question`),
  zamiast pytania dla użytkownika „czy X, czy Y?”; z Bielikiem 11B trafność wartości
  parametrów wzrosła z 0,55 do 0,78, a rodzaju danych z 16/33 do 32/33 (ADR-008,
  ARCHITECTURE 4.2).

[0.1.0]: https://github.com/Daldek/Retman/commits/develop
