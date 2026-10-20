# Sprawdzanie dostępności bez sieci przed potwierdzeniem (decyzja autora 4)

- **Data:** 2026-10-19
- **Zakres:** jak spełnić „bez sieci przed potwierdzeniem planu” (decyzja autora 4) i dać
  użytkownikowi informację o dostępności danych: niezmiennik N-12, hak `preview` (offline), krok
  `check` (sieć, osobna zgoda), kontrakt, UX, wpływ na pliki Retmana, testy, ryzyka.
- **Metoda:** oba narzędzia uruchamiane offline pod **blokadą gniazd** (DNS + `connect` rzucają
  wyjątek; każda próba jest zgłaszana): Kartograf `develop` `d7b5369e` (czyste drzewo), IMGWTools
  `31e96fa` (eksport `git archive` do `/tmp`, bo drzewo IMGWTools miało w chwili badania ~25
  niezatwierdzonych plików edytowanych przez kogoś innego; wyniki identyczne na czystym eksporcie).
  [WNIOSEK] = odczytane z kodu/dokumentacji, niewykonane. Kontrakty uzgodnione komunikatami z
  GeometryArea (hak `preview`), IntegrationStrategy (`ToolContext`, `PlanClient`/`RunClient`) i
  ImgwScope (operacje IMGWTools). Powtarzalność: dodatek.
- **Status:** decyzja delegowana przez autora (2026-10-19) — decyzje autora 4 i 8.

## Decyzje końcowe (nadpisują treść raportu poniżej)

Źródło: konsolidacyjny plan wdrożenia z 2026-10-19.

1. **Bez sieci przed potwierdzeniem (N-12)** — `preview` jest **WYMAGANY**, a **krok `check`
   (odpowiedź `s`) jest wdrażany w v0.1** (raport oznaczał go jako zalecany i możliwy do przesunięcia
   na v0.2 — to nadpisane). Kontrakt się nie zmienia.
2. **Ortofotomapa (decyzja autora, nadpisuje K2/D10):** Retman pyta o kolor; produkt `orthophoto`
   idzie przez własny handler na providerze (`GugikOrtoProvider(color=…)` + `DownloadManager`),
   wyłącznie po kodach arkuszy (geometria/bbox → problem w podglądzie offline). Podgląd
   (`validate_command("imagery download", …)`) działa bez koloru. W tabeli p. 4.9 wiersz
   „`download_sheet_hierarchy` … orthophoto → plan świeżości `imagery download`” pozostaje [WNIOSEK]:
   funkcja `check` dla ortofotomapy musi być zgodna z tą drogą wykonania (wybór podejmuje autor
   adaptera Kartografa; wg p. 8 pkt 3 `check` można w v0.1 ograniczyć do operacji arkuszowych i BDOT10k).
3. **Handler** ma sygnaturę `handler(params, inputs, output_dir, ctx)`; operacja deklaruje `calls`
   i/lub `handler` (co najmniej jedno). `ToolContext`/`PlanClient`/`RunClient`/`ToolDriftError`
   dokładnie wg raportu `2026-10-19-integracja-narzedzi.md` (p. 1.3–1.4); numer ADR i numery W/N
   przydziela Main (ten raport proponuje N-12 i W-17).
4. Podgląd offline obowiązuje dla **każdej** operacji i każdego typu obszaru (Kartograf i IMGWTools).

## 1. Rekomendacja (rozstrzygająca)

**Niezmiennik (nowy, proponowany N-12).** Przed `plan.confirm()` Retman nie woła **żadnej funkcji
narzędzia ze skutkiem sieciowym**. Jedyny wyjątek to `Retman.check(plan)`, osiągalne tylko po
*osobnym* `plan.confirm_check()`. (Serwer modelu decyzyjnego jest poza tą regułą: konfiguruje go
użytkownik, N-04.) Dziś niezmiennik już zachodzi: `httpx` jest importowany tylko w
`retman/backends/openai_compatible.py` i `retman/doctor.py`; ekstraktory to czysty kod.

Dwie warstwy, w tej kolejności:

| Warstwa | Co | Sieć | v0.1 |
|---|---|---|---|
| 1. **`preview`** (offline) | jeden opcjonalny hak manifestu, wołany gdy nie zostały pytania; `validate_command` Kartografa/IMGWTools dla **każdej** operacji i typu obszaru; *problem* ponownie otwiera wskazane parametry jako pytania | nigdy | **WYMAGANE** |
| 2. **`check`** (sieć, osobny krok) | opcjonalny klucz manifestu `check`; 4. odpowiedź `s` w pytaniu o plan; własna uwaga + własna zgoda; raport tylko do odczytu; nigdy nie edytuje planu | dopiero po zgodzie | **WDRAŻANE w v0.1** (decyzja końcowa 1; wcześniej: zalecane, addytywne, mogło przesunąć się na v0.2 bez zmiany kontraktu) |

Dlaczego taka kolejność: niepoprawne żądanie (5 m + KRON86, wycinek WCS w 0,5 m, NMPT bez
rozdzielczości, zły TERYT, zły plik geometrii) jest odrzucane przez narzędzie *offline*, więc nigdy
nie dociera do pytania o potwierdzenie i **żaden krok sieciowy nie jest wydawany na żądanie, które
narzędzie odrzuca**. Czego walidacja offline nie wie, to co źródło *ma* dla obszaru (lata,
istniejące rozdzielczości, pełne pokrycie, opublikowane pliki IMGW) — tylko to jest krokiem sieciowym.

**Odrzucone alternatywy** (powód w jednym wierszu):
- *Sieć w trakcie planowania / automatyczne sprawdzenie* — narusza decyzję 4.
- *Sprawdzenie jako widoczna samodzielna operacja* („Sprawdź dostępność…”) — ponowne wpisywanie
  kontekstu, zużywa numery wyników i foldery przestrzeni roboczej, dokłada się do listy
  rozpoznawania 10 opcji; mapowanie plan → zapytanie i tak jest kodem. (Zostaje możliwe później:
  nakładka, której `handler` używa funkcji `check`.)
