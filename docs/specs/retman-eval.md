# Specyfikacja: `retman-eval`

**Status:** projekt do akceptacji autora
**Data:** 2026-10-11
**Podstawa:** PRD W-01, W-02, W-03, N-05, N-07, rozdz. 8; ARCHITECTURE 3.4, 6.2, 8.1–8.3, 9.2;
STANDARDS 6.3, 6.4, 10.4, 17.1

## 1. Cel

`retman-eval` mierzy, jak dobrze Retman **planuje** polecenia: czy rozpoznaje operację,
czy poprawnie ustala parametry, kiedy dopytuje i jak często myli się, nie pytając.
Wynik służy do:

1. sprawdzenia wymagań W-01 (trafność rozpoznania), W-02 (≤ 1% błędów wśród decyzji
   podjętych bez dopytywania) i W-03 (polecenia spoza zakresu niczego nie uruchamiają),
2. **dostrojenia progów pewności** dla konkretnego modelu — obowiązkowego dla backendów innych
   niż basal (ARCHITECTURE 6.2),
3. strojenia opisów operacji i opcji w `pl.toml` (ARCHITECTURE 4.2, 12 pkt 5),
4. porównania modeli i backendów na tym samym zbiorze (ARCHITECTURE 8.2, 12 pkt 11),
5. zebrania czasów od polecenia do planu (PRD N-07, ARCHITECTURE 9.2).

**Poza zakresem:** wykonywanie operacji (eval nigdy nie wywołuje handlerów ani narzędzi,
ARCHITECTURE 6.3), ocena opisów wyników (`TextBackend`, v0.2), łańcuchy (v0.2).

## 2. Zbiór poleceń testowych

### 2.1. Plik i format

`retman/eval/commands.jsonl` — dane pakietu, instalowane z Retmanem (ARCHITECTURE 8.1),
UTF-8, LF, jeden obiekt JSON w linii. Polecenia po polsku, identyfikatory po angielsku.

| Pole | Wymagane | Znaczenie |
| --- | --- | --- |
| `id` | tak | unikalny identyfikator, np. `"kartograf-dem-sheet-007"`; stabilny między wersjami zbioru |
| `command` | tak | treść polecenia |
| `operation` | tak | oczekiwany identyfikator operacji albo `"out_of_scope"` |
| `params` | nie | **tylko wartości podane w poleceniu**, w postaci znormalizowanej jak w planie: klucze opcji dla `choice` (np. `"5m"`), `true`/`false` dla `bool`, wartości ekstraktora dla `free` (np. `{"type": "sheet", "code": "N-34-130-D-d-2-4"}`) |
| `expect_clarify` | nie | parametry, o które Retman **musi** zapytać: polecenie ich nie podaje, a parametr jest wymagany (np. `["target_crs", "vertical_crs"]`), albo zapis ma kilka odczytów (np. dwa odczyty prostokąta PL-1992) |
| `tags` | tak | kategorie z p. 2.3, co najmniej jedna |
| `note` | nie | uzasadnienie oczekiwań w trudnych przypadkach (po polsku) |

Każdy parametr operacji, który ma zastosowanie (z uwzględnieniem `depends_on`), jest
**dokładnie w jednym** z pól `params` albo `expect_clarify` — zbiór nie zostawia parametrów
bez oczekiwania. Dla parametru niepodanego w poleceniu poprawną decyzją modelu jest
`unspecified`, a Retman musi o niego zapytać. Operacje Kartografa nie mają wartości
domyślnych (ADR-006). Gdyby inna operacja miała `default`, parametr niepodany w poleceniu
nie trafia do `expect_clarify`, a pytanie o niego liczy się jako zbędne (p. 5.2).

Przykłady:

```json
{"id": "kartograf-dem-sheet-001", "command": "Pobierz NMT 5 m dla arkusza N-34-130-D-d-2-4", "operation": "download_dem_sheet", "params": {"area": {"type": "sheet", "code": "N-34-130-D-d-2-4"}, "resolution": "5m"}, "expect_clarify": ["vertical_crs"], "tags": ["formal", "incomplete"]}
{"id": "kartograf-cutout-004", "command": "wytnij mi dsm z prostokąta 52.40 16.90 52.41 16.91", "operation": "download_elevation_cutout", "params": {"product": "dsm", "area": {"type": "bbox", "min_x": 16.9, "min_y": 52.4, "max_x": 16.91, "max_y": 52.41, "crs": "EPSG:4326"}}, "expect_clarify": ["target_crs", "vertical_crs"], "tags": ["colloquial", "incomplete"]}
{"id": "oos-003", "command": "Jaka będzie jutro pogoda w Poznaniu?", "operation": "out_of_scope", "tags": ["out_of_scope"]}
```

### 2.2. Walidacja zbioru (test offline)

Test w `tests/eval/` sprawdza bez modelu, że każdy wpis:

- ma unikalne `id` i poprawny JSON,
- wskazuje istniejącą operację (albo `out_of_scope`) i istniejące parametry tej operacji,
- ma w `params` wartości dozwolone przez manifest (`options`, `accepts`, `range`),
- dla parametrów `free` ma wartości, które **ekstraktor rzeczywiście wyciąga** z `command`
  (ten sam kod co w planowaniu) — rozbieżność to błąd zbioru, nie modelu,
- nie wymienia tego samego parametru w `params` i `expect_clarify`,
- obejmuje polami `params` i `expect_clarify` wszystkie parametry, które mają zastosowanie
  przy oczekiwanych wartościach (`depends_on`), oprócz tych z `default`.

Zbiór jest sprawdzany dla operacji **wszystkich** narzędzi z `retman/tools/`, nie tylko
zainstalowanych.

### 2.3. Zasady budowy (ARCHITECTURE 8.1)

| Tag | Znaczenie | Minimum |
| --- | --- | --- |
| `formal` | zapis urzędowy, pełne nazwy | — |
| `colloquial` | język potoczny, skróty („nmt”, „dsm”, „ortofoto”) | — |
| `typo` | literówki, brak polskich znaków | — |
| `incomplete` | brak wymaganej wartości → oczekiwane `expect_clarify` | — |
| `ambiguous` | zapis o kilku odczytach (np. kolejność osi PL-1992) | — |
| `complete` | polecenie podaje wszystkie parametry — oczekiwany plan bez pytań | 3 na operację |
| `out_of_scope` | polecenie nie dotyczy żadnej operacji | 10 w całym zbiorze |
| `near_miss` | polecenie bliskie zakresowi, ale niewykonalne (np. LAZ, opady) | 5 w całym zbiorze |

- **Co najmniej 15 poleceń na operację**, w tym co najmniej 3 `incomplete` albo
  `ambiguous` i co najmniej 3 `colloquial` albo `typo`.
- Każda opcja każdego parametru `choice` pojawia się w co najmniej jednym poleceniu.
- Każda forma obszaru przyjmowana przez operację (`accepts`) pojawia się w co najmniej dwóch
  poleceniach.
- Po udostępnieniu testerom: dopisywanie prawdziwych poleceń za zgodą użytkowników
  (rozdz. 10 ARCHITECTURE); nowe wpisy dostają nowe `id`, istniejące się nie zmieniają.

Na start: cztery operacje Kartografa (ADR-001) → co najmniej 60 poleceń + 15 spoza zakresu
i bliskich zakresowi.

## 3. Uruchomienie

```bash
retman-eval --config PATH [--commands PATH] [--operations ID[,ID...]] [--tags TAG[,TAG...]]
            [--repeat N] [--target-error P] [--output RAW.jsonl] [--report REPORT.md]
```

| Opcja | Znaczenie |
| --- | --- |
| `--config` | plik centralny z backendem, modelem, progami i timeoutem; **wymagany** — eval nigdy nie czyta domyślnego pliku użytkownika po cichu, bo porównuje konfiguracje |
| `--commands` | inny zbiór (np. roboczy); domyślnie zbiór z pakietu |
| `--operations`, `--tags` | zawężenie zbioru |
| `--repeat N` | każde polecenie N razy (stabilność modeli losujących); domyślnie 1 |
| `--target-error P` | docelowy odsetek błędów powyżej progu (np. `0.01` dla W-02); tylko z tą opcją raport podaje zalecane progi (p. 5.3) |
| `--output` | surowe rekordy (p. 4.3) do dalszej analizy |
| `--report` | raport Markdown; bez opcji raport trafia na standardowe wyjście |

