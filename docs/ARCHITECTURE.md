# Retman — architektura

> **Status dokumentu:** szkic (2026-10-11) · **Licencja:** MIT · **Język dokumentu:** polski
> **Wymagania i zakres produktu:** [PRD.md](PRD.md)

Ten dokument opisuje, **jak** zrealizować wymagania z PRD. Oznaczenia w nawiasach kwadratowych,
np. [W-02] albo [N-03], wskazują wymagania z PRD, które dana część realizuje.

---

## 1. Zasady projektowe

### 1.1. Zasady

| Zasada | Co oznacza w praktyce | Wymagania |
| --- | --- | --- |
| **Narzędzia nic nie wiedzą o Retmanie** | Hydrograf i reszta nie zawierają żadnego kodu, plików ani zależności związanych z Retmanem. Retman korzysta wyłącznie z ich publicznego API (p. 3.2). Jedyny możliwy wyjątek w przyszłości: opcjonalny panel czatu w GUI (p. 7.4). | [N-03] |
| **Retman nie zawiera modelu** | Model to osobna usługa (np. LM Studio, Ollama, basal-serve, API dostawcy), z którą Retman łączy się przez API. Kod nie zależy od konkretnego modelu — wybór modelu to tylko konfiguracja (p. 3.3). | [N-02], [N-10] |
| **Liczby liczy kod, nie model** | Model wybiera operację i opcje. Współrzędne, daty, prawdopodobieństwa i inne wartości wyciąga i sprawdza kod. | [W-01], [W-08] |
| **Listy dla wyborów, liczby dla wartości** | Metody czy typy analiz to wybór z listy. Wartości ciągłe (np. prawdopodobieństwo) to liczby, nie listy. | [W-08] |
| **Nie zgadywać po cichu** | Gdy pewność jest za niska albo brakuje danych, Retman dopytuje. Gdy pasuje kilka wcześniejszych wyników, pyta, którego użyć (p. 5.3). Wartości domyślne i wcześniejsze wyniki są zawsze pokazane w planie. | [W-02], [W-04], [W-07] |
| **Zawsze potwierdzenie przed wykonaniem** | Użytkownik widzi plan i zatwierdza go. W wersjach 0.x bez wyjątków (p. 6.3). | [W-05] |

### 1.2. Świadome ograniczenia projektowe

- **Model nie planuje łańcuchów.** Łańcuchy (v0.2) buduje kod na podstawie zależności między
  operacjami, a model wybiera tylko cel i parametry (p. 4.5).
- **Dokumentacja narzędzi nie jest czytana w trakcie działania.** Służy do generowania
  i sprawdzania opisów (p. 3.2.3).
- **Brak trybu wykonania bez potwierdzenia** w wersjach 0.x.

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

Każde polecenie przechodzi przez sześć kroków [W-01], [W-02], [W-04], [W-05]:

```
 Polecenie użytkownika
        │
        ▼
 1 ROZPOZNANIE OPERACJI ──── model decyzyjny: "którą operację wybrać?" (choice)
        │
        ▼
 2 PARAMETRY Z LIST ──────── model decyzyjny: "który rodzaj danych? jaka metoda?" (choice)
        │
        ▼
 3 PARAMETRY SWOBODNE ───── kod: ekstraktory (współrzędne, daty, prawdopodobieństwa, stacje, pliki)
        │                    + przestrzeń robocza (wcześniejsze wyniki, rozdz. 5)
        ▼
 4 WALIDACJA I DOPYTANIE ── czego brakuje? co ma za niską pewność? → pytanie do użytkownika
        │
        ▼
 5 PLAN + POTWIERDZENIE ─── "Pobiorę dobowe opady ze stacji Poznań (2000–2020). Wykonać?"
        │
        ▼
 6 WYKONANIE + OPIS ─────── handler w Retmanie → publiczne API narzędzia → wynik
                             → zapis w przestrzeni roboczej → (opcjonalnie) opis po polsku przez model tekstowy
```

### Przykład (pojedyncza operacja, model decyzyjny: basal)

Polecenie: *„Pobierz dobowe opady ze stacji Poznań z lat 2000–2020”*

| Krok | Kto | Wynik |
| --- | --- | --- |
| ① | basal | operacja = `fetch_imgw_data` (pewność 0.96) |
| ② | basal | `variable` = `precipitation` (0.98), `interval` = `daily` (0.94) |
| ③ | ekstraktory | stacja „Poznań” → dopasowanie do listy stacji IMGW; okres = 2000-01-01 – 2020-12-31 |
| ④ | walidator | wszystkie wymagane parametry są, pewności powyżej progów; gdyby nazwie „Poznań” odpowiadało kilka stacji, Retman dopyta, o którą chodzi |
| ⑤ | Retman | pokazuje plan i czeka na potwierdzenie |
| ⑥ | handler IMGWTools w Retmanie | wywołuje IMGWTools, zapisuje wynik w przestrzeni roboczej (rozdz. 5) |

> Przykład jest poglądowy: nazwy operacji i parametrów zostaną ustalone razem z listą operacji (PRD).

Gdy operacja wymaga danych, których polecenie nie zawiera (np. przepływ wymaga charakterystyki
zlewni), Retman w v0.1 szuka ich w pliku wskazanym w poleceniu albo we wcześniejszych wynikach
(rozdz. 5). Jeśli ich tam nie ma, informuje, czego brakuje. Automatyczne dokładanie kroków
to łańcuchy w v0.2 (p. 4.5).

---

## 3. Architektura

### 3.1. Moduły