- *Sprawdzenie jako ukryta operacja uruchamiana przez `execute()`* — zachowuje jedną bramkę, ale
  wymaga powiązania + flagi ukrycia + wyświetlenia wyniku + numeracji; właściwość pojedynczej
  bramki uzyskujemy tu regułami bramki i testami (4.1, 7).
- *Flaga CLI `--check` / sprawdzenie bez TTY* — druga ścieżka do sieci bez zgody na ekranie.
- *Łatanie gniazd w czasie działania wokół `preview`* — globalny monkeypatch jest niebezpieczny,
  gdy MCP (0.3) / HTTP (0.4) obsługują współbieżne plany; wymuszać testami z nagrywającą blokadą (7).
- *Wyprowadzanie „wymaga zgody” z metadanych skutków narzędzia* — Kartograf deklaruje `effects`
  per komenda, ale **nie dla bliźniaków `check_*`**; `check_command` IMGWTools jest offline dla
  większości komend. Reguła zamiast tego: **każdy zadeklarowany `check` jest krokiem sieciowym**
  (zachowawczo, jednolicie).
- *Przełącznik w `retman.toml` wyłączający sprawdzenia* — niepotrzebny (zob. 4.8).

## 2. Dowody: co jest offline w narzędziach

### 2.1 Kartograf 0.8.0

| Funkcja | Wynik pod blokadą | Dowód |
|---|---|---|
| `validate_command(cmd, options, *, output_dir=None)` | **offline, nic nie zapisuje** („without network and without writing: what the function does before its first request”). Rzuca `ValidationError` z `.option` **lub** `.options` (krotka) + `.allowed`: 5m+KRON86 (`options=('resolution','vertical_crs')`, tekst wymienia KRON86: 0.5m,1m), NMPT bez rozdzielczości, brak vertical_crs, wycinek WCS ≠ 1 m („wycinki PL (--cutout) sa tylko 1 m”), zły arkusz (`ParseError`), TERYT ≠ 4 cyfry, nieznana etykieta rozdzielczości (wymienia warianty rejestru) | `kartograf/commands.py:185-212`; `project/commands.py:137-153` (`validate`: „no network”); `download/data.py:532-584` (`validate_data_request`, `dry=True`); przebieg z blokadą |
| `get_catalog`, `data_commands`, `list_sources`, `describe_sheet`, `parse_command`, `countries_for_bbox`, `transform_bbox` | offline | przebieg z blokadą |
| `check_pl_cutout`, `check_command` (wycinek) | **offline**: „WCS channel has no remote version signal … no PRG, WCS or metadata cache request is made”; czyta tylko lokalny magazyn. `check_image_cutout`, `check_cz_cutout`: to samo w docstringach [nie uruchomione] | `download/cutout.py:424-451`; przebieg z blokadą |
| `check_landcover(bdot10k, teryt=…)`, pusty magazyn | offline (status `missing`, brak sygnału); z `bbox=`/`sheet=` → **sieć** (powiaty PRG, jedna pozycja na powiat) | `landcover/manager.py:2064`; przebieg z blokadą |
| `check_availability`, `check_data`, `check_command` (arkusz), `check_soil`, `check_hsg`, `discover_teryts_for_bbox` | **sieć** | `download/availability.py:1-60,451-549` (indeks WFS + PRG, „no data file is ever requested”); przebieg z blokadą |
| `check_collection`, `check_laz_area`, `check_cz_laz`, `check_cz_sheet` | sieć dla kanałów ze zdalnym sygnałem (indeks WFS / HEAD / ATOM); kanały bez niego (kafle WCS/ImageServer) czytają tylko lokalny magazyn [docstringi, nie uruchomione] | `download/collections.py:3434`, `laz.py:498` |

Trzy fakty kształtujące projekt:

1. **„check” oznacza *świeżość lokalnego magazynu*, a nie dostępność.** `check_*` zwraca `UpdatePlan`
   (`kartograf-plan/1`, pozycje `missing|current|newer|unverifiable|check_failed`,
   `download/plan.py:1-85`). W świeżym folderze wyniku wszystko jest `missing`. Raport
   *dostępności* (lata, rozdzielczości, układ wysokościowy, `complete`, `download_hint`) to
   `check_availability` → `AvailabilityReport` (`kartograf-availability/1`; klucze JSON
   `combinations[].{year,resolution,vertical_crs,format,horizontal,complete,sheets_full,sheets_partial,uncovered_m2}`,
   sprawdzone przez serializację syntetycznego raportu) = komenda katalogu `elevation availability`
   (`kind=query, effects=['network']`).
2. **Ta komenda jest poza warstwą komend**: `run_command`/`check_command`/`validate_command` przyjmują
   tylko 12 komend *danych* (sprawdzone: `ValidationError: do projektu mozna dodac komendy zapisujace
   dane`). Uzgodnione z IntegrationStrategy: `RunClient.query(call)` jest trzecim czasownikiem dla
   komend zapytań sieciowych.
3. **Skutek uboczny cache**: `cache=True` (domyślnie każde `check_*`) otwiera `.kartograf_cache.db` w
   **cwd** (`cache/defaults.py:13-15,50-54`) = folder projektu użytkownika. Kilka `check_*` mówi
   też „the metadata cache is refreshed, never read”. Handlery sprawdzające przekazują więc
   `cache=False` (albo jawny `MetadataCache`), nigdy domyślną wartość.

Opóźnienie (zmierzone, ciepłe): `import kartograf` 0,44 s raz na proces; `validate_command`
0,0003–0,001 s na wywołanie. Wywołania offline **nie** utworzyły żadnego pliku w cwd (sprawdzone).
Typy zwracane: `check_data`, `check_landcover`, `check_soil`, `check_hsg`, `check_collection`,
`check_pl_cutout`, `check_command` → `UpdatePlan`; `check_availability` → `AvailabilityReport`;
`check_project` → `ProjectCheck`. Wszystkie mają `to_dict()` (dokument JSON z polem `schema`).

