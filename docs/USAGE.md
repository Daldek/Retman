# Working with Retman

A user guide: how to set up Retman, how to issue commands, answer questions, approve plans and
find results — in the terminal and from Python.

**Status:** before v0.1.0. Ten Kartograf 0.8.0 operations, 19 Obserwator 3.0.0 (formerly IMGWTools)
operations and nine Hydrolog 1.0 operations, 38 in all, work (section 9) with a decision model
compatible with the OpenAI API (e.g. LM Studio); the basal backend does not exist yet.

> **About the examples.** The runs below were recorded on Retman 0.1.0.dev0 with Kartograf 0.8.0
> and Obserwator 3.0.0. The model's decisions were substituted with a stub (`FakeDecisionBackend`), so with
> a real model Retman may ask different or additional questions — e.g. ask about the operation or its
> group when the model is uncertain. The texts of questions, plans and messages are real; paths were
> shortened. The execution in section 5.2 saves a time series from the **Obserwator test store**
> (fictional stations, no network); no downloads from GUGiK were performed, and the report in
> section 5.4 was produced from a saved GUGiK response.

## Table of contents

1. [Preparation](#1-preparation)
2. [Project folder](#2-project-folder)
3. [First command](#3-first-command)
4. [Answering questions](#4-answering-questions)
5. [Plan, change, check and execution](#5-plan-change-check-and-execution)
6. [Results and project journal](#6-results-and-project-journal)
7. [Session, options and working without a terminal](#7-session-options-and-working-without-a-terminal)
8. [Exit codes](#8-exit-codes)
9. [What Retman Can Do Now](#9-what-retman-can-do-now)
10. [Retman in Python](#10-retman-in-python)
11. [Diagnostics: `retman doctor check`](#11-diagnostics-retman-doctor-check)
12. [Tuning thresholds: `retman eval run`](#12-tuning-thresholds-retman-eval-run)
13. [Good practices and limitations](#13-good-practices-and-limitations)

---

## 1. Preparation

Retman does not include a language model. Four things are needed: Retman with the tools
in **one** environment, a running model server, settings and the tools' data stores.

### 1.1. Installation

Installation is described in ARCHITECTURE 9.4. Until v0.1.0 is released there is no release tag, and
the Kartograf `v0.8.0` and Obserwator `v3.0.0` tags have not been pushed yet, so you install Retman from
the `develop` branch and the tools from pinned commits (the same ones the tests use, the `tools` group
in `pyproject.toml`; they are the members of the Nogat release set `candidate-4`, all on GitHub, and
`docs/PROGRESS.md` names them):

```bash
uv tool install "git+https://github.com/Daldek/Retman@develop" \
    --with "kartograf @ git+https://github.com/Daldek/Kartograf@c9afdd3f85b164b21e3ab2ce1b8cc02c050712f1" \
    --with "obserwator[store] @ git+https://github.com/Daldek/Obserwator@0394af7c66b60cccb88f14b6118893b78443dc21" \
    --with "hydrolog @ git+https://github.com/Daldek/Hydrolog@9e2cb618b115d94d93fb7caaf871a5fa5c1770a1"
```

The Obserwator `store` extra installs `pyarrow` (time series are Parquet files). Once the tags are
released, the command will get the versions `@v0.8.0` and `@v3.0.0`. A tool installed in a different
environment is invisible to Retman; `retman doctor check` (section 11) then gives the command that
will add it.

### 1.2. Model server

For now Retman talks to a server compatible with the OpenAI API, e.g. LM Studio with a loaded
model (tested: Bielik 11B, `docs/research/2026-10-11-lm-studio-openai-compatible.md`).
The server is started separately, before working with Retman.

### 1.3. Settings and data stores

Retman's settings are the `[retman]` tables of the `nogat.toml` file, shared by the Nogat tools. It lives
in the user's settings folder (on Linux `~/.config/nogat/nogat.toml`); a different file is pointed to
by the `NOGAT_CONFIG` variable or the `--config PATH` option on the command. The file is **optional**:
every setting has a default value except the model server (`[retman.decision]`), and an environment
variable overrides the file. A value comes from the first of these places:

1. a command option (`--lang`, `--verbose`, `--quiet`; `--config` only names the file);
2. the `RETMAN_<KEY>` variable — the key with dots replaced by `_`, e.g. `decision.url` is `RETMAN_DECISION_URL`;
3. the `NOGAT_<KEY>` variable — only for shared keys: `lang`, `log_level`, `data_dir`, `cache_dir`;
4. the `[retman]` table of the file (subtables: `[retman.decision]`, `[retman.tools.kartograf]` …);
5. the `[nogat]` table of the file — shared keys only;
6. the default value.

All variables are listed in the README and `.env.example`. What Retman sees and where it comes from
is shown by

```bash
retman config show           # text; with --json a retman-config/1 document
```

It shows the settings file (even an unreadable one — then with the error description), every key with
its value and source (default, variable or file), the variable with the model provider's key (`jest`
"present" or `brak` "missing", never the value) and the tools' stores with their size. Stores and caches
are by default located in the user's folders: the Kartograf store in `<data_dir>/kartograf`, the two
Obserwator folders — the data root in `<data_dir>/obserwator` and the raw root in
`<data_dir>/obserwator-raw` — the Kartograf cache in `<cache_dir>/kartograf/metadata.db`,
Obserwator reference data in `<cache_dir>/obserwator/reference`, the command set in
`<data_dir>/retman/collected.jsonl` (`data_dir` and `cache_dir` are the nogat user's data and cache
folders; on Linux `~/.local/share/nogat` and `~/.cache/nogat`). Obserwator keeps what the providers
publish (downloaded archives, the station sources of the catalogs, PMAXTP cells) in its raw root and
what it builds from them (series, station catalogs, analyses) in its data root (ADR-034).

```bash
retman config init   # appends the [retman] tables to nogat.toml and creates the tool store folders
```

All of this can be left at the defaults, but `retman config init` writes the complete set of settings
to the file so that nothing is hidden. In the terminal it asks about collecting commands (section 6.4)
and about the folder for the **tools' data stores**, creates the folders, checks that the disk supports
hard links, writes the tables, and finally — with your consent — creates both Obserwator folders (no
network). The run (Enter accepts the default value; paths were shortened):

```
$ retman config init
Czy zbierać Twoje polecenia ze wszystkich projektów w jednym pliku (~/.local/share/nogat/retman/collected.jsonl)?
Zapisywane są: polecenie, plan, Twoje odpowiedzi i decyzje modelu — do budowy i strojenia zbioru testowego.
Plik zostaje na tym komputerze; nic nie jest nigdzie wysyłane. Ustawienie można zmienić w [retman.privacy] collect_commands.
Zbierać polecenia? [t]ak / [N]ie:
Gdzie trzymać dane pobierane przez narzędzia (Kartograf, Obserwator)?
Magazyny to trzy osobne foldery w wybranym folderze — kartograf, a dla Obserwatora obserwator (folder danych: szeregi, katalogi stacji, analizy) i obserwator-raw (folder surowy: pobrane archiwa) — więc wszystkie są na jednym dysku. Wybierz dysk z dużą ilością miejsca: rastry i archiwa zajmują gigabajty, a magazyny są wspólne dla wszystkich projektów.
Plik cache Kartografa trafi na dysk lokalny użytkownika: ~/.cache/nogat/kartograf/metadata.db.
Folder na magazyny [Enter = ~/.local/share/nogat]:
~/.config/nogat/nogat.toml
Zbieranie poleceń wyłączone ([retman.privacy] collect_commands = false).
Magazyny narzędzi (ustawienia [retman.tools.*] w pliku):
  Kartograf: ~/.local/share/nogat/kartograf
  Obserwator, folder danych: ~/.local/share/nogat/obserwator
  Obserwator, folder surowy: ~/.local/share/nogat/obserwator-raw
Czy utworzyć teraz magazyn Obserwatora? To dwa foldery:
  folder surowy (pobrane archiwa, źródła katalogów stacji, komórki PMAXTP): ~/.local/share/nogat/obserwator-raw
  folder danych (szeregi, katalogi stacji, analizy): ~/.local/share/nogat/obserwator
Tworzenie nie używa sieci: znacznik powstaje w pustym folderze albo w folderze, który ma już układ swojego rodzaju, po jego sprawdzeniu przez Obserwatora. Bez nich nie działają operacje na danych IMGW, które zapisują się lokalnie.
Utworzyć oba foldery Obserwatora? [t]ak / [N]ie: t
Folder surowy Obserwatora gotowy: ~/.local/share/nogat/obserwator-raw
Folder danych Obserwatora gotowy: ~/.local/share/nogat/obserwator
```

`retman config init` prints the path of the file it wrote the tables to. An existing file stays as it was:
the `[retman]` tables are appended at the end, and other tables (`[nogat]`, tables of other tools) are not
touched. If the file already has a `[retman]` table, `retman config init` ends with a `conflict` error
(code 4) and changes nothing. Without a terminal it writes the tables with the visible default paths and
creates nothing (Kartograf writes the marker of its store on the first download, and you create both
Obserwator folders with the command "Utwórz magazyn Obserwatora" (create the Obserwator store)). If the disk of the chosen folder **has no hard
links** (FAT/exFAT, some network shares), `retman config init` ends with a `store_unavailable` error
(code 8) and does not write the file — point to a folder on another disk.

The store tables in the file, with absolute paths (shortened here to `~`):

```toml
[retman.tools.kartograf]
store_dir = '~/.local/share/nogat/kartograf'              # downloaded files, shared across all projects
cache_file = '~/.cache/nogat/kartograf/metadata.db'       # metadata cache; LOCAL disk, not a network share
workers = 4                                               # parallel transfers
update = "local"                                          # "local" | "upgrade" | "force"

[retman.tools.obserwator]
store_dir = '~/.local/share/nogat/obserwator'                   # data root: series, station catalogs, analyses
raw_store_dir = '~/.local/share/nogat/obserwator-raw'           # raw root: archives, station sources, PMAXTP cells
reference_data_dir = '~/.cache/nogat/obserwator/reference'      # optional station locations file
```

Stores cannot be nested inside one another (the Kartograf store and the two Obserwator folders are
three separate folders), and their paths cannot contain symbolic links.
`update = "local"` means: use the saved versions and do not ask the sources for newer ones. The table
template is in `src/retman/config_template.toml`. A copy of a store is made preserving hard links
(`rsync -aH`); what will not be downloaded again is described in the tool's README.

**Splitting an older Obserwator store.** An Obserwator store written before release set
`candidate-4` holds archives, PMAXTP, series and station catalogs in one folder marked by
`obserwator-store.json`. Used as the data root it is refused (`store_unavailable`, reason
`wrong_root`, in `retman doctor check` and in every plan that needs the data root). Split it once,
with hard links, as Obserwator's USAGE ("Splitting a store") describes; with the default folders:

```bash
cd ~/.local/share/nogat
mv obserwator obserwator-old                       # the default path is now the data root
mkdir obserwator-raw obserwator
cp -al obserwator-old/archives obserwator-old/pmaxtp obserwator-raw/   # name only the trees the old store has
cp -al obserwator-old/series obserwator-old/stations obserwator/       # and analyses/, if it has one
retman plan run --text "Utwórz magazyn Obserwatora"   # store init of both folders, after confirmation
retman doctor check                                # both Obserwator folders: ✓
```

"Utwórz magazyn Obserwatora" (create the Obserwator store) runs `store init` of the raw folder and
then of the data folder; Obserwator verifies the layout of each before it writes its marker
(`obserwator-store.json`, `obserwator-data.json`). With the `obserwator` command of a separate
installation the same is `obserwator store init --root RAW` and
`obserwator store init --kind data --root DATA`. The copy takes almost no space, because the files
are hard links, and it must stay on the disk of the old folder; once both folders check clean, the
old folder can be removed. The `api_keys.json` of the Obserwator server, if the old folder had one,
goes into the data root. Folders elsewhere are named by `store_dir` (data) and `raw_store_dir` (raw).

**There is no built-in model server default without `config init`.** The generated file selects
`openai_compatible` at LM Studio's local URL (`http://127.0.0.1:1234/v1`) and leaves the
model name as `<model-name>` for you to replace; change the URL for another server and tune the numeric
thresholds for your model. You can instead pass the settings as `RETMAN_DECISION_*` variables without a file:

```toml
[retman.decision]
backend = "openai_compatible"
url = "http://127.0.0.1:1234/v1"   # LM Studio server address
model = "<model-name>"             # model name on the server
timeout_s = 30
confidence = "auto"                # logprobs, or answer consistency when the server does not provide them
consistency_runs = 3

[retman.decision.thresholds]
operation = 0.90                   # confidence thresholds tuned for the model (section 12)
parameter = 0.90
```

The `"auto"` thresholds work only with basal; with another backend you have to enter numbers. Without the
model settings, a command with text to recognise ends with a `validation_error` error (reason
`invalid_config`, code 2) listing the missing keys, while `retman results list`, `retman journal show`, `retman config show` and `retman config init` work without them.
All settings are described in ARCHITECTURE 9.1 and ADR-021.

### 1.4. Check

```bash
retman doctor check
```

When everything is in order, it ends with code 0; details in section 11.

---

## 2. Project folder

Retman works in **the folder it was started in** (the project folder, e.g. the folder of a single
catchment). The results subfolder is created there (by default `retman-output/`, setting
`[retman.output] results_dir`) with the numbered results and the project journal:

```
zlewnia-a/
└── retman-output/
    ├── journal.jsonl                                  # journal: commands, questions, answers, plans, checks
    └── 001_export_station_series/                     # result #1
        ├── result.json                                # values, their sources, versions, model decisions, tool trace
        ├── hydro_daily_149190310_2022-11-01_2024-10-31.csv
        ├── tool_1_series_export.json                  # full tool documents (audit trail)
        └── tool_2_series_select.json
```

**Kartograf's** data does not live in the project folder: Kartograf saves it in its own store
(`[retman.tools.kartograf] store_dir`), and the result points to those files by absolute path and SHA-256 checksum (section 6.2).
The result then contains `result.json` and the tool's documents, and the summary says where the files are.

Run Retman in the project folder, not in your home directory or in the repository.

---

## 3. First command

A command is an ordinary sentence in Polish, in quotation marks:

```
$ retman plan run --text "Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4"
? W którym układzie wysokościowym pobrać NMT: EVRF2007 czy KRON86?
  1) EVRF2007
  2) KRON86 (tylko 0,5 m i 1 m)
> 1
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> n
Plan odrzucony.
```

What happened:

1. The model chose the operation from the list of available ones — there are more than 9 operations, so it
   first chose a group ("Dane przestrzenne GUGiK", GUGiK spatial data) and then an operation within it (here: DEM (NMT) for a map sheet).
2. The sheet code (godło) was read from the command text by **code** — numbers, sheet codes and
   coordinates are not guessed by the model; the resolution the model only picked from the
   operation's list of resolutions.
3. The command did not give the vertical datum, so Retman **asked** instead of assuming a default value
   (Kartograf operations have no default values, ADR-006).
4. The plan shows every value. The row marked `← podgląd, bez sieci` was filled in by the **tool**:
   Kartograf checked the plan offline (whether it accepts such a request) and counted the map sheets. Up to
   this point Retman did not use the tool's network access (PRD N-12).
5. Nothing was executed without `t`.

The more complete the command, the fewer questions:

```
$ retman plan run --text "ściągnij bdot dla powiatu 2264 w gpkg"
Plan:
Operacja: Pobranie BDOT10k (bieżące paczki powiatów)
Obszar BDOT10k: powiat o kodzie TERYT 2264
Format BDOT10k: GeoPackage (.gpkg)
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

Retman also understands English names and abbreviations used in practice (DEM, DTM, DSM, orthophoto,
GPKG, SHP) as well as colloquial spelling and text without Polish diacritics.

---

## 4. Answering questions

Retman asks **one question at a time**. You can answer a question with:

| Answer | Action |
| --- | --- |
| an option number, e.g. `1` | selects the option from the list |
| your own words, e.g. `kronsztadt` | the answer is checked by the same rules as a command; if it is unclear, Retman asks again |
| `?` | shows help for the question (value range, tool limitations) |
| `anuluj` | cancels the command (exit code 130) |

A notation with several possible readings always ends in a question. Example: PL-1992 coordinates
without an indication of axis order — Retman shows both readings and suggests the format:

```
$ retman plan run --check --text "Wytnij NMT 530000,382000,530100,382100 EPSG:2180 w EVRF2007, wynik w PL-1992"
? Jaki prostokąt współrzędnych albo plik geometrii wyciąć z danych wysokościowych?
  1) prostokąt w PL-1992 (kolejność E, N): E 530000–530100, N 382000–382100
  2) prostokąt w PL-1992 (zamieniona kolejność N, E): E 382000–382100, N 530000–530100
  np. 530000,382000,530100,382100 EPSG:2180
> 1
Plan:
Operacja: Wycinek NMT albo NMPT 1 m dla prostokąta lub obszaru
Produkt wycinka: NMT (numeryczny model terenu)
Układ współrzędnych wyniku: EPSG:2180 (PL-1992)
Układ wysokościowy wycinka: EVRF2007
Prostokąt lub obszar wycinka: prostokąt w PL-1992 (EPSG:2180): E 530000–530100, N 382000–382100
```

The same question comes up for a probability notation that has two readings (is "Q50" 50% or a return
period of 50 years?). A value given without a sign, such as "dla 1" ("for 1"), also always ends in
a question:

```
$ retman plan run --check --text "Opady maksymalne PMAXTP dla punktu 52.23, 21.01 metodą POT dla Q50"
? Dla jakiego prawdopodobieństwa przewyższenia zawęzić tabelę (np. 1%, 2%, 10%)?
  1) p = 50%
  2) okres powtarzalności T = 50 lat (p = 2%)
  np. 1%
> 1
Plan:
Operacja: Opady maksymalne PMAXTP dla punktu
Punkt: punkt 52.23° N, 21.01° E
Metoda obliczeń: POT (maksima ponadprogowe)
Zapis w magazynie: Tylko plik wyniku
Prawdopodobieństwo: 50% (T = 2 lat)
Czas trwania opadu: wszystkie czasy trwania z tabeli PMAXTP ← nie podano w poleceniu, parametr nieobowiązkowy
```

An answer outside the list ends with the message `Błąd: Wybierz jedną z podanych możliwości.`
("Error: Choose one of the given options.") and the same question.

### 4.1. Questions the model does not resolve

Retman always asks when a value could change the result and the command does not resolve it:

- **type of year** (hydrological, from 1 November to 31 October, or calendar) for IMGW station
  time series — there is no default value, and the word "hydrologiczne" describing the data ("dane
  hydrologiczne z lat 2000–2020", "hydrological data from 2000–2020") is not an answer;
- **a station given in an inflected form** ("na Rabie", "w Poznaniu" — "on the Raba", "in Poznań") —
  Retman shows its reading and asks for confirmation by selecting from a list; it does not correct
  misspelled names;
- **a relative period** ("ostatnie 10 lat", "od 2010" — "the last 10 years", "since 2010") — it does not
  convert it to dates; it asks for years or dates;
- **the layer of a geometry file** (a GeoPackage with several layers):

```
$ retman plan run --text "Pobierz NMT 1 m w EVRF2007 dla obszaru z pliku zlewnie.gpkg"
? Która warstwa pliku zlewnie.gpkg wyznacza obszar?
  1) zlewnie
  2) dzialki
> 2
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Godło arkusza lub obszar NMT: obszar z pliku ~/zlewnia-a/zlewnie.gpkg, warstwa „dzialki” (arkusze 1:10000 (PL-1992), które obiekty warstwy przecinają swoim kształtem, nie obwiednią; NMT 100 m: pliki województw przecinających obwiednię)
Obwiednia obszaru: 0.2 × 0.2 km (EPSG:2180: E 530200–530400, N 382100–382300) ← podgląd, bez sieci
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

A file with a single layer (and a Shapefile) does not trigger a question. Plans show a sentence about
what the file means for the given operation (e.g. a cutout is a single rectangle covering all objects
of the layer, without clipping), as well as the bounding box and number of map sheets from the preview.
GeoJSON and GML files are not accepted — the geometry must be an SHP or GPKG file.

### 4.2. The tool rejects a choice

The tool checks the complete plan **offline**. When it rejects a combination (e.g. DEM (NMT) 5 m is
available only in EVRF2007 together with KRON86), Retman no longer trusts that value and **asks again**
about the parameter the tool pointed to, with the reason in the question (the tool's text is quoted
in it):

```
$ retman plan run --text "Pobierz NMT 5 m w układzie KRON86 dla arkusza N-34-130-D-d-2-4"
? W jakiej rozdzielczości pobrać NMT: 0,15 m, 0,5 m, 0,6 m, 1 m, 5 m, 10 m czy 100 m?
  1) 0,15 m (tylko EVRF2007)
  2) 0,5 m
  3) 0,6 m (tylko EVRF2007)
  4) 1 m
  5) 5 m (tylko EVRF2007)
  6) 10 m (tylko EVRF2007)
  7) 100 m (pliki województw, bez układu wysokościowego)
Błąd: Kartograf odrzuca ten wybór: NMT 5m (PL) is only available in EVRF2007 - got --vertical-crs KRON86; available in KRON86: 0.5m, 1m
> 4
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: KRON86 (tylko 0,5 m i 1 m)
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

A plan the tool does not accept cannot be confirmed. Answering one parameter invalidates the parameters
that depend on it (here the vertical reference system): Retman reads them anew from the command, and
the preview runs again.

---

## 5. Plan, change, check and execution

After collecting all values, Retman shows the plan and waits for a decision:

| Answer | Action |
| --- | --- |
| `t` | executes the plan |
| `n` | rejects the plan (exit code 130); the journal records "rejected" |
| `z` | changes one value without typing the command again |
| `s` | checks data availability (network, separate consent); only when the operation offers it (section 5.4) |
| `?` | help |
| `anuluj` | cancels (exit code 130) |

These are the Polish words. With `--lang en` the prompts are English and the words are `y` (yes), `n`,
`c` (change), `a` (availability check) and `cancel`; a session ends with `end` instead of `koniec`. The
words of each language are the `[answers]` table of its translation file.

### 5.1. Changing a value (`z`)

```
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> z
Którą wartość zmienić?
  1) Produkt wycinka: NMT (numeryczny model terenu)
  2) Układ współrzędnych wyniku: EPSG:2180 (PL-1992)
  3) Układ wysokościowy wycinka: EVRF2007
  4) Prostokąt lub obszar wycinka: prostokąt w PL-1992 (EPSG:2180): E 530000–530100, N 382000–382100
> 2
? Do jakiego układu współrzędnych zapisać wycinek?
  1) EPSG:2180 (PL-1992)
  2) EPSG:5514 (S-JTSK)
  3) EPSG:3045 (ETRS89/TM33)