```
retman/
├── core/
│   ├── pipeline.py          # steps ①–⑥, main logic
│   ├── plan.py              # Plan object (operation + parameters + confidences + sources)
│   ├── result.py            # Result object (p. 7.3)
│   ├── workspace.py         # project results: numbering, lookup by kind, input selection (ch. 5)
│   ├── journal.py           # project journal and audit data (p. 5.4)
│   └── dialog.py            # questions and answers, independent of the user interface (p. 6.4)
├── registry/
│   ├── operation.py         # internal Operation and parameter model
│   ├── manifest.py          # manifest schema and validation (p. 4.1)
│   └── loader.py            # loading tool descriptions, checking installed tool versions
├── adapters/
│   └── manifest_adapter.py  # generic adapter: params → handler → Result
├── tools/                   # descriptions and handlers for each supported tool (p. 3.2.2)
│   ├── hydrograf/
│   ├── hydrolog/
│   ├── imgwtools/
│   ├── kartograf/
│   └── basichydraulics/
├── devtools/
│   └── scaffold.py          # draft generation and API drift check (p. 3.2.3)
├── kinds.py                 # registry of data kinds and their file formats (p. 3.2.6)
├── i18n/
│   ├── loader.py            # loading translation files
│   └── pl.toml              # Polish texts for core messages
├── backends/                # connections to separately installed models (p. 3.3)
│   ├── base.py              # DecisionBackend and TextBackend interfaces
│   ├── openai_compatible.py # any OpenAI-compatible API: LM Studio, Ollama, vLLM, providers
│   ├── basal.py             # basal-serve API
│   └── native/              # providers with their own API (optional extras, v0.2)
├── extractors/
│   ├── coordinates.py       # geographic coordinates and PL-1992
│   ├── areas.py             # areas: map sheet codes (godło), bounding boxes, TERYT codes (ADR-001)
│   ├── numbers.py           # numbers with units (km², mm, m³/s)
│   ├── probability.py       # exceedance probability and return period (p. 4.4)
│   ├── dates.py             # dates and periods
│   ├── stations.py          # station names → IMGW station list
│   ├── paths.py             # file paths mentioned in the command
│   └── results.py           # result numbers mentioned in the command, e.g. "#3" (p. 5.2)
├── chains/
│   └── resolver.py          # chain building from input/output dependencies (v0.2)
├── eval/
│   ├── runner.py            # retman-eval: runs the test command set, prints the report (p. 8.2)
│   └── commands.jsonl       # test command set, shipped as package data (p. 8.1)
├── testing.py               # test helpers: fake backend, manifest validation
├── exceptions.py            # RetmanError hierarchy, e.g. PlanNotConfirmedError (p. 6.3)
├── doctor.py                # environment check (p. 7.2)
├── add_tool.py              # retman add-tool: installs a known tool via uv (v0.5+, p. 9.4)
├── cli.py                   # terminal conversation built on core/dialog.py (p. 6.4)
└── config.py                # central config file: location, loading, `retman init` (p. 9.1)
```

### 3.2. Adaptery: jak Retman łączy się z narzędziami [N-03], [W-06]

#### 3.2.1. Zasada: narzędzia nic nie wiedzą o Retmanie

Narzędzia nie zawierają żadnego kodu, plików ani zależności związanych z Retmanem.
Wszystko, czego Retman potrzebuje, mieszka w repo Retmana, a z narzędzi korzysta on wyłącznie
przez ich **publiczne API** — tak samo jak każdy inny użytkownik tych bibliotek.

Od narzędzi Retman oczekuje tylko dobrych praktyk, które są korzystne niezależnie od niego:
- **stabilne publiczne API** i wersjonowanie semantyczne (zmiana łamiąca zgodność = nowa wersja główna),
- **podpowiedzi typów**, zwłaszcza `Literal` (lub `Enum`) dla wyborów i `Path` dla plików,
- **docstringi w stylu NumPy** (styl już stosowany we wszystkich narzędziach).

#### 3.2.2. Co mieszka w Retmanie

```
retman/tools/hydrolog/
├── manifest.py    # operations: params, inputs, outputs, supported versions (p. 4.1)
├── handlers.py    # thin wrappers around the hydrolog public API (p. 3.2.4)
└── pl.toml        # Polish texts and synonyms (p. 4.2)
```

| Element | Rola |
| --- | --- |
| **Manifest** | opis operacji: parametry, dozwolone wartości, wejścia i wyjścia, obsługiwane wersje narzędzia |
| **Handlery** | cienkie funkcje, które wywołują publiczne API narzędzia i zamieniają wyniki na pliki |
| **Tłumaczenia** | polskie teksty i synonimy dla basala i użytkownika |
| **Wspólny adapter** | jeden dla wszystkich narzędzi: waliduje parametry, wywołuje handler, buduje `Result` |
| **Rejestr rodzajów danych** | nazwy `kind` i ich formaty plików (p. 3.2.6) |

Zasady:
- **Każda operacja jest opisana raz**, przy narzędziu, które ją faktycznie wykonuje. Hydrograf
  importuje Hydrologa, ale opis Hydrografa nie powtarza operacji Hydrologa.
- Procedury złożone, które narzędzie już ma (np. w Hydrografie), są **jedną operacją**.
  Retman nie odtwarza ich krok po kroku.

#### 3.2.3. Rola dokumentacji narzędzi

Dokumentacja narzędzi (sygnatury funkcji, typy, docstringi) jest **źródłem, z którego Retman
generuje i sprawdza swoje opisy**. Nie jest czytana w trakcie działania.

**Dwa narzędzia deweloperskie** (`retman.devtools`, dla autora, nie dla użytkownika końcowego):

1. **Generator szkiców**

   ```bash
   retman-scaffold hydrolog.peak_flow
   ```

   Odczytuje sygnaturę i docstring funkcji (statycznie, bez uruchamiania narzędzia, np. biblioteką
   `griffe`), w tym sekcje `Parameters` i `Returns` docstringów w stylu NumPy, i tworzy szkic:
   wpis w manifeście, szkielet handlera i puste pola w `pl.toml`.
   Autor uzupełnia to, czego w dokumentacji nie ma (tabela niżej).

2. **Kontrola rozjazdów**

   ```bash
   retman-scaffold --check
   ```

   Porównuje opisy przechowywane w Retmanie z aktualnym publicznym API narzędzi i zgłasza
   różnice: nowe, usunięte lub przemianowane parametry, zmienione dozwolone wartości (`Literal`),
   zmienione wartości domyślne. Uruchamiana w CI Retmana.

**Co da się wyczytać z dokumentacji, a co trzeba dopisać:**

| Informacja | Z dokumentacji? |
| --- | --- |
| parametry, typy, wartości domyślne | tak (sygnatura) |
| dozwolone wybory | tak, jeśli `Literal` lub `Enum` |
| opis po angielsku | tak (docstring) |
| pliki wejściowe i wyjściowe | częściowo (`Path`); rodzaj danych (`kind`) trzeba dopisać |
| zakresy wartości | tylko jeśli są w docstringu w ustalonej formie; zwykle trzeba dopisać |
| polskie teksty i synonimy | nie — trzeba dopisać |
| które funkcje udostępnić w Retmanie | nie — decyzja autora |

**Dlaczego dokumentacja nie jest czytana w trakcie działania:**
1. nie zawiera wszystkich potrzebnych informacji (tabela wyżej),
2. mały model nie zbuduje wiarygodnie wywołania funkcji na podstawie samego opisu,
3. zmiana docstringu zmieniałaby po cichu zachowanie Retmana — a opisy przechowywane
   w Retmanie są przejrzane, przetestowane i zmieniają się tylko świadomie.

#### 3.2.4. Handler

Handler mieszka w Retmanie i tłumaczy „język Retmana” na wywołanie publicznego API narzędzia:

```python
# retman/tools/hydrograf/handlers.py
from pathlib import Path

import hydrograf  # public API only


def delineate_catchment(params: dict, inputs: dict[str, Path], output_dir: Path) -> dict:
    """
    Delineate a catchment for a point using the hydrograf public API.

    params     – validated parameter values, e.g. {"point": (52.41, 16.93)}
    inputs     – input files by input name (none for this operation)
    output_dir – the only directory the handler may write to
    """
    lat, lon = params["point"]
    catchment = hydrograf.delineate(lat=lat, lon=lon)  # illustrative name of a public function

    out_file = output_dir / "catchment.geojson"
    catchment.to_geojson(out_file)                     # illustrative method

    return {
        "values": {"area_km2": catchment.area_km2},     # short results
        "files": {"catchment_characteristics": out_file},  # key = output kind
        "warnings": [],
    }
```

> Nazwy funkcji Hydrografa w przykładzie są poglądowe.

Zasady handlera:
1. **Tylko publiczne API narzędzia** — żadnych odwołań do elementów prywatnych (`_nazwa`).
2. **Dane wejściowe przychodzą jako pliki**, wyniki wychodzą jako pliki w `output_dir`.
   Klucze w `files` to rodzaje danych (`kind`, p. 3.2.6). Zamiana obiektów narzędzia na pliki
   (i z powrotem) to zadanie handlera.
3. **Żadnej rozmowy z użytkownikiem**: bez `input()` i `print()`. Dopytywanie i komunikaty
   to zadanie Retmana.
4. **Błędy zgłasza zwykłym wyjątkiem.** Wspólny adapter go przechwytuje i zwraca
   `Result(ok=False)`; awaria jednego narzędzia nie blokuje pozostałych.
5. **Zapis tylko do `output_dir`.** Handler nie zmienia plików użytkownika.

#### 3.2.5. Co robi wspólny adapter

1. **Przy starcie:** dla każdego narzędzia z `retman/tools/` sprawdza, czy jest zainstalowane
   i czy jego wersja mieści się w obsługiwanym zakresie (p. 3.2.7). Wczytuje opisy i je waliduje:
   unikalność identyfikatorów, znane rodzaje danych, komplet tłumaczeń. Operacje narzędzi
   niezainstalowanych są niedostępne (`retman doctor` podpowiada, jak je doinstalować).
2. **Przy planowaniu:** zamienia manifesty na wewnętrzne obiekty `Operation`, z których korzysta pipeline.
3. **Przy wykonaniu:** dopiero teraz importuje handler i narzędzie (szybszy start, a uszkodzone
   narzędzie nie psuje reszty), przygotowuje `output_dir` i pliki wejściowe, wywołuje handler,
   sprawdza zwrócone pliki z deklaracją `outputs`, buduje `Result` i zapisuje go w przestrzeni roboczej.

#### 3.2.6. Rejestr rodzajów danych (`kind`)

Rodzaj danych to nazwa + format pliku + prosty walidator, np.:

| `kind` | Format | Walidator sprawdza m.in. |
| --- | --- | --- |
| `catchment_characteristics` | GeoJSON z atrybutami | geometria poligonu, wymagane atrybuty (powierzchnia itd.) |
| `precipitation_series` | CSV | kolumny daty i wartości, jednostka |

Rejestr jest w Retmanie. Narzędzia nie znają tych nazw — zamianą ich obiektów na pliki
danego rodzaju zajmują się handlery. Jeden wynik może zawierać kilka plików tego samego
rodzaju (np. arkusze NMT), więc `files` przypisuje rodzajowi listę ścieżek.

Rodzaje danych Kartografa (ADR-004) — format jest taki, jaki zwraca Kartograf; walidator
sprawdza rozszerzenie i nagłówek pliku, bez bibliotek geoprzestrzennych:

| `kind` | Format | Walidator sprawdza m.in. |
| --- | --- | --- |
| `dem` | NMT: ESRI ASCII Grid (`.asc`, arkusze) albo GeoTIFF (`.tif`, wycinek) | rozszerzenie; nagłówek `ncols` (ASC) albo sygnatura TIFF |
| `dsm` | NMPT: jak `dem` | jak `dem` |
| `orthophoto` | GeoTIFF (`.tif`) | sygnatura TIFF |
| `topographic_vector` | BDOT10k: GeoPackage (`.gpkg`) albo Shapefile (`.shp`) | nagłówek SQLite (GPKG) albo kod pliku Shapefile |

Lista rodzajów pozostałych narzędzi to otwarta kwestia (rozdz. 12).

#### 3.2.7. Wersje i zgodność

Pilnowanie zgodności to rola Retmana, nie narzędzi. Narzędzia rozwijają się niezależnie,
a Retman dostosowuje się do nich:

- Każde narzędzie ma w manifeście **obsługiwany zakres wersji** (np. `">=1.1,<2"`), odpowiadający
  tagom wydań w repozytorium narzędzia na GitHubie. Retman sprawdza wersję zainstalowanego
  narzędzia przy starcie (p. 3.2.5); sam z siebie narzędzi nie instaluje (p. 9.3, 9.4).
- **CI Retmana** uruchamia testy handlerów na najstarszej i najnowszej obsługiwanej wersji
  każdego narzędzia, a regularnie (np. co noc) także na bieżącej gałęzi głównej narzędzi —
  zmiana API, która zepsułaby Retmana, wychodzi od razu.
- **Kontrola rozjazdów** (`retman-scaffold --check`, p. 3.2.3) działa w tym samym CI.
- `retman doctor` pokazuje zainstalowaną wersję każdego narzędzia na tle obsługiwanego zakresu.

#### 3.2.8. Testy narzędzi

Wszystkie testy związane z narzędziami są w repo Retmana:
- walidacja manifestów (identyfikatory, rodzaje danych, komplet tłumaczeń),
- testy handlerów na prawdziwych narzędziach z małymi danymi testowymi,
- kontrola rozjazdów z aktualnym API.

#### 3.2.9. Narzędzia ekosystemu

| Narzędzie | Przykładowy zakres operacji | Zależy od |
| --- | --- | --- |
| Kartograf | pobieranie danych przestrzennych | — |
| IMGWTools | pobieranie danych pomiarowych IMGW | — |
| Hydrolog | obliczenia hydrologiczne (przepływy, metody) | — |
| BasicHydraulics | proste obliczenia hydrauliczne | — |
| Hydrograf | wyznaczanie zlewni, procedury złożone | Hydrolog (i inne) |

Kolumna „Przykładowy zakres” jest orientacyjna; konkretne operacje ustala PRD.
Narzędzia innych autorów obsługuje się tak samo: opis i handlery w `retman/tools/`.

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
        question – question text in the user's language (from translation files)
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

1. **Maks. 10 opcji na pytanie.** Gdy operacji będzie więcej, rozpoznanie jest **dwustopniowe**:
   najpierw kategoria (np. opady, przepływy, zlewnia), potem operacja w kategorii.
2. **Słaby w dokładnych liczbach.** Wartości liczbowe zawsze wyciągają ekstraktory (krok ③).
3. **Kolejność opcji ma znaczenie.** basal uśrednia kolejność prostą i odwróconą; mimo to
   testy (rozdz. 8) muszą sprawdzać stabilność przy przetasowaniu opcji.