### 2.2 IMGWTools 3.0.0 (`31e96fa`)

| Funkcja | Wynik pod blokadą | Dowód |
|---|---|---|
| `validate_command(cmd, /, *, options)` | **offline** („without network access”); zwraca znormalizowane opcje; rok < `first_year` (1951 dla hydro dobowych), współrzędne poza 49–55°N, gramatyka kodu stacji (9 cyfr lub WIGOS), normalizacja zbioru/dostawcy. **Offline nie istnieje górna granica roku** | `commands.py:2077-2121`; `datasets.py:169-171,209,21` |
| `datasets()`, `get_dataset`, `providers()`, `archive_files()` | offline (URL-e archiwów liczone z rejestru) | przebieg z blokadą |
| `check_command` dla `datasets download`, `stations find` (live), `pmaxtp fetch`, `current hydro` (przebieg z blokadą); `datasets files`, `pmaxtp url`, `store init|info`, … (ta sama tabela dyspozycji, nie uruchomione) | **plan na sucho offline** (`imgw-plan/1`, URL-e + oczekiwane ścieżki, status `missing`/`unverifiable`, „bez żadnego żądania”) | `commands.py:2354-2490,2672-2712,2715-2779` |
| `check_pmaxtp` (przebieg z blokadą), `check_series` [docstring: „no network access and no writes”, nie uruchomione] | offline | `store/pmaxtp.py:171`, `store/series.py:350` |
| `check_store` (= `check_command("store sync")`) (przebieg z blokadą); `check_catalog`, `check_project` [docstringi: HEAD / listingi, nie uruchomione] | **sieć**: listing katalogu + HEAD; „a file is published when its name appears in the listing”; nieopublikowany → `unverifiable` z `error="nieopublikowany"`; wymaga *istniejącego* korzenia magazynu | `store/sync.py:759-830`; `store/catalog.py:1429`; `project.py:2049` |
| `find_stations(source="live")`, `fetch_pmaxtp` (przebieg z blokadą); pozostałe `fetch_*` [nie uruchomione] | sieć | przebieg z blokadą |
| `find_stations(source="store")` | offline, ale rzuca `IMGWStoreError`, dopóki `build_catalog` (operacja sieciowa) nie wypełni magazynu | przebieg z blokadą |

Metadane skutków istnieją i są dobre: `DataCommand.network` / `.writes` per komenda oraz niezmiennik
„każda komenda zapisująca ma bliźniaka `check`” (`store/types.py:1048-1056,1072-1073`; spec
`docs/superpowers/specs/2026-10-19-agent-support-design.md` §3.2). Ponieważ `check_command` IMGWTools
jest w większości *planem na sucho*, **nie deklarować `check` dla operacji punktowych/live**
(`pmaxtp fetch`, `current *`, `stations find`): nie ma tam nic do dowiedzenia się, czego nie
powie samo wywołanie, a zgoda byłaby zmarnowana. Dla synchronizacji archiwów sensownym sprawdzeniem
sieciowym jest `check_store` (opublikowany / nieopublikowany / błąd per plik).

Typy zwracane: `check_command` → `CommandResult[StorePlan]` (koperta `imgw-result/1`; `.result`
to plan `imgw-plan/1`; status `partial`/`failed`, gdy pozycje są `check_failed`); `check_store`,
`check_catalog`, `check_series`, `check_pmaxtp`, `check_project` → `StorePlan` (JSON
`items[].{dataset,url,year,month,station_code,status,error,…}`, `actions[]`, `requests`).

## 3. UX

### 3.1 CLI (polski; dokładne teksty proponowane, w `pl.toml`)

Pytanie dostaje 4. klawisz **tylko gdy operacja deklaruje `check` i plan jest kompletny**:

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
    NMT 5 m, EVRF2007 — rok 2024, komplet
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

Reguły: każda odpowiedź inna niż `t` w pytaniu o zgodę = **odmowa** (zamknięcie awaryjne; dziennik
`rejected`, powrót do pytania o plan, „Sprawdzenie pominięte.”). Po raporcie wraca to samo pytanie o
plan; `z` działa jak dziś (użytkownik decyduje, co zmienić); `t` potwierdza plan. Sprawdzenie nigdy
nie blokuje `t`, nawet przy `unavailable` (Retman informuje, użytkownik decyduje). Ctrl+C w trakcie
sprawdzenia → standardowe „Anulowano.” (kod 3), ale dziennik nadal dostaje zdarzenie `check`
(`try/finally`). Nieudane sprawdzenie (brak sieci, błąd usługi) to *raport* ze statusem `unknown`,
a nie wyjątek: „Sprawdzenie nie powiodło się: …”, powrót do pytania o plan. Bez terminala /
`--plan-only`: **brak sprawdzenia** (kody wyjścia bez zmian). Tryb sesji: nic szczególnego.

### 3.2 API Pythona (odzwierciedla `confirm()` / `execute()`, ARCHITECTURE 7.1)

```python
plan = retman.plan("…")                      # offline; `preview` already ran
while plan.questions: …                      # as today
if plan.can_check:                           # operation declares `check` and plan is complete
    print(plan.check_notice())               # what the step contacts and sends (from pl.toml)
    if input("Check availability? [y/n] ") == "y":
        plan.confirm_check()                 # separate consent; does NOT confirm the plan
        report = retman.check(plan)          # CheckReport; raises CheckNotConfirmedError without confirm_check()
        print(report.summary())              # status + lines; plan values untouched
print(plan.summary())                        # now has a "Sprawdzenie dostępności: …" row
if input("Execute? [y/n] ") == "y":
    plan.confirm(); result = retman.execute(plan)
```

## 4. Kontrakt

### 4.1 Reguły bramki (testowalne niezmienniki)

