# Retman — architektura

> **Status dokumentu:** szkic (2026-10-11, uzupełniony 2026-10-19) · **Licencja:** MIT · **Język dokumentu:** polski
> **Wymagania i zakres produktu:** [PRD.md](PRD.md)

Ten dokument opisuje, **jak** zrealizować wymagania z PRD. Oznaczenia w nawiasach kwadratowych,
np. [W-02] albo [N-03], wskazują wymagania z PRD, które dana część realizuje.

---

## 1. Zasady projektowe

### 1.1. Zasady

| Zasada | Co oznacza w praktyce | Wymagania |
| --- | --- | --- |
| **Narzędzia nic nie wiedzą o Retmanie** | Hydrograf i reszta nie zawierają żadnego kodu, plików ani zależności związanych z Retmanem. Retman korzysta wyłącznie z ich publicznego API Pythona (p. 3.2; nie przez ich serwery MCP, p. 3.2.1). Jedyny możliwy wyjątek w przyszłości: opcjonalny panel czatu w GUI (p. 7.4). | [N-03] |
| **Retman nie zawiera modelu** | Model to osobna usługa (np. LM Studio, Ollama, basal-serve, API dostawcy), z którą Retman łączy się przez API. Kod nie zależy od konkretnego modelu — wybór modelu to tylko konfiguracja (p. 3.3). | [N-02], [N-10] |
| **Liczby liczy kod, nie model** | Model wybiera operację i opcje. Współrzędne, daty, prawdopodobieństwa i inne wartości wyciąga i sprawdza kod. | [W-01], [W-08] |
| **Listy dla wyborów, liczby dla wartości** | Metody czy typy analiz to wybór z listy. Wartości ciągłe (np. prawdopodobieństwo) to liczby, nie listy. | [W-08] |
| **Nie zgadywać po cichu** | Gdy pewność jest za niska albo brakuje danych, Retman dopytuje. Gdy pasuje kilka wcześniejszych wyników, pyta, którego użyć (p. 5.3). Wartości domyślne i wcześniejsze wyniki są zawsze pokazane w planie. | [W-02], [W-04], [W-07] |
| **Zawsze potwierdzenie przed wykonaniem** | Użytkownik widzi plan i zatwierdza go. W wersjach 0.x bez wyjątków (p. 6.3). Potwierdzenia nie da się wczytać z zapisanego planu. | [W-05] |
| **Bez sieci przed potwierdzeniem** | Przed `plan.confirm()` Retman nie woła żadnej funkcji narzędzia z efektem sieciowym ani zapisem: planowanie to ekstraktory w kodzie, walidacja offline przez narzędzie i podgląd planu, a kod planowania widzi tylko połowę offline klienta narzędzia (p. 3.2.4). Sieć dopiero po potwierdzeniu planu albo — jako osobny krok z własną zgodą — w sprawdzeniu dostępności (p. 6.5). Serwer modelu jest poza tą regułą (N-04). | [N-12], [W-17] |

### 1.2. Świadome ograniczenia projektowe

- **Model nie planuje łańcuchów.** Łańcuchy (v0.2) buduje kod na podstawie zależności między
  operacjami, a model wybiera tylko cel i parametry (p. 4.5).
- **Katalogi i dokumentacja narzędzi nie są czytane w trakcie działania.** Służą do szkiców
  i kontroli zgodności opisów (p. 3.2.3); opcje w manifestach są statyczne.
- **Brak trybu wykonania bez potwierdzenia** w wersjach 0.x i brak sieci narzędzi przed
  potwierdzeniem, poza sprawdzeniem dostępności na życzenie.

### 1.3. Język

| Element | Język |
| --- | --- |
| Kod: identyfikatory, nazwy operacji i parametrów, komentarze, docstringi | **angielski** |
| Teksty dla użytkownika i modelu: pytania do basala, opisy opcji, komunikaty, plan | **pliki tłumaczeń** (p. 4.2): polski w v0.1, angielski później |
| README, PRD, ten dokument i inne dokumenty poza kodem | **polski** |

Teksty dla użytkownika i modelu nie mogą być po angielsku w kodzie, bo basal najlepiej działa,
gdy pytania i opcje są w tym samym języku co polecenie (p. 3.4). Dlatego trafiają do plików
tłumaczeń, a kod odwołuje się do nich przez angielskie klucze.

---

## 2. Przegląd działania

Każde polecenie przechodzi przez sześć kroków [W-01], [W-02], [W-04], [W-05], [W-17], [N-12]:

```
 Polecenie użytkownika
        │
        ▼
 1 ROZPOZNANIE OPERACJI ──── model decyzyjny: "którą operację wybrać?" (choice);
        │                    gdy operacji jest więcej niż 9: najpierw kategoria, potem operacja (p. 3.4)
        ▼
 2 PARAMETRY Z LIST ──────── model decyzyjny: "który rodzaj danych? jaka metoda?" (choice)
        │
        ▼
 3 PARAMETRY SWOBODNE ───── kod: ekstraktory (współrzędne, daty, prawdopodobieństwa, stacje, pliki)
        │                    + przestrzeń robocza (wcześniejsze wyniki, rozdz. 5)
        ▼
 4 WALIDACJA I DOPYTANIE ── czego brakuje? co ma za niską pewność? → pytanie do użytkownika;
        │                    kompletny plan sprawdza offline narzędzie (podgląd) — odrzuca → pytanie ponownie
        ▼
 5 PLAN + POTWIERDZENIE ─── "Pobiorę dobowe opady ze stacji Poznań (2000–2020). Wykonać?"
        │                    opcjonalnie `s`: sprawdzenie dostępności (sieć, osobna zgoda, p. 6.5)
        ▼  ─────────────── do tego miejsca bez sieci narzędzi (N-12) ───────────────
 6 WYKONANIE + OPIS ─────── wywołania albo handler w Retmanie → publiczne API narzędzia → wynik
                            → zapis w przestrzeni roboczej → (opcjonalnie) opis po polsku przez model tekstowy
```

### Przykład (pojedyncza operacja, model decyzyjny: basal)

Polecenie: *„Pobierz dobowe opady ze stacji Poznań z lat 2000–2020”*

| Krok | Kto | Wynik |
| --- | --- | --- |
| ① | basal | operacja = `fetch_imgw_data` (pewność 0.96) |
| ② | basal | `variable` = `precipitation` (0.98), `interval` = `daily` (0.94) |
| ③ | ekstraktory | stacja „Poznań” → dopasowanie do listy stacji IMGW; okres = 2000-01-01 – 2020-12-31 |
| ④ | walidator, narzędzie | wszystkie wymagane parametry są, pewności powyżej progów; gdyby nazwie „Poznań” odpowiadało kilka stacji, Retman dopyta, o którą chodzi; kompletny plan narzędzie sprawdza offline (np. rok przed początkiem serii) |
| ⑤ | Retman | pokazuje plan (z wierszami podglądu) i czeka na potwierdzenie; użytkownik może najpierw zlecić sprawdzenie dostępności (`s`) |
| ⑥ | wykonawca wywołań IMGWTools w Retmanie | wykonuje komendy katalogu IMGWTools, zapisuje wynik w przestrzeni roboczej (rozdz. 5) |

> Przykład jest poglądowy: nazwy operacji i parametrów zostaną ustalone razem z listą operacji (PRD).

Gdy operacja wymaga danych, których polecenie nie zawiera (np. przepływ wymaga charakterystyki
zlewni), Retman w v0.1 szuka ich w pliku wskazanym w poleceniu albo we wcześniejszych wynikach
(rozdz. 5). Jeśli ich tam nie ma, informuje, czego brakuje. Automatyczne dokładanie kroków
to łańcuchy w v0.2 (p. 4.5).

---

## 3. Architektura

### 3.1. Moduły

```
src/retman/
├── core/
│   ├── pipeline.py          # steps ①–⑥, main logic; Retman.check() (p. 6.5)
│   ├── plan.py              # Plan object (operation + parameters + confidences + sources, review state, consent)
│   ├── result.py            # Result object (p. 7.3)
│   ├── check.py             # CheckReport: the availability check report (p. 6.5)
│   ├── geometry.py          # geometry files as areas: GeoPackage layers (stdlib sqlite3), checksums (p. 6.1)
│   ├── workspace.py         # project results: numbering, lookup by kind, input selection (ch. 5)
│   ├── journal.py           # project journal and audit data (p. 5.4)
│   ├── collection.py        # optional collection of commands from all projects (p. 5.4, ADR-010)
│   └── dialog.py            # questions and answers, independent of the user interface (p. 6.4)
├── registry/
│   ├── operation.py         # internal Operation and parameter model; two-stage recognition helpers (p. 3.4)
│   ├── manifest.py          # manifest schema, hook output types and validation (p. 4.1)
│   └── loader.py            # loading tool descriptions, checking installed tool versions, category limits
├── adapters/
│   ├── catalog.py           # command layer: CatalogCall, ToolRun, ToolError, PlanClient/RunClient, ToolContext, run_calls (p. 3.2.4)
│   └── manifest_adapter.py  # generic adapter: params → handler/calls → Result; offline preview, availability check
├── tools/                   # descriptions, call builders, clients and handlers for each supported tool (p. 3.2.2)
│   ├── hydrograf/
│   ├── hydrolog/
│   ├── imgwtools/
│   ├── kartograf/
│   └── basichydraulics/
├── devtools/                # retman-scaffold: list, draft and the drift check (p. 3.2.3)
├── kinds.py                 # registry of data kinds and their file validators (p. 3.2.6)
├── i18n/
│   ├── loader.py            # loading translation files
│   └── pl.toml              # Polish texts for core messages
├── backends/                # connections to separately installed models (p. 3.3)
│   ├── base.py              # DecisionBackend and TextBackend interfaces
│   ├── openai_compatible.py # any OpenAI-compatible API: LM Studio, Ollama, vLLM, providers
│   ├── basal.py             # basal-serve API
│   └── native/              # providers with their own API (optional extras, v0.2)
├── extractors/
│   ├── base.py              # Match, Reading, Hint and ExtractionContext: offline facts for context-aware extractors (p. 4.3)
│   ├── text.py              # folding, word spans and typo tolerance shared by the extractors
│   ├── coordinates.py       # points (WGS84, PL-1992 converted in pure Python) and PMAXTP grid cells
│   ├── areas.py             # areas: map sheet codes (godło), bounding boxes, TERYT codes, geometry files (ADR-001, ADR-016)
│   ├── crs.py               # coordinate systems and their role: input rectangle vs result (ADR-009)
│   ├── numbers.py           # Polish numerals and durations (15 min, 2 godziny)
│   ├── probability.py       # exceedance probability and return period (p. 4.4)
│   ├── dates.py             # years, periods and the kind of year (hydrological or calendar)
│   ├── stations.py          # station names and codes → the offline station catalog of the IMGWTools store
│   ├── places.py            # place and river names as search fragments for the station search
│   ├── variables.py         # measured variables checked against the chosen dataset
│   ├── identifiers.py       # names given by the user (e.g. a project task)
│   ├── paths.py             # file paths mentioned in the command
│   └── results.py           # result numbers mentioned in the command, e.g. "#3" (p. 5.2)
├── chains/
│   └── resolver.py          # chain building from input/output dependencies (v0.2)
├── eval/
│   ├── runner.py            # retman-eval: runs the test command set, prints the report (p. 8.2)
│   ├── dataset.py           # loading and validating the test command set (p. 8.1)
│   ├── metrics.py           # quality measures, threshold curve (p. 8.2)
│   ├── report.py            # Markdown report (p. 8.2)
│   └── commands.jsonl       # test command set, shipped as package data (p. 8.1)
├── testing.py               # test helpers: FakeDecisionBackend, FakeToolClient, tool_context (p. 8.3)
├── exceptions.py            # RetmanError hierarchy, e.g. PlanNotConfirmedError, CheckNotConfirmedError (p. 6.3, 6.5)
├── doctor.py                # environment check (p. 7.2)
├── stores.py                # tool stores on disk: checks for doctor, set-up for init (p. 9.1)
├── initialize.py            # retman init: config file, store folders, IMGWTools store (p. 9.1)
├── add_tool.py              # retman add-tool: installs a known tool via uv (v0.5+, p. 9.4)
├── cli.py                   # terminal conversation built on core/dialog.py (p. 6.4)
├── config.py                # central config file: location, loading, validation (p. 9.1)
└── config_template.toml     # the commented template that `retman init` writes (p. 9.1)
```

### 3.2. Adaptery: jak Retman łączy się z narzędziami [N-03], [W-06]

#### 3.2.1. Zasada: narzędzia nic nie wiedzą o Retmanie

Narzędzia nie zawierają żadnego kodu, plików ani zależności związanych z Retmanem.
Wszystko, czego Retman potrzebuje, mieszka w repo Retmana, a z narzędzi korzysta on wyłącznie
przez ich **publiczne API Pythona** — tak samo jak każdy inny użytkownik tych bibliotek.
Serwery MCP narzędzi (`kartograf-mcp`, `imgw mcp`) nie są używane (ADR-018): to cienka nakładka
na te same wywołania biblioteki, dokładałaby zależności, a bramki W-05 i N-12 trzeba by
utrzymywać w osobnym procesie z jego własną polityką zapisu.

Od narzędzi Retman oczekuje tylko dobrych praktyk, które są korzystne niezależnie od niego:
- **stabilne publiczne API** i wersjonowanie semantyczne (zmiana łamiąca zgodność = nowa wersja główna),
- **katalog komend czytelny dla maszyn** (nazwy komend, opcje z dozwolonymi wartościami, skutki:
  sieć i zapis), **walidacja offline** (`validate_command`), dokumenty wyniku w JSON z polem
  `schema` i stabilne kody błędów — Kartograf 0.8.0 i IMGWTools 3.0.0 to mają i na tym opiera się
  warstwa komend (p. 3.2.4),
- dla narzędzi bez katalogu: **podpowiedzi typów**, zwłaszcza `Literal` (lub `Enum`) dla wyborów
  i `Path` dla plików, oraz **docstringi w stylu NumPy**.

#### 3.2.2. Co mieszka w Retmanie

```
src/retman/tools/hydrolog/
├── manifest.py    # operations: params, inputs, outputs, supported versions (p. 4.1)
├── handlers.py    # thin wrappers around the hydrolog public API (p. 3.2.4)
└── pl.toml        # Polish texts and synonyms (p. 4.2)
```

Narzędzie z katalogiem komend (Kartograf, IMGWTools) ma w tym samym folderze dodatkowo
budowniczych wywołań, klienta oraz funkcje podglądu i sprawdzenia (p. 3.2.4).

| Element | Rola |
| --- | --- |
| **Manifest** | opis operacji: parametry, dozwolone wartości, wejścia i wyjścia, obsługiwane wersje narzędzia, odwołania do budowniczych, podglądu i sprawdzenia |
| **Buildery wywołań** | czyste funkcje zamieniające parametry Retmana na wywołania komend katalogu narzędzia (`CatalogCall`); te same służą walidacji w planie i wykonaniu |
| **Klient narzędzia** | jedna cienka klasa na narzędzie: importuje je leniwie, tłumaczy wywołania na jego publiczne API, błędy narzędzia na `ToolError`, a dokumenty wyniku na `ToolRun` |
| **Handlery** | funkcje, które wołają publiczne API (albo wspólnego wykonawcę wywołań) i zamieniają wyniki na pliki — tam, gdzie wynik wymaga obróbki |
| **Podgląd i sprawdzenie** | funkcja offline, która dopowiada wiersze planu i problemy (podgląd), oraz funkcja sieciowa na życzenie (sprawdzenie dostępności) |
| **Tłumaczenia** | polskie teksty i synonimy dla basala i użytkownika, komunikaty błędów i ostrzeżeń |
| **Wspólny adapter** | jeden dla wszystkich narzędzi: waliduje parametry, wykonuje wywołania albo handler, buduje `Result` |
| **Rejestr rodzajów danych** | nazwy `kind` i ich formaty plików (p. 3.2.6) |

Zasady:
- **Każda operacja jest opisana raz**, przy narzędziu, które ją faktycznie wykonuje. Hydrograf
  importuje Hydrologa, ale opis Hydrografa nie powtarza operacji Hydrologa.
- Procedury złożone, które narzędzie już ma (np. w Hydrografie), są **jedną operacją**.
  Retman nie odtwarza ich krok po kroku.

#### 3.2.3. Rola katalogów i dokumentacji narzędzi

Katalogi komend i dokumentacja narzędzi są **źródłem, z którego Retman generuje szkice
i sprawdza zgodność swoich opisów**. Nie są czytane w trakcie działania, a manifesty są statyczne
(ADR-019): opcje nigdy nie są wyprowadzane z zainstalowanego narzędzia przy ładowaniu. Powody:

1. każda opcja potrzebuje polskich tekstów i synonimów, inaczej narzędzie się nie załaduje,
   a tekst pisany maszynowo naruszałby p. 1.3 i ADR-007;
2. katalog nie ma kształtu opcji Retmana: dozwolone rozdzielczości Kartografa to suma 14 wartości
   po produktach i krajach, a basal przyjmuje 9 opcji (p. 3.4) — poprawne wartości zależą
   od produktu i układu wysokościowego;
3. zbiór `retman-eval` musi być powtarzalny, a zawartość i kolejność katalogu zmieniają się
   między wersjami narzędzi; opisy przechowywane w Retmanie są przejrzane, przetestowane
   i zmieniają się tylko świadomie;
4. ładowanie manifestów nie może importować narzędzi (p. 3.2.5), a mały model nie zbuduje
   wiarygodnie wywołania na podstawie samego opisu.

**Narzędzie deweloperskie `retman-scaffold`** (pakiet `retman.devtools`, dla autora, nie dla
użytkownika końcowego; skrypt pakietu podstawowego, bez własnych zależności) czyta maszynowe
katalogi narzędzi (`get_catalog` i `list_sources` Kartografa, `command_schema` IMGWTools) przez
małe czytniki w `src/retman/devtools/readers/` — bez sieci:

```bash
retman-scaffold list <tool>                     # catalog commands, which operations use them, suggested use
retman-scaffold draft <tool> "<command>" [--fix k=v] [--only a,b] [--id op] [--write]
retman-scaffold --check [--tool T] [--operation OP] [--json] [--require-tools] [--verbose]
```

Szkic (`draft`) niczego nie nadpisuje: pisze na standardowe wyjście, a z `--write` do
`src/retman/tools/<narzędzie>/_drafts/` (folder poza gitem). Autor uzupełnia to, czego w katalogu nie
ma (tabela niżej); teksty polskie, kategoria, rodzaje danych i ekstraktory mają w szkicu znacznik
`TODO`, a test odrzuca każdy taki znacznik w zatwierdzonym `pl.toml`. Kody wyjścia: `0` — bez
błędów, `1` — wykryto błędy (albo polecenie się nie powiodło), `2` — błędne użycie.

**Co da się wyczytać z katalogu, a co trzeba dopisać:**

| Informacja | Z katalogu narzędzia? |
| --- | --- |
| parametry, ich typy i wymagalność | tak (Kartograf: opis parametrów komendy; IMGWTools: schemat JSON komendy) |
| dozwolone wybory | tak (`allowed`, `enum`), ale jako suma po produktach i krajach — wartości właściwe dla operacji zawęża próba przez `validate_command`; listy dłuższe niż 9 trzeba podzielić |
| wartości domyślne | tak, ale Retman ich nie przejmuje: nie ma ukrytych wartości domyślnych (ADR-006) |
| zakresy wartości | IMGWTools tak (`minimum`, `maximum`); Kartograf zwykle trzeba dopisać |
| zależności między parametrami | częściowo (opis ograniczeń); egzekwuje je `validate_command` |
| opis po angielsku | IMGWTools tak; Kartograf tylko po polsku, bez diakrytyków |
| skutki komendy (sieć, zapis) | tak |
| pliki wejściowe i wyjściowe | tylko jako nazwy produktów; rodzaj danych (`kind`) trzeba dopisać |
| polskie teksty i synonimy | nie — trzeba dopisać |
| które komendy udostępnić w Retmanie | nie — decyzja autora |

**Kontrola zgodności** (`retman-scaffold --check`, ADR-019) to **zgodność przez wykonanie**: dla
każdego zainstalowanego narzędzia w obsługiwanym zakresie wersji uruchamia prawdziwych budowniczych
wywołań na siatce wyborów z manifestu, a każde wywołanie sprawdza offline samo narzędzie
(`validate_command`, tak jak w planie). Całość działa pod strażnikiem, który zapisuje każdą próbę
użycia sieci i każdy utworzony plik. Niezmiennik pokrycia (X4) sprawia, że „wszystkie rozdzielczości”
pozostaje prawdą z konstrukcji: nowa wartość narzędzia nie pojawia się niezauważona.

| Kontrola | Co znajduje | Ważność |
| --- | --- | --- |
| X1 | zadeklarowana komenda, której nie ma w katalogu albo która nie jest komendą danych; budowniczy emituje niezadeklarowaną komendę | błąd |
| X2 | odrzucenie, które nie jest odpowiedzią, jaką użytkownik może zmienić (brakująca lub nieznana opcja, odrzucenie niewskazujące parametru); odrzucone pary siatki kartezjańskiej (np. 5 m z KRON86) są tylko raportowane | błąd; info |
| X3 | opcja manifestu, której narzędzie nie przyjmuje w żadnym punkcie siatki | błąd |
| X4 | **pokrycie:** wartość, którą narzędzie przyjmuje, a manifest jej ani nie oferuje, ani nie wymienia w `excluded` | błąd |
| X5 | przestarzały wpis `excluded` | ostrzeżenie |
| X6 | wartość domyślna na opcji wymaganej przez narzędzie albo parametr opcjonalny za taką opcją (ADR-006) | ostrzeżenie |
| X7 | `lookup` klienta przyjmuje komendę ze skutkami; sprawdzenie offline dotknęło sieci albo zapisało plik; operacja z komendą sieciową i zapisującą bez `check` i bez uzasadnionego `no_check`; `no_check` przy operacji, której żadna komenda go nie potrzebuje | błąd; ostrzeżenie |
| X8 | kod błędu narzędzia bez tekstu `[errors.<kod>]`; schemat dokumentu nieznany klientowi | błąd |
| X9 | komendy danych katalogu, których nie wystawia żadna operacja | info |
| X10 | brak kompletnego wiersza `retman-eval` z wartościami swobodnymi dla operacji (siatka nie powstała) | ostrzeżenie |

Kontrola działa w pytest i w CI Retmana (p. 3.2.7).

#### 3.2.4. Wywołania, handler, podgląd i sprawdzenie

Tłumaczenie „języka Retmana” na wywołanie publicznego API narzędzia mieszka w Retmanie i ma
dwie formy; operacja deklaruje co najmniej jedną z nich (p. 4.3):

- **`calls` — warstwa komend.** Dla narzędzi z katalogiem komend (Kartograf, IMGWTools): czysty
  *budowniczy wywołań* zamienia parametry na listę wywołań komend katalogu, a wspólny wykonawca
  wykonuje je przez *klienta narzędzia* (`src/retman/adapters/catalog.py`). Powód: katalog jest
  deklarowanym źródłem prawdy tych narzędzi — ma walidację offline z tymi samymi regułami co
  uruchomienie, stabilne kody błędów i dokumenty wyniku — a typowane funkcje i klasy dostawców
  zmieniły się w Kartografie 0.8.0 tak, że zepsuły wszystkie handlery (ADR-013).
- **`handler` — własna funkcja.** Dla operacji, które muszą obrobić wynik (np. rozpakować
  archiwum) albo dla narzędzi bez katalogu. Handler może sam wołać wspólnego wykonawcę
  (`run_calls`) albo klienta (`ctx.runner`).

**Wywołania i klient.** Budowniczy jest czysty: nie dotyka systemu plików ani sieci i jest wołany
dwa razy tym samym kodem — w planie (walidacja) i przy wykonaniu:

```python
# src/retman/tools/<tool>/calls.py (illustrative)
def fetch_dem(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    area = params["area"]
    options = {
        "product": "nmt",
        "resolution": ctx.tool_value("resolution", params["resolution"]),   # "0_5m" -> "0.5m"
        "sheet": area["code"],
    }
    return [CatalogCall("elevation download", options, kind="dem", params={"sheet": "area"})]
```

`CatalogCall` niesie: `command` (komenda katalogu), `options` (w formie JSON, dokładnie tak, jak
przyjmują je `validate_command` i `run_command`; **bez** argumentów środowiskowych — magazynu,
liczby wątków, cache, trybu aktualizacji — bo dodaje je klient z `[retman.tools.<narzędzie>]`, p. 9.1),
`kind` (rodzaj plików, które wywołanie daje: klucz w `files`) i `params` (opcja narzędzia →
parametr Retmana, gdy nazwy się różnią; kieruje odrzucenie przez narzędzie do parametru, o który
trzeba zapytać ponownie). Operacja złożona to kilka wywołań; wykonawca zatrzymuje się na
pierwszym wywołaniu zakończonym `failed` albo `cancelled`, a `partial` kontynuuje z ostrzeżeniami.

Klient jest **podzielony według możliwości**, więc bramka [W-05], [N-12] wynika ze struktury kodu:

| Obiekt | Gdzie istnieje | Metody |
| --- | --- | --- |
| `PlanClient` (dla kodu planowania opakowany w `PlanView`) | w planowaniu: buildery, podgląd, ekstraktory kontekstowe | `validate(call)` — walidacja przez narzędzie, offline; `command_line(call)` — dokładna linia komendy (offline, do śladu audytowego); `lookup(call)` — komenda bez skutków (bez sieci i zapisu), np. lista stacji z magazynu; inna komenda to `ToolError("not_offline")` |
| `RunClient` (dodaje do `PlanClient`) | tylko w `execute()` i w `Retman.check()` po zgodzie na sprawdzenie | `run(call)` — komenda danych (zapisuje magazyn narzędzia); `check(call)` — plan świeżości narzędzia (krok sieciowy); `query(call)` — zapytanie sieciowe tylko do odczytu (np. raport dostępności) |

`PlanView` nie ma atrybutów `run`, `check` ani `query`: krok sieciowy przed potwierdzeniem jest
niemożliwy z konstrukcji, a nie tylko z konwencji. Klient powstaje z fabryki z manifestu (klucz
`client`): `factory(settings) -> RunClient` dostaje zwalidowaną tabelę `[retman.tools.<narzędzie>]`,
nie może użyć sieci ani nic zapisać przy tworzeniu, jest budowana leniwie, raz na `Retman`
i narzędzie, a `ImportError` kończy się błędem `RetmanError` z podpowiedzią `retman doctor`.
Błędy narzędzia klient zgłasza jako `ToolError` (stabilny `code`, opcja lub opcje, których dotyczy,
dozwolone wartości, tekst i wskazówka narzędzia), wyniki jako `ToolRun` (`status`: `ok`, `partial`,
`failed`, `cancelled`; pliki z sumą SHA-256 i etykietą wersji; porażki; uwagi `info`, `warning`,
`error`; pełny dokument JSON; dokładna linia komendy; schemat dokumentu).

Wszystko, co budowniczy, podgląd, sprawdzenie i handler wolno wiedzieć o otoczeniu, niesie
`ToolContext`: `tool`, `settings` (tabela `[retman.tools.<narzędzie>]`), `project_dir`, `output_dir`
(`None` w planowaniu — folder wyniku jeszcze nie istnieje), `inputs` (zwalidowane wejścia),
`client`, `specs` (parametry operacji z manifestu), `operation` (planowana albo wykonywana
operacja — po to, żeby handler mógł oddać zwykłe wywołania katalogu wykonawcy `run_calls`)
oraz pomocniki `ctx.runner` (pełny klient; w planowaniu zgłasza błąd), `ctx.store_dir`,
`ctx.tool_value(parametr, klucz)` i `ctx.option_meta(parametr, klucz)`.

**Podgląd planu (offline) [N-12].** Gdy plan jest kompletny, adapter wykonuje `preview_operation`:

1. każde wywołanie budowniczego waliduje narzędzie (`PlanClient.validate`) — to samo żądanie,
   które wykonałoby operację, bez sieci i zapisu. Odrzucenie (`ToolError` z opcją lub opcjami,
   których dotyczy) jest kierowane na parametry Retmana (przez `CatalogCall.params` albo takie
   same nazwy) i staje się pytaniem zadanym ponownie z powodem (`Plan.reopened`, p. 6.3).
   Opcja zagnieżdżona w innej opcji (np. opcje zadania w IMGWTools `project add`) ma ścieżkę
   `options.<nazwa>` w `ToolError.option` i w `CatalogCall.params`, więc też trafia do swojego
   parametru. Odrzucenie, którego nie da się skierować na żaden parametr, to `ToolDriftError`:
   zainstalowane narzędzie nie przyjmuje już tego, co opisuje manifest (`retman doctor`,
   `retman-scaffold --check`);
2. jeśli narzędzie przyjęło wszystkie wywołania, woła `preview(params, ctx)`, która zwraca
   `PreviewOutput` = `{values, rows, problems}`: `values` trafiają tylko do audytu
   (`result.json["preview"]`), `rows` to dodatkowe wiersze planu (z oznaczeniem
   `← podgląd, bez sieci`; teksty `[preview.<klucz>]`), `problems` to kolejne powody ponownego
   zapytania (niepusta lista parametrów operacji i klucz tekstu z `[problems.<klucz>]`).

Dla obszarów z pliku geometrii podgląd pokazuje np. obwiednię i liczbę arkuszy, które Retman
liczy publicznymi funkcjami narzędzia offline, więc plan mówi, co plik faktycznie oznacza
dla tej operacji (p. 6.1, 6.3).

**Sprawdzenie dostępności (sieć, na życzenie).** `check(params, ctx) -> CheckOutput` =
`{status, items}` jest wołane wyłącznie przez `Retman.check()` po osobnej zgodzie (p. 6.5),
z pełnym klientem: `ctx.runner.check(call)` (plan świeżości narzędzia) albo
`ctx.runner.query(call)` (zapytanie tylko do odczytu). Każdy zadeklarowany `check` traktujemy
jako krok sieciowy — także wtedy, gdy narzędzie w niektórych przypadkach nie łączy się z siecią.

**Wynik i pliki.** Wykonawca zapisuje pełny dokument każdego wywołania jako
`output_dir/tool_<n>_<komenda>.json` i dołącza do wyniku blok audytowy `tool` (komenda, opcje,
linia komendy, status, pliki z sumami, nazwa i suma dokumentu; p. 5.4). Funkcja `describe` operacji
(albo mapowanie ogólne) zamienia wywołania i ich wyniki na `HandlerOutput` = `{values, files,
warnings[, tool]}`. Klucze w `files` to rodzaje danych (`kind`, p. 3.2.6); plik musi leżeć
w `output_dir` **albo w magazynie narzędzia** (`[retman.tools.<narzędzie>] store_dir`) — gdzie indziej
to błąd. Pliki z magazynu wynik wskazuje ścieżką bezwzględną i sumą SHA-256, niczego nie kopiując.

**Komunikaty.** Użytkownik widzi własny tekst Retmana wybrany po stabilnym kodzie błędu
narzędzia (`[errors.<kod>]`, p. 4.2), a tekst narzędzia — często po polsku bez diakrytyków
i z flagami wiersza poleceń — tylko jako cytat (`{detail}`). Uwagi o jakości danych i licencji są
pokazywane dosłownie, bo dokumenty narzędzi nie dają o nich ustrukturyzowanych liczb ani
sformułowań prawnych; uwagi `info` zostają w śladzie audytowym.

Przykład handlera (narzędzie bez katalogu):

```python
# src/retman/tools/hydrograf/handlers.py
from pathlib import Path

import hydrograf  # public API only

from retman.adapters.catalog import ToolContext
from retman.registry.manifest import HandlerOutput


def delineate_catchment(
    params: dict, inputs: dict[str, Path], output_dir: Path, ctx: ToolContext
) -> HandlerOutput:
    """
    Delineate a catchment for a point using the hydrograf public API.

    params     – validated parameter values, e.g. {"point": {"latitude": 52.41, "longitude": 16.93, ...}}
    inputs     – input files by input name (none for this operation)
    output_dir – the only directory the handler may write to
    ctx        – [retman.tools.hydrograf] settings and the tool's client (p. 3.2.4)
    """
    point = params["point"]
    catchment = hydrograf.delineate(lat=point["latitude"], lon=point["longitude"])  # illustrative name of a public function

    out_file = output_dir / "catchment.geojson"
    catchment.to_geojson(out_file)                     # illustrative method

    return {
        "values": {"area_km2": catchment.area_km2},     # short results
        "files": {"catchment_characteristics": [out_file]},  # key = output kind, value = list of paths
        "warnings": [],
    }
```

> Nazwy funkcji Hydrografa w przykładzie są poglądowe.

Zasady handlerów i budowniczych:
1. **Tylko publiczne API narzędzia** — żadnych odwołań do elementów prywatnych (`_nazwa`).
2. **Dane wejściowe przychodzą jako pliki**, wyniki wychodzą jako pliki w `output_dir` albo
   w magazynie narzędzia. Klucze w `files` to rodzaje danych (`kind`, p. 3.2.6). Zamiana obiektów
   narzędzia na pliki (i z powrotem) to zadanie handlera albo klienta.
3. **Żadnej rozmowy z użytkownikiem**: bez `input()` i `print()`. Dopytywanie i komunikaty
   to zadanie Retmana.
4. **Błędy zgłasza wyjątkiem.** Błąd narzędzia klient zamienia na `ToolError`; wspólny adapter
   przechwytuje każdy wyjątek i zwraca `Result(ok=False)` (z `error_code`, gdy to błąd narzędzia);
   awaria jednego narzędzia nie blokuje pozostałych.
5. **Zapis tylko do `output_dir`.** Handler nie zmienia plików użytkownika; magazyn narzędzia
   zapisuje samo narzędzie, przez klienta.
6. **Buildery, podgląd i ekstraktory są czyste i offline** [N-12]: nie dotykają systemu plików
   ani sieci i widzą tylko `PlanClient`.

#### 3.2.5. Co robi wspólny adapter

1. **Przy starcie:** dla każdego narzędzia z `src/retman/tools/` sprawdza — bez importowania go —
   czy jest zainstalowane i czy jego wersja mieści się w obsługiwanym zakresie (p. 3.2.7).
   Wczytuje opisy i je waliduje: unikalność identyfikatorów, znane rodzaje danych, komplet
   tłumaczeń, reguły kluczy `handler`/`calls`/`client`/`excluded`, limity kategorii (p. 3.4).
   Operacje narzędzi niezainstalowanych są niedostępne (`retman doctor` podpowiada, jak je
   doinstalować).
2. **Przy planowaniu:** zamienia manifesty na wewnętrzne obiekty `Operation`, z których korzysta
   pipeline. Narzędzie wybranej operacji jest importowane dopiero teraz, przez klienta, a kod
   planowania dostaje tylko jego połowę offline (`PlanView`): ekstraktory kontekstowe wyszukują
   w katalogu, a podgląd waliduje wywołania (p. 3.2.4). Sieci ani zapisu nie ma (N-12).
3. **Przy wykonaniu:** buduje pełnego klienta (`RunClient`), przygotowuje `output_dir` i pliki
   wejściowe, liczy sumy kontrolne plików geometrii, wywołuje handler albo wykonawcę wywołań,
   sprawdza zwrócone pliki z deklaracją `outputs` (rodzaj, walidator, położenie w `output_dir`
   albo w magazynie narzędzia), tłumaczy ostrzeżenia, buduje `Result` i zapisuje go w przestrzeni
   roboczej. Uszkodzone narzędzie nie psuje reszty: błąd jest wynikiem tej operacji.
4. **Przy sprawdzeniu dostępności:** po osobnej zgodzie woła funkcję `check` operacji z pełnym
   klientem, tłumaczy pozycje raportu i zwraca `CheckReport`; nie tworzy wyniku (p. 6.5).

#### 3.2.6. Rejestr rodzajów danych (`kind`)

Rodzaj danych to nazwa + akceptowane rozszerzenia + prosty walidator offline, napisany wyłącznie
na bibliotece standardowej (bez bibliotek geoprzestrzennych i bez sieci). Rejestr
(`src/retman/kinds.py`) jest w Retmanie. Narzędzia nie znają tych nazw — zamianą ich wyników na pliki
danego rodzaju zajmują się wywołania i handlery. Jeden wynik może zawierać kilka plików tego
samego rodzaju (np. arkusze NMT), więc `files` przypisuje rodzajowi listę ścieżek. Walidator
sprawdza rozszerzenie i nagłówek (albo kolumny, albo schemat), a niezgodność zgłasza jako
`KindValidationError` z powodem (klucz w `[kinds.errors]` pliku tłumaczeń).

Rodzaje danych Kartografa (ADR-004, ADR-016) — format jest taki, jaki zwraca Kartograf:

| `kind` | Format | Walidator sprawdza m.in. |
| --- | --- | --- |
| `dem` | NMT: ESRI ASCII Grid (`.asc`, arkusze) albo GeoTIFF (`.tif`, wycinek) | rozszerzenie; nagłówek `ncols` (ASC) albo sygnatura TIFF |
| `dsm` | NMPT: jak `dem` | jak `dem` |
| `orthophoto` | GeoTIFF (`.tif`) | sygnatura TIFF |
| `topographic_vector` | BDOT10k: GeoPackage (`.gpkg`) albo Shapefile (`.shp`) | nagłówek SQLite (GPKG) albo kod pliku Shapefile |
| `dem_archive` | NMT 100 m: archiwum ZIP z plikiem XYZ na województwo (`.zip`) | sygnatura ZIP |
| `area_geometry` | plik użytkownika z geometrią obszaru: GeoPackage albo Shapefile | jak `topographic_vector`; waliduje obszar z pliku w planie (p. 6.1), zarezerwowany też jako rodzaj wyjściowy przyszłych operacji (łańcuchy, v0.2) |

Rodzaje danych IMGWTools (ADR-017) — pliki tabelaryczne i dokumenty JSON; walidatory czytają
tylko początek pliku (nagłówek i kilka pierwszych wierszy):

| `kind` | Format | Walidator sprawdza m.in. |
| --- | --- | --- |
| `station_list` | lista stacji (CSV) | kolumny `provider`, `kind`, `station_code`, `name`, `river`, `latitude`, `longitude` |
| `hydro_series` | szereg czasowy stacji hydrologicznej (CSV) | nagłówek `date,year,<zmienna> [<jednostka>],<zmienna>_flag,…,attribution_source,attribution_processed`; zmienne H, Q, T (także `_min`, `_mean`, `_max`); ČHMÚ dodaje kolumny `_quality` i `_source_flag` |
| `meteo_series` | szereg czasowy stacji meteorologicznej (CSV) | jak `hydro_series`, bez zmiennych hydrologicznych |
| `pmaxtp_table` | opady maksymalne PMAXTP (CSV) | kolumny `duration_min`, `probability_percent`, `ks_mm`, `sg_mm`, `rb_mm`, `attribution_source`, `attribution_processed` |
| `current_hydro` | dane bieżące hydrologiczne (CSV) | kolumny `station_code`, `station_name`, `water_level_cm`, `flow_m3s` |
| `current_meteo` | dane bieżące meteorologiczne (CSV) | kolumny `station_code`, `station_name`, `air_temp_c`, `wind_speed_ms` |
| `current_synop` | dane bieżące synoptyczne (CSV) | kolumny `station_code`, `station_name`, `measurement_date`, `temperature_c` |
| `imgw_warnings` | ostrzeżenia IMGW (CSV) | kolumny `id`, `kind`, `level` |
| `hydro_states` | stany wody na stacjach (CSV) | kolumny `station_code`, `name`, `water_state` |
| `archive_records` | rekordy wyeksportowane z magazynu archiwów (CSV albo JSON Lines) | pola `station_code`, `dataset`, `date` (nagłówek CSV albo pierwszy rekord) |
| `imgw_archive` | archiwum IMGW tak, jak opublikowane (`.zip`, `.json`, `.csv`, `.txt`) | sygnatura ZIP, początek JSON (`{` albo `[`) albo tekst niebinarny |
| `imgw_plan` | plan pobrania lub synchronizacji IMGWTools (JSON) | dokument ze `schema` równym `imgw-plan/1` |
| `imgw_report` | raport IMGWTools (JSON) | dokument `imgw-result/1` — pierwszy klucz to `schema` |

Rodzaje pozostałych narzędzi (Hydrolog, Hydrograf, BasicHydraulics) to otwarta kwestia
(rozdz. 12).

#### 3.2.7. Wersje i zgodność

Pilnowanie zgodności to rola Retmana, nie narzędzi. Narzędzia rozwijają się niezależnie,
a Retman dostosowuje się do nich:

- Każde narzędzie ma w manifeście **obsługiwany zakres wersji**: Kartograf `>=0.8.0,<0.9`
  (wydania 0.x mogą łamać zgodność), IMGWTools `>=3.0.0,<4` (wersjonowanie semantyczne i kontrakty
  dokumentów `/1`; ADR-012). Zakres odpowiada tagom wydań w repozytorium narzędzia na GitHubie;
  do czasu wypchnięcia tagów `v0.8.0` i `v3.0.0` grupa zależności `tools` przypina wypchnięte
  commity (p. 9.3). Retman sprawdza wersję zainstalowanego narzędzia przy starcie (p. 3.2.5); sam
  z siebie narzędzi nie instaluje (p. 9.3, 9.4).
- **CI Retmana** uruchamia testy handlerów i kontrolę zgodności (`retman-scaffold --check`,
  p. 3.2.3) na najstarszej i najnowszej obsługiwanej wersji każdego narzędzia, a regularnie
  (np. co noc) także na bieżącej gałęzi głównej narzędzi — zmiana API, która zepsułaby Retmana,
  wychodzi od razu.
- `retman doctor` pokazuje zainstalowaną wersję każdego narzędzia na tle obsługiwanego zakresu.

#### 3.2.8. Testy narzędzi

Wszystkie testy związane z narzędziami są w repo Retmana:
- walidacja manifestów (identyfikatory, rodzaje danych, komplet tłumaczeń, reguły kluczy),
- buildery wywołań i mappery wyników na **nagranych prawdziwych dokumentach** narzędzi
  (`tests/fixtures/<narzędzie>/`), z atrapą klienta `FakeToolClient` zamiast monkeypatchowania
  wnętrz narzędzia (p. 8.3),
- testy na prawdziwych narzędziach z małymi danymi, offline (IMGWTools: jego pakietowy magazyn
  fikcyjny, `imgwtools.testing.build_fixture_store`); pomijane (`pytest.importorskip`), gdy narzędzia
  nie ma, oraz testy `live` uruchamiane świadomie,
- kontrola zgodności z aktualnym API (`retman-scaffold --check`).

#### 3.2.9. Narzędzia ekosystemu

| Narzędzie | Zakres operacji | Zależy od | Stan |
| --- | --- | --- | --- |
| Kartograf | pobieranie danych przestrzennych (NMT, NMPT, ortofotomapa, BDOT10k) | — | v0.1, wersja 0.8.0 |
| IMGWTools | dane pomiarowe IMGW-PIB i ČHMÚ: stacje, dane bieżące, PMAXTP, szeregi, archiwa i magazyn, projekty danych | — | v0.1, wersja 3.0.0 |
| Hydrolog | obliczenia hydrologiczne (przepływy, metody) | — | planowane (v0.2) |
| BasicHydraulics | proste obliczenia hydrauliczne | — | planowane (v0.2) |
| Hydrograf | wyznaczanie zlewni, procedury złożone | Hydrolog (i inne) | planowane (v0.2) |

Konkretne operacje ustala PRD (p. 7.2); opisy operacji Kartografa i IMGWTools: p. 3.2.10
i 3.2.11. Narzędzia innych autorów obsługuje się tak samo: opis, budowniczowie lub handlery
i klient w `src/retman/tools/`.

#### 3.2.10. Operacje Kartografa 0.8.0

Cztery operacje (ADR-001, ADR-012, ADR-016) w jednej kategorii, `spatial_data` („Dane przestrzenne
GUGiK”). Wszystkie idą przez warstwę komend (`calls`), mają podgląd offline i sprawdzenie
dostępności (`check`):

| Operacja (`id`) | Komendy katalogu | Obszar (`accepts`) | Parametry, o które Retman dopytuje | Rodzaje wyjściowe |
| --- | --- | --- | --- | --- |
| `download_dem_sheet` — NMT dla arkusza lub obszaru | `elevation download` | `sheet`, `geometry` | rozdzielczość (0,15; 0,5; 0,6; 1; 5; 10 albo 100 m); układ wysokościowy (EVRF2007 albo KRON86; nie dotyczy 100 m) | `dem`; NMT 100 m: `dem_archive` |
| `download_sheet_hierarchy` — arkusze potomne: NMT, NMPT albo ortofotomapa | `elevation download`, `imagery download` | `sheet`, `geometry` (ortofotomapa tylko `sheet`) | produkt; skala docelowa (1:10000 w PL-1992; 1:5000, 1:2000, 1:1000, 1:500 w PL-2000); rozdzielczość NMT (0,15–10 m) albo NMPT (0,5; 0,6; 1 m); układ wysokościowy; kolor ortofotomapy (RGB, CIR, B/W) | `dem`, `dsm`, `orthophoto` |
| `download_elevation_cutout` — wycinek NMT albo NMPT 1 m | `elevation download` | `bbox`, `geometry` | produkt; układ wyniku (EPSG:2180, 5514, 3045 — czyta go kod, nie model, ADR-009); układ wysokościowy | `dem`, `dsm` |
| `download_bdot10k` — BDOT10k (bieżące paczki powiatów) | `landcover download` | `teryt`, `bbox`, `sheet`, `geometry` | format (GeoPackage albo Shapefile) | `topographic_vector` |

Operacje Kartografa nie mają wartości domyślnych (ADR-006): o rozdzielczość, układ wysokościowy,
skalę, kolor i format Retman pyta, gdy polecenie ich nie zawiera. Obsługiwane są wszystkie
rozdzielczości siatek ASC Kartografa (ADR-012); to, co narzędzie mimo to nie przyjmuje, jest
w `excluded` z uzasadnieniem (np. NMT 100 m w arkuszach potomnych: to pliki województw).
Model dostaje do wyboru sumaryczną listę rozdzielczości, a niepoprawną parę (np. 5 m z KRON86)
odrzuca Kartograf w podglądzie, offline — Retman pyta wtedy ponownie o oba parametry, z powodem
(„Kartograf odrzuca ten wybór: …”, p. 6.3).

**Obszar z pliku geometrii** (ADR-016). Plik czyta Kartograf; Retman wypisuje tylko warstwy
GeoPackage (pyta, gdy jest ich kilka), liczy sumy SHA-256 plików i pokazuje w podglądzie
obwiednię (EPSG:2180) oraz — dla arkuszy — liczbę arkuszy. Co plik oznacza, mówi plan
(`geometry_note`):

| Operacja | Znaczenie pliku | Uwagi |
| --- | --- | --- |
| NMT dla arkusza, arkusze potomne | arkusze w danej skali, których obwiednia styka się z obwiednią któregokolwiek obiektu warstwy; kształt wieloboku nie jest uwzględniany | liczba arkuszy 0 to problem podglądu |
| wycinek | jeden prostokąt obejmujący wszystkie obiekty warstwy, bez przycinania do wieloboku | poza lądem Polski brak danych |
| BDOT10k | pełne pakiety wszystkich powiatów przecinających obwiednię | obszar poza Polską odrzuca podgląd; listę powiatów zna dopiero usługa PRG (sieć, po potwierdzeniu albo w sprawdzeniu) |
| ortofotomapa (arkusze potomne) | plik nie jest przyjmowany — klasa dostawcy bierze tylko godła | problem podglądu: Retman pyta ponownie o produkt i obszar |

