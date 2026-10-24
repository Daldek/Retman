# Plik geometrii (SHP/GPKG) jako obszar w Retmanie na Kartografie 0.8.0

- **Data:** 2026-10-19
- **Zakres:** obszar podany plikiem SHP/GPKG dla czterech operacji Kartografa
  (`download_dem_sheet`, `download_sheet_hierarchy`, `download_elevation_cutout`,
  `download_bdot10k`): kształt wartości, wybór warstwy, podgląd w planie, rodzaj
  `area_geometry`, audyt, wpływ na pliki i dokumenty.
- **Metoda:** wszystko oznaczone „sprawdzone” uruchomiono offline na Kartografie `develop`
  `d7b5369e` (0.8.0) z blokadą gniazd (każda próba sieci rzuca wyjątek); wywołania offline
  niczego nie zapisały na dysk. Pliki testowe: `/tmp/geo/` (SHP z ukośnym wielokątem + `.prj`,
  SHP bez `.prj`, SHP z punktem, SHP w WGS84, GPKG jedno- i dwuwarstwowy zrobione
  `pyogrio`). Nie sprawdzano żadnej ścieżki pobierania z siecią [WNIOSEK z lektury kodu tam,
  gdzie zaznaczono].
- **Status:** decyzja delegowana przez autora (2026-10-19)

## Decyzje końcowe (nadpisują treść raportu)

Źródło: konsolidacja z 2026-10-19 (`impl-plan`, decyzje autora).

1. **Ortofotomapa:** Retman PYTA o kolor (`rgb`/`cir`/`bw` → `"RGB"`/`"CIR"`/`"B/W"`);
   operacja arkuszowa dla produktu `orthophoto` idzie przez własny handler oparty na
   dostawcy (`GugikOrtoProvider(color=…)` + `DownloadManager`), a nie przez
   `download_data`. Skutek dla tego raportu: **dla produktu `orthophoto` geometria (i bbox)
   nie jest przyjmowana** — klasy dostawców biorą wyłącznie kody arkuszy (p. 3.2, ryzyko 10);
   kombinacja „ortofotomapa + plik geometrii” to problem offline w `preview`
   (`PreviewProblem` na parametrze `area`), nie błąd po potwierdzeniu. Uwaga 11 z p. 7
   (brak opcji `color` w `imagery download`) jest tym samym rozstrzygnięta: kolor trafia do
   `GugikOrtoProvider`, a walidacja planu `validate_command("imagery download", …)` biegnie
   bez koloru.
2. Handlery warstwy komend wg konsolidacji: `handler(params, inputs, output_dir, ctx)`;
   operacja deklaruje `calls` i/lub `handler` (co najmniej jedno). Dla geometrii (produkty
   `dem`/`dsm`, wycinek, BDOT10k) bez zmian: `calls` budują `CatalogCall` z mapą opcja → param
   z p. 3.3.
3. `preview` jest OBOWIĄZKOWY, a krok `check` (`s`) wdrażany w v0.1 (raport `check`); brak
   sieci przed potwierdzeniem (N-12) — cały podgląd geometrii (odczyt pliku, obwiednia,
   liczba arkuszy) jest lokalny.
4. Pozostałe decyzje tego raportu (p. 1) obowiązują bez zmian.

## 1. Rekomendacja (decyzje)

1. **Geometria pozostaje wartością `area`**, a nie wejściem (`input`) przestrzeni roboczej
   ani rodzajem (`kind`). Kształt (rozszerza dzisiejszą wartość,
   `retman/extractors/areas.py:273-288`):
   `{"type": "geometry", "path": "<ścieżka bezwzględna>", "layer": "<tabela obiektów GPKG>" | None}`
   — `layer` to `None` dla SHP, napis dla GPKG, i **jest zawsze wybierany jawnie** (W-02).
2. **Wszystkie cztery operacje Kartografa przyjmują `["…", "geometry"]` i przekazują plik
   Kartografowi natywnie** (`geometry=Path`, `layer=`), przez rodzinę
   `download_data` / `download_landcover`. Bez GIS po stronie Retmana, bez nowej zależności.
   Semantyka per operacja — p. 3.2 (różnią się, plan musi to mówić).
3. **Wybór warstwy = Retman pyta**, gdy GPKG ma więcej niż jedną tabelę obiektów (Kartograf
   po cichu bierze pierwszą i emituje tylko komunikat Info, który `validate_command`
   połyka — sprawdzone). Jedna tabela → używana i pokazana w planie. SHP → bez warstwy.
4. **Lista warstw GPKG offline: stdlib `sqlite3` w nowym `retman/core/geometry.py`**
   (to samo jednolinijkowe SQL co w Kartografie, `kartograf/core/geometry.py:252-269`).
   Kartograf ma funkcję offline (`kartograf.core.geometry.resolve_layer`, `:390-427`), ale
   **nie jest publiczna**: `resolve_layer`, `read_feature_bboxes`, `read_source_crs`,
   `LayerChoice` NIE są w `kartograf.__all__` (sprawdzone: `hasattr(kartograf,
   "resolve_layer") == False`). Publiczne są tylko `get_overall_bbox` i
   `find_sheets_for_geometry`. Errata do raportu wpływu (p. 2 „Nowe możliwości”), który
   wymieniał `read_feature_bboxes`/`read_source_crs` jako eksportowane.
5. **Przejrzystość planu przez jeden wspólny hak offline `preview`** (uzgodniony z
   `TwoStepCheck`; ja jestem właścicielem klucza i typu `PreviewOutput`, oni — semantyki
   `problems`). Dla obszarów-geometrii pokazuje obwiednię i, dla operacji arkuszowych,
   **liczbę arkuszy**, liczone publicznymi funkcjami offline Kartografa; ujawnia też własną
   walidację Kartografa sprzed sieci (`kartograf.validate_command`) przed potwierdzeniem.
