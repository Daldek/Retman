# Integracja narzędzi — jak Retman woła Kartografa 0.8.0 / IMGWTools 3.0.0 i skąd biorą się manifesty

- **Data:** 2026-10-19
- **Zakres:** (Q1) sposób wywoływania narzędzi przez handlery; (Q2) `retman-scaffold`: szkice
  i kontrola dryfu; (Q3) opcje statyczne czy wyprowadzane z katalogu w czasie ładowania.
  Podstawa: Retman `develop` `f1b7294` (+ niezatwierdzone `PROGRESS.md`, raport wpływu, `uv.lock`),
  Kartograf `develop` `d7b5369e` = 0.8.0 (czyste drzewo, tag niewypchnięty), IMGWTools `slave`
  `31e96fa` = 3.0.0 (tag niewypchnięty).
- **Metoda:** odczyt kodu i dokumentacji obu narzędzi oraz Retmana; sondy uruchamiane offline
  (z blokadą gniazd tam, gdzie liczy się próba połączenia), skrypty jednorazowe w `/tmp/probe`,
  nic nie zapisano w żadnym repozytorium. IMGWTools analizowano na czystym eksporcie
  `git archive slave` (`/tmp/imgw-slave`; w chwili startu drzewo robocze było na
  `fix/archiwista-compat` z niezatwierdzonymi zmianami w `src/imgwtools/store/*` i
  `exceptions.py`; po zakończeniu repo było na `slave`, czyste, na tym samym `31e96fa`).
- **Oznaczenia:** „sprawdzone” = wykonane offline podczas badania; [WNIOSEK] = niewykonane.
  Odwołania `ścieżka:linia` dotyczą repozytorium nazwanego w zdaniu.
- **Status:** decyzja delegowana przez autora (2026-10-19) — decyzja nr 8 autora: rekomendacja
  ma stać się decyzją, a ADR musi zaznaczać delegację.

## Decyzje końcowe (nadpisują treść raportu poniżej)

Źródło: konsolidacyjny plan wdrożenia z 2026-10-19 (decyzje autora).

**Aktualizacja (2026-10-19, wieczór):** IMGWTools `0d98f3b` (`origin/slave`) zapisuje magazyn
dowiązaniami twardymi na każdej platformie (model Kartografa); pin Retmana `0d98f3b`. Uwagi
o zapisie „tylko Linux” (D8, ryzyko 17) dotyczą wyłącznie `31e96fa`; magazyn IMGW, tak jak
Kartografa, wymaga systemu plików z dowiązaniami twardymi.

1. **Kolor ortofotomapy JEST pytaniem (decyzja autora).** D10 i wniosek „ortofotomapa = RGB bez
   pytania” (p. 0, 1.2, 6 pkt 2, dodatek A) **zastąpione**: Retman pyta o kolor
   (`rgb`/`cir`/`bw` → `"RGB"`/`"CIR"`/`"B/W"`), a ortofotomapa idzie przez **własny handler**
   oparty na providerze (`GugikOrtoProvider(color=…)` + `DownloadManager`), wyłącznie po kodach
   arkuszy (geometria/bbox nie są dla ortofotomapy przyjmowane → problem w podglądzie offline).
   Walidacja w czasie planowania nadal woła `validate_command("imagery download", …)` — bez koloru.
   Parametr koloru dotyczy tylko produktu `orthophoto` (`depends_on`). To jest „wąska alternatywa”
   z p. 1.2 (kontrpozycja KartografSpec), przyjęta tylko dla ortofotomapy; reszta zostaje na
   warstwie komend.
2. **Handler i `calls` (decyzja 1 planu):** operacja deklaruje `calls` i/lub `handler` (**co
   najmniej jedno**; handler może sam wołać `run_calls` / `ctx.client`) — zastępuje regułę
   „dokładnie jedno z handler / calls” z p. 1.3 i 4 pkt 1. Sygnatura handlera:
   `handler(params, inputs, output_dir, ctx)`.
3. **IMGWTools v3.0.0 będzie zawierał poprawkę przenośnego zapisu magazynu (autor).** Ryzyko 17
   i część D8 o zapisie „tylko Linux” dotyczą commita `31e96fa`; docelowo dolna granica
   `>=3.0.0` jest bezpieczna na każdej platformie. Do czasu pojawienia się tagów grupa `tools`
   przypina wypchnięte commity (`kartograf @ git+https://github.com/Daldek/Kartograf@<pełny sha
   origin/develop>`, `imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@31e96fa…`
   z `origin/slave`; plan wdrożenia podaje `8e9bcbb0…` dla Kartografa zamiast `d7b5369e`);
   sonda platformowa w `retman doctor` zostaje.
4. **`year_type` jest ZAWSZE pytaniem**, gdy nie podano go w poleceniu (brak zgadywania) —
   dotyczy operacji IMGWTools (zakres ImgwScope), nie zmienia kontraktu integracji.
5. **Scaffold:** zaimplementowane `retman-scaffold --check`, `list` i `draft` (p. 2.2–2.4).
   Plan wymaga kontroli dryfu X1–X8; X9–X10 pozostają w projekcie jako informacyjne.
6. **Magazyny i konfiguracja:** `[tools.kartograf] store_dir, cache_file, workers, update`
   oraz `[tools.imgwtools] store_dir, reference_data_dir` w `retman.toml` (bez ukrytych
   wartości domyślnych; `retman init` je zapisuje; oba magazyny na jednym dysku).
   `Config.tools: dict[str, dict[str, Any]]`; `ToolContext.settings` = ta tabela.
   Ekstraktory potrzebujące danych narzędzia dostają `ExtractionContext`
   (`retman/extractors/base.py`; tylko odczyty offline przez `PlanClient.lookup` i ustawienia).
7. Wszystkie rozdzielczości Kartografa (K4), rodzaj `dem_archive` dla NMT 100 m (K5),
   wszystkie operacje IMGWTools (26 operacji, rozpoznawanie dwuetapowe: kategoria → operacja).

Odwzorowanie decyzji autora: 2 (pytać o nowe wartości) → buildery nigdy nie wymyślają wartości,
podgląd pyta ponownie po odrzuceniu przez narzędzie; 3 (wszystkie rozdzielczości) → niezmiennik
pokrycia D6; 4 (brak sieci przed potwierdzeniem) → D2; 5 (całe IMGWTools) → dodatek B + wymóg
rozpoznawania dwuetapowego (p. 6); 6 (magazyny) → D5; 7 (MCP) → API w procesie, zob.
`2026-10-19-mcp.md`; 8 → adnotacja w ADR o delegacji.

---

## 0. Decyzje

| # | Decyzja |
|---|---|
| **D1** | **Handlery wołają każde narzędzie przez jego warstwę komend** (Kartograf `validate_command` / `run_command` / `check_command`; IMGWTools te same nazwy), a nie przez typowane funkcje per produkt ani klasy providerów. Kształt hybrydowy: jeden generyczny runner w rdzeniu, jeden cienki klient na narzędzie, jeden czysty *builder wywołań* na operację (`calls(params, ctx) -> list[CatalogCall]`). Operacje złożone (seria stacji IMGWTools) to kilka wywołań. Typowane funkcje biblioteki zostają tylko dla (a) pomocników offline i zapytań, które nie są komendami danych katalogu (Kartograf `list_sources`, `describe_sheet`, `get_overall_bbox`, `find_sheets_for_geometry`, `check_availability`, czytniki magazynu), (b) narzędzi bez katalogu (Hydrolog, Hydrograf, BasicHydraulics: sprawdzone, brak `run_command`/`get_catalog` w ich repozytoriach). Wyjątek wg decyzji końcowej 1: ortofotomapa (handler na providerze). |
| **D2** | **Podział uprawnień wymusza W-05 / decyzję autora 4 strukturalnie.** `PlanClient` (validate, command_line, lookup) to jedyny obiekt narzędzia istniejący przed `plan.confirm()`; `RunClient` (+ run, check, query) istnieje tylko wewnątrz `execute()` i wewnątrz `Retman.check()` (TwoStepCheck). Walidacja offline (`validate_command`) działa w czasie planowania dla każdej operacji opartej na katalogu, więc odrzucona kombinacja wychodzi przed potwierdzeniem, a nie jako `TypeError` po nim. |
| **D3** | **Komunikaty.** Użytkownik widzi własny tekst Retmana z `pl.toml`, wybrany po stabilnym `code` błędu narzędzia (i skierowany do parametru z `details.option`); `detail`/`hint` narzędzia trafiają do zapisu audytowego i są cytowane tylko jako `{detail}`. Uwagi: tekst Retmana tylko tam, gdzie znaczenie jest ustrukturyzowane i bez liczb w prozie; uwagi z liczbami i o jakości danych (np. Kartograf `no_coverage_some`, `incomplete_campaign`) oraz uwagi prawne/licencyjne dostawców (IMGWTools `license_terms`) pokazywane są dosłownie, bo dokumenty nie dają ustrukturyzowanych liczb per arkusz (p. 1.5); nieznane ostrzeżenia — dosłownie za ogólnym prefiksem Retmana; nic nie jest gubione. |
| **D4** | **Wynikiem są dokumenty JSON narzędzi** (`kartograf-download/1`, `imgw-result/1`), konsumowane jako dane do `ToolRun` i mapowane na `HandlerOutput`; `HandlerOutput` dostaje opcjonalny blok audytowy `tool` (dokładna linia komendy z `format_command`, wersja narzędzia, SHA-256/etykieta wersji per plik; pełny dokument zapisany jako plik w folderze wyniku). |
| **D5** | **Magazyny i konfiguracja.** Jeden katalog magazynu na narzędzie, poza folderami wyników, deklarowany w `retman.toml` `[tools.kartograf]` / `[tools.imgwtools]` (decyzja autora 6, N-11). Argumenty środowiskowe (`output_dir`/`root`, `workers`, `cache`, `update`) pochodzą wyłącznie z tej tabeli, nigdy z domyślnych wartości narzędzia ani zmiennych środowiskowych. Wyniki wskazują pliki magazynu przez ścieżkę bezwzględną + SHA-256 (nic nie jest kopiowane); pliki, które Retman lub narzędzie *eksportuje*, trafiają do `output_dir`. |
| **D6** | **Manifesty zostają statyczne i recenzowane; opcje nigdy nie są wyprowadzane z zainstalowanego katalogu w czasie ładowania** (Q3). Dochodzi pięć opcjonalnych kluczy manifestu: `calls`, `commands`, `tool_values`, `option_meta` (nieprzezroczyste dane per opcja, tylko dla builderów), `excluded`; klucze opcji nie zawierają kropek (`0_5m`). „WSZYSTKIE rozdzielczości” wymusza *niezmiennik pokrycia* w kontroli dryfu, a nie listy dynamiczne. Tabeli `combinations` (poprawne pary) w v0.1 NIE dodajemy. |
| **D7** | **`retman-scaffold` czyta maszynowe katalogi narzędzi** (`get_catalog`, `command_schema`, `list_sources`, `datasets`), a nie docstringi: `list` / `draft` / `--check`. Bez `griffe` i bez nowej zależności w v0.1. Kontrola dryfu to *zgodność przez wykonanie*: uruchamia prawdziwe buildery wywołań na siatce wyborów z manifestu przez offline'owe `validate_command` narzędzia, plus sondę pokrycia uwzględniającą zakres. Działa w pytest, w CI i (lekko) w `retman doctor`. |
| **D8** | **Wersje.** Kartograf `>=0.8.0,<0.9` (minory 0.x mogą łamać). IMGWTools `>=3.0.0,<4` (semver + addytywne kontrakty IMGW-13; autor może wybrać `<3.1`), **ale 3.0.0 jako otagowany (`31e96fa`) zapisuje magazyn tylko na Linuksie**: `store/writer.py:93-98` rzuca `IMGWStoreConflictError` na każdej innej platformie (sprawdzone), więc na Windows/macOS (PRD N-09) dolną granicą musi być wydanie z przenośnym zapisem — w chwili badania niewydana praca na `fix/archiwista-compat` (ImgwScope) [WNIOSEK: wydanie 3.0.x]. **Decyzja końcowa 3: autor włoży tę poprawkę do v3.0.0.** Bez statycznej flagi platformy: `retman doctor` sonduje przez `imgwtools.testing.build_fixture_store` w katalogu tymczasowym (p. 1.6). CI uruchamia zgodność na najstarszej/najnowszej wersji z zakresu oraz nocnie na gałęziach integracyjnych narzędzi. |
| **D9** | **Testy.** `FakeToolClient` w `retman/testing.py` + nagrane dokumenty JSON zastępują 8 testów z monkeypatchem; testy IMGWTools używają jego oficjalnego magazynu fikcyjnego offline; prawdziwych narzędzi dotykają tylko testy zgodności (offline) i testy `live`. |
| **D10** | **[ZASTĄPIONE decyzją końcową 1]** Luka do rozstrzygnięcia z autorem: `color` ortofotomapy (RGB/CIR/B/W) istnieje tylko w klasie providera (`GugikOrtoProvider(color=)`); `imagery download` nie ma opcji `color` (sprawdzone: `nieznana opcja 'color'`). Pierwotna rekomendacja: ortofotomapa przez warstwę komend = RGB, wpisane w etykiecie operacji, bez pytania; CIR/B-W czeka na ogólne `--color` w Kartografie (autor jest właścicielem obu repozytoriów). **Rozstrzygnięcie autora: Retman pyta o kolor, własny handler na providerze.** |