> 2
Plan:
Operacja: Wycinek NMT albo NMPT 1 m dla prostokąta lub obszaru
Produkt wycinka: NMT (numeryczny model terenu)
Układ wysokościowy wycinka: EVRF2007
Prostokąt lub obszar wycinka: prostokąt w PL-1992 (EPSG:2180): E 530000–530100, N 382000–382100
Układ współrzędnych wyniku: EPSG:5514 (S-JTSK)
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

After the change the plan is shown again (with a fresh offline preview), and the previous confirmation
and availability check no longer apply. The plan shows the rectangle as Retman **read** it (E, N), so that
a mistake in the axis order is visible before execution.

### 5.2. Execution (`t`)

An example from the Obserwator test store (fictional station "Raba Górna", no network). The command does
not specify the kind of year, so Retman asks; the data source (store) was chosen by the model:

```
$ retman plan run --text "Pobierz dobowe przepływy ze stacji Raba Górna z lat 2023–2024"
? Czy podane lata to lata kalendarzowe (1 I – 31 XII) czy hydrologiczne (1 XI – 31 X)?
  1) Hydrologiczne (1 XI – 31 X)
  2) Kalendarzowe (1 I – 31 XII)
> 1
Plan:
Operacja: Eksport szeregu stacji do CSV
Zbiór danych: Dane hydrologiczne dobowe IMGW-PIB
Stacja: Raba Górna (hydro, IMGW-PIB, kod 149190310)
Okres: 2023–2024
Źródło danych: Z lokalnego magazynu (bez sieci)
Zmienne: Q — przepływ
Rodzaj lat: Hydrologiczne (1 XI – 31 X)
Magazyn Obserwatora: ~/.local/share/nogat/obserwator (z konfiguracji) ← podgląd, bez sieci
Dane w magazynie: 2024-02-29 – 2024-02-29, luk: 0 ← podgląd, bez sieci
Okres w magazynie: magazyn pokrywa tylko część wybranego okresu (2024-02-29 – 2024-02-29) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> t
Gotowe. Wynik #1: szereg stacji 149190310 (91 wierszy, 2023-12-01 – 2024-02-29) zapisany w pliku CSV.
Uwaga: Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy. Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone. For private and research use; other uses require checking the IMGW-PIB terms, including the exceptions for high-value data.
```

