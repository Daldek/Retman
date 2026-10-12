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
| [ADR-007](#adr-007-opcje-z-etykietą-dla-użytkownika-i-opisem-dla-modelu) | Opcje z etykietą dla użytkownika i opisem dla modelu | 2026-10-12 | Przyjęta |
| [ADR-008](#adr-008-osobne-pytanie-dla-modelu-model_question) | Osobne pytanie dla modelu (`model_question`) | 2026-10-12 | Przyjęta |
| [ADR-009](#adr-009-układ-wyniku-wycinka-rozpoznawany-w-kodzie) | Układ wyniku wycinka rozpoznawany w kodzie | 2026-10-12 | Przyjęta |
| [ADR-010](#adr-010-zbiór-poleceń-ze-wszystkich-projektów) | Zbiór poleceń ze wszystkich projektów | 2026-10-12 | Przyjęta |

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
`retman-eval` (`docs/specs/2026-10-11-retman-eval.md`) trzeba było ustalić, czy pytanie o taki
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

## ADR-007: Opcje z etykietą dla użytkownika i opisem dla modelu

**Data:** 2026-10-12
**Status:** Przyjęta

**Kontekst:** Operacje miały już osobno `label` (dla użytkownika) i `description`
(z synonimami, tylko dla modelu), ale opcja parametru miała jeden tekst. Ten sam tekst
szedł do modelu, do pytania w terminalu i do planu, więc synonimy dopisane dla modelu
(„DEM”, „rzeźba terenu”) zaśmiecały to, co widzi użytkownik.

**Opcje:**
- A) rozdzielić opcje jak operacje: `label` dla użytkownika, `description` dla modelu,
- B) usunąć synonimy z opcji i zostawić je tylko w opisach operacji,
- C) usunąć synonimy w ogóle — Retman rozumie tylko polskie nazwy urzędowe.

**Decyzja:** A — w praktyce często używa się angielskich nazw i skrótów (DEM, DSM, SHP),
mimo że komunikacja jest po polsku, więc model musi je znać, a użytkownik ma widzieć
krótkie nazwy.

**Konsekwencje:** każda opcja w pliku tłumaczeń ma `options.<klucz>.label`
i `options.<klucz>.description`; `unspecified` nigdy nie jest pokazywany, więc ma tylko
`description`. Walidacja manifestu wymaga obu pól. Odpowiedź użytkownika własnymi słowami
model też dopasowuje do opisów (opcji i operacji), nie do etykiet. ARCHITECTURE 4.2,
DEVELOPMENT_STANDARDS 17.

---

## ADR-008: Osobne pytanie dla modelu (`model_question`)

**Data:** 2026-10-12
**Status:** Przyjęta

**Kontekst:** Pierwszy przebieg `retman-eval` z Bielikiem 11B
(`docs/research/2026-10-12-bielik-11b-retman-eval.md`): model wybierał „nie podano” dla
rodzaju danych w 17/34 poleceniach, mimo „NMT”/„DSM” w treści. Model dostawał to samo
pytanie co użytkownik („Czy wycinek ma zawierać NMT (teren) czy NMPT (pokrycie terenu)?”).
Diagnostyka na tym samym serwerze: pytanie o to, co wymienia polecenie, dało 32/34 (21 pewnych
≥ 0,9 zamiast 4), poprawiło też format, układ wysokościowy, rozdzielczość i skalę, bez nowych
błędów z wysoką pewnością.

**Opcje:**
- A) osobny tekst `model_question` dla parametrów wybieranych przez model,
- B) przeredagować `question` tak, by służył obu stronom,
- C) rozpoznawać wartości w kodzie (słowniki synonimów) zamiast w modelu.

**Decyzja:** A — pytanie dla użytkownika ma zostać naturalne („1 m czy 5 m?”), a model
potrzebuje pytania o treść polecenia; rozdział jak `label`/`description` (ADR-007). C zostaje
do rozważenia dla układu wyniku (`target_crs`), którego A nie poprawia.

**Konsekwencje:** parametry `choice` i `bool` mają w pliku tłumaczeń `model_question`
(wymagane przez walidację manifestu); pipeline używa go przy decyzji z polecenia i przy
odpowiedzi własnymi słowami, a pytanie użytkownika (`question`) — tylko w terminalu
i w dzienniku. Pytanie o operację (`dialog.operation`) bez zmian. Przy backendzie basal
do sprawdzenia, czy jego kalibracja pasuje do takiego brzmienia. ARCHITECTURE 3.3.1, 4.2,
DEVELOPMENT_STANDARDS 17.1.