**Odrzucone alternatywy (z powodem).** Typowane funkcje per produkt lub klasy providerów dla
arkuszy/wycinków (niestabilna powierzchnia, brak walidacji offline, brak maszynowo czytelnych
wyborów). Automatyczne wystawianie każdej komendy katalogu jako operacji w czasie ładowania
(brak polskich tekstów/synonimów, 12 + 37 komend wobec limitu 9 operacji, brak recenzji).
Opcje wyprowadzane z zainstalowanego katalogu w czasie ładowania (Q3). Subprocess `--json`
jako domyślny transport (te same dokumenty, +0,45 s na wywołanie, brak haków, trudniejsze
testy; zostaje jako wymienny `ToolClient`). Serwery MCP narzędzi (raport MCP). Magazyn per wynik
(ponowne pobieranie, `update` traci sens). Tabela `combinations` w v0.1 (ogólny podgląd
pokrywa niepoprawne pary).

---

## 1. Q1: jak handlery wołają narzędzia

### 1.1 Porównanie opcji

| Kryterium | Funkcje typowane / klasy providerów | Warstwa komend (`run_command`, `check_command`, `validate_command`) | Werdykt |
|---|---|---|---|
| Stabilność między wersjami | Kartograf 0.7.2 → 0.8.0 złamał 4/4 operacje i 8/8 testów offline (raport wpływu p. 1); złamana powierzchnia to `DownloadManager` (bez `resolution`, `last_result`), konstruktory providerów (nowe wymagane argumenty), sygnatura `download_pl_cutout`, usunięty `LandCoverManager`. IMGWTools 3.0.0 usunął API 2.x bez aliasów (IMGWTools `docs/DECISIONS.md` ADR-002 D14). | Katalog jest deklarowanym jedynym źródłem prawdy: Kartograf Z9 (`docs/DEVELOPMENT_STANDARDS.md:507`) i ADR-046 D4 (`docs/DECISIONS.md:4136+`); testy kontraktowe porównują katalog z sygnaturami funkcji i przepuszczają każdy przykład z katalogu przez `validate_command` (standardy Kartografa 17.2 pkt 6). IMGWTools ADR-002 D1/D2 (`docs/DECISIONS.md:110-111`): nazwa opcji = nazwa parametru Pythona. Dokumenty są addytywne w obrębie `/1` (Kartograf Z11 `:519`, IMGWTools IMGW-13 `docs/ARCHITECTURE.md:226+`); kody błędów są kontraktem (Kartograf Z4/Z10 `:513`, `:843`; IMGWTools D5 `:114`). Zewnętrzni konsumenci od tego zależą (Archiwista KB-2..5; trwałe nazwy opcji zadań projektu). | katalog |
| Walidacja przed potwierdzeniem | brak (wywołanie = wykonanie) | `validate_command`: offline, bez zapisu, te same reguły co przebieg; błędy niosą `option`/`options`/`allowed` (sprawdzone, p. 2.5) | katalog |
| Reguły między parametrami | tylko w kodzie | wymusza je `validate_command`; `constraints` katalogu są dokumentacją („zrodlem zachowania zostaje biblioteka”, Kartograf USAGE 9.4) | katalog |
| Maszynowo czytelne wybory | sygnatury Kartografa to `str \| None` dla `product`, `resolution`, `vertical_crs`, `format`, `country` (sprawdzone `inspect`), tylko `update` jest `Literal`. ARCHITECTURE 3.2.3 zakładał `Literal`: to nieprawda. IMGWTools nie ma `py.typed` (sprawdzone: brak pliku mimo klasyfikatora). | `allowed` katalogu / `enum` JSON-Schema | katalog |
| Skutki przed uruchomieniem | nieznane | Kartograf `CommandInfo.effects` (`network`, `store_write`, …); IMGWTools `DataCommand.network/writes` = `x-imgw.network/writes` (`store/types.py:1018+`) | katalog |
| Typowane wyniki | bogate dataclassy | te same obiekty w procesie oraz stabilne dokumenty JSON z wiodącym kluczem `schema` (`to_dict()`/`to_json()`) | konsumować dokumenty JSON |
| Model błędów | wyjątki z `code`, `hint`, `details` | identyczny (`run_command` je rzuca) | remis |
| Haki | `on_progress`, `on_notice` oba; `cancel` tylko IMGWTools | te same haki przechodzą; Kartograf `run_command` nie ma `cancel` (ADR-046 D4) | remis |
| Testowalność | dziś każdy test monkeypatchuje wnętrzności narzędzia (`tests/tools/kartograf/test_handlers.py:57-264`, dziewięć `monkeypatch.setattr` na `DownloadManager`, `LandCoverManager`, `download_pl_cutout`, `discover_teryts_for_bbox`) | jedno miejsce styku należące do Retmana (protokół klienta); IMGWTools `imgwtools.testing.build_fixture_store` (prawdziwe uruchomienia offline, sprawdzone); nagrane dokumenty | katalog |
| mypy | Retman używa dziś `Any` dla obiektów narzędzi (`handlers.py:27`); błędy typów zależą od tego, co zainstalowano | TypedDicty Retmana dla dokumentów; narzędzia importowane dynamicznie, więc `mypy retman/ tests/` nie zależy od zainstalowanych narzędzi | katalog |
| Pokrycie potrzeb Retmana | zapytania (dostępność, arkusze, źródła, pomocniki geometrii) nie są komendami danych katalogu: `validate_command`/`check_command` odrzucają `elevation availability` (sprawdzone) | 12 komend danych Kartografa; wszystkie 37 komend IMGWTools | hybryda |
| Subprocess `kartograf ... --json` | n/d | te same dokumenty; izolacja procesu, ale ~0,45 s uruchomienia na wywołanie (tyle co import), brak haków, problemy ze ścieżkami/cytowaniem na Windows, gorsze testy | na razie nie; protokół klienta zostawia to jako wymienny zapas |

Dowód, że autor narzędzia ma na myśli właśnie warstwę komend do takiego użycia: IMGWTools
`docs/ARCHITECTURE.md:245` („Retman runs data actions as a handler via the public command
catalog ... effects from `x-imgw.writes`/`x-imgw.network`”),
`docs/superpowers/specs/2026-10-19-agent-support-design.md:554-561` („`enum` -> `options`,
`minimum`/`maximum` -> `range`, `required`; `retman-scaffold --check` can compare the manifest
with `imgw-commands/1` instead of docstrings; `format_command` for the audit trail”),
`docs/DECISIONS.md:265` (ADR-004 D11). Kartograf: `docs/USAGE.md` 9.5 („... can build, validate
and run tasks without knowing per-product functions”). Oba dokumenty są ogólne (N-03 zachowane).

### 1.2 Dlaczego hybryda i czego warstwa komend nie pokrywa

* **Poza `run_command` (potrzebni typowani pomocnicy):** zapytania Kartografa `check_availability`,
  `describe_sheet`/`parse`, `find_sheets`, `list_sources`, `list_layers`, czytniki magazynu;
  pomocniki geometrii `get_overall_bbox`, `find_sheets_for_geometry` (raport GeometryArea).
  `KartografClient.lookup` (offline) i `.query` (sieć) to małe tablice dyspozycji Retmana z typowanymi
  adapterami (`bbox`+`bbox_crs` w formie JSON → `BBox`, wynik `.to_dict()`), a nie dyspozycja
  refleksyjna; odczyty offline wolno tylko dla komend, których `effects` w katalogu są puste.
  IMGWTools nie potrzebuje żadnych: każde zapytanie jest komendą katalogu.
* **Operacje złożone** (IMGWTools: `store sync` + `series export`) nie mogą być jedną komendą
  katalogu: builder zwraca kilka wywołań; runner zatrzymuje się na pierwszym `failed`/`cancelled`.
* **Mapowanie semantyczne zostaje w builderach**, a nie w deklaratywnym DSL: np. `target_scale` →
  `scale` tylko dla arkuszy nadrzędnych PL-2000 (arkusz PL-1992 ze `scale` jest odrzucany,
  sprawdzone); `dem`/`dsm`/`orthophoto` wybierają produkt `nmt`/`nmpt` komendy `elevation download`
  albo produkt `orto` komendy `imagery download`. Buildery są czyste, testowane offline i
  walidowane kontrolą dryfu.
* **Handlery przetwarzające zostają** tam, gdzie plik narzędzia jest archiwum: SHP BDOT10k to ZIP
  w magazynie (istniejące `_extract_shapefiles`, `handlers.py:163`, przechodzi do własnego handlera
  rozpakowującego do `output_dir`). Ponadto (decyzja końcowa 1) własny handler ortofotomapy.
* **Dlaczego nie wołać wprost `download_data` / `download_landcover`?** Zachowanie to ta sama funkcja
  (`run_command` ją wywołuje; CLI Kartografa = testy parytetu API, ADR-037 Z7), ale wywołanie wprost
  traci `validate_command` (kontrolę offline przed potwierdzeniem), `format_command` (powtarzalna
  linia komendy do śladu audytowego) i jednolitą formę opcji JSON (potrzeba obiektów `BBox`/`Path` i
  domyślnych wartości per funkcja: `workers` to 4 w `download_data` i 1 w `download_landcover`,
  sprawdzone). Droga przez katalog nie kosztuje nic więcej.