6. **Nowy rodzaj `area_geometry`** (`.gpkg`, `.shp`, te same walidatory nagłówków co
   `topographic_vector`) — używany teraz do walidacji pliku użytkownika w czasie planu;
   zarezerwowany jako rodzaj *wyjściowy* przyszłych operacji produkujących obszar (łańcuchy
   v0.2). **Wynik BDOT10k (`topographic_vector`) NIE jest źródłem geometrii** (p. 6).
7. **Audyt:** SHA-256 plików geometrii w `result.json` (dziś zapisywana jest tylko
   ścieżka; wejścia dostają sumę kontrolną, parametry obszaru nie).
8. Żadnych nowych kluczy `retman.toml` (analiza N-11 w p. 3.5).

## 2. Dowody

### 2.1 Retman dziś (w połowie gotowy; blokadą był Kartograf 0.7.2)

- `extract_area` już emituje `{"type":"geometry","path":…}` dla `.shp`/`.gpkg`
  (`retman/extractors/areas.py:273-288`); `validate_area` to przyjmuje (`:319-325`);
  ekstraktor ścieżek wymienia `shp|gpkg|geojson|gml|…` (`retman/extractors/paths.py:10`).
- Potok: `_validate_free` sprawdza tylko `is_file()` rozwiązanej ścieżki
  (`pipeline.py:307-310`, tekst `dialog.invalid_geometry`); `_normalize_free` robi ją
  bezwzględną względem `project_dir` (`:313-318`); `_display` drukuje
  `extractors.area.geometry` = „obszar z pliku {path}” (`:222-223`, `i18n/pl.toml:19`);
  kolekcja zachowuje tylko nazwę pliku (`_portable`, `:836-840`).
- Żadna operacja manifestu Kartografa nie przyjmuje geometrii (`accepts` =
  `["sheet"]`, `["sheet"]`, `["bbox"]`, `["teryt","bbox","sheet"]`,
  `retman/tools/kartograf/manifest.py:23,58,107,144`); `retman/tools/kartograf/pl.toml:113`
  wręcz mówi, że geometria jest odrzucana, bo API jej nie miało. Filtrowanie `accepts`:
  `pipeline.py:252-274`, `:285-289`.
- Rodzaje: `kinds.py:18-23` ma `dem, dsm, orthophoto, topographic_vector` (wynik BDOT10k) —
  **brak rodzaju dla wektora obszaru zainteresowania**.
- `inputs` są obowiązkowe per operacja (`pipeline.py:569-588`); nie ma alternatywy „wejście
  ALBO parametr”, więc wejście-rodzaj nie wyrazi „arkusz | bbox | geometria”. Wybór pliku z
  przestrzeni roboczej (`#N`, `find_by_kind`, `workspace.py:66-93`) nie nadaje się więc dla
  parametru obszaru w v0.1. Ścieżka do pliku w `retman-output/…` już działa jako obszar
  (względem katalogu projektu); nie działają tylko odwołania `#N`.
- Luka audytu: `execute` liczy sumy dla `plan.inputs` (`pipeline.py:943-949`) i wyjść
  (`:972-981`), nie dla plików obszaru.
- Istniejący test przypina stary kształt wartości: `tests/core/test_pipeline.py:205-217`
  (`{"type":"geometry","path":…}` z 16-bajtowym fałszywym GPKG).

### 2.2 Kartograf 0.8.0 (sprawdzone)

- Publiczne: `get_overall_bbox(filepath: Path, layer=None, target_crs="EPSG:2180") -> BBox`
  (`core/geometry.py:570-608`, suma obwiedni obiektów; CRS z `.prj` / srs GPKG, transformacja
  pyproj; brak obiektów → `ValidationError`). `find_sheets_for_geometry(filepath: Path,
  target_scale, layer=None, *, sheet_system) -> list[str]` (`:611-655`). Komenda
  `find_sheets(geometry=, layer=, scale=, sheet_system=)` (`sheet_info.py:349-436`).
  **Musi być `Path`**, nie `str` (CHANGELOG Hydrografa, l. 48, dokumentuje awarię).
- `geometry=`/`layer=` przyjmują: `download_data`, `check_data`, `download_landcover`,
  `check_landcover`, `download_soil`, `calculate_hsg` (sygnatury przez `inspect`).
  **`download_pl_cutout(*, bbox, horizontal_crs, output_dir, vertical_crs, product, …)` NIE ma
  `geometry`** — docstring każe podać obwiednię jako `bbox` (`download/cutout.py:638-640`);
  wycinek z geometrią to `download_data(cutout=True, geometry=…)` (`download/data.py:891-912`
  → `_dispatch_area` → `_download_pl_geometry` `:1235-1279` → `_download_pl_cutout`
  `:1752-1816`).
- **Semantyka wycinka:** jeden GeoTIFF **całej obwiedni wszystkich obiektów warstwy**; bez
  maskowania do wieloboku; nodata tylko poza lądem Polski (maska PRG) — pomoc katalogu:
  „w trybie --geometry obejmuje CALA obwiednie geometrii”; ADR-027
  `docs/DECISIONS.md:1357-1359` (historyczny wycinek arkuszowy, ta sama reguła);
  `cutout.py:618-624`. Obwiednie punktowe/zerowej powierzchni są odrzucane dla wycinka
  (`options.py:976-989`, sprawdzone).
