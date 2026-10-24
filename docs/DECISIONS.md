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
| [ADR-001](#adr-001-pierwsze-operacje-v01-z-kartografa) | Pierwsze operacje v0.1 z Kartografa | 2026-10-11 | Przyjęta — uzupełniona przez ADR-016, ADR-017 |
| [ADR-002](#adr-002-python--312) | Python ≥ 3.12 | 2026-10-11 | Przyjęta |
| [ADR-003](#adr-003-obsługiwane-wersje-kartografa-i-instalacja-deweloperska) | Obsługiwane wersje Kartografa i instalacja deweloperska | 2026-10-11 | Przyjęta — częściowo zastąpiona przez ADR-012 (zakres wersji, przypięcie) |
| [ADR-004](#adr-004-rodzaje-danych-kartografa-osobny-kind-na-produkt) | Rodzaje danych Kartografa: osobny `kind` na produkt | 2026-10-11 | Przyjęta — uzupełniona przez ADR-016, ADR-017 (nowe rodzaje) |
| [ADR-005](#adr-005-klient-http-httpx) | Klient HTTP: `httpx` | 2026-10-11 | Przyjęta |
| [ADR-006](#adr-006-operacje-kartografa-bez-wartości-domyślnych) | Operacje Kartografa bez wartości domyślnych | 2026-10-11 | Przyjęta — uzupełniona przez ADR-012 (nowe pytania) |
| [ADR-007](#adr-007-opcje-z-etykietą-dla-użytkownika-i-opisem-dla-modelu) | Opcje z etykietą dla użytkownika i opisem dla modelu | 2026-10-12 | Przyjęta |
| [ADR-008](#adr-008-osobne-pytanie-dla-modelu-model_question) | Osobne pytanie dla modelu (`model_question`) | 2026-10-12 | Przyjęta |
| [ADR-009](#adr-009-układ-wyniku-wycinka-rozpoznawany-w-kodzie) | Układ wyniku wycinka rozpoznawany w kodzie | 2026-10-12 | Przyjęta |
| [ADR-010](#adr-010-zbiór-poleceń-ze-wszystkich-projektów) | Zbiór poleceń ze wszystkich projektów | 2026-10-12 | Przyjęta — uzupełniona przez ADR-011 |
| [ADR-011](#adr-011-eksport-zbioru-poleceń-i-szkic-wpisów-retman-eval) | Eksport zbioru poleceń i szkic wpisów `retman-eval` | 2026-10-12 | Przyjęta (wdrożenie odłożone) |
| [ADR-012](#adr-012-kartograf-080-i-imgwtools-300) | Kartograf 0.8.0 i IMGWTools 3.0.0 | 2026-10-19 | Przyjęta; zastępuje część ADR-003, uzupełnia ADR-006 |
| [ADR-013](#adr-013-narzędzia-wołane-przez-warstwę-komend) | Narzędzia wołane przez warstwę komend | 2026-10-19 | Przyjęta |
| [ADR-014](#adr-014-bez-sieci-przed-potwierdzeniem-podgląd-i-sprawdzenie) | Bez sieci przed potwierdzeniem: podgląd i sprawdzenie | 2026-10-19 | Przyjęta |
| [ADR-015](#adr-015-magazyny-narzędzi-poza-folderami-wyników) | Magazyny narzędzi poza folderami wyników | 2026-10-19 | Przyjęta |
| [ADR-016](#adr-016-plik-geometrii-jako-obszar) | Plik geometrii jako obszar | 2026-10-19 | Przyjęta; uzupełnia ADR-001 |
| [ADR-017](#adr-017-całe-imgwtools-w-v01-i-rozpoznawanie-dwustopniowe) | Całe IMGWTools w v0.1 i rozpoznawanie dwustopniowe | 2026-10-19 | Przyjęta; uzupełnia ADR-001 |
| [ADR-018](#adr-018-mcp-narzędzia-przez-api-pythona-serwer-retmana-w-v03) | MCP: narzędzia przez API Pythona, serwer Retmana w v0.3 | 2026-10-19 | Przyjęta |
| [ADR-019](#adr-019-statyczne-manifesty-i-retman-scaffold-z-katalogów-narzędzi) | Statyczne manifesty i `retman-scaffold` z katalogów narzędzi | 2026-10-19 | Przyjęta |
| [ADR-020](decisions/0020-error-registry.md) | Adopt the shared error registry (new ADRs are files in `decisions/`, DOC-8.2) | 2026-10-24 | Przyjęta |

---

## ADR-001: Pierwsze operacje v0.1 z Kartografa

**Data:** 2026-10-11
**Status:** Przyjęta — uzupełniona przez ADR-016 (plik geometrii), ADR-017 (operacje IMGWTools)

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

**Errata 1 (2026-10-19, Kartograf 0.8.0):** operacje A–E w 0.8.0 wołają warstwę komend
Kartografa (ADR-013), nie wymienione funkcje; `LandCoverManager` i `download_pl_cutout` w dawnej
postaci nie istnieją. Plik geometrii działa od 0.8.0 (ADR-016); operacje drugiego narzędzia —
ADR-017.

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
**Status:** Przyjęta — częściowo zastąpiona przez ADR-012 (zakres wersji, przypięcie)

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

**Errata 1 (2026-10-19, ADR-012):** zakres `>=0.7.2,<0.8` i pin `@v0.7.2` zastąpione przez
`>=0.8.0,<0.9` i przypięty commit Kartografa (do tagu `v0.8.0`); grupa `tools` zawiera też
`imgwtools[store]`. Mechanizm grupy `tools` bez zmian.

---

## ADR-004: Rodzaje danych Kartografa: osobny `kind` na produkt

**Data:** 2026-10-11
**Status:** Przyjęta — uzupełniona przez ADR-016, ADR-017 (nowe rodzaje)

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

**Errata 1 (2026-10-19, Kartograf 0.8.0 i IMGWTools 3.0.0):** nowe rodzaje `dem_archive`
(NMT 100 m — ZIP województwa), `area_geometry` (ADR-016) i 13 rodzajów IMGWTools (ADR-017);
`retman/kinds.py` ma walidator per rodzaj.

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
**Status:** Przyjęta — uzupełniona przez ADR-012 (nowe pytania Kartografa 0.8.0)

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

**Errata 1 (2026-10-19, Kartograf 0.8.0):** „wartości stałe, których nie da się wybrać”
przestały istnieć: od 0.8.0 NMPT ma kilka rozdzielczości i dwa układy wysokościowe, a
ortofotomapa trzy wersje koloru. Wszystkie stają się parametrami z pytaniem (ADR-012).

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
**Status:** Przyjęta — uzupełniona przez ADR-011 (przekazanie zbioru i szkic wpisów `retman-eval`)

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

## ADR-011: Eksport zbioru poleceń i szkic wpisów `retman-eval`

**Data:** 2026-10-12
**Status:** Przyjęta; uzupełnia ADR-010. **Wdrożenie odłożone** (decyzja autora, 2026-10-12).

**Kontekst:** ADR-010 zostawił otwarte dwie sprawy: jak użytkownik przekazuje zbiór poleceń
autorowi (nigdy automatycznie, ARCHITECTURE rozdz. 10) i jak z pełnych wpisów zbioru
powstają wpisy zbioru testowego `retman-eval` (spec. `docs/specs/2026-10-11-retman-eval.md`).

**Opcje:**
- przekazanie: A) eksport do pliku i wysyłka ręczna przez użytkownika (e-mail, prywatny
  kanał); B) załącznik do zgłoszenia na GitHubie (publiczny — polecenia zawierają
  lokalizacje); C) prywatne repozytorium albo formularz z uploadem;
- szkic wpisów: 1) opcja `retman-eval`; 2) część eksportu; 3) osobne podpolecenie obok
  eksportu.

**Decyzja:**
- przekazanie: **A** (wybór autora); **C z formularzem** do rozważenia później — przyjmie te
  same pełne wpisy, więc nie zmienia formatu;
- szkic: **3** — polecenie `retman collect` z dwoma podpoleceniami:
  - `retman collect export [--from RRRR-MM-DD] [--to RRRR-MM-DD] --output PLIK` — kopiuje
    pełne wpisy z okresu, wypisuje ich liczbę według operacji i statusu (do przejrzenia
    przed wysłaniem), nic nie wysyła; kod 1, gdy zbieranie jest wyłączone albo wybór pusty;
  - `retman collect draft PLIK --output SZKIC` — zamienia pełne wpisy (z eksportu albo
    zbioru) na wpisy `retman-eval` ze stabilnym `id`, tagiem `collected` i polem `review`
    w miejscach do rozstrzygnięcia przez człowieka.

Uzasadnienie wyboru 3: `retman-eval` mierzy i wymaga modelu, a szkic to zamiana formatu bez
modelu, po której i tak następuje przegląd człowieka; eksport robi użytkownik, który nie
powinien rozstrzygać oczekiwań testu, a szkic gubi dane (decyzje modelu, prawdopodobieństwa,
status), których autor potrzebuje do analiz; szkic robi autor — także z plików od testerów.

**Reguły szkicu:** wartość ze źródłem `command` w planie zatwierdzonym → `params`; wartość
ze źródłem `user` → `review` (polecenie jej nie podało — `expect_clarify` — albo model był
niepewny lub się mylił); plan odrzucony, zmieniony lub anulowany → `review`; „poza
zakresem” → `operation: "out_of_scope"` z `review`, czy słusznie. Wpis z nieprzejrzanym
polem `review` jest odrzucany przez walidację zbioru (`retman/eval/dataset.py`).

**Konsekwencje (przy wdrożeniu):** kod szkicu obok walidacji zbioru
(`retman/eval/dataset.py`), polecenie w CLI; ARCHITECTURE 5.4 i 7.1 (lista poleceń), USAGE
6.4, specyfikacja `retman-eval` p. 2 (pole `review`, tag `collected`). Do ustalenia przy
wdrożeniu: czy eksport może anonimizować wpisy (np. pomijać wybrane), skoro współrzędne są
potrzebne do testów.

---

## ADR-012: Kartograf 0.8.0 i IMGWTools 3.0.0

**Data:** 2026-10-19
**Status:** Przyjęta; zastępuje część ADR-003 (zakres wersji, przypięcie), uzupełnia ADR-006

**Kontekst:** Autor wydaje Kartografa 0.8.0 i IMGWTools 3.0.0 ze zmianami łamiącymi API
(`docs/research/2026-10-19-kartograf-0.8.0-imgwtools-3.0.0-wplyw.md`). Na Kartografie 0.8.0
wszystkie cztery operacje adaptera przestały działać; IMGWTools 2.x nie miał adaptera.

**Opcje:**
- A) zostać przy Kartografie 0.7.2 do czasu stabilizacji,
- B) przejść od razu, przypinając wypchnięte commity do czasu tagów.

**Decyzja:** B (autor: „jak najszybciej; największe zmiany już weszły”). Zakresy:
Kartograf `>=0.8.0,<0.9`, IMGWTools `>=3.0.0,<4` (semver i kontrakty `/1` IMGWTools). Grupa
`tools` przypina do czasu tagów `kartograf@8e9bcbb0` (`origin/develop`) i
`imgwtools[store]@0d98f3b` (`origin/slave`, publikacja wersji magazynu dowiązaniami twardymi —
działa na Linuksie, macOS i Windows; autor włącza ją do v3.0.0). Retman pyta o każdą nową
wymaganą wartość (autor): rozdzielczość i układ wysokościowy NMPT, kolor ortofotomapy
(RGB/CIR/B-W). Obsługiwane są wszystkie rozdzielczości arkuszy ASC Kartografa (NMT 0,15; 0,5;
0,6; 1; 5; 10; 100 m; NMPT 0,5; 0,6; 1 m).

**Konsekwencje:** po wypchnięciu tagów `v0.8.0` i `v3.0.0` grupa `tools` przechodzi na tagi.
Kompletność rozdzielczości pilnuje kontrola pokrycia (ADR-019). Szczegóły:
`docs/research/2026-10-19-kartograf-0.8.0-migracja.md`, `…-imgwtools-3.0.0-operacje.md`.

---

## ADR-013: Narzędzia wołane przez warstwę komend

**Data:** 2026-10-19
**Status:** Przyjęta

**Kontekst:** Kartograf 0.8.0 i IMGWTools 3.0.0 mają katalog komend (`validate_command`,
`run_command`, `check_command`, `format_command`) z kodami błędów i dokumentami wyniku JSON.
Zmiana typowanych funkcji i klas dostawców w 0.8.0 zepsuła wszystkie handlery. Autor powierzył
rozstrzygnięcie badaniu (2026-10-19); rekomendacja stała się decyzją.

**Opcje:**
- A) typowane funkcje i klasy dostawców narzędzi w handlerach,
- B) warstwa komend: czysty budowniczy wywołań na operację, wspólny wykonawca, klient na
  narzędzie,
- C) podproces CLI `--json`; D) serwery MCP narzędzi (ADR-018).

**Decyzja:** B. `retman/adapters/catalog.py` (`CatalogCall`, `ToolRun`, `ToolError`,
`PlanView`/`RunClient`, `ToolContext`); manifest: `client` (fabryka klienta), w operacji `calls`,
`commands`, `describe`, `preview`, `check`, `handler(params, inputs, output_dir, ctx)` (co
najmniej jedno z `handler`/`calls`), w parametrze `tool_values`, `option_meta`, `excluded`;
klucze opcji bez kropek. Przed potwierdzeniem istnieje tylko widok offline (`validate`,
`command_line`, `lookup`); `run`/`check`/`query` — dopiero w wykonaniu i w zatwierdzonym
sprawdzeniu. Wyjątek: ortofotomapa z kolorem przez `GugikOrtoProvider` + `DownloadManager`
(komenda `imagery download` nie ma opcji koloru; decyzja autora), tylko dla godeł arkuszy.
Komunikaty: teksty Retmana wg kodu błędu narzędzia (`[errors.<kod>]`), tekst narzędzia jako
`{detail}`; ostrzeżenia o jakości danych i licencji dosłownie.

**Konsekwencje:** ARCHITECTURE 3.2, 4.1, 4.3; testy przez `FakeToolClient` i nagrane dokumenty
narzędzi. Badanie: `docs/research/2026-10-19-integracja-narzedzi.md`.

---

## ADR-014: Bez sieci przed potwierdzeniem: podgląd i sprawdzenie

**Data:** 2026-10-19
**Status:** Przyjęta

**Kontekst:** Autor: sprawdzanie dostępności nie może używać sieci przed potwierdzeniem;
dopuszczalne dwa kroki z jawnym zapytaniem sieciowym.

**Opcje:**
- A) sieć w planowaniu; B) osobna operacja „sprawdź”; C) podgląd offline zawsze + opcjonalne
  sprawdzenie sieciowe jako osobny krok z własną zgodą.

**Decyzja:** C. Niezmiennik N-12: przed `plan.confirm()` Retman nie woła żadnej funkcji
narzędzia z efektem sieciowym. Podgląd (`preview`, wymagany): walidacja offline każdego
wywołania i wiersze planu; odrzucenie narzędzia ponownie otwiera wskazane parametry
(`Plan.reopened`). Sprawdzenie (`check`): odpowiedź `s` w planie, własny komunikat i zgoda
(`plan.confirm_check()`, jednorazowa), raport tylko informacyjny, nie zmienia planu, nie
zajmuje numeru wyniku; zdarzenie `check` w dzienniku.

**Konsekwencje:** PRD N-12, W-17; ARCHITECTURE 2, 6.3–6.5, 5.4. Badanie:
`docs/research/2026-10-19-sprawdzanie-dostepnosci.md`.

---

## ADR-015: Magazyny narzędzi poza folderami wyników

**Data:** 2026-10-19
**Status:** Przyjęta

**Kontekst:** Kartograf 0.8.0 zapisuje do magazynu wersji (niezmienne wersje, sidecary,
dowiązania twarde), IMGWTools 3.0.0 do własnego magazynu. Autor: magazyn IMGW obok magazynu
Kartografa (ten sam dysk, inne foldery).

**Opcje:** A) magazyn w każdym folderze wyniku; B) jeden magazyn na narzędzie w `retman.toml`.

**Decyzja:** B. `[tools.kartograf] store_dir, cache_file, workers, update` i
`[tools.imgwtools] store_dir, reference_data_dir`; `retman init` zapisuje sąsiednie foldery i
(za zgodą) inicjuje magazyn IMGW; wymagane dowiązania twarde. Wynik odwołuje się do plików
magazynu ścieżką bezwzględną i SHA-256; pliki eksportowane trafiają do folderu wyniku.
`retman doctor` sprawdza magazyny i dowiązania twarde (sonda zapisu IMGW z `--deep`).

**Konsekwencje:** konfiguracje bez `[tools.*]` są odrzucane (`retman init` od nowa albo
dopisanie sekcji); ARCHITECTURE 3.2.4, 5.4, 7.2, 9.1.

---

## ADR-016: Plik geometrii jako obszar

**Data:** 2026-10-19
**Status:** Przyjęta; uzupełnia ADR-001

**Kontekst:** Backlog „plik geometrii jako obszar” czekał na publiczne API Kartografa; 0.8.0
ma `get_overall_bbox`, `find_sheets_for_geometry` i `geometry=`/`layer=` w funkcjach komend.
Rozstrzygnięcie delegowane badaniu.

**Opcje:** A) prostokąt geometrii liczony przez Retmana; B) arkusze przecinające geometrię;
C) przekazanie pliku narzędziu (`geometry=`).