* **Rozważona kontrpozycja (KartografSpec): providery + `DownloadManager` dla arkuszy,
  `download_pl_cutout` dla wycinków. Odrzucona z dowodami** (z wyjątkiem ortofotomapy, p. decyzja
  końcowa 1). (1) Droga provider/manager przyjmuje tylko kody arkuszy, więc obszary z geometrii
  (raport GeometryArea) wymagałyby pętli po arkuszach po stronie Retmana; `download_data(geometry=)`
  to jedyne wejście przyjmujące plik. (2) Uwagi o jakości danych (`incomplete_campaign`,
  `sheet_crs_mismatch`, `better_coverage`, `link_outside_range`) produkuje wyłącznie `download_data`
  (`download/data.py:1542-1552`, sprawdzone), więc droga przez managera po cichu gubiłaby ostrzeżenia
  ważne w hydrologii. (3) `validate_command` waliduje dokładnie żądanie `download_data`: walidacja
  jednego wywołania i wykonanie innego przywróciłyby dryf między sprawdzonym a wykonanym. (4)
  Powierzchnią, która złamała 4/4 operacje w 0.8.0, były klasy managera/providerów; warstwa komend
  jest utrzymywanym kontraktem. Co traci warstwa komend: ustrukturyzowane liczby porażek per arkusz
  (p. 1.5) i opcję `color` ortofotomapy (D10), każde z podaną łagodzącą ścieżką. Autor uznał wagę
  koloru za wyższą niż (1)–(4) tylko dla ortofotomapy: jeden własny handler dla produktu
  `orthophoto` (`GugikOrtoProvider(color=)` + `DownloadManager`, bez geometrii, bez uwag o jakości
  danych); wszystko inne zostaje na warstwie komend.

### 1.3 Dokładny kontrakt

Nowy moduł `retman/adapters/catalog.py` (tylko stdlib; nie importuje żadnego narzędzia):

```python
ToolDocument = Mapping[str, Any]            # the tool's JSON document; first key "schema"

@dataclass(frozen=True)
class CatalogCall:
    command: str                            # catalog id: "elevation download", "series export"
    options: Mapping[str, object]           # JSON-form options exactly as validate_command/run_command take them
                                            # (bbox = 4 numbers + REQUIRED bbox_crs; path = str; lists = list)
    kind: str | None = None                 # data kind of the files this call yields (HandlerOutput.files key); for commands whose result is a
                                            # document with no file (IMGWTools stations find, current *, pmaxtp fetch, series summary, ...) the
                                            # per-tool mapper writes the document into output_dir (CSV for tables, JSON otherwise) under this kind
    params: Mapping[str, str] = field(default_factory=dict)   # tool option -> Retman param, only where names differ
                                            # e.g. {"sheet": "area", "bbox": "area", "bbox_crs": "area", "geometry": "area",
                                            #       "layer": "area", "horizontal_crs": "target_crs"}  (error routing)

@dataclass(frozen=True)
class ToolFile:   path: Path; sha256: str | None; version: str | None; status: str | None
@dataclass(frozen=True)
class ToolFailure: unit: str; kind: str; detail: str
@dataclass(frozen=True)
class ToolNotice:  level: Literal["info", "warning", "error"]; code: str; text: str
@dataclass(frozen=True)
class ToolRun:
    command: str
    status: Literal["ok", "partial", "failed", "cancelled"]
    files: tuple[ToolFile, ...]; failed: tuple[ToolFailure, ...]; notices: tuple[ToolNotice, ...]
    document: ToolDocument                  # raw JSON (audit)
    command_line: str                       # format_command(...) incl. environment arguments
    schema: str                             # "kartograf-download/1", "imgw-result/1"

class ToolError(RetmanError):               # raised by clients instead of tool exceptions
    tool: str; code: str; detail: str; hint: str | None
    option: str | None; options: tuple[str, ...]; allowed: tuple[str, ...] | None; details: Mapping[str, Any]

class PlanClient(Protocol):                 # BEFORE plan.confirm(): no network, no writes
    def validate(self, call: CatalogCall) -> None: ...            # validate_command; raises ToolError
    def command_line(self, call: CatalogCall) -> str: ...         # format_command (offline), for audit/--explain
    def lookup(self, call: CatalogCall) -> ToolDocument: ...      # effects-free catalog commands (network False, writes none) plus explicit
                                                                  #   option-conditioned entries (IMGWTools `stations find` only with source="store"); else ToolError("not_offline")

class RunClient(PlanClient, Protocol):      # only in execute() and in Retman.check() (after plan.confirm_check())
    def run(self, call: CatalogCall) -> ToolRun: ...              # data command; writes the store
    def check(self, call: CatalogCall) -> ToolDocument: ...       # freshness plan: check_command; treat EVERY declared check as a network step (TwoStepCheck rule),
                                                                  #   although some are offline: Kartograf WCS cutouts, TERYT-only BDOT10k on an empty store; IMGWTools non-twin commands
    def query(self, call: CatalogCall) -> ToolDocument: ...       # network read-only queries outside run/check/validate:
                                                                  #   Kartograf "elevation availability", IMGWTools "stations find --source live", "current ..."

@dataclass(frozen=True)
class ToolContext:                          # the SAME type for preview, check and handler (GeometryArea/TwoStepCheck adopt it)
    tool: str
    settings: Mapping[str, Any]             # validated [tools.<tool>] table (store_dir, workers, ...)
    project_dir: Path
    output_dir: Path | None                 # None while planning/previewing (no result folder exists yet)
    inputs: Mapping[str, Path]              # validated workspace inputs; {} while planning
    client: PlanClient                      # a RunClient inside execute()/check()
    @property
    def store_dir(self) -> Path: ...        # settings["store_dir"]
    def tool_value(self, param: str, key: str) -> str: ...   # manifest `tool_values` lookup (identity if absent)
    def option_meta(self, param: str, key: str) -> Mapping[str, Any]: ...   # manifest `option_meta` (opaque per-option dict for builders; {} if absent)
```

Plan wdrożenia dodaje do tego kontraktu `ToolDriftError(RetmanError)` (p. 1.4) oraz `run_calls`.

Na narzędzie (`retman/tools/<narzędzie>/`): `client.py` (leniwy import narzędzia przez
`importlib`; implementuje protokoły; mapuje `KartografError`/`IMGWError`, `OSError` → `io_error`,
cokolwiek innego → `internal_error` na `ToolError` przez `raise ... from err`; mapuje dokumenty na
`ToolRun`), `calls.py` (czyste buildery), `handlers.py` (tylko handlery przetwarzające),
`manifest.py`, `pl.toml`.

Kontrakt handlera staje się `handler(params, inputs, output_dir, ctx)`; operacje oparte na
katalogu deklarują `calls` zamiast `handler` i idą przez generyczny runner (wg decyzji końcowej 2
operacja może mieć też `handler`, który sam woła `run_calls`):

```python
def run_calls(op, params, inputs, output_dir, ctx: ToolContext) -> HandlerOutput:
    runs = []
    for call in load(op["calls"])(params, ctx):            # same builder as validate/check/preview
        run = ctx.client.run(call)                          # ToolError on tool errors
        runs.append((call, run))
        if run.status in ("failed", "cancelled"):
            break
    return describe_runs(op, runs)                          # per-tool mapper: files by call.kind, values, warnings, `tool` audit
```

Argumenty środowiskowe dodaje klient z `ctx.settings`, nigdy builder, i powtarza je w
`command_line`: Kartograf `output_dir=store_dir`, `workers`, `update` (`"local"` → `None`) oraz
`cache=MetadataCache(db_path=cache_file)` dla **run, check i query jednakowo** (każde
`check_*`/`check_availability` Kartografa domyślnie ma `cache=True` = plik `.kartograf_cache.db`
w CWD, czyli zapis w folderze projektu użytkownika: nigdy nie używać domyślnej wartości;
sprawdzone: `check_command(..., cache=False)` niczego nie tworzy); IMGWTools dodaje `root`, gdy
komenda ma opcję `root`, a wywołanie jej nie podało. Nigdy nie polegać na zmiennych środowiskowych
(`IMGW_STORE_ROOT`, `KARTOGRAF_*`): N-11, DEV-13.1. Jeden udokumentowany wyjątek: klient
IMGWTools eksportuje `IMGW_DATA_DIR` z `[tools.imgwtools].reference_data_dir` raz, w konstruktorze
i przed pierwszym `import imgwtools`, na czas życia procesu, bo narzędzie nie ma opcji dla pliku
statycznych lokalizacji stacji (ryzyko 19).

Buildery są czyste i nigdy nie dotykają systemu plików. W trakcie planowania
`ctx.output_dir is None`: builder dodaje opcję ścieżki wyjściowej (IMGWTools `series export --path
<output_dir>/series.csv`) tylko gdy `ctx.output_dir` jest ustawiony, więc walidacja w planie
działa bez niej (tryb strumieniowy jest poprawny offline); ścieżki wyjściowe kontroluje Retman,
nie użytkownik. Wejścia względem magazynu (`root`) nigdy nie trafiają do builderów (dodaje je klient).

Dodatki do manifestu (`retman/registry/manifest.py`; reguły `validate_manifest` w nawiasach):

```python
class ParamSpec:     tool_values: NotRequired[dict[str, str]]  # option key -> tool value when they differ ("0_5m": "0.5m", "evrf2007": "EVRF2007")
                     #   [keys are a subset of options, tool values unique; option keys must match ^[a-z0-9_]+$]
                     option_meta: NotRequired[dict[str, dict[str, Any]]]   # option key -> opaque dict read only by builders (IMGWTools: provider, kind, numbering, slug) [keys subset of options, JSON-serializable]
class OperationSpec: handler: NotRequired[str]                  # custom handler; exactly one of handler / calls
                     calls: NotRequired[str]                    # "module:function" -> Callable[[dict, ToolContext], list[CatalogCall]]
                     commands: NotRequired[list[str]]           # catalog commands the calls may use (inventory for drift/doctor) [non-empty with calls]
                     excluded: NotRequired[dict[str, dict[str, str]]]   # param -> {tool value: reason}: deliberate coverage gaps [reason non-empty]
class HandlerOutput: tool: NotRequired[ToolAudit]               # {"tool", "version", "calls": [{command, options, command_line, schema, status, document_file, sha256}]}
# (preview and check keys: GeometryArea / TwoStepCheck reports)
```

(Uwaga: komentarz „exactly one of handler / calls” jest **zastąpiony** decyzją końcową 2 —
„co najmniej jedno”.) Klucze bez kropek wymusza `Texts._lookup` (`retman/i18n/loader.py:60` dzieli
po `.`): `options."0.5m".label` jest nieosiągalne (sprawdzone), więc NMT `0.15m`/`0.5m`/`0.6m`
stają się `0_15m`/`0_5m`/`0_6m` z `tool_values`. (`tool_values` celowo nie nazywa się
`values`/`option_values`: `values` oznacza już krótkie wyniki w `HandlerOutput`/`Result`,
`option_values` mapuje opcję → wartość ekstraktora dla wyborów czytanych kodem, ADR-009.)

### 1.4 Przebieg