- **Semantyka arkuszy:** `find_sheets_for_geometry` działa per **obwiednia obiektu** i łączy
  arkusze (`:645-655`), więc ukośny wielokąt daje arkusze całej swojej obwiedni. Sprawdzone:
  ukośny wielokąt, obwiednia 12,5 × 11,0 km → 42 arkusze po geometrii == 42 arkusze po jego
  bbox (`find_sheets_for_bbox`). Zbiór to „arkusze obwiedni obiektów”, niekoniecznie arkusze
  dotykane przez sam wielokąt (cienki ukośny dotyka mniej; dokładnej liczby nie liczono).
- **Semantyka BDOT10k:** `download_landcover(geometry=)` → `geometry_envelope_2180`
  (`landcover/manager.py:1300-1301`) → powiaty przez PRG WFS (`providers/pl/prg.py:341-369`,
  **sieć**) → całe paczki powiatów; żądania obszarowe ograniczone do 100 plików / 10 GB
  (CHANGELOG 0.8.0, test E2E 2026-10-19). Geometria punktowa jest poprawna i wybiera
  powiat, który ją zawiera.
- Tryb arkuszowy `download_data(geometry=)` wymaga jawnych `country` i `sheet_system`
  (pomoc `--sheet-system`; sprawdzone błędy). PL-1992 → tylko 1:10000 i `scale` jest
  **zabronione**; PL-2000 → `scale` ∈ {1:5000, 1:2000, 1:1000, 1:500}, `1:10000` odrzucone
  (sprawdzone: `1992+1:10000`, `1992+1:2000`, `2000+1:10000` = `ValidationError`;
  `2000+1:500` OK). Zatem `sheet_system` jest **funkcją docelowej skali** dla obszarów
  geometrycznych.
- Wycinek z geometrią: `country` wymagane, `horizontal_crs` wymagane, `sheet_system` można
  pominąć (tylko 1992), rozdzielczość tylko 1 m (można pominąć) — sprawdzone
  `validate_command`.
- Brak limitu liczby arkuszy w `download_data` w trybie arkuszowym (grep `download/data.py`
  nie znalazł limitów; limit 100 plików / 10 GB dotyczy land cover) [WNIOSEK: nie
  wykonywano na żywo]. Dlatego plan musi pokazywać liczbę.
- **Walidacja offline sprzed sieci istnieje i jest publiczna:**
  `kartograf.validate_command(command, options, *, output_dir=None)`
  (`commands.py:185-…`, w `__all__`): „bez sieci i bez zapisu… Plik geometrii jest
  czytany, tak jak czyta go funkcja”. Sprawdzone, że wyłapuje: brak pliku; SHP bez `.prj`
  („Brak pliku .prj shapefile”); nieznaną warstwę GPKG (wymienia dostępne); zerową
  powierzchnię dla wycinka; geometrię poza PL dla `country="pl"` (komunikat z obwiednią w
  EPSG:4326 i wskazówką CRS); brak `country`/`sheet_system`/`scale`/`horizontal_crs`;
  niepoprawne kombinacje skala/system. **Niewyłapane** dla BDOT10k: geometria daleko poza PL
  przechodzi (`far.shp` OK) i pada dopiero po zapytaniu do PRG w sieci. Po cichu też
  przyjmuje `layer=` przy SHP oraz wielowarstwowy GPKG bez `layer`.
- Sprawdzony przebieg offline z blokadą gniazd: `validate_command` ×2, `get_overall_bbox`,
  `find_sheets_for_geometry` (42 arkusze 1992/1:10000; 117 arkuszy 2000/1:2000 dla tego
  samego wielokąta) — razem ≈ 1,3 s wraz z interpreterem i importem Kartografa.
- Strona Hydrografa (łańcuchy v0.2): ARCHITECTURE 3.2.6 deklaruje `catchment_characteristics`
  jako GeoJSON; Kartograf czyta **tylko `.shp`/`.gpkg`** (`core/geometry.py:23`;
  nieobsługiwane rozszerzenie → `ValidationError`). Własny `backend/scripts/bootstrap.py:268`
  Hydrografa niesie tę samą uwagę. Czy Hydrograf potrafi zapisać granicę GPKG/SHP: nie
  sprawdzano [WNIOSEK: nie].

## 3. Dokładny kontrakt

### 3.1 Wartość obszaru, lista warstw i pytanie o warstwę

```
{"type": "geometry", "path": str (absolute, normalized by _normalize_free),
 "layer": str | None}      # key absent = not yet decided
```

Reguły (jeden pomocnik `Retman._complete_geometry(plan, operation, spec, value) -> Question | None`,
wołany z `_extract_param` tuż przed `_validate_free` oraz z gałęzi `known` w `_populate`):

| Plik | Reguła |
|---|---|
| `.shp` | `layer = None`; do Kartografa jako `layer=None` (nigdy warstwa dla SHP) |
| `.gpkg`, 1 tabela obiektów | `layer = <ta nazwa>`, pokazana w planie |
| `.gpkg`, >1 tabel obiektów, brak `layer` | `Question(name="area", type="choice", text=dialog.geometry_layer, options=[Option(str(i), <nazwa warstwy>, {**value, "layer": name})])`; odpowiedź numerem wykorzystuje istniejącą ścieżkę `selection.value` w `answer_plan` (`pipeline.py:606-611`) → `_validate_free` → `_normalize_free` → `_set_param`, bez nowego typu pytania |
| `.gpkg`, 0 tabel obiektów / nieczytelny / nie SQLite | pytanie z `error=dialog.geometry_unreadable` (`{error}`) |
| `plan.known["area"]` (API Pythona), wielowarstwowy bez `layer` | `raise RetmanError(dialog.geometry_layer_required)` — wartości `known` są stałe, nigdy pytane |