4. **Pytać w języku polecenia.** Pytania i opisy opcji muszą istnieć w pliku tłumaczeń dla
   języka polecenia (p. 4.2).
5. **Opcja „nie da się ustalić”.** Każde pytanie o parametr, który może nie paść w poleceniu,
   ma dodatkową opcję `unspecified` („polecenie tego nie określa”).
6. **Opcja „żadna z powyższych”** [W-03]. Pytanie o operację (krok ①) zawsze zawiera opcję
   `out_of_scope` („polecenie nie dotyczy żadnej z dostępnych operacji”). Jej wybór kończy
   się komunikatem o tym, co Retman potrafi, a nie zgadywaniem najbliższej operacji.
   Opcja liczy się do limitu 10 opcji.

---

## 4. Rejestr operacji

### 4.1. Manifest — definicja operacji

Operacje każdego narzędzia opisuje manifest w `retman/tools/<narzędzie>/manifest.py`:
zwykły słownik Pythona, po angielsku. Szkic manifestu można wygenerować z dokumentacji
narzędzia (p. 3.2.3). Każda operacja deklaruje też **co przyjmuje** (`inputs`) i **co zwraca**
(`outputs`) — na tej podstawie działa przestrzeń robocza (rozdz. 5), a w v0.2 łańcuchy (p. 4.5).

```python
# retman/tools/hydrolog/manifest.py
MANIFEST = {
    "tool": "hydrolog",
    "distribution": "hydrolog",              # package name for the installed-version check
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

### 4.2. Teksty dla użytkownika i modelu (pliki tłumaczeń)

Pytania do basala, opisy opcji i etykiety w planie są w plikach tłumaczeń, z kluczami
odpowiadającymi identyfikatorom z manifestu. Każde narzędzie ma w Retmanie własny plik.

```toml
# retman/tools/hydrolog/pl.toml

[operations.peak_flow]
label = "Obliczenie przepływu maksymalnego"
description = "Obliczenie przepływu maksymalnego o zadanym prawdopodobieństwie: przepływ miarodajny, woda stuletnia"

[operations.peak_flow.params.method]
label = "Metoda"
question = "Jaką metodą policzyć przepływ?"
options.punzet = "Metoda Punzeta"
options.bogdanowicz_stachy = "Metoda Bogdanowicz-Stachy"
options.scs_cn = "Metoda SCS-CN"