```
plan(): operation (model) -> params (model/extractors/questions)            # unchanged
  _populate complete -> preview_operation(op, params, ctx)                  # ctx = ToolContext(client=PlanClient); GeometryArea/TwoStepCheck hook
       1. for call in calls(params, ctx): ctx.client.validate(call)         # OFFLINE; ToolError -> PreviewProblem(params=routed via call.params / option(s),
                                                                            #   key="tool_rejected", args={"detail": ...}) -> params reopened, plan not confirmable
       2. op-specific preview (rows, extra problems)
plan.confirm() -> execute(): ToolContext(client=RunClient) -> run_calls / custom handler -> HandlerOutput -> kind validation -> result.json
(optional) plan.confirm_check() -> Retman.check(): ToolContext(client=RunClient) -> manifest `check` function uses ctx.client.check()/query()
```

Koszt podglądu: import narzędzia w czasie planowania tylko dla narzędzia wybranej operacji:
`import kartograf` ~0,45 s ciepły / 1,15 s zimny, `import imgwtools` ~0,23 s ciepły
(sprawdzone); `validate_command` ~0,2–0,6 ms na wywołanie (sprawdzone). Mediana czasu planu to
10,6 s (PROGRESS), start pozostaje bez importów (ARCHITECTURE 3.2.5).

Reguła kierowania: `ToolError` staje się pytaniem do użytkownika tylko gdy nazywa parametry
Retmana (przez `call.params`, `option` lub `options`). Gdy nie da się nazwać żadnego parametru
Retmana (odrzucona opcja jest ustalona przez operację albo narzędzie odrzuca każdy punkt siatki),
to jest dryf, a nie błąd użytkownika: rzucamy programistyczny `ToolDriftError(RetmanError)`
(„zainstalowane narzędzie nie przyjmuje już tej operacji: uruchom `retman doctor` /
`retman-scaffold --check`”); nigdy nie otwieramy ponownie wszystkich parametrów jako rozwiązania
zastępczego, bo to samo odrzucenie zapętliłoby się. (Mechanizm `reopened` z TwoStepCheck wykonuje
ponowne otwarcie, a jego reguła „nic do ponownego otwarcia → `RetmanError`” jest odpowiednią
gwarancją zakończenia.)

`plan.from_dict` odtwarza `confirmed` z wejścia (`retman/core/plan.py:152`): podział uprawnień
jest tak mocny, jak bramka `confirmed` w `execute()`. To luka W-05 zauważona w raporcie MCP;
naprawić (zerować `confirmed` przy wczytaniu) przed jakimkolwiek zdalnym interfejsem, nie blokuje v0.1.

### 1.5 Mapowanie wyników, błędów i uwag

Kartograf `kartograf-download/1` (jeden kształt dokumentu dla wszystkich 5 typów raportów;
sprawdzone przez zbudowanie `DataReport` offline): `{schema, files[{unit,country,file{path,status,label,sha256,version_path,newer,unverified,same_as}], raw, inputs, failed[{unit,country,error,kind}], stale, superseded, summary, notices[{level,code,text}], ok}`.

| Pole dokumentu | `HandlerOutput` / zachowanie |
|---|---|
| `ok` / `files` / `failed` | status `ok`; `ok=false` z plikami = `partial` (sukces + ostrzeżenia); brak plików = `failed` → `ToolError(code z pierwszego failed.kind)` (`no_coverage`, `year_out_of_range`, `download`) |
| `files[].file.path` (standardowa ścieżka linku w magazynie) | `files[call.kind]` po `validate_file`; `sha256`, `version_path`, `label`, `status` → audyt |
| `files[].file.unverified` = `"unchecked"` | ostrzeżenie `unchecked_local` (tryb domyślny nigdy nie pyta źródła o świeżość, ADR-036 erratum 3): „użyto zapisanych wersji bez sprawdzania nowszych” (zastępuje dzisiejszy tekst `unverified`, którego znaczenie się zmieniło) |
| `failed[]` | ziarnistość to część żądania, a nie arkusz: wieloarkuszowe żądanie PL agreguje twarde porażki w JEDEN `UnitFailure("PL", "PL", "N z M arkuszy nie pobrano (...)", "download")` i raportuje częściowy brak pokrycia WYŁĄCZNIE jako uwagę `no_coverage_some` z liczbami w prozie (`download/data.py:1457-1488` i `1493-1505`; sprawdzone w kodzie, także KartografSpec). Mapowanie: brak plików → `ToolError` (kod z `kind`: `no_coverage`, `year_out_of_range`, `download`); pliki + porażka → sukces, tekst porażki pokazany dosłownie jako ostrzeżenie. Liczb per arkusz nie da się odtworzyć z dokumentu; jeśli autor chce tekstów z liczbami należących do Retmana, builder liczy oczekiwaną liczbę offline publicznymi pomocnikami (`SheetParser(code).get_all_descendants("1:10000")`, sprawdzone: 4 arkusze dla `N-34-130-D-d-2`; `find_sheets_for_bbox`, `find_sheets_for_geometry`), a mapper używa `missing = expected - len(files)`. |
| `notices` | tabela w `client.py`: klucze Retmana tylko dla kodów o ustrukturyzowanym znaczeniu i bez liczb w prozie (`all_nodata`, `cache_disabled`); każda inna uwaga `warning` (jakościowe `incomplete_campaign`, `sheet_crs_mismatch`, `better_coverage`, `link_outside_range`, liczbowe `no_coverage_some`, `cutout_size`, `download_size`, `whole_country_size`) → `tool_notice` z tekstem narzędzia dosłownie; uwagi `info` → tylko audyt. Uwagi o jakości danych istnieją tylko na ścieżce `download_data`. |
| `masked_pixels` wycinka | nie ma go w `kartograf-download/1` (tylko uwaga `all_nodata`; `data.py` go nie wspomina); jest w sidecarze pliku `extra.mask.masked_pixels` (`download/cutout.py:340-375`), do odczytu offline po przebiegu publicznym `kartograf.read_sidecar(path)` („the data file is never opened”, `store.py:517`). Ten sam czytnik daje `data_year`, `campaign`, `full_sheet`, `coverage` do wierszy proweniencji w bloku audytowym. Wzbogacenie opcjonalne; pominięcie wartości/ostrzeżenia `masked_pixels` jest prostym zapasem. |
| values | `file_count`, `bytes`, `new`, `local` (dzisiejsze `missing_sheets` per arkusz nie jest dostępne z dokumentu, zob. `failed[]`) |

IMGWTools `imgw-result/1` (`CommandResult.to_json()`; `status` ok/partial/failed/cancelled; komendy
listujące zwracają `Page`; `series export --path` zwraca wyeksportowaną `Path`, sprawdzone): pliki =
`path` wywołania (rodzaj z wywołania), `notices` łącznie z `license_terms` (sprawdzone na
`series export`) pokazywane dosłownie (IMGWTools `AGENTS.md` reguła 12), `SyncReport.items[].status
== "failed"` → ostrzeżenia, `cancelled` → `Result(ok=False)` z tekstem o anulowaniu. Runner
kontynuuje po wywołaniu `partial` i zatrzymuje się na `failed`/`cancelled`. Komendy, których wynikiem
jest dokument bez pliku (`stations find`, `current *`, `pmaxtp fetch`, `datasets list/providers`,
`series summary`, `store info/scan`): mapper zapisuje dokument do `output_dir` (CSV dla tabel, JSON
w pozostałych przypadkach) i zgłasza go pod `call.kind`; pliki zapisywane przez samo narzędzie
pozostają opcjami `path`/`output`/`plan` (ImgwScope).

**Błędy.** `ToolError.code` to kod z rejestru narzędzia: Kartograf `invalid_input`, `usage_error`,
`invalid_sheet_code`, `download_failed`, `no_coverage`, `year_out_of_range`, `cache_error`,
`invalid_sidecar`, `transform_failed`, `transform_unavailable`, `io_error`, `interrupted`,
`terminated`, `internal_error`, `kartograf_error` (Kartograf `docs/USAGE.md:3303-3385`); IMGWTools
`validation_error`, `not_found`, `conflict`, `source_unavailable`, `missing_dependency`,
`data_error`, `store_unavailable`, `io_error`, `cancelled`, `forbidden`, `internal_error`
(`exceptions.py:65`). Tekst Retmana: `pl.toml` narzędzia `[errors.<code>]` z `{detail}`,
`{option_label}`, `{allowed}`; zapas w rdzeniu `errors.tool_error` („Narzedzie {tool} zglosilo
blad ({code}): {detail}”). Dlaczego nie pokazywać surowych komunikatów narzędzia jako głównego
tekstu: komunikaty Kartografa są po polsku bez diakrytyków (ADR-037 Z5, `DECISIONS.md:2768`) i
zawierają flagi CLI (sprawdzone: „NMT 5m (PL) jest dostepny tylko w EVRF2007 - podano
--vertical-crs KRON86; dostepne w KRON86: 0.5m, 1m”); IMGWTools mówi wprost „decide by `code`, not
by the Polish `detail`” (`AGENTS.md:21`). Cytowane w `{detail}` pozostają przydatne (wymieniają
poprawne alternatywy). `result.error` to dziś `str(err)` (`manifest_adapter.py:55`): staje się
zmapowanym tekstem; surowe `{code, message/detail, hint, details}` idą do `result.json`.

### 1.6 Magazyny, `output_dir` i konfiguracja (D5)

Fakty: `output_dir` Kartografa TO magazyn wersjonowany (niezmienne wersje + sidecary, ścieżka
standardowa = twardy link do `version_path`, ADR-036); `root` IMGWTools to trwały magazyn między
komendami, a jego roczne archiwa są ogólnopolskie (`AGENTS.md` reguła 7), bez twardych linków
(IMGWTools ADR-001 D1). Magazyn per wynik (dzisiejszy `output_dir`) pobierałby wszystko od nowa i
odbierał sens `update`; notatka w PROGRESS o CIFS „database is locked” dla cache metadanych w
folderze wyniku jest tego objawem.

```toml
# retman.toml (template written by `retman init`; both paths on one disk, chosen once, written in full: no hidden default, N-11)
[tools.kartograf]
store_dir  = '/data/retman/kartograf'                 # run_command(output_dir=...)
cache_file = '/home/<user>/.local/share/retman/kartograf_cache.db'   # MetadataCache(db_path=...); local disk (CIFS risk)
workers    = 4                                        # download_data defaults to 4, download_landcover to 1 (verified): always explicit
update     = "local"                                  # use stored versions, download only what is missing; never asks sources for freshness
[tools.imgwtools]
store_dir          = '/data/retman/imgwtools'          # root option of every store/series/pmaxtp command; initialised by `retman init` (store init)
reference_data_dir = '/data/retman/imgwtools-reference' # exported as IMGW_DATA_DIR once, in the client constructor before the first `import imgwtools` (static station locations for `store catalog`); replaces the tool's ambient ./data lookup (risk 19)
```

* Wyniki wskazują pliki magazynu przez ścieżkę bezwzględną + SHA-256 + `version_path`; Retman nic
  nie kopiuje. Wymaga to: `execute_operation` przyjmuje pliki pod `output_dir` LUB w deklarowanym
  magazynie narzędzia (`manifest_adapter.py:34` odrzuca dziś wszystko poza `output_dir`);
  `pipeline.py:975` zapisuje ścieżki względne względem projektu (`relative_to(project_dir)` rzuca
  dla ścieżek spoza) → względne wewnątrz projektu, bezwzględne z `"store": "<narzędzie>"` w
  przeciwnym razie; `Workspace.find_by_kind` już działa z ścieżkami bezwzględnymi
  (`project_dir / absolute` = absolute). Same handlery nadal piszą tylko do `output_dir`.