`plan.change("area")` ponownie otwiera pytanie o obszar i porzuca warstwę, bo warstwa jest
częścią wartości (zmiana `depends_on` niepotrzebna). Wpisanie nazwy warstwy w odpowiedzi: w
v0.1 nieobsługiwane (tylko numery, jak w każdym pytaniu z listą); zła odpowiedź pyta
ponownie z listą (opcjonalnie później: dopasowanie dokładnej etykiety ograniczone do tego
pytania).

Nowy `retman/core/geometry.py`:

```python
def geometry_layers(path: Path) -> tuple[str, ...]:
    """Feature tables of a GPKG in file order; () for SHP. stdlib only, read-only."""
    # sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    # SELECT table_name FROM gpkg_contents WHERE data_type = 'features'   (same text as Kartograf, no ORDER BY)
    # sqlite3.Error -> raise KindValidationError-like GeometryFileError(path, reason)
```

Sprawdzone ze stdlib: `('zlewnie','dzialki')` / `('obszar',)`; plik niebędący bazą o nazwie
`.gpkg` rzuca `sqlite3.DatabaseError`. Łapać `sqlite3.Error`.

Gałąź geometrii w `_validate_free` po zmianie: rozwiąż ścieżkę →
`validate_file("area_geometry", path)` (rozszerzenie + nagłówek; `KindValidationError`/`OSError`
mapować na `dialog.invalid_file`) → jeśli wartość ma `layer`: `.gpkg` ⇒
`layer in geometry_layers(path)`, `.shp` ⇒ `layer is None`. `validate_area`
(`areas.py:319-325`) dodatkowo wymaga, by `layer` było `None` albo niepustym `str`.

Drobna poprawka ekstraktora: `extract_area` po cichu gubi `.geojson`/`.gml` (obszar wygląda
wtedy na „brakujący”). Emitować odczyt geometrii także dla `.geojson`/`.gml`, aby osiągalny
był istniejący `extractors.errors.invalid_geometry` („Geometria musi być plikiem SHP lub
GPKG”) (W-02: powiedzieć użytkownikowi dlaczego, nie ignorować). Zaktualizować komentarz
nagłówka „Copied from Kartograf 0.7.2” (`areas.py:10`) na 0.8.0.

### 3.2 Macierz per operacja (manifest: zmienia się tylko `accepts`; bez nowych parametrów)

`country="pl"` i system arkuszy są stałe z operacji / wyprowadzone z własnego wyboru skali
przez użytkownika (p. 3.5), więc bez dodatkowych pytań.

| Operacja | `accepts` | Semantyka dla geometrii | Wywołanie Kartografa (przez `download_data`/`download_landcover`; `Path`, jawne `layer`) | Zdanie w planie (`geometry_note` per operacja) |
|---|---|---|---|---|
| `download_dem_sheet` | `["sheet","geometry"]` | arkusze NMT 1:10000 PL-1992, których komórka przecina **obwiednię co najmniej jednego obiektu** warstwy | `download_data(product="nmt", geometry=, layer=, country="pl", sheet_system="1992", vertical_crs=, resolution=, output_dir=…)` | „arkusze 1:10000 (PL-1992) przecinające obwiednię któregokolwiek obiektu warstwy; kształt wieloboku nie jest uwzględniany” |
| `download_sheet_hierarchy` | `["sheet","geometry"]` | to samo dla `target_scale`; `scale_10000` ⇒ `sheet_system="1992"` i **bez** `scale`; `scale_5000/2000/1000/500` ⇒ `sheet_system="2000"`, `scale="1:N"`. Produkt dem/dsm/orthophoto → `nmt`/`nmpt`/`orto` | `download_data(product=…, geometry=, layer=, country="pl", sheet_system=…, scale=…, …)` | jak wyżej, z systemem/skalą |
| `download_elevation_cutout` | `["bbox","geometry"]` | JEDEN GeoTIFF **obwiedni wszystkich obiektów** warstwy; **bez przycinania do wieloboku**; nodata tylko poza lądem Polski | `download_data(product="nmt"/"nmpt", geometry=, layer=, country="pl", cutout=True, horizontal_crs=target_crs, vertical_crs=…, …)` | „jeden prostokąt obejmujący wszystkie obiekty warstwy; nie przycina do wieloboku; poza lądem Polski brak danych” |
| `download_bdot10k` | `["teryt","bbox","sheet","geometry"]` | **każdy powiat, którego wielokąt PRG przecina obwiednię**, każdy jako cała paczka, bez przycinania; lista powiatów znana dopiero po zapytaniu do sieci | `download_landcover(product="bdot10k", geometry=, layer=, format=…, output_dir=…)` | „pełne pakiety wszystkich powiatów przecinających obwiednię obszaru; lista powiatów dopiero po zapytaniu do PRG (sieć, po potwierdzeniu)” |

Dlaczego `download_dem_sheet` też przyjmuje geometrię: nic nie kosztuje (zero parametrów,
tylko gałąź handlera) i unika ślepego zaułka, w którym rozpoznawacz operacji wybiera „NMT dla
arkusza” dla „NMT dla obszaru z pliku X”, a filtr `accepts` (`pipeline.py:252-274`) odrzuca
plik i pyta o kod arkusza. To dokładnie `download_sheet_hierarchy` z `scale_10000`.

**Ortofotomapa (decyzja końcowa):** dla produktu `orthophoto` w `download_sheet_hierarchy`
geometria nie jest przyjmowana (handler oparty na dostawcy, tylko kody arkuszy) — problem
offline w `preview`, patrz „Decyzje końcowe”.

