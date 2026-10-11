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
- Specyfikacja `retman-eval` (`docs/specs/retman-eval.md`).

### Zmienione

- Operacje Kartografa nie mają wartości domyślnych: Retman dopytuje o rozdzielczość,
  układ wysokościowy i format, jeśli polecenie ich nie podaje (ADR-006).

[0.1.0]: https://github.com/Daldek/Retman/commits/develop
