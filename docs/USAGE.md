# Praca z Retmanem

Przewodnik dla użytkownika: jak przygotować Retmana, jak wydawać polecenia, odpowiadać
na pytania, zatwierdzać plany i odnajdywać wyniki — w terminalu i z Pythona.

**Stan:** przed v0.1.0. Działają cztery operacje Kartografa 0.8.0 i 26 operacji IMGWTools 3.0.0
(p. 9) z modelem decyzyjnym zgodnym z API OpenAI (np. LM Studio); backend basal jeszcze nie powstał.

> **O przykładach.** Przebiegi poniżej zarejestrowano na Retmanie 0.1.0.dev0 z Kartografem 0.8.0
> i IMGWTools 3.0.0. Decyzje modelu podstawiono w nich atrapą (`FakeDecisionBackend`), więc z prawdziwym
> modelem Retman może zadać inne lub dodatkowe pytania — np. dopytać o operację albo o jej grupę, gdy
> model jest niepewny. Teksty pytań, planów i komunikatów są prawdziwe; ścieżki skrócono. Wykonanie
> w p. 5.2 zapisuje szereg z **magazynu testowego IMGWTools** (stacje fikcyjne, bez sieci); pobrań z GUGiK
> nie wykonywano, a raport w p. 5.4 powstał z zapisanej odpowiedzi GUGiK.

## Spis treści