Kontrakt handlera: gałąź geometrii to mała funkcja mapująca współdzielona przez handler i
`preview` (`_geometry_request(params) -> (command_id, options_dict)`, identyfikatory komend
`"elevation download"`, `"imagery download"`, `"landcover download"`; opcje są snake_case =
nazwy argumentów API, identyczne dla `run_command`/`validate_command`/`download_data`). Jeśli
decyzja siostrzana wybiera katalog (`run_command`) dla handlerów, geometria działa bez zmian.
**Jeśli wybierze klasy dostawców (`DownloadManager`/`GugikProvider`) dla operacji
arkuszowych, geometria NIE jest tam wspierana** (klasy biorą tylko kody arkuszy); jedyną
alternatywą byłaby pętla `find_sheets_for_geometry` po stronie Retmana — odradzam. Handler
wycinka: `DataReport` nie ma `masked_pixels`/`all_nodata`; mapować komunikat `ALL_NODATA`
(`DataReport.notices[i].code`) na istniejące ostrzeżenie; `masked_pixels` zostaje w sidecarze
wersji (`cutout.py:340-371`). Zapasowa ścieżka tylko dla wycinka (udokumentowana przez
Kartografa, `cutout.py:638-640`): `get_overall_bbox(path, layer, "EPSG:2180")` +
`download_pl_cutout(bbox=…, parent_request=kartograf.parent_request_for(bbox, ("PL",)))`;
traci walidację geometrii Kartografa, którą `preview` dodaje z powrotem.

### 3.3 Hak `preview` (offline, w czasie planu)

`retman/registry/manifest.py`:

```python
class PreviewRow(TypedDict):        # text in tool pl.toml [preview.<key>] label= / value=
    key: str
    args: dict[str, str]
class PreviewProblem(TypedDict):    # semantics: TwoStepCheck (params reopened, plan not confirmable)
    params: list[str]
    key: str                        # text in [problems]
    args: dict[str, str]
class PreviewOutput(TypedDict):
    values: dict[str, Any]          # JSON, audit only → result.json["preview"]
    rows: list[PreviewRow]          # extra plan rows, marker "podgląd"
    problems: list[PreviewProblem]
# OperationSpec: preview: NotRequired[str]   # "module:function", same format as handler (":" required)
# signature: (params: dict[str, Any], context: Context) -> PreviewOutput ; OFFLINE ; lazy import ; called when all params are set
# `context` = the SAME read-only object that handler(params, inputs, output_dir, context) receives (type/injection decided by the store/config decision; needed so IMGWTools preview can read the store). The Kartograf geometry preview ignores it.
```

Implementacja Kartografa (`retman/tools/kartograf/handlers.py`, jedna funkcja na operację
albo jedna wspólna). **Połowa „problems” działa dla KAŻDEGO typu obszaru**
(arkusz/bbox/teryt/geometria) i dla każdej operacji Kartografa, bo reguły kombinacji (np.
5 m + KRON86, rozdzielczość wycinka, NMPT bez rozdzielczości) nie zależą od obszaru;
**wiersze/wartości poniżej dotyczą wyłącznie geometrii** (obszar niegeometryczny → puste
`rows`, `values`).

1. (Wykonuje adapter, patrz „Zazębienie” niżej; zostawione tu dla reguł mapowania.)
   `kartograf.validate_command(cmd, options, output_dir=None)` dla każdego wywołania;
   `kartograf.ValidationError` → problem
   `{"params": <zmapowane>, "key": "tool_rejected", "args": {"detail": str(err)}}`. Mapowanie
   czyta ZARÓWNO `err.option`, jak i `err.options` (krotka, np. `('resolution','vertical_crs')`)
   i kieruje przez mapę opcja → param budowniczego wywołań: `geometry`/`layer`/`bbox`/
   `bbox_crs`/`sheet`/`teryt` → `["area"]`; `vertical_crs`, `resolution`,
   `horizontal_crs`(→`target_crs`), `scale`(→`target_scale`), `product`, `format` → param
   manifestu o tym samym znaczeniu. **Bez zapasowego „wszystkie parametry wyboru”** (zapętliłoby
   się na odrzuceniu, którego żadna odpowiedź użytkownika nie naprawi): jeśli nic nie
   kieruje (opcja stała w operacji albo dryf narzędzia), adapter rzuca programistyczny
   `ToolDriftError(RetmanError)` wskazujący na `retman doctor` / `retman-scaffold --check`
   (patrz `local://research-check.md` 4.9). Surowy tekst Kartografa w `detail`.
2. `envelope = kartograf.get_overall_bbox(Path(path), layer=layer, target_crs="EPSG:2180")` →
   wiersz `envelope` („12,5 × 11,0 km, E 360000–372500, N 500000–511000, EPSG:2180”);
   wartości `{"envelope": [min_x, min_y, max_x, max_y, "EPSG:2180"]}`.
3. Operacje arkuszowe:
   `n = len(kartograf.find_sheets_for_geometry(Path(path), scale, layer, sheet_system=system))`
   → wiersz `sheet_count` („42 arkusze 1:10000, PL-1992”) i `sheet_system` (wartość
   wyprowadzona, pokazana, nie pytana); `n == 0` → problem `no_sheets`.
4. BDOT10k: po (2) sprawdzić obwiednię z konserwatywnymi zakresami Polski, już istniejącymi w
   `areas.py:71-76` → problem `outside_poland` (istniejący tekst
   `extractors.errors.outside_poland`), bo `validate_command` tego nie wyłapuje.
5. **Ortofotomapa (decyzja końcowa):** produkt `orthophoto` + obszar `geometry` (lub `bbox`) →
   problem na `area` (handler dostawcy bierze tylko kody arkuszy).