1. `Retman.check()` rzuca `CheckNotConfirmedError`, chyba że `plan.check_confirmed`; zgoda jest
   **jednorazowa** (czyszczona przy wejściu), **nieserializowana** (`to_dict` ją pomija; `from_dict`
   zawsze daje `False`), czyszczona każdą zmianą planu (`_updated`).
2. `confirm_check()` nigdy nie ustawia `confirmed`; `execute()` nadal wymaga `confirm()`. `check()`
   **czyści `confirmed`/`confirmed_at`** (podsumowanie się zmieniło; użytkownik musi potwierdzić po
   zobaczeniu raportu): kolejność to zawsze check → confirm → execute.
3. `confirm_check()`/`check()` wymagają kompletnego planu (brak otwartych pytań, ustawiona
   `operation`) i zadeklarowanego `check`.
4. Sprawdzenie **nie tworzy numeru wyniku, folderu wyniku, nic nie zapisuje w przestrzeni roboczej**.
   Jedyne punkty wejścia zdolne do sieci to `execute()` (po `confirm()`) i `check()` (po
   `confirm_check()`); każdy buduje zdolnego do sieci `ctx.client` (`RunClient`); w `preview` klient
   jest offline'owym `PlanClient` (IntegrationStrategy).
5. Sprawdzenie **nigdy nie zmienia wartości planu** (4.6). `plan.checks` zawsze opisuje *dokładnie*
   bieżący stan planu (`_updated` je czyści); starsze sprawdzenia zostają w dzienniku.
6. Błąd narzędzia/sieci → `CheckReport(status="unknown", error=…)`; `KeyboardInterrupt` propaguje
   się (zapisany w dzienniku).

### 4.2 Manifest, typy haków (jeden nowy klucz ode mnie; `preview` należy do GeometryArea)

```python
# retman/registry/manifest.py
class CheckItem(TypedDict):                  # like HandlerWarning
    key: str                                 # entry of the tool's [check] table in pl.toml
    args: dict[str, str]                     # fills {placeholders}

class CheckOutput(TypedDict):
    status: Literal["available", "partial", "unavailable", "unknown"]
    items: list[CheckItem]                   # display order: the plan's own selection first, then alternatives

# OperationSpec (additive, both NotRequired):
#   preview: str    # "module:function" — GeometryArea owns PreviewOutput = {values, rows, problems}
#   check:   str    # "module:function" — presence = the operation offers `s` (a NETWORK step)
# signatures (ctx = read-only ToolContext, IntegrationStrategy; drop the argument if ToolContext is not adopted):
#   preview(params: dict[str, Any], ctx) -> PreviewOutput      # OFFLINE, ctx.client = PlanClient
#   check(params: dict[str, Any], ctx)   -> CheckOutput        # NETWORK, ctx.client = RunClient (check()/query())
class PreviewProblem(TypedDict):             # declared by GeometryArea with PreviewOutput; semantics specified here (4.5)
    params: list[str]                        # NON-EMPTY; every name must be a param of the operation
    key: str                                 # text in the tool's [problems.<key>]
    args: dict[str, str]
```

Znaczenie `status` (rdzeń sam przypisuje `unknown` przy wyjątkach): `available` = wybór z planu
może być obsłużony tak, jak określono; `partial` = część (brakujące/niekompletne arkusze lub
pliki); `unavailable` = nic; `unknown` = nie dało się ustalić. Handlery powinny streszczać zamiast
zrzucać (np. ≤ jedna linia na rok/kombinację); linie trafiają do dziennika i `result.json`.

Dodatki do `validate_manifest`: dla `preview` i `check` niepuste i zawiera `":"` (ta sama reguła co
`handler`); gdy `check` jest obecny, wymagany klucz tłumaczenia `operations.<id>.check.notice` w
każdym zadeklarowanym języku. Klucze pozycji nie są walidowane statycznie (tak jak
`HandlerWarning.key`); ćwiczą je testy handlerów (STANDARDS 10.4).

### 4.3 Teksty

Rdzeń `retman/i18n/pl.toml`:

```toml
[plan]
check = "Sprawdzenie dostępności: {status} ({time})"
[check]
status_available = "dane dostępne"
status_partial = "dane dostępne częściowo"
status_unavailable = "brak danych dla tego wyboru"
status_unknown = "nie udało się sprawdzić"
notice = "Sprawdzenie dostępności to osobny krok i jedyny, który łączy się z internetem przed wykonaniem planu. {operation}\nNie pobiera plików, niczego nie zapisuje w wynikach i nie wysyła Twojego polecenia — tylko wartości z planu."
header = "Sprawdzenie dostępności ({tool} {version}, {time}): {status}"
failed = "Sprawdzenie nie powiodło się: {error}"
[cli]
confirmation_check = "Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)"
check_confirmation = "Połączyć się z internetem i sprawdzić? [t]ak / [n]ie"
check_declined = "Sprawdzenie pominięte."
checking = "Sprawdzam… (Ctrl+C przerywa)"
[journal]
check = "sprawdzenie dostępności"
check_approved = "wykonane"
check_rejected = "pominięte"
```

`retman/tools/kartograf/pl.toml`: `[operations.<id>.check] notice = "Zapytam usługi GUGiK
(skorowidz arkuszy WFS i warstwę PRG) o dane dla godła z planu."`; tabela `[check]` szablonów pozycji
(`selection_available`, `selection_partial`, `selection_unavailable`, `other_combination`, …);
`[problems]` (klucz GeometryArea `kartograf_validation = "Kartograf odrzuca ten wybór: {error}"`
jako zapas; **zalecane osobne klucze dla dwóch częstych reguł** — rozdzielczość × układ
wysokościowy oraz „wycinek tylko 1 m” — z `{allowed}` z `ValidationError.allowed`, bo własny tekst
Kartografa to polski ASCII bez diakrytyków).

### 4.4 Rdzeń (pliki Retmana)