1. [Przygotowanie](#1-przygotowanie)
2. [Folder projektu](#2-folder-projektu)
3. [Pierwsze polecenie](#3-pierwsze-polecenie)
4. [Odpowiadanie na pytania](#4-odpowiadanie-na-pytania)
5. [Plan, zmiana, sprawdzenie i wykonanie](#5-plan-zmiana-sprawdzenie-i-wykonanie)
6. [Wyniki i dziennik projektu](#6-wyniki-i-dziennik-projektu)
7. [Sesja, opcje i praca bez terminala](#7-sesja-opcje-i-praca-bez-terminala)
8. [Kody wyjścia](#8-kody-wyjścia)
9. [Co Retman potrafi teraz](#9-co-retman-potrafi-teraz)
10. [Retman w Pythonie](#10-retman-w-pythonie)
11. [Diagnostyka: `retman doctor`](#11-diagnostyka-retman-doctor)
12. [Dostrajanie progów: `retman-eval`](#12-dostrajanie-progów-retman-eval)
13. [Dobre praktyki i ograniczenia](#13-dobre-praktyki-i-ograniczenia)

---

## 1. Przygotowanie

Retman nie zawiera modelu językowego. Potrzebne są cztery rzeczy: Retman z narzędziami
w **jednym** środowisku, działający serwer modelu, ustawienia i magazyny danych narzędzi.

### 1.1. Instalacja

Instalację opisuje ARCHITECTURE 9.4. Do czasu wydania v0.1.0 nie ma tagu wydania, a tagów `v0.8.0`
Kartografa i `v3.0.0` IMGWTools jeszcze nie wypchnięto, więc instaluje się Retmana z gałęzi `develop`
i narzędzia z przypiętych commitów (te same, których używają testy, grupa `tools` w `pyproject.toml`):

```bash
uv tool install "git+https://github.com/Daldek/Retman@develop" \
    --with "kartograf @ git+https://github.com/Daldek/Kartograf@8e9bcbb058d11f06afae5a65e62f31870f69d169" \
    --with "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@0d98f3babeeeee49b2146a977b62bfa92114beea"
```

Dodatek `store` IMGWTools instaluje `pyarrow` (szeregi czasowe to pliki Parquet). Po wydaniu tagów
polecenie dostanie wersje `@v0.8.0` i `@v3.0.0`. Narzędzie zainstalowane w innym środowisku jest dla
Retmana niewidoczne; `retman doctor` (p. 11) podaje wtedy polecenie, które je doda.

### 1.2. Serwer modelu

Na razie Retman rozmawia z serwerem zgodnym z API OpenAI, np. LM Studio z załadowanym
modelem (sprawdzony: Bielik 11B, `docs/research/2026-10-11-lm-studio-openai-compatible.md`).
Serwer uruchamia się osobno, przed pracą z Retmanem.

### 1.3. Ustawienia i magazyny danych

Ustawienia Retmana to tabele `[retman]` pliku `nogat.toml`, wspólnego dla narzędzi Nogat. Leży w folderze
ustawień użytkownika (w Linuksie `~/.config/nogat/nogat.toml`); inny plik wskazuje zmienna `NOGAT_CONFIG`
albo opcja `--config PATH` przy poleceniu. Plik jest **opcjonalny**: każde ustawienie ma wartość domyślną
poza serwerem modelu (`[retman.decision]`), a zmienna środowiska przesłania plik. Wartość pochodzi
z pierwszego z miejsc:

1. opcja polecenia (na razie tylko `--config`, `--verbose`, `--quiet`);
2. zmienna `RETMAN_<KLUCZ>` — klucz z kropkami zamienionymi na `_`, np. `decision.url` to `RETMAN_DECISION_URL`;
3. zmienna `NOGAT_<KLUCZ>` — tylko dla kluczy wspólnych: `lang`, `log_level`, `data_dir`, `cache_dir`;
4. tabela `[retman]` pliku (podtabele: `[retman.decision]`, `[retman.tools.kartograf]` …);
5. tabela `[nogat]` pliku — tylko klucze wspólne;
6. wartość domyślna.

Wszystkie zmienne wymienia README i `.env.example`. Co Retman widzi i skąd to ma, pokazuje

```bash
retman config show           # tekst; z --json dokument retman-config/1
```

Pokazuje plik ustawień (także nieczytelny — wtedy z opisem błędu), każdy klucz z wartością i źródłem
(domyślna, zmienna albo plik), zmienną z kluczem dostawcy modelu (`jest` albo `brak`, nigdy wartość) oraz
magazyny narzędzi z rozmiarem. Magazyny i cache mają domyślnie miejsce w folderach użytkownika: magazyn
Kartografa w `<data_dir>/kartograf`, magazyn IMGWTools w `<data_dir>/imgw`, cache Kartografa
w `<cache_dir>/kartograf/metadata.db`, dane referencyjne IMGWTools w `<cache_dir>/imgw/reference`,
zbiór poleceń w `<data_dir>/retman/collected.jsonl` (`data_dir` i `cache_dir` to foldery danych i cache
użytkownika nogat; w Linuksie `~/.local/share/nogat` i `~/.cache/nogat`).

```bash
retman init        # dopisuje tabele [retman] do nogat.toml i tworzy foldery magazynów narzędzi
```

Wszystko to można zostawić domyślne, ale `retman init` zapisuje komplet ustawień w pliku, żeby nic
nie było ukryte. W terminalu pyta o zbieranie poleceń (p. 6.4) i o folder na **magazyny danych
narzędzi**, tworzy foldery, sprawdza, że dysk ma dowiązania twarde, zapisuje tabele, a na końcu — za
Twoją zgodą — tworzy magazyn IMGWTools (bez sieci). Przebieg (Enter przyjmuje wartość domyślną; ścieżki
skrócono):

```
$ retman init
Czy zbierać Twoje polecenia ze wszystkich projektów w jednym pliku (~/.local/share/nogat/retman/collected.jsonl)?
Zapisywane są: polecenie, plan, Twoje odpowiedzi i decyzje modelu — do budowy i strojenia zbioru testowego.
Plik zostaje na tym komputerze; nic nie jest nigdzie wysyłane. Ustawienie można zmienić w [retman.privacy] collect_commands.
Zbierać polecenia? [t]ak / [N]ie:
Gdzie trzymać dane pobierane przez narzędzia (Kartograf, IMGWTools)?
Magazyny to dwa osobne foldery w wybranym folderze — kartograf i imgw — więc oba są na jednym dysku. Wybierz dysk z dużą ilością miejsca: rastry i archiwa zajmują gigabajty, a magazyny są wspólne dla wszystkich projektów.
Plik cache Kartografa trafi na dysk lokalny użytkownika: ~/.cache/nogat/kartograf/metadata.db.
Folder na magazyny [Enter = ~/.local/share/nogat]:
~/.config/nogat/nogat.toml
Zbieranie poleceń wyłączone ([retman.privacy] collect_commands = false).
Magazyny narzędzi (ustawienia [retman.tools.*] w pliku):
  Kartograf: ~/.local/share/nogat/kartograf
  IMGWTools: ~/.local/share/nogat/imgw
Czy utworzyć teraz magazyn IMGWTools w ~/.local/share/nogat/imgw?
Tworzenie nie używa sieci: w pustym folderze powstaje znacznik magazynu. Bez magazynu nie działają operacje na danych IMGW, które zapisują się lokalnie.
Utworzyć magazyn IMGWTools? [t]ak / [N]ie: t
Magazyn IMGWTools gotowy: ~/.local/share/nogat/imgw
```

`retman init` wypisuje ścieżkę pliku, do którego zapisał tabele. Istniejący plik zostaje, jak był: tabele
`[retman]` są dopisywane na końcu, a inne tabele (`[nogat]`, tabele innych narzędzi) nie są ruszane.
Jeśli plik ma już tabelę `[retman]`, `retman init` kończy się błędem `conflict` (kod 4) i niczego nie
zmienia. Bez terminala zapisuje tabele z widocznymi ścieżkami domyślnymi i niczego nie tworzy (Kartograf
utworzy swój magazyn przy pierwszym pobraniu, a magazyn IMGWTools utworzysz poleceniem „Utwórz magazyn
IMGW”). Jeśli dysk wybranego folderu **nie ma dowiązań twardych** (FAT/exFAT, część udziałów
sieciowych), `retman init` kończy się błędem `store_unavailable` (kod 8) i nie zapisuje pliku — wskaż
folder na innym dysku.

Tabele magazynów w pliku, ze ścieżkami bezwzględnymi (tu skrócono do `~`):

```toml
[retman.tools.kartograf]
store_dir = '~/.local/share/nogat/kartograf'              # pobrane pliki, wspólne dla wszystkich projektów
cache_file = '~/.cache/nogat/kartograf/metadata.db'       # cache metadanych; dysk LOKALNY, nie udział sieciowy
workers = 4                                               # równoległe transfery
update = "local"                                          # "local" | "upgrade" | "force"

[retman.tools.imgwtools]
store_dir = '~/.local/share/nogat/imgw'                   # obok magazynu Kartografa, w osobnym folderze
reference_data_dir = '~/.cache/nogat/imgw/reference'      # opcjonalny plik położeń stacji
```

Magazyny nie mogą leżeć jeden w drugim, a ich ścieżki nie mogą zawierać dowiązań symbolicznych.
`update = "local"` oznacza: użyj zapisanych wersji i nie pytaj źródeł o nowsze. Szablon tabel jest w
`src/retman/config_template.toml`. Kopię magazynu robi się z zachowaniem dowiązań twardych (`rsync -aH`);
co się nie pobierze ponownie, mówi README narzędzia.

**Serwer modelu nie ma wartości domyślnych.** Szablon jest ustawiony na basal, więc dla LM Studio trzeba
zmienić tabelę `[retman.decision]` (wartości adresu i modelu — własne); można też podać je zmiennymi
`RETMAN_DECISION_*` i obejść się bez pliku:

```toml
[retman.decision]
backend = "openai_compatible"
url = "http://127.0.0.1:1234/v1"   # adres serwera LM Studio
model = "<nazwa-modelu>"           # nazwa modelu na serwerze
timeout_s = 30
confidence = "auto"                # logprobs, a gdy serwer ich nie podaje — zgodność odpowiedzi
consistency_runs = 3

[retman.decision.thresholds]
operation = 0.90                   # progi pewności dostrojone dla modelu (p. 12)
parameter = 0.90
```

Progi `"auto"` działają tylko z basalem; z innym backendem trzeba wpisać liczby. Bez ustawień modelu
polecenie z tekstem do rozpoznania kończy się błędem `validation_error` (powód `invalid_config`, kod 2) z listą
brakujących kluczy, a `retman results`, `retman log`, `retman config show` i `retman init` działają bez nich.
Wszystkie ustawienia opisuje ARCHITECTURE 9.1 i ADR-021.

### 1.4. Sprawdzenie

```bash
retman doctor
```

Gdy wszystko jest w porządku, kończy się kodem 0; szczegóły w p. 11.

---

## 2. Folder projektu

Retman pracuje w **folderze, w którym go uruchomiono** (folder projektu, np. folder jednej
zlewni). Tam powstaje podfolder wyników (domyślnie `retman-output/`, ustawienie
`[retman.output] results_dir`) z numerowanymi wynikami i dziennikiem projektu:

```
zlewnia-a/
└── retman-output/
    ├── journal.jsonl                                  # dziennik: polecenia, pytania, odpowiedzi, plany, sprawdzenia
    └── 001_export_station_series/                     # wynik #1
        ├── result.json                                # wartości, ich źródła, wersje, decyzje modelu, ślad narzędzia
        ├── hydro_daily_149190310_2022-11-01_2024-10-31.csv
        ├── tool_1_series_export.json                  # pełne dokumenty narzędzia (ślad audytowy)
        └── tool_2_series_select.json
```

Dane **Kartografa** nie leżą w folderze projektu: Kartograf zapisuje je w swoim magazynie
(`[retman.tools.kartograf] store_dir`), a wynik wskazuje te pliki ścieżką bezwzględną i sumą SHA-256 (p. 6.2).
Wynik zawiera wtedy `result.json` i dokumenty narzędzia, a podsumowanie mówi, gdzie są pliki.

Uruchamiaj Retmana w folderze projektu, nie w katalogu domowym ani w repozytorium.

---

## 3. Pierwsze polecenie

Polecenie to zwykłe zdanie po polsku, w cudzysłowie:

```
$ retman "Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4"
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

Co się stało:

1. Model wybrał operację z listy dostępnych — operacji jest więcej niż 9, więc najpierw wybrał grupę
   („Dane przestrzenne GUGiK”), a potem operację w niej (tu: NMT dla arkusza).
2. Godło arkusza i rozdzielczość odczytał **kod** z treści polecenia — liczb, godeł
   i współrzędnych nie odgaduje model.
3. Polecenie nie podawało układu wysokościowego, więc Retman **zapytał**, zamiast przyjąć
   wartość domyślną (operacje Kartografa nie mają wartości domyślnych, ADR-006).
4. Plan pokazuje każdą wartość. Wiersz z oznaczeniem `← podgląd, bez sieci` dopowiedział **narzędzie**:
   Kartograf sprawdził plan offline (czy przyjmuje takie żądanie) i policzył arkusze. Do tego miejsca
   Retman nie użył sieci narzędzia (PRD N-12).
5. Nic nie zostało wykonane bez `t`.

Im pełniejsze polecenie, tym mniej pytań:

```
$ retman "ściągnij bdot dla powiatu 2264 w gpkg"
Plan:
Operacja: Pobranie BDOT10k (bieżące paczki powiatów)
Obszar BDOT10k: powiat o kodzie TERYT 2264
Format BDOT10k: GeoPackage (.gpkg)
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

Retman rozumie też nazwy i skróty angielskie używane w praktyce (DEM, DTM, DSM, orthophoto,
GPKG, SHP) oraz zapis potoczny i bez polskich znaków.

---

## 4. Odpowiadanie na pytania

Retman zadaje **jedno pytanie naraz**. Na pytanie można odpowiedzieć:

| Odpowiedź | Działanie |
| --- | --- |
| numer opcji, np. `1` | wybiera opcję z listy |
| własne słowa, np. `kronsztadt` | odpowiedź sprawdzają te same reguły co polecenie; gdy jest niejasna, Retman pyta ponownie |
| `?` | pokazuje pomoc do pytania (zakres wartości, ograniczenia narzędzia) |
| `anuluj` | przerywa polecenie (kod 3) |

Zapis o kilku możliwych odczytach zawsze kończy się pytaniem. Przykład: współrzędne PL-1992
bez wskazania kolejności osi — Retman pokazuje oba odczyty i podpowiada format:

```
$ retman --plan-only "Wytnij NMT 530000,382000,530100,382100 EPSG:2180 w EVRF2007, wynik w PL-1992"
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

Tak samo pytanie dostaje zapis prawdopodobieństwa, który ma dwa odczyty („Q50” to 50% czy okres
powtarzalności 50 lat?). Wartość podana bez znaku, jak „dla 1”, też zawsze kończy się pytaniem:

```
$ retman --plan-only "Opady maksymalne PMAXTP dla punktu 52.23, 21.01 metodą POT dla Q50"
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
```

Odpowiedź spoza listy kończy się komunikatem `Błąd: Wybierz jedną z podanych możliwości.`
i tym samym pytaniem.

### 4.1. Pytania, których model nie rozstrzyga

Retman pyta zawsze, gdy wartość mogłaby zmienić wynik, a polecenie jej nie rozstrzyga:

- **rodzaj roku** (hydrologiczny od 1 listopada do 31 października czy kalendarzowy) przy szeregach
  stacji IMGW — nie ma wartości domyślnej, a słowo „hydrologiczne” opisujące dane („dane
  hydrologiczne z lat 2000–2020”) nie jest odpowiedzią;
- **stacja podana w formie odmienionej** („na Rabie”, „w Poznaniu”) — Retman pokazuje odczyt i prosi
  o potwierdzenie wyborem z listy; nazw nie poprawia po literówkach;
- **okres względny** („ostatnie 10 lat”, „od 2010”) — nie zamienia go na daty, prosi o lata albo daty;
- **warstwa pliku geometrii** (GeoPackage z kilkoma warstwami):

```
$ retman "Pobierz NMT 1 m w EVRF2007 dla obszaru z pliku zlewnie.gpkg"
? Która warstwa pliku zlewnie.gpkg wyznacza obszar?
  1) zlewnie
  2) dzialki
> 2
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Godło arkusza lub obszar NMT: obszar z pliku ~/zlewnia-a/zlewnie.gpkg, warstwa „dzialki” (arkusze 1:10000 (PL-1992) przecinające obwiednię któregokolwiek obiektu warstwy; kształt wieloboku nie jest uwzględniany)
Obwiednia obszaru: 0.2 × 0.2 km (EPSG:2180: E 530200–530400, N 382100–382300) ← podgląd, bez sieci
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

Plik z jedną warstwą (i Shapefile) nie wywołuje pytania. Plany pokazują zdanie o tym, co plik oznacza dla
danej operacji (np. wycinek to jeden prostokąt obejmujący wszystkie obiekty warstwy, bez przycinania),
oraz obwiednię i liczbę arkuszy z podglądu. Pliki GeoJSON i GML nie są przyjmowane — geometria musi
być plikiem SHP albo GPKG.

### 4.2. Narzędzie odrzuca wybór

Narzędzie sprawdza kompletny plan **offline**. Gdy odrzuci kombinację (np. NMT 5 m dostępny tylko
w EVRF2007 razem z KRON86), Retman nie ufa już tej wartości i **pyta ponownie** o parametr, który narzędzie
wskazało, z powodem w pytaniu (tekst narzędzia jest w nim cytatem):

```
$ retman "Pobierz NMT 5 m w układzie KRON86 dla arkusza N-34-130-D-d-2-4"
? W jakiej rozdzielczości pobrać NMT: 0,15 m, 0,5 m, 0,6 m, 1 m, 5 m, 10 m czy 100 m?
  1) 0,15 m (tylko EVRF2007)
  2) 0,5 m
  3) 0,6 m (tylko EVRF2007)
  4) 1 m
  5) 5 m (tylko EVRF2007)
  6) 10 m (tylko EVRF2007)
  7) 100 m (pliki województw, bez układu wysokościowego)
Błąd: Kartograf odrzuca ten wybór: NMT 5m (PL) jest dostepny tylko w EVRF2007 - podano --vertical-crs KRON86; dostepne w KRON86: 0.5m, 1m
> 4
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: KRON86 (tylko 0,5 m i 1 m)
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

Plan, którego narzędzie nie przyjmuje, nie da się potwierdzić. Odpowiedź na jeden parametr unieważnia
parametry od niego zależne (tu układ wysokościowy): Retman odczytuje je od nowa z polecenia, a podgląd
uruchamia się ponownie.

---

## 5. Plan, zmiana, sprawdzenie i wykonanie

Po zebraniu wszystkich wartości Retman pokazuje plan i czeka na decyzję:

| Odpowiedź | Działanie |
| --- | --- |
| `t` | wykonuje plan |
| `n` | odrzuca plan (kod 3); w dzienniku zostaje „odrzucony” |
| `z` | zmiana jednej wartości bez wpisywania polecenia od nowa |
| `s` | sprawdzenie dostępności danych (sieć, osobna zgoda); tylko gdy operacja je oferuje (p. 5.4) |
| `?` | pomoc |
| `anuluj` | przerywa (kod 3) |

### 5.1. Zmiana wartości (`z`)

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

Po zmianie plan pokazuje się od nowa (z ponownym podglądem offline), a poprzednie potwierdzenie
i sprawdzenie dostępności przestają obowiązywać. Plan pokazuje prostokąt tak, jak Retman go **odczytał**
(E, N), żeby pomyłkę w kolejności osi było widać przed wykonaniem.

### 5.2. Wykonanie (`t`)

Przykład z magazynu testowego IMGWTools (fikcyjna stacja „Raba Górna”, bez sieci). Polecenie nie podaje
rodzaju roku, więc Retman pyta; źródło danych (magazyn) wybrał model:

```
$ retman "Pobierz dobowe przepływy ze stacji Raba Górna z lat 2023–2024"
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
Magazyn IMGW: ~/.local/share/nogat/imgw (z ustawień) ← podgląd, bez sieci
Dane w magazynie: 2024-02-29 – 2024-02-29, luk: 0 ← podgląd, bez sieci
Okres w magazynie: magazyn pokrywa tylko część wybranego okresu (2024-02-29 – 2024-02-29) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> t
Gotowe. Wynik #1: szereg stacji 149190310 (91 wierszy, 2023-12-01 – 2024-02-29) zapisany w pliku CSV.
Uwaga: Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy. Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone. Do użytku prywatnego i badawczego; inne zastosowania wymagają sprawdzenia warunków IMGW-PIB, także wyjątków dla danych o wysokiej wartości.
```

Po podsumowaniu Retman wypisuje **ostrzeżenia** operacji, każde w osobnej linii „Uwaga: …”: uwagi
narzędzia o jakości danych (np. niepełny lot GUGiK) i licencyjne (IMGW) są pokazywane dosłownie, a wynik
częściowy jest wynikiem z ostrzeżeniem. Wynik nieudany też dostaje numer i kończy się kodem 1; komunikat
wybiera Retman po stabilnym kodzie błędu narzędzia, a tekst narzędzia jest tylko cytatem
(np. „GUGiK nie ma danych dla wskazanego obszaru i wybranych parametrów produktu. Szczegóły: …”).
Pobranie z GUGiK przez Kartografa wygląda tak samo: pliki trafiają do magazynu Kartografa, a podsumowanie
mówi, gdzie są („Pliki w magazynie narzędzia: …”).

### 5.3. Podgląd planu (offline)

Wiersze z `← podgląd, bez sieci` to to, co narzędzie ustaliło o Twoim planie **bez użycia sieci** i bez
zapisu: stan magazynu, liczba arkuszy, obwiednia pliku geometrii, zakres danych w magazynie, liczba plików
archiwów do sprawdzenia. Służą do tego, żebyś widział, co plan faktycznie oznacza, zanim go potwierdzisz.
Gdy podgląd wykryje, że plan się nie uda (np. brak magazynu IMGW, brak szeregu zbioru w magazynie przy
źródle „magazyn”, ortofotomapa dla pliku geometrii), Retman pyta ponownie o odpowiednie parametry
z wyjaśnieniem.

Parametr nieobowiązkowy, którego polecenie nie podało, też ma swój wiersz — z tym, co oznacza jego brak:

```
Dostawca danych: obaj dostawcy (IMGW-PIB i ČHMÚ) ← nie podano w poleceniu, parametr nieobowiązkowy
Rodzaj stacji: wszystkie rodzaje (hydrologiczne i meteorologiczne) ← nie podano w poleceniu, parametr nieobowiązkowy
```

Retman o takie parametry nie pyta; jeśli chcesz zawęzić wynik, odpowiedz `z` i wybierz wartość albo
podaj ją w poleceniu. Gdy narzędzie zgłasza wiele podobnych uwag (np. kilkadziesiąt stacji bez
położenia), wynik pokazuje pierwsze trzy i liczbę pozostałych; pełna lista jest w pliku `tool_*.json`
w folderze wyniku.

### 5.4. Sprawdzenie dostępności (`s`)

Podgląd offline wie, czy narzędzie przyjmie żądanie, ale nie wie, **co źródło danych faktycznie ma**:
które lata i rozdzielczości istnieją, czy pokrycie jest pełne, które archiwa IMGW są już opublikowane.
Można to sprawdzić — to osobny krok z siecią i **własną zgodą**, jedyny przed potwierdzeniem planu.
Odpowiedź `s` jest dostępna tylko dla operacji, które oferują sprawdzenie, i tylko przy kompletnym planie:

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

(Raport powstał z zapisanej odpowiedzi GUGiK dla tego arkusza.) Zasady:

- Każda odpowiedź inna niż `t` w pytaniu o zgodę to **odmowa**: „Sprawdzenie pominięte.” i powrót do planu.
  Zgoda jest jednorazowa i obejmuje jedno sprawdzenie.
- Raport **tylko informuje** — niczego w planie nie zmienia. Po nim wraca to samo pytanie o plan:
  `z` zmienia wartość (np. na rozdzielczość z raportu), `t` potwierdza, `n` rezygnuje. Sprawdzenie
  cofa wcześniejsze potwierdzenie planu; kolejność to zawsze sprawdzenie, potem potwierdzenie.
- Status raportu to „dane dostępne”, „dane dostępne częściowo”, „brak danych dla tego wyboru” albo „nie
  udało się sprawdzić” (brak sieci, błąd usługi — to raport, nie awaria). Plan pokazuje wtedy wiersz
  „Sprawdzenie dostępności: …”.
- Wysyłane są wyłącznie wartości z planu (obszar, produkt, lata…) — nigdy treść polecenia ani plik.
- Sprawdzenie nie zajmuje numeru wyniku. Jest w dzienniku projektu także wtedy, gdy je odrzucisz (p. 6.3).
- Bez terminala i z `--plan-only` Retman nigdy nie sprawdza (p. 7).

Sprawdzenie oferują m.in. cztery operacje Kartografa (lata, rozdzielczości i kompletność pokrycia; dla
BDOT10k — powiaty obszaru i paczki już w magazynie) oraz budowa katalogu stacji, eksport szeregu ze źródła
„serwer”, synchronizacja archiwów i pobranie danych projektu IMGW (ile plików jest nowszych albo brakuje).

---

## 6. Wyniki i dziennik projektu

### 6.1. Lista wyników

```
$ retman results
Gotowe. Wynik #1: szereg stacji 149190310 (91 wierszy, 2023-12-01 – 2024-02-29) zapisany w pliku CSV.
```

### 6.2. `result.json`

Każdy wynik ma `result.json` z danymi do odtworzenia obliczeń: operację, każdą wartość
ze **źródłem** (`command` — z polecenia, `user` — z odpowiedzi, `default`, `workspace` — z wcześniejszego
wyniku, `known` — podana z Pythona), pewność decyzji modelu, pliki z sumami SHA-256, wartości zwrócone
przez narzędzie, ostrzeżenia, wersje Retmana i narzędzia oraz czasy. Fragment (wynik z p. 5.2):

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
  "tool": "imgwtools", "version": "3.0.0",
  "calls": [{"command": "series export",
             "command_line": "imgw series export --root <magazyn> --dataset pl.imgw.hydro_daily --station 149190310 …",
             "status": "ok", "document_file": "tool_1_series_export.json", "sha256": "7b645332…"}]
 }
}
```

Dodatkowe sekcje: `tool` — dokładna linia komendy narzędzia z argumentami środowiskowymi, jej status, pliki
i suma pełnego dokumentu narzędzia (zapisanego obok jako `tool_<n>_<komenda>.json`); `preview` — wartości
ustalone przez podgląd (np. obwiednia obszaru, liczba arkuszy); `checks` — raporty sprawdzeń dostępności
dla końcowego stanu planu; `error_code` — stabilny kod błędu narzędzia, gdy wynik się nie powiódł;
dla obszaru z pliku geometrii wpis parametru ma `files` — sumy SHA-256 plików geometrii.

Plik, który narzędzie trzyma w swoim magazynie (Kartograf), wynik wskazuje ścieżką bezwzględną, nazwą
narzędzia i sumą kontrolną, a nie kopią:

```json
"files": {"dem": [{"path": "/dane/retman/stores/kartograf/nmt/…/N-34-130-D-d-2-4.asc", "store": "kartograf", "sha256": "…"}]}
```

### 6.3. Dziennik projektu

```
$ retman log
2026-10-19T20:11:10.307989+00:00 polecenie: Pobierz dobowe przepływy ze stacji Raba Górna z lat 2023–2024
2026-10-19T20:11:10.484466+00:00 pytanie: Czy podane lata to lata kalendarzowe (1 I – 31 XII) czy hydrologiczne (1 XI – 31 X)?
2026-10-19T20:11:10.484568+00:00 odpowiedź: 1
2026-10-19T20:11:10.496161+00:00 sprawdzenie dostępności: wykonane
2026-10-19T20:11:10.501945+00:00 plan: zatwierdzony
2026-10-19T20:11:10.604695+00:00 wykonanie: 1
```

Dziennik jest tylko dopisywany i obejmuje także plany odrzucone, zmienione i przerwane oraz **każde
sprawdzenie dostępności** — wykonane („wykonane”) albo odrzucone („pominięte”, wtedy bez użycia sieci),
także przerwane Ctrl+C. Przy każdym planie zapisuje, co Retman zrozumiał: wartości ze źródłami (`values`),
decyzje modelu z pewnością (`decisions`) i — przy zmianie — którą wartość poprawiono (`changed`); pytanie
zadane ponownie po odrzuceniu przez narzędzie ma też powód (`reason`). Polecenie spoza zakresu ma własne
zdarzenie z decyzją modelu. Treść poleceń i odpowiedzi zapisuje się przy `[retman.log] journal_commands = true`
(domyślnie); przy `false` dziennik nie zawiera też pokazanego planu, powodu ponownego pytania i linii raportu.

### 6.4. Zbiór poleceń (opcjonalny)

Po zgodzie w `retman init` (`[retman.privacy] collect_commands = true`) Retman dopisuje wynik
każdego planowania ze wszystkich projektów do jednego pliku (`[retman.privacy] collect_path`):
polecenie, Twoje odpowiedzi, wartości ze źródłami, decyzje modelu, status (zatwierdzony
z wynikiem wykonania, odrzucony, zmieniony, anulowany, poza zakresem), wersje i nazwę modelu
— bez adresu serwera i bez ścieżek lokalnych (z pliku geometrii zostaje nazwa). Plik zostaje na Twoim
komputerze; służy do budowy zbioru testowego `retman-eval` z prawdziwej pracy. Wyłączenie:
`collect_commands = false`.

---

## 7. Sesja, opcje i praca bez terminala

### 7.1. Sesja

`retman` bez polecenia otwiera sesję: kolejne polecenia wpisuje się po znaku `>`.
`koniec` zamyka sesję (kod 0), `anuluj` przerywa (kod 3).

### 7.2. Opcje

| Opcja | Działanie |
| --- | --- |
| `--plan-only` | zadaje pytania i pokazuje plan (z podglądem offline), ale go nie wykonuje i nie sprawdza dostępności (kod 0) |
| `--explain` | pod planem wypisuje decyzje modelu: wybór, pewność, metodę i prawdopodobieństwa opcji |
| `--config PATH` | inny plik `nogat.toml` niż domyślny (p. 1.3) |
| `--verbose`, `--quiet` | poziom logu technicznego na stderr: `debug` albo tylko błędy; bez opcji decyduje `RETMAN_LOG_LEVEL`, potem `NOGAT_LOG_LEVEL`, potem `log_level` w `[retman]` i `[nogat]` (domyślnie `warning`); log nie zawiera poleceń ani odpowiedzi |
| `--json` | z `retman doctor`: raport w JSON |
| `--deep` | z `retman doctor`: także wolniejsze sprawdzenia (próbny zapis do magazynu IMGWTools) |

```
$ retman --plan-only "Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4"
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
```

### 7.3. Bez terminala (skrypty, potoki, CI)

Gdy wejście nie jest terminalem, Retman nie zadaje pytań, niczego nie wykonuje i nie sprawdza dostępności
— wypisuje, czego brakuje, i kończy kodem 2:

```
$ retman "Pobierz NMT dla arkusza N-34-130-D-d-2-4" < /dev/null
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Brakuje: W jakiej rozdzielczości pobrać NMT: 0,15 m, 0,5 m, 0,6 m, 1 m, 5 m, 10 m czy 100 m?
```

Pełny plan bez terminala sprawdza się przez `--plan-only`; wykonanie zawsze wymaga
potwierdzenia — w terminalu albo z Pythona (p. 10).

### 7.4. Polecenie spoza zakresu

```
$ retman "Jaka będzie jutro pogoda?"
Błąd: Polecenie nie dotyczy dostępnych operacji: Stacje i rejestr danych IMGW, Dane bieżące i ostrzeżenia IMGW, Opady maksymalne PMAXTP, Szeregi czasowe stacji IMGW i ČHMÚ, Archiwa i magazyn danych IMGW, Projekty danych IMGW, Dane przestrzenne GUGiK
```

Przy rozpoznawaniu dwustopniowym Retman wymienia **grupy** operacji, a nie dopasowuje na siłę najbliższej
operacji (PRD W-03).

---

## 8. Kody wyjścia

Kody wyjścia są kodami wspólnego rejestru Nogat ([ERROR_REGISTRY](https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md)):
ten sam kod znaczy to samo w każdym narzędziu. Przy błędzie ostatnia linia stderr to dokument
`retman-error/1` (jeden wiersz JSON: `code`, `title`, `message`, `hint`, `details`, `exit_code`);
`details.reason` zawęża kod (np. `out_of_scope`, `input_required`, `missing_config`).
Przerwanie przez użytkownika nie jest błędem i nie drukuje dokumentu.

| Kod | Nazwa | Znaczenie w Retmanie |
| --- | --- | --- |
| 0 | `ok` | operacja wykonana, plan pokazany przy `--plan-only`, sesja zakończona `koniec` |
| 1 | `internal_error` | błąd Retmana albo nieoczekiwany wyjątek; błąd w operacji, którego narzędzie nie opisało |
| 2 | `validation_error` | błędna opcja lub zmienna (`usage`), błędna konfiguracja (`invalid_config`), potrzebne odpowiedzi lub potwierdzenie, a wejście nie jest terminalem (`input_required`) |
| 3 | `not_found` | brak pliku ustawień wskazanego przez `--config` albo `NOGAT_CONFIG` (`missing_config`), pliku wejściowego albo wyniku |
| 4 | `conflict` | plik ustawień ma już tabelę `[retman]` (`output_exists`), plan niepotwierdzony lub zmieniony |
| 5 | `source_unavailable` | model nie odpowiada (`backend_connection`) albo źródło danych narzędzia zawiodło |
| 6 | `missing_dependency` | narzędzie nie jest zainstalowane (`tool_not_installed`) albo brak operacji (`no_operations`) |
| 7 | `data_error` | plik niezgodny ze swoim rodzajem, zły zbiór poleceń `retman-eval` |
| 8 | `store_unavailable` | magazyn narzędzia nie działa (np. dysk bez dowiązań twardych) |
| 9 | `io_error` | zapis lub odczyt pliku nie powiódł się |
| 10 | `partial` | `retman doctor`: coś blokuje pracę, a część kontroli przeszła; `retman-eval`: naruszenie W-03; `retman-scaffold --check`: błędy w części narzędzi |
| 11 | `failed` | to samo, gdy żadna kontrola ani narzędzie nie przeszło |
| 13 | `calculation_error` | narzędzie nie potrafi policzyć wyniku z poprawnych danych |
| 14 | `no_data` | źródło nie ma danych dla obszaru lub okresu (np. `no_coverage` Kartografa) |
| 15 | `unsupported` | polecenie spoza zakresu (`out_of_scope`) albo brak sprawdzenia dostępności (`no_check`) |
| 130 | `cancelled` | przerwane przez użytkownika (`anuluj`, `n`, Ctrl+C — także w trakcie sprawdzenia dostępności) |
| 143 | `terminated` | proces dostał SIGTERM |

Kody 10 i 11 nie oznaczają błędu: wynik został wydrukowany, a kod mówi, czy każda jednostka przeszła.
`retman-eval` i `retman-scaffold` mają te same kody; opcje i miary eval: p. 12.

---

## 9. Co Retman potrafi teraz

Operacje są w siedmiu grupach (w tym jednej Kartografa); Retman najpierw wybiera grupę, potem operację.

### 9.1. Kartograf 0.8.0 — dane przestrzenne GUGiK (ADR-001, ADR-012, ADR-016)

Wszystkie pobierają dane z GUGiK do magazynu Kartografa; mają podgląd offline i sprawdzenie dostępności:

| Operacja | Obszar | Parametry (Retman dopyta o brakujące) | Przykładowe polecenie |
| --- | --- | --- | --- |
| Pobranie NMT dla arkusza lub obszaru | godło arkusza PL-1992 lub PL-2000; plik geometrii | rozdzielczość 0,15 / 0,5 / 0,6 / 1 / 5 / 10 / 100 m; układ wysokościowy EVRF2007 / KRON86 (KRON86 tylko 0,5 m i 1 m; 100 m bez układu) | `Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4` |
| Pobranie arkuszy potomnych | godło arkusza nadrzędnego; plik geometrii (nie dla ortofotomapy) | produkt NMT / NMPT / ortofotomapa; skala docelowa 1:10000–1:500 (drobniejsze niż 1:10000 tylko w PL-2000); dla NMT rozdzielczość 0,15–10 m, dla NMPT 0,5 / 0,6 / 1 m; układ wysokościowy; dla ortofotomapy kolor RGB / CIR / B-W | `Rozwiń N-34-130-D-d-2 do 1:10000, ściągnij DSM z arkuszy potomnych` |
| Wycinek NMT albo NMPT 1 m | prostokąt w PL-1992 (EPSG:2180) albo WGS84 (EPSG:4326); plik geometrii | produkt NMT / NMPT; układ wyniku EPSG:2180 / 5514 / 3045 (kod z prefiksem `EPSG:`, sama liczba albo nazwa, np. `wynik w 2180`, `do S-JTSK`); układ wysokościowy | `wytnij dsm z prostokąta 52.40 16.90 52.41 16.91 do 3045` |
| Pobranie BDOT10k | powiat (TERYT, 4 cyfry), godło, prostokąt albo plik geometrii | format GeoPackage / Shapefile | `ściągnij bdot dla powiatu 2264 w gpkg` |

Formy zapisu obszaru:

- **godło**: `N-34-130-D-d-2-4` (PL-1992, także 8-członowe `N-34-50-A-c-3-2-3`), `5.123.45` (PL-2000);
- **TERYT powiatu**: `TERYT 2264`, `powiat 2264`;
- **prostokąt**: cztery liczby i układ, np. `530000,382000,530100,382100 EPSG:2180` albo
  `52.40 16.90 52.41 16.91` (WGS84). Przy niejednoznacznej kolejności osi Retman pyta (p. 4);
- **plik geometrii** SHP albo GPKG (p. 4.1): Kartograf czyta plik sam; Retman pyta o warstwę GeoPackage,
  gdy jest ich kilka, pokazuje w planie obwiednię i liczbę arkuszy oraz zapisuje sumy SHA-256 plików.

### 9.2. IMGWTools 3.0.0 — dane IMGW-PIB i ČHMÚ (ADR-017)

26 operacji w sześciu grupach. Wszystkie wymagają zainicjowanego magazynu IMGW (p. 1.3); rozpoznawanie
stacji po nazwie działa offline z katalogu stacji w magazynie. Kolumna „Sieć” mówi, czy wykonanie łączy się
z serwerem (dopiero po `t`):

| Grupa | Operacje | Sieć |
| --- | --- | --- |
| Stacje i rejestr danych IMGW | wyszukanie stacji IMGW i ČHMÚ (po nazwie, rzece, rodzaju); budowa katalogu stacji w magazynie (`s`); lista zbiorów danych i dostawców | wyszukanie ze źródła „serwer” i budowa katalogu |
| Dane bieżące i ostrzeżenia | aktualne pomiary stacji hydrologicznej, meteorologicznej albo synoptycznej; ostrzeżenia hydrologiczne i meteorologiczne; stany wody (alarmowe i ostrzegawcze) | tak |
| Opady maksymalne PMAXTP | tabela dla punktu (metoda POT albo AMP; zapis komórki w magazynie albo nie; zawężenie do wybranych prawdopodobieństw i czasów trwania); odczyt zapisanej komórki | pobranie tak, odczyt nie |
| Szeregi czasowe stacji | eksport szeregu stacji do CSV (zbiór, okres, rodzaj roku, zmienne; źródło „magazyn” albo „serwer”, `s`); pokrycie danych stacji w magazynie; budowa szeregów | źródło „serwer” |
| Archiwa i magazyn danych IMGW | pobranie archiwów hydrologicznych albo meteorologicznych do folderu wyniku; sprawdzenie archiwów względem magazynu (plan); pobranie archiwów do magazynu (`s`), także według planu z wcześniejszego wyniku (np. „#5”); eksport zapisanych archiwów do CSV albo JSON Lines; utworzenie magazynu; opis magazynu | pobrania i sprawdzenie tak |
| Projekty danych IMGW | utworzenie projektu; dodanie i usunięcie zadania; wskazanie magazynu; pobranie i przypięcie danych (`s`); sprawdzenie aktualności; weryfikacja przypiętych danych | pobranie i sprawdzenie tak |

Przykładowe polecenia (poglądowe; nie wszystkie są jeszcze w zbiorze `retman-eval`): „Znajdź stacje hydrologiczne na Wiśle”,
„Zbuduj katalog stacji IMGW”, „Jakie dane ma ČHMÚ?”, „Aktualny stan wody na stacji Poznań-Bogdanka”,
„Jakie są ostrzeżenia hydrologiczne?”, „Opady maksymalne PMAXTP dla punktu 52.23, 21.01 metodą POT”,
„Pobierz dobowe opady ze stacji Poznań z lat 2000–2020”, „Za jakie lata mam dane stacji Poznań-Ławica?”,
„Sprawdź, ile trzeba pobrać dla opadów dobowych 2000–2020”, „Utwórz magazyn IMGW”, „Co mam w magazynie IMGW?”.

Zasady operacji IMGWTools:

- **stacje**: kod (9 cyfr dla IMGW-PIB, identyfikator WIGOS dla ČHMÚ) albo nazwa z katalogu w magazynie;
  odmieniona nazwa wymaga potwierdzenia; bez katalogu Retman czyta tylko kody i podpowiada „Zbuduj katalog
  stacji IMGW”;
- **okres**: archiwa biorą lata w numeracji archiwów narzędzia (dla danych hydrologicznych IMGW-PIB — lata
  hydrologiczne), szeregi biorą lata albo daty i rodzaj roku (zawsze pytanie);
- **PMAXTP**: prawdopodobieństwo i czas trwania z polecenia zawężają tabelę wyniku; wartość spoza tabeli
  daje ostrzeżenie, nie jest po cichu pomijana;
- **licencja**: uwagi dostawcy danych są pokazywane po wykonaniu (p. 5.2);
- magazyn jest tworzony tylko świadomie (`retman init` albo operacja „Utwórz magazyn IMGW”) — brak magazynu
  to powód ponownego pytania z podpowiedzią, nie ciche utworzenie.

---

## 10. Retman w Pythonie

Ten sam przebieg — pytania, plan, sprawdzenie, potwierdzenie — jest dostępny z Pythona:

```python
from pathlib import Path

from retman import Plan, Retman

retman = Retman.from_config(Path("nogat.toml"), project_dir=Path("zlewnia-a"))

plan = retman.plan("Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4")
for question in plan.questions:          # tu: vertical_crs
    print(question.text)                 # pytanie w języku użytkownika
    for number, option in enumerate(question.options, start=1):
        print(f"  {number}) {option.label}")
plan = plan.answer("vertical_crs", "1")  # numer albo własne słowa

print(plan.summary())                    # ten sam plan co w terminalu (z wierszami podglądu)

if plan.can_check:                       # operacja oferuje sprawdzenie dostępności
    print(plan.check_notice())           # co sprawdzenie kontaktuje i co wysyła
    plan.confirm_check()                 # osobna, jednorazowa zgoda; nie potwierdza planu
    report = retman.check(plan)          # CheckReport; bez zgody CheckNotConfirmedError
    print(report.summary())              # status i linie; wartości planu bez zmian

plan.confirm()                           # bez tego execute() zgłasza PlanNotConfirmedError
result = retman.execute(plan)
if result.ok:
    print(result.summary)
    print(result.files)                  # {"dem": [Path(...)]} — w folderze wyniku albo w magazynie narzędzia
else:
    print(result.error, result.error_code)
for warning in result.warnings:          # uwagi narzędzia (jakość danych, licencja): pokaż je zawsze
    print("Uwaga:", warning)
```

- `Retman.from_config()` bez ścieżki czyta `nogat.toml` z lokalizacji systemowej (albo z `NOGAT_CONFIG`)
  i zmienne `RETMAN_*`, a `project_dir` domyślnie to bieżący folder.
- Wartości znane z góry podaje się przez `known` — trafiają do planu ze źródłem `known`
  i nie są nadpisywane przez model ani otwierane ponownie po odrzuceniu przez narzędzie:

  ```python
  plan = retman.plan(
      "Pobierz NMT dla arkusza N-34-130-D-d-2-4",
      known={"resolution": "1m", "vertical_crs": "kron86"},
  )
  assert plan.questions == []
  ```

- Plan da się zapisać i wznowić: `plan.to_dict()` (JSON) oraz `Plan.from_dict(state, retman=retman)`.
  Wczytany plan jest **zawsze niepotwierdzony** (także gdy zapisany stan niesie `confirmed`) i trzeba go
  potwierdzić od nowa; zgoda na sprawdzenie też nie jest zapisywana.
- `plan.change(name)` ponownie otwiera jedną wartość (jak `z` w terminalu); każda zmiana planu
  unieważnia potwierdzenie, zgodę na sprawdzenie i raporty sprawdzeń.
- `plan.preview_rows`, `plan.preview_values`, `plan.reopened` i `plan.checks` pokazują stan podglądu
  i sprawdzeń; `retman.record_check(plan, "rejected")` zapisuje w dzienniku odmowę sprawdzenia.
- Do testów `Retman(config, backend, project_dir, clients={"kartograf": klient})` przyjmuje własnego
  klienta narzędzia (np. `retman.testing.FakeToolClient`, który zapisuje każde wywołanie).
- Polecenie spoza zakresu zgłasza `retman.exceptions.OutOfScopeError` z listą dostępnych
  operacji (albo ich grup) w `operations`.

Pełny opis API: ARCHITECTURE 7.1 i 7.3.

---

## 11. Diagnostyka: `retman doctor`

`retman doctor` w jednym miejscu pokazuje, co działa, co nie i jak to naprawić:
plik konfiguracji, folder projektu i zapis wyników, adres serwera modelu (zawsze pokazany,
bez oceniania), czy model jest na serwerze, pytanie testowe z oczywistą odpowiedzią, metodę
pewności i progi, zainstalowane narzędzia na tle obsługiwanych wersji, **magazyny danych narzędzi**,
zgodność opisów z narzędziami i komplet tłumaczeń.

```
$ retman doctor
Retman 0.1.0.dev0

Konfiguracja
  ✓ plik ustawień: nogat.toml (istnieje)
  ✓ projekt: <folder projektu> → wyniki w retman-output/ (0 wyników, zapis możliwy)

Model decyzyjny
  ✓ adres modelu (openai_compatible): http://127.0.0.1:18731/v1
  ✓ model: bielik-11b dostępny na serwerze
  ✓ pytanie testowe: poprawna odpowiedź (bez pewności)
  ! pewność: niedostępna (confidence = "none") — wybory modelu w planie są oznaczone jako niezweryfikowane → ustaw confidence = "auto" w [retman.decision] (nogat.toml), jeśli serwer podaje logprobs

Narzędzia
  ✓ imgwtools 3.0.0, obsługiwane >=3.0.0,<4, 26 operacji
  ✓ kartograf 0.8.0, obsługiwane >=0.8.0,<0.9, 4 operacje

Magazyny danych narzędzi
  ✓ kartograf: magazyn ~/.local/share/nogat/kartograf (zapis możliwy, dowiązania twarde działają)
  ✓ kartograf: cache metadanych ~/.cache/nogat/kartograf/metadata.db
  ✓ imgwtools: magazyn ~/.local/share/nogat/imgw (znacznik imgw-store.json, schemat imgw-store/1, dowiązania twarde działają)
  ✓ imgwtools: pyarrow 26.0.0 (szeregi czasowe)
  ✓ imgwtools: dane referencyjne ~/.cache/nogat/imgw/reference (hydro_stations_locations.csv: brak)

Zgodność opisów z narzędziami (retman-scaffold --check)
  ✓ imgwtools 3.0.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)
  ✓ kartograf 0.8.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)

Tłumaczenia (pl)
  ✓ komplet

Model tekstowy
  – wyłączony ([retman.text] backend = "none")
```

(Układ raportu; wartości adresów, wersji i ścieżek zależą od środowiska.) Sekcja „Magazyny” sprawdza
ścieżki (bez dowiązań symbolicznych), prawo zapisu, **dowiązania twarde w obu magazynach**, cache Kartografa,
znacznik magazynu IMGWTools, `pyarrow` i folder danych referencyjnych. Brak magazynu IMGW to ostrzeżenie
z podpowiedzią „utwórz go: retman init”; dysk bez dowiązań twardych albo obcy folder w miejscu magazynu to
problem blokujący. Sekcja „Zgodność” to lekka wersja `retman-scaffold --check`: ostrzega, gdy zainstalowane
narzędzie przyjmuje wartość, której opisy ani nie oferują, ani nie wyłączają; nie blokuje pracy.

`retman doctor --deep` dodaje wolniejsze sprawdzenie: próbny zapis do magazynu IMGWTools na wbudowanych
danych testowych narzędzia, w katalogu tymczasowym i bez sieci:

```
  ✓ imgwtools 3.0.0: zapis do magazynu działa na tym systemie (próba na danych testowych)
```

Gdy serwer modelu nie działa:

```
Model decyzyjny
  ✗ serwer modelu nie odpowiada (http://127.0.0.1:18731/v1) → uruchom serwer modelu (np. LM Studio albo basal-serve, instrukcja w README) i sprawdź [retman.decision] url w nogat.toml albo zmienną RETMAN_DECISION_URL
```

Oznaczenia: `✓` działa, `!` ostrzeżenie (da się pracować), `✗` problem, `–` wyłączone.
Kod wyjścia 1 oznacza problem blokujący pracę. `retman doctor --json` wypisuje ten sam raport
w JSON — do wklejenia w zgłoszeniu błędu. Gdy zwykłe polecenie nie może połączyć się
z modelem, komunikat błędu też podpowiada `retman doctor`.

---

## 12. Dostrajanie progów: `retman-eval`

Progi pewności decydują, kiedy Retman przyjmuje wybór modelu, a kiedy dopytuje. Dla modelu
innego niż basal trzeba je dostroić na zbiorze poleceń testowych:

```bash
retman-eval --config nogat.toml --target-error 0.01 --report raport.md --output rekordy.jsonl
```

`retman-eval` planuje każde polecenie ze zbioru (bez wykonywania operacji i bez sieci narzędzi) i raportuje
trafność operacji i parametrów, błędy przyjęte bez pytania (W-02), ciche zgadywanie,
naruszenia W-03, czasy oraz **zalecane progi** dla zadanego odsetka błędów. Przy rozpoznawaniu
dwustopniowym pytanie o grupę operacji liczy się jako dopytanie użytkownika. Zalecanych progów
nie zapisuje sam — wpisuje się je do `[retman.decision.thresholds]`. Kody wyjścia: 0 — przebieg
zakończony, 10 — wystąpiło naruszenie W-03 (przebieg zakończony), 2 — błędne argumenty,
3 — nie ma wskazanego pliku ustawień, 5 — model nie odpowiada, 130 — przerwany; pełna lista w p. 8.
Opcje i miary: `docs/specs/2026-10-11-retman-eval.md`.

---

## 13. Dobre praktyki i ograniczenia

- **Podawaj w poleceniu wszystko, co wiesz** — rozdzielczość, układ, format, rodzaj roku. Retman nie
  przyjmuje wartości domyślnych za użytkownika; czego brakuje, o to zapyta.
- **Czytaj plan przed `t`.** Wartości z odpowiedzi i z polecenia są tam w postaci, w jakiej
  Retman je zrozumiał; wiersze `← podgląd, bez sieci` mówią, co narzędzie ustaliło offline; wybory
  modelu bez pewności są oznaczone „wybór modelu niezweryfikowany”.
- **Sprawdź dostępność, gdy nie jesteś pewien danych** (`s`): lata, rozdzielczości i kompletność pokrycia
  GUGiK albo to, ile archiwów IMGW trzeba pobrać — zanim potwierdzisz pobranie. Raport tylko informuje.
- **Współrzędne PL-1992**: przy zapisie bez wskazania kolejności osi Retman pyta, który
  odczyt jest właściwy (p. 4).
- **Układ wyniku wycinka** rozpoznaje kod, nie model: po słowach „wynik”, „do”, „przelicz”,
  „zapisz”, „docelowy” (także bez polskich znaków i z jedną literówką). Układ podany zaraz
  po współrzędnych (`… 382100 PL-1992`) Retman traktuje jako układ prostokąta i pyta
  o układ wyniku; tak samo przy literówce w samym kodzie (`2108`).
- **Plik geometrii**: tylko SHP i GPKG; plik nie jest przycinany do kształtu — operacje arkuszowe biorą
  arkusze, których obwiednia styka się z obwiednią któregokolwiek obiektu, a wycinek to jeden prostokąt
  wszystkich obiektów. Ortofotomapy nie pobiera się dla pliku (tylko dla godła).
- **BDOT10k** dla godła, prostokąta lub pliku pobiera pełne pakiety każdego przecinanego powiatu,
  bez przycinania — pliki mogą być duże (Kartograf odrzuca obszar o ponad 100 pakietach lub ponad 10 GB).
- **Magazyny**: dane Kartografa i IMGWTools są wspólne dla wszystkich projektów i leżą poza folderem
  projektu; wymagają dysku z dowiązaniami twardymi (nie FAT/exFAT), a cache Kartografa — dysku lokalnego.
  Folder projektu na udziale sieciowym (np. CIFS) nie jest już problemem dla cache (cache jest poza projektem).
- Pobierany jest najnowszy dostępny materiał GUGiK; wyboru rocznika i kampanii jeszcze nie ma. Kartograf
  w trybie `update = "local"` używa zapisanych wersji i nie pyta źródeł o nowsze.
- Retman nie wysyła poleceń poza skonfigurowany model; narzędzia łączą się z usługami danych dopiero po `t`
  albo, na życzenie, w sprawdzeniu dostępności, które wysyła tylko wartości z planu.