After the summary Retman prints the operation's **warnings**, each on its own line "Uwaga: …" (Notice: …):
the tool's notices about data quality (e.g. an incomplete GUGiK flight), in Retman's words when it has
a text for the notice and verbatim otherwise, and a partial result is a result with a warning; the
licence lines of the data provider come last. A failed result also gets a number, and the run ends with
the registry error of its failure (its code is the exit code, section 8); Retman chooses the message
based on the tool's stable error code, and the tool's text is only a quotation (e.g. "Źródło danych
(GUGiK, SoilGrids, CORINE) nie ma danych dla wskazanego obszaru i wybranych parametrów produktu.
Szczegóły: …" — the data source has no data for the given area and selected product parameters.
Details: …).
The tools write their texts in English and Retman shows them as they come, so a Polish message can
quote an English detail (section 4.2; ADR-024). The licence lines are the tool's too: when its
document carries the lines the provider's terms require (Nogat DEV §20: `attribution` and
`terms_notice`), Retman shows each of them verbatim as a warning, keeps them in `result.json`
(section 6.2) and adds them as the trailing columns `attribution` and `terms_notice` to the CSV
tables it writes itself (stations, current data, warnings, water states, PMAXTP; ADR-033). For an
Obserwator that gives no such lines, like the one pinned now (section 1.1), the licence notice is the
text built from the tool's provider registry: the provider's attribution (Polish, in the wording
IMGW-PIB requires) followed by the English notice of the tool, as in the example above.
A download from GUGiK via Kartograf looks the same: the files go to Kartograf's store (`store_dir`;
Retman always calls Kartograf with the store, which all projects share, never with a plain
folder for its files), and the summary says where they are ("Pliki w magazynie
narzędzia: …" — Files in the tool's store: …). The error codes of Kartograf are the codes of
the registry (section 8): GUGiK having no data for the area is `no_data`, and a failed transfer
is `source_unavailable`.

### 5.3. Plan preview (offline)

The rows with `← podgląd, bez sieci` are what the tool determined about your plan **without using the
network** and without writing anything: the state of the store, the number of map sheets, the bounding box
of the geometry file, the range of data in the store, the number of archive files to check. They are there
so that you can see what the plan actually means before you confirm it.
When the preview detects that the plan will fail (e.g. no series of the dataset in the store with source
"magazyn" (store), orthophoto for a geometry file), Retman asks again about the relevant parameters with
an explanation. A problem that no answer can fix (e.g. no Obserwator store) ends the plan with its
registry error (here `store_unavailable`, code 8) and a hint how to fix it.

An optional parameter that the command did not provide also has its own row — with what its absence
means:

```
Dostawca danych: obaj dostawcy (IMGW-PIB i ČHMÚ) ← nie podano w poleceniu, parametr nieobowiązkowy
Rodzaj stacji: wszystkie rodzaje (hydrologiczne i meteorologiczne) ← nie podano w poleceniu, parametr nieobowiązkowy
```

Retman does not ask about such parameters; if you want to narrow the result, answer `z` and choose a value
or give it in the command. When the tool reports many similar notices (e.g. several dozen stations without
a location), the result shows the first three and the number of remaining ones; the full list is in the
`tool_*.json` file in the result folder.

### 5.4. Availability check (`s`)

The offline preview knows whether the tool will accept the request, but it does not know **what the data
source actually has**: which years and resolutions exist, whether the coverage is complete, which IMGW
archives have already been published. You can check this — it is a separate step with network access and
**its own consent**, the only one before the plan is confirmed.
The answer `s` is available only for operations that offer a check, and only when the plan is complete:

```
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> s
Sprawdzenie dostępności to osobny krok i jedyny, który łączy się z internetem przed wykonaniem planu. Zapytam usługi GUGiK (skorowidz arkuszy WFS i warstwę PRG) o lata, rozdzielczości i układy wysokościowe dla godła albo pliku z planu. NMT 100 m (pliki województw) nie ma takiego skorowidza i niczego nie sprawdzam.
Nie pobiera plików, niczego nie zapisuje w wynikach i nie wysyła Twojego polecenia — tylko wartości z planu.
Połączyć się z internetem i sprawdzić? [t]ak / [n]ie
> t
Sprawdzam… (Ctrl+C przerywa)
Sprawdzenie dostępności (kartograf 0.8.0, 2026-10-19 20:11): dane dostępne
  Twój wybór: NMT 1m, EVRF2007 — komplet arkuszy, najnowszy rok 2025
  Dostępne także dla tego obszaru:
    NMT 1m, KRON86 — rok 2013, komplet arkuszy
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

(The report was produced from a saved GUGiK response for this map sheet.) Rules:

- Any answer other than `t` to the consent question is a **refusal**: "Sprawdzenie pominięte." (Check
  skipped.) and return to the plan. Consent is one-off and covers a single check.
- The report **only informs** — it changes nothing in the plan. After it, the same question about the plan
  returns: `z` changes a value (e.g. to a resolution from the report), `t` confirms, `n` gives up. The check
  revokes an earlier confirmation of the plan; the order is always check first, then confirmation.
- The report status is "dane dostępne" (data available), "dane dostępne częściowo" (data partially
  available), "brak danych dla tego wyboru" (no data for this selection) or "nie udało się sprawdzić"
  (could not check: no network, service error — this is a report, not a failure). The plan then shows the
  row "Sprawdzenie dostępności: …" (Availability check: …).
- Only values from the plan are sent (area, product, years…) — never the text of the command or a file.
- The check does not take up a result number. It is recorded in the project journal even when you refuse
  it (section 6.3).
- Without a terminal and with `--check` Retman never checks (section 7).

The check is offered by the eight Kartograf download operations (years, resolutions and completeness of
coverage or the newest flights; for BDOT10k and BDOO — the counties or voivodeships of the area and the
packages already in the store; for CORINE and SoilGrids — the published edition) as well as building
the station catalog, exporting a series from source "serwer" (server) and synchronising archives (how
many files are newer or missing).

---

## 6. Results and project journal

### 6.1. List of results

```
$ retman results list
Gotowe. Wynik #1: szereg stacji 149190310 (91 wierszy, 2023-12-01 – 2024-02-29) zapisany w pliku CSV.
```

### 6.2. `result.json`

Each result has a `result.json` with the data needed to reproduce the computation: the operation, every
value with its **source** (`command` — from the command, `user` — from an answer, `default`, `workspace`
— from an earlier result, `known` — passed from Python), the confidence of the decision model, files with
SHA-256 checksums, values returned by the tool, warnings, Retman and tool versions, and timestamps.
Excerpt (result from section 5.2):

```json
{
 "ok": true,
 "number": 1,
 "operation": "export_station_series",
 "params": {
  "station": {
   "value": {"type": "station", "provider": "IMGW-PIB", "kind": "hydro",
             "code": "149190310", "name": "Raba Górna", "river": "Raba", "in_catalog": true},
   "source": "command", "confidence": null, "unverified": false
  },
  "year_type": {"value": "hydrological", "source": "user", "confidence": null, "unverified": false}
 },
 "files": {
  "hydro_series": [{"path": "retman-output/001_export_station_series/hydro_daily_149190310_2022-11-01_2024-10-31.csv",
                    "sha256": "329eb7e8…"}]
 },
 "values": {"rows": 91, "first_date": "2023-12-01", "last_date": "2024-02-29", "dataset": "pl.imgw.hydro_daily"},
 "warnings": ["Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej …"],
 "tool": {
  "tool": "obserwator", "version": "3.0.0",
  "calls": [{"command": "series export",
             "command_line": "obserwator series export --root <store> --dataset pl.imgw.hydro_daily --station 149190310 … --json",
             "status": "ok", "document_file": "tool_1_series_export.json", "sha256": "7b645332…"}]
 }
}
```

Additional sections: `tool` — the exact tool command line with environment arguments, its status, files
and the checksum of the full tool document (saved alongside as `tool_<n>_<command>.json`); `preview` —
values established by the preview (e.g. the bounding box of the area, the number of map sheets);
`checks` — availability check reports for the final state of the plan; `error_code` — a stable tool error
code when the result failed; `attribution` and `terms_notice` — the lines the data providers' terms
require, verbatim as the tools gave them, when they gave any (section 5.2); for an area from a geometry
file, the parameter entry has `files` — SHA-256 checksums of the geometry files.

A file that the tool keeps in its own store (Kartograf) is referenced by the result with an absolute path,
the tool name and a checksum, not with a copy:

```json
"files": {"dem": [{"path": "/dane/retman/stores/kartograf/nmt/…/N-34-130-D-d-2-4.asc", "store": "kartograf", "sha256": "…"}]}
```

### 6.3. Project journal

```
$ retman journal show
2026-10-19T20:11:10.307989+00:00 polecenie: Pobierz dobowe przepływy ze stacji Raba Górna z lat 2023–2024
2026-10-19T20:11:10.484466+00:00 pytanie: Czy podane lata to lata kalendarzowe (1 I – 31 XII) czy hydrologiczne (1 XI – 31 X)?
2026-10-19T20:11:10.484568+00:00 odpowiedź: 1
2026-10-19T20:11:10.496161+00:00 sprawdzenie dostępności: wykonane
2026-10-19T20:11:10.501945+00:00 plan: zatwierdzony
2026-10-19T20:11:10.604695+00:00 wykonanie: 1
```

The journal is append-only and also covers rejected, changed and interrupted plans as well as **every
availability check** — performed ("wykonane") or declined ("pominięte", in which case no network is used),
including those interrupted with Ctrl+C. For each plan it records what Retman understood: values with their
sources (`values`), decision-model decisions with confidence (`decisions`) and — on a change — which value
was corrected (`changed`); a question asked again after the tool rejected the answer also has a reason
(`reason`). A command outside the scope has its own event with the model's decision. The text of commands
and answers is recorded when `[retman.log] journal_commands = true` (the default); with `false` the journal
also omits the displayed plan, the reason for re-asking and the report lines.

### 6.4. Command set (optional)

After you consent in `retman config init` (`[retman.privacy] collect_commands = true`), Retman appends the
result of every planning run from all projects to a single file (`[retman.privacy] collect_path`):
the command, your answers, values with their sources, model decisions, status (approved
with the execution result, rejected, changed, cancelled, out of scope), versions and the model name
— without the server address and without local paths (of a geometry file only the name remains). The file
stays on your computer; it serves to build a test set for `retman eval run` from real work. To disable:
`collect_commands = false`.

---

## 7. Session, options and working without a terminal

### 7.1. Session

`retman plan run` without `--text` in a terminal opens a session: you type successive commands after the
`>` prompt. `koniec` ("end"; `end` with `--lang en`) closes the session (exit code 0), `anuluj` ("cancel";
`cancel` with `--lang en`) aborts it (exit code 130). Every `retman` command is a group and a verb
(`retman commands list` lists them all); the options of each command are described by
`retman <group> <verb> --help`.

### 7.2. Options

| Option | Effect |
| --- | --- |
| `--text TEXT` | the command in Polish (`plan run`); without it a terminal opens a session |
| `--check` | asks questions and shows the plan (with an offline preview), but does not execute it and does not check availability (exit code 0); with `--json` open questions are in `result.questions`, not an error |
| `--yes` | confirms a complete plan without asking and executes it; mutually exclusive with `--check` |
| `--explain` | prints the decision-model decisions below the plan: choice, confidence, method and option probabilities |
| `--config PATH` | a `nogat.toml` file other than the default (section 1.3) |
| `--json` | in every command: a single `retman-result/1` envelope on stdout and nothing else; never asks |
| `--lang pl\|en` | language of the texts for people: `pl` (default) or `en`; inside `--json` documents the reports of `doctor check` and `scaffold check` and the error messages are English whatever `--lang` says, while the labels, questions and summaries of plans and results are in the language they were made in |
| `--verbose`, `--quiet` | technical log level on stderr: `debug` or errors only; without the option `RETMAN_LOG_LEVEL` decides, then `NOGAT_LOG_LEVEL`, then `log_level` in `[retman]` and `[nogat]` (default `warning`); the log contains neither commands nor answers |
| `--deep` | with `doctor check`: also slower checks (a trial write of both Obserwator folders) |

```
$ retman plan run --check --text "Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4"
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
```

### 7.3. Without a terminal (scripts, pipelines, CI)

When the input is not a terminal or `--json` is given, Retman asks no questions, executes nothing without
`--yes` and runs no availability check. A plan with open questions is shown by `--check`; without `--check`
and `--yes` (or with an open question) the command ends with the error `validation_error` (reason
`input_required`, code 2; `details.questions` lists the questions, `details.option` — the missing option):

```
$ retman plan run --text "Pobierz NMT dla arkusza N-34-130-D-d-2-4" --check < /dev/null
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Brakuje: W jakiej rozdzielczości pobrać NMT: 0,15 m, 0,5 m, 0,6 m, 1 m, 5 m, 10 m czy 100 m?
```

A full plan is executed with `--yes` only after a human has seen it (`--check`); in a terminal
execution requires confirmation, from Python — see section 10.

### 7.4. Command out of scope

```
$ retman plan run --text "Jaka będzie jutro pogoda?"
Błąd: Polecenie nie dotyczy dostępnych operacji: Opad i odpływ (Hydrolog), Analizy zlewni i przepływów (Hydrolog), Dane glebowe SoilGrids, Dane przestrzenne GUGiK, Stacje i rejestr danych IMGW, Dane bieżące i ostrzeżenia IMGW, Opady maksymalne PMAXTP, Szeregi czasowe stacji IMGW i ČHMÚ, Archiwa danych IMGW i magazyn Obserwatora
```

With two-stage recognition Retman lists the **groups** of operations instead of forcing a match to the
nearest operation (PRD W-03).

---

## 8. Exit codes

Exit codes are codes of the shared Nogat registry ([ERROR_REGISTRY](https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md)):
the same code means the same thing in every tool. On error, the last line of stderr is a
`retman-error/1` document (one line of JSON: `code`, `title`, `message`, `hint`, `details`, `exit_code`);
`details.reason` narrows the code (e.g. `out_of_scope`, `input_required`, `missing_config`).
Interruption by the user is not an error and prints no document.

| Code | Name | Meaning in Retman |
| --- | --- | --- |
| 0 | `ok` | operation executed, plan shown with `--check`, session ended with `koniec` |
| 1 | `internal_error` | Retman error or unexpected exception; an error in an operation that the tool did not describe |
| 2 | `validation_error` | invalid option or variable (`usage`), invalid configuration (`invalid_config`), answers or confirmation needed while the input is not a terminal (`input_required`) |
| 3 | `not_found` | missing settings file pointed to by `--config` or `NOGAT_CONFIG` (`missing_config`), missing input file or result |
| 4 | `conflict` | settings file already has a `[retman]` table (`output_exists`), plan not confirmed or changed |
| 5 | `source_unavailable` | model does not respond (`backend_connection`) or the tool's data source failed |
| 6 | `missing_dependency` | tool is not installed (`tool_not_installed`) or no operations (`no_operations`) |
| 7 | `data_error` | file inconsistent with its data kind, bad command set for `eval run` |
| 8 | `store_unavailable` | tool store does not work (e.g. disk without hard links) |
| 9 | `io_error` | writing or reading a file failed |
| 10 | `partial` | result printed, but some of the `items` units did not pass: `doctor check` (something blocks work, some checks passed), `eval run` (some commands to be rejected were planned), `scaffold check` (errors in some tools) |
| 11 | `failed` | the same, when no check or tool passed |
| 12 | `forbidden` | the tool refuses to write in that place (Obserwator, Hydrolog) |
| 13 | `calculation_error` | tool cannot compute a result from valid data |
| 14 | `no_data` | source has no data for the area or period (e.g. GUGiK has none for the area; the `result.json` of a failed result keeps the tool's precision, e.g. `no_coverage`, as the `reason` of its failure) |
| 15 | `unsupported` | command out of scope (`out_of_scope`) or no availability check (`no_check`) |
| 130 | `cancelled` | interrupted by the user (`anuluj`, `n`, Ctrl+C — also during an availability check) |
| 143 | `terminated` | process received SIGTERM |

Codes 10 and 11 do not mean an error: the result was printed, and the code says whether every unit passed.
`eval run` and `scaffold check` have the same codes; eval options and measures: see section 12.

---

## 9. What Retman Can Do Now

Operations fall into nine groups: two for Kartograf (spatial data and SoilGrids soil data, the latter
shared with Hydrolog), five for Obserwator and two more for Hydrolog; Retman first picks the group, then
the operation.

### 9.1. Kartograf 0.8.0 — spatial data and SoilGrids soils (ADR-001, ADR-012, ADR-016)

Ten operations in two groups. Six of them download data from GUGiK and Copernicus (CORINE) and
two from SoilGrids (ISRIC) into the Kartograf store (always the store, never plain files in the results folder) and
have an offline preview and an availability check; one writes the marker of the store and one
reads its segments:

| Operation | Area | Parameters (Retman asks about missing ones) | Example command |
| --- | --- | --- | --- |
| Download DEM (NMT) for a map sheet or area | PL-1992 or PL-2000 sheet code (godło); geometry file | resolution 0.15 / 0.5 / 0.6 / 1 / 5 / 10 / 100 m; vertical datum EVRF2007 / KRON86 (KRON86 only for 0.5 m and 1 m; 100 m without a datum) | `Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4` |
| Download child map sheets | parent sheet code (godło); geometry file (not for orthophoto) | product DEM (NMT) / DSM (NMPT) / orthophoto; target scale 1:10000–1:500 (finer than 1:10000 only in PL-2000); for DEM resolution 0.15–10 m, for DSM 0.5 / 0.6 / 1 m; vertical datum; for orthophoto colour RGB / CIR / B-W | `Rozwiń N-34-130-D-d-2 do 1:10000, ściągnij DSM z arkuszy potomnych` |
| Cutout of DEM (NMT) or DSM (NMPT) 1 m | rectangle in PL-1992 (EPSG:2180) or WGS84 (EPSG:4326); geometry file | product DEM (NMT) / DSM (NMPT); result CRS EPSG:2180 / 5514 / 3045 (code with the `EPSG:` prefix, the bare number or a name, e.g. `wynik w 2180`, `do S-JTSK`); vertical datum | `wytnij dsm z prostokąta 52.40 16.90 52.41 16.91 do 3045` |
| Download BDOT10k | county (TERYT, 4 digits), sheet code (godło), rectangle or geometry file | format GeoPackage / Shapefile | `ściągnij bdot dla powiatu 2264 w gpkg` |
| Orthophoto cutout | rectangle in PL-1992 (EPSG:2180) or WGS84 (EPSG:4326); geometry file (the rectangle around it) | product orthophoto (RGB) / true orthophoto (true orto, selected cities); for the orthophoto the WCS variant standard (newest photos) / high (pixel of 10 cm or less); pixel 5 cm (true orto only) / 10 cm / 25 cm / 50 cm / 1 m. One GeoTIFF in EPSG:2180 from the server's composition of flights (no year choice) | `Wytnij ortofotomapę standardową 25 cm z 16.90 52.40 16.91 52.41` |
| Land cover: CORINE or BDOO | sheet code (godło), rectangle or geometry file | product CORINE Land Cover / BDOO; the CORINE edition 2018 / 2012 / 2006 / 2000 / 1990 or the BDOO release 2026–2021 / 2015. CORINE is one raster of the area: class codes (GeoTIFF) with CLMS credentials (`CLMS_CREDENTIALS`), otherwise a coloured WMS preview (PNG), which the result says; BDOO is the GML package (ZIP) of every voivodeship the area touches | `Pobierz CORINE Land Cover 2018 dla arkusza N-34-130-D` |
| Create the Kartograf store | the folder `store_dir` of the settings | none; it writes the store marker `kartograf-store.json` (nothing is downloaded, no check), into a new or an empty folder or into a layout that has lost its marker, after Kartograf has checked the layout; a folder with other files or a store inside another store is refused in the plan | `Utwórz magazyn Kartografa` |
| Overview of the Kartograf store | the folder `store_dir` of the settings | none; it lists the segments (product folders) with the product, the country, the dataset and whether the installed Kartograf knows them; a read, offline (a folder that does not exist is refused in the plan) | `Pokaż, co jest w magazynie Kartografa` |
| Download a SoilGrids soil layer | sheet code (godło), rectangle or geometry file (the rectangle around it) | property: clay / sand / silt / organic carbon / pH / bulk density / coarse fragments / CEC / nitrogen; for organic carbon its measure: content SOC / density OCD / stock OCS; depth 0–5 / 5–15 / 15–30 / 30–60 / 60–100 / 100–200 cm (the stock: 0–30 cm); statistic mean / median / 5% / 95% quantile / uncertainty. The result gives the unit of the integer values of the file and the divisor to the usual unit (clay in g/kg: percent = value / 10) | `Pobierz zawartość iłu 0-5 cm, średnia, dla arkusza N-34-130-D-d-2-4` |
| Hydrologic soil groups HSG (A–D, SCS-CN) | sheet code (godło), rectangle or geometry file (the rectangle around it) | depth of the texture 0–5 … 100–200 cm; Kartograf downloads the clay, sand and silt of that depth and computes the groups; the result gives the share and the area of each group | `Wyznacz grupy HSG z głębokości 0-5 cm dla arkusza N-34-130-D-d-2-4` |

Ways of writing the area:

- **sheet code (godło)**: `N-34-130-D-d-2-4` (PL-1992, also the 8-part `N-34-50-A-c-3-2-3`), `5.123.45`
  (PL-2000);
- **county TERYT**: `TERYT 2264`, `powiat 2264`;
- **rectangle**: four numbers and a CRS, e.g. `530000,382000,530100,382100 EPSG:2180` or
  `52.40 16.90 52.41 16.91` (WGS84). When the axis order is ambiguous, Retman asks (section 4);
- **geometry file** SHP or GPKG (section 4.1): Kartograf reads the file itself; Retman asks about the
  GeoPackage layer when there are several, shows the bounding box and the number of map sheets in the plan,
  and records the SHA-256 checksums of the files.

### 9.2. Obserwator 3.0.0 — IMGW-PIB and ČHMÚ data (ADR-017)

19 operations in five groups. Obserwator keeps two folders (section 1.3, ADR-034): the raw folder
(`raw_store_dir`) with what it downloads into the store (archives, the station sources of the
catalogs, PMAXTP cells) and the data folder (`store_dir`) with what it builds from them (series,
station catalogs). The operations that read or write them (station search in the store, the station
catalog, series, PMAXTP kept in the store, the archives of the store, the store description) require
the initialised Obserwator folders (section 1.3); current data, warnings, the list of datasets, a
PMAXTP table not kept in the store and archive downloads to the result folder need none. Recognising
stations by name works offline from the station catalog in the data folder. The "Network" column says whether
execution connects to the server (only after `t`):

| Group | Operations | Network |
| --- | --- | --- |
| IMGW stations and data registry | search for IMGW and ČHMÚ stations (by name, river, kind); build the station catalog (`s`): the station lists of the provider are downloaded into the raw folder, then the catalog is built in the data folder; list of datasets and providers | search from the "server" source and catalog build |
| Current data and warnings | current measurements of a hydrological, meteorological or synoptic station; hydrological and meteorological warnings; water levels (alarm and warning) | yes |
| PMAXTP maximum precipitation | table for a point (POT or AMP method; saving the cell in the store or not; narrowing to selected probabilities and durations); reading a saved cell | download yes, read no |
| Station time series | export of a station's time series to CSV (dataset, period, year kind, variables; source "store" or "server", `s`; "server" downloads the archives and builds the series first); data coverage of a station in the store; building time series | "server" source |
| IMGW data archives and the Obserwator store | download of hydrological or meteorological archives to the result folder; check of archives against the store (plan); download of archives into the store, followed by building the dataset's series (`s`), also per a plan from an earlier result (e.g. "#5", archives only); export of stored archives to CSV or JSON Lines; creation of both folders; store description (the data folder; the raw folder for archives, PMAXTP and observations) | downloads and check yes |

Example commands (illustrative; not all are in the `retman eval run` set yet): "Znajdź stacje hydrologiczne
na Wiśle" (find hydrological stations on the Vistula), "Zbuduj katalog stacji IMGW" (build the IMGW station
catalog), "Jakie dane ma ČHMÚ?" (what data does ČHMÚ have?), "Aktualny stan wody na stacji Poznań-Bogdanka"
(current water level at the Poznań-Bogdanka station), "Jakie są ostrzeżenia hydrologiczne?" (what are the
hydrological warnings?), "Opady maksymalne PMAXTP dla punktu 52.23, 21.01 metodą POT" (PMAXTP maximum
precipitation for point 52.23, 21.01 using the POT method), "Pobierz dobowe opady ze stacji Poznań z lat
2000–2020" (download daily precipitation from the Poznań station for 2000–2020), "Za jakie lata mam dane
stacji Poznań-Ławica?" (which years of data do I have for the Poznań-Ławica station?), "Sprawdź, ile trzeba
pobrać dla opadów dobowych 2000–2020" (check how much needs downloading for daily precipitation 2000–2020),
"Utwórz magazyn Obserwatora" (create the Obserwator store), "Co mam w magazynie IMGW?" (what is in my
Obserwator store?; a command may still name the store after the IMGW data).

Rules for Obserwator operations:

- **stations**: a code (9 digits for IMGW-PIB, WIGOS identifier for ČHMÚ) or a name from the catalog in the
  data folder; an inflected name requires confirmation; without a catalog Retman reads only codes and suggests
  "Zbuduj katalog stacji IMGW": a station named in words ("ze stacji Racibórz-Miedonia") is then a question
  for its code, never a request for every station;
- **period**: archives take years in the tool's archive numbering (for IMGW-PIB hydrological data —
  hydrological years), time series take years or dates plus the year kind (no default: a question unless
  the command states it);
- **PMAXTP**: the probability and duration from the command narrow the result table; a value outside the
  table gives a warning and is not silently skipped;
- **licence**: the data provider's licence lines are shown after execution as the last warnings, and the
  lines of Nogat DEV §20 that the tool gives also go into `result.json` and the CSV tables Retman writes
  (section 5.2);
- the folders are created only deliberately (`retman config init` or the "Utwórz magazyn Obserwatora"
  operation, which creates both) — a missing folder ends the plan with the error `store_unavailable`
  (code 8) and a hint how to create it, and a store not yet split (reason `wrong_root`) with the
  hint to split it (section 1.3); nothing is created silently.

### 9.3. Hydrolog 1.0 — catchment hydrology, computed offline

Nine operations in three groups: rainfall and runoff, catchment and flow analyses, and the soil groups
of texture rasters, which belong to the soil data group shared with Kartograf. Hydrolog computes on
your computer: it downloads nothing and keeps no store (there is no `[retman.tools.hydrolog]` table);
its inputs are your files or earlier results (`#N`):

| Operation | Input | Parameters (Retman asks about missing ones) | Example command |
| --- | --- | --- | --- |
| Design hyetograph (Hydrolog) | — | shape: block / triangular / Beta / Euler II; rainfall total in mm; duration; time step (default 5 min, after „krok” or „co”) | `Oblicz hietogram Eulera typu II dla opadu 38,4 mm trwającego 2 godziny` |
| Effective rainfall by SCS-CN (Hydrolog) | — | curve number after „CN”; rainfall total in mm; antecedent moisture dry / average (default) / wet | `Oblicz opad efektywny metodą SCS-CN dla CN 72 i opadu 50 mm` |
| Design hydrograph of a catchment (Hydrolog) | — | area in km² or ha; CN; time of concentration (after „czas koncentracji” or „tc”); the rain of the hyetograph; moisture; SCS unit hydrograph | `Policz hydrogram dla zlewni 45,3 km², CN 72, tc 90 min, opad Euler II 62 mm w 120 min` |
| Time of concentration (Hydrolog) | a watershed file (`WatershedParameters` JSON) or result #N | method: Kirpich / NRCS / Giandotti / FAA / Kerby / Kerby–Kirpich (no default: asked when the command names none); a method the watershed lacks fields for is asked again | `Oblicz czas koncentracji metodą Kirpicha dla zlewni z pliku zlewnia.json` |
| Flood quantiles (Hydrolog) | a daily flow series of Obserwator (result #N or CSV) | probabilities or return periods (default: 2–1000 years); distribution: all (default) / log-normal / GEV / Pearson III / Weibull; the plan shows the complete hydrological years | `Oblicz przepływy maksymalne Q1% i Q10% z szeregu #3` |
| Watershed morphometry (Hydrolog) | a watershed file (`WatershedParameters` JSON) or result #N | — | `Oblicz parametry morfometryczne zlewni z pliku zlewnia.json` |
| Hydrographs through a river network (Hydrolog) | a network file (`hydrolog-network/1` JSON) or result #N whose subcatchments hold their hydrographs or compute them from rain | — ; the plan shows the network, its nodes and its outlet (Hydrolog routes it in memory first); the result gives the peak, the time to peak and the volume of every node, the table `<id>.csv` of every node in `hydrographs/` and the schematic `network.svg` | `Przeprowadź hydrogramy przez sieć rzeczną z pliku siec.json` |
| Hydrographs through a river network with an inflow table (Hydrolog) | a network file and an inflow table (CSV with `time_min` and a discharge column per subcatchment, or the table of a node of an earlier result) | — ; as above; a network whose subcatchments read the table, planned without one, ends the plan with the advice to name it | `Przeprowadź hydrogramy przez sieć z pliku siec.json z dopływami z pliku doplywy.csv` |
| Hydrologic soil groups HSG of texture rasters (Hydrolog) | clay, sand and silt rasters on one grid: earlier SoilGrids results #N (each taken by its property) or GeoTIFF files | — ; nothing is downloaded; the same file for two textures ends the plan; the result gives the cells and the share of each group | `Wyznacz grupy HSG z rastrów iłu, piasku i pyłu z wyników #1, #2 i #3` |

---

## 10. Retman in Python

The same flow — questions, plan, check, confirmation — is available from Python:

```python
from pathlib import Path

from retman import Plan, Retman

retman = Retman.from_config(Path("nogat.toml"), project_dir=Path("zlewnia-a"))

plan = retman.plan("Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4")
for question in plan.questions:          # here: vertical_crs
    print(question.text)                 # question in the user's language
    for number, option in enumerate(question.options, start=1):
        print(f"  {number}) {option.label}")
plan = plan.answer("vertical_crs", "1")  # a number or your own words

print(plan.summary())                    # the same plan as in the terminal (with preview rows)

if plan.can_check:                       # the operation offers an availability check
    print(plan.check_notice())           # what the check contacts and what it sends
    plan.confirm_check()                 # separate, one-time consent; does not confirm the plan
    report = retman.check(plan)          # CheckReport; without consent CheckNotConfirmedError
    print(report.summary())              # status and lines; plan values unchanged

plan.confirm()                           # without this execute() raises PlanNotConfirmedError
result = retman.execute(plan)
if result.ok:
    print(result.summary)
    print(result.files)                  # {"dem": [Path(...)]} — in the output folder or in the tool's store
else:
    print(result.error, result.error_code)
for warning in result.warnings:          # tool notes (data quality, license): always show them
    print("Uwaga:", warning)
```

- `Retman.from_config()` without a path reads `nogat.toml` from the system location (or from
  `NOGAT_CONFIG`) and the `RETMAN_*` variables, and `project_dir` defaults to the current folder.
- Values known up front are passed through `known` — they go into the plan with source `known`
  and are neither overwritten by the model nor reopened after the tool rejects them:

  ```python
  plan = retman.plan(
      "Pobierz NMT dla arkusza N-34-130-D-d-2-4",
      known={"resolution": "1m", "vertical_crs": "kron86"},
  )
  assert plan.questions == []
  ```

- A plan can be saved and resumed: `plan.to_dict()` (JSON) and `Plan.from_dict(state, retman=retman)`.
  A loaded plan is **always unconfirmed** (even when the saved state carries `confirmed`) and must be
  confirmed again; consent to the check is not saved either.
- `plan.change(name)` reopens a single value (like `z` in the terminal); every change to the plan
  invalidates the confirmation, the consent to the check and the check reports.
- `plan.preview_rows`, `plan.preview_values`, `plan.reopened` and `plan.checks` show the state of the
  preview and the checks; `retman.record_check(plan, "rejected")` records a refusal of the check in
  the journal.
- For tests, `Retman(config, backend, project_dir, clients={"kartograf": client})` accepts a custom
  tool client (e.g. `retman.testing.FakeToolClient`, which records every call).
- A command outside the scope raises `retman.exceptions.OutOfScopeError` with the list of available
  operations (or their groups) in `operations`.

Full API description: ARCHITECTURE 7.1 and 7.3.

---

## 11. Diagnostics: `retman doctor check`

`retman doctor check` shows in one place what works, what does not and how to fix it:
the configuration file, the project folder and writing of results, the model server address (always
shown, without judgement), whether the model is on the server, a test question with an obvious answer,
the confidence method and thresholds, installed tools against the supported versions, **tool data
stores**, conformance of the descriptions with the tools and the completeness of translations.

```
$ retman doctor check
Retman 0.1.0.dev0

Konfiguracja
  ✓ plik ustawień: nogat.toml (istnieje)
  ✓ projekt: <project folder> → wyniki w retman-output/ (0 wyników, zapis możliwy)

Model decyzyjny
  ✓ adres modelu (openai_compatible): http://127.0.0.1:18731/v1
  ✓ model: bielik-11b dostępny na serwerze
  ✓ pytanie testowe: poprawna odpowiedź (bez pewności)
  ! pewność: niedostępna (confidence = "none") — wybory modelu w planie są oznaczone jako niezweryfikowane → ustaw confidence = "auto" w [retman.decision] (nogat.toml), jeśli serwer podaje logprobs

Narzędzia
  ✓ hydrolog 1.0.0, obsługiwane >=1.0.0.dev0,<2, 9 operacji
  ✓ kartograf 0.8.0, obsługiwane >=0.8.0.dev0,<0.9, 10 operacji
  ✓ obserwator 3.0.0, obsługiwane >=3.0.0.dev0,<4, 19 operacji

Magazyny danych narzędzi
  ✓ kartograf: magazyn ~/.local/share/nogat/kartograf (zapis możliwy, dowiązania twarde działają)
  ✓ kartograf: cache metadanych ~/.cache/nogat/kartograf/metadata.db
  ✓ obserwator, folder danych: ~/.local/share/nogat/obserwator (znacznik obserwator-data.json, schemat obserwator-data/1, dowiązania twarde działają)
  ✓ obserwator, folder surowy: ~/.local/share/nogat/obserwator-raw (znacznik obserwator-store.json, schemat obserwator-store/1, dowiązania twarde działają)
  ✓ obserwator: pyarrow 26.0.0 (szeregi czasowe)
  ✓ obserwator: dane referencyjne ~/.cache/nogat/obserwator/reference (hydro_stations_locations.csv: brak)

Zgodność opisów z narzędziami (retman scaffold check)
  ✓ hydrolog 1.0.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)
  ✓ kartograf 0.8.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)
  ✓ obserwator 3.0.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)

Tłumaczenia (pl)
  ✓ komplet

Model tekstowy
  – wyłączony ([retman.text] backend = "none")
```

(Report layout; the values of addresses, versions and paths depend on the environment.) The "Stores"
section checks paths (without symbolic links), write permission, **hard links in every store folder**, the
store marker of each tool (`kartograf-store.json`; for Obserwator `obserwator-data.json` in the data
folder and `obserwator-store.json` in the raw folder), the Kartograf cache,
`pyarrow` and the reference data folder. A missing Obserwator folder (also a folder that holds only the
`api_keys.json` of the Obserwator server) is a warning with the hint "create it: retman config init
(in a terminal) or the command 'Utwórz magazyn Obserwatora'"; a missing Kartograf store is only a
warning and an empty one is fine, because Kartograf marks it by itself at the first download. A disk
without hard links, a foreign folder in the store's place, a marker that the tool cannot read, a store
inside another store, a folder with the layout of a store but no marker and an Obserwator folder that
holds only the marker of the other kind (`wrong_root`: an Obserwator store not yet split, see
section 1.3) are blocking problems,
each with a hint which folder to choose instead; for the layout without a marker the hint is the
command "Utwórz magazyn Obserwatora" for Obserwator and "Utwórz magazyn Kartografa" (or
`kartograf store init --root <folder>`) for Kartograf, and either makes the tool check the layout
and write the marker. The plan of a Kartograf operation names the same folder problems before you
confirm anything.
The "Conformance" section is a lightweight version of `retman scaffold check`: it warns when an
installed tool accepts a value that the descriptions neither offer nor exclude; it does not block
work.

`retman doctor check --deep` adds a slower check: a trial write of both Obserwator folders on the tool's
built-in test data, in a temporary directory and without network access:

```
  ✓ obserwator 3.0.0: zapis do magazynu działa na tym systemie (próba na danych testowych)
```

When the model server is not running:

```
Model decyzyjny
  ✗ serwer modelu nie odpowiada (http://127.0.0.1:18731/v1) → uruchom serwer modelu (np. LM Studio albo basal-serve, instrukcja w README) i sprawdź [retman.decision] url w nogat.toml albo zmienną RETMAN_DECISION_URL
```

Markers: `✓` works, `!` warning (work is possible), `✗` problem, `–` disabled.
Exit code 10 (`partial`) means a problem blocking work with some checks having passed, and 11
(`failed`) — that none passed; the report is printed in that case. `retman doctor check --json`
prints the same report in the `retman-result/1` envelope (each check is an `items` unit) — for pasting
into a bug report. When an ordinary command cannot connect to the model, the error message also
suggests `retman doctor check`.

---

## 12. Tuning thresholds: `retman eval run`

Confidence thresholds decide when Retman accepts the model's choice and when it asks follow-up
questions. For a model other than basal they must be tuned on a test command set:

```bash
retman eval run --config nogat.toml --target-error 0.01 --report report.md --output records.jsonl
```

`retman eval run` plans every command in the set (without executing operations and without tool network
access) and reports operation and parameter accuracy, errors accepted without asking (W-02), silent
guessing, W-03 violations, timings and **recommended thresholds** for a given error rate. With two-stage
recognition, the question about the operation group counts as asking the user. It does not save the
recommended thresholds itself — you enter them in `[retman.decision.thresholds]`. Exit codes: 0 — run
completed, 10 — a W-03 violation occurred (run completed; 11 when every command to be refused was
planned), 2 — invalid arguments,
3 — the specified settings file does not exist, 5 — the model does not respond, 130 — interrupted; full
list in section 8. Options and metrics: `docs/specs/2026-10-11-retman-eval.md`.

---

## 13. Good practices and limitations

- **Put everything you know into the command** — resolution, coordinate system, format, type of year.
  Retman does not assume default values on the user's behalf; whatever is missing, it asks for.
- **Read the plan before `t`.** Values from answers and from the command appear there in the form in
  which Retman understood them; rows marked `← podgląd, bez sieci` (preview, no network) say what the
  tool determined offline; model choices without confidence are marked "wybór modelu niezweryfikowany"
  (model choice unverified).
- **Check availability when you are unsure about the data** (`s`): years, resolutions and completeness
  of GUGiK coverage, or how many IMGW archives need to be downloaded — before you confirm the download.
  The report is informational only.
- **PL-1992 coordinates**: when written without indicating the axis order, Retman asks which
  reading is correct (section 4).
- **The coordinate system of the cutout result** is recognised by code, not by the model: after the
  words "wynik", "do", "przelicz", "zapisz", "docelowy" (also without Polish diacritics and with a single
  typo). A coordinate system given right after the coordinates (`… 382100 PL-1992`) Retman treats as
  the system of the rectangle and asks about the result system; likewise with a typo in the code itself
  (`2108`).
- **Geometry file**: SHP and GPKG only; sheet operations take the map sheets that the features meet
  (a polygon by its shape, not every sheet of its bounding box), while the cutout is a single rectangle
  covering all features, not clipped to the shape. Orthophoto sheets are not downloaded for a file (only for a sheet
  code); the orthophoto cutout takes the rectangle around the file.
- **BDOT10k** for a sheet code, rectangle or file downloads the full packages of every intersected county,
  without clipping — the files can be large (Kartograf rejects an area with more than 100 packages or
  more than 10 GB).
- **Stores**: Kartograf and Obserwator data are shared by all projects and live outside the project
  folder; they require a disk with hard links (not FAT/exFAT), and the Kartograf cache — a local disk.
  A project folder on a network share (e.g. CIFS) is no longer a problem for the cache (the cache is
  outside the project).
- **The tools' texts are English**: the part of a message that quotes a tool (the detail of an error, a
  notice Retman has no text of its own for) is not translated, whatever `lang` says, and the providers'
  licence lines are passed on as the tool words them; the documents saved with the result
  (`tool_<n>_<command>.json`) keep the tool's own words.
- The latest available GUGiK material is downloaded, except BDOO, whose release you choose; selecting a
  year and campaign of a flight is not yet available.
  Kartograf in `update = "local"` mode uses saved versions and does not ask the sources for newer ones.
- Retman does not send commands anywhere other than the configured model; tools connect to data services
  only after `t` or, on request, in the availability check, which sends only values from the plan.