**Wynik i magazyn.** Kartograf zapisuje pobrane pliki w swoim magazynie (`[retman.tools.kartograf]
store_dir`) jako niezmienne wersje; wynik wskazuje je ścieżką bezwzględną i sumą SHA-256 (p. 5.4)
i zawiera dokument narzędzia (`tool_<n>_<komenda>.json`). Wyjątek: BDOT10k w Shapefile Kartograf
zwraca w magazynie archiwa ZIP, a mapper rozpakowuje wszystkie `.shp` wraz z plikami towarzyszącymi
do folderu wyniku (z odrzuceniem niebezpiecznych ścieżek w archiwum). Ortofotomapa w wybranym
kolorze idzie przez własny handler (klasa dostawcy narzędzia, ADR-013), do tego samego magazynu.
Uwagi Kartografa o jakości danych (np. niepełny lot, inny układ arkusza, brak danych dla części
arkuszy) wynik pokazuje własnym tekstem z `[warnings]` albo dosłownie; częściowy wynik jest wynikiem
z ostrzeżeniem.

**Sprawdzenie dostępności** (`s`, p. 6.5): dla NMT, NMPT i wycinka pyta usługi GUGiK (skorowidz
arkuszy WFS i warstwę PRG) o lata, rozdzielczości, układy wysokościowe i kompletność arkuszy dla
obszaru z planu (`elevation availability`); dla wycinka to przybliżenie, bo wycinek składa serwer
WCS. Dla ortofotomapy sprawdza plan świeżości dla wariantu RGB (skorowidz zna tylko RGB); dla BDOT10k
pyta usługę PRG, które powiaty przecina obszar i ile ich paczek jest już w magazynie (dla kodu TERYT
bez sieci). NMT 100 m (pliki województw) i warianty CIR i czarno-biały nie mają skorowidza — sprawdzenie
niczego wtedy nie sprawdza i mówi to wprost.

#### 3.2.11. Operacje IMGWTools 3.0.0

Całe IMGWTools w v0.1 (ADR-017): 26 operacji w sześciu kategoriach, na danych IMGW-PIB i ČHMÚ.
Razem z kategorią `spatial_data` Kartografa jest ich siedem (w żadnej nie więcej niż 9 operacji),
więc rozpoznawanie jest dwustopniowe (p. 3.4). Wszystkie operacje idą przez warstwę komend; te,
które łączą się z serwerem, robią to dopiero po potwierdzeniu planu. Operacje oznaczone `check`
oferują sprawdzenie dostępności (p. 6.5).