* Pełny dokument narzędzia każdego wywołania zapisywany jest jako
  `output_dir/tool_<n>_<command>.json` (wewnątrz folderu wyniku), z odsyłaczem z `result.json`
  i SHA-256: pełna proweniencja bez rozdymania `result.json`.
* `retman doctor`: magazyn istnieje i jest zapisywalny, a jego ścieżka NIE ma składnika
  będącego dowiązaniem symbolicznym (IMGWTools `store/writer.py:123-133` odrzuca każdą część
  korzenia magazynu będącą symlinkiem i każde `..`; `retman init` musi zapisać rozwiązaną ścieżkę
  bezwzględną), znacznik magazynu IMGWTools (`imgw-store.json`) obecny (inaczej
  `store_unavailable`: wskazówka `retman init`), `pyarrow` importowalny, gdy operacje serii są
  włączone (`imgwtools[store]`), ścieżka cache na dysku lokalnym; z `--deep` sonda platformowa
  (`imgwtools.testing.build_fixture_store` w katalogu tymczasowym, offline, ~1,7 s), bo zapisy
  magazynu w IMGWTools `31e96fa` działają tylko na Linuksie (D8; decyzja końcowa 3).

### 1.7 Testy, mypy, haki, anulowanie

* `FakeToolClient` (`retman/testing.py`, jak `FakeDecisionBackend`): zapisuje `(method, call)`,
  zwraca gotowe `ToolRun`/dokumenty; asercje „golden-call” `(command, options)` per operacja;
  asercja braku `run/check/query` przed potwierdzeniem. Nagrane prawdziwe dokumenty leżą w
  `tests/fixtures/<narzędzie>/` (CLAUDE.md, Tests: fixtures from real responses). Istniejące 8
  testów przypina usunięte wnętrzności; zastąpić (DEV-10.5: nigdy nie przypinać szczegółów
  implementacji). Zachować testy handlera rozpakowującego SHP.
* IMGWTools: `imgwtools.testing.build_fixture_store(root, variant=...)` + prawdziwe `run_command`
  offline (sprawdzone: cała sonda, razem z budową magazynu, trwała 1,7 s z `series summary`,
  `series export` → CSV, uwagą `license_terms`, siecią zablokowaną). Wymaga `imgwtools[store]`
  (pyarrow).
* Zgodność (p. 2.4) to jedyny test wymagający prawdziwego narzędzia offline; `pytest.importorskip`.
* mypy: TypedDicty Retmana dla dwóch rodzin dokumentów; narzędzia przez `importlib.import_module`
  → bramka nie zależy od zainstalowanych narzędzi; zachować override dla `kartograf`, dodać `imgwtools`.
* Haki: v0.1 nie przekazuje `on_progress` (brak kanału UI; handlery nie mogą drukować) ani
  `on_notice` (uwagi są w zwracanym dokumencie); `cancel` (tylko IMGWTools) = brak: Ctrl-C rzuca
  `KeyboardInterrupt`, kod wyjścia 3 (ARCHITECTURE 6.4). Bezpiecznie: wersje Kartografa są
  zatwierdzane atomowo (USAGE 9.3, kod 130), IMGWTools nigdy nie publikuje częściowej wersji
  (`docs/ARCHITECTURE.md:224`). Zarezerwować `ToolContext` na późniejsze `on_progress`. Ryzyko:
  `KeyboardInterrupt` omija `except Exception` w `execute_operation`, więc dla przerwanego
  przebiegu nie powstaje `result.json` (W-15 tego chce); poza zakresem.

---

## 2. Q2: `retman-scaffold`: szkice i kontrola dryfu

### 2.1 Co dają katalogi (wszystko sprawdzone na zainstalowanych 0.8.0 / 3.0.0)

| Potrzeba | Kartograf | IMGWTools |
|---|---|---|
| Komendy, parametry, wymagane | `get_catalog(params=True)`: 41 komend, 12 komend danych (`data_commands()`); `ParamInfo`: `name`, `argument`, `kind`, `required`, `allowed`, `default`, `accepts`, `task`, `description` (polski ASCII) (`catalog/model.py:31`) | `command_schema(lang=...)`: 37 schematów JSON z `properties`, `required`, `enum`, `minimum`/`maximum`, `pattern`, `dependentRequired`, `oneOf`, `x-imgw` (`commands.py:2834-2877`); `description`/`help` także po angielsku (`lang="en"`) |
| Wybory | `allowed` jest SUMĄ po produktach i krajach: `resolution` ma 14 wartości, `vertical_crs` 3 (`EVRF2007`, `KRON86`, `Bpv`), `format` 10 | `enum`; enumy `dataset`: 7 wartości dla komend store/series (mieści się w jednym wyborze), 12 dla `datasets files/download` (> 9: nie może być jednym wyborem Retmana); rejestr ma 17 zbiorów |
| Reguły między parametrami | `constraints`: `one_of`, `requires`, `excludes`, `applies_to` (mapuje na `depends_on`), `required_when`; tylko dokumentacyjne | `dependentRequired`, `oneOf`, proza w `x-imgw.rules` |
| Dokładna macierz poprawnych wartości | `list_sources(group="elevation")` → wiersze `select` (offline) = (product, country, format, resolution, vertical_crs); równa się temu, co akceptuje `validate_command` (sonda niżej) | rejestr `datasets(kind=, provider=)` |
| Skutki | `effects` per komenda | `x-imgw.network`, `x-imgw.writes`, kształt/typ `result` |
| Błędy / uwagi | `get_catalog(tables=True).errors` (kody, kody wyjścia); kody uwag to stałe w `kartograf/notices.py` (nie deklarowany rejestr) [WNIOSEK: stabilne] | `ERROR_CODES`; kody uwag to literały tekstowe, bez rejestru |
| Przykłady | walidowane testami samego narzędzia (`examples`) | przepływy w `AGENTS.md` (walidowane) |

### 2.2 Generowane a pisane ręcznie

| Element | Źródło | Generowany? |
|---|---|---|
| `id` operacji, `category` | id komendy / grupa | tylko szkic (autor zmienia nazwy; category = grupa; > 9 operacji wymaga rozpoznawania dwuetapowego) |
| `commands`, zalążek `calls` | id komendy + opcje `--fix` | tak (zalążek z jedną linią na opcję) |
| nazwy parametrów, `type`, `required` | `kind`/`required` katalogu; typ/required ze schematu IMGW | tak |
| `options` wyboru, `tool_values` | `allowed` zawężone sondą (niżej); klucze zsluggowane, kropki → `_` | tak; > 9 opcji → znacznik `SPLIT_REQUIRED` |
| `depends_on` | `applies_to`/`required_when` z jednowartościowym `when`; sonda znajduje opcje, które stają się N/D (NMT `100m` bez `vertical_crs`) | tak |
| `range` | IMGW `minimum`/`maximum` | tak |
| `accepts`, `extractor` | rodzaje `bbox`/`path`/`sheet` → `area`; listy `year` → zalążek `period` | sugerowany zalążek |
| `description` (angielski) | IMGWTools `lang="en"`; Kartograf ma tylko polski ASCII → `TODO` + polski tekst jako komentarz | częściowo |
| rodzaje `outputs` | nazwy produktów → rodzaje kandydujące | tylko wskazówka |
| kolejność pytań, klucz `unspecified` | kolejność w manifeście | klucz generowany, tekst ręcznie |
| **`pl.toml`** `label`, `question`, `model_question`, `label`/`description` opcji (synonimy, nazwy angielskie), `example`, `help`, teksty `[errors]`/`[warnings]` | polska proza ASCII z katalogu jako komentarze `#` | **tylko szkielet kluczy, wartości `TODO`; polski z diakrytykami i synonimami ręcznie** (ARCHITECTURE 3.2.3 tabela, ADR-007/008). Test odrzuca każdy znacznik `TODO` w zatwierdzonym `pl.toml`. |
| ekstraktory, logika semantyczna builderów, handlery przetwarzające, komendy eval, które operacje wystawić | — | ręcznie |

Nigdy nie nadpisuje zrecenzowanych plików: domyślnie stdout, `--write` tworzy
`retman/tools/<narzędzie>/_drafts/<op>.{py,toml}` (w `.gitignore`).

### 2.3 CLI i przykład szkicu

```
retman-scaffold list <tool>                               # catalog commands + which operations expose them + suggested classification (x-imgw / effects)
retman-scaffold draft kartograf "elevation download" --fix product=nmt --only sheet,resolution,vertical_crs --id download_dem_sheet
retman-scaffold --check [--tool kartograf] [--json] [--require-tools]     # drift check; exit 0 clean (INFO ok), 1 errors, 2 usage
```

`draft` dla wycinka NMT arkuszowego wyemitowałby (tabela par pochodzi z sondy, p. 2.5):

```python
{"id": "download_dem_sheet", "category": "spatial_data", "description": "TODO ...", "inputs": [], "outputs": ["dem"],   # TODO kind
 "commands": ["elevation download"], "calls": "retman.tools.kartograf.calls:download_dem_sheet",
 "params": [
   {"name": "area", "type": "free", "extractor": "area", "accepts": ["sheet"], "required": True},
   {"name": "resolution", "type": "choice", "required": True,                      # 7 options <= 9
    "options": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m", "100m"],
    "tool_values": {"0_15m": "0.15m", "0_5m": "0.5m", "0_6m": "0.6m"}},                # identity entries omitted
   {"name": "vertical_crs", "type": "choice", "required": True, "options": ["evrf2007", "kron86"],
    "tool_values": {"evrf2007": "EVRF2007", "kron86": "KRON86"},
    "depends_on": {"resolution": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m"]}}],        # 100m: validate_command accepts it without vertical_crs
}
# valid pairs (resolution/vertical_crs): 0.15/EVRF2007  0.5/EVRF2007,KRON86  0.6/EVRF2007  1/EVRF2007,KRON86  5/EVRF2007  10/EVRF2007  100/-   (NMT, PL ASC grids)
```

### 2.4 Semantyka kontroli dryfu (`retman-scaffold --check`)

Działa per zainstalowane narzędzie, którego wersja jest w `supported_versions` (inaczej SKIP;
`--require-tools` zamienia brak narzędzia na błąd, dla CI). Wszystko offline.