Raporty z przebiegów na modelach zapisuje się w `docs/research/` (STANDARDS 6.4).

**Kody wyjścia:**

| Kod | Znaczenie |
| --- | --- |
| `0` | przebieg zakończony; miary są tylko raportowane — eval mierzy, nie ocenia |
| `1` | błąd konfiguracji, zbioru albo backendu (np. brak połączenia z modelem — przerywa przebieg, raport częściowy nie powstaje) |
| `3` | przerwane przez użytkownika |
| `4` | przebieg zakończony, ale wystąpiło **naruszenie W-03** (p. 5.2) — jedyne kryterium oceniane zawsze, bo wymaganie jest bezwzględne („0”) i nie zależy od szumu |

Progi dla pozostałych miar nie są wpisane w kod. Gdy PRD ustali wartości docelowe, można
dodać opcję z wartościami podanymi wprost (np. `--require operation=0.95,error=0.01`);
domyślnie dalej `0`, bo eval wymaga działającego modelu, nie wchodzi do bramki offline,
a wyniki na kilkudziesięciu poleceniach są zaszumione.

## 4. Przebieg dla jednego polecenia

### 4.1. Izolacja

- Każde polecenie planuje **nowy obiekt `Retman`** z `--config`, z folderem projektu
  w katalogu tymczasowym (pusty: bez wcześniejszych wyników, dziennik nie trafia do folderu
  użytkownika). Katalog jest usuwany po przebiegu.
- Używany jest ten sam pipeline co w CLI (`Retman.plan`, `Plan.answer`); eval nie ma własnej
  logiki decyzji.
- Eval nie wywołuje `confirm()` ani `execute()`.
- Sieć: tylko serwer modelu z `--config`.

### 4.2. Kroki

1. `plan = retman.plan(command)`; pomiar czasu ściennego (`plan_s`).
2. Polecenie spoza zakresu kończy się wyjątkiem **`OutOfScopeError`** (nowa podklasa
   `RetmanError` z atrybutem `operations`; dziś pipeline zgłasza ogólny `RetmanError`,
   p. 7). Eval zapisuje wynik `out_of_scope`.
3. Jeśli plan pyta o operację (niska pewność), eval zapisuje pytanie i jego opcje, a potem
   — **jak użytkownik znający właściwą odpowiedź** — wybiera oczekiwaną operację numerem,
   o ile jest wśród opcji. To pozwala zmierzyć parametry także wtedy. Gdy oczekiwanej
   operacji nie ma wśród opcji, rekord dostaje `operation_offered = false` i parametry
   nie są oceniane.
4. Eval **nie odpowiada** na pytania o parametry: zapisuje ich listę (nazwy i typy).
5. Zapisuje decyzje modelu z `plan.decisions` (nazwa, wybrany klucz, prawdopodobieństwa,
   pewność, metoda), wartości z `plan.values` ze źródłami oraz pytania.

### 4.3. Surowy rekord (`--output`)

Jedna linia na przebieg polecenia (przy `--repeat` — na każde powtórzenie):

```json
{"id": "...", "repeat": 0, "expected": {"operation": "...", "params": {}, "expect_clarify": []},
 "outcome": "plan" | "out_of_scope" | "error",
 "operation_question": {"asked": true, "offered": ["...", "..."]},
 "decisions": [{"name": "operation", "key": "...", "confidence": 0.93, "method": "logprobs", "probabilities": {}}],
 "values": {"resolution": {"value": "5m", "source": "command"}},
 "questions": ["target_crs"],
 "plan_s": 6.8,
 "environment": {"retman": "...", "tools": {"kartograf": "0.7.2"}, "backend": "openai_compatible", "model": "...", "confidence": "logprobs", "thresholds": {"operation": 0.9, "parameter": 0.9}}}
```