| Kategoria (`id`) | Operacja (`id`) — co robi | Rodzaj wyniku | Sieć i zapis |
| --- | --- | --- | --- |
| `imgw_catalog` — stacje i rejestr danych | `find_imgw_stations` — wyszukanie stacji po nazwie, rzece, dostawcy i rodzaju | `station_list` | z magazynu bez sieci; z serwera sieć |
| | `build_imgw_station_catalog` — budowa katalogu stacji w magazynie, opcjonalnie z plikiem położeń; `check` | — | sieć; zapis w magazynie |
| | `list_imgw_datasets` — zbiory danych i dostawcy | `imgw_report` | bez sieci |
| `imgw_current` — dane bieżące i ostrzeżenia | `fetch_current_observations` — aktualne pomiary stacji hydrologicznej, meteorologicznej albo synoptycznej | `current_hydro`, `current_meteo`, `current_synop` | sieć |
| | `fetch_imgw_warnings` — ostrzeżenia hydrologiczne i meteorologiczne | `imgw_warnings` | sieć |
| | `fetch_hydro_states` — stany wody na stacjach (alarmowe i ostrzegawcze) | `hydro_states` | sieć |
| `imgw_pmaxtp` — opady maksymalne PMAXTP | `get_pmaxtp` — tabela opadów maksymalnych dla punktu (metoda POT albo AMP; filtry: prawdopodobieństwo i czas trwania; zapis komórki w magazynie albo nie) | `pmaxtp_table` | sieć; z zapisem także magazyn |
| | `read_stored_pmaxtp` — odczyt zapisanej komórki siatki | `pmaxtp_table` | bez sieci |
| `imgw_series` — szeregi czasowe stacji | `export_station_series` — szereg stacji (zbiór, okres, rodzaj roku, zmienne) do CSV; `check` | `hydro_series`, `meteo_series` | z magazynu bez sieci; z serwera pobranie archiwów do magazynu (sieć, zapis) |
| | `show_station_coverage` — pokrycie danych stacji w magazynie (lata, luki) | `imgw_report` | bez sieci |
| | `build_imgw_series` — budowa szeregów zbioru z archiwów w magazynie | — | zapis w magazynie |
| `imgw_archives` — archiwa i magazyn | `download_hydro_archives`, `download_meteo_archives` — pobranie archiwów do folderu wyniku, bez magazynu | `imgw_archive` | sieć |
| | `check_imgw_archives` — plan: co trzeba pobrać względem magazynu | `imgw_plan` | sieć |
| | `sync_imgw_store` — pobranie archiwów do magazynu; `check` | — | sieć; zapis w magazynie |
| | `sync_imgw_store_by_plan` — pobranie według planu z wyniku `check_imgw_archives` (wejście `imgw_plan`, np. „#5”) | — | sieć; zapis w magazynie |
| | `export_imgw_archive` — eksport zapisanych archiwów do CSV albo JSON Lines | `archive_records` | bez sieci |
| | `init_imgw_store` — utworzenie magazynu | — | zapis (znacznik magazynu) |
| | `inspect_imgw_store` — opis magazynu (wpisy, wersje, problemy) | `imgw_report` | bez sieci |
| `imgw_projects` — projekty danych | `init_imgw_project`, `add_imgw_project_task`, `remove_imgw_project_task`, `set_imgw_project_store` — manifest projektu (`imgw-project.json`) w folderze projektu | — | zapis w folderze projektu |
| | `download_imgw_project` — pobranie i przypięcie danych zadań projektu; `check` | — | sieć; zapis |
| | `check_imgw_project` — plan aktualności danych projektu | `imgw_plan` | sieć |
| | `verify_imgw_project` — weryfikacja przypiętych danych (stan albo sumy kontrolne) | `imgw_report` | bez sieci |

Operacje zapisujące tylko do magazynu albo do folderu projektu (bez rodzaju wyniku) zostawiają
w folderze wyniku `result.json` i dokumenty narzędzia; pozostałe zapisują CSV i raporty w folderze
wyniku — IMGWTools nigdy nie wskazuje w wyniku plików magazynu. Operacje, których wynikiem jest
dokument bez pliku (listy, tabele), zapisują go jako CSV (tabele) albo JSON.

**Zasady wspólne dla operacji IMGWTools:**

- **Magazyn** (`[retman.tools.imgwtools] store_dir`, p. 9.1) jest opcją `root` każdej komendy, którą
  dodaje klient. Brak magazynu, folder obcy albo magazyn o nieobsługiwanym schemacie to
  **problem podglądu** z poleceniem naprawy („Utwórz magazyn IMGW”, `retman init`); żadna
  operacja nie tworzy magazynu po cichu. `reference_data_dir` klient eksportuje raz jako zmienną
  `IMGW_DATA_DIR` przed pierwszym importem narzędzia — jedyny wyjątek od zasady „bez zmiennych
  środowiskowych”, bo narzędzie nie ma opcji dla pliku statycznych położeń stacji; wartość
  pochodzi z ustawień, a nie z otoczenia.
- **Stacje** czyta ekstraktor `station` **offline z katalogu w magazynie** (kody: 9 cyfr
  IMGW-PIB, identyfikator WIGOS ČHMÚ; nazwy z odmianą polską, odmieniona nazwa wymaga
  potwierdzenia, p. 6.1). Bez katalogu Retman czyta tylko kody i wskazuje operację
  `build_imgw_station_catalog` (jawna, potwierdzana, z siecią); do tego czasu nie szuka stacji
  przez sieć w trakcie pytań.
- **Okres: dwie semantyki, nigdy mieszane.** Operacje archiwów biorą `years` — lata w numeracji
  archiwów narzędzia (dla hydrologicznych zbiorów IMGW-PIB są to lata hydrologiczne). Operacje
  szeregów biorą `period` (lata albo daty) i `year_type` (rok hydrologiczny albo kalendarzowy) —
  **zawsze pytanie**, gdy nie padło w poleceniu, bo to zmienia daty (1 listopada – 31 października
  wobec 1 stycznia – 31 grudnia). Retman nie wystawia `months` narzędzia (dla danych hydrologicznych
  to indeks pliku w roku hydrologicznym).
- **Zbiory danych** (`dataset`) to zamknięte listy dla modelu (klucze bez kropek, `tool_values`
  zamienia je na klucze rejestru narzędzia, np. `pl_hydro_daily` → `pl.imgw.hydro_daily`):
  siedem zbiorów dla komend magazynu i szeregów (IMGW-PIB: hydro dobowe, miesięczne i półroczne,
  meteo klimatyczne dobowe i opadowe dobowe; ČHMÚ: hydro dobowe i meteo dobowe), a dla pobrania
  archiwów do folderu wyniku dwie operacje — hydrologiczna (5 zbiorów, w tym zjawiska
  hydrologiczne) i meteorologiczna (7 zbiorów, w tym miesięczne, synoptyczne i terminowe) —
  zbiory drugiej operacji są w `excluded` pierwszej (kontrola pokrycia, p. 3.2.3). Metadane zbioru
  (dostawca, rodzaj, zmienne, numeracja lat) niesie `option_meta`; z nich korzystają ekstraktory
  kontekstowe (np. zmienne dostępne w zbiorze, stacje właściwego dostawcy i rodzaju).
- **PMAXTP:** żądanie do narzędzia przyjmuje tylko punkt i metodę, a wynikiem jest tabela
  (czas trwania × prawdopodobieństwo; kolumny `ks_mm`, `sg_mm`, `rb_mm`). `probability` i `duration`
  z polecenia są więc **filtrami wyjścia** (p. 4.4): wartość spoza tabeli nie ginie po cichu, tylko
  daje ostrzeżenie, a gdy żadna nie występuje, zapisywana jest cała tabela. Punkt w PL-1992 Retman
  przelicza sam, bez bibliotek geoprzestrzennych; punkt poza ramką PMAXTP (49–55° N, 14–24,5° E)
  jest odrzucany z powodem.
- **Licencja i atrybucja:** uwagi `license_terms` dostawcy są pokazywane dosłownie w ostrzeżeniach
  wyniku, a atrybucja rejestru jest w kolumnach CSV (`attribution_source`, `attribution_processed`).
- **Podgląd** (offline) dopowiada w planie m.in. stan magazynu i liczbę stacji pasujących do nazwy,
  zakres danych w magazynie (lata, luki) i liczbę plików archiwów do sprawdzenia, a odrzuca plan,
  którego magazyn nie obsłuży (np. brak szeregu zbioru albo stacji w szeregu przy źródle „magazyn”).
  **Sprawdzenie dostępności** (`check`) mają tylko operacje, w których sieć zmienia to, co się
  wydarzy: budowa katalogu stacji (czy listy źródła są nowsze), eksport szeregu (przy źródle
  „serwer”: ile archiwów trzeba pobrać; przy źródle „magazyn” sprawdzenie nie łączy się z siecią
  i mówi to wprost) i synchronizacja archiwów (ile plików jest nowszych albo brakuje i ile to
  danych — zapytania HEAD bez pobierania), pobranie danych projektu (stan zadań). Operacje punktowe
  i „na żywo” oraz operacje-artefakty (`check_imgw_archives`, `check_imgw_project`) nie mają `check`: sprawdzenie
  nie powiedziałoby nic, czego nie powie samo wykonanie, a wynik tych operacji jest planem
  (`imgw_plan`), który użytkownik potwierdza i wykonuje (`sync_imgw_store_by_plan`).
- **Wyłączone komendy katalogu** (7 z 37, każda osiągalna przez CLI i API IMGWTools): `datasets
  files`, `pmaxtp url`, `pmaxtp check` i `series select` to wyszukiwania offline używane przez
  podglądy i mappery, nie osobne operacje; `series read` daje te same rekordy co eksport szeregu
  (a plik z kolumnami licencyjnymi daje `export_station_series`); `commands schema` i `commands guide`
  opisują sam katalog (Retman czyta schematy wyłącznie w `retman-scaffold`). Komenda `project add`
  jest wystawiona dla zadań `series select` i `pmaxtp sync`; pozostałe typy zadań nie mają czego
  przypinać albo są objęte zadaniem szeregu.

### 3.3. Modele: Retman nie zawiera modelu [N-01], [N-02], [N-10]

Retman nie jest dystrybuowany z żadnym modelem językowym. Model działa jako **osobna usługa** —
lokalnie (np. LM Studio, Ollama, basal-serve), w sieci jednostki albo u dostawcy — a Retman
łączy się z nim przez API. Dzięki temu podstawowa instalacja Retmana jest mała i nie zawiera
bibliotek uczenia maszynowego.

**Konfiguracja domyślna:** model decyzyjny to **basal** przez **basal-serve** — osobny program
z pakietu `basal`, który zadaje modelowi pytania w specjalny sposób i zwraca skalibrowane
prawdopodobieństwa opcji (p. 3.3.3). basal-serve **nie jest zależnością Retmana**, nawet
opcjonalną, bo wymaga PyTorcha i bibliotek GPU; instaluje się go osobno według instrukcji basala.

#### 3.3.1. Dwie role modelu

| Rola | Interfejs | Do czego | Wymagana? |
| --- | --- | --- | --- |
| **Model decyzyjny** | `DecisionBackend` | wybór operacji i opcji (kroki ①–②) | tak |
| **Model tekstowy** | `TextBackend` | opis wyników po polsku (od v0.2) | nie |

Obie role może pełnić ten sam model (np. jeden model w LM Studio) albo dwa różne
(np. basal do decyzji i Bielik do opisów). Retman rozmawia z modelami wyłącznie przez te dwa
interfejsy, więc zamiana modelu nie wymaga zmian w pozostałym kodzie.

```python
from typing import Protocol


class DecisionBackend(Protocol):
    """A model that picks one of the given options and reports how confident it is."""

    def choose(self, state: str, question: str, options: dict[str, str]) -> "Decision":
        """
        state    – the user's command (plus optional context)
        question – question for the model in the user's language (from translation
                   files; for parameters: `model_question`, p. 4.2)
        options  – {key: description}, e.g. {"punzet": "Metoda Punzeta", ...}
        Returns the chosen key, probabilities of all options and the confidence.
        """
        ...

    def yes_no(self, state: str, question: str) -> "Decision":
        """A yes/no question, e.g. whether the command specifies a location."""
        ...


class TextBackend(Protocol):
    """A model that writes text — used only for describing results (optional)."""

    def describe(self, result_summary: dict, language: str = "pl") -> str:
        ...
```

#### 3.3.2. Rodzaje połączeń (backendy)

| Backend | Z czym się łączy | Rola | Wersja |
| --- | --- | --- | --- |
| `basal` | basal-serve, instalowany osobno według instrukcji basala | **decyzje — domyślnie**, ze skalibrowaną pewnością | v0.1 |
| `openai_compatible` | dowolny serwer z API zgodnym z OpenAI: LM Studio, Ollama, llama.cpp server, vLLM, a także dostawcy z takim API | decyzje (alternatywa dla basala); od v0.2 także opis wyników | v0.1 |
| natywne API dostawców | dostawcy z własnym API (np. Anthropic) | decyzje i/lub tekst | v0.2, opcjonalne dodatki |
| `none` | — | brak opisu wyników: wynik pokazuje szablon tekstowy | v0.1 |

Backendy rozmawiają z API bezpośrednio przez HTTP, bez SDK dostawców — podstawowa instalacja
pozostaje mała. Backend `basal` to własne zapytanie HTTP do basal-serve, bez klienta z pakietu
`basal`, żeby nie instalować jego zależności.

#### 3.3.3. Jak model podejmuje decyzję

**basal (przez basal-serve).** basal-serve buduje stałe zapytanie z poleceniem, pytaniem
i opcjami oznaczonymi literami. Nie pozwala modelowi pisać — odczytuje tylko prawdopodobieństwa
kolejnej litery (A, B, C…). Powtarza pytanie z odwróconą kolejnością opcji i uśrednia wynik,
a na końcu stosuje kalibrację dołączoną do modelu. Wynik: prawdopodobieństwo każdej opcji
i pewność, bez żadnego tekstu.

**Model generatywny (alternatywa).** Model generatywny (np. Bielik, Qwen, model frontierowy)
nie zwraca takich prawdopodobieństw, więc backend `openai_compatible` działa tak:

1. **Wybór.** Pyta model o jedną z opcji i wymusza format odpowiedzi: listę dozwolonych kluczy,
   jeśli serwer obsługuje odpowiedzi ustrukturyzowane; w przeciwnym razie sprawdza odpowiedź
   i w razie potrzeby ponawia pytanie.
2. **Pewność** — według ustawienia `confidence` (p. 9.1):
   - `auto` (domyślnie): z `logprobs` (prawdopodobieństw tokenów), jeśli serwer je zwraca;
     w przeciwnym razie **zgodność** — kilka zapytań (np. 3) i odsetek zgodnych odpowiedzi,
   - `logprobs` albo `consistency` — wymuszenie jednej z metod,
   - `none` — bez pewności; tylko z jawnego wyboru użytkownika (np. żeby ograniczyć liczbę
     wywołań płatnego API).

   Progi pewności dla tych metod trzeba wpisać liczbą — `"auto"` oznacza kalibrację basala
   i z tym backendem jest błędem konfiguracji (p. 6.2).
3. **Niska pewność lub niezgodne odpowiedzi** — Retman dopytuje, tak samo jak przy niskiej
   pewności basala (PRD N-05). W trybie `none` każda wartość wybrana przez model jest w planie
   oznaczona jako **niezweryfikowana**, a zabezpieczeniem pozostaje obowiązkowe potwierdzenie
   planu (p. 6.3).

#### 3.3.4. Przykładowe konfiguracje

| Konfiguracja | Decyzje | Opis wyników | Uwagi |
| --- | --- | --- | --- |
| **Domyślna** | basal (basal-serve) | Bielik w LM Studio (od 0.2; w 0.1 szablon) | skalibrowana pewność decyzji, polski model do tekstu; dwie usługi obok Retmana |
| **Najprostsza** | jeden model w LM Studio (`openai_compatible`) | ten sam model (od 0.2) | jedna usługa; pewność z `logprobs` albo ze zgodności kilku odpowiedzi (p. 3.3.3); progi pewności wpisane liczbą (p. 6.2) |
| **Z modelem frontierowym** | model dostawcy przez API | model dostawcy (od 0.2) | wymaga klucza API; polecenia trafiają do dostawcy (rozdz. 10); progi pewności wpisane liczbą (p. 6.2) |
| **Minimalna** | dowolny model | `none` | wyniki opisane szablonem |
| **Serwer jednostki** | basal-serve na serwerze w sieci wewnętrznej | jak w domyślnej | komputer użytkownika bez GPU; od v0.1 — wystarczy zmienić `url` w konfiguracji |

Opis wyników przez model tekstowy działa od v0.2; w v0.1 wyniki opisuje szablon tekstowy.

> Dostęp do modelu przez subskrypcję czatu zwykle nie obejmuje dostępu przez API — do pracy
> z Retmanem potrzebny jest klucz API (do sprawdzenia u konkretnego dostawcy).

### 3.4. Ograniczenia basala, które architektura musi uwzględnić

Dotyczy konfiguracji z basalem. Część zasad (pkt 2, 4–6) obowiązuje także dla modeli
generatywnych, bo upraszcza im zadanie.

1. **Maks. 10 opcji na pytanie.** Pytanie o operację zawiera operacje i opcję `out_of_scope`
   (pkt 6), więc jedno pytanie obsłuży do 9 operacji. Operacji jest więcej (od v0.1 Kartograf
   i całe IMGWTools), więc rozpoznanie jest **dwustopniowe**: model wybiera najpierw
   **kategorię** (opcje: kategorie i `out_of_scope`), potem **operację w kategorii** (opcje:
   operacje tej kategorii i `out_of_scope`). Decyzje mają nazwy `category` i `operation`
   (p. 5.4); niepewny wybór kategorii kończy się pytaniem `category` z 2–3 najbardziej
   prawdopodobnymi grupami (p. 6.1). Loader wymusza limity przy starcie: najwyżej 9 kategorii,
   najwyżej 9 operacji w kategorii, a każda kategoria ma `label` i `description` w pliku
   tłumaczeń narzędzia (`[categories.<id>]`, p. 4.2; kategorię o tej samej nazwie w kilku
   narzędziach opisuje pierwsze z nich, które ma jej tekst). Parametr `choice` ma osobny limit:
   najwyżej 9 opcji plus `unspecified` (p. 4.3) — dłuższe listy wartości narzędzia dzieli się
   na parametry albo operacje.
2. **Słaby w dokładnych liczbach.** Wartości liczbowe zawsze wyciągają ekstraktory (krok ③).
3. **Kolejność opcji ma znaczenie.** basal uśrednia kolejność prostą i odwróconą; mimo to
   testy (rozdz. 8) muszą sprawdzać stabilność przy przetasowaniu opcji.
4. **Pytać w języku polecenia.** Pytania i opisy opcji muszą istnieć w pliku tłumaczeń dla
   języka polecenia (p. 4.2).
5. **Opcja „nie da się ustalić”.** Każde pytanie o parametr, który może nie paść w poleceniu,
   ma dodatkową opcję `unspecified` („polecenie tego nie określa”).
6. **Opcja „żadna z powyższych”** [W-03]. Pytanie o operację (krok ①) zawsze zawiera opcję
   `out_of_scope` („polecenie nie dotyczy żadnej z dostępnych operacji”) — przy rozpoznawaniu
   dwustopniowym na obu stopniach. Jej wybór kończy się komunikatem o tym, co Retman potrafi
   (przy dwóch stopniach: o grupach operacji), a nie zgadywaniem najbliższej operacji.
   Opcja liczy się do limitu 10 opcji.

---

## 4. Rejestr operacji

### 4.1. Manifest — definicja operacji

Operacje każdego narzędzia opisuje manifest w `src/retman/tools/<narzędzie>/manifest.py`:
zwykły słownik Pythona, po angielsku. Manifest jest **statyczny i przeglądany przez człowieka**:
opcje nigdy nie są wyprowadzane z zainstalowanego narzędzia przy ładowaniu (ADR-019) — mają
polskie teksty i synonimy, zbiór `retman-eval` musi być powtarzalny, a start Retmana nie
importuje narzędzi. Szkic manifestu można wygenerować z katalogu komend narzędzia
(`retman-scaffold draft`, p. 3.2.3), a zgodność manifestu z zainstalowanym narzędziem sprawdza
`retman-scaffold --check`. Każda operacja deklaruje też **co przyjmuje** (`inputs`) i **co zwraca**
(`outputs`) — na tej podstawie działa przestrzeń robocza (rozdz. 5), a w v0.2 łańcuchy (p. 4.5).

Klucze narzędzia: `tool`, `distribution` (nazwa pakietu do sprawdzenia wersji), `source`
(wymaganie dla `--with` w podpowiedziach `retman doctor`, p. 9.4), `supported_versions`,
`translations`, `operations` oraz `client` — fabryka klienta narzędzia (`"moduł:funkcja"`,
p. 3.2.4), wymagana, gdy któraś operacja deklaruje `calls`.

```python
# src/retman/tools/hydrolog/manifest.py — a tool without a command catalog: operations with a handler
MANIFEST = {
    "tool": "hydrolog",
    "distribution": "hydrolog",              # package name for the installed-version check
    "source": "git+https://github.com/Daldek/Hydrolog",  # for `--with` in retman doctor hints (p. 9.4)
    "supported_versions": ">=1.1,<2",        # checked at startup and in CI (p. 3.2.7)
    "translations": {"pl": "pl.toml"},       # relative to this package
    "operations": [
        {
            "id": "peak_flow",
            "category": "flows",
            "description": "Peak flow with a given exceedance probability",
            "inputs": [
                # Catchment characteristics: from a file, a previous result (ch. 5)
                # or, from v0.2, an earlier chain step.
                {"name": "catchment", "kind": "catchment_characteristics"},
            ],
            "outputs": ["peak_flow"],
            "params": [
                {
                    "name": "method",
                    "type": "choice",
                    "options": ["punzet", "bogdanowicz_stachy", "scs_cn"],
                    "default": "punzet",       # used when the command does not specify a method
                },
                {
                    "name": "probability",
                    "type": "free",
                    "extractor": "probability",  # a number, not a list (p. 4.4)
                    "required": True,
                    "multiple": True,            # e.g. "Q1% i Q10%"
                    "range": [0.0001, 0.5],      # allowed range, example values
                },
            ],
            "handler": "retman.tools.hydrolog.handlers:compute_peak_flow",
        },
    ],
}
```

Operacja narzędzia z katalogiem komend (Kartograf, IMGWTools) zamiast handlera ma budowniczego
wywołań, a do tego podgląd i sprawdzenie. Fragment manifestu Kartografa:

```python
# src/retman/tools/kartograf/manifest.py (fragment)
MANIFEST = {
    "tool": "kartograf",
    "distribution": "kartograf",
    "source": "git+https://github.com/Daldek/Kartograf",
    "supported_versions": ">=0.8.0,<0.9",
    "translations": {"pl": "pl.toml"},
    "client": "retman.tools.kartograf.client:create",    # factory(settings) -> RunClient (p. 3.2.4)
    "operations": [
        {
            "id": "download_dem_sheet",
            "category": "spatial_data",                   # first stage of the recognition (p. 3.4)
            "description": "Download a GUGiK digital terrain model for a map sheet",
            "inputs": [],
            "outputs": ["dem", "dem_archive"],
            "commands": ["elevation download"],           # commands the builder may use (p. 3.2.3)
            "calls": "retman.tools.kartograf.calls:download_dem_sheet",          # pure builder: params → catalog calls
            "describe": "retman.tools.kartograf.describe:download_dem_sheet",    # runs → files, values, warnings
            "preview": "retman.tools.kartograf.preview:download_dem_sheet",      # offline: plan rows and problems
            "check": "retman.tools.kartograf.checks:download_dem_sheet",         # network step on request (p. 6.5)
            "params": [
                {"name": "area", "type": "free", "extractor": "area",
                 "accepts": ["sheet", "geometry"], "required": True},
                {
                    "name": "resolution",
                    "type": "choice",
                    "options": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m", "100m"],
                    "tool_values": {"0_15m": "0.15m", "0_5m": "0.5m", "0_6m": "0.6m"},  # option keys have no dots
                    "required": True,
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "tool_values": {"evrf2007": "EVRF2007", "kron86": "KRON86"},
                    "required": True,
                    # NMT 100 m has no height system: asking would be a question the call drops
                    "depends_on": {"resolution": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m"]},
                },
            ],
        },
        # ... download_sheet_hierarchy, download_elevation_cutout, download_bdot10k
    ],
}
```

Operacja `download_sheet_hierarchy` ma obok `calls` także `handler`: ortofotomapa z wariantem
barwnym (RGB, CIR, B/W) idzie przez klasę dostawcy narzędzia, bo komenda katalogu `imagery download`
nie ma opcji koloru (ADR-013). Ma też `excluded` — wartości narzędzia, których Retman świadomie
nie wystawia, z uzasadnieniem (np. `"resolution": {"100m": "NMT 100 m is published as province
files, not as sheets"}`); kontrola pokrycia (p. 3.2.3) wymaga, by każda wartość narzędzia była
albo oferowana, albo tu wymieniona.

### 4.2. Teksty dla użytkownika i modelu (pliki tłumaczeń)

Pytania do basala, opisy opcji i etykiety w planie są w plikach tłumaczeń, z kluczami
odpowiadającymi identyfikatorom z manifestu. Każde narzędzie ma w Retmanie własny plik, a rdzeń
własny (`src/retman/i18n/pl.toml`: plan, dialog, CLI, wyniki, dziennik, błędy, ostrzeżenia,
sprawdzenie dostępności, rodzaje danych, `retman init`, `retman doctor`, ekstraktory).

```toml
# src/retman/tools/hydrolog/pl.toml

[operations.peak_flow]
label = "Obliczenie przepływu maksymalnego"
description = "Obliczenie przepływu maksymalnego o zadanym prawdopodobieństwie: przepływ miarodajny, woda stuletnia"

[operations.peak_flow.params.method]
label = "Metoda"
question = "Jaką metodą policzyć przepływ?"
model_question = "Jaką metodę wymienia polecenie?"
options.punzet.label = "Metoda Punzeta"
options.punzet.description = "Metoda Punzeta, Punzet"
options.bogdanowicz_stachy.label = "Metoda Bogdanowicz-Stachy"
options.bogdanowicz_stachy.description = "Metoda Bogdanowicz-Stachy, Bogdanowicz i Stachý"
options.scs_cn.label = "Metoda SCS-CN"
options.scs_cn.description = "Metoda SCS-CN, Soil Conservation Service, curve number, CN"
options.unspecified.description = "Polecenie nie określa metody"

[operations.peak_flow.params.probability]
label = "Prawdopodobieństwo przewyższenia"
```

Zasady:
- `label` operacji i opcji to krótka nazwa pokazywana użytkownikowi (plan, pytania, lista
  operacji); `description` trafia tylko do modelu decyzyjnego i może zawierać synonimy,
  określenia potoczne oraz nazwy i skróty angielskie (DEM, DSM, SHP), bo to one pomagają
  dopasować polecenie i odpowiedź użytkownika (ADR-007). Opcja `unspecified` nie jest
  pokazywana użytkownikowi, więc ma tylko `description`.
- `question` to pytanie dla użytkownika („Czy pobrać NMT w rozdzielczości 1 m czy 5 m?”);
  parametr wybierany przez model (`choice`, `bool`) ma też `model_question` — pytanie
  o to, **co wymienia polecenie** („Jaką rozdzielczość wymienia polecenie?”). Model dostaje
  je przy poleceniu i przy odpowiedzi użytkownika własnymi słowami; pytanie w formie
  „czy X, czy Y?” model odczytuje jako niewiadomą i częściej wybiera `unspecified`
  (ADR-008).
- Parametr `free` ma też `example` (przykład formatu w pytaniu), a każdy parametr może
  mieć `help` (odpowiedź na `?`, p. 6.4).
- Klucze opcji i kategorie to proste słowa `[a-z0-9_]+`: kropka w kluczu psuje wyszukiwanie
  tłumaczeń (rozdziela ono klucze po kropkach). Wartość narzędzia z kropką ma więc osobny klucz
  i wpis `tool_values` — rozdzielczość „0,5 m” to opcja `0_5m` odpowiadająca wartości `0.5m`
  narzędzia (p. 4.3).
- Test automatyczny (`validate_manifest`) sprawdza, że każda operacja, parametr i opcja ma tekst
  w każdym obsługiwanym języku; dla operacji z `check` także `check.notice`, a dla parametru
  czytanego przez ekstraktor tylko teksty dla użytkownika (bez tekstów dla modelu). Brak
  tłumaczenia = test nie przechodzi.

W `[operations.<id>]` oprócz `label` i `description` mogą być: `summary` — szablon wiersza
wyniku (miejsca na klucze `values` wyniku oraz `number`, `operation`, `directory`; bez niego
działa ogólny tekst rdzenia), `check.notice` — zdanie o tym, co sprawdzenie dostępności
kontaktuje (obowiązkowe przy `check`, p. 6.5), a w parametrze obszaru `geometry_note` — zdanie
dopisywane w planie do obszaru z pliku geometrii, które mówi, co ta operacja z nim robi.
Poza `[operations.*]` plik narzędzia ma tabele obsługujące rozpoznawanie i komunikaty:

| Tabela | Treść |
| --- | --- |
| `[categories.<id>]` | `label` i `description` kategorii (dla modelu i użytkownika); wymagane dla każdej kategorii, gdy łączna liczba operacji przekracza 9 (rozpoznawanie dwustopniowe, p. 3.4); tekst bierze się od pierwszego narzędzia, które opisuje kategorię |
| `[errors.<kod>]` | tekst Retmana dla stabilnego kodu błędu narzędzia (miejsca `{tool}`, `{code}`, `{detail}`, `{hint}`, `{option}`, `{option_label}`, `{allowed}`); tekst samego narzędzia pojawia się tylko jako `{detail}`; bez wpisu działa ogólny tekst rdzenia |
| `[problems.<klucz>]` | teksty problemów podglądu (`PreviewProblem.key`, p. 3.2.4) |
| `[preview.<klucz>]` | `label` i `value` dodatkowego wiersza planu z podglądu |
| `[check.<klucz>]` | linie raportu sprawdzenia dostępności (`CheckItem.key`) |
| `[warnings.<klucz>]` | teksty ostrzeżeń składanych przez Retmana (kody uwag narzędzia i klucze `HandlerWarning`); inne uwagi `warning` i `error` narzędzia są pokazywane dosłownie za ogólnym tekstem rdzenia, a uwagi `info` zostają w śladzie audytowym. Gdy jedno wywołanie zgłasza ponad 5 uwag o tym samym kodzie, wynik pokazuje pierwsze 3 i jedną linię `tool_notices_more` z liczbą pozostałych (pełna lista zostaje w dokumencie narzędzia `tool_<n>_<komenda>.json`) |

### 4.3. Typy parametrów i pola operacji

| Typ parametru | Skąd wartość | Przykłady |
| --- | --- | --- |
| `choice` | model decyzyjny, wybór z listy (najwyżej 9 opcji, z `unspecified` 10; p. 3.4); z kluczem `extractor` — kod (ekstraktor), bez modelu | metoda, rodzaj danych, rozdzielczość, zbiór danych; układ wyniku wycinka (`crs`), rodzaj roku (`year_type`) |
| `free` | ekstraktor w kodzie | współrzędne, punkt, data, okres, lata, prawdopodobieństwo, czas trwania, powierzchnia, stacja, zmienne, ścieżka pliku, nazwa |
| `bool` | model decyzyjny, tak/nie | „czy uwzględnić retencję?” |

Dodatkowe klucze parametrów: `required`, `default`, `multiple` (kilka wartości naraz; wartość
podana pojedynczo jest opakowywana w listę), `range` (dozwolony zakres dla liczb), `accepts`
(które rodzaje wartości ekstraktora przyjmuje operacja, np. ekstraktor `area` daje godło arkusza,
prostokąt, kod TERYT albo plik z geometrią, a wycinek przyjmuje tylko `["bbox", "geometry"]`),
`depends_on` (parametr dotyczy tylko wybranych wartości innego parametru `choice`, np.
rozdzielczość tylko dla NMT: `{"product": ["dem"]}`). Dla `choice` dochodzą jeszcze trzy klucze.

- `option_values` (z kluczem `extractor`): klucz opcji → wartość ekstraktora, np.
  `{"epsg_2180": "EPSG:2180"}`. Wartość ustala wtedy kod: dokładnie jedna obsługiwana wartość
  z polecenia → plan; brak, kilka albo wartość nieobsługiwana → pytanie z listą opcji. Model nie
  dostaje takiego parametru, więc nie ma on `model_question` ani opisów opcji dla modelu
  (ADR-009). Stosujemy to tam, gdzie model myli rolę wartości w zdaniu — np. układ prostokąta
  wejściowego z układem wyniku — albo gdzie wolno pytać tylko o to, co użytkownik rzeczywiście
  powiedział (rodzaj roku).
- `tool_values`: klucz opcji → wartość, jaką zna narzędzie, gdy się różnią, np.
  `{"0_5m": "0.5m", "evrf2007": "EVRF2007"}`. Budowniczy wywołań czyta ją przez
  `ctx.tool_value(parametr, klucz)`; bez wpisu wartością narzędzia jest sam klucz. Wartości
  narzędzia muszą być niepuste i unikalne w obrębie parametru.
- `option_meta`: klucz opcji → nieprzezroczysty słownik JSON dla budowniczych i ekstraktorów
  kontekstowych, np. dostawca, rodzaj i zmienne zbioru danych (`ctx.option_meta(parametr,
  klucz)`). Klucze `tool_values` i `option_meta` muszą być kluczami opcji.

| Pole operacji | Znaczenie |
| --- | --- |
| `id` | identyfikator (po angielsku), unikalny w całym Retmanie |
| `category` | kategoria (`[a-z0-9_]+`) — pierwszy stopień rozpoznawania dwustopniowego (p. 3.4) |
| `description` | krótki opis po angielsku (dla programistów; tekst dla użytkownika jest w tłumaczeniach) |
| `inputs` | wejścia: nazwa + rodzaj danych (`kind`); źródło to plik, przestrzeń robocza, (v0.2) wcześniejszy krok łańcucha |
| `outputs` | rodzaje danych zwracanych przez operację |
| `params` | parametry |
| `handler` | handler w Retmanie (`moduł:funkcja`), wołany jako `handler(params, inputs, output_dir, ctx)` — dla operacji, które muszą obrobić wynik (p. 3.2.4) |
| `calls` | czysty budowniczy wywołań (`moduł:funkcja`) `calls(params, ctx) -> list[CatalogCall]`; wołany offline w planowaniu (walidacja przez narzędzie) i przy wykonaniu przez wspólnego wykonawcę (p. 3.2.4) |
| `commands` | komendy katalogu, których budowniczy może użyć (inwentarz dla kontroli zgodności, p. 3.2.3); niepuste przy `calls` |
| `describe` | mapper wyników wywołań na `HandlerOutput` (`moduł:funkcja`); wymaga `calls`, bez niego działa mapowanie ogólne |
| `excluded` | świadomie nieobsługiwane wartości narzędzia w parametrach `choice`: `{parametr: {wartość narzędzia: uzasadnienie}}`; wartość nie może być jednocześnie oferowana, uzasadnienie jest niepuste (kontrola pokrycia, p. 3.2.3) |
| `preview` | funkcja offline `preview(params, ctx) -> PreviewOutput`, wołana, gdy plan jest kompletny (p. 3.2.4) |
| `check` | funkcja sprawdzenia dostępności `check(params, ctx) -> CheckOutput`; jej obecność włącza odpowiedź `s` (p. 6.5) i wymaga tekstu `check.notice` |
| `no_check` | jawne, przejrzane uzasadnienie (po angielsku, dla opiekunów), dlaczego operacja z komendą sieciową i zapisującą nie ma kroku `check`; wyklucza `check`, akceptuje je kontrola X7 |

Operacja deklaruje co najmniej jedno z `handler` i `calls` (handler może sam wołać wspólnego
wykonawcę, p. 3.2.4); `calls` wymaga niepustego `commands` i klucza `client` w narzędziu;
`handler`, `calls`, `describe`, `preview`, `check` i `client` to odwołania `"moduł:atrybut"`
importowane leniwie. `validate_manifest` sprawdza przy ładowaniu także: unikalność `id`, znane
rodzaje danych (`kind`), `default` wśród opcji, spójność `depends_on`, `option_values`,
`tool_values`, `option_meta` i `excluded` oraz komplet tłumaczeń. Przy więcej niż 9 operacjach
loader wymaga co najwyżej 9 kategorii, co najwyżej 9 operacji w kategorii i tekstów każdej
kategorii (p. 3.4).

**Ekstraktory** (wartości czyta kod, nigdy model; rejestr w `src/retman/extractors/__init__.py`).
Ekstraktory kontekstowe (`station`, `years`, `period`, `variables`) dostają dodatkowo
`ExtractionContext`: ustawienia `[retman.tools.<narzędzie>]`, folder projektu, dzisiejszą datę (stałą
w obrębie jednego `Retman`, więc planowanie jest powtarzalne), `scope` — scalone `option_meta`
opcji już wybranych w parametrach `choice` (np. dostawca, rodzaj i zmienne zbioru danych;
parametr zbioru musi więc stać w manifeście przed stacją i zmiennymi) oraz `lookup` — offline
wyszukiwanie w katalogu narzędzia (`PlanClient.lookup`; jedyne takie wyszukiwanie to lista stacji
z magazynu IMGWTools, `stations find` ze `source=store`). Nie importują narzędzi i nie używają sieci.

| Ekstraktor | Co czyta | Wartość |
| --- | --- | --- |
| `area` | godło arkusza (także 8-członowe godło PL-1992), prostokąt w PL-1992 albo WGS84, kod TERYT powiatu, plik geometrii (SHP, GPKG) | `{type: sheet\|bbox\|teryt\|geometry, …}`; geometria: `{type: geometry, path, layer}` (p. 6.1) |
| `crs` | układ współrzędnych wyniku (nie prostokąta wejściowego) | `EPSG:<kod>` przez `option_values` |
| `point` | punkt WGS84 albo PL-1992; kolejność osi nigdy nie jest zgadywana | `{type: point, latitude, longitude, input_crs}` (PL-1992: także `easting`, `northing`) |
| `grid_cell` | komórka siatki PMAXTP („751/317”) | `{type: grid_cell, ind_x, ind_y}` |
| `probability` | prawdopodobieństwo i okres powtarzalności (p. 4.4) | ułamek `p` (lista przy `multiple`) |
| `duration` | czas trwania opadu („15 min”, „2 godziny”, „półgodzinny”) | liczba minut (lista przy `multiple`) |
| `station` | stacja IMGW-PIB albo ČHMÚ po kodzie (9 cyfr, WIGOS) albo po nazwie, offline z katalogu w magazynie; zawężana przez `scope` (dostawca, rodzaj) | `{type: station, provider, kind, code, name, river, in_catalog}` |
| `synop_station` | stacja synoptyczna (kod 5 cyfr albo fragment nazwy) | `{type: synop_station, code, name}` |
| `place_query` | fragment nazwy stacji albo rzeki do wyszukiwania (odmieniona forma sprowadzona do tematu) | `{type: query, text, raw}` |
| `years` | lata archiwów w numeracji narzędzia („2000–2020”, „2010, 2012 i 2015”) | `{type: years, first, last}` albo `{type: year_list, years}` |
| `period` | okres: lata albo daty („od 1 stycznia 2000 do 31 grudnia 2020”) | wartość `years` albo `{type: dates, start, end}` |
| `year_type` | rok hydrologiczny albo kalendarzowy; przy braku w poleceniu zawsze pytanie | wybór `hydrological` / `calendar` przez `option_values` |
| `variables` | zmienne pomiarowe zbioru danych (kody albo słowa: „przepływ”, „stan wody”), sprawdzane względem `scope["variables"]` | lista kodów zmiennych |
| `identifier` | nazwa nadana przez użytkownika (np. zadania projektu) | tekst zgodny z `^[a-z0-9][a-z0-9_-]{0,63}$` — bez cichego „poprawiania” |
| `path` | ścieżka pliku wymieniona w poleceniu | ścieżka |
| `result` | numer wyniku („#3”, p. 5.2) | liczba |

### 4.4. Prawdopodobieństwo i okres powtarzalności [W-08]

Prawdopodobieństwo jest **liczbą**, bo obliczenia można wykonać dla dowolnej wartości.
Wyciąga je ekstraktor `probability` w kodzie, bez udziału modelu. W operacjach PMAXTP (IMGWTools)
służy jako **filtr wyjścia**: żądanie do narzędzia nie przyjmuje prawdopodobieństwa, a tabela
wyniku ma ich wiele, więc wartość z polecenia nie ginie po cichu (podobnie czas trwania opadu,
ekstraktor `duration`).

**Przechowywanie:** zawsze jako ułamek `p` (np. `0.01`). W planie pokazywane jako procent
i okres powtarzalności: „1% (T = 100 lat)”, gdzie T = 1/p.

**Rozpoznawane formy:**

| Zapis w poleceniu | Wynik |
| --- | --- |
| „1%”, „p = 1%”, „Q1%”, „Q 1 %” | 0.01 |
| „prawdopodobieństwo 0,01” | 0.01 |
| „woda stuletnia”, „przepływ stuletni” | 0.01 |
| „pięćdziesięcioletnia”, „okres powtarzalności 50 lat”, „T = 50”, „raz na 50 lat” | 0.02 |
| „Q1% i Q10%” | [0.01, 0.10] (gdy `multiple`) |
| „dla 1, 2 i 10%” | [0.01, 0.02, 0.10] (gdy `multiple`) |

Przymiotniki liczebnikowe („dziesięcioletnia”, „dwudziestoletnia”, „pięćsetletnia”,
„tysiącletnia” itd.) rozpoznaje słownik w kodzie, pokryty testami.

**Zapisy niejednoznaczne — Retman dopytuje:**

| Zapis | Problem | Reakcja |
| --- | --- | --- |
| „Q50”, „Q20”, „Q2” (bez %) | może oznaczać p = 50% albo T = 50 lat (p = 2%) | pyta, o które chodzi |
| „Q10” | oba odczyty dają 10% | przyjmuje 10%, bez pytania |
| „Q1”, „Q100”, „Q500” | jeden z odczytów (T = 1 rok albo p = 100% i więcej) jest niemożliwy | „Q1” przyjmuje jako 1%; „Q100” i „Q500” jako T (1%, 0,2%) i pokazuje to w planie |
| „dla 1”, „dla 0,5” (liczba bez „%”, bez „Q” i bez okresu w latach) | 1% czy p = 1? 0,5% czy p = 0,5? | **zawsze** pyta — także gdy jeden z odczytów jest niemożliwy |
| „Q50 i Q10” (lista z niejednoznacznym elementem) | ten sam problem dla każdego elementu | cała lista ma kilka odczytów (p = 50%, 10% albo T = 50 lat, p = 10%): pyta o odczyt całej listy, nie miesza ich |

Liczba bez znaku („%”, „Q”, „T =”, okresu w latach) jest czytana tylko po słowie wskazującym
(„dla”, „prawdopodobieństwo”, „p =”) albo w liście rozpoczętej takim słowem — nigdy jako część
punktu, daty, roku, godła arkusza ani innej liczby.

**Walidacja:** `0 < p < 1` (obie granice wyłączone) oraz zakres `range` z manifestu operacji
(metoda może mieć własne ograniczenia). Wartość poza zakresem → komunikat z dozwolonym zakresem.

### 4.5. Łańcuchy operacji (v0.2) [W-12]

Deklaracje `inputs`/`outputs` są wpisywane już w v0.1, gdzie służą do wyszukiwania danych
w przestrzeni roboczej (rozdz. 5). Resolver opisany poniżej powstaje w v0.2.
Alternatywa do oceny po dodaniu kolejnych narzędzi — łańcuchy jako przepisy autora: rozdz. 12
pkt 14.

Model **nie planuje** łańcuchów. Wybiera tylko cel, a kolejne kroki wynikają z deklaracji
`inputs`/`outputs` — podobnie jak w arkuszu kalkulacyjnym formuły liczą się w kolejności zależności.

**Przykład:** *„Policz przepływ stuletni metodą Punzeta dla punktu 52.41, 16.93”*

1. basal rozpoznaje cel: `peak_flow` (Hydrolog).
2. Operacja potrzebuje wejścia `catchment_characteristics`, a polecenie podaje tylko punkt.
3. Resolver znajduje operację, która to wejście zwraca: `delineate_catchment` (Hydrograf),
   i dokłada ją przed obliczeniem.
4. Użytkownik zatwierdza plan z dwoma krokami: zlewnia → przepływ.

**Algorytm (resolver):**

1. Model decyzyjny rozpoznaje operację docelową.
2. Dla każdego wejścia resolver sprawdza po kolei:
   1. czy polecenie wskazuje plik albo wcześniejszy wynik (rozdz. 5) → bierze go,
   2. czy istnieje operacja, która zwraca ten rodzaj danych → dokłada krok,
   3. jeśli nie → dopytuje użytkownika.
3. Krok 2 powtarza się dla dokładanych operacji, aż wszystkie wejścia są znane.
4. Jeśli wejście może dostarczyć kilka operacji, wybór należy do modelu decyzyjnego (pytanie `choice`)
   albo do użytkownika, gdy pewność jest niska.
5. Resolver wykrywa cykle i brak zainstalowanego narzędzia
   („do tego potrzebny jest Hydrograf” razem z poleceniem instalacji, p. 9.4).

**Wykonanie łańcucha:**

- Użytkownik zatwierdza **cały plan** (wszystkie kroki naraz), a nie każdy krok osobno.
- Pytania o brakujące parametry są zbierane z całego łańcucha i zadawane razem.
- Po każdym kroku wykonywana jest **kontrola sensowności** wyniku (np. powierzchnia zlewni
  w oczekiwanym zakresie, brak luk w danych). Przy niezgodności łańcuch zatrzymuje się
  i pokazuje, co jest podejrzane.
- Wyniki pośrednie trafiają do przestrzeni roboczej, więc po błędzie można wznowić
  łańcuch od miejsca, w którym się zatrzymał.

---

## 5. Przestrzeń robocza [W-07]

Przestrzeń robocza pozwala kolejnemu poleceniu skorzystać z wyniku poprzedniego. Bez niej
w v0.1 nie dałoby się wykonać operacji, które potrzebują złożonych danych wejściowych
(np. charakterystyki zlewni), bo takich danych nie da się podać w jednym zdaniu.

### 5.1. Projekt = folder

Przestrzeń robocza należy do **projektu**, a projekt to folder, w którym uruchamia się Retmana.
Wyniki trafiają do podfolderu wyników w tym folderze; jego nazwę określa ustawienie `output.results_dir`
(domyślnie `retman-output`, p. 9.1). Wyniki z różnych projektów nigdy się nie mieszają.

```
~/projekty/zlewnia-a/              ← tu uruchamiasz: cd ~/projekty/zlewnia-a && retman
└── retman-output/                 ← tworzony przy pierwszym wyniku
    ├── 001_delineate_catchment/
    │   ├── catchment.geojson
    │   └── result.json
    └── 002_peak_flow/
        └── ...
```

Pliki wyniku leżą w jego podfolderze albo — gdy narzędzie trzyma dane w swoim magazynie —
w magazynie, który leży poza folderem projektu i jest wspólny dla projektów (p. 9.1): wynik
wskazuje wtedy te pliki ścieżką bezwzględną i sumą SHA-256 (p. 5.4), niczego nie kopiując.
Wynik może być wejściem kolejnej operacji w obu przypadkach (p. 5.3).

### 5.2. Numery wyników

- Każdy wynik dostaje **kolejny numer w projekcie** (#1, #2, …), który Retman pokazuje
  po wykonaniu, np. „Wynik #1: zlewnia, punkt 52.41° N, 16.93° E — 118,4 km²”.
- Numer jest częścią nazwy podfolderu (`001_delineate_catchment/`) i jest zapisany
  w `result.json` razem z operacją, parametrami, rodzajami wyjść (`kind`), datą, plikami
  i krótkim opisem, który pozwala odróżnić wyniki od siebie (pełna zawartość: p. 5.4).
- Do wyniku można odwołać się wprost: *„Policz Q1% dla zlewni #1”*. Numer wyciąga ekstraktor
  `results` (kod, bez modelu).
- `retman results` wyświetla listę wyników bieżącego projektu.

### 5.3. Wybór wejścia — bez zgadywania

Gdy operacja potrzebuje wejścia danego rodzaju (np. `catchment_characteristics`):

| Sytuacja | Co robi Retman |
| --- | --- |
| polecenie wskazuje plik („…z pliku warta.geojson”) albo numer wyniku („#1”) | bierze dokładnie to; plik sprawdza walidator rodzaju danych (p. 3.2.6) |
| w projekcie jest **jeden** pasujący wynik | proponuje go w planie, wyraźnie oznaczony |
| pasujących wyników jest **więcej niż jeden** | **zawsze pyta**, którego użyć — także wtedy, gdy jeden z nich jest najnowszy |
| nie ma żadnego | mówi, czego brakuje i jak to uzyskać (np. „najpierw wyznacz zlewnię”) |

Retman **nie próbuje odgadnąć**, o który wątek chodzi użytkownikowi. Przy więcej niż jednej
możliwości pyta, więc mieszanie wątków w jednym projekcie nie prowadzi do cichych pomyłek.
Kandydaci są opisani tym, co pozwala ich odróżnić: numerem, najważniejszymi parametrami i czasem.

```
? Której zlewni użyć?
  1) #1  punkt 52.41, 16.93 — 118,4 km² (dziś 14:32)
  2) #3  punkt 52.28, 17.05 — 36,1 km² (dziś 15:10)
> 1
```

**Przykład pracy krok po kroku** (w projekcie jest jedna zlewnia):

```bash
retman "Wyznacz zlewnię dla punktu 52.41, 16.93"            # → Wynik #1
retman "Policz przepływ stuletni Punzetem dla tej zlewni"
```

Plan drugiego polecenia:

```
Plan:
  Operacja:                          Obliczenie przepływu maksymalnego
  Zlewnia:                           ← wynik #1: punkt 52.41° N, 16.93° E, 118,4 km² (2026-10-11 14:32)
  Metoda:                            Punzet
  Prawdopodobieństwo przewyższenia:  1% (T = 100 lat)
Wykonać? [t]ak / [n]ie / [z]mień
```

Ponieważ każde wykonanie wymaga potwierdzenia (p. 6.3), użytkownik zawsze widzi, który wynik
został użyty, i może go zmienić (`z`).

### 5.4. Dziennik projektu i ślad audytowy [W-15]

Cel: z samego folderu projektu da się ustalić, **co, czym i jak** zostało policzone — także po
miesiącach i na innym komputerze. To ważne zwłaszcza dla administracji, która wydaje decyzje na
podstawie obliczeń.

Wyjątek: przy `journal_commands = false` (p. 9.1) `result.json` i dziennik nie zawierają treści
poleceń ani odpowiedzi użytkownika, a dziennik także innych pokazanych użytkownikowi tekstów,
które mogą je cytować (planu, powodu ponownego zadania pytania, linii raportu dostępności);
pozostałe dane audytowe są zapisywane zawsze (PRD W-15).

**1. Dane audytowe w `result.json`** (przy każdym wyniku):

| Sekcja | Zawartość |
| --- | --- |
| `number`, `operation` | numer wyniku i wykonana operacja |
| `command` | polecenie użytkownika i odpowiedzi na pytania Retmana (jeśli `journal_commands = true`, p. 9.1) |
| `params` | każda użyta wartość razem ze źródłem: `command`, `default`, `workspace`, `known`, `user` (p. 7.1); dla obszaru z pliku geometrii wartość niesie też wybraną warstwę, a wpis ma `files` — sumy kontrolne SHA-256 plików geometrii według nazw (Shapefile: `.shp`, `.shx`, `.dbf`, `.prj`) |
| `decisions` | decyzje modelu: pytanie, wybrana opcja, prawdopodobieństwa, pewność i jej metoda (`basal`, `logprobs`, `consistency`, `none`) |
| `inputs` | źródło każdego wejścia: wynik #N albo plik — ścieżka i suma kontrolna SHA-256, żeby było widać, czy plik później się zmienił |
| `outputs`, `values`, `files`, `warnings`, `error` | jak w `Result` (p. 7.3); każdy plik wynikowy z sumą kontrolną SHA-256: ścieżka względna wobec projektu, a dla pliku w magazynie narzędzia ścieżka bezwzględna i `store` (nazwa narzędzia) |
| `error_code` | stabilny kod błędu narzędzia, gdy operacja nie powiodła się z jego powodu (tylko wtedy) |
| `tool` | blok wywołań katalogu narzędzia (tylko operacje przez warstwę komend, p. 3.2.4): narzędzie i jego wersja oraz dla każdego wywołania komenda, opcje, dokładna linia komendy (z argumentami środowiskowymi), schemat dokumentu, status, pliki (ścieżka, SHA-256, etykieta wersji, status) i nazwa oraz suma SHA-256 pełnego dokumentu narzędzia, zapisanego w folderze wyniku jako `tool_<n>_<komenda>.json` |
| `unset` | parametry nieobowiązkowe, których polecenie nie podało, z tekstem, co to znaczy (p. 6.3); tylko gdy niepuste |
| `preview` | wartości ustalone przez podgląd offline (np. obwiednia obszaru, liczba arkuszy); tylko gdy niepuste |
| `checks` | raporty sprawdzeń dostępności wykonanych dla końcowego stanu planu (`CheckReport.to_dict()`, p. 6.5); tylko gdy były |
| `environment` | wersja Retmana, wersje użytych narzędzi, model decyzyjny (backend, nazwa, adres serwera), wersja Pythona, system |
| `timing` | zatwierdzenie planu, początek i koniec wykonania, czas trwania |

**2. Dziennik projektu** — `retman-output/journal.jsonl`, jeden wiersz na zdarzenie:

| Zdarzenie | Zapisywane |
| --- | --- |
| polecenie | treść (jeśli `journal_commands = true`), czas, identyfikator sesji |
| pytanie i odpowiedź | treść pytania, odpowiedź użytkownika (jeśli `journal_commands = true`); przy pytaniu zadanym ponownie po odrzuceniu przez narzędzie także powód (`reason`, jeśli `journal_commands = true`) |
| plan | pokazany plan i jego decyzja: **zatwierdzony / odrzucony / zmieniony / anulowany**; do tego dane: wartości ze źródłami (`values`, `inputs`), otwarte pytania, decyzje modelu z pewnością (`decisions`), a przy zmianie — nazwa zmienianej wartości (`changed`) |
| poza zakresem | decyzja modelu, że polecenie nie dotyczy żadnej operacji (z pewnością) |
| sprawdzenie dostępności | `check` (p. 6.5): zgoda i wykonanie (`approved`, „wykonane”) albo odmowa zgody (`rejected`, „pominięte”, bez użycia sieci); wynik (`available`, `partial`, `unavailable`, `unknown`), błąd, narzędzie i jego wersja, linie raportu (jeśli `journal_commands = true`) oraz dane planu, które zostały wysłane (wartości ze źródłami, wejścia, decyzje modelu); zapisywane także przy przerwaniu (Ctrl+C); nie trafia do zbioru poleceń (ADR-010) |
| wykonanie | numer wyniku albo opis błędu |

Dziennik jest **tylko dopisywany** — Retman nigdy nie zmienia ani nie usuwa wpisów. Zapisuje
też to, co **nie** zostało wykonane (odrzucone plany, anulowanie, błędy), bo to także część
historii pracy.

`retman log` pokazuje dziennik w czytelnej formie:

```
$ retman log
2026-10-11 14:31  polecenie: „Wyznacz zlewnię dla punktu 52.41, 16.93”
2026-10-11 14:31  plan zatwierdzony → wynik #1 (zlewnia, 118,4 km², 12 s)
2026-10-11 15:02  polecenie: „Policz przepływ dla tej zlewni”
2026-10-11 15:02  pytanie: Której zlewni użyć? → #1
2026-10-11 15:03  plan odrzucony
```

`retman log` pokazuje też zdarzenie „sprawdzenie dostępności” z rozstrzygnięciem „wykonane”
albo „pominięte”.

**3. Log techniczny** — osobny, do diagnozowania problemów Retmana (połączenia, czasy odpowiedzi,
błędy); biblioteka loguje przez `logging`, a CLI wypisuje log na stderr (DEV-12). **Bez treści
poleceń i odpowiedzi.** Poziom: `--verbose` (debug) albo `--quiet` (tylko błędy), potem
`RETMAN_LOG_LEVEL`, `NOGAT_LOG_LEVEL` i ustawienie `log_level` w `[retman]` i `[nogat]` (p. 9.1); domyślnie
`warning`.

**4. Zbiór poleceń** (opcjonalny, ADR-010) — jeden plik ze **wszystkich** projektów, do budowy
i strojenia zbioru testowego (`retman-eval`). Każdy wiersz to wynik planowania: status
(zatwierdzony z wynikiem wykonania, odrzucony, zmieniony, anulowany, poza zakresem),
polecenie, odpowiedzi, wartości ze źródłami, pytania, decyzje modelu, wersje Retmana
i narzędzia, backend i nazwa modelu — **bez adresu serwera** i bez ścieżek lokalnych (z pliku
geometrii zostaje nazwa). Włącza go tylko wyraźna zgoda: `retman init` pyta o to w terminalu,
bez terminala zapisuje `false`; ścieżka pliku jest wpisana w `[retman.privacy]` (`collect_path`,
domyślnie `<data_dir>/retman/collected.jsonl`: w Linuksie `~/.local/share/nogat/retman/collected.jsonl`,
w macOS `~/Library/Application Support/nogat/retman/collected.jsonl`, w Windows
`%LOCALAPPDATA%\nogat\retman\collected.jsonl`). Zbiór jest niezależny od `journal_commands`;
`retman-eval` nigdy do niego nie pisze. Plik zostaje na komputerze użytkownika.

**Cztery rzeczy, których nie należy mylić:**

| Co | Gdzie | Treść poleceń |
| --- | --- | --- |
| dziennik projektu + dane audytowe | folder projektu | **tak** — to zapis pracy użytkownika; można wyłączyć (`journal_commands`) |
| log techniczny | stderr (CLI) | nie |
| zbiór poleceń | jeden plik użytkownika (`collect_path`) | **tak**, tylko po wyraźnej zgodzie (`collect_commands`, rozdz. 10) |

### 5.5. Później (v0.2+)

- Nazwy wyników obok numerów („zapisz jako zlewnia_warta”).
- Przestrzeń robocza jako miejsce na wyniki pośrednie łańcuchów (p. 4.5).
- Ponowne wykonanie zapisanego planu na podstawie danych audytowych (np. `retman rerun #3`).

---

## 6. Dopytywanie i potwierdzanie

### 6.1. Kiedy Retman dopytuje [W-02], [W-03]

| Sytuacja | Reakcja |
| --- | --- |
| Pewność wyboru operacji < próg | Pokazuje 2–3 najbardziej prawdopodobne operacje do wyboru |
| Pewność wyboru kategorii < próg (rozpoznawanie dwustopniowe, p. 3.4) | Pokazuje 2–3 najbardziej prawdopodobne grupy operacji do wyboru; operację w wybranej grupie wskazuje potem model |
| Wybrano `out_of_scope` (w którymkolwiek stopniu rozpoznawania) | Informuje, że polecenie nie pasuje do żadnej operacji (przy rozpoznawaniu dwustopniowym — do żadnej grupy), i pokazuje listę dostępnych |
| Wymagany parametr = `unspecified` | Pyta o ten parametr, pokazując listę opcji |
| Pewność parametru < próg | Pyta: „Czy chodziło o X?” |
| Ekstraktor nic nie znalazł | Prosi o wartość i podaje przykład formatu |
| Ekstraktor znalazł kilka dopasowań (np. kilka stacji o podobnej nazwie) | Pokazuje kandydatów do wyboru |
| Dopasowanie nieścisłe: nazwa stacji tylko w formie odmienionej („w Poznaniu”, „z Opola”) | Pokazuje odczyt i prosi o jego potwierdzenie wyborem z listy; odmienionej nazwy nie przyjmuje po cichu. Nazw nie poprawia też po literówkach |
| Stacja podana nazwą, a w magazynie IMGWTools nie ma katalogu stacji | Katalog istnieje dopiero po operacji budującej go (sieć, po potwierdzeniu), więc do tego czasu Retman czyta tylko kody stacji (9 cyfr, WIGOS) i pyta o kod |
| Rodzaj roku (hydrologiczny czy kalendarzowy) nie padł w poleceniu | **Zawsze** pyta — nie ma wartości domyślnej. Słowo „hydrologiczne” opisujące dane („dane hydrologiczne z lat 2000–2020”) nie jest odpowiedzią |
| Okres względny lub otwarty („ostatnie 10 lat”, „od 2010”) | Nie zgaduje dat: prosi o lata albo daty. Sama czterocyfrowa liczba nie jest rokiem (może być kodem TERYT, godłem albo kodem EPSG) |
| W projekcie jest kilka pasujących wyników (np. kilka zlewni) | Pyta, którego użyć (p. 5.3) |
| Zapis niejednoznaczny (np. „Q50”, p. 4.4) | Pyta, który odczyt jest właściwy |
| Plik geometrii w GeoPackage z kilkoma warstwami | Pokazuje listę warstw do wyboru; warstwy nie zgaduje (jedna warstwa jest używana i pokazana w planie, Shapefile warstw nie ma) |
| Plik obszaru w formacie, którego narzędzia nie czytają (GeoJSON, GML) | Odmawia z powodem: geometria musi być plikiem SHP albo GPKG |
| Narzędzie odrzuca wybór offline (np. rozdzielczość i układ wysokościowy, które nie tworzą poprawnej pary) | Pyta ponownie o parametry, które narzędzie wskazało, z powodem w pytaniu (p. 6.3) |
| Brak wymaganego wejścia (ani w pliku, ani w przestrzeni roboczej) | Informuje, czego brakuje i jak to uzyskać |
| Wartość poza zakresem (np. współrzędne poza Polską, prawdopodobieństwo poza `range`) | Informuje i prosi o poprawkę |
| Prawdopodobnie zamieniona kolejność współrzędnych | Patrz uwaga niżej |

**Uwaga o współrzędnych.** Kolejność osi bywa myląca: w WGS84 ludzie piszą raz „szerokość, długość”,
raz odwrotnie, a w układzie PL-1992 (EPSG:2180) oś X oznacza kierunek północny, odwrotnie niż
w intuicyjnym „X = wschód”. Ekstraktor rozpoznaje układ i kolejność po etykietach i po rozłącznych
zakresach wartości dla Polski; para pasująca do obu kolejności daje dwa odczyty, więc Retman
pyta, zamiast wybierać. Współrzędne PL-1992 przelicza w czystym Pythonie, bez bibliotek
geoprzestrzennych i bez narzędzia. Plan zawsze pokazuje, jak Retman odczytał współrzędne
(np. „52.41° N, 16.93° E”), i prosi o potwierdzenie, gdy interpretacja jest niejednoznaczna.

### 6.2. Progi pewności [N-05]

- **Domyślnie** (`"auto"`) Retman bierze progi z kalibracji basala (`CALIBRATION.json`, poziom błędu 1%).
  Wartość `"auto"` jest dozwolona tylko z `backend = "basal"`.
- Można je **nadpisać** liczbą w konfiguracji (p. 9.1).
- Progi basala dobrano na prostych formatach pytań (opisy opcji, pytania tak/nie). Dla pytań
  Retmana należy je **dostroić na własnym zbiorze testowym** (rozdz. 8) i wpisać do konfiguracji.
- Osobny próg dla rozpoznania operacji (także wyboru kategorii, p. 3.4) i dla parametrów.
- Dla modeli bez skalibrowanej pewności progi z kalibracji basala nie mają zastosowania.
  Przy pewności z `logprobs` lub zgodności progi trzeba dostroić osobno dla danego modelu
  i wpisać liczbą; `"auto"` z backendem innym niż `basal` (np. `openai_compatible`) to **błąd
  konfiguracji** — Retman zgłasza go przy starcie, a `retman doctor` pokazuje go z podpowiedzią,
  bo Retman nie ma ukrytych wartości domyślnych (p. 9.1). W trybie `none` progi są pomijane
  (ich wartość nie jest sprawdzana), a wartości wybrane przez model są w planie oznaczone
  jako niezweryfikowane (p. 3.3.3).

### 6.3. Potwierdzenie [W-04], [W-05]

Przed wykonaniem Retman zawsze pokazuje plan w czytelnej formie, np.:

```
Plan:
  Operacja:      Pobranie danych pomiarowych IMGW
  Rodzaj:        opad
  Krok czasowy:  dobowy
  Stacja:        Poznań (kod stacji z listy IMGW)
  Okres:         2000-01-01 – 2020-12-31
  Format:        CSV   ← wartość domyślna, nie podano w poleceniu
Wykonać? [t]ak / [n]ie / [z]mień
```

Zasady:
- W wersjach 0.x **każde wykonanie wymaga potwierdzenia**. Nie ma trybu, który je pomija.
- Plan jest kompletny wtedy i tylko wtedy, gdy nie ma otwartych pytań. Gdy jest kompletny,
  narzędzie sprawdza go **offline** (podgląd, p. 3.2.4): waliduje każde wywołanie, które
  wykonałoby operację, i może dopisać do planu wiersze oznaczone `← podgląd, bez sieci` (np.
  liczbę arkuszy dla obszaru z pliku geometrii). Gdy narzędzie odrzuca wartość, Retman pyta
  ponownie o parametry, które narzędzie wskazało, z powodem w pytaniu — plan, którego narzędzie
  nie przyjmuje, nie da się potwierdzić. Wartości podanych z zewnątrz (`known`) nie otwiera
  ponownie, a gdy nie ma nic do otwarcia, zgłasza błąd (`RetmanError`) zamiast zapętlać pytania.
  Odrzucenie, którego żadna odpowiedź nie naprawi (zainstalowane narzędzie nie przyjmuje już
  tego, co opisuje manifest), kończy się błędem `ToolDriftError` z podpowiedzią `retman doctor`.
- Parametry uzupełnione wartością domyślną, odczyty niejednoznacznych zapisów, wejścia wzięte
  z przestrzeni roboczej i wiersze podglądu są wyraźnie oznaczone, żeby użytkownik mógł je zmienić.
- Parametr nieobowiązkowy (bez `required` i bez `default`), którego polecenie nie podało, nie jest
  pytaniem, ale ma w planie własny wiersz z tekstem `params.<p>.unset` (np. „Rodzaj stacji:
  wszystkie rodzaje (hydrologiczne i meteorologiczne) ← nie podano w poleceniu, parametr
  nieobowiązkowy”); `validate_manifest` wymaga tego tekstu, a `result.json["unset"]` go zapisuje
  (N-11: nic nie dzieje się po cichu).
- Potwierdzenie dotyczy dokładnie tego planu: każda zmiana (odpowiedź, `z`) i każde sprawdzenie
  dostępności (p. 6.5) je cofa. Kolejność to zawsze: sprawdzenie, potwierdzenie, wykonanie.
- W API Pythona `execute()` przyjmuje wyłącznie plan potwierdzony przez `plan.confirm()`.
  Bez tego zgłasza błąd `PlanNotConfirmedError`. Potwierdzenia nie przenosi serializacja:
  `Plan.from_dict` zawsze zwraca plan niepotwierdzony (p. 7.1).
- Testy jakości (rozdz. 8) sprawdzają planowanie, nie wykonanie, więc obowiązkowe
  potwierdzenie im nie przeszkadza.

### 6.4. Rozmowa w terminalu [W-02], [W-05], [W-11]

Dopytywanie i potwierdzanie w CLI mają formę **rozmowy w terminalu**.

| Polecenie | Tryb |
| --- | --- |
| `retman "…"` | **jedno polecenie**: pytania → plan → potwierdzenie → wynik, potem koniec |
| `retman` | **sesja**: wiele poleceń w jednej rozmowie (np. najpierw zlewnia, potem przepływ „dla tej zlewni”); wyjście: `koniec` albo Ctrl+D |

**Przykład** (nazwy stacji i liczby poglądowe):

```
$ retman "ściągnij opady z poznania"
Rozumiem: pobranie danych pomiarowych IMGW (opad).

? Za jaki okres pobrać dane?
  np. „2000–2020”, „ostatnie 10 lat”, „od 2015”
> od 2010 do 2020

? Nazwie „Poznań” odpowiada kilka stacji. Którą wybrać?
  1) Poznań-Ławica
  2) Poznań-Strzeszyn
> 1

Plan:
  Operacja:      Pobranie danych pomiarowych IMGW
  Rodzaj:        opad
  Krok czasowy:  dobowy   ← wartość domyślna, nie podano w poleceniu
  Stacja:        Poznań-Ławica
  Okres:         2010-01-01 – 2020-12-31
Wykonać? [t]ak / [n]ie / [z]mień
> t

Gotowe. Wynik #4: pobrano 4018 dni pomiarów. Pliki: retman-output/004_fetch_imgw_data/
```

**Zasady rozmowy:**
- **Jedno pytanie naraz**: najpierw operacja (jeśli jest niepewna), potem parametry w kolejności
  z manifestu.
- Przy wyborze z listy można podać **numer opcji albo odpowiedzieć własnymi słowami**. Słowa
  przechodzą przez ten sam mechanizm co polecenie (model decyzyjny dla wyborów, ekstraktory dla
  wartości). Jeśli odpowiedź nadal jest niejasna, Retman mówi, jak ją zrozumiał, i pyta ponownie.
- Pytanie o wartość pokazuje **przykład formatu**. Błędna odpowiedź → krótkie wyjaśnienie, co jest
  nie tak, i to samo pytanie jeszcze raz.
- Gdy parametr ma wartość domyślną, jest pokazana w nawiasie, a **Enter** ją przyjmuje.
- **`?`** przy dowolnym pytaniu pokazuje krótkie wyjaśnienie parametru (z pliku tłumaczeń).
- **`anuluj`** albo Ctrl+C przerywa bez wykonania czegokolwiek.
- Przy planie: **`t`** wykonuje, **`n`** rezygnuje, **`z`** pozwala zmienić wybraną wartość
  (lista numerowana) bez wpisywania polecenia od nowa; **`s`** — tylko gdy operacja oferuje
  sprawdzenie dostępności — uruchamia osobny krok z własną uwagą i zgodą (p. 6.5).
- Po wykonaniu CLI drukuje podsumowanie wyniku, a potem każde ostrzeżenie narzędzia w osobnej
  linii „Uwaga: …” (uwagi o jakości danych i licencyjne).
- Odpowiedzi trafiają do planu ze źródłem `user` (p. 7.1).

**Bez terminala** (skrypty, potoki, CI — wejście nie jest terminalem) Retman nie zadaje pytań
i niczego nie wykonuje, ani nie sprawdza dostępności (p. 6.5). Wypisuje, czego brakuje albo jaki
byłby plan, i kończy pracę z odpowiednim kodem wyjścia. To konsekwencja obowiązkowego
potwierdzenia (p. 6.3) i reguły „bez sieci przed potwierdzeniem” (N-12).

| Kod wyjścia | Znaczenie |
| --- | --- |
| 0 | operacja wykonana (albo pokazany plan przy `--plan-only`) |
| 2 | `validation_error`: błędna opcja lub konfiguracja, albo potrzebne odpowiedzi lub potwierdzenie, a wejście nie jest terminalem (`details.reason` `input_required`) |
| 15 | `unsupported`: polecenie spoza zakresu (W-03, `details.reason` `out_of_scope`) |
| 130 | `cancelled`: przerwane przez użytkownika (`anuluj`, `n`, Ctrl+C) |
| inne | kod rejestru Nogat błędu, który zakończył wywołanie (ERR §2): np. 5 — model nie odpowiada, 14 — źródło nie ma danych, 1 — błąd w Retmanie |

Ostatnia linia stderr przy błędzie to dokument `retman-error/1` (AGI-3.3); pełna tabela kodów
jest w USAGE p. 8. Mapowanie klas wyjątków na kody opisuje ADR-020.

**Jedna logika, wiele interfejsów.** Rozmowa w terminalu to tylko warstwa wyświetlania. Pytania
tworzy i odpowiedzi sprawdza `core/dialog.py`, dostępny też z Pythona (`plan.questions`,
`plan.answer()`, `plan.can_check`, `plan.confirm_check()`, p. 7.1). Dzięki temu te same pytania
obsłużą później serwer MCP, API HTTP i GUI (p. 7.4, 7.5).

**Zależności:** w v0.1 wyłącznie biblioteka standardowa Pythona (`input()`), bez bibliotek
do interfejsów terminalowych.

### 6.5. Sprawdzenie dostępności [W-17], [N-12]

Walidacja offline (p. 6.3) wie, czy narzędzie przyjmie żądanie, ale nie wie, **co źródło danych
faktycznie ma** dla wybranego obszaru: które lata i rozdzielczości istnieją, czy pokrycie jest
pełne, które archiwa IMGW są już opublikowane. Można się tego dowiedzieć tylko przez sieć,
a przed potwierdzeniem planu Retman jej nie używa (N-12). Dlatego sprawdzenie jest **osobnym
krokiem na życzenie**, z własną uwagą i własną zgodą — jedynym wyjątkiem od tej reguły.

Odpowiedź **`s`** w pytaniu o plan jest dostępna tylko wtedy, gdy operacja deklaruje `check`
(p. 4.3) i plan jest kompletny (przykład poglądowy; linie raportu pochodzą z `pl.toml` narzędzia):

```
Plan:
  Operacja:                 Pobranie NMT dla arkusza
  Godło arkusza NMT:        godło arkusza N-34-130-D-d-2-4
  Rozdzielczość NMT:        1 m
  Układ wysokościowy NMT:   EVRF2007
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> s
Sprawdzenie dostępności to osobny krok i jedyny, który łączy się z internetem przed wykonaniem planu.
Zapytam usługi GUGiK (skorowidz arkuszy WFS i warstwę PRG) o dane dla godła z planu.
Nie pobiera plików, niczego nie zapisuje w wynikach i nie wysyła Twojego polecenia — tylko wartości z planu.
Połączyć się z internetem i sprawdzić? [t]ak / [n]ie
> t
Sprawdzam… (Ctrl+C przerywa)
Sprawdzenie dostępności (Kartograf 0.8.0, 2026-10-19 16:12): dane dostępne
  Twój wybór: NMT, 1 m, EVRF2007 — dostępny, rok 2023, komplet arkuszy
  Dostępne także dla tego obszaru:
    NMT 0,5 m, EVRF2007 — rok 2025, komplet
    NMT 1 m, KRON86 — rok 2019, komplet
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

**Reguły bramki** (testowalne niezmienniki):

1. `Retman.check()` zgłasza `CheckNotConfirmedError`, jeśli nie było `plan.confirm_check()`. Zgoda
   jest jednorazowa (`check()` ją zużywa), nie jest częścią stanu planu (`to_dict()` jej nie
   zapisuje, a `from_dict` zawsze daje „brak zgody”) i jest cofana każdą zmianą planu.
2. `confirm_check()` nie potwierdza planu. `check()` **cofa** potwierdzenie planu, bo podsumowanie
   się zmieniło — użytkownik potwierdza dopiero po zobaczeniu raportu.
3. `confirm_check()` i `check()` wymagają kompletnego planu i zadeklarowanego `check`
   (inaczej `PlanIncompleteError`).
4. Sprawdzenie nie tworzy numeru ani folderu wyniku i niczego nie zapisuje w przestrzeni
   roboczej. Jedyne punkty wejścia zdolne do użycia sieci narzędzia to `execute()` (po `confirm()`)
   i `check()` (po `confirm_check()`) — tylko one budują pełnego klienta narzędzia (`RunClient`,
   p. 3.2.4).
5. Sprawdzenie **nigdy nie zmienia wartości planu**: informuje, a decyduje użytkownik (W-02).
   `plan.checks` opisuje zawsze dokładnie bieżący stan planu (zmiana planu je czyści), wcześniejsze
   sprawdzenia zostają w dzienniku. Po sprawdzeniu plan pokazuje wiersz „Sprawdzenie dostępności:
   <status> (<czas>)”, więc zatwierdzony plan i dziennik zapisują, że użytkownik zdecydował po
   zobaczeniu raportu. Sprawdzenie nie blokuje `t` — także przy statusie „brak danych”.
6. Awaria sprawdzenia (brak sieci, błąd usługi) to **raport ze statusem `unknown`** i powodem
   w `error`, a nie wyjątek. Przerwanie (`KeyboardInterrupt`) propaguje się, a dziennik i tak
   dostaje zdarzenie `check`.

**Statusy** (`CheckReport.status`): `available` — wybór z planu może być obsłużony tak, jak
określono; `partial` — część (brakujące lub niekompletne arkusze, pliki); `unavailable` — nic;
`unknown` — nie dało się ustalić. Linie raportu (`items` → `lines`) są w kolejności: najpierw własny
wybór z planu, potem alternatywy (np. inne lata albo rozdzielczości dla tego obszaru); tekst
każdej linii pochodzi z tabeli `[check]` w `pl.toml` narzędzia.

**Co sprawdzenie wysyła:** wyłącznie wartości z planu (obszar, produkt, lata…) do tych samych
usług danych, które zapytałoby wykonanie; nigdy treści polecenia, odpowiedzi, danych modelu ani
zawartości plików. Uwaga przed zgodą (`operations.<id>.check.notice`) mówi, które usługi zostaną
zapytane. W ustawieniach nie ma przełącznika wyłączającego sprawdzenia: każde wymaga zgody
na ekranie.

**CLI:** każda odpowiedź inna niż `t` w pytaniu o zgodę jest **odmową** (zamknięcie awaryjne):
dziennik zapisuje „pominięte”, Retman mówi „Sprawdzenie pominięte.” i wraca do pytania o plan.
Po raporcie wraca to samo pytanie o plan, a `z` działa jak zwykle — każda nowa wartość przechodzi
znów przez podgląd offline. Bez terminala i z `--plan-only` Retman nigdy nie sprawdza (kody wyjścia
bez zmian). Ctrl+C w trakcie sprawdzenia kończy rozmowę kodem 3 („Anulowano.”).

**Dziennik i wynik:** zdarzenie `check` (p. 5.4) zapisuje zgodę albo odmowę, status, błąd, narzędzie
i jego wersję, linie raportu oraz dane planu, które zostały wysłane; zapisywane jest także przy
przerwaniu. Raporty końcowego stanu planu trafiają do `result.json` (`checks`).

---

## 7. Interfejsy

### 7.1. Biblioteka Python + CLI (v0.1) [W-11]

**CLI:**

```bash
retman "Pobierz dobowe opady ze stacji Poznań z lat 2000–2020"   # one command (p. 6.4)
retman                     # session: many commands in one conversation (p. 6.4)
retman --plan-only "..."   # show the plan only, run nothing
retman --explain "..."     # show model decisions and confidences (diagnostics)
retman --config <file> ... # use another central config file (e.g. for tests)
retman doctor              # environment check (p. 7.2)
retman doctor --deep       # also the slow checks: a trial write to the IMGWTools store (p. 7.2)
retman doctor --json       # the same report as JSON, for bug reports
retman results             # list results of the current project (p. 5.2)
retman log                 # show the project journal (p. 5.4)
retman init                # create the central config file and the tool stores (p. 9.1); a wizard from v0.5
retman add-tool kartograf  # add a known tool to Retman's environment (from v0.5, p. 9.4)
```

**Python:**

```python
from retman import Retman

retman = Retman.from_config()        # central config file (p. 9.1); an explicit path is optional, e.g. in tests

plan = retman.plan("ściągnij opady z poznania")

# Answer Retman's questions one by one (the CLI does the same in the terminal, p. 6.4)
while plan.questions:
    question = plan.questions[0]
    print(question.text)                 # question in the user's language
    for number, option in enumerate(question.options, start=1):
        print(f"  {number}) {option.label}")
    plan = plan.answer(question.name, input("> "))
    # The answer is checked with the same extractors and validators as the command.
    # An invalid answer keeps the question open and explains why in question.error.
    # A complete plan has been checked offline by the tool (p. 3.2.4): if the tool
    # rejects a value, the parameters it names come back as questions with the reason.

print(plan.summary())                    # human-readable plan; defaults, workspace inputs and preview rows are marked

# Optional: ask the tool's data services what exists for this plan (a separate network step, p. 6.5)
if plan.can_check:
    print(plan.check_notice())           # what the step contacts and what it sends
    if input("Check availability? [y/n] ") == "y":
        plan.confirm_check()             # separate, single-use consent; does NOT confirm the plan
        report = retman.check(plan)      # CheckReport; raises CheckNotConfirmedError without confirm_check()
        print(report.summary())          # status and lines; the plan's values are untouched
    else:
        retman.record_check(plan, "rejected")    # journal entry; no network was used

if input("Execute? [y/n] ") == "y":
    plan.confirm()                       # explicit confirmation is mandatory (check() withdraws it)
    result = retman.execute(plan)        # raises PlanNotConfirmedError without confirm()

    if result.ok:
        print(result.summary)            # short description of the result
        print("Files:", result.files)
    else:
        print("Error:", result.error)
    for warning in result.warnings:      # tool notices (data quality, licence): always show them
        print("Warning:", warning)
```

`Retman.from_config()` bez argumentu wczytuje ustawienia (p. 9.1) — te same, z których
korzysta CLI; jawną ścieżkę (`path`), atrapę modelu (`backend`) i folder projektu (`project_dir`)
można podać opcjonalnie, np. w testach. Konstruktor `Retman(config, backend, project_dir)`
przyjmuje dodatkowo `clients={narzędzie: klient}` (wstrzyknięcie klientów narzędzi, np.
`FakeToolClient`; domyślnie klient jest budowany leniwie z manifestu, p. 3.2.4) i `today`
(data, względem której ekstraktory czytają wyrażenia względne).

| Element | Znaczenie |
| --- | --- |
| `plan.questions` | lista otwartych pytań (`Question`); pusta, gdy plan jest kompletny (i zaakceptowany przez podgląd narzędzia) |
| `Question` | `name` (parametr), `type` (`choice`, `value`, `confirm`), `text` (treść w języku użytkownika), `options` (dla wyborów), `default`, `example` (przykład formatu), `error` (dlaczego poprzednia odpowiedź była błędna albo dlaczego narzędzie odrzuciło wartość), `help` (odpowiedź na `?`) |
| `plan.answer(name, answer)` | zwraca nowy plan z odpowiedzią; numer opcji albo własne słowa |
| `plan.change(name)` | ponownie otwiera pokazaną wartość do poprawy (`z` w CLI) |
| `plan.preview_rows`, `plan.preview_values` | to, co narzędzie ustaliło offline o kompletnym planie: wiersze (pokazane w planie z oznaczeniem) i wartości (tylko do audytu, p. 5.4) |
| `plan.reopened` | parametry, które narzędzie odrzuciło po odpowiedzi użytkownika, z tekstem pokazanym przy ponownym pytaniu (p. 6.3) |
| `plan.can_check` | czy operacja oferuje sprawdzenie dostępności, a plan jest kompletny (p. 6.5) |
| `plan.check_notice()` | tekst do pokazania przed zgodą: co sprawdzenie kontaktuje i co wysyła |
| `plan.confirm_check()` | jednorazowa zgoda na jedno sprawdzenie; nie potwierdza planu |
| `retman.check(plan)` | sprawdzenie dostępności; zwraca `CheckReport`; bez zgody `CheckNotConfirmedError`; cofa potwierdzenie planu; nie tworzy wyniku |
| `retman.record_check(plan, "rejected")` | wpis w dzienniku o odmowie zgody (bez użycia sieci) |
| `plan.checks` | raporty sprawdzeń dla bieżącego stanu planu |
| `CheckReport` | `operation`, `tool`, `version`, `checked_at`, `status` (`available`, `partial`, `unavailable`, `unknown`), `header`, `items` (fakty dla maszyn), `lines` (linie pokazane użytkownikowi), `error`; `summary()`, `to_dict()` |
| `result.warnings` | przetłumaczone ostrzeżenia operacji; wywołujący musi je pokazać (p. 7.3) |
| `result.error_code` | stabilny kod błędu narzędzia, gdy operacja nie powiodła się z jego powodu |

**Plan jako dane i wartości znane z zewnątrz** (przygotowanie pod współpracę z GUI, p. 7.4):

```python
from retman import Plan

# Values already known from another source (e.g. filled in a GUI form) are treated as fixed:
# Retman does not ask about them and never overwrites them, it only fills in what is missing.
plan = retman.plan(
    "Policz przepływ dla tej zlewni, nie wiem jaką metodą",
    known={"probability": [0.01]},
)

state = plan.to_dict()          # JSON-serializable: operation, values and the source of each value
same_plan = Plan.from_dict(state, retman=retman)    # `retman=` lets the loaded plan answer questions
```

`to_dict()` zawiera wartości ze źródłami, pytania, decyzje modelu, `reopened`, wiersze i wartości
podglądu oraz raporty sprawdzeń. Zgoda na sprawdzenie nie jest częścią stanu, a `Plan.from_dict`
**zawsze zwraca plan niepotwierdzony** — także gdy zapisany stan niesie `confirmed`: potwierdzenie
trzeba dać ponownie (`plan.confirm()`), co zamyka lukę, przez którą przesłany plan mógłby wykonać
się bez człowieka [W-05].

Źródło każdej wartości w planie: `command` (z polecenia), `default` (wartość domyślna),
`workspace` (wcześniejszy wynik), `known` (podana z zewnątrz, np. w GUI), `user` (odpowiedź na pytanie Retmana).

### 7.2. `retman doctor` — sprawdzenie środowiska [W-10]

`retman doctor` w jednym miejscu pokazuje, co działa, co nie i jak to naprawić.

**Co sprawdza:**

| Obszar | Sprawdzenia |
| --- | --- |
| Konfiguracja | ścieżka i poprawność pliku ustawień `nogat.toml` (wszystkie problemy naraz; brak pliku to nie błąd, obowiązują wartości domyślne) i ustawienia modelu (ich brak blokuje planowanie); folder bieżącego projektu i czy folder wyników jest zapisywalny |
| Model decyzyjny | **adres serwera**; czy odpowiada; jaki model jest załadowany; **pytanie testowe** z oczywistą odpowiedzią (czy model odpowiada sensownie); skąd pochodzi pewność (`basal`, `logprobs`, zgodność, niedostępna) i progi (`"auto"` z backendem innym niż `basal` to błąd konfiguracji, p. 6.2) |
| Model tekstowy | czy jest włączony; **adres serwera**; czy odpowiada |
| Narzędzia | które są zainstalowane; czy ich wersje mieszczą się w obsługiwanym zakresie; liczba dostępnych operacji |
| Magazyny danych narzędzi | dla narzędzi w użyciu (zainstalowanych, w obsługiwanej wersji, niewyłączonych): ścieżka magazynu bez dowiązań symbolicznych (IMGWTools takiej nie przyjmuje: błąd; Kartograf: ostrzeżenie), folder istnieje albo da się go utworzyć i można w nim zapisywać, **dowiązania twarde działają w obu magazynach** (próba w magazynie albo w najbliższym istniejącym folderze tego samego dysku); Kartograf: cache metadanych (brak to ostrzeżenie — Kartograf działa wolniej); IMGWTools: znacznik `imgw-store.json` i jego schemat (brak magazynu to ostrzeżenie z podpowiedzią, folder obcy albo uszkodzony znacznik to błąd), `pyarrow` (szeregi czasowe), folder danych referencyjnych; z `--deep` także próbny zapis do magazynu IMGWTools |
| Zgodność opisów z narzędziami | lekka wersja `retman-scaffold --check` (p. 3.2.3) dla narzędzi w użyciu: komendy z manifestu są w katalogu zainstalowanego narzędzia, a narzędzie nie oferuje wartości, której manifest ani nie oferuje, ani nie wyłącza (np. „kartograf 0.8.1 przyjmuje rozdzielczość 0,3 m”); operacje bez wiersza w zbiorze `retman-eval` są zgłoszone jako niesprawdzone. Linie ostrzegają, ale nie blokują pracy (kod wyjścia bez zmian) |
| Tłumaczenia | komplet tekstów dla języka z ustawienia `lang` |
| Przestrzeń robocza | folder wyników bieżącego projektu; liczba wyników; czy `result.json` dają się odczytać |

**Przykładowy wynik:**

```
$ retman doctor
Retman 0.1.0

Konfiguracja
  ✓ plik ustawień: ~/.config/nogat/nogat.toml (istnieje)
  ✓ projekt: ~/projekty/zlewnia-a → wyniki w retman-output/ (5 wyników, zapis możliwy)

Model decyzyjny
  ✓ adres modelu (basal): http://127.0.0.1:8000
  ✓ model: basal-1.5-mini dostępny na serwerze
  ✓ pytanie testowe: poprawna odpowiedź (pewność 0,99 z basala)
  ! progi pewności: "auto" — zalecane dostrojenie na własnym zbiorze testowym (retman-eval, ARCHITECTURE 6.2)

Narzędzia
  ✓ imgwtools 3.0.0, obsługiwane >=3.0.0,<4, 26 operacji
  ✓ kartograf 0.8.0, obsługiwane >=0.8.0,<0.9, 4 operacje

Magazyny danych narzędzi
  ✓ kartograf: magazyn /dane/retman/stores/kartograf (zapis możliwy, dowiązania twarde działają)
  ✓ kartograf: cache metadanych /home/ola/.local/share/retman/kartograf_cache.db
  ✓ imgwtools: magazyn /dane/retman/stores/imgwtools (znacznik imgw-store.json, schemat imgw-store/1, dowiązania twarde działają)
  ✓ imgwtools: pyarrow 18.1.0 (szeregi czasowe)
  ✓ imgwtools: dane referencyjne /home/ola/.local/share/retman/imgw-reference (hydro_stations_locations.csv: brak)

Zgodność opisów z narzędziami (retman-scaffold --check)
  ✓ imgwtools 3.0.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)
  ✓ kartograf 0.8.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)

Tłumaczenia (pl)
  ✓ komplet

Model tekstowy
  – wyłączony ([retman.text] backend = "none")
```

Adres każdego modelu jest pokazany bez oceniania go — o tym, gdzie działa model, decyduje
użytkownik w ustawieniach (rozdz. 10).

Gdy serwer modelu nie działa albo magazyn nie nadaje się do zapisu, raport podpowiada, co zrobić, np.:

```
Model decyzyjny
  ✗ serwer modelu nie odpowiada (http://127.0.0.1:8000) → uruchom serwer modelu (np. LM Studio albo basal-serve, instrukcja w README) i sprawdź [retman.decision] url w ~/.config/nogat/nogat.toml albo zmienną RETMAN_DECISION_URL

Magazyny danych narzędzi
  ✗ imgwtools: system plików magazynu (/mnt/usb/imgw) nie obsługuje dowiązań twardych (Operation not permitted) → oba magazyny narzędzi wymagają dowiązań twardych (nie ma ich FAT/exFAT ani część udziałów sieciowych); wskaż magazyn na innym dysku w [retman.tools.imgwtools] store_dir (~/.config/nogat/nogat.toml)
```

Zasady:
- Każdy problem ma **podpowiedź, jak go naprawić** (polecenie, ustawienie albo odnośnik do README).
- Kod wyjścia: `0` gdy da się pracować, `1` gdy coś blokuje pracę (np. brak modelu, brak jakichkolwiek
  operacji albo magazyn, w którym narzędzie nie zapisze danych).
- `retman doctor --json` — ten sam raport w formacie do wklejenia w zgłoszeniu błędu.
- `retman doctor --deep` — dodatkowo wolniejsze sprawdzenia: próbny zapis do magazynu IMGWTools
  na wbudowanych danych testowych narzędzia, w katalogu tymczasowym i bez sieci (inicjacja
  magazynu, archiwa, szereg, katalog stacji). Pokazuje, że zainstalowana wersja narzędzia zapisuje
  magazyn na tym systemie; wymaga `pyarrow`.
- Gdy zwykłe polecenie nie może połączyć się z modelem, komunikat błędu podpowiada `retman doctor`.

### 7.3. Wynik operacji [W-09]

`execute()` zawsze zwraca obiekt `Result` o tej samej budowie, niezależnie od narzędzia:

| Pole | Zawartość |
| --- | --- |
| `ok` | `True`, jeśli operacja się powiodła |
| `number` | numer wyniku w projekcie (#1, #2, …; p. 5.2) |
| `operation` | identyfikator wykonanej operacji |
| `params` | parametry faktycznie użyte (z oznaczeniem, które były domyślne) |
| `inputs` | źródła wejść (plik, wcześniejszy wynik) |
| `outputs` | rodzaje zwróconych danych (`kind`) — podstawa przestrzeni roboczej |
| `values` | wyniki liczbowe lub krótkie (np. `{"file_count": 12}`) |
| `files` | ścieżki do zapisanych plików, według rodzaju danych: w folderze wyniku albo w magazynie narzędzia (p. 3.2.4) |
| `warnings` | przetłumaczone ostrzeżenia: wynik częściowy, uwagi narzędzia o jakości danych i licencji (dosłownie; uwagi czysto informacyjne zostają w śladzie audytowym). Wywołujący musi je pokazać — CLI drukuje je po podsumowaniu |
| `error` | opis błędu, gdy `ok = False`; dla błędu narzędzia — tekst Retmana wybrany po stabilnym kodzie błędu, a tekst narzędzia tylko jako cytat |
| `error_code` | stabilny kod błędu narzędzia (np. `no_coverage`), gdy operacja nie powiodła się z jego powodu; inaczej `None` |
| `tool` | blok audytowy wywołań katalogu narzędzia (p. 5.4); `None` dla operacji bez takich wywołań |
| `summary` | krótki opis w języku użytkownika (szablon operacji, ogólny szablon albo `TextBackend`) |

Pliki trafiają do folderu wyników bieżącego projektu, w podkatalogu z numerem wyniku i nazwą
operacji, np. `retman-output/004_export_station_series/`, razem z plikiem `result.json`, który
zawiera też dane audytowe (p. 5.4). Wyjątek: pliki, które narzędzie trzyma w swoim magazynie
(Kartograf), zostają w magazynie — wynik wskazuje je ścieżką bezwzględną i sumą SHA-256, a podkatalog
wyniku zawiera `result.json` i dokumenty narzędzia (`tool_<n>_<komenda>.json`); podsumowanie
mówi wtedy, gdzie leżą pliki.

### 7.4. Integracja z GUI narzędzi (v0.5+) [W-13]

Scenariusze użytkownika opisuje PRD. Tu: jak je zrealizować technicznie.

**Model:** plan Retmana to **stan formularza** — operacja, wartości parametrów i źródło każdej
z nich. Potwierdzenie planu odpowiada przyciskowi „Uruchom” w GUI. Scenariusz „część wypełniam
w GUI, resztę ustalam z Retmanem” to plan z częścią wartości ze źródła `known`.

**Co v0.1 zapewnia już teraz** (mały koszt, otwarta droga na później):
- plan serializowany do JSON (`to_dict()` / `from_dict()`), ze źródłem każdej wartości (p. 7.1);
  odczytany plan jest zawsze niepotwierdzony,
- wartości znane z zewnątrz (`known`): Retman ich nie zmienia, uzupełnia tylko brakujące,
- rozdzielenie planowania od wykonania (p. 6.3),
- sprawdzenie dostępności jako osobny krok z własną zgodą (`plan.can_check`, `plan.confirm_check()`,
  `retman.check()`, p. 6.5) — w GUI to osobny przycisk „Sprawdź dostępność”,
- wyniki jako pliki z `result.json` (p. 7.3), które GUI może wczytać.

**Dobra praktyka po stronie GUI:** formularze oparte na tych samych funkcjach publicznego API,
z których korzystają handlery Retmana. Wtedy nazwy pól i parametrów są wspólne, a przekazanie
planu do formularza jest proste.

**Warianty połączenia** (do decyzji, gdy GUI powstaną):

| Wariant | Jak działa | Niezależność narzędzia |
| --- | --- | --- |
| A. Wymiana plików | Retman zapisuje plan do pliku JSON; GUI umie wczytać parametry z pliku i obserwuje katalog wyników | pełna — GUI nie wie o Retmanie |
| B. Opcjonalny panel czatu | GUI, gdy wykryje działający serwer Retmana (API HTTP), pokazuje panel czatu i wymienia z nim plany | GUI działa w pełni bez Retmana; integracja to opcjonalny dodatek |

Wygodna realizacja scenariuszy z PRD wymaga wariantu B. To jedyne miejsce, w którym zasada
„narzędzia nic nie wiedzą o Retmanie” zostaje złagodzona — i tylko jako opcjonalny dodatek.

**Kto uruchamia analizę w scenariuszach z GUI:** rekomendacja — GUI (jego przycisk „Uruchom”),
a Retman tylko planuje. Wtedy jest jedna ścieżka wykonania i wyniki pokazują się w GUI
w naturalny sposób. Samodzielny Retman (CLI, API Pythona) nadal wykonuje operacje sam.

### 7.5. Pozostałe interfejsy (później)

| Interfejs | Wersja | Uwagi |
| --- | --- | --- |
| Serwer MCP | v0.3 | opcjonalny dodatek `retman[mcp]` (stdio): plany Retmana z potwierdzeniem człowieka w kliencie i śladem audytowym (p. 7.5.1, ADR-018) |
| API HTTP | v0.4 | dostęp do Retmana dla aplikacji webowej i integracji z GUI (model na serwerze jednostki działa bez tego od v0.1, p. 3.3.4) |
| Czat w przeglądarce | v0.5+ | dla użytkowników końcowych |

#### 7.5.1. Serwer MCP (v0.3) [W-16]

Projekt zapisany w ADR-018; w v0.1 i v0.2 nie ma kodu, zależności ani konfiguracji MCP. Retman
rozmawia z narzędziami przez ich API Pythona (p. 3.2.1), a sam staje się serwerem MCP dla
zewnętrznych asystentów AI. Daje im to, czego serwery MCP narzędzi nie mają: plan pokazany ze
źródłem każdej wartości, potwierdzenie człowieka, ślad audytowy i numerowaną przestrzeń roboczą.

- **Pakiet:** moduł `src/retman/mcp_server.py` (SDK importowany leniwie), opcjonalny dodatek
  `retman[mcp]` (`mcp>=2.3,<3`), nigdy w zależnościach podstawowych (p. 9.3). Uruchomienie:
  `retman mcp --project <katalog>` (stdio; `--project` jest obowiązkowe, bez domyślnego bieżącego
  katalogu). Streamable HTTP dopiero z API HTTP (v0.4).
- **Stan po stronie serwera:** plany w pamięci (`plan_id` → `Plan`, z limitem czasu życia i liczby).
  Serwer **nigdy nie wczytuje planu przysłanego przez klienta**; `Plan.from_dict` i tak nie przywraca
  potwierdzenia (p. 7.1).

| Narzędzie MCP | Zachowanie |
| --- | --- |
| `retman_operations` | lista operacji zainstalowanych narzędzi (id, polska etykieta, parametry, rodzaje danych); tylko do odczytu |
| `retman_plan(command, known?)` | `Retman.plan`; zwraca plan i jego podsumowanie; wartości przekazane przez agenta w `known` są w planie oznaczone tym źródłem |
| `retman_answer(plan_id, name, answer)` | `plan.answer`; zwraca nowy plan z otwartymi pytaniami |
| `retman_check(plan_id)` | sprawdzenie dostępności (p. 6.5) z własnym elicitation i własną zgodą człowieka; zgoda nigdy nie pochodzi od agenta |
| `retman_execute(plan_id)` | **jedyna** ścieżka wykonania |

`retman_execute` zachowuje niezmiennik W-05: plan musi istnieć i nie mieć otwartych pytań; serwer
pyta **człowieka** przez MCP elicitation, pokazując pełne podsumowanie planu (`plan.summary()`
z oznaczonymi wartościami domyślnymi, z przestrzeni roboczej i `known`) i pole logiczne
`confirm`; dopiero przy zgodzie dla tego planu woła `plan.confirm()`, a potem `execute()`.
Odmowa albo anulowanie kończy się wpisem „plan odrzucony” w dzienniku. **Zamknięcie awaryjne:**
klient, który nie deklaruje elicitation (albo odpowiada inaczej), nie wykona niczego — dostaje
błąd `confirmation_unavailable` z podsumowaniem planu i instrukcją uruchomienia w terminalu;
`retman_plan` i `retman_answer` nadal działają. Agent nie ma argumentu `confirm` ani przełącznika
w konfiguracji.

Pytania Retmana (W-02) wracają do agenta jako dane, ale każda wartość dostarczona przez agenta jest
w planie oznaczona (źródło `known` albo `user` z `channel: "mcp"`), więc trafia do planu, który
przegląda człowiek: bramka człowieka jest na planie końcowym, nie na każdym pytaniu (do
rozstrzygnięcia na starcie v0.3: rozdz. 12, pkt 16).

**Ślad audytowy** (addytywnie): `result.json` i dziennik dostają `channel` (`cli`, `python`, `mcp`),
a dla `mcp` także `client` (nazwa i wersja z `initialize`), `confirmation` (metoda i czas)
oraz `command.origin = "agent"` (tekst polecenia to parafraza agenta, nie słowa użytkownika).

**Prywatność** (N-04): klient-agent jest usługą spoza ustawień Retmana, zwykle modelem w chmurze.
Tabela `[retman.mcp]` pojawi się w szablonie ustawień dopiero w v0.3: `transport = "stdio"`,
`confirmation = "elicitation"`, `plan_ttl_seconds`, `max_open_plans` i `expose_command_text = false`
(treść poleceń jest ukryta przed agentem nawet przy `journal_commands = true`). Zasoby
`retman://results` zwracają `result.json` bez `command` i bez ścieżek bezwzględnych;
`retman doctor` dostaje linię „MCP”. Audyt obejmuje tylko operacje wykonane przez Retmana — kto
uruchamia serwery MCP narzędzi bezpośrednio, omija ślad.

**Testy** (offline, pamięciowy transport SDK z `FakeDecisionBackend`): `retman_execute` bez zgody
w elicitation nie ma skutku; klient bez elicitation dostaje `confirmation_unavailable`, nic nie jest
wykonane ani zapisane; słownik planu z `confirmed = true` nie jest honorowany; zasób nie ujawnia
treści poleceń ani ścieżek bezwzględnych; dziennik zapisuje `channel = "mcp"` oraz odmowy.

---

## 8. Testy i ocena jakości

Docelowe wartości miar jakości ustala PRD. Tu: jak je mierzyć.

### 8.1. Zbiór poleceń testowych

Plik `src/retman/eval/commands.jsonl` (dane pakietu, instalowane razem z Retmanem), jedna linia =
jedno polecenie z oczekiwanym wynikiem.
Polecenia są po polsku (to dane wejściowe), identyfikatory po angielsku:

```json
{"command": "Pobierz dobowe opady ze stacji Poznań z lat 2000–2020", "operation": "fetch_imgw_data", "params": {"variable": "precipitation", "interval": "daily", "station": "Poznań", "period": ["2000-01-01", "2020-12-31"]}}
{"command": "ściągnij opady z poznania", "operation": "fetch_imgw_data", "params": {"variable": "precipitation", "station": "Poznań"}, "expect_clarify": ["period"]}
{"command": "Wyznacz zlewnię dla punktu 52.41, 16.93", "operation": "delineate_catchment", "params": {"point": [52.41, 16.93]}}
{"command": "Policz Q1% i Q10% Punzetem dla tej zlewni", "operation": "peak_flow", "params": {"method": "punzet", "probability": [0.01, 0.10]}}
{"command": "Ile wynosi Q50 dla tej zlewni?", "operation": "peak_flow", "expect_clarify": ["probability"]}
{"command": "Jaka będzie jutro pogoda?", "operation": "out_of_scope"}
```

Zasady budowy zbioru:
- minimum 15 różnie sformułowanych poleceń na operację (formalnie, potocznie, z błędami, skrótami),
- polecenia celowo niepełne i niejednoznaczne (sprawdzają dopytywanie),
- polecenia spoza zakresu (oczekiwana operacja `out_of_scope`),
- po udostępnieniu narzędzia: uzupełnianie zbioru o prawdziwe polecenia użytkowników,
  zebrane za ich zgodą (rozdz. 10).

### 8.2. Miary jakości

| Miara | Znaczenie |
| --- | --- |
| Trafność operacji | % poprawnie rozpoznanych operacji |
| Trafność parametrów | % poprawnych wartości parametrów |
| Pokrycie automatyczne | % poleceń obsłużonych bez dopytywania |
| Błąd przy pewności | % błędnych decyzji wśród tych powyżej progu; cel wstępny ≤ 1% (PRD W-02) |
| Trafne dopytania | % przypadków, w których Retman dopytał o to, czego faktycznie brakowało |

Przy rozpoznawaniu dwustopniowym (p. 3.4) `retman-eval` zapisuje w rekordzie także pytanie
o kategorię (`category_question`: czy padło i co zaproponowano), odpowiada na nie kategorią
oczekiwanej operacji i liczy je jako dopytanie użytkownika. Osobnej miary trafności kategorii
nie ma — o poprawności decyduje operacja końcowa.

Polecenie `retman-eval --backend basal` uruchamia zbiór i drukuje raport. Ten sam zbiór służy
do porównywania backendów (basal-1.5-mini vs basal-1.5 vs model generatywny).

`retman-eval` jest częścią **pakietu podstawowego** (p. 9.3), bez dodatkowych zależności. Każdy
użytkownik i wdrażający może nim dostroić progi pewności dla własnego modelu, co jest
obowiązkowe dla backendów innych niż basal (p. 6.2).

### 8.3. Testy jednostkowe i integracyjne

- Ekstraktory testowane bez modelu (czysty kod, `pytest`), w tym wszystkie formy z p. 4.4;
  ekstraktory kontekstowe (stacje, zmienne) na sztucznym katalogu i atrapie wyszukiwania offline.
- Pipeline testowany z **atrapą backendu** (`FakeDecisionBackend`) — testy nie wymagają GPU.
- Wspólny adapter testowany na narzędziu-atrapie (`tests/fixtures/dummy_tool`: manifest, buildery
  wywołań, handlery, podgląd, sprawdzenie i klient) z atrapą klienta `FakeToolClient`
  (`src/retman/testing.py`). Atrapa zapisuje każde wywołanie (`calls`, `network_calls`), więc test
  bramki [N-12] sprawdza, że przed `plan.confirm()` nie było żadnego wywołania `run`, `check`
  ani `query`, a przed `plan.confirm_check()` — żadnego wywołania `check` ani `query` (p. 6.5).
- Opisy narzędzi: walidacja manifestów i tłumaczeń (także tekstów kategorii i komunikatów
  kodów błędów narzędzia), buildery wywołań i mappery wyników na nagranych prawdziwych
  dokumentach narzędzi (`tests/fixtures/<narzędzie>/`), zgodność z katalogiem zainstalowanego
  narzędzia przez wykonanie (`retman-scaffold --check`, p. 3.2.3) i testy na prawdziwych
  narzędziach z małymi danymi, a dla IMGWTools na pakietowym magazynie fikcyjnym
  (`imgwtools.testing.build_fixture_store`), offline (p. 3.2.7–3.2.8).
- Przestrzeń robocza: zapis i odczyt `result.json`, numeracja wyników, reguły wyboru wejścia
  z p. 5.3 (w tym pytanie przy kilku kandydatach).
- Dziennik projektu: wpis dla każdego kroku, także dla odrzuconych planów, anulowania i błędów,
  oraz dla sprawdzeń dostępności (wykonanych, odrzuconych i przerwanych); komplet danych
  audytowych w `result.json` (p. 5.4).
- Sprawdzenie dostępności i podgląd: zgoda jednorazowa, cofana zmianą planu, niezapisywana
  w planie; ponowne otwarcie parametrów po odrzuceniu przez narzędzie (p. 6.5, 6.3).

---

## 9. Konfiguracja i wymagania techniczne

### 9.1. Ustawienia: tabele `[retman]` pliku `nogat.toml` [N-11, ADR-021]

Ustawienia **niezależne od projektu** — m.in. modele, progi pewności, język, prywatność
i magazyny danych narzędzi — czyta Retman z **jednego pliku na komputerze, wspólnego dla narzędzi
Nogat** (DEV-18.1): `nogat.toml` w folderze ustawień użytkownika (`platformdirs.user_config_path("nogat")`),
z pliku wskazanego przez `NOGAT_CONFIG` albo przez opcję `--config PATH`. Plik czyta się
`tomllib`; Retman nie wymaga ani pakietu `nogat`, ani pliku `.env`. Tabela `[nogat]` ma klucze wspólne
(`lang`, `log_level`, `data_dir`, `cache_dir`), tabela `[retman]` i jej podtabele — ustawienia Retmana.

**Kolejność źródeł** każdego ustawienia: opcja polecenia (na razie żadne ustawienie jej nie ma;
`--config` wskazuje plik), zmienna `RETMAN_<KLUCZ>`, zmienna `NOGAT_<KLUCZ>` (tylko klucze wspólne),
tabela `[retman]`, tabela `[nogat]` (tylko klucze wspólne), wartość domyślna. `<KLUCZ>` to klucz
z kropkami zamienionymi na `_` wielkimi literami (`decision.url` — `RETMAN_DECISION_URL`); pusta
zmienna znaczy „nie ustawiono”. Moduł `retman.environment` znajduje wartość (tabela kluczy `KEYS`,
`Environment.setting`), moduł `retman.config` sprawdza ją i buduje `Settings` (bez serwera modelu)
i `Config` (z nim). Wartość nieużyteczna jest odrzucana z opisem, a `load_settings` i `load_config`
zgłaszają wszystkie takie problemy naraz jako `ConfigError` (`validation_error`, powód `invalid_config`);
plik nieczytelny, z błędem TOML albo wskazany, a nieistniejący, kończy każde polecenie tym samym błędem.

- **Brak ukrytych wartości domyślnych** [N-11]: `retman config show` (`retman-config/1`, DEV-18.6)
  pokazuje każde ustawienie z wartością i źródłem (`default`, `env`, `file`), plik (także nieużyteczny),
  zmienną z kluczem dostawcy modelu (`present` albo `missing`), magazyny narzędzi z rozmiarem
  (dowiązanie twarde liczone raz); `retman init` zapisuje wszystkie tabele z widocznymi wartościami.
  Tabelę `[retman]` dopisuje na końcu istniejącego pliku, nie ruszając innych tabel; istniejąca tabela
  `[retman]` to `conflict` (powód `output_exists`).
- **Serwer modelu nie ma wartości domyślnych**: `[retman.decision]` (adres, model, progi) nie ma sensownej
  wartości domyślnej, więc `load_config` zgłasza brakujące klucze (`missing_key`), a polecenia bez modelu
  (`retman results`, `retman log`, `retman config show`, `retman init`, `retman doctor`) działają z samych
  wartości domyślnych (`load_settings`). Klucz API nie jest ustawieniem: czyta go się ze zmiennej, którą
  nazywa `decision.api_key_env` (rozdz. 10, DEV-18.4).
- **Rzeczy zależne od projektu nie są w ustawieniach.** Wyniki i dziennik trafiają do folderu projektu
  (rozdz. 5, odstępstwo od DEV-18.2: w ustawieniach jest tylko nazwa podfolderu wyników `output.results_dir`).
- **Magazyny narzędzi** [ADR-015, ADR-021]: Kartograf i IMGWTools trzymają pobrane dane w magazynie
  poza folderami wyników, wspólnym dla wszystkich projektów. Argumenty środowiskowe narzędzi
  (magazyn, liczba wątków, cache, tryb aktualizacji) klient bierze wyłącznie z tabel
  `[retman.tools.<narzędzie>]` (p. 3.2.4); mają wartości domyślne: magazyn Kartografa
  `<data_dir>/kartograf`, magazyn IMGWTools `<data_dir>/imgw`, cache Kartografa
  `<cache_dir>/kartograf/metadata.db`, dane referencyjne IMGWTools `<cache_dir>/imgw/reference`,
  zbiór poleceń `<data_dir>/retman/collected.jsonl`. `data_dir` i `cache_dir` to foldery danych
  i cache użytkownika nogat (`platformdirs.user_data_path("nogat")`, `user_cache_path("nogat")`;
  w Linuksie `~/.local/share/nogat` i `~/.cache/nogat`). Ścieżki są bezwzględne, bez `..`; magazyny
  Kartografa i IMGWTools to dwa osobne foldery obok siebie na jednym dysku, a żaden nie zawiera
  drugiego (cache Kartografa i dane referencyjne IMGWTools też nie leżą w magazynie). Dysk musi
  mieć dowiązania twarde (nie mają ich FAT/exFAT ani część udziałów sieciowych); cache metadanych
  Kartografa musi leżeć na dysku lokalnym. `update` Kartografa: `local` — użyj zapisanych wersji
  i nie pytaj źródeł o nowsze, `upgrade` — pobierz także nowsze, `force` — pobierz ponownie.
  W terminalu `retman init` pyta o zbieranie poleceń (p. 5.4) i o folder na magazyny narzędzi
  (domyślnie `data_dir`), tworzy foldery (magazyn Kartografa, folder cache i danych referencyjnych),
  sprawdza, że dysk ma dowiązania twarde, i dopiero potem zapisuje tabele; na końcu, za zgodą, inicjuje
  magazyn IMGWTools (`store init`, bez sieci). Bez terminala zapisuje tabele z widocznymi ścieżkami
  domyślnymi i niczego nie tworzy. Dysk bez dowiązań twardych kończy `retman init` błędem przed zapisem
  (kod wyjścia 8 albo 9), a odmowa `store init` przez IMGWTools z tego powodu zostawia plik i podpowiada
  zmianę obu `store_dir`. Od wersji łatwej (0.5+) `retman init` działa jako kreator: pyta też, gdzie
  działa model, sprawdza połączenie i zapisuje plik (p. 9.4).
- **Język** (`lang`, `pl` albo `en`): teksty Retmana istnieją tylko po polsku, więc `en` jest przyjmowany
  i pokazywany przez `retman config show`, a komunikaty zostają polskie, aż powstaną teksty angielskie
  (odstępstwo od DEV-2.2 w `CLAUDE.md`). Dane maszynowe są zawsze po angielsku.
- W pliku nie ma opisów narzędzi (manifestów) ani tekstów (tłumaczeń) — to część kodu Retmana,
  testowana w CI (p. 3.2, 4.2). Nie ma w nim też kluczy API, tylko nazwy zmiennych
  środowiskowych (rozdz. 10). Sekcja `[retman.mcp]` pojawi się dopiero w v0.3 (bez nieużywanych kluczy).

Wszystkie zmienne wymienia README i `.env.example`; szablon tabel (`src/retman/config_template.toml`):

```toml
[retman]
# lang = "pl"            # language of questions, options and messages: "pl" | "en"
# log_level = "warning"  # technical log on stderr: "debug" | "info" | "warning" | "error"
# data_dir = "..."       # parent of the data stores and of the command collection
# cache_dir = "..."      # parent of the caches

[retman.decision]
backend = "basal"                   # "basal" (default) | "openai_compatible"
url = "http://127.0.0.1:8000"       # basal-serve running locally (started separately)
model = "basal-1.5-mini"
timeout_s = 30                      # how long to wait for the model server
# Generative model instead of basal, e.g. LM Studio:
# backend = "openai_compatible"
# url = "http://127.0.0.1:1234/v1"
# model = "<model-name>"
# api_key_env = "PROVIDER_API_KEY"  # external providers: NAME of the environment variable holding the key
# confidence = "auto"               # "auto" | "logprobs" | "consistency" | "none" (ARCHITECTURE 3.3.3)
# consistency_runs = 3              # queries per decision for the consistency check
# With this backend [retman.decision.thresholds] must be numbers tuned for the model
# (ARCHITECTURE 6.2); with confidence = "none" the thresholds are ignored.

[retman.decision.thresholds]
operation = "auto"      # "auto" = basal calibration, allowed only with backend = "basal"; after tuning set a number, e.g. 0.90
parameter = "auto"

[retman.text]
backend = "none"        # from v0.2: "openai_compatible" (e.g. Bielik in LM Studio)

[retman.output]
results_dir = "retman-output"  # results folder created inside the project folder, i.e. where Retman runs

[retman.adapters]
# By default Retman enables every supported tool that is installed in a supported version.
# The optional "enabled" list only NARROWS that set.
# enabled = ["kartograf"]

[retman.tools.kartograf]
# The store: every downloaded file is kept here as an immutable version and shared by all
# projects. Absolute path without symbolic links, on a disk with hard links (not FAT/exFAT).
# Keep it on the same disk as the IMGWTools store, in a separate folder.
store_dir = '/home/<user>/.local/share/nogat/kartograf'
# Metadata cache (SQLite). Keep it on a LOCAL disk, never on a network share.
cache_file = '/home/<user>/.cache/nogat/kartograf/metadata.db'
workers = 4         # parallel transfers
update = "local"    # "local" = use stored versions, ask no source | "upgrade" = also download newer versions | "force" = download again

[retman.tools.imgwtools]
# The IMGWTools store (archives, series, station catalog): a separate folder next to the
# Kartograf store; neither store may contain the other. Absolute path without symbolic links.
store_dir = '/home/<user>/.local/share/nogat/imgw'
# Optional reference files for the station catalog (hydro_stations_locations.csv); may stay empty.
reference_data_dir = '/home/<user>/.cache/nogat/imgw/reference'

[retman.log]
journal_commands = true    # store command texts and answers in the project journal

[retman.privacy]
# Collect planning outcomes (command, plan, answers, model decisions) from ALL projects
# in one file, to build and tune the test set (ARCHITECTURE 5.4, rozdz. 10). Separate from
# the project journal; stays on this computer, nothing is sent anywhere. retman init asks.
collect_commands = false
collect_path = '/home/<user>/.local/share/nogat/retman/collected.jsonl'
```

### 9.2. Systemy i sprzęt [N-06], [N-09]

Systemy docelowe: **Windows, Linux i macOS**. CI Retmana uruchamia testy na wszystkich trzech.

**Sam Retman** nie ma wymagań sprzętowych poza Pythonem ≥ 3.12. Wymagania dotyczą
**serwera modelu** i zależą od wybranej konfiguracji (p. 3.3.4). Orientacyjnie:

| Model | Gdzie | Uwagi |
| --- | --- | --- |
| basal-1.5-mini (1.5B) | GPU 6–8 GB, Apple Silicon, ewentualnie CPU | ~3 GB pamięci |
| basal-1.5 (4.5B) | GPU 8–12 GB, Apple Silicon 16 GB+ | lepsza trafność |
| basal-1.5-max (11B) | serwer | najwyższa trafność |
| model generatywny w LM Studio / Ollama | zależnie od rozmiaru i kwantyzacji | np. Bielik do decyzji lub opisów |
| model dostawcy przez API | brak wymagań lokalnych | wymaga klucza API |

**Zalecany sprzęt do pracy lokalnej** (PRD N-06): karta NVIDIA z ok. 6–8 GB pamięci albo Apple
Silicon z ok. 16 GB pamięci — z zapasem na model tekstowy od v0.2.

**Pomiary czasu odpowiedzi (v0.1):** czas od polecenia do planu dla konfiguracji z p. 3.3.4
na sprzęcie autora (macOS, Linux) i — jeśli możliwe — na laptopie bez GPU. Wyniki trafiają
do dokumentacji jako wskazówka doboru modelu (PRD, N-07).

### 9.3. Pakiet [N-08]

- Python ≥ 3.12 (ADR-002: tyle wymaga Kartograf, a narzędzia działają w środowisku Retmana),
  `pyproject.toml` zgodny z PEP 639, licencja MIT.
- Kod, identyfikatory, komentarze i docstringi po angielsku; teksty dla użytkownika w plikach
  tłumaczeń; README i dokumentacja po polsku (p. 1.3).
- Zależności podstawowe: minimalne — klient HTTP. Plik centralny odczytuje `tomllib`
  z biblioteki standardowej; `retman init` zapisuje go z szablonu z komentarzami (p. 9.1),
  więc biblioteka do zapisu TOML nie jest potrzebna. **Pakiet nie zawiera modelu
  ani bibliotek uczenia maszynowego** (np. PyTorcha) ani SDK dostawców. Narzędzia hydrologiczne
  **nie są** zależnościami podstawowymi. Biblioteka protokołu MCP (`mcp`) też nie jest zależnością
  podstawową — nie jest SDK dostawcy modelu ani biblioteką ML, ale łamałaby regułę „tylko klient
  HTTP” — i wolno ją dodać wyłącznie jako opcjonalny dodatek `retman[mcp]` dla interfejsu
  z v0.3 (ADR-018). W v0.1 Retman nie ma kodu, zależności ani konfiguracji MCP.
- **basal (basal-serve) nie jest zależnością Retmana** — ani podstawową, ani opcjonalną.
  Backend `basal` to własne zapytanie HTTP, bez klienta z pakietu `basal` (p. 3.3.2).
- **Dystrybucja przez GitHub, bez PyPI.** Retman instaluje się z repozytorium, np.
  `uv tool install git+https://github.com/Daldek/Retman` (szczegóły: p. 9.4).
- Opisy narzędzi są wbudowane w Retmana (`src/retman/tools/`). **Retman nie instaluje niczego sam
  z siebie.** Narzędzia instaluje użytkownik razem z Retmanem, w tym samym środowisku (p. 9.4),
  a od wersji łatwej także na wyraźne polecenie `retman add-tool` (z potwierdzeniem). Retman
  sprawdza ich wersje, a `retman doctor` podpowiada, jak doinstalować brakujące. Narzędzia są
  importowane leniwie (`importlib`, p. 3.2.5), więc ani start Retmana, ani `mypy retman/ tests/`
  nie zależą od tego, co jest zainstalowane.
- Grupa zależności `tools` w `pyproject.toml` służy testom i ręcznym uruchomieniom; nie jest
  zależnością środowiska użytkownika. Do czasu tagów `v0.8.0` (Kartograf) i `v3.0.0` (IMGWTools)
  przypina wypchnięte commity: Kartografa `8e9bcbb0` (`origin/develop`) i IMGWTools z dodatkiem
  `store` (`0d98f3b`, `origin/slave`); po wydaniu przechodzi na tagi (ADR-012). Dodatek `store`
  IMGWTools instaluje `pyarrow` (szeregi czasowe to pliki Parquet).
- Retman **nie ma dodatków instalujących narzędzia** (`retman[hydrograf]` itp.). Zależności
  wskazujące bezpośrednio na repozytoria Git wymuszałyby sztywne wersje zamiast zakresów
  i zablokowałyby ewentualną późniejszą publikację na PyPI.
- `retman-eval` i `retman-scaffold` należą do pakietu podstawowego (skrypty, bez dodatkowych
  zależności): `retman-eval` razem ze zbiorem poleceń testowych (p. 8.2), `retman-scaffold`
  (p. 3.2.3) jako narzędzie autora, które czyta katalogi zainstalowanych narzędzi. Dodatek
  `retman[dev]` ma tylko narzędzia pracy nad kodem (pytest, ruff, mypy).

### 9.4. Instalacja [N-09], [W-14]

**Podstawa: `uv`** — jeden program dla Windows, Linuxa i macOS, który sam instaluje Pythona
i tworzy osobne środowisko dla Retmana. Użytkownik nie musi mieć wcześniej zainstalowanego
Pythona. Obie ścieżki (trudna i łatwa) wykonują **te same kroki**; łatwa tylko je automatyzuje,
więc utrzymywany jest jeden mechanizm instalacji.

**Trzy warstwy:**

| Warstwa | Co | Skąd | Kto instaluje |
| --- | --- | --- | --- |
| 1 | Python + Retman | GitHub (wydania oznaczone tagami) | `uv` |
| 2 | narzędzia | GitHub (jedno także PyPI) | `uv`, w **tym samym środowisku** co Retman |
| 3 | serwer modelu: basal-serve (domyślnie) albo serwer z API zgodnym z OpenAI, np. LM Studio (p. 3.3.2); od 0.2 także serwer modelu tekstowego, np. Bielik w LM Studio | według ich własnych instrukcji | osobno (PRD N-10); przy serwerze jednostki — wdrażający |

**Narzędzia muszą być w środowisku Retmana**, bo handlery je importują. Narzędzie zainstalowane
w innym środowisku jest dla Retmana niewidoczne — `retman doctor` zgłasza je jako niezainstalowane
i podaje polecenie, które je doda.

#### Wersja trudna (0.x — autor i testerzy)

```bash
# 1. Install uv (once). Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh
#    Windows (PowerShell):
#    irm https://astral.sh/uv/install.ps1 | iex

# 2. Retman together with the tools you need, in ONE environment
#    (@v0.1.0 = a tagged release, so testers have a stable version).
#    imgwtools[store] brings pyarrow: its time series are Parquet files
uv tool install "git+https://github.com/Daldek/Retman@v0.1.0" \
    --with "kartograf @ git+https://github.com/Daldek/Kartograf@v0.8.0" \
    --with "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@v3.0.0"

# 3. Model server: installed separately, following basal's instructions, then started
basal-serve --model Remek/basal-1.5-mini --mode <depends on hardware>

# 4. Central config (asks where to keep the tool stores) and environment check
retman init
retman doctor
```

- **Dodanie narzędzia później:** to samo polecenie z dodatkowym `--with`.
- **Aktualizacja:** to samo polecenie z nowym tagiem wydania. Do czasu wypchnięcia tagów
  `v0.8.0` i `v3.0.0` zamiast tagu podaje się commit z grupy `tools` w `pyproject.toml` (p. 9.3).
- **Magazyny narzędzi** powstają przy `retman init` (p. 9.1); `retman doctor` sprawdza ich
  ścieżki, prawa zapisu, dowiązania twarde, `pyarrow` i dane referencyjne, a z `--deep` także
  próbny zapis do magazynu IMGWTools (p. 7.2).
- **basal-serve** trzeba uruchomić przed pracą z Retmanem; jeśli nie działa, `retman doctor`
  i komunikat błędu podpowiadają, jak go uruchomić (p. 7.2).

#### Wersja łatwa (0.5+, przed 1.0)

1. **Skrypt instalacyjny** — `install.sh` (Linux, macOS) i `install.ps1` (Windows) w repozytorium
   Retmana. Instaluje `uv`, Retmana i narzędzia wybrane z listy, czyli wykonuje kroki 1–2
   wersji trudnej.
2. **Kreator `retman init`** — pyta, gdzie działa model (na tym komputerze / na serwerze jednostki
   pod podanym adresem / u dostawcy), od razu sprawdza połączenie i zapisuje ustawienia (p. 9.1).
3. **`retman add-tool <narzędzie>`** — doinstalowuje znane Retmanowi narzędzie do jego środowiska,
   w wersji z obsługiwanego zakresu, przez `uv`. Jak każda operacja wymaga potwierdzenia:

   ```
   $ retman add-tool kartograf
   Doinstaluję Kartograf 0.8.0 (obsługiwane wersje: >=0.8.0,<0.9) z GitHuba do środowiska Retmana.
   Wykonać? [t]ak / [n]ie
   ```

   Działa tylko dla narzędzi, które Retman zna (ma ich opisy w `src/retman/tools/`).
4. **Model** — przy serwerze jednostki użytkownik niczego nie instaluje, tylko wpisuje adres
   w kreatorze. Lokalnie dostaje instrukcję (albo osobny skrypt) dla basal-serve; Retman nie zawiera
   modelu (PRD N-10).

#### Sprawdzanie w CI

- **Test instalacji na czystych systemach** (Windows, Linux, macOS): instalacja Retmana ze wszystkimi
  narzędziami, a potem `retman doctor --deep` (z próbnym zapisem do magazynu IMGWTools na każdym
  systemie). Zależności narzędzi (np. biblioteki geoprzestrzenne) uznano za niekłopotliwe — test
  potwierdza to na każdym systemie, zanim problem trafi do testerów.
- Od wersji łatwej ten sam test obejmuje skrypty instalacyjne.

---

## 10. Bezpieczeństwo i prywatność [N-04], [W-05]

- Każde wykonanie operacji wymaga potwierdzenia planu (p. 6.3), bez wyjątków w wersjach 0.x.
  Potwierdzenia nie da się wczytać z danych: `Plan.from_dict` zawsze zwraca plan niepotwierdzony
  (p. 7.1), więc zapisany albo przesłany plan nigdy nie wykona się bez nowego potwierdzenia.
- **Bez sieci przed potwierdzeniem** [N-12]: z klienta narzędzia kod planowania (buildery
  wywołań, podgląd, ekstraktory kontekstowe) widzi tylko połowę offline (`PlanView`: walidacja,
  linia komendy, wyszukiwanie w katalogu bez skutków; p. 3.2.4). Funkcje z efektem sieciowym lub
  zapisem (`run`, `check`, `query`) istnieją dopiero w `execute()` i w sprawdzeniu dostępności
  po osobnej zgodzie (p. 6.5). Serwer modelu jest poza tą regułą — konfiguruje go użytkownik.
- **Sprawdzenie dostępności wysyła tylko wartości z planu** (obszar, produkt, lata…) do tych
  samych usług danych, które zapytałoby wykonanie; nigdy treści polecenia, odpowiedzi, danych
  modelu ani zawartości plików. Zgoda jest jednorazowa, nie jest częścią zapisanego planu,
  a każda zmiana planu ją cofa (p. 6.5).
- Handlery zapisują wyłącznie do przydzielonego katalogu wyników (p. 3.2.4). Magazyn narzędzia
  zapisuje tylko samo narzędzie, przez swój klient, w folderze z `[retman.tools.<narzędzie>] store_dir`;
  Retman niczego w nim nie zmienia ani nie usuwa.
- **Magazyny narzędzi** (p. 9.1): ścieżki są bezwzględne, bez `..` i bez składnika będącego
  dowiązaniem symbolicznym (IMGWTools takiej ścieżki nie przyjmuje; `retman doctor` zgłasza ją
  także dla Kartografa), magazyny są rodzeństwem (żaden nie leży w drugim; cache Kartografa
  i dane referencyjne IMGWTools nie leżą w magazynie) i leżą na dysku z dowiązaniami twardymi
  (p. 7.2). Pliki z magazynu są w wyniku wskazywane ścieżką bezwzględną i sumą SHA-256 (p. 5.4).
- **Pliki geometrii** użytkownika (SHP, GPKG) Retman tylko odczytuje: listę warstw GeoPackage
  czyta przez `sqlite3` w trybie tylko do odczytu, a w śladzie audytowym zapisuje nazwę warstwy
  i sumy SHA-256 plików (p. 5.4). Plik czyta narzędzie; do usług danych trafiają parametry żądania,
  nie plik.
- Retman nie wysyła poleceń użytkownika ani jego odpowiedzi poza skonfigurowane backendy modeli.
  Narzędzia łączą się z publicznymi usługami danych (GUGiK, IMGW, ČHMÚ) po potwierdzeniu planu
  albo, na życzenie, w sprawdzeniu dostępności; do usług trafiają parametry żądania.
- Domyślna konfiguracja modeli wskazuje wyłącznie na `localhost`.
- **Gdzie działa model, decyduje użytkownik** w ustawieniach. Retman nie ocenia adresów
  i nie ostrzega; `retman doctor` pokazuje adres każdego modelu (p. 7.2).
- basal-serve nie ma własnej kontroli dostępu. Na serwerze jednostki zabezpieczenie dostępu
  należy do wdrażającego (wzmianka w README).
- **Klucze API** są odczytywane wyłącznie ze zmiennych środowiskowych (w konfiguracji jest tylko
  nazwa zmiennej). Nigdy nie trafiają do plików konfiguracyjnych, logów ani `result.json`.
- **Dziennik projektu i dane audytowe** zawierają treść poleceń, bo są zapisem pracy użytkownika;
  zostają w folderze projektu, a zapisywanie w nich treści poleceń i odpowiedzi można wyłączyć
  (`journal_commands = false`, p. 5.4). Wtedy dziennik nie zawiera też innych tekstów, które
  mogą cytować słowa lub ścieżki użytkownika: pokazanego planu, powodu ponownego zadania pytania
  i linii raportu dostępności.
- **Log techniczny** jest zapisywany lokalnie, bez treści poleceń (p. 5.4).
- Zbieranie poleceń ze wszystkich projektów w jednym pliku (`[retman.privacy] collect_commands`,
  p. 5.4) jest **opcjonalne, domyślnie wyłączone i wymaga wyraźnej zgody** — `retman init`
  pyta o nią. Plik zostaje na komputerze użytkownika. Przekazywanie poleceń autorowi wymaga
  osobnej, wyraźnej zgody użytkownika i nigdy nie dzieje się automatycznie.
- **Serwer MCP (od v0.3, p. 7.5.1):** wykonanie przez MCP tylko po potwierdzeniu człowieka
  w kliencie; klient, który go nie potrafi uzyskać, dostaje tylko plan (zamknięcie awaryjne).
  Asystent AI podłączony przez MCP jest usługą spoza ustawień Retmana (N-04): treść poleceń
  i ścieżki bezwzględne są dla niego domyślnie ukryte.

---

## 11. Komponenty w kolejnych wersjach

Zakres produktowy wersji opisuje PRD. Tu: które komponenty techniczne powstają w której wersji.

| Wersja | Komponenty |
| --- | --- |
| **0.1** | rdzeń pipeline, backend `basal` (domyślny) i `openai_compatible` (alternatywa), ekstraktory (w tym prawdopodobieństwo, stacje, okresy, punkty, plik geometrii), wspólny adapter z warstwą komend (`calls`, klienci narzędzi, podgląd offline, sprawdzenie dostępności), adaptery Kartografa 0.8.0 i całego IMGWTools 3.0.0 z dwustopniowym rozpoznawaniem operacji, magazyny narzędzi w konfiguracji, `retman-scaffold` (`list`, `draft`, `--check`), CI z testami na obsługiwanych wersjach narzędzi, pliki tłumaczeń (PL), CLI i API Pythona (w tym plan jako dane i `known`), `retman doctor`, przestrzeń robocza w folderze projektu (numerowane wyniki, wybór wejścia bez zgadywania, `retman results`), plik centralny i `retman init`, dziennik projektu i ślad audytowy (`retman log`), `retman-eval`, pomiary czasu odpowiedzi (p. 9.2), CI na Windows, Linux i macOS, w tym test instalacji na czystych systemach (p. 9.4) |
| 0.2 | resolver łańcuchów, kontrole sensowności między krokami, wznawianie łańcucha, nazwane wyniki, opis wyników przez model tekstowy, natywne API dostawców (opcjonalne), opisy i handlery pozostałych narzędzi ekosystemu (Hydrolog, Hydrograf, BasicHydraulics) |
| 0.3 | serwer MCP (`retman[mcp]`, stdio, potwierdzenie przez elicitation, pole `channel` w śladzie; p. 7.5.1) |
| 0.4 | API HTTP |
| 0.5+ | okno czatu dla ścieżki prostej, skrypty instalacyjne (`install.sh`, `install.ps1`), kreator `retman init`, `retman add-tool`, integracja z GUI (p. 7.4), pliki `en.toml` |

---

## 12. Otwarte kwestie techniczne

1. **Typy w publicznym API narzędzi** — rozstrzygnięte dla Kartografa i IMGWTools: wybory nie są
   typowane jako `Literal` (Kartograf: `str | None`), a maszynowym źródłem prawdy jest katalog
   komend (`allowed`, `enum`, `validate_command`), więc `retman-scaffold` czyta katalogi,
   a nie docstringi (ADR-013, ADR-019). Do sprawdzenia dla Hydrologa, Hydrografa
   i BasicHydraulics: czy mają katalog komend, a jeśli nie — czy wybory są typowane
   jako `Literal`/`Enum`, a pliki jako `Path`.
2. **Ekstrakcja parametrów swobodnych** — dla stacji IMGW nazwy rozwiązuje kod, offline,
   z katalogu w magazynie (p. 4.3). Otwarte zostaje to, czy w trudnych przypadkach
   (np. obszar podany nazwą rzeki lub miejscowości zamiast współrzędnych) wystarczy kod,
   czy potrzebny będzie Bielik albo geokoder.
3. **`facts: "auto"` w basalu** — sprawdzić, czy wbudowane rozpoznawanie dat i kwot po polsku
   może zastąpić część ekstraktorów.
4. **Progi pewności** — dostroić na własnym zbiorze testowym zamiast domyślnych.
5. **Słownictwo branżowe** — sprawdzić, jak basal radzi sobie z terminami hydrologicznymi
   (np. „przepływ miarodajny”, „SNQ”, „WWQ”) i ile synonimów potrzeba w opisach operacji i opcji.
6. **Kontrole sensowności danych** — gdzie je umieścić: w samych narzędziach (korzystają z nich
   wszyscy, także bez Retmana) czy w Retmanie? Rekomendacja: kontrole wyników w narzędziach,
   w Retmanie tylko kontrole przejść między krokami łańcucha.
7. **Rodzaje danych** — pełna lista nazw `kind`, ich formatów plików i wymaganych atrybutów
   (p. 3.2.6). Formaty warto od początku dobierać tak, żeby przyszłe GUI mogły je wczytywać.
   Ustalone dla Kartografa (ADR-004, ADR-016) i IMGWTools (ADR-017); Hydrolog, Hydrograf
   i BasicHydraulics otwarte.
8. **Integracja z GUI** (p. 7.4) — wariant połączenia (A czy B) i technologia GUI, gdy GUI powstaną.
9. **LM Studio jako serwer modelu** — czy jego API zwraca `logprobs` i obsługuje odpowiedzi
   ustrukturyzowane (lista dozwolonych wartości). Od tego zależy jakość decyzji modeli
   generatywnych (p. 3.3.3). Sprawdzone 2026-10-11 dla Bielika 11B i 4.5B (MLX): `logprobs`
   i enumeracja w `json_schema` działają; Qwen nieprzetestowany
   (`docs/research/2026-10-11-lm-studio-openai-compatible.md`).
10. **basal w LM Studio** (niski priorytet — domyślnie basal działa przez basal-serve) — basal ma pliki GGUF, ale jego decyzje wymagają specjalnego odczytu
    (prawdopodobieństwa liter opcji, obie kolejności, kalibracja), który dziś zapewnia basal-serve.
    Do sprawdzenia: czy da się odtworzyć ten odczyt w Retmanie przez API z `logprobs`, żeby basal
    działał w LM Studio bez osobnego basal-serve.
11. **Modele generatywne a basal** — porównanie trafności i pokrycia automatycznego na zbiorze
    testowym (rozdz. 8) dla konfiguracji z p. 3.3.4.
12. **basal-serve na Windows** — który tryb pracy (PyTorch, Ollama, llama.cpp) działa najpewniej;
    od tego zależy instrukcja instalacji modelu dla testerów z Windows (p. 9.4).
13. **Uruchamianie basal-serve** — ręcznie przed pracą czy jako usługa startująca z systemem
    (w wersji łatwej); usługa to wygoda, ale też ingerencja w system użytkownika.
14. **Łańcuchy: resolver czy przepisy autora** (p. 4.5) — alternatywa: łańcuchy jako przepisy
    pisane i przeglądane przez autora, a logika resolvera tylko do szkicu i sprawdzania
    przepisów. Do oceny po dodaniu kolejnych narzędzi; razem z nią możliwe zastosowania n8n
    jako otoczenia Retmana (monitoring, kontrola jakości, rejestr wyników, kanały zleceń).
    Opis: `docs/PROGRESS.md`, Backlog, „Do rozważenia”.
15. **Klienci MCP a potwierdzenie** (p. 7.5.1) — które klienty implementują elicitation z wydania
    protokołu 2026-07-28. Test dymny przed v0.3; zamknięcie awaryjne obowiązuje niezależnie
    od wyniku.
16. **Pytania Retmana przez MCP** (p. 7.5.1) — wartości dostarczone przez agenta jako `known`
    czy także wybory przez elicitation. Rozstrzygnięcie na starcie v0.3.