**Decyzja:** C. Obszar `{type: "geometry", path, layer}`; warstwę GeoPackage z kilkoma
tabelami wybiera użytkownik (lista przez `sqlite3`, `retman/core/geometry.py`). Semantyka
per operacja w planie (podgląd: obwiednia, liczba arkuszy). Ortofotomapa przyjmuje tylko
godła (ADR-013). Rodzaj `area_geometry`; SHA-256 pliku w śladzie audytowym.

**Konsekwencje:** ARCHITECTURE 3.2.6, 4.3, 6.1. Badanie:
`docs/research/2026-10-19-plik-geometrii.md`.

---

## ADR-017: Całe IMGWTools w v0.1 i rozpoznawanie dwustopniowe

**Data:** 2026-10-19
**Status:** Przyjęta; uzupełnia ADR-001

**Kontekst:** PRD 7.1 wymaga operacji z co najmniej dwóch narzędzi. Autor: „całe IMGW wchodzi
do v0.1”, z ČHMÚ.

**Opcje:** A) kilka operacji IMGWTools; B) wszystkie możliwości użytkowe katalogu IMGWTools.

**Decyzja:** B — 26 operacji w 6 kategoriach (stacje i katalog, dane bieżące, PMAXTP, szeregi,
archiwa i magazyn, projekty danych); 7 komend katalogu wyłączonych z uzasadnieniem. Ponad 9
operacji ⇒ rozpoznawanie dwustopniowe: model wybiera kategorię, potem operację (≤ 9 opcji na
krok, `[categories.<id>]` w `pl.toml`). Nowe ekstraktory: stacja (offline z katalogu
magazynu), lata, okres, rodzaj roku (zawsze pytanie), punkt, komórka siatki,
prawdopodobieństwo, czas trwania, zmienne, nazwa zadania. 13 nowych rodzajów danych.