```python
# retman/exceptions.py
class CheckNotConfirmedError(RetmanError):   # sibling of PlanNotConfirmedError, NOT a subclass (callers' remedy differs)

# retman/core/check.py  (new, tiny)
@dataclass(frozen=True)
class CheckReport:
    operation: str; tool: str; version: str
    checked_at: str                           # journal.utc_now()
    status: Literal["available","partial","unavailable","unknown"]
    items: list[CheckItem]                    # machine-readable facts
    lines: list[str]                          # rendered Polish lines, exactly as shown
    error: str | None = None
    def summary(self) -> str: ...             # header + lines
    def to_dict(self) -> dict[str, Any]: ...  # JSON; from_dict for Plan.from_dict

# retman/core/plan.py — Plan gets:
reopened: dict[str, str]                      # param -> translated error (4.5); serialized
check_confirmed: bool = False                 # NOT serialized
checks: list[CheckReport]                     # serialized; reset by _updated
@property can_check -> bool                   # owner set, operation set, no questions, "check" in spec
def check_notice(self) -> str                 # delegates to Retman.check_notice(plan)
def confirm_check(self) -> "Plan"             # PlanIncompleteError if not can_check; sets check_confirmed
# _updated: replace(..., confirmed=False, confirmed_at=None, check_confirmed=False, checks=[])
# summary(): last row texts.get("plan.check", status=…, time=…) when checks
# to_dict/from_dict: + "reopened", "checks" (required keys, clean cutover, no .get fallback)

# retman/core/pipeline.py — Retman gets:
def check_notice(self, plan) -> str           # texts "check.notice" with operation's operations.<id>.check.notice
def check(self, plan) -> CheckReport          # gate rules 4.1; journal "check"; appends to plan.checks
def record_check(self, plan, status) -> None  # journal "check" with status "rejected" (declined consent)

# retman/adapters/manifest_adapter.py
def run_check(operation, params, ctx, texts) -> CheckReport
    # lazy importlib of operation.spec["check"]; lines = operation.texts.get(f"check.{key}", **args);
    # `except Exception` -> status "unknown", error=str(err), lines=[texts.get("check.failed", error=err)]
    # (same stance as execute_operation: a tool failure is a result, not a crash; BaseException propagates)
```

`retman/__init__.py`: eksport `CheckReport`.

### 4.5 Punkt wywołania `preview` i semantyka `problems` (moje; typ haka należy do GeometryArea)

Punkt wywołania: koniec `Retman._populate` (`pipeline.py:536-590`), po `plan.questions = questions`,
**tylko gdy `questions` jest puste** i `"preview" in operation.spec`; zatem raz przy `plan()` i
ponownie po każdym `answer_plan`/`change_plan` (oba kończą się w `_populate`). Koszt: jeden leniwy
import narzędzia na proces (0,44 s Kartograf, 0,24 s IMGWTools) + < 1 ms na wywołanie.

**Pułapka, która dyktuje projekt.** „Otwórz ponownie” nie może znaczyć „zdejmij wartość i dodaj
`Question`”, jak robi `change_plan` (`pipeline.py:787-819`): następne `_populate` *wyprowadza
wartość od nowa* (`_extract_param` ponownie czyta `plan.command`; `_choice_param` używa ponownie lub
pyta model), więc problem na parametrze wyprowadzonym z polecenia zostałby po cichu ustawiony z
powrotem (lub zapętlony), a użytkownik nigdy by nie został zapytany. A przy dwóch nazwanych
parametrach (5m + KRON86) użytkownik byłby pytany tylko o pierwszy i nigdy nie mógłby zmienić
drugiego. Naprawa — utrwalony znacznik:

```python
# _populate loop, AFTER the `applicable` check and the `known` branch, BEFORE derivation:
if name in plan.reopened:
    questions.append(self._param_question(operation, spec, error=plan.reopened[name])); continue

# end of _populate:
plan.questions = questions
if not questions and "preview" in operation.spec:
    params = {name: entry.value for name, entry in plan.values.items()}
    out = preview_operation(operation, params, ctx)          # offline; ctx.client = PlanClient
    if out["problems"]:
        self._reopen(plan, operation, out["problems"])       # sets plan.reopened, pops value/display/label; the model decision stays in plan.decisions (truthful audit)
        return self._populate(plan)                          # questions now non-empty -> no further preview
return plan

# _reopen: for each problem, names = [n for n in problem["params"] if n in plan.values and n not in plan.known];
# text = operation.texts.get(f"problems.{key}", **args); plan.reopened[n] = text for each name.
# If NOTHING gets reopened (all known / not in plan.values) -> raise RetmanError(text)   # guarantees termination
# unknown param name in a problem -> ManifestError-like programmer error.
# answer_plan: build `updated` with reopened=dict(plan.reopened) (like values=dict(plan.values)); on a successful answer for `name`:
#   updated.reopened.pop(name, None)   (value source "user")
```

Wynik dla 5m + KRON86: użytkownik jest pytany o `resolution` (z pokazanym błędem), potem o
`vertical_crs` (z pokazanym błędem), każde z normalnymi ponumerowanymi opcjami; odpowiedzi wchodzą
w normalne ścieżki; podgląd uruchamia się ponownie, gdy oba są odpowiedziane. `confirm()` jest
blokowane automatycznie, bo plan ma pytania (brak nowego stanu „problems” dla konsumentów
API/GUI/MCP: zachowane **plan kompletny ⇔ brak pytań**). Audyt: `answer_plan` zapisuje zdarzenie
`question` z `error=question.error`, gdy ustawione (dlaczego zapytano ponownie). `retman-eval`:
odrzucone kombinacje to `expect_clarify`; planowanie pozostaje offline względem narzędzi.

### 4.6 Co sprawdzenie może zrobić z planem