[operations.peak_flow.params.probability]
label = "Prawdopodobieństwo przewyższenia"
```

Zasady:
- `label` operacji to krótka nazwa pokazywana użytkownikowi (plan, pytania, lista operacji);
  `description` trafia tylko do modelu decyzyjnego i może zawierać synonimy i określenia
  potoczne, bo to one pomagają dopasować polecenie. To samo dotyczy opisów opcji.
- Parametr `free` ma też `example` (przykład formatu w pytaniu), a każdy parametr może
  mieć `help` (odpowiedź na `?`, p. 6.4).
- Test automatyczny sprawdza, że każda operacja, parametr i opcja ma tekst w każdym
  obsługiwanym języku. Brak tłumaczenia = test nie przechodzi.

### 4.3. Typy parametrów i pola operacji

| Typ parametru | Skąd wartość | Przykłady |
| --- | --- | --- |
| `choice` | model decyzyjny, wybór z listy | metoda, rodzaj danych, typ analizy |
| `free` | ekstraktor w kodzie | współrzędne, data, prawdopodobieństwo, powierzchnia, stacja, ścieżka pliku |
| `bool` | model decyzyjny, tak/nie | „czy uwzględnić retencję?” |

Dodatkowe klucze parametrów: `required`, `default`, `multiple` (kilka wartości naraz),
`range` (dozwolony zakres dla liczb), `accepts` (które rodzaje wartości ekstraktora
przyjmuje operacja, np. ekstraktor `area` daje godło arkusza, prostokąt, kod TERYT albo plik
z geometrią, a pobranie BDOT10k przyjmuje tylko `["teryt", "bbox", "sheet"]`), `depends_on`
(parametr dotyczy tylko wybranych wartości innego parametru `choice`, np. rozdzielczość tylko
dla NMT: `{"product": ["dem"]}`).

| Pole operacji | Znaczenie |
| --- | --- |
| `id` | identyfikator (po angielsku), unikalny w całym Retmanie |
| `category` | kategoria (do dwustopniowego rozpoznania w v0.2) |
| `description` | krótki opis po angielsku (dla programistów; tekst dla użytkownika jest w tłumaczeniach) |
| `inputs` | wejścia: nazwa + rodzaj danych (`kind`); źródło to plik, przestrzeń robocza, (v0.2) wcześniejszy krok łańcucha |
| `outputs` | rodzaje danych zwracanych przez operację |
| `params` | parametry |
| `handler` | ścieżka do funkcji handlera w Retmanie (`moduł:funkcja`) |

### 4.4. Prawdopodobieństwo i okres powtarzalności [W-08]

Prawdopodobieństwo jest **liczbą**, bo obliczenia można wykonać dla dowolnej wartości.
Wyciąga je ekstraktor `probability` w kodzie, bez udziału modelu.

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
| „Q100”, „Q500” | p = 100% i więcej jest niemożliwe | przyjmuje T (1%, 0,2%) i pokazuje to w planie |
| „dla 1”, „dla 0,5” (liczba bez „%”, bez „Q” i bez okresu w latach) | 1% czy p = 1? 0,5% czy p = 0,5? | **zawsze** pyta — także gdy jeden z odczytów jest niemożliwy |

**Walidacja:** `0 < p < 1` oraz zakres `range` z manifestu operacji (metoda może mieć własne
ograniczenia). Wartość poza zakresem → komunikat z dozwolonym zakresem.

### 4.5. Łańcuchy operacji (v0.2) [W-12]

Deklaracje `inputs`/`outputs` są wpisywane już w v0.1, gdzie służą do wyszukiwania danych
w przestrzeni roboczej (rozdz. 5). Resolver opisany poniżej powstaje w v0.2.

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
Wyniki trafiają do podfolderu wyników w tym folderze; jego nazwę określa plik centralny
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
poleceń ani odpowiedzi użytkownika; pozostałe dane audytowe są zapisywane zawsze (PRD W-15).

**1. Dane audytowe w `result.json`** (przy każdym wyniku):

| Sekcja | Zawartość |
| --- | --- |
| `number`, `operation` | numer wyniku i wykonana operacja |
| `command` | polecenie użytkownika i odpowiedzi na pytania Retmana (jeśli `journal_commands = true`, p. 9.1) |
| `params` | każda użyta wartość razem ze źródłem: `command`, `default`, `workspace`, `known`, `user` (p. 7.1) |
| `decisions` | decyzje modelu: pytanie, wybrana opcja, prawdopodobieństwa, pewność i jej metoda (`basal`, `logprobs`, `consistency`, `none`) |
| `inputs` | źródło każdego wejścia: wynik #N albo plik — ścieżka i suma kontrolna SHA-256, żeby było widać, czy plik później się zmienił |
| `outputs`, `values`, `files`, `warnings`, `error` | jak w `Result` (p. 7.3); pliki wynikowe także z sumami kontrolnymi |
| `environment` | wersja Retmana, wersje użytych narzędzi, model decyzyjny (backend, nazwa, adres serwera), wersja Pythona, system |
| `timing` | zatwierdzenie planu, początek i koniec wykonania, czas trwania |

**2. Dziennik projektu** — `retman-output/journal.jsonl`, jeden wiersz na zdarzenie:

| Zdarzenie | Zapisywane |
| --- | --- |
| polecenie | treść (jeśli `journal_commands = true`), czas, identyfikator sesji |
| pytanie i odpowiedź | treść pytania, odpowiedź użytkownika (jeśli `journal_commands = true`) |
| plan | pokazany plan i jego decyzja: **zatwierdzony / odrzucony / zmieniony / anulowany** |
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

**3. Log techniczny** — osobny, do diagnozowania problemów Retmana (połączenia, czasy odpowiedzi,
błędy), w katalogu logów użytkownika: Linux `~/.local/state/retman/`, macOS
`~/Library/Logs/retman/`, Windows `%LOCALAPPDATA%\retman\Logs\`. **Bez treści poleceń.**
Poziom szczegółowości ustawia plik centralny (`diagnostic_level`, p. 9.1).

**Trzy rzeczy, których nie należy mylić:**

| Co | Gdzie | Treść poleceń |
| --- | --- | --- |
| dziennik projektu + dane audytowe | folder projektu | **tak** — to zapis pracy użytkownika; można wyłączyć (`journal_commands`) |
| log techniczny | katalog logów użytkownika | nie |
| zbieranie poleceń do ulepszania zbioru testowego | — | domyślnie wyłączone (`collect_commands`, rozdz. 10) |

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
| Wybrano `out_of_scope` | Informuje, że polecenie nie pasuje do żadnej operacji, i pokazuje listę dostępnych |
| Wymagany parametr = `unspecified` | Pyta o ten parametr, pokazując listę opcji |
| Pewność parametru < próg | Pyta: „Czy chodziło o X?” |
| Ekstraktor nic nie znalazł | Prosi o wartość i podaje przykład formatu |
| Ekstraktor znalazł kilka dopasowań (np. kilka stacji o podobnej nazwie) | Pokazuje kandydatów do wyboru |
| W projekcie jest kilka pasujących wyników (np. kilka zlewni) | Pyta, którego użyć (p. 5.3) |
| Zapis niejednoznaczny (np. „Q50”, p. 4.4) | Pyta, który odczyt jest właściwy |
| Brak wymaganego wejścia (ani w pliku, ani w przestrzeni roboczej) | Informuje, czego brakuje i jak to uzyskać |
| Wartość poza zakresem (np. współrzędne poza Polską, prawdopodobieństwo poza `range`) | Informuje i prosi o poprawkę |
| Prawdopodobnie zamieniona kolejność współrzędnych | Patrz uwaga niżej |

**Uwaga o współrzędnych.** Kolejność osi bywa myląca: w WGS84 ludzie piszą raz „szerokość, długość”,
raz odwrotnie, a w układzie PL-1992 (EPSG:2180) oś X oznacza kierunek północny, odwrotnie niż
w intuicyjnym „X = wschód”. Ekstraktor rozpoznaje układ i kolejność po zakresach wartości dla Polski.
Gdy interpretacja jest niejednoznaczna, Retman pokazuje w planie, jak odczytał współrzędne
(np. „52.41° N, 16.93° E”), i prosi o potwierdzenie.

### 6.2. Progi pewności [N-05]

- **Domyślnie** (`"auto"`) Retman bierze progi z kalibracji basala (`CALIBRATION.json`, poziom błędu 1%).
  Wartość `"auto"` jest dozwolona tylko z `backend = "basal"`.
- Można je **nadpisać** liczbą w konfiguracji (p. 9.1).
- Progi basala dobrano na prostych formatach pytań (opisy opcji, pytania tak/nie). Dla pytań
  Retmana należy je **dostroić na własnym zbiorze testowym** (rozdz. 8) i wpisać do konfiguracji.
- Osobny próg dla rozpoznania operacji i dla parametrów.
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
- Parametry uzupełnione wartością domyślną, odczyty niejednoznacznych zapisów oraz wejścia
  wzięte z przestrzeni roboczej są wyraźnie oznaczone, żeby użytkownik mógł je zmienić.
- W API Pythona `execute()` przyjmuje wyłącznie plan potwierdzony przez `plan.confirm()`.
  Bez tego zgłasza błąd `PlanNotConfirmedError`.
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
  (lista numerowana) bez wpisywania polecenia od nowa.
- Odpowiedzi trafiają do planu ze źródłem `user` (p. 7.1).

**Bez terminala** (skrypty, potoki, CI — wejście nie jest terminalem) Retman nie zadaje pytań
i niczego nie wykonuje. Wypisuje, czego brakuje albo jaki byłby plan, i kończy pracę
z odpowiednim kodem wyjścia. To konsekwencja obowiązkowego potwierdzenia (p. 6.3).

| Kod wyjścia | Znaczenie |
| --- | --- |
| 0 | operacja wykonana (albo pokazany plan przy `--plan-only`) |
| 1 | błąd (np. brak połączenia z modelem, błąd narzędzia) |
| 2 | potrzebne odpowiedzi lub potwierdzenie, a wejście nie jest terminalem |
| 3 | przerwane przez użytkownika |

**Jedna logika, wiele interfejsów.** Rozmowa w terminalu to tylko warstwa wyświetlania. Pytania
tworzy i odpowiedzi sprawdza `core/dialog.py`, dostępny też z Pythona (`plan.questions`,
`plan.answer()`, p. 7.1). Dzięki temu te same pytania obsłużą później serwer MCP, API HTTP i GUI
(p. 7.4, 7.5).

**Zależności:** w v0.1 wyłącznie biblioteka standardowa Pythona (`input()`), bez bibliotek
do interfejsów terminalowych.

---

## 7. Interfejsy

### 7.1. Biblioteka Python + CLI (v0.1) [W-11]

**CLI:**

```bash
retman "Pobierz dobowe opady ze stacji Poznań z lat 2000–2020"   # one command (p. 6.4)
retman                     # session: many commands in one conversation (p. 6.4)
retman --plan-only "..."   # show the plan only, run nothing
retman --explain "..."     # show model decisions and confidences (diagnostics)
retman doctor              # environment check (p. 7.2)
retman results             # list results of the current project (p. 5.2)
retman log                 # show the project journal (p. 5.4)
retman init                # create the central config file (p. 9.1); a wizard from v0.5
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

