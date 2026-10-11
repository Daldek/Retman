# Rejestr decyzji — Retman

Każda decyzja architektoniczna lub projektowa jest udokumentowana poniżej.
Format: numer, data, kontekst (dlaczego temat powstał), rozważone opcje, decyzja, konsekwencje.

Treść decyzji opisuje stan w chwili jej podjęcia i nie jest modernizowana.
Późniejsze zmiany faktów i ustalenia dodatkowe są dopisywane na końcu wpisu
jako erraty `**Errata N (RRRR-MM-DD, źródło/powód):**`, numerowane w obrębie
ADR chronologicznie. Szablon nowego wpisu: [Szablon nowego ADR](#szablon-nowego-adr).

**Słownik statusów** (linia `**Status:**` każdego wpisu):
- `Przyjęta` — decyzja obowiązuje w całości;
- `Przyjęta — częściowo zastąpiona przez ADR-x (zakres)` — wskazana część nie obowiązuje;
- `Przyjęta — uzupełniona przez ADR-x (zakres)` — obowiązuje, późniejsza decyzja ją rozszerza;
- `Zastąpiona przez ADR-x` — nie obowiązuje;
- `Odrzucona` — rozważona i nieprzyjęta.

Po średniku status może podać relacje odwrotne (`zastępuje ...`, `uzupełnia ...`);
każda relacja jest zapisana po obu stronach.

## Indeks

| ADR | Tytuł | Data | Status |
|---|---|---|---|
| [ADR-001](#adr-001-pierwsze-operacje-v01-z-kartografa) | Pierwsze operacje v0.1 z Kartografa | 2026-10-11 | Przyjęta |
| [ADR-002](#adr-002-python--312) | Python ≥ 3.12 | 2026-10-11 | Przyjęta |
| [ADR-003](#adr-003-obsługiwane-wersje-kartografa-i-instalacja-deweloperska) | Obsługiwane wersje Kartografa i instalacja deweloperska | 2026-10-11 | Przyjęta |
| [ADR-004](#adr-004-rodzaje-danych-kartografa-osobny-kind-na-produkt) | Rodzaje danych Kartografa: osobny `kind` na produkt | 2026-10-11 | Przyjęta |
| [ADR-005](#adr-005-klient-http-httpx) | Klient HTTP: `httpx` | 2026-10-11 | Przyjęta |
| [ADR-006](#adr-006-operacje-kartografa-bez-wartości-domyślnych) | Operacje Kartografa bez wartości domyślnych | 2026-10-11 | Przyjęta |

---

## ADR-001: Pierwsze operacje v0.1 z Kartografa

**Data:** 2026-10-11
**Status:** Przyjęta

**Kontekst:** PRD 7.2 wymagał listy pierwszych operacji; bez niej nie mogły powstać
manifesty, handlery ani zbiór testowy. Autor wybrał Kartografa v0.7.2 jako pierwsze
narzędzie do sprawdzania możliwości Retmana.

**Opcje (operacje publicznego API Kartografa 0.7.2):**
- A) NMT dla arkusza (`DownloadManager.download_sheet`),
- B) NMT/NMPT/ortofotomapa dla arkusza nadrzędnego (`DownloadManager.download_hierarchy`),
- C) wycinek NMT/NMPT dla obszaru przez WCS (`download_pl_cutout`),
- D) chmura punktów LAZ dla obszaru (`download_laz_area`),
- E) BDOT10k dla powiatu albo obszaru (`LandCoverManager`),
- F) grupy glebowe HSG (`calculate_hsg_by_*`).

**Decyzja:** A, B, C i E. Obszar w poleceniu: godło arkusza, prostokąt we współrzędnych
PL-1992, prostokąt w stopniach WGS84, plik z geometrią (SHP/GPKG).

**Konsekwencje:** PRD 7.2 dostaje listę; wymóg PRD 7.1 „z co najmniej dwóch narzędzi”
pozostaje — operacja drugiego narzędzia do ustalenia. Potrzebne ekstraktory godła,
prostokąta (z rozpoznaniem układu), kodu TERYT i ścieżek (ARCHITECTURE 3.1).

---

## ADR-002: Python ≥ 3.12

**Data:** 2026-10-11
**Status:** Przyjęta

**Kontekst:** Kartograf 0.7.2 wymaga Pythona ≥ 3.12, a narzędzia muszą działać w tym
samym środowisku co Retman (PRD N-09, ARCHITECTURE 9.4). Retman miał wymagać ≥ 3.11.

**Opcje:**
- A) podnieść Retmana do ≥ 3.12 — jedno środowisko bez wyjątków,
- B) zostawić ≥ 3.11 — operacje Kartografa tylko na 3.12+, CI w dwóch wariantach.

**Decyzja:** A.

**Konsekwencje:** `requires-python = ">=3.12"`; zmienione ARCHITECTURE 9.2, 9.3,
STANDARDS 5.1, 6.1, 8.1, README, CLAUDE.md.

---

## ADR-003: Obsługiwane wersje Kartografa i instalacja deweloperska

**Data:** 2026-10-11
**Status:** Przyjęta

**Kontekst:** Manifest podaje obsługiwany zakres wersji narzędzia (ARCHITECTURE 3.2.7),
a testy handlerów potrzebują prawdziwego narzędzia w `.venv`. Retman nie ma dodatków
instalujących narzędzia (ARCHITECTURE 9.3).