Koszt (zmierzony przez TwoStepCheck): `import kartograf` ≈ 0,44 s raz na proces (ciepły),
`validate_command` < 1 ms na wywołanie, więc połowę „problems” uruchamiać przy każdym
wywołaniu preview; dodatki geometrii (odczyt pliku, obwiednia, liczba arkuszy) kosztują ms
dla małych plików i są liczone ponownie tylko, gdy zmieni się obszar/warstwa/skala
(cache po tych wartościach).

**Zazębienie z `local://research-integration.md` (nazwy uzgodnione z IntegrationStrategy;
ich zapis wygrywa przy konfliktach):**

- `context` to `ToolContext` (zamrożona dataclass, `retman/adapters/catalog.py`: tool,
  settings, store_dir, project_dir, output_dir (None podczas podglądu), inputs, client).
  Sygnatury: `handler(params, inputs, output_dir, ctx)`, `preview(params, ctx)`;
  `ctx.client` to `PlanClient` (walidacja/command_line/zapytania offline) w czasie podglądu.
- Mój `_geometry_request(params) -> (command_id, options)` JEST ich czystym budowniczym
  per operacja `calls(params, ctx) -> list[CatalogCall]`; `CatalogCall.params` mapuje opcję
  narzędzia → param Retmana dla kierowania błędów, dla geometrii:
  `{"geometry": "area", "layer": "area", "sheet_system": "target_scale", "scale": "target_scale"}`.
  Postać JSON opcji: `geometry` = str ścieżka, `layer` = str (pominięte dla SHP),
  `country="pl"`; handler i preview wołają tego samego budowniczego.
- Punkt 1 wyżej (ogólne `validate_command` → problemy, mapowanie option/options) wykonuje
  `preview_operation()` ADAPTERA dla każdego wywołania operacji (`ToolError(option=…)` →
  `PreviewProblem(params=[zmapowane], key="tool_rejected", args={"detail": …})`), a nie
  każda operacja osobno. Funkcja `preview` geometrii Kartografa dodaje więc tylko
  wiersze/wartości i dodatkowe problemy: `envelope`, `sheet_count`/`sheet_system`,
  `no_sheets`, `outside_poland` (BDOT10k). `get_overall_bbox` / `find_sheets_for_geometry`
  wołane bezpośrednio (publiczne typowane pomocniki, argument `Path`).
- **Semantyka ponownego otwarcia (kontrakt TwoStepCheck):** problem na `area` (brak `.prj`,
  zerowa powierzchnia, poza PL, zła warstwa) jest obsługiwany przez rdzeń przez
  `Plan.reopened[param] = przetłumaczony błąd`: `_populate` emituje pytanie bez ponownego
  wyprowadzania wartości z `plan.command`; odpowiedź zdejmuje wpis (źródło `user`). Hak
  tylko zwraca problemy i nigdy nie zdejmuje wartości. Dla geometrii odpowiedź na to pytanie
  idzie zwykłą ścieżką obszaru (`_extract_param`/`answer_plan` → `_complete_geometry` →
  `_validate_free`), więc poprawiona ścieżka albo numer warstwy czyści problem; pytanie o
  warstwę z p. 3.1 jest niezależne od `reopened` (powstaje, gdy brakuje warstwy, nie z
  problemu haka).

### 3.4 Wyświetlanie planu i teksty (polskie, w `pl.toml`)

- Rdzeń `retman/i18n/pl.toml`: `extractors.area.geometry_layer = "obszar z pliku {path}, warstwa „{layer}”"`
  (gdy `layer` ustawione; `geometry` zostaje dla SHP); `dialog.geometry_layer = "Która warstwa pliku {file} wyznacza obszar?"`;
  `dialog.geometry_unreadable`; `dialog.geometry_layer_required`.
- Narzędzie `retman/tools/kartograf/pl.toml`: per operacja
  `operations.<op>.params.area.geometry_note` (teksty z macierzy wyżej, klucz opcjonalny);
  `_display` (`pipeline.py:211-236`) dokleja je do wyświetlenia geometrii; `label`/
  `question`/`help` obszaru przepisane ogólnie („Obszar …”, usunąć zdanie z `pl.toml:113`,
  że geometria jest odrzucana); `[preview.envelope]`, `[preview.sheet_count]`,
  `[preview.sheet_system]`, `[problems.*]`. Pełny kod: `retman/tools/kartograf/pl.toml`
  (wdrożony).
- Przykładowy plan (wycinek):

```
Plan:
  Operacja:   Wycinek NMT/NMPT z WCS GUGiK
  Obszar:     obszar z pliku zlewnie.gpkg, warstwa „dzialki” (jeden prostokąt obejmujący wszystkie obiekty warstwy; nie przycina do wieloboku)
  Obwiednia:  12,5 × 11,0 km (EPSG:2180: E 360000–372500, N 500000–511000)   ← podgląd, bez sieci
  …
```

  (operacja arkuszowa: `Arkusze: 42 × 1:10000 (PL-1992) — arkusze przecinające obwiednię obiektów  ← podgląd, bez sieci`).

### 3.5 Konfiguracja / N-11 / W-05 / N-03 / N-10

- **N-11:** bez nowych kluczy. Jedyne stałe wartości to `country="pl"` (tożsamość operacji
  GUGiK; operacja czeska byłaby osobną operacją) oraz `scale_10000→1992`, pozostałe→`2000`
  (opublikowana reguła Kartografa, sprawdzona wyżej, i pokazana w planie jako wiersz
  `sheet_system`). Żadna nie jest wartością domyślną pominiętego wyboru użytkownika. Warstwa
  nigdy nie jest domyślna.
- **W-05:** nic w tym projekcie nie wykonuje się bez `plan.confirm()`; `preview` jest offline
  i tylko do odczytu; sieć startuje dopiero po potwierdzeniu (decyzja autora 4 spełniona:
  odczyt/walidacja geometrii/liczba arkuszy są lokalne).