**Konsekwencje:** PRD 7.2; ARCHITECTURE 3.1, 3.2.6, 3.4, 4.4, 6.1. Badanie:
`docs/research/2026-10-19-imgwtools-3.0.0-operacje.md`.

---

## ADR-018: MCP: narzędzia przez API Pythona, serwer Retmana w v0.3

**Data:** 2026-10-19
**Status:** Przyjęta

**Kontekst:** Kartograf (`kartograf-mcp`) i IMGWTools (`imgw mcp`) mają serwery MCP. Autor
nie wiedział, co optymalne; rozstrzygnięcie delegowane badaniu.

**Opcje:** A) Retman woła narzędzia przez API Pythona; B) Retman jako klient MCP narzędzi;
C) Retman jako serwer MCP; D) odłożyć.

**Decyzja:** A w każdej wersji; B odrzucona (cienka nakładka na te same funkcje, +23 pakiety,
trudniejsze W-05 i testy); C w v0.3 jako opcjonalny dodatek `retman[mcp]`, z potwierdzeniem
człowieka przez elicitation i odmową wykonania, gdy klient tego nie umie. W v0.1 bez kodu,
zależności i konfiguracji MCP.

**Konsekwencje:** ARCHITECTURE 3.2.1, 7.5, 9.3, 11, 12; PRD 9. Badanie:
`docs/research/2026-10-19-mcp.md`.