**Opcje:**
- A) `>=0.7.2,<0.8`; Kartograf z tagu Git w grupie zależności deweloperskich,
- B) `==0.7.2`; jak wyżej,
- C) `>=0.7.2,<0.8`; instalacja edytowalna z katalogu `../Kartograf`.

**Decyzja:** A. Grupa `tools` w `[dependency-groups]` `pyproject.toml`
(`kartograf @ git+https://github.com/Daldek/Kartograf@v0.7.2`) — nie trafia do metadanych
pakietu, więc użytkownik dalej instaluje narzędzia sam (`--with`).

**Konsekwencje:** STANDARDS 6.1 opisuje `uv pip install --group tools`. Katalog
`../Kartograf` nie jest używany (jego gałąź robocza nie musi odpowiadać wydaniu).

---

## ADR-004: Rodzaje danych Kartografa: osobny `kind` na produkt

**Data:** 2026-10-11
**Status:** Przyjęta

**Kontekst:** ARCHITECTURE 12 pkt 7 — lista rodzajów danych była otwarta. Operacje
z ADR-001 zwracają rastry NMT, NMPT, ortofotomapy i wektory BDOT10k.

**Opcje:**
- A) osobny `kind` na produkt: `dem`, `dsm`, `orthophoto`, `topographic_vector`,
- B) kindy formatowe: `raster`, `vector`,
- C) osobny `kind` na produkt i postać (zbiór arkuszy / wycinek).

**Decyzja:** A. Format plików jest taki, jaki zwraca Kartograf (Retman ich nie konwertuje);
walidator rodzaju sprawdza rozszerzenie i nagłówek pliku, bez bibliotek geoprzestrzennych.

**Konsekwencje:** ARCHITECTURE 3.2.6 dostaje tabelę rodzajów Kartografa; jeden wynik może
mieć kilka plików tego samego rodzaju (arkusze). Lista dla pozostałych narzędzi nadal otwarta.

---

## ADR-005: Klient HTTP: `httpx`

**Data:** 2026-10-11
**Status:** Przyjęta

**Kontekst:** Zależności podstawowe to tylko klient HTTP (ARCHITECTURE 9.3); backendy
potrzebują jawnych timeoutów i testów offline na zapisanych odpowiedziach (STANDARDS 10.4, 13.2).

**Opcje:**
- A) `httpx` — timeouty per zapytanie, wbudowany `MockTransport` do testów offline,
- B) `requests` — już w środowisku przez Kartografa, ale testy offline wymagałyby
  dodatkowej biblioteki atrap,
- C) `urllib` z biblioteki standardowej — bez zależności, więcej własnego kodu.

**Decyzja:** A.

**Konsekwencje:** `dependencies = ["httpx>=0.27"]`.

---

## ADR-006: Operacje Kartografa bez wartości domyślnych

**Data:** 2026-10-11
**Status:** Przyjęta

**Kontekst:** Manifest Kartografa (ADR-001) miał wartości domyślne dla rozdzielczości NMT
(1 m), układu wysokościowego (EVRF2007) i formatu BDOT10k (GeoPackage). Przy specyfikacji
`retman-eval` (`docs/specs/retman-eval.md`) trzeba było ustalić, czy pytanie o taki
parametr jest błędem, czy zbędnym kosztem.

**Opcje:**
- A) zostawić wartości domyślne — mniej pytań, ale wynik zależy od wartości, których
  użytkownik nie wybrał,
- B) usunąć wartości domyślne — Retman dopytuje o każdy szczegół, którego polecenie nie podaje.

**Decyzja:** B — autor woli, żeby Retman dopytywał o szczegóły, niż przyjmował wartości
domyślne. Parametry bez wartości w poleceniu są wymagane (`required`), więc trafiają do
pytań. Wartości stałe, których nie da się wybrać (NMPT tylko 1 m / EVRF2007, ortofotomapa),
nie są parametrami.

**Konsekwencje:** `retman/tools/kartograf/manifest.py` bez kluczy `default`; teksty
`unspecified` w `pl.toml` zapowiadają pytanie. W `retman-eval` pytanie o parametr niepodany
w poleceniu jest oczekiwane (`expect_clarify`), a przyjęcie wartości bez pytania — cichym
zgadywaniem.

---

## Szablon nowego ADR

Kopiuj poniższy blok przy dodawaniu decyzji: kolejny numer, status ze
słownika na początku pliku, nowy wiersz w indeksie i odsyłacze po obu
stronach relacji. Wpisy dodawaj nad tą sekcją, oddzielone `---`.
Erraty dopisuj na końcu wpisu.

```markdown
## ADR-XXX: Tytuł

**Data:** RRRR-MM-DD
**Status:** Przyjęta | Przyjęta — częściowo zastąpiona przez ADR-YYY (zakres) | Przyjęta — uzupełniona przez ADR-YYY (zakres) | Zastąpiona przez ADR-YYY | Odrzucona

**Kontekst:** Dlaczego temat powstał.

**Opcje:**
- A) ...
- B) ...

**Decyzja:** Która opcja i dlaczego.

**Konsekwencje:** Co z tego wynika (w tym zmiany w PRD.md / ARCHITECTURE.md).

**Errata 1 (RRRR-MM-DD, źródło/powód):** Dopisywane później.
```