- **N-03:** tylko publiczne API (`validate_command`, `get_overall_bbox`,
  `find_sheets_for_geometry`, `download_data`, `download_landcover`); listowanie `sqlite3` ze
  stdlib to własny kod Retmana.
- **N-10 / zależności:** żadnych dodanych. Kartograf już zależy od pyshp/pyogrio/pyproj; rdzeń
  Retmana zostaje stdlib + klient HTTP.

### 3.6 Rodzaj i audyt

- `retman/kinds.py`: `"area_geometry": Kind("area_geometry", (".gpkg", ".shp"))` —
  istniejące gałęzie w `validate_file` (`:51-56`) już walidują oba nagłówki. Wiersz w tabeli
  ARCHITECTURE 3.2.6.
- `execute`: dla wartości geometrii dodać do `params_audit[name]`
  `{"files": {"<nazwa>": "<sha256>", …}}` — dla SHP istniejące członki
  `.shp/.shx/.dbf/.prj`, dla GPKG jeden plik; pomocnik `Workspace.describe_geometry(path)`
  obok `describe_input` (`workspace.py:95-105`). Zapisywane są też `values` podglądu.
- Kolekcja (`_portable`, `pipeline.py:836-840`) zachowuje nazwę pliku i nazwę warstwy;
  nazwę warstwy traktować jak nazwę pliku (uwaga o prywatności w ARCHITECTURE 10).

## 4. Wpływ na pliki Retmana

- `retman/extractors/areas.py`: komentarz nagłówka (0.8.0); odczyt geometrii dla
  `.geojson`/`.gml`; `validate_area` sprawdza `layer`.
- `retman/kinds.py`: rodzaj `area_geometry`.
- `retman/core/geometry.py` (nowy): `geometry_layers`, typ błędu.
- `retman/core/pipeline.py`: `_complete_geometry` (+ miejsca wywołania w `_extract_param` i
  gałęzi `known` w `_populate`); gałąź geometrii `_validate_free` (`:307-310`); gałąź
  geometrii `_display` (`:222-223`) z warstwą i uwagą; suma kontrolna audytu w `execute`
  (`:933-941`); miejsce wywołania preview (wspólne z TwoStepCheck).
- `retman/registry/manifest.py`: `OperationSpec.preview`, typy `PreviewOutput`;
  `validate_manifest` sprawdza format napisu handlera; aktualizacja docstringu `accepts`
  (`:21-22`).
- `retman/adapters/manifest_adapter.py`: `preview_operation(operation, params, context) ->
  PreviewOutput` (leniwy import, jak `execute_operation`).
- `retman/core/workspace.py`: `describe_geometry`.
- `retman/tools/kartograf/manifest.py`: `accepts` czterech operacji, klucz `preview`;
  `handlers.py`: gałęzie geometrii + `_geometry_request` + `preview_*`; `pl.toml` wg p. 3.4.
- `retman/i18n/pl.toml`: cztery nowe klucze.
- Testy: zaktualizować `tests/core/test_pipeline.py:205-217` (użyć prawdziwego minimalnego
  GPKG utworzonego `sqlite3` ze stdlib: tabela `gpkg_contents`; wartość ma teraz `"layer"`);
  nowe: `geometry_layers` (jedna/wiele/brak/nie-baza/SHP); potok: pytanie przy wielu
  warstwach, automat przy jednej, SHP `None`, `known` bez warstwy rzuca, `change("area")`
  porzuca warstwę, ścieżka względna; `tests/tools/kartograf`: preview z prawdziwymi
  fixture'ami SHP/GPKG zbudowanymi z zależności Kartografa (pyshp, pyogrio) — liczba
  arkuszy równa `find_sheets_for_geometry`, problemy dla zerowej powierzchni / poza PL /
  brak `.prj` / zła warstwa, blokada gniazd dowodząca braku sieci; **test dryfu**: każda
  warstwa z `geometry_layers` jest akceptowana, a obca nazwa odrzucana przez
  `kartograf.get_overall_bbox(layer=)` (zachowanie publiczne, bez wnętrzności); test sumy
  kontrolnej audytu. `retman/eval/commands.jsonl`: ≥ 5 poleceń z geometrią wg ARCHITECTURE 13.1
  pkt 10 (w tym wielowarstwowy GPKG, odrzucenie `.geojson`, sformułowanie „wielobok nie jest
  przycinany”).

## 5. Zmiany w dokumentacji

- **ARCHITECTURE:** 3.2.4 (kształt wartości obszaru; `preview` obok handlera); 3.2.6 (rodzaj
  `area_geometry`; uwaga, że `topographic_vector` to dane, nie obszar); 4.1/4.3 (tabela pól
  operacji: `preview`; przykład `accepts` zawiera teraz geometrię dla czterech operacji);
  5.3 (obszar z pliku; ścieżka w `retman-output/` działa, odwołanie `#N` odłożone do v0.2);
  6.1 tabela (wiersze: GPKG z kilkoma warstwami → pytać; nieczytelny plik → pytać ponownie);
  6.3 (przykład planu z wierszami podglądu i uwagą „nie przycina”); 10 (odczyt pliku
  użytkownika tylko do odczytu; nazwa warstwy w kolekcji; audyt sum kontrolnych); 12 (nowa
  otwarta kwestia: obszar z GeoJSON Hydrografa, p. 6); 3.1 lista modułów (`core/geometry.py`).
- **PRD:** 7.2 tabela, wiersze 170–172 — arkusze NMT/NMPT/ortofotomapy i BDOT10k przyjmują
  „plik z geometrią”; bez nowych pozycji W-/N-.