Rekord **nie zawiera adresu serwera modelu** ani ścieżek lokalnych — raporty trafiają do
repozytorium (p. 3), a o adresie decyduje użytkownik (ARCHITECTURE rozdz. 10).

## 5. Miary

### 5.1. Ocena pojedynczych decyzji i wartości

| Element | Poprawny, gdy |
| --- | --- |
| decyzja `operation` | klucz = oczekiwana operacja (także `out_of_scope`) |
| decyzja parametru `choice`/`bool` z oczekiwaną wartością | klucz = wartość z `params` |
| decyzja parametru, którego polecenie nie określa | klucz = `unspecified` (Retman ma zapytać); inny klucz przyjęty bez pytania to **ciche zgadywanie** — błąd |
| wartość `free` (ekstraktor) | wartość w planie = wartość z `params` (równość dokładna — obie pochodzą z tego samego kodu) |

Decyzja jest **przyjęta bez pytania**, gdy pipeline nie zadał o nią pytania (pewność ≥ próg
albo metoda `none`).

### 5.2. Miary raportu (ARCHITECTURE 8.2)

| Miara | Definicja |
| --- | --- |
| Trafność operacji | poprawne decyzje `operation` / wszystkie polecenia (z `out_of_scope`); osobno: w zakresie, spoza zakresu |
| Trafność parametrów | poprawne wartości / oczekiwane wartości z `params` — z podziałem: poprawne bez pytania, błędne bez pytania, zapytane |
| Pokrycie automatyczne | polecenia `complete` (bez `expect_clarify`), których plan nie zadał żadnego pytania / wszystkie takie polecenia |
| **Błąd przy pewności (W-02)** | błędne decyzje przyjęte bez pytania / wszystkie decyzje przyjęte bez pytania; osobno dla operacji, parametrów modelu i wartości ekstraktorów, oraz łącznie |
| Ciche zgadywanie | decyzje inne niż `unspecified` przyjęte bez pytania dla parametrów, których polecenie nie określa |
| Trafne dopytania | parametry z `expect_clarify`, o które zapytano / wszystkie z `expect_clarify` (czułość) |
| Pytania zbędne | pytania o parametry, których wartość **jest** w `params` (model niepewny mimo podanej wartości), oraz — w operacjach z `default` — o parametry niepodane; liczone jako koszt na polecenie, nie jako błąd; strojenie opisów i progów ma je zmniejszać |
| **Naruszenia W-03** | polecenia `out_of_scope`, dla których powstał plan z operacją i bez pytania o operację; wymagane 0 |
| Stabilność (`--repeat`) | odsetek poleceń z identycznymi kluczami decyzji we wszystkich powtórzeniach |
| Czas planu (N-07) | mediana, 90. percentyl i maksimum `plan_s`; osobno liczba zapytań do modelu na plan |

Każda miara jest podawana jako ułamek **i** liczebność (np. `0,93 (56/60)`), z podziałem
na operacje i tagi. Błędne przypadki są wypisane z `id`, poleceniem, oczekiwaniem
i decyzją — to materiał do poprawiania opisów w `pl.toml`.

### 5.3. Krzywa progów i zalecane progi

Decyzje są zapisane z pewnością, więc eval liczy miary dla **dowolnego progu** bez
ponownego pytania modelu:

- dla każdej obserwowanej wartości pewności `t` (osobno dla operacji i parametrów):
  odsetek błędów wśród decyzji o pewności ≥ `t` oraz odsetek decyzji, które przy `t` byłyby
  przyjęte bez pytania;
- z `--target-error P`: **zalecany próg** = najmniejsze `t`, przy którym odsetek błędów
  ≤ `P`, wraz z liczbą decyzji powyżej progu. Przy mniej niż 1/`P` decyzjach powyżej progu
  raport ostrzega, że zbiór jest za mały, by potwierdzić `P`.

Krzywa dotyczy decyzji modelu zebranych przy **progach z `--config`**. Decyzje parametrów
z planów, w których operacja wymagała pytania, pochodzą z kroku 4.2.3 (odpowiedź jak
użytkownik), więc są dostępne niezależnie od progu operacji.