---

## ADR-009: Układ wyniku wycinka rozpoznawany w kodzie

**Data:** 2026-10-12
**Status:** Przyjęta

**Kontekst:** W przebiegach `retman-eval` z Bielikiem 11B
(`docs/research/2026-10-12-bielik-11b-retman-eval.md`) jedyne decyzje błędne przyjęte bez
pytania dotyczyły `target_crs`: układ podany dla prostokąta wejściowego („… 382100
PL-1992”) model brał za układ wyniku z pewnością do 0,97. Ani opis opcji, ani
`model_question` (ADR-008) tego nie poprawiły — błąd wynika z roli kodu w zdaniu.

**Opcje:**
- A) kod rozpoznaje układy i ich rolę (prostokąt / wynik); niejasne → pytanie,
- B) jak A, a gdy kod nic nie rozpozna — model,
- C) zostawić model z progiem tak wysokim, by takie przypadki zawsze kończyły się pytaniem.

**Decyzja:** A (wybór autora). Liczby i kody odczytuje kod (ARCHITECTURE 1.1); model
myli role z wysoką pewnością, więc droga B przywracałaby ciche zgadywanie.

**Konsekwencje:** ekstraktor `retman/extractors/crs.py`: nazwy i kody układów (z `EPSG:`,
samą liczbą przy słowie o układzie, nazwą: PL-1992, PUWG 1992, S-JTSK, Křovák, ETRS89/TM33,
UTM 33N, WGS84), rola z położenia (zaraz po prostokącie = wejście), słów przed wzmianką
(„wynik”, „do”, „przelicz”, „zapisz”, „docelowy” = wynik; „prostokąt”, „współrzędne” =
wejście) i z niezgodności z układem liczb prostokąta. Tekst bez polskich znaków i wielkości
liter; jedna literówka tolerowana w słowach od 5 liter, krótkie słowa i kody — dokładnie
(literówka w kodzie kończy się pytaniem). Odpowiedź na pytanie czyta osobna funkcja
(sam kod „2180” wystarcza). Schemat manifestu: `choice` z `extractor` i `option_values`
(ARCHITECTURE 4.3); walidacja wymaga dla niego tylko tekstów dla użytkownika. Kartograf:
`download_elevation_cutout.target_crs`.

---

## ADR-010: Zbiór poleceń ze wszystkich projektów

**Data:** 2026-10-12
**Status:** Przyjęta

**Kontekst:** `[privacy] collect_commands` istniało w konfiguracji bez określonego działania
(miejsce zapisu „—” w ARCHITECTURE 5.4). Autor chce oceniać rozpoznanie poleceń na podstawie
pracy z Retmanem i budować z niej zbiór testowy. Dziennik projektu zostaje w folderze
projektu i nie zawierał decyzji modelu dla planów niewykonanych.

**Opcje:**
- A) usunąć ustawienie — wystarczy dziennik projektu,
- B) zbieranie w jednym pliku ze wszystkich projektów, za wyraźną zgodą.

**Decyzja:** B (wybór autora): domyślnie wyłączone, ale `retman init` pyta o zgodę przy
pierwszej konfiguracji. Dziennik projektu uzupełniony o dane planu (wartości ze źródłami,
decyzje modelu z pewnością, zmieniana wartość) i o zdarzenie „poza zakresem”.

**Konsekwencje:** `retman/core/collection.py`; `[privacy] collect_path` (pełna ścieżka
wpisana przez `retman init`, bez ukrytej wartości domyślnej, N-11); `init_config(…,
collect_commands=)`; wpis po każdym wyniku planowania (dla zatwierdzonego — po wykonaniu,
z jego wynikiem), bez adresu serwera i ścieżek lokalnych; `retman-eval` nie zbiera.
ARCHITECTURE 5.4, 9.1, rozdz. 10. Otwarte: sposób przekazania zbioru autorowi (osobna,
wyraźna zgoda, nigdy automatycznie) i krok „zbiór → szkic wpisów `retman-eval`”.

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