**Nic automatycznie.** Bez auto-wyboru, bez ukrywania opcji, bez zmian wartości (W-02: raport
informuje; odpowiada tylko użytkownik). v0.1 **nie ma pola `offers`** (brak konsumenta; dodanie go
później jest addytywne). Alternatywy lat/rozdzielczości pojawiają się jako linie raportu;
użytkownik może wtedy użyć `z` (istniejący przepływ), a każda nowa wartość przechodzi normalny
offline'owy `preview`. To pokrywa też `year`/`min_year`/`max_year` z Kartografa 0.8.0: nie da się
ich poznać offline, więc raport jest miejscem, w którym użytkownik dowiaduje się, jakie lata
istnieją, zanim jakiś wybierze. Po sprawdzeniu podsumowanie niesie jeden dodatkowy wiersz, więc
zatwierdzony plan i dziennik zapisują, że użytkownik zdecydował *po* jego zobaczeniu.

### 4.7 Dziennik i audyt (dodatki do ARCHITECTURE 5.4)

Zdarzenie `journal.jsonl` `check` (tylko dopisywane, zapisywane w `finally`):
`{"event":"check","status":"approved"|"rejected","result":"available|partial|unavailable|unknown"|null,"error":…,"tool":…,"version":…,
"lines":[…], **_plan_data(plan)}` — `_plan_data` (wartości ze źródłami, wejścia, decyzje) *jest tym,
co zostało wysłane*. `rejected` = zgoda odmówiona, brak sieci. Nie zapisywane do kolekcji ADR-010
(to nie wynik planowania). `retman log` renderuje `journal.check` + `journal.check_<status>`
(`cli.py:218`: rozszerzyć gałąź tłumaczenia `event == "plan"` na `"check"`).
`result.json["checks"]` = `[CheckReport.to_dict()]` *końcowego* stanu planu (dodane obok
`record["decisions"]`, `pipeline.py:984`; klucz obecny tylko gdy niepusty). Prywatność:
sprawdzenie wysyła tylko wartości planu (obszar, produkt, lata) do tych samych usług danych, które
odpytałoby wykonanie; nigdy tekstu polecenia, odpowiedzi, danych modelu ani zawartości plików.
Napisać to w ARCHITECTURE 10.

### 4.8 Konfiguracja / N-11

**Brak nowych kluczy `retman.toml`.** Sam Retman nie wprowadza żadnej wartości: `s` i uwagi to
teksty; statusy to kod; limity czasu należą do narzędzia (Retman żadnych nie przekazuje);
`cache=False` to jawny argument wewnątrz handlerów sprawdzających, a nie ustawienie Retmana.
Główny przełącznik „wyłącz sprawdzenia” rozważono i odrzucono: miejsce, które zezwala na pobieranie
z GUGiK/IMGW, zezwala na sprawdzenie wstępne, a to, które nie zezwala, i tak nie może wykonać.
Gdy decyzja o magazynie da wspólny plik cache metadanych, handlery przełączają się z `cache=False`
na niego bez zmiany kontraktu (sprawdzenie dzieliłoby wtedy odpowiedzi indeksu z późniejszym pobraniem).
(Zob. integracja: `[tools.kartograf] cache_file` jest już zdefiniowany — klient przekazuje
`MetadataCache(db_path=cache_file)` dla run/check/query.)

### 4.9 Handlery referencyjne

Kartograf (dokumenty JSON przez `ctx.client`; builder `calls(params, ctx)` wspólny dla
validate/run, IntegrationStrategy):

```python
def check_download_dem_sheet(params, ctx) -> CheckOutput:
    doc = ctx.client.query(availability_call(params))      # kartograf-availability/1, NETWORK; the client MUST pass cache=False (or an explicit MetadataCache), never the cwd default
    want = (params["resolution"], params["vertical_crs"].upper())
    mine = [c for c in doc["combinations"] if (c["resolution"], c["vertical_crs"]) == want]
    status = "available" if any(c["complete"] for c in mine) else "partial" if mine else "unavailable"
    return {"status": status, "items": [selection_item(status, params, mine), *map(other_item, others(doc, mine))]}
```

| Operacja Retmana | `check` (kandydaci v0.1) | Wywołanie Kartografa |
|---|---|---|
| `download_dem_sheet` | tak | availability `product=nmt`, `sheet=<code>` |
| `download_sheet_hierarchy` | tak | availability dla arkusza nadrzędnego (dem→nmt, dsm→nmpt); orthophoto → plan świeżości `check` komendy `imagery download` zmapowany na liczby / `NoCoverageError`→`unavailable` [WNIOSEK, nie uruchomione live; zob. decyzja końcowa 2] |
| `download_elevation_cutout` | tak, sformułowanie „wg skorowidza arkuszy” | availability `country=pl`, `bbox=…`; WCS składa najnowsze loty, indeks jest zastępnikiem [WNIOSEK] |
| `download_bdot10k` | tak | `check` komendy `landcover download` → jedna pozycja planu na powiat (PRG, sieć): „N pakietów powiatowych: …” — lista powiatów jest *niepoznawalna offline* |
| synchronizacja archiwów IMGWTools (jeśli ImgwScope ją definiuje) | tak | `ctx.client.check(sync_call)` → `imgw-plan/1`: opublikowane = `missing+newer+current`; nieopublikowane = `status=="unverifiable" and error=="nieopublikowany"`; `check_failed` → `unknown`, jeśli nic nie opublikowano |
| operacje punktowe/live IMGWTools, operacje z artefaktem planu (`check_imgw_archives` ImgwScope → `imgw_plan`) | **bez `check`** | te sprawdzenia-artefakty to zwykłe operacje (plan→confirm→execute), a nie haki; nigdy nie deklarować obu na jednej operacji |