- **DECISIONS:** jeden nowy ADR „Plik geometrii jako obszar (Kartograf 0.8.0)” zapisujący, że
  wynika z delegacji tej kwestii przez autora 2026-10-19 (decyzja autora 8); errata do
  ADR-001 (geometria była w decydowanych formach obszaru, ale zablokowana przez 0.7.2 — teraz
  wdrożona dla czterech operacji) i ADR-004 (nowy rodzaj).
- `docs/USAGE.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md` (zamknąć pozycję backlogu „Plik
  geometrii jako obszar”, PROGRESS.md:399-401), `README.md`, jeśli wymienia formy obszaru.

## 6. Łańcuchy (v0.2) i inne narzędzia

- **Wynik BDOT10k jako geometria: nie.** Paczka powiatu BDOT10k to dane (kilkadziesiąt
  tabel na powiat; domyślna `layer` byłaby bez sensu); obszar, który pokrywa, to powiat =
  TERYT, już typ obszaru. Jawna ścieżka do pliku nadal działa.
- **Zlewnia z Hydrografa:** jej deklarowany rodzaj to GeoJSON (ARCHITECTURE:301), a
  Kartograf nie czyta GeoJSON. Dwie opcje, decyzja przy v0.2:
  (a) adapter Hydrografa zapisuje też granicę GPKG/SHP i deklaruje ją jako wyjście
  `area_geometry` — wtedy parametr obszaru zyskuje rozwiązywanie `#N`: jeśli polecenie ma
  odwołanie do wyniku i `geometry ∈ accepts`, szukać `workspace.find_by_kind("area_geometry")`
  (ponownie używając `_input_question`), wartość
  `{"type":"geometry","path":…,"layer":…,"number":N}` (opcjonalny klucz `number` zachowuje
  zgodność kształtu v0.1 w przód; wyświetlenie „#3: zlewnia.gpkg”);
  (b) jeśli Hydrograf nie umie zapisać GPKG/SHP, Retman liczy obwiednię WGS84 z GeoJSON
  samym `json` (bez zależności GIS) i przekazuje obszar `bbox` (różni się od `geometry`
  tylko dla wyboru arkuszy przy wielu obiektach). Konwerter wymagający GDAL/fiona jest
  odrzucony (bez ciężkich zależności).
- Dane/`country` czeskie: projekt geometrii jest agnostyczny wobec kraju (`country="pl"` dziś);
  operacja CZ dodaje własne `country`.

## 7. Ryzyka i rzeczy niesprawdzone

1. **Oczekiwanie obwiednia vs wielobok.** Użytkownicy mogą oczekiwać przycinania do
   wieloboku; Kartograf nigdy go nie maskuje (wycinek), wybiera arkusze po obwiedni obiektu
   (sprawdzone 42 = 42), a BDOT10k dostarcza całe powiaty. Łagodzenie: `geometry_note` +
   wiersze podglądu; to główne ryzyko UX.
2. **Ślepe plamy rozmiaru:** brak limitu liczby arkuszy w Kartografie (tylko grep); duży
   wielobok może znaczyć tysiące arkuszy 1 m. Strażnikiem jest liczba w podglądzie;
   konfigurowalna odmowa `max_sheets` możliwa później, nie była wymagana.
3. **Ścieżki na żywo nieuruchomione** (brak sieci): `download_data(geometry=…)` dla
   arkuszy, wycinka i `download_landcover(geometry=…)` zwalidowane offline i wyczytane z
   kodu, niewykonane [WNIOSEK]; jeden test live na operację przed wydaniem (DEV-10.1
   `live`).
4. `validate_command` nie odrzuca obszarów BDOT10k poza PL (sprawdzone) → własna kontrola
   zakresu obwiedni w podglądzie.
5. **Dryf listowania warstw:** Retman kopiuje jednolinijkowe SQL Kartografa; pokryte testem
   dryfu na zachowaniu publicznym. Opcjonalna prośba do upstreamu (autor jest właścicielem
   obu repozytoriów; nie edytować z Retmana): wyeksportować `resolve_layer` w
   `kartograf.__all__`, potem zastąpić nim `geometry_layers`.
6. GPKG z wieloma warstwami (np. paczka BDOT10k podana przez pomyłkę, ~60 tabel) daje długą
   numerowaną listę; akceptowalne (sygnalizuje złe wejście).
7. `Path` vs `str`: zawsze przekazywać `Path` do `find_sheets_for_geometry`/`get_overall_bbox`
   (precedens awarii w Hydrografie).
8. Podgląd importuje Kartografa podczas planowania (≈ 0,6 s); tylko dla obszarów
   geometrycznych; operacje niezainstalowanych narzędzi i tak są niedostępne, więc nowego
   trybu awarii brak.
9. GPKG w trybie WAL na nośniku tylko do odczytu może nie otworzyć się w `mode=ro` —
   zgłaszane jako pytanie „nieczytelny”; [WNIOSEK] rzadkie.
10. Sprzężenie: projekt zakłada, że handlery arkuszy/wycinka/BDOT10k używają rodziny
    `download_data`/`download_landcover` (funkcja biblioteczna albo jej komenda katalogu).
    Ścieżka klas dostawców nie przyjmie geometrii (3.2) — dotyczy to teraz ortofotomapy
    (decyzja końcowa).
11. Uwaga poboczna dla właściciela operacji arkuszowych: `imagery download` nie ma opcji
    `color` (`validate_command`: „nieznana opcja 'color'”); wymóg `GugikOrtoProvider(color=)` z
    raportu wpływu dotyczy tylko ścieżki klas dostawców — a ta jest teraz użyta dla
    ortofotomapy (decyzja końcowa).
