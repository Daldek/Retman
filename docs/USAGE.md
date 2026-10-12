# Praca z Retmanem

Przewodnik dla użytkownika: jak przygotować Retmana, jak wydawać polecenia, odpowiadać
na pytania, zatwierdzać plany i odnajdywać wyniki — w terminalu i z Pythona.

**Stan:** przed v0.1.0. Działają cztery operacje Kartografa 0.7.2 (p. 9) z modelem decyzyjnym
zgodnym z API OpenAI (np. LM Studio); backend basal jeszcze nie powstał.

> **O przykładach.** Przebiegi poniżej zarejestrowano na Retmanie 0.1.0.dev0 z Kartografem
> 0.7.2. Decyzje modelu podstawiono w nich atrapą (`FakeDecisionBackend`), więc z prawdziwym
> modelem Retman może zadać inne lub dodatkowe pytania — np. dopytać o operację, gdy model jest
> niepewny. Teksty pytań, planów i komunikatów są prawdziwe. Wykonanie w p. 5 pobrało dane
> z GUGiK naprawdę.

## Spis treści

1. [Przygotowanie](#1-przygotowanie)
2. [Folder projektu](#2-folder-projektu)
3. [Pierwsze polecenie](#3-pierwsze-polecenie)
4. [Odpowiadanie na pytania](#4-odpowiadanie-na-pytania)
5. [Plan, zmiana i wykonanie](#5-plan-zmiana-i-wykonanie)
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

Retman nie zawiera modelu językowego. Potrzebne są trzy rzeczy: Retman z narzędziami
w **jednym** środowisku, działający serwer modelu i plik konfiguracji.

### 1.1. Instalacja

Instalację opisuje ARCHITECTURE 9.4. Do czasu wydania v0.1.0 nie ma tagu wydania, więc
instaluje się wersję z gałęzi `develop` razem z Kartografem:

```bash
uv tool install "git+https://github.com/Daldek/Retman@develop" \
    --with "git+https://github.com/Daldek/Kartograf@v0.7.2"
```

Narzędzie zainstalowane w innym środowisku jest dla Retmana niewidoczne; `retman doctor`
(p. 11) podaje wtedy polecenie, które je doda.

### 1.2. Serwer modelu

Na razie Retman rozmawia z serwerem zgodnym z API OpenAI, np. LM Studio z załadowanym
modelem (sprawdzony: Bielik 11B, `docs/research/2026-10-11-lm-studio-openai-compatible.md`).
Serwer uruchamia się osobno, przed pracą z Retmanem.

### 1.3. Plik konfiguracji

```bash
retman init        # tworzy plik centralny retman.toml z komentarzami
```

`retman init` wypisuje ścieżkę utworzonego pliku i nigdy nie nadpisuje istniejącego.
Szablon jest ustawiony na basal, więc dla LM Studio trzeba zmienić sekcję `[decision]`
(wartości adresu i modelu — własne):

```toml
[decision]
backend = "openai_compatible"
url = "http://127.0.0.1:1234/v1"   # adres serwera LM Studio
model = "<nazwa-modelu>"           # nazwa modelu na serwerze
timeout_s = 30
confidence = "auto"                # logprobs, a gdy serwer ich nie podaje — zgodność odpowiedzi
consistency_runs = 3

[decision.thresholds]
operation = 0.90                   # progi pewności dostrojone dla modelu (p. 12)
parameter = 0.90
```

Progi `"auto"` działają tylko z basalem; z innym backendem trzeba wpisać liczby — Retman
nie ma ukrytych wartości domyślnych. Wszystkie ustawienia opisuje ARCHITECTURE 9.1.
Inny plik niż domyślny wskazuje się opcją `--config PATH` przy każdym poleceniu.

### 1.4. Sprawdzenie

```bash
retman doctor
```

Gdy wszystko jest w porządku, kończy się kodem 0; szczegóły w p. 11.

---

## 2. Folder projektu

Retman pracuje w **folderze, w którym go uruchomiono** (folder projektu, np. folder jednej
zlewni). Tam powstaje podfolder wyników (domyślnie `retman-output/`, ustawienie
`[output] results_dir`) z numerowanymi wynikami i dziennikiem projektu:

```
zlewnia-a/
└── retman-output/
    ├── journal.jsonl                       # dziennik: polecenia, pytania, odpowiedzi, plany
    └── 001_download_elevation_cutout/      # wynik #1
        ├── result.json                     # wartości, ich źródła, wersje, decyzje modelu
        └── nmt/…/530000_382000_530100_382100_20261012.tif
```

Uruchamiaj Retmana w folderze projektu, nie w katalogu domowym ani w repozytorium.

---

## 3. Pierwsze polecenie

Polecenie to zwykłe zdanie po polsku, w cudzysłowie:

```
$ retman "Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4"
? W którym układzie wysokościowym pobrać NMT: EVRF2007 czy KRON86?
  1) EVRF2007
  2) KRON86 (tylko 1 m)
> 1
Plan:
Operacja: Pobranie NMT dla arkusza
Godło arkusza NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Wykonać? [t]ak / [n]ie / [z]mień
> n
Plan odrzucony.
```

Co się stało:

1. Model wybrał operację z listy dostępnych (tu: NMT dla arkusza).
2. Godło arkusza i rozdzielczość odczytał **kod** z treści polecenia — liczb, godeł
   i współrzędnych nie odgaduje model.
3. Polecenie nie podawało układu wysokościowego, więc Retman **zapytał**, zamiast przyjąć
   wartość domyślną (operacje Kartografa nie mają wartości domyślnych, ADR-006).
4. Plan pokazuje każdą wartość; nic nie zostało wykonane bez `t`.

Im pełniejsze polecenie, tym mniej pytań:

```
$ retman "ściągnij bdot dla powiatu 2264 w gpkg"
Plan:
Operacja: Pobranie BDOT10k
Obszar BDOT10k: powiat o kodzie TERYT 2264
Format BDOT10k: GeoPackage (.gpkg)
Wykonać? [t]ak / [n]ie / [z]mień
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
$ retman "Wytnij NMT 530000,382000,530100,382100 EPSG:2180 w EVRF2007, wynik w PL-1992"
? Jaki prostokąt współrzędnych wyciąć z danych wysokościowych?
  1) prostokąt w PL-1992 (kolejność E, N): E 530000–530100, N 382000–382100
  2) prostokąt w PL-1992 (zamieniona kolejność N, E): E 382000–382100, N 530000–530100
  np. 530000,382000,530100,382100 EPSG:2180
> ?
Podaj granice prostokąta w PL-1992 (EPSG:2180) lub WGS84 (EPSG:4326). Pliki geometrii SHP/GPKG nie są przyjmowane: publiczne API Kartografa nie udostępnia ich dokładnego prostokąta, a argument geometry wycinka WCS jest nieaktywny.
? Jaki prostokąt współrzędnych wyciąć z danych wysokościowych?
  …
> 1
```

Odpowiedź spoza listy kończy się komunikatem `Błąd: Wybierz jedną z podanych możliwości.`
i tym samym pytaniem.

---

## 5. Plan, zmiana i wykonanie

Po zebraniu wszystkich wartości Retman pokazuje plan i czeka na decyzję:

| Odpowiedź | Działanie |
| --- | --- |
| `t` | wykonuje plan |
| `n` | odrzuca plan (kod 3); w dzienniku zostaje „odrzucony” |
| `z` | zmiana jednej wartości bez wpisywania polecenia od nowa |
| `?` | pomoc |
| `anuluj` | przerywa (kod 3) |

### 5.1. Zmiana wartości (`z`)

```
$ retman "wytnij nmt dla 52.40 16.90 52.41 16.91"
? Do jakiego układu współrzędnych zapisać wycinek?
  1) EPSG:2180 (PL-1992)
  2) EPSG:5514 (S-JTSK)
  3) EPSG:3045 (ETRS89/TM33)
> 2
? Jaki układ wysokościowy wybrać dla wycinka NMT/NMPT 1 m?
  1) EVRF2007
  2) KRON86
> 1
Plan:
Operacja: Wycinek NMT albo NMPT dla prostokąta
Produkt wycinka: NMT (numeryczny model terenu)
Prostokąt wycinka: prostokąt WGS84 (EPSG:4326): 52.4–52.41° N, 16.9–16.91° E
Układ współrzędnych wyniku: EPSG:5514 (S-JTSK)
Układ wysokościowy wycinka: EVRF2007
Wykonać? [t]ak / [n]ie / [z]mień
> z
Którą wartość zmienić?
  1) Produkt wycinka: NMT (numeryczny model terenu)
  2) Prostokąt wycinka: prostokąt WGS84 (EPSG:4326): 52.4–52.41° N, 16.9–16.91° E
  3) Układ współrzędnych wyniku: EPSG:5514 (S-JTSK)
  4) Układ wysokościowy wycinka: EVRF2007
> 3
? Do jakiego układu współrzędnych zapisać wycinek?
  1) EPSG:2180 (PL-1992)
  2) EPSG:5514 (S-JTSK)
  3) EPSG:3045 (ETRS89/TM33)
> 1
Plan:
Operacja: Wycinek NMT albo NMPT dla prostokąta
Produkt wycinka: NMT (numeryczny model terenu)
Prostokąt wycinka: prostokąt WGS84 (EPSG:4326): 52.4–52.41° N, 16.9–16.91° E
Układ wysokościowy wycinka: EVRF2007
Układ współrzędnych wyniku: EPSG:2180 (PL-1992)
Wykonać? [t]ak / [n]ie / [z]mień
```

Plan pokazuje prostokąt tak, jak Retman go **odczytał** (N/E), żeby pomyłkę w kolejności
osi było widać przed wykonaniem.

### 5.2. Wykonanie (`t`)

```
Plan:
Operacja: Wycinek NMT albo NMPT dla prostokąta
Produkt wycinka: NMT (numeryczny model terenu)
Układ współrzędnych wyniku: EPSG:2180 (PL-1992)
Układ wysokościowy wycinka: EVRF2007
Prostokąt wycinka: prostokąt w PL-1992 (EPSG:2180): E 530000–530100, N 382000–382100
Wykonać? [t]ak / [n]ie / [z]mień
> t
Pobranie wycinek NMT EVRF2007 (530000,382000)-(530100,382100) nieudane (proba 1/3): ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')); ponowienie za 2s
Gotowe. Wynik #1: Wycinek NMT albo NMPT dla prostokąta. Pliki: <folder projektu>/retman-output/001_download_elevation_cutout
```

Linia o ponowieniu pochodzi z Kartografa — narzędzie samo ponawia pobieranie przy chwilowych
błędach serwera GUGiK. Wynik nieudany też dostaje numer i kończy się kodem 1 z komunikatem
narzędzia (np. „GUGiK nie ma danych dla żadnego z żądanych arkuszy”).

---

## 6. Wyniki i dziennik projektu

### 6.1. Lista wyników

```
$ retman results
Gotowe. Wynik #1: Wycinek NMT albo NMPT dla prostokąta. Pliki: <folder projektu>/retman-output/001_download_elevation_cutout
```

### 6.2. `result.json`

Każdy wynik ma `result.json` z danymi do odtworzenia obliczeń: operację, każdą wartość
ze **źródłem** (`command` — z polecenia, `user` — z odpowiedzi, `known` — podana z Pythona),
pewność decyzji modelu, pliki z sumami SHA-256, wartości zwrócone przez narzędzie,
ostrzeżenia, wersje Retmana i narzędzia oraz czasy. Fragment:

```json
{
 "ok": true,
 "number": 1,
 "operation": "download_elevation_cutout",
 "params": {
  "product": {"value": "dem", "source": "command", "confidence": 0.97, "unverified": false},
  "area": {
   "value": {"type": "bbox", "min_x": 530000.0, "min_y": 382000.0,
             "max_x": 530100.0, "max_y": 382100.0, "crs": "EPSG:2180"},
   "source": "user", "confidence": null, "unverified": false
  }
 },
 "files": {
  "dem": [{"path": "retman-output/001_download_elevation_cutout/nmt/pl_1992_1m_evrf2007/bbox/530000_382000_530100_382100_20261012.tif",
           "sha256": "72702ec1…"}]
 },
 "values": {"masked_pixels": 0, "all_nodata": false, "bytes": 262902}
}
```

### 6.3. Dziennik projektu

```
$ retman log
2026-10-12T08:01:31.735796+00:00 polecenie: Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4
2026-10-12T08:01:31.736630+00:00 pytanie: W którym układzie wysokościowym pobrać NMT: EVRF2007 czy KRON86?
2026-10-12T08:01:31.736755+00:00 odpowiedź: 1
2026-10-12T08:01:31.740853+00:00 plan: odrzucony
…
2026-10-12T08:01:59.830761+00:00 plan: zatwierdzony
2026-10-12T08:02:46.164452+00:00 wykonanie: 1
```

Dziennik jest tylko dopisywany i obejmuje także plany odrzucone, zmienione i przerwane.
Treść poleceń i odpowiedzi zapisuje się przy `[log] journal_commands = true` (domyślnie).

---

## 7. Sesja, opcje i praca bez terminala

### 7.1. Sesja

`retman` bez polecenia otwiera sesję: kolejne polecenia wpisuje się po znaku `>`.
`koniec` zamyka sesję (kod 0), `anuluj` przerywa (kod 3).

### 7.2. Opcje

| Opcja | Działanie |
| --- | --- |
| `--plan-only` | zadaje pytania i pokazuje plan, ale go nie wykonuje (kod 0) |
| `--explain` | pod planem wypisuje decyzje modelu: wybór, pewność, metodę i prawdopodobieństwa opcji |
| `--config PATH` | inny plik konfiguracji niż domyślny |
| `--json` | z `retman doctor`: raport w JSON |

```
$ retman --plan-only "Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4"
Plan:
Operacja: Pobranie NMT dla arkusza
Godło arkusza NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
```

### 7.3. Bez terminala (skrypty, potoki, CI)

Gdy wejście nie jest terminalem, Retman nie zadaje pytań i niczego nie wykonuje — wypisuje,
czego brakuje, i kończy kodem 2:

```
$ retman "Pobierz NMT dla arkusza N-34-130-D-d-2-4" < /dev/null
Plan:
Operacja: Pobranie NMT dla arkusza
Godło arkusza NMT: godło arkusza N-34-130-D-d-2-4
Brakuje: Czy pobrać NMT w rozdzielczości 1 m czy 5 m?, W którym układzie wysokościowym pobrać NMT: EVRF2007 czy KRON86?
```

Pełny plan bez terminala sprawdza się przez `--plan-only`; wykonanie zawsze wymaga
potwierdzenia — w terminalu albo z Pythona (p. 10).

### 7.4. Polecenie spoza zakresu

```
$ retman "Jaka będzie jutro pogoda?"
Błąd: Polecenie nie dotyczy dostępnych operacji: Pobranie NMT dla arkusza, Pobranie arkuszy potomnych (NMT, NMPT albo ortofotomapa), Wycinek NMT albo NMPT dla prostokąta, Pobranie BDOT10k
```

Retman nie dopasowuje na siłę najbliższej operacji (PRD W-03).

---

## 8. Kody wyjścia

| Kod | Znaczenie |
| --- | --- |
| 0 | operacja wykonana, plan pokazany przy `--plan-only`, sesja zakończona `koniec` |
| 1 | błąd: konfiguracja, brak połączenia z modelem, błąd narzędzia, polecenie spoza zakresu |
| 2 | potrzebne odpowiedzi lub potwierdzenie, a wejście nie jest terminalem |
| 3 | przerwane przez użytkownika (`anuluj`, `n`, Ctrl+C) |

`retman doctor`: 0 — da się pracować, 1 — coś blokuje pracę. `retman-eval`: p. 12.

---

## 9. Co Retman potrafi teraz

Operacje Kartografa 0.7.2 (ADR-001); wszystkie pobierają dane z GUGiK:

| Operacja | Obszar | Parametry (Retman dopyta o brakujące) | Przykładowe polecenie |
| --- | --- | --- | --- |
| Pobranie NMT dla arkusza | godło arkusza PL-1992 lub PL-2000 | rozdzielczość 1 m / 5 m; układ wysokościowy EVRF2007 / KRON86 (5 m tylko w EVRF2007) | `Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4` |
| Pobranie arkuszy potomnych | godło arkusza nadrzędnego | produkt NMT / NMPT / ortofotomapa; skala docelowa 1:10000–1:500 (drobniejsze niż 1:10000 tylko w PL-2000); dla NMT rozdzielczość i układ wysokościowy | `Rozwiń N-34-130-D-d-2 do 1:10000, ściągnij DSM z arkuszy potomnych` |
| Wycinek NMT albo NMPT | prostokąt w PL-1992 (EPSG:2180) albo WGS84 (EPSG:4326) | produkt NMT / NMPT; układ wyniku EPSG:2180 / 5514 / 3045 (kod z prefiksem `EPSG:` albo sama liczba, np. `wynik w 2180`); układ wysokościowy | `wytnij dsm z prostokąta 52.40 16.90 52.41 16.91 do 3045` |
| Pobranie BDOT10k | powiat (TERYT, 4 cyfry), godło albo prostokąt | format GeoPackage / Shapefile | `ściągnij bdot dla powiatu 2264 w gpkg` |

Formy zapisu obszaru:

- **godło**: `N-34-130-D-d-2-4` (PL-1992), `5.123.45` (PL-2000);
- **TERYT powiatu**: `TERYT 2264`, `powiat 2264`;
- **prostokąt**: cztery liczby i układ, np. `530000,382000,530100,382100 EPSG:2180` albo
  `52.40 16.90 52.41 16.91` (WGS84). Przy niejednoznacznej kolejności osi Retman pyta (p. 4).

Pliki geometrii (SHP/GPKG) Retman rozpoznaje, ale żadna z obecnych operacji ich nie
przyjmuje.

---

## 10. Retman w Pythonie

Ten sam przebieg — pytania, plan, potwierdzenie — jest dostępny z Pythona:

```python
from pathlib import Path

from retman import Plan, Retman

retman = Retman.from_config(Path("retman.toml"), project_dir=Path("zlewnia-a"))

plan = retman.plan("Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4")
for question in plan.questions:          # tu: vertical_crs
    print(question.text)                 # pytanie w języku użytkownika
    for number, option in enumerate(question.options, start=1):
        print(f"  {number}) {option.label}")
plan = plan.answer("vertical_crs", "1")  # numer albo własne słowa

print(plan.summary())                    # ten sam plan co w terminalu
plan.confirm()                           # bez tego execute() zgłasza PlanNotConfirmedError
result = retman.execute(plan)
if result.ok:
    print(result.summary)
    print(result.files)                  # {"dem": [Path(...)]}
else:
    print(result.error)
```

- `Retman.from_config()` bez ścieżki czyta plik centralny z lokalizacji systemowej,
  a `project_dir` domyślnie to bieżący folder.
- Wartości znane z góry podaje się przez `known` — trafiają do planu ze źródłem `known`
  i nie są nadpisywane przez model:

  ```python
  plan = retman.plan(
      "Pobierz NMT dla arkusza N-34-130-D-d-2-4",
      known={"resolution": "1m", "vertical_crs": "kron86"},
  )
  assert plan.questions == []
  ```

- Plan da się zapisać i wznowić: `plan.to_dict()` (JSON) oraz
  `Plan.from_dict(state, retman=retman)`.
- `plan.change(name)` ponownie otwiera jedną wartość (jak `z` w terminalu).
- Polecenie spoza zakresu zgłasza `retman.exceptions.OutOfScopeError` z listą dostępnych
  operacji w `operations`.

Pełny opis API: ARCHITECTURE 7.1 i 7.3.

---

## 11. Diagnostyka: `retman doctor`

`retman doctor` w jednym miejscu pokazuje, co działa, co nie i jak to naprawić:
plik konfiguracji, folder projektu i zapis wyników, adres serwera modelu (zawsze pokazany,
bez oceniania), czy model jest na serwerze, pytanie testowe z oczywistą odpowiedzią, metodę
pewności i progi, zainstalowane narzędzia na tle obsługiwanych wersji, komplet tłumaczeń.

```
$ retman doctor
Retman 0.1.0.dev0

Konfiguracja
  ✓ plik centralny: retman.toml
  ✓ projekt: <folder projektu> → wyniki w retman-output/ (0 wyników, zapis możliwy)

Model decyzyjny
  ✓ adres modelu (openai_compatible): http://127.0.0.1:18731/v1
  ✓ model: bielik-11b dostępny na serwerze
  ✓ pytanie testowe: poprawna odpowiedź (bez pewności)
  ! pewność: niedostępna (confidence = "none") — wybory modelu w planie są oznaczone jako niezweryfikowane → ustaw confidence = "auto" w retman.toml, jeśli serwer podaje logprobs

Narzędzia
  ✓ kartograf 0.7.2, obsługiwane >=0.7.2,<0.8, 4 operacje

Tłumaczenia (pl)
  ✓ komplet

Model tekstowy
  – wyłączony ([text] backend = "none")
```

(Przebieg na lokalnym serwerze testowym zgodnym z API OpenAI; ścieżki zastąpione opisem.)
Gdy serwer modelu nie działa:

```
Model decyzyjny
  ✗ serwer modelu nie odpowiada (http://127.0.0.1:18731/v1) → uruchom serwer modelu (np. LM Studio albo basal-serve, instrukcja w README) i sprawdź [decision] url w retman.toml
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
retman-eval --config retman.toml --target-error 0.01 --report raport.md --output rekordy.jsonl
```

`retman-eval` planuje każde polecenie ze zbioru (bez wykonywania operacji) i raportuje
trafność operacji i parametrów, błędy przyjęte bez pytania (W-02), ciche zgadywanie,
naruszenia W-03, czasy oraz **zalecane progi** dla zadanego odsetka błędów. Zalecanych progów
nie zapisuje sam — wpisuje się je do `[decision.thresholds]`. Kody wyjścia: 0 — przebieg
zakończony, 1 — błąd konfiguracji, zbioru albo modelu, 3 — przerwany, 4 — wystąpiło
naruszenie W-03. Opcje i miary: `docs/specs/2026-10-11-retman-eval.md`.

---

## 13. Dobre praktyki i ograniczenia

- **Podawaj w poleceniu wszystko, co wiesz** — rozdzielczość, układ, format. Retman nie
  przyjmuje wartości domyślnych za użytkownika; czego brakuje, o to zapyta.
- **Czytaj plan przed `t`.** Wartości z odpowiedzi i z polecenia są tam w postaci, w jakiej
  Retman je zrozumiał; wybory modelu bez pewności są oznaczone „wybór modelu
  niezweryfikowany”.
- **Współrzędne PL-1992**: przy zapisie bez wskazania kolejności osi Retman pyta, który
  odczyt jest właściwy (p. 4).
- **BDOT10k** dla godła lub prostokąta pobiera pełne pakiety każdego przecinanego powiatu,
  bez przycinania — pliki mogą być duże.
- Pobierany jest najnowszy dostępny materiał GUGiK; wyboru rocznika i kampanii jeszcze nie ma.
- Folder projektu na udziale sieciowym (np. CIFS) może uniemożliwić Kartografowi użycie cache
  metadanych („database is locked”); praca trwa wtedy bez cache.