Offline `preview` (wszystkie operacje Kartografa, każdy typ obszaru): `validate_command` →
`PreviewProblem(params=[err.option / err.options skierowane na parametry manifestu przez mapę
opcja→parametr buildera wywołań], key=…)`. **Bez zapasu „wszystkie parametry wyboru”** (uzgodnione z
IntegrationStrategy): odrzucenie, którego nie da się skierować na żaden parametr Retmana (odrzucona
opcja jest ustalona przez operację albo narzędzie dryfuje), rzuca programistyczny
`ToolDriftError(RetmanError)` („zainstalowane narzędzie nie przyjmuje już tej operacji: retman
doctor / retman-scaffold --check”); ponowne pytanie o niepowiązane parametry zapętliłoby się na tym
samym odrzuceniu. Ta sama rodzina zakończenia co 4.5 („nic do ponownego otwarcia → RetmanError”).
IMGWTools: `validate_command` (+ liczba `archive_files` jako wiersz podglądu; lata < `first_year`
łapane offline, lata przyszłe tylko przez sprawdzenie sieciowe). `validate_command` łapie brakujące
**wymagane** opcje (sprawdzone: `vertical_crs`, `resolution` NMPT), ale **nie** opcje, którym
biblioteka nadaje wartość domyślną (sprawdzone: BDOT10k z pominiętym `format` → zaakceptowane); to
siatka bezpieczeństwa dla decyzji 2/3, a nie zamiennik pytania.

## 5. Wpływ na pliki Retmana

| Plik | Zmiana |
|---|---|
| `registry/manifest.py` | `OperationSpec.check`/`.preview`; `CheckItem`, `CheckOutput`, `PreviewProblem`; `validate_manifest` (`:96-205`): reguła `":"` + tłumaczenie `check.notice` |
| `exceptions.py` | `CheckNotConfirmedError` |
| `core/check.py` (nowy) | `CheckReport` |
| `core/plan.py` | pola `reopened`, `check_confirmed`, `checks`; `can_check`, `check_notice`, `confirm_check`; `_updated` (`:157-158`); wiersz `summary`; `to_dict`/`from_dict` (`:111-155`) |
| `core/pipeline.py` | `_populate` (`:536-590`): gałąź `reopened` + punkt wywołania podglądu; `_reopen`; `answer_plan` (`:592-785`): zdejmowanie `reopened`, `error` w dzienniku; `check`, `check_notice`, `record_check`; `execute` (`:919-1010`): `record["checks"]` |
| `adapters/manifest_adapter.py` | `run_check` (obok `execute_operation`, `:13-57`); `preview_operation` należy do GeometryArea/IntegrationStrategy |
| `cli.py` | `_conversation` (`:63-141`): tekst potwierdzenia + gałąź `s`; renderowanie `log` (`:218`) |
| `i18n/pl.toml`, `tools/kartograf/pl.toml`, `tools/kartograf/handlers.py`/`manifest.py` | teksty 4.3; `preview_*`, `check_*`; klucze manifestu |
| `tests/conftest.py` (`:36-60`) | nagrywający wariant `_block_network` (7) |
| `__init__.py` | eksport `CheckReport` |

Szacunek: ~250 linii kodu + ~250 testów; sama warstwa 2 to ~150 z nich i da się ją wyciąć bez
dotykania warstwy 1.

## 6. Zmiany w dokumentacji (dokumenty po polsku; numeracja to propozycja — raport MCP rezerwuje już W-16)

- **ARCHITECTURE**: 1.1 nowy wiersz zasady „Bez sieci przed potwierdzeniem”; 2 (krok ④: offline
  `preview`; krok ⑤: opcjonalne `s`; uwaga w diagramie); 3.1 moduły (`core/check.py`); 3.2.4 reguły
  handlerów (`preview` offline, `check` sieć, bez `input()`/`print()`); 3.2.5 pkt 2/3 (narzędzie
  może być importowane w planowaniu tylko dla operacji z `preview`); 4.1–4.3 (klucze, tabela pól,
  teksty `[check]`/`[problems]`/`check.notice`); 5.4 (wiersz dziennika `check`; wiersz `result.json`
  `checks`); 6.1 (wiersz: kombinacja odrzucona offline przez narzędzie → pyta ponownie); 6.3 (osobna
  zgoda na sprawdzenie); 6.4 (klawisz `s`; bez TTY: brak sprawdzenia); **nowe 6.5 „Sprawdzenie
  dostępności”** (UX 3.1, reguły bramki 4.1, co jest wysyłane); 7.1 (tabela API: `can_check`,
  `check_notice`, `confirm_check`, `check`, `checks`); 7.4/7.5 (przycisk GUI / przyszłe narzędzie MCP
  `retman_check` z własnym elicitation, zamknięcie awaryjne, zgoda nigdy przyjmowana od agenta); 8.3
  (testy); 10 (punkt o prywatności); 11 (wiersz 0.1); 12 (otwarte: wyszukiwanie nazwy stacji,
  zastępnik wycinka).
- **PRD**: nowe **N-12** (brak sieci przed potwierdzeniem; jedyny wyjątek W-17) i **W-17**
  (sprawdzenie dostępności na życzenie użytkownika, osobne potwierdzenie, tylko informacyjne; v0.1
  — wdrażane wg decyzji końcowej 1); 7.1 linia zakresu.
- **DECISIONS**: nowy ADR „Sieć dopiero po potwierdzeniu: `preview` offline i sprawdzenie
  dostępności” — zapisuje delegację (decyzje autora 4 + 8), opcje z p. 1, konsekwencje; wiersz indeksu.
- **DEVELOPMENT_STANDARDS** 17.1: kroki „preview (validate_command, test offline pod nagrywającą
  blokadą)” i „check? (czy jest sensowne sprawdzenie wstępne w sieci; tekst uwagi)”.
- **CLAUDE.md** punkt twardego ograniczenia: „Bez sieci przed potwierdzeniem (N-12): narzędzia
  wołamy z siecią dopiero po `plan.confirm()`; wyjątek: `retman.check()` po `plan.confirm_check()`.”
- `docs/USAGE.md` (klawisz `s`), `CHANGELOG.md`, `PROGRESS.md`.

## 7. Testy (offline; `FakeDecisionBackend`; fałszywe narzędzie w `tests/fixtures/dummy_tool`)