Zalecane progi nie są zapisywane automatycznie: użytkownik wpisuje je do `retman.toml`
(brak ukrytych wartości, PRD N-11).

## 6. Raport

Markdown, po polsku, z sekcjami: konfiguracja (wersje, backend, model, metoda pewności,
progi — bez adresu), zbiór (liczba poleceń według operacji i tagów), miary z p. 5.2,
krzywe i zalecane progi z p. 5.3, lista błędów, lista naruszeń W-03, czasy. Teksty raportu
są w `retman/i18n/pl.toml` (sekcja `[eval]`), jak wszystkie teksty dla użytkownika.

## 7. Zmiany w kodzie potrzebne do eval

| Zmiana | Gdzie | Powód |
| --- | --- | --- |
| `OutOfScopeError(RetmanError)` z atrybutem `operations` | `retman/exceptions.py`, `core/pipeline.py`, `cli.py` | eval musi odróżnić „spoza zakresu” od błędu; CLI może wtedy pominąć prefiks „Błąd:” |
| liczba zapytań do modelu na plan | licznik w pipeline albo opakowanie backendu w eval | miara czasu (p. 5.2) |
| `retman-eval` w `[project.scripts]` | `pyproject.toml` | ARCHITECTURE 9.3: pakiet podstawowy, bez dodatkowych zależności |
| moduły `retman/eval/{runner,metrics,report}.py`, dane `retman/eval/commands.jsonl` | ARCHITECTURE 3.1 | — |

## 8. Testy (offline, `FakeDecisionBackend`)

- walidacja zbioru z p. 2.2 na prawdziwym `commands.jsonl`;
- miary na małym zbiorze sztucznym z zadanymi decyzjami i pewnościami: każda definicja
  z p. 5.2, w tym ciche zgadywanie, naruszenie W-03 i pytanie o operację z odpowiedzią
  „jak użytkownik”;
- krzywa progów i zalecany próg na danych z dokładnie znanym wynikiem, w tym ostrzeżenie
  o zbyt małym zbiorze;
- izolacja: przebieg nie tworzy plików poza katalogiem tymczasowym i nie wywołuje handlerów;
- rekordy i raport nie zawierają adresu z `--config`.

Test `live` (świadomie, `-m live`): jeden przebieg kilku poleceń na serwerze z
`--live-openai-url`.

## 9. Kryteria akceptacji

1. `retman-eval --config <plik z LM Studio>` przechodzi cały zbiór Kartografa i tworzy
   raport z wszystkimi miarami z p. 5.2 i krzywą z p. 5.3.
2. Raport z przebiegu Bielik 11B (`logprobs`) trafia do `docs/research/`, z zaleceniem progów
   dla `--target-error 0.01`.
3. Testy z p. 8 przechodzą offline; bramka STANDARDS 18 czysta.
4. Specyfikacja i PROGRESS opisują stan; ARCHITECTURE 8.1–8.2 zostaje bez zmian do decyzji
   z p. 10.1.

## 10. Decyzje autora

1. **Wywołanie i backend** (2026-10-11): ARCHITECTURE 8.2 (`--backend basal`) na razie bez
   zmian. basal-serve nie jest jeszcze dostępny, więc eval powstaje i działa na tym, co jest
   (`openai_compatible`, LM Studio) przez `--config PATH`; sposób wywołania do ponownego
   rozpatrzenia, gdy powstanie backend `basal`.
2. **Autor zbioru** (2026-10-11): zbiór startowy przygotowuje agent jako szkic, autor go
   przegląda przed pierwszym przebiegiem.
3. **Kod wyjścia** (2026-10-11): wg rekomendacji — `0` niezależnie od miar, `4` przy
   naruszeniu W-03 (p. 3); progi pozostałych miar ewentualnie później, jawną opcją.
4. **Wartości domyślne** (2026-10-11, ADR-006): operacje Kartografa nie mają wartości
   domyślnych; Retman ma dopytywać o szczegóły niepodane w poleceniu (p. 2.1, 5.1).