print(plan.summary())                    # human-readable plan; defaults and workspace inputs are marked
if input("Execute? [y/n] ") == "y":
    plan.confirm()                       # explicit confirmation is mandatory
    result = retman.execute(plan)        # raises PlanNotConfirmedError without confirm()

    if result.ok:
        print(result.summary)            # short description of the result
        print("Files:", result.files)
    else:
        print("Error:", result.error)
```

`Retman.from_config()` bez argumentu wczytuje plik centralny (p. 9.1) — ten sam, z którego
korzysta CLI; jawną ścieżkę można podać opcjonalnie, np. w testach.

| Element | Znaczenie |
| --- | --- |
| `plan.questions` | lista otwartych pytań (`Question`); pusta, gdy plan jest kompletny |
| `Question` | `name` (parametr), `type` (`choice`, `value`, `confirm`), `text` (treść w języku użytkownika), `options` (dla wyborów), `default`, `example` (przykład formatu), `error` (dlaczego poprzednia odpowiedź była błędna) |
| `plan.answer(name, answer)` | zwraca nowy plan z odpowiedzią; numer opcji albo własne słowa |

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
same_plan = Plan.from_dict(state)
```

Źródło każdej wartości w planie: `command` (z polecenia), `default` (wartość domyślna),
`workspace` (wcześniejszy wynik), `known` (podana z zewnątrz, np. w GUI), `user` (odpowiedź na pytanie Retmana).

### 7.2. `retman doctor` — sprawdzenie środowiska [W-10]

`retman doctor` w jednym miejscu pokazuje, co działa, co nie i jak to naprawić.

**Co sprawdza:**

| Obszar | Sprawdzenia |
| --- | --- |
| Konfiguracja | ścieżka i poprawność pliku centralnego; folder bieżącego projektu i czy folder wyników jest zapisywalny |
| Model decyzyjny | **adres serwera**; czy odpowiada; jaki model jest załadowany; **pytanie testowe** z oczywistą odpowiedzią (czy model odpowiada sensownie); skąd pochodzi pewność (`basal`, `logprobs`, zgodność, niedostępna) i progi (`"auto"` z backendem innym niż `basal` to błąd konfiguracji, p. 6.2) |
| Model tekstowy | czy jest włączony; **adres serwera**; czy odpowiada |
| Narzędzia | które są zainstalowane; czy ich wersje mieszczą się w obsługiwanym zakresie; liczba dostępnych operacji |
| Tłumaczenia | komplet tekstów dla języka z `[ui] language` |
| Przestrzeń robocza | folder wyników bieżącego projektu; liczba wyników; czy `result.json` dają się odczytać |

**Przykładowy wynik:**

```
$ retman doctor
Retman 0.1.0

Konfiguracja
  ✓ plik centralny: ~/.config/retman/retman.toml
  ✓ projekt: ~/projekty/zlewnia-a → wyniki w retman-output/ (5 wyników, zapis możliwy)

Model decyzyjny
  ✓ basal-serve: http://127.0.0.1:8000 (lokalnie)
  ✓ model: basal-1.5-mini, pytanie testowe: poprawna odpowiedź
  ! progi pewności: "auto" — zalecane dostrojenie na własnym zbiorze testowym (p. 6.2)

Narzędzia
  ✓ imgwtools  0.4.2   obsługiwane >=0.4,<0.5   3 operacje
  ! hydrolog   2.0.0   obsługiwane >=1.1,<2      wersja spoza zakresu — operacje wyłączone
  ✗ kartograf  nie zainstalowany                 → uv tool install … --with git+https://github.com/Daldek/Kartograf (p. 9.4)

Tłumaczenia (pl)
  ✓ komplet

Model tekstowy
  – wyłączony ([text] backend = "none")
```

Adres każdego modelu jest pokazany bez oceniania go — o tym, gdzie działa model, decyduje
użytkownik w pliku centralnym (rozdz. 10).

Gdy serwer modelu nie działa, raport podpowiada, jak go uruchomić, np.:

```
Model decyzyjny
  ✗ basal-serve nie odpowiada (http://127.0.0.1:8000) → uruchom basal-serve (instrukcja w README)
```

Zasady:
- Każdy problem ma **podpowiedź, jak go naprawić** (polecenie, ustawienie albo odnośnik do README).
- Kod wyjścia: `0` gdy da się pracować, `1` gdy coś blokuje pracę (np. brak modelu albo brak narzędzi).
- `retman doctor --json` — ten sam raport w formacie do wklejenia w zgłoszeniu błędu.
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
| `values` | wyniki liczbowe lub krótkie (np. `{"peak_flow_m3s": 42.7}`) |
| `files` | ścieżki do zapisanych plików, według rodzaju danych |
| `warnings` | ostrzeżenia z narzędzia (np. luki w danych) |
| `error` | opis błędu, gdy `ok = False` |
| `summary` | krótki opis w języku użytkownika (szablon albo `TextBackend`) |

Pliki trafiają do folderu wyników bieżącego projektu, w podkatalogu z numerem wyniku i nazwą
operacji, np. `retman-output/004_fetch_imgw_data/`, razem z plikiem `result.json`, który zawiera też dane audytowe (p. 5.4).

### 7.4. Integracja z GUI narzędzi (v0.5+) [W-13]

Scenariusze użytkownika opisuje PRD. Tu: jak je zrealizować technicznie.

**Model:** plan Retmana to **stan formularza** — operacja, wartości parametrów i źródło każdej
z nich. Potwierdzenie planu odpowiada przyciskowi „Uruchom” w GUI. Scenariusz „część wypełniam
w GUI, resztę ustalam z Retmanem” to plan z częścią wartości ze źródła `known`.

**Co v0.1 zapewnia już teraz** (mały koszt, otwarta droga na później):
- plan serializowany do JSON (`to_dict()` / `from_dict()`), ze źródłem każdej wartości (p. 7.1),
- wartości znane z zewnątrz (`known`): Retman ich nie zmienia, uzupełnia tylko brakujące,
- rozdzielenie planowania od wykonania (p. 6.3),
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
| Serwer MCP | v0.3 | te same operacje dostępne dla dowolnego klienta MCP |
| API HTTP | v0.4 | dostęp do Retmana dla aplikacji webowej i integracji z GUI (model na serwerze jednostki działa bez tego od v0.1, p. 3.3.4) |
| Czat w przeglądarce | v0.5+ | dla użytkowników końcowych |

---

## 8. Testy i ocena jakości

Docelowe wartości miar jakości ustala PRD. Tu: jak je mierzyć.

### 8.1. Zbiór poleceń testowych