| ID | Kontrola | Ważność |
|---|---|---|
| X1 | każda `commands[*]` istnieje w zainstalowanym katalogu; buildery emitują tylko zadeklarowane komendy | błąd |
| X2 | **zgodność siatki:** siatka = iloczyn kartezjański opcji wyborów (+ pominięte, gdzie opcjonalne/nieaktywne wg `depends_on`) × próbki parametrów wolnych (wartości z kompletnych wpisów operacji w `retman/eval/commands.jsonl`, już walidowanych względem manifestów); każdy punkt → prawdziwe `calls()` → `PlanClient.validate`. Odrzucenia klasyfikowane z `ToolError`: `option` nieobecna w wywołaniu = *brak wymaganej opcji* = dryf; `option` nieznana katalogowi lub nieznana komenda = dryf; `option`/`options` obecne w wywołaniu (wartość lub para odrzucona w tym punkcie siatki) = INFO macierz, bo siatka kartezjańska z konstrukcji zawiera niepoprawne pary (np. 5 m + KRON86) — dopiero X3/X4 zamieniają je w błędy | błąd |
| X3 | martwa opcja: opcja manifestu akceptowana w żadnym punkcie siatki | błąd |
| X4 | **pokrycie:** dla każdej związanej opcji każda wartość `allowed` katalogu NIEoferowana i spoza `excluded` jest sondowana przez nadpisanie tej opcji w każdym wywołaniu siatki; zaakceptowana w którymkolwiek punkcie = luka pokrycia. Uwzględnia zakres z konstrukcji (np. `resolution=2m` jest odrzucane dla PL NMT, `format=GML` wymaga `year`, którego operacja nie wystawia) | błąd |
| X5 | przestarzały wpis `excluded` (wartości nie ma już w katalogu / nie jest akceptowana nigdzie) | ostrzeżenie |
| X6 | opcja wymagana w katalogu vs `required` w manifeście; `default` w manifeście na opcji wymaganej w katalogu (ADR-006) | ostrzeżenie |
| X7 | skutki: komendy używane przez `lookup` są wolne od skutków (`network False`, `writes none`) albo na jawnej liście dozwolonych klienta dla opcji warunkowych (weryfikowane offline testami pod nagrywającą blokadą sieci); komendy z `network` wymagają zadeklarowanego `check` (TwoStepCheck) albo jawnej notatki | błąd |
| X8 | kody błędów narzędzia bez tekstu `[errors]` w `pl.toml`; `schema` dokumentu spoza znanego zbioru (`/2`) | błąd |
| X9 | komendy danych katalogu, do których nie odwołuje się żadna operacja (raport „jeszcze niewystawione”, odpowiedź na „WSZYSTKO z IMGWTools”) | info |
| X10 | operacje bez próbek eval dla parametrów wolnych | ostrzeżenie |

Istniejące `validate_manifest` już pokrywa tłumaczenia, liczbę opcji ≤ 9 (`manifest.py:141-144`) i
liczbę operacji (`loader.py:94`). Miejsca uruchamiania: moduł pytest
(`tests/tools/test_conformance.py`, parametryzowany narzędzie/operacja, `importorskip`), macierz
CI (najstarsza/najnowsza w zakresie + nocnie na `develop`/`slave` narzędzi; ARCHITECTURE 3.2.7)
oraz lekka linia w `retman doctor` (X1, X4 bez siatki), żeby użytkownik z nowszym narzędziem w
zakresie zobaczył „luka pokrycia: kartograf 0.8.1 oferuje 0.3m”.

### 2.5 Dowody (sprawdzone, offline)

1. **Obecny manifest vs zainstalowany Kartograf** (`/tmp/probe/conformance_probe.py`): siatka
   `{1m,5m} x {evrf2007,kron86}` = 4 punkty; `validate_command` odrzuca `(5m, kron86)` z
   `invalid_input`, `options=('resolution','vertical_crs')`; manifest dziś oferuje parę, którą
   narzędzie odrzuca (wychodzi dopiero w czasie handlera). Luka pokrycia względem macierzy PL NMT
   ASC (8 par z układem wysokościowym): brak `(0.15m,EVRF2007) (0.5m,EVRF2007) (0.5m,KRON86)
   (0.6m,EVRF2007) (10m,EVRF2007)` oraz `100m` bez układu wysokościowego.
2. **Sonda przez walidację odtwarza rejestr** (`/tmp/probe/coverage_by_validation.py`): suma
   `allowed` katalogu (14 rozdzielczości × {EVRF2007, KRON86, Bpv, pominięte}) przez
   `validate_command` akceptuje dokładnie 9 par NMT i 5 par NMPT, identycznych z wierszami `select`
   z `list_sources(group="elevation")`; 60 wywołań = 35 ms (0,18–0,59 ms/wywołanie). Macierz nie
   wymaga więc kodu specyficznego dla rejestru ani tabeli w manifeście.
3. **Klasyfikacja `check_command`** (gniazda zablokowane): Kartograf `check_command("elevation
   download", ...)` dla arkusza próbuje DNS (krok sieciowy); dla wycinków WCS i BDOT10k tylko po
   TERYT na pustym magazynie jest offline, `check_availability` jest siecią (TwoStepCheck, sprawdzone
   osobno). IMGWTools `check_command` dla `stations find`, `datasets download`, `pmaxtp fetch`
   zwraca plan (pozycje `unverifiable`/`missing`) bez sieci; jego bliźniaki (`store check`/`sync`,
   `project check`) listują/HEAD-ują serwery (`AGENTS.md:141`). `validate_command` jest offline w obu.
4. Dodatek A: wszystkie cztery obecne operacje Retmana przechodzą przez
   `kartograf.validate_command` z kształtami wywołań wymienionymi tam.

---

## 3. Q3: opcje statyczne czy wyprowadzane w czasie ładowania

**Decyzja: statyczne, recenzowane, w manifeście. Nigdy nie wyprowadzamy `options` z zainstalowanego
katalogu w czasie ładowania.** Dryf jest wykrywany (CI, doctor) i wymuszany jako niezmiennik
pokrycia, a nie po cichu pochłaniany.

Powody (każdy z dowodem):
1. **Każda opcja potrzebuje polskich tekstów, inaczej całe narzędzie się nie załaduje.**
   `validate_manifest` wymaga `label` (+ `description` dla wyborów decydowanych przez model, +
   `unspecified`) per opcja (`manifest.py:192-198`); wyprowadzona opcja ich nie ma, a tekst polski
   pisany maszynowo naruszyłby ARCHITECTURE 1.3 i ADR-007 (synonimy i nazwy angielskie pochodzą od autora).
2. **Katalog nie ma kształtu opcji Retmana.** `allowed` dla `resolution` to suma 14 wartości po
   PL/CZ/archiwach (sprawdzone) wobec limitu basala 9 opcji łącznie z `unspecified`
   (`manifest.py:141-144`, ARCHITECTURE 3.4 pkt 1); poprawne wartości zależą od produktu i układu
   wysokościowego i istnieją tylko jako `list_sources`/zachowanie walidatora. Realne listy per
   produkt to 7 (NMT) i 3 (NMPT): statyczne listy per operacja się mieszczą, suma nie.
3. **Powtarzalność i zbiór eval.** `retman/eval/dataset.py:validate_commands` sprawdza oczekiwane
   parametry względem dostarczonych manifestów; basal jest wrażliwy na kolejność (ARCHITECTURE 3.4
   pkt 3); kolejność i zawartość katalogu zmieniają się między wersjami narzędzi. Opcje dynamiczne
   uzależniłyby metryki i decyzje od instalacji i złamały ARCHITECTURE 3.2.3 pkt 3 („opisy zmieniaja
   sie tylko swiadomie”).
4. **Ładowanie offline i bez importów.** Loader waliduje manifesty/tłumaczenia bez importowania
   narzędzi i pomija niezainstalowane (`loader.py:71-93`, ARCHITECTURE 3.2.5);
   wyprowadzanie importowałoby każde zainstalowane narzędzie w każdym procesie (0,45 s Kartograf,
   0,23 s IMGWTools ciepły) i pozwoliło zepsutemu narzędziu zatruć ładowanie manifestów.
5. **N-11 nie przemawia za listami dynamicznymi.** ARCHITECTURE 9.1: manifesty i tłumaczenia to
   kod, nie konfiguracja; N-11 zabrania ukrytych *ustawień/wartości domyślnych*, którymi tu są
   `workers`, `cache`, `update`, ścieżki magazynów (wszystkie w `[tools.*]`). Lista brana po cichu
   z dowolnie zainstalowanego narzędzia jest gorzej recenzowalnym wyborem.
6. **Klucze opcji i tak nie mogą być wartościami narzędzia:** kropki psują wyszukiwanie tłumaczeń
   (sprawdzone), wielkość liter jest inna (`evrf2007` vs `EVRF2007`).

### 3.1 Czego wymaga „WSZYSTKIE rozdzielczości” (sprawdzona macierz, siatki ASC PL dla NMT/NMPT)

| Produkt | Rozdzielczości (pary z układem wysokościowym) |
|---|---|
| NMT (9 par) | 0,15 m EVRF2007; 0,5 m EVRF2007 i KRON86; 0,6 m EVRF2007; 1 m EVRF2007 i KRON86; 5 m EVRF2007; 10 m EVRF2007; 100 m BEZ układu wysokościowego (pliki XYZ województw, nie ASC) |
| NMPT (5 par) | 0,5 m EVRF2007 i KRON86; 0,6 m EVRF2007; 1 m EVRF2007 i KRON86 |

Konsekwencje dla manifestu:
* Opcje rozdzielczości NMT (7): `0_15m 0_5m 0_6m 1m 5m 10m 100m` (+ `unspecified` = 8 ≤ 10 OK);
  NMPT: `0_5m 0_6m 1m`. W `download_sheet_hierarchy` rozdzielić na `resolution` (`depends_on` product
  `dem`) i `resolution_dsm` (`depends_on` product `dsm`): istniejące `depends_on`, istniejące
  walidatory, builder mapuje oba na opcję narzędzia `resolution`.
* `vertical_crs` po `resolution`, `depends_on` wszystkie rozdzielczości oprócz `100m` (inaczej
  Retman zadawałby pytanie, którego odpowiedź builder musiałby po cichu odrzucić).
* Niepoprawne pary (np. 5 m + KRON86) obsługuje ogólny podgląd: model dostaje listę sumaryczną (żeby
  rozpoznać, co mówi polecenie), `validate_command` odrzuca parę, adapter otwiera ponownie oba
  parametry z `error` = „tool_rejected {detail}” (detail narzędzia wymienia poprawne alternatywy).
  Tabeli `combinations` w v0.1 nie ma. Wyzwalacz do dodania jej później: rundy konfliktów widoczne
  w `retman-eval` (`expect_clarify`) lub uwagi testerów; scaffold już potrafi wydrukować tabelę par.
* `100m` zwraca pliki XYZ województw: `kinds.KINDS["dem"]` przyjmuje tylko `.asc`/`.tif`
  (`kinds.py:18`), a `validate_file` traktuje każdy sufiks inny niż `.asc`/`.tif`/`.gpkg` jako
  Shapefile (`kinds.py:57-60`), więc walidacja musi stać się per sufiks (ImgwScope potrzebuje tej
  samej zmiany dla nowych rodzajów): albo rozszerzyć `dem` o `.xyz` + walidator (brak nagłówka:
  sprawdzić, że pierwszy wiersz ma 3 liczby), albo wpisać `100m` do `excluded` z tym powodem do
  czasu wdrożenia. Decyzja autora 3 mówi: wszystkie; rekomendacja = włączyć (rozszerzyć rodzaj);
  decyzja końcowa 7: rodzaj `dem_archive` dla NMT 100 m.
* Zbiór eval: dodać polecenia dla nowych rozdzielczości (ARCHITECTURE 13.1 pkt 10); scaffold wypisuje,
  które opcje nie mają polecenia eval.

### 3.2 Niezmiennik pokrycia

`X4` przerywa CI, gdy zainstalowane narzędzie oferuje (w zakresie operacji) wartość, której
manifest ani nie oferuje, ani nie wymienia w `excluded` z powodem. Efekt: nowe wartości narzędzia
nie pojawią się niezauważone, a „wszystkie rozdzielczości” pozostaje prawdą z konstrukcji.
Użytkownicy z nowszym narzędziem w zakresie zobaczą lukę w `retman doctor` zamiast błędnego planu.