---

## ADR-019: Statyczne manifesty i `retman-scaffold` z katalogów narzędzi

**Data:** 2026-10-19
**Status:** Przyjęta

**Kontekst:** Autor chce obsługi wszystkich rozdzielczości; katalogi narzędzi opisują opcje
maszynowo. `retman-scaffold` był w bramce, ale nie istniał. Rozstrzygnięcie delegowane.

**Opcje:** A) opcje wyprowadzane z zainstalowanego katalogu przy ładowaniu; B) opcje
statyczne w manifeście + kontrola dryfu.

**Decyzja:** B. Opcje mają polskie teksty, a zbiór `retman-eval` musi być powtarzalny.
`retman-scaffold list | draft | --check` czyta katalogi narzędzi (bez nowych zależności);
`--check` to zgodność przez wykonanie: prawdziwi budowniczowie wywołań na siatce opcji
manifestu przez `validate_command` offline, kontrola pokrycia (każda wartość narzędzia
oferowana albo w `excluded`), efekty sieciowe, teksty kodów błędów (X1–X10). Lekka wersja w
`retman doctor`.

**Konsekwencje:** ARCHITECTURE 3.2.3, 3.2.7, 8.3; STANDARDS 17. Badanie:
`docs/research/2026-10-19-integracja-narzedzi.md` (rozdz. 2–3).

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