Plik `retman/eval/commands.jsonl` (dane pakietu, instalowane razem z Retmanem), jedna linia =
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

Polecenie `retman-eval --backend basal` uruchamia zbiór i drukuje raport. Ten sam zbiór służy
do porównywania backendów (basal-1.5-mini vs basal-1.5 vs model generatywny).

`retman-eval` jest częścią **pakietu podstawowego** (p. 9.3), bez dodatkowych zależności. Każdy
użytkownik i wdrażający może nim dostroić progi pewności dla własnego modelu, co jest
obowiązkowe dla backendów innych niż basal (p. 6.2).

### 8.3. Testy jednostkowe i integracyjne

- Ekstraktory testowane bez modelu (czysty kod, `pytest`), w tym wszystkie formy z p. 4.4.
- Pipeline testowany z **atrapą backendu** (`FakeDecisionBackend`) — testy nie wymagają GPU.
- Wspólny adapter testowany na narzędziu-atrapie (manifest + handlery w testach).
- Opisy narzędzi: walidacja manifestów i tłumaczeń, testy handlerów na prawdziwych narzędziach,
  kontrola rozjazdów z API (p. 3.2.7–3.2.8).
- Przestrzeń robocza: zapis i odczyt `result.json`, numeracja wyników, reguły wyboru wejścia
  z p. 5.3 (w tym pytanie przy kilku kandydatach).
- Dziennik projektu: wpis dla każdego kroku, także dla odrzuconych planów, anulowania i błędów;
  komplet danych audytowych w `result.json` (p. 5.4).

---

## 9. Konfiguracja i wymagania techniczne

### 9.1. Plik centralny `retman.toml` [N-11]

Ustawienia **niezależne od projektu** — m.in. modele, progi pewności, język i prywatność — są
w **jednym pliku na komputerze**, w standardowym katalogu konfiguracji systemu:

| System | Ścieżka |
| --- | --- |
| Linux | `~/.config/retman/retman.toml` (albo `$XDG_CONFIG_HOME/retman/`) |
| macOS | `~/Library/Application Support/retman/retman.toml` |
| Windows | `%APPDATA%\retman\retman.toml` |

- `retman init` tworzy pełny plik ze wszystkimi ustawieniami i komentarzami. **Retman nie ma
  ukrytych wartości domyślnych** — każda wartość, której używa, jest widoczna w pliku.
  Bez pliku Retman nie startuje i podpowiada `retman init`. Od wersji łatwej (0.5+)
  `retman init` działa jako kreator: pyta, gdzie działa model, sprawdza połączenie i zapisuje
  plik (p. 9.4).
- `retman doctor` pokazuje ścieżkę używanego pliku.
- **Rzeczy zależne od projektu nie są w pliku centralnym.** Wyniki trafiają do folderu projektu
  (rozdz. 5); w pliku jest tylko nazwa podfolderu wyników.
- W pliku nie ma opisów narzędzi (manifestów) ani tekstów (tłumaczeń) — to część kodu Retmana,
  testowana w CI (p. 3.2, 4.2). Nie ma w nim też kluczy API, tylko nazwy zmiennych
  środowiskowych (rozdz. 10).

```toml
[decision]
backend = "basal"                   # "basal" (default) | "openai_compatible" | native providers (v0.2)
url = "http://127.0.0.1:8000"       # basal-serve running locally (started separately)
model = "basal-1.5-mini"
timeout_s = 30                      # how long to wait for the model server
# Generative model instead of basal, e.g. LM Studio:
# backend = "openai_compatible"
# url = "http://127.0.0.1:1234/v1"
# model = "<model-name>"
# api_key_env = "PROVIDER_API_KEY"  # external providers: NAME of the environment variable holding the key
# confidence = "auto"               # "auto" | "logprobs" | "consistency" | "none" (p. 3.3.3)
# consistency_runs = 3              # queries per decision for the consistency check (p. 3.3.3)
# With this backend [decision.thresholds] must be numbers tuned for the model (p. 6.2);
# with confidence = "none" the thresholds are ignored.

[decision.thresholds]
operation = "auto"      # "auto" = basal calibration, allowed only with backend = "basal"; after tuning set a number, e.g. 0.90
parameter = "auto"

[text]
backend = "none"        # from v0.2: "openai_compatible" (e.g. Bielik in LM Studio)
# url = "http://127.0.0.1:1234/v1"
# model = "<bielik-model-name>"

[ui]
language = "pl"         # language of questions, options and messages

[output]
results_dir = "retman-output"  # results folder created inside the project folder, i.e. where Retman runs (ch. 5)

[adapters]
# By default Retman enables every supported tool that is installed in a supported version.
# The optional "enabled" list only NARROWS that set.
# enabled = ["imgwtools", "kartograf"]

[log]
journal_commands = true    # store command texts and answers in the project journal (p. 5.4)
diagnostic_level = "info"  # technical log in the user's log directory: "debug" | "info" | "warning"

[privacy]
collect_commands = false   # true = collect commands to improve the test set (separate from the journal)
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
  **nie są** zależnościami podstawowymi.
- **basal (basal-serve) nie jest zależnością Retmana** — ani podstawową, ani opcjonalną.
  Backend `basal` to własne zapytanie HTTP, bez klienta z pakietu `basal` (p. 3.3.2).
- **Dystrybucja przez GitHub, bez PyPI.** Retman instaluje się z repozytorium, np.
  `uv tool install git+https://github.com/Daldek/Retman` (szczegóły: p. 9.4).
- Opisy narzędzi są wbudowane w Retmana (`retman/tools/`). **Retman nie instaluje niczego sam
  z siebie.** Narzędzia instaluje użytkownik razem z Retmanem, w tym samym środowisku (p. 9.4),
  a od wersji łatwej także na wyraźne polecenie `retman add-tool` (z potwierdzeniem). Retman
  sprawdza ich wersje, a `retman doctor` podpowiada, jak doinstalować brakujące.
- Retman **nie ma dodatków instalujących narzędzia** (`retman[hydrograf]` itp.). Zależności
  wskazujące bezpośrednio na repozytoria Git wymuszałyby sztywne wersje zamiast zakresów
  i zablokowałyby ewentualną późniejszą publikację na PyPI.
- Narzędzia deweloperskie (`retman-scaffold`) jako osobny dodatek: `retman[dev]`. `retman-eval`
  należy do pakietu podstawowego razem ze zbiorem poleceń testowych (p. 8.2).

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
#    (@v0.1.0 = a tagged release, so testers have a stable version)
uv tool install "git+https://github.com/Daldek/Retman@v0.1.0" \
    --with "git+https://github.com/Daldek/IMGWTools" \
    --with "git+https://github.com/Daldek/Hydrolog"

# 3. Model server: installed separately, following basal's instructions, then started
basal-serve --model Remek/basal-1.5-mini --mode <depends on hardware>