---

## 4. Wpływ na pliki Retmana (sugerowana kolejność)

1. `retman/registry/manifest.py`: nowe klucze (`calls`, `commands`, `tool_values`, `excluded`,
   `HandlerOutput.tool`), reguły `validate_manifest` (co najmniej jedno z `handler`/`calls` — wg
   decyzji końcowej 2, regex klucza opcji, spójność `tool_values`, kształt `excluded`).
   `registry/loader.py`: dopuścić operacje bez `handler`.
2. `retman/adapters/catalog.py` (nowy), `retman/adapters/manifest_adapter.py` (`ToolContext` z
   `PlanClient` dla podglądu i `RunClient` dla execute/check, dozwolone korzenie plików =
   `output_dir` + magazyny narzędzi, `ToolError` → tekst `Result.error`, audyt `tool`;
   `preview_operation` wspólne z GeometryArea/TwoStepCheck), `retman/exceptions.py` (`ToolError`).
3. `retman/core/pipeline.py`: obsługa problemów podglądu/walidacji (wspólna), zapis ścieżek `:975`
   (względne w projekcie, inaczej bezwzględne + `store`), blok `tool` w `result.json`;
   `retman/core/workspace.py`: nic dla lookup (ścieżki bezwzględne już działają). `retman/cli.py:137`
   drukuje tylko `result.summary`: `Result.warnings` nigdy nie są pokazywane (sprawdzone: brak
   odwołań do `warnings` w `cli.py`), więc wydrukować je po podsumowaniu (uwagi licencyjne
   dostawców są obowiązkowe, IMGWTools `AGENTS.md` reguła 12).
4. `retman/config.py`, `config_template.toml`: `[tools.kartograf]`, `[tools.imgwtools]` (typowane
   ustawienia, problemy `ConfigError`); `retman init` zapisuje obie ścieżki i uruchamia `store init`
   dla IMGWTools po zgodzie; `retman/doctor.py`: magazyny, `pyarrow`, lekka zgodność.
5. `retman/tools/kartograf/`: `manifest.py` (`supported_versions=">=0.8.0,<0.9"`, nowe
   parametry/opcje, `tool_values`, `calls`, `commands`), `calls.py`, `client.py`, `handlers.py`
   (rozpakowanie SHP + handler ortofotomapy, decyzja końcowa 1), `pl.toml` (opcje, `[errors.*]`,
   `[warnings.*]`; usunąć teksty „geometria odrzucona” i stałe 1 m/EVRF2007).
6. `retman/tools/imgwtools/` (nowy): ten sam układ; `source = "imgwtools[store] @
   git+https://github.com/Daldek/IMGWTools"` (wskazówka doctora już cytuje `{source}`, klucze doctora
   w `pl.toml`), nowe rodzaje.
7. `retman/kinds.py`: `.xyz` dla `dem` (100 m) i rodzaje wyników IMGWTools (ARCHITECTURE 17.2).
8. `retman/testing.py`: `FakeToolClient`; `tests/tools/<narzędzie>/` (buildery, zgodność, mappery z
   `tests/fixtures/<narzędzie>/*.json`), `tests/tools/kartograf/test_handlers.py` (zastąpić),
   `tests/adapters/` (uprawnienia: brak `run/check/query` przed potwierdzeniem),
   `tests/fixtures/dummy_tool` (handler 4-argumentowy).
9. `retman/devtools/scaffold.py` + `retman/devtools/readers/{kartograf,imgwtools}.py`;
   `pyproject.toml`: skrypt `retman-scaffold`, grupa `tools` (`kartograf @ git+...@v0.8.0`,
   `imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@v3.0.0`; do czasu tagów użyć SHA
   commitów, p. decyzja końcowa 3), override mypy dla `imgwtools`.
10. `retman/i18n/pl.toml`: `dialog.tool_rejected`, `errors.tool_error`, `warnings.tool_notice`,
    etykiety wierszy planu.

## 5. Dokumenty do zmiany (dokumenty po polsku, ten raport także)

* **ARCHITECTURE:** 1.2 (katalog czytany tylko przez narzędzia deweloperskie i walidację offline);
  3.1 lista modułów (`adapters/catalog.py`, `devtools/readers`, katalogi narzędzi dostają
  `client.py`, `calls.py`); 3.2.2 drzewo/tabela; **3.2.3 przepisać** (czytniki katalogu; generowane
  vs ręczne; semantyka dryfu; czytnik sygnatur/`griffe` odłożony do pierwszego narzędzia bez
  katalogu, v0.2); **3.2.4** (handler + builder wywołań, `ToolContext`, reguły 1 i 5 przeformułowane:
  publiczne API = warstwa komend i publiczni pomocnicy; zapisy do `output_dir` lub przez narzędzie
  do jego magazynu); 3.2.5 (podgląd z walidacją; `RunClient` dopiero po potwierdzeniu); 3.2.6
  (`dem` `.xyz`, rodzaje IMGWTools); 3.2.7 (zakresy, zgodność w CI); 3.2.8; 4.1 przykład; 4.3
  (`tool_values`, `calls`, `commands`, `excluded`; klucze bez kropek); 5.4 (blok `tool`, pliki poza
  projektem); 6.1 (wiersz: narzędzie odrzuciło kombinację → parametry otwarte ponownie); 6.3
  (`--explain` pokazuje linię komendy narzędzia); 7.2 (linie doctora); 9.1 (`[tools.*]`); 9.3
  (scaffold nie wymaga nowej zależności); 9.4 (`--with "imgwtools[store] @ ..."`); 10 (magazyny poza
  projektem); 11 (wiersz v0.1); **12 pkt 1 zamknięty** (sprawdzone: funkcje Kartografa nie są typowane
  `Literal`, IMGWTools nie ma `py.typed`; wybory pochodzą z katalogów).
* **PRD:** 7.2 (lista operacji wg decyzji autora); bez nowych W/N; sformułowanie W-09 („wyniki to
  pliki w folderze wyników” → pliki w magazynach narzędzi wskazywane z folderu wyników).
* **DECISIONS:** ADR „Handlery przez katalog komend narzędzi” (D1–D5, D8) i ADR „Manifesty
  statyczne; `retman-scaffold` z katalogów” (D6–D7, D9), oba z adnotacją o delegacji wg decyzji autora
  8 i sprawdzonych faktach powyżej; erratum do ADR-003 (zakresy, grupa tools) i ADR-006 (nowe
  wartości pytane; bez wartości domyślnych). Numery ADR: raport MCP proponuje ADR-012; resztę
  przydziela Main.
* **Dawne STANDARDS** (usunięte, dziś `CLAUDE.md` i ARCHITECTURE 13): 6.1 (grupa tools), 10.4 (testy handlerów: fałszywy klient, nagrane dokumenty,
  magazyn fikcyjny, zgodność), 17.1 (szkic z katalogu; zgodność), 18 (lista kontrolna).
  **CLAUDE.md:** linia bramki `retman-scaffold --check` bez zmian, dodać „narzędzia wołamy przez ich
  katalog komend”. USAGE, CHANGELOG, PROGRESS.

## 6. Ryzyka, otwarte kwestie, [WNIOSEK]

1. **Więcej niż 9 operacji.** `loader.py:94` rzuca powyżej 9 operacji (`len(operations) + 1 > 10`,
   `out_of_scope` wliczone): 4 operacje Kartografa + 5–6 IMGWTools (dodatek B) = 9–10 już leży na
   limicie lub nad nim, a cokolwiek więcej (HSG, gleby, produkty pokrycia terenu, Hydrolog) go
   przekracza. Rozpoznawanie dwuetapowe wg `category` (ARCHITECTURE 3.4 pkt 1) jest warunkiem
   wstępnym decyzji autora 5 i nie jest jeszcze zaimplementowane (decyzja końcowa 7: kategoria → operacja).
2. **`color` ortofotomapy** (D10): nieosiągalny przez warstwę komend; droga przez klasę providera
   przywraca niestabilną powierzchnię — **rozstrzygnięte** decyzją końcową 1 (pytanie o kolor + własny
   handler na providerze tylko dla ortofotomapy). Pozostaje ryzyko stabilności tej jednej powierzchni
   (konstruktory providerów i `DownloadManager` zmieniają się między minorami 0.x): jej pokrycie
   testami zgodności/live jest obowiązkiem adaptera.
3. **`constraints` katalogu są dokumentacyjne** (Kartograf USAGE 9.4): ufać tylko walidatorowi;
   X2/X4 zależą od tego, że `validate_command` jest tak samo ścisłe jak przebieg (deklaruje to
   narzędzie, testy istnieją) [WNIOSEK dla przyszłych wersji].
4. **Minory 0.x mogą zmieniać katalog** (nowa wymagana opcja, nowe kody): łagodzone `<0.9`, nocną
   zgodnością, doctorem; awaria przesuwa się z „TypeError po potwierdzeniu” na odrzucenie w planie.
5. **Tagi niewypchnięte** (v0.8.0, v3.0.0): przypiąć SHA commitów do czasu ich pojawienia się.
   Praca w toku w IMGWTools, widziana jako niezatwierdzona na `fix/archiwista-compat` w chwili
   startu (katalog stacji zyskuje pole `meteo_kind` klimat/opad, które pomogłoby wybrać
   `pl.imgw.meteo_climate_daily` vs `pl.imgw.meteo_precip_daily` dla stacji), może wyjść jako
   3.0.x/3.1 [WNIOSEK: niewydane]; po wydaniu powtórzyć zgodność na otagowanej wersji
   (decyzja końcowa 3: poprawka przenośnego zapisu ma wejść do v3.0.0).
6. **Wspólne magazyny poza projektem:** `retman-output` nie zawiera już danych (sformułowanie PRD
   W-09; dokumentacja); twarde linki Kartografa (ADR-036) mogą zawodzić na CIFS/exFAT i wymagają
   semantyki tego samego wolumenu [WNIOSEK dla Windows]; `cache_file` na dysku lokalnym;
   `store_dir` na udziale sieciowym wymaga testu dymnego (PROGRESS 2026-10-11 „database is locked”).
7. **Serie IMGWTools wymagają `pyarrow`** (`imgwtools[store]`; `import imgwtools` go nie ładuje,
   sprawdzone): `missing_dependency` (kod wyjścia 6) → kontrola doctora + wskazówka instalacji.
8. **Inicjalizacja magazynu IMGWTools to zapis:** robić w `retman init` (za zgodą), raportować w
   doctorze; nigdy po cichu wewnątrz planu.
9. **`check_command` to nie jedna rzecz:** Kartograf = plan świeżości, sieć dla arkuszy i BDOT10k po
   obszarze, offline dla wycinków WCS; IMGWTools = plan offline dla większości komend, sieć dla
   bliźniaków; dostępność to osobny czasownik zapytania (styk TwoStepCheck). Reguła: każdy
   zadeklarowany `check` jest traktowany jako krok sieciowy.
10. **Komunikaty Kartografa to polski ASCII z flagami CLI** (sprawdzone): cytowane tylko jako `{detail}`.
11. **`Plan.from_dict` ufa `confirmed`** (`plan.py:152`): osłabia D2 dla każdego zdalnego
    interfejsu/GUI/MCP (raport MCP).