1. Bramka rdzenia: `check()` bez `confirm_check()` rzuca i nie woła żadnego handlera;
   `confirm_check()` ≠ `confirm()`; zgoda jednorazowa; `answer`/`change` zerują zgodę i `checks`;
   `from_dict` nigdy nie odtwarza zgody; `check()` czyści `confirmed`; nie powstaje katalog/numer
   wyniku; wyjątek handlera → raport `unknown`; `result.json["checks"]` tylko dla stanu końcowego;
   dziennik `check` dla zatwierdzone / odrzucone / przerwane.
2. Problemy `preview`: ponowne otwarcie obu parametrów kombinacji, każdy pytany raz, odpowiedź →
   podgląd przechodzi; ponowna odpowiedź tą samą wartością wraca do pytania (bez cichego
   wyprowadzenia od nowa); wartości `known` nietknięte → `RetmanError`; nic do ponownego otwarcia →
   `RetmanError` (zakończenie); `confirm()` zablokowane, gdy coś otwarto ponownie.
3. CLI: `s` pokazane tylko z `can_check`; `n`/inne → dziennik `rejected`, handler niewołany; `t` →
   raport wydrukowany, pytanie wraca; bez TTY i `--plan-only` nigdy nie sprawdza; linie `retman log`.
4. Walidacja manifestu: format `check`, `check.notice` obecne dla każdego języka.
5. Testy kontraktowe z prawdziwym narzędziem (`tests/tools/kartograf`): reguły `validate_command`
   powyżej z **0 prób połączenia i bez utworzonych plików** — rozszerzyć `_block_network`, by
   *nagrywał* próby i asertował pustą listę (narzędzie połykające odmowę połączenia inaczej by
   przeszło); mapowanie `check` na **nagranych** dokumentach `kartograf-availability/1` /
   `imgw-plan/1` przez fałszywego klienta; jeden test `live` na narzędzie. CI uruchamia je na
   najstarszej/najnowszej obsługiwanej wersji narzędzi i nocnie na głównej gałęzi narzędzi
   (ARCHITECTURE 3.2.7) — to utrzymuje prawdziwość twierdzeń „offline” przez aktualizacje narzędzi.

## 8. Ryzyka i otwarte zależności

1. **Twierdzenia „offline” mogą dryfować** z wydaniami łatek narzędzi → test 5; jeśli
   `PlanClient` IntegrationStrategy wejdzie, wymusi niezmiennik *strukturalnie* dla wszystkich
   wywołań katalogu (brak czasowników sieciowych), a nagrywająca blokada zostaje siatką dla
   bezpośrednich wywołań biblioteki.
2. **Błędna semantyka „check”**: użycie `check_*` Kartografa (świeżość) tam, gdzie chodzi o
   dostępność, daje „wszystko brakuje”. Handler musi używać `check_availability`/`query` dla
   wysokości; weryfikowane testami na nagranych dokumentach.
3. Dostępność wycinka według indeksu arkuszy jest zastępnikiem dla WCS [WNIOSEK]; ścieżka `check`
   dla ortofotomapy nie uruchamiana live [WNIOSEK]. Jeśli autor adaptera woli, w v0.1 wdrożyć
   `check` tylko dla operacji arkuszowych i BDOT10k.
4. **Rozwiązywanie nazwy stacji w planowaniu** (przykład IMGW „ściągnij opady z poznania”) też musi
   być offline: tylko `find_stations(source="store")`; lista stacji w magazynie istnieje dopiero po
   `build_catalog` (sieć). Zalecany wzorzec: *sieć wypełnia magazyn przez jawną, potwierdzoną
   operację; planowanie czyta magazyn offline*; bez magazynu Retman pyta o kod stacji (gramatyka
   sprawdzana offline). Wyszukiwanie sieciowe w trakcie pytań byłoby drugim krokiem za zgodą z tą
   samą bramką — nieprojektowane tutaj.
5. **Dwie bramki** (`execute`, `check`) muszą pozostać jedynymi punktami wejścia do sieci;
   MCP (0.3)/HTTP (0.4) nigdy nie mogą przyjmować zgody od klienta; `Plan.from_dict` powinien też
   przestać odtwarzać `confirmed` (zasygnalizowane w raporcie MCP).
6. `cache=False` powtarza zapytania do indeksu (sprawdzenie, potem pobranie), dopóki nie wejdzie
   decyzja o wspólnym magazynie/cache. `import kartograf` przesuwa się do planowania dla operacji z
   `preview` (0,44 s ciepły; ~1,2 s zimny wg raportu MCP).
7. Wcześniej istniejąca luka: ani `cli.py`, ani `pipeline.py` nie drukują `result.warnings` (np.
   „GUGiK nie ma danych dla 3 z 12 arkuszy”); sprawdzenie drukuje własne linie, ale ostrzeżenia po
   wykonaniu pozostają w CLI niewidoczne (zob. raport integracji, ryzyko 15).
8. Zależności od decyzji pobocznych, żadna nie blokuje: typ `ctx` i wstrzykiwanie magazynu
   (IntegrationStrategy/ImgwScope; jeśli kontekst nie zostanie przyjęty, usunąć argument),
   `PreviewOutput` (GeometryArea, w tym poleganie na `reopened` dla problemów obszaru), numeracja
   ADR/W/N (integrator), niewypchnięte tagi v0.8.0/v3.0.0.

## Dodatek: odtworzenie dowodów

```python
# guard.py — imported before the tool
import socket
class NetAttempt(Exception): ...
def _deny(*a, **k): raise NetAttempt(repr(a)[:120])
socket.getaddrinfo = socket.create_connection = socket.socket.connect = socket.socket.connect_ex = _deny
```

Uruchomienie: `cd /tmp && uv run --no-project --python 3.12 --with <ścieżka do repozytorium Kartograf> python probe.py`
(IMGWTools: `--with '/tmp/imgw_31e96fa[store]'`). Każda funkcja wymieniona jako „offline” i każda
wymieniona jako „sieć” **bez** znacznika `[docstring, not run]` zachowała się tak, jak opisano:
offline kończyły się lub rzucały własny `ValidationError`/`IMGW*Error` z **zerem** `NetAttempt`;
sieciowe rzucały `NetAttempt`.