# 4. Central config and environment check
retman init
retman doctor
```

- **Dodanie narzędzia później:** to samo polecenie z dodatkowym `--with`.
- **Aktualizacja:** to samo polecenie z nowym tagiem wydania.
- **basal-serve** trzeba uruchomić przed pracą z Retmanem; jeśli nie działa, `retman doctor`
  i komunikat błędu podpowiadają, jak go uruchomić (p. 7.2).

#### Wersja łatwa (0.5+, przed 1.0)

1. **Skrypt instalacyjny** — `install.sh` (Linux, macOS) i `install.ps1` (Windows) w repozytorium
   Retmana. Instaluje `uv`, Retmana i narzędzia wybrane z listy, czyli wykonuje kroki 1–2
   wersji trudnej.
2. **Kreator `retman init`** — pyta, gdzie działa model (na tym komputerze / na serwerze jednostki
   pod podanym adresem / u dostawcy), od razu sprawdza połączenie i zapisuje plik centralny (p. 9.1).
3. **`retman add-tool <narzędzie>`** — doinstalowuje znane Retmanowi narzędzie do jego środowiska,
   w wersji z obsługiwanego zakresu, przez `uv`. Jak każda operacja wymaga potwierdzenia:

   ```
   $ retman add-tool kartograf
   Doinstaluję Kartograf 0.3.1 (obsługiwane wersje: >=0.3,<0.4) z GitHuba do środowiska Retmana.
   Wykonać? [t]ak / [n]ie
   ```

   Działa tylko dla narzędzi, które Retman zna (ma ich opisy w `retman/tools/`).
4. **Model** — przy serwerze jednostki użytkownik niczego nie instaluje, tylko wpisuje adres
   w kreatorze. Lokalnie dostaje instrukcję (albo osobny skrypt) dla basal-serve; Retman nie zawiera
   modelu (PRD N-10).

#### Sprawdzanie w CI

- **Test instalacji na czystych systemach** (Windows, Linux, macOS): instalacja Retmana ze wszystkimi
  narzędziami, a potem `retman doctor`. Zależności narzędzi (np. biblioteki geoprzestrzenne) uznano
  za niekłopotliwe — test potwierdza to na każdym systemie, zanim problem trafi do testerów.
- Od wersji łatwej ten sam test obejmuje skrypty instalacyjne.

---

## 10. Bezpieczeństwo i prywatność [N-04], [W-05]

- Każde wykonanie operacji wymaga potwierdzenia planu (p. 6.3), bez wyjątków w wersjach 0.x.
- Handlery zapisują wyłącznie do przydzielonego katalogu wyników (p. 3.2.4).
- Retman nie wysyła poleceń ani danych poza skonfigurowane backendy.
- Domyślna konfiguracja wskazuje wyłącznie na `localhost`.
- **Gdzie działa model, decyduje użytkownik** w pliku centralnym. Retman nie ocenia adresów
  i nie ostrzega; `retman doctor` pokazuje adres każdego modelu (p. 7.2).
- basal-serve nie ma własnej kontroli dostępu. Na serwerze jednostki zabezpieczenie dostępu
  należy do wdrażającego (wzmianka w README).
- **Klucze API** są odczytywane wyłącznie ze zmiennych środowiskowych (w konfiguracji jest tylko
  nazwa zmiennej). Nigdy nie trafiają do plików konfiguracyjnych, logów ani `result.json`.
- **Dziennik projektu i dane audytowe** zawierają treść poleceń, bo są zapisem pracy użytkownika;
  zostają w folderze projektu, a zapisywanie w nich treści poleceń i odpowiedzi można wyłączyć
  (`journal_commands = false`, p. 5.4).
- **Log techniczny** jest zapisywany lokalnie, bez treści poleceń (p. 5.4).
- Zbieranie treści poleceń do ulepszania zbioru testowego jest **opcjonalne i domyślnie wyłączone** (`[privacy] collect_commands`).
  Przekazywanie poleceń autorowi wymaga osobnej, wyraźnej zgody użytkownika i nigdy nie dzieje
  się automatycznie.

---

## 11. Komponenty w kolejnych wersjach

Zakres produktowy wersji opisuje PRD. Tu: które komponenty techniczne powstają w której wersji.

| Wersja | Komponenty |
| --- | --- |
| **0.1** | rdzeń pipeline, backend `basal` (domyślny) i `openai_compatible` (alternatywa), ekstraktory (w tym prawdopodobieństwo), wspólny adapter, opisy i handlery dla narzędzi z pierwszych operacji, `retman-scaffold` (szkice + kontrola rozjazdów), CI z testami na obsługiwanych wersjach narzędzi, pliki tłumaczeń (PL), CLI i API Pythona (w tym plan jako dane i `known`), `retman doctor`, przestrzeń robocza w folderze projektu (numerowane wyniki, wybór wejścia bez zgadywania, `retman results`), plik centralny i `retman init`, dziennik projektu i ślad audytowy (`retman log`), `retman-eval`, pomiary czasu odpowiedzi (p. 9.2), CI na Windows, Linux i macOS, w tym test instalacji na czystych systemach (p. 9.4) |
| 0.2 | resolver łańcuchów, kontrole sensowności między krokami, wznawianie łańcucha, nazwane wyniki, opis wyników przez model tekstowy, natywne API dostawców (opcjonalne), dwustopniowe rozpoznanie operacji, opisy i handlery pozostałych narzędzi ekosystemu |
| 0.3 | serwer MCP |
| 0.4 | API HTTP |
| 0.5+ | okno czatu dla ścieżki prostej, skrypty instalacyjne (`install.sh`, `install.ps1`), kreator `retman init`, `retman add-tool`, integracja z GUI (p. 7.4), pliki `en.toml` |

---

## 12. Otwarte kwestie techniczne

1. **Typy w publicznym API narzędzi** — docstringi są w stylu NumPy (ustalone). Do sprawdzenia:
   czy wybory (np. metody obliczeń) są typowane jako `Literal`/`Enum`, a pliki jako `Path`.
   Od tego zależy, ile generator szkiców wyczyta automatycznie.
2. **Ekstrakcja parametrów swobodnych** — czy wystarczy kod, czy w trudnych przypadkach
   (np. nazwa rzeki lub miejscowości zamiast współrzędnych) potrzebny będzie Bielik albo geokoder?
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
   Ustalone dla Kartografa (ADR-004); pozostałe narzędzia otwarte.
8. **Integracja z GUI** (p. 7.4) — wariant połączenia (A czy B) i technologia GUI, gdy GUI powstaną.
9. **LM Studio jako serwer modelu** — czy jego API zwraca `logprobs` i obsługuje odpowiedzi
   ustrukturyzowane (lista dozwolonych wartości). Od tego zależy jakość decyzji modeli
   generatywnych (p. 3.3.3).
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