12. **Przerwane przebiegi** nie zostawiają `result.json` (p. 1.7).
13. **Sformułowanie N-03.** Dokumentacja IMGWTools wymienia Retmana jako konsumenta
    (`docs/ARCHITECTURE.md:245`, `README.md:678`, `CLAUDE.md:587`, spec 2026-10-19 p. 8), a jego
    `docs/PROGRESS.md:281` wymienia `imgwtools.testing` „dla Archiwisty i Retmana” (sam moduł to
    ogólny budowniczy fikstur, docstring: „consumers”; kodu Retmana brak). PRD N-03 mówi, że
    narzędzia nie zawierają „niczego związanego z Retmanem”: autor powinien potwierdzić, że wzmianki
    w dokumentacji o ogólnym konsumencie są dopuszczalne (spec IMGWTools sam mówi „no code for
    Retman in IMGWTools”). Kartograf wspomina Retmana tylko w notatkach badawczych.
14. Niesprawdzone: jakakolwiek żywa ścieżka pobierania przez `run_command` (brak sieci); zachowanie
    na Windows; dokładne rozmiary/czas przebiegu zgodności na dużych katalogach [WNIOSEK: sekundy].
15. **Ostrzeżenia nie są dziś wyświetlane:** `cli.py:137` drukuje tylko `result.summary`, więc
    mapowanie uwag/ostrzeżeń z D3 dociera do użytkownika dopiero po tym, jak CLI zacznie drukować
    `Result.warnings` (zauważył też TwoStepCheck); uwagi licencyjne mają znaczenie prawne dla danych
    IMGW-PIB/CHMI.
16. **Liczby porażek per arkusz nie są ustrukturyzowane** w `kartograf-download/1` (agregowane w
    `_finish_pl_sheets`): dzisiejsze ostrzeżenia Retmana `no_coverage {count,total}` /
    `failed_sheets {count,total}` stają się dosłownym tekstem Kartografa (polski ASCII, wymienia
    arkusze), chyba że autor zechce obliczenia offline `requested - delivered`.
17. **Zapisy magazynu w IMGWTools 3.0.0 (`31e96fa`) działają tylko na Linuksie**
    (`store/writer.py:93-98`, sprawdzone: `_atomic_publish` używa `renameat2(RENAME_NOREPLACE)` i
    rzuca `IMGWStoreConflictError` gdzie indziej; wywołujący `writer.py:650,1045`, `series.py:1145`,
    `catalog.py:212`, czyli publikacja archiwów/wersji, `series build`, `store catalog`), a Retman
    celuje w Windows, Linux i macOS: `store sync`, `series build`, `store catalog` i zapisy magazynu
    za `pmaxtp sync` zawodziłyby poza Linuksem do wydania z przenośnym zapisem (D8). **Decyzja
    końcowa 3: autor włoży poprawkę do v3.0.0**; do tego czasu CI międzyplatformowe dla operacji
    IMGWTools musi iść na wydaniu z poprawką, a dokumentacja musi wskazywać minimalną wersję
    IMGWTools per platforma.
18. **Korzeń magazynu IMGWTools nie może zawierać symlinku** (`store/writer.py:123-133`,
    sprawdzone): symlinkowany katalog domowy, `/data` lub ścieżka macOS `/tmp` kończy się
    `validation_error`; `retman init` rozwiązuje ścieżkę, a doctor sprawdza ją ponownie.
19. **IMGWTools czyta wejścia z otoczenia, które omijają `retman.toml`** (znalezione przez ImgwScope,
    sprawdzone w kodzie): `store catalog` i `check_catalog` czytają
    `$IMGW_DATA_DIR/hydro_stations_locations.csv`, domyślnie `./data/` względem katalogu roboczego,
    czyli folderu projektu Retmana (`store/catalog.py:1313-1333`, wywołania `:1586` i `:1970`). Bez
    pydantic-settings (środowisko `imgwtools[store]`) zmienna jest czytana przy każdym wywołaniu, a
    `.env` w cwd ignorowany; z zainstalowanym pydantic-settings (dowolny dodatek `[cli]`/`[api]` lub
    inny pakiet) `settings = Settings()` budowane jest przy pierwszym imporcie `imgwtools.config` i
    zamrożone: późniejsze zmiany środowiska są ignorowane, `.env` z cwd jest stosowany, a zmienna
    ustawiona przed tym pierwszym importem nadpisuje `.env` (`config.py:12-20`; sondy ImgwScope). To
    koliduje z D5/N-11. Łagodzenie: klucz konfiguracji `[tools.imgwtools] reference_data_dir`; klient
    eksportuje `IMGW_DATA_DIR` RAZ w konstruktorze przed pierwszym `import imgwtools`, na czas życia
    procesu (bez przełączania per wywołanie i bez blokady, więc bezpieczne także dla równoległych
    serwerów); jeśli `imgwtools.config` jest już zaimportowany z innym `data_dir`, zamknąć dostęp
    błędem `ToolError`. `retman doctor` ostrzega o `./data/hydro_stations_locations.csv` i o `.env`
    w projekcie. Właściwa poprawka: jawna opcja w IMGWTools (autor jest właścicielem obu repozytoriów).

---

## Dodatek A: operacje Kartografa jako wywołania katalogu (wszystkie sprawdzone przez `validate_command`, offline)

| Operacja Retmana | Wywołanie | Uwagi |
|---|---|---|
| `download_dem_sheet` | `elevation download {product: nmt, sheet: <code>, resolution, vertical_crs}` rodzaj `dem` | OK dla 1m/EVRF2007, 0.5m/KRON86 (nowe), `100m` bez vertical_crs; grubszy arkusz sam rozwija się do arkuszy 1:10000 |
| `download_sheet_hierarchy` | `dem` → `elevation download {product: nmt, ...}`; `dsm` → `elevation download {product: nmpt, resolution, vertical_crs}`; `orthophoto` → `imagery download {product: orto}` **[wg decyzji końcowej 1: własny handler z `GugikOrtoProvider(color=…)` + `DownloadManager`; `validate_command("imagery download", …)` tylko w podglądzie, bez koloru]**; `sheet` = nadrzędny; `scale` tylko dla arkuszy nadrzędnych PL-2000 | NMPT bez `resolution` jest odrzucane (nowość w 0.8.0); `scale 1:10000` z arkuszem nadrzędnym PL-1992 jest odrzucane; `color` jest nieznaną opcją komendy |
| `download_elevation_cutout` | `elevation download {product: nmt/nmpt, country: pl, bbox: [x0,y0,x1,y1], bbox_crs, cutout: true, horizontal_crs: <target_crs>, vertical_crs}` | `resolution` pominięte (wycinek to tylko 1 m); plik geometrii: `geometry`+`layer` zamiast `bbox` (GeometryArea) |
| `download_bdot10k` | `landcover download {product: bdot10k, teryt / sheet / bbox+bbox_crs / geometry+layer, format: GPKG lub SHP}` rodzaj `topographic_vector` | SHP = ZIP per powiat w magazynie: własny handler rozpakowuje do `output_dir`; `format` jest dla narzędzia opcjonalny, Retman nadal pyta (ADR-006); `GML` wymaga `year` (edycje archiwalne): w `excluded` |

## Dodatek B: katalog IMGWTools 3.0.0: proponowana klasyfikacja (autor potwierdza, co znaczy „WSZYSTKO z IMGWTools”)

Wyprowadzone z `x-imgw` (grupa, `network`, `writes`, kształt wyniku); 37 komend w 8 grupach. Ta tabela
to tylko wejście wyprowadzone z katalogu: listę operacji IMGWTools posiada ImgwScope i tam, gdzie
się różnią, ona wygrywa (kontrakt integracji powyżej od niej nie zależy; zob. decyzja końcowa 7:
26 operacji).

| Klasa | Komendy | Użycie w Retmanie |
|---|---|---|
| Operacje (język naturalny) | `stations find` (sieć tylko dla `source=live`) | `find_stations`; zasila też ekstraktor stacji przez `lookup` z `source=store` (offline) |
| | `current hydro / meteo / synop / warnings / hydro-states` (sieć, bez zapisów) | jedna operacja `fetch_current_data` z wyborem `source` (5 opcji) |
| | `pmaxtp fetch` (sieć, bez zapisów); ścieżka magazynu `pmaxtp sync` + `pmaxtp read` | `fetch_pmaxtp` (metoda POT/AMP; zasila Hydrologa) |
| | złożone `store sync` + `series export --path` (dostawca wybierany gramatyką kodu stacji: 9 cyfr IMGW-PIB, WIGOS CHMI; `stations` wymagane dla CHMI, zabronione dla IMGW-PIB) | `fetch_station_series` → CSV serii w `output_dir` |
| | `store catalog` (sieć, zapisuje) | `build_station_catalog` (jawny krok sieciowy; umożliwia wyszukiwanie stacji offline) |
| | `datasets download` (sieć, zapisuje `replace` do katalogu pobierania) | opcjonalne `download_archives` |
| `lookup` w czasie planowania (offline, bez skutków) | `datasets list / providers / files`, `store info / scan`, `series summary / select / read`, `pmaxtp url / read` | ekstraktory, wiersze podglądu („już w magazynie”), „co jest w moim magazynie” |
| Przygotowanie przez `retman init` / doctor | `store init` | zapis za zgodą, nigdy wewnątrz planu |
| Kroki wewnętrzne / TwoStepCheck | `store check`, bliźniaki `check_*`, `series build` (automatycznie z `series=true`), `store export` | nie są operacjami |
| Wykluczone | `project *` (8), `commands schema / guide` | dublują przestrzeń roboczą/audyt Retmana; `commands schema` używa tylko scaffold |

## Dodatek C: indeks dowodów

Retman: `registry/loader.py:71-94`; `registry/manifest.py:141-159,178-198`;
`adapters/manifest_adapter.py:27-36,55`; `core/pipeline.py:540-590,919-1010`; `core/plan.py:152`;
`i18n/loader.py:60`; `tools/kartograf/handlers.py:27,75-97,117-118,141,163`;
`tests/tools/kartograf/test_handlers.py:57-263`; `tests/conftest.py:38`;
`eval/dataset.py:validate_commands`; `pyproject.toml:40,70`; ARCHITECTURE 3.2.3–3.2.8, 4.1–4.3, 9.1,
9.3, 13.1; CLAUDE.md.
Kartograf (`d7b5369e`): `commands.py:185,278,348`; `catalog/model.py:31,85,108`;
`catalog/build.py:344,388`; `__init__.py:461-488`; `sources/registry.py:304`; `source_info.py:207`;
`docs/DECISIONS.md:2730-2830,4136+`; `docs/DEVELOPMENT_STANDARDS.md:507-523,843-863`;
`docs/USAGE.md:3303-3385,3487-3530`.
IMGWTools (`31e96fa`): `commands.py:2077,2284,2715,2834-2877,2881`; `store/types.py:957,1018,1101`;
`exceptions.py:65,135`; `testing.py:1-60`; `docs/ARCHITECTURE.md:224,226,245`;
`docs/DECISIONS.md:110-118,265`; `docs/superpowers/specs/2026-10-19-agent-support-design.md:554-561`;
`AGENTS.md:15-21,37-48,141,241-257`.
Sondy (offline): `/tmp/probe/conformance_probe.py`, `coverage_by_validation.py`,
`appendix_a_validate.py`, `/tmp/imgwprobe/imgw_fixture_probe.py`.
