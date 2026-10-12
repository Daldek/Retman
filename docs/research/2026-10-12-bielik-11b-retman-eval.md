# Bielik 11B w `retman-eval` — pierwszy przebieg (2026-10-12)

**Status:** przebieg roboczy na **szkicu** zbioru poleceń (przed przeglądem autora, spec.
`docs/specs/2026-10-11-retman-eval.md` rozdz. 10 pkt 2).
**Pełne raporty z narzędzia:** `2026-10-12-bielik-11b-retman-eval-raport.md` (przed
zmianami), `…-model-question-raport.md` (po ADR-008) i `…-crs-raport.md` (po ADR-009) —
miary, krzywe progów, błędne przypadki, czasy.

## Konfiguracja

| Element | Wartość |
| --- | --- |
| Retman | 0.1.0.dev0 (`develop`, po `500e607`) |
| Narzędzie | Kartograf 0.7.2, 4 operacje |
| Backend | `openai_compatible`, LM Studio (adres poza repozytorium) |
| Model | `bielik-11b-v3.0-instruct-mlx` |
| Pewność | `logprobs` |
| Progi w przebiegu | operacja 0.9, parametr 0.9 |
| Zbiór | 79 poleceń: 4 × 15–19 Kartografa + 10 spoza zakresu + 5 bliskich zakresowi; `--repeat 1` |
| Uruchomienie | `retman-eval --config <plik> --target-error 0.01`; `retman doctor` przed przebiegiem: wszystko ✓ |

## Najważniejsze wyniki

| Miara | Wynik |
| --- | --- |
| Trafność operacji | 0,89 (70/79); w zakresie 57/64, spoza zakresu 13/15 |
| Naruszenia W-03 | **0** (0/15) |
| Błąd przyjęty bez pytania (W-02), łącznie | 0,01 (2/137) — oba przypadki to ciche zgadywanie `target_crs` (niżej) |
| Wartości z ekstraktorów | 0 błędów (0/59) |
| Trafne dopytania | 0,85 (35/41) |
| Pokrycie automatyczne poleceń kompletnych | **0,17 (6/36)** |
| Pytania zbędne | 0,84 na polecenie (66/79) |
| Czas planu | mediana 11,1 s, P90 14,9 s, max 15,1 s; 1–4 zapytania do modelu, ok. 3,7 s na zapytanie |

**Zalecane progi** (`--target-error 0.01`):

- operacja: **0,70** — 64/79 decyzji powyżej progu, 0 błędów;
- parametry modelu: **0,94** — tylko 23/130 decyzji powyżej progu, 0 błędów.

Oba zalecenia są **niepotwierdzone**: powyżej progu jest mniej niż 100 decyzji, więc zbiór
jest za mały, by wykazać błąd ≤ 1%. Progów nie wpisano do żadnej konfiguracji.

## Obserwacje

### 1. Rozpoznanie operacji — dobre, z wyjątkiem arkuszy potomnych

Wszystkie 9 błędnych decyzji o operacji miało pewność ≤ 0,66, więc przy progu 0,70 każda
kończy się pytaniem o operację. 6 z 9 dotyczy `download_sheet_hierarchy` (9/15 trafnych):
model myli „arkusze potomne / spod godła / rozwiń / dzieci” z NMT dla arkusza albo
z wycinkiem. Kandydat do strojenia: opis operacji w `pl.toml` (słowa „rozwiń”, „spod
godła”, „potomne”, „hierarchia” na początku opisu).

Bliskie zakresowi: `near-001` (LAZ → wycinek, 0,38) i `near-004` (HSG → BDOT10k, 0,42) —
niska pewność, więc pytanie zamiast wykonania; W-03 nie naruszone.

### 2. Parametry — model często wybiera „nie podano” mimo podanej wartości

Trafność decyzji parametrów (klucz = oczekiwany, z `unspecified` dla niepodanych):

| Parametr | Trafne | Uwagi |
| --- | --- | --- |
| `product` | **16/33** | 17 razy `unspecified` mimo „NMT”, „DSM”, „NMPT”, „DTM” w poleceniu (np. „Wytnij DSM …” → `unspecified` 0,88) |
| `target_crs` | 13/19 | 4 razy kod układu **prostokąta wejściowego** wzięty za układ wyniku (pkt 3) |
| `format` | 12/15 | „w GPKG”, „do shp” → `unspecified` |
| `vertical_crs` | 32/34 | |
| `resolution` | 13/15 | |
| `target_scale` | 13/14 | |

Skutek: Retman jest bezpieczny (pyta), ale męczący — tylko 6 z 36 poleceń kompletnych
przechodzi bez pytań, a przy zalecanym progu 0,94 dla parametrów pytań byłoby jeszcze więcej.

**Eksperyment (odrzucony):** opisy `unspecified` bez nazw opcji („Polecenie nie określa
rodzaju danych” zamiast „Nie podano produktu — dopytaj o NMT lub NMPT”). Wynik na tym samym
zbiorze: `product` 11/33 (gorzej), `format` 9/15 (gorzej), `resolution` 15/15,
`vertical_crs` 33/34, `target_scale` 14/14 (lepiej); pokrycie automatyczne 3/36. Hipoteza,
że nazwy opcji w opisie `unspecified` przyciągają model, się nie potwierdziła; teksty
przywrócono. Przyczyna słabego `product` pozostaje otwarta — kandydaci: brzmienie pytania
(„Czy wycinek ma zawierać NMT (teren) czy NMPT (pokrycie terenu)?”), kolejność opcji,
dłuższe opisy z „DSM”/„DEM” na początku.

### 3. Ciche zgadywanie `target_crs` — jedyne naruszenia W-02

`kartograf-cutout-008` („… 530000 382000 530100 382100 PL-1992.”) i `-015` („… w pl-1992”):
układ podany dla prostokąta wejściowego model przyjął jako układ wyniku z pewnością 0,943
i 0,925 — **powyżej** progu 0,9, więc bez pytania. Przy zalecanym progu 0,9436 oba trafiłyby
do pytania, ale `-008` z zapasem 0,0004. Tak samo pomylił się w `-009` (0,88) i `-019`
(0,66), tam poniżej progu. Opis `unspecified` mówiący, że układ prostokąta nie jest
układem wyniku (zmiana `500e607`), tego nie zapobiegł. Model nie odróżnia ról tego samego
kodu w zdaniu — argument za rozpoznawaniem kodu EPSG układu wyniku w kodzie Retmana
(reguły kontekstu „wynik / do / przelicz”), zamiast w modelu.

### 4. Kody EPSG bez prefiksu

`kartograf-cutout-016` („wynik w 2180”) → `epsg_2180` (0,68), `-017` („do układu 5514”)
→ `epsg_5514` (0,47): model wybiera właściwy kod, ale z niską pewnością, więc Retman pyta.
`-018` („w 2180, przelicz do 3045”) — błędna operacja (0,49 → pytanie). `-019` („w układzie
2180”, dwuznaczne) → `epsg_2180` z pewnością 0,66 — pytanie, zgodnie z oczekiwaniem.

## Zmiany w `retman-eval` wynikające z przebiegu

Lista „Błędne przypadki” wymieniała też wartości, o które Retman zapytał, i parametry
zależne od niezapytanego jeszcze parametru (`depends_on`) — ok. 90 pozycji szumu. Teraz
wypisywane są tylko wartości **przyjęte** błędnie (bez zmian w miarach); raport w tym
katalogu wygenerowano ponownie z tych samych surowych rekordów.

## Diagnostyka: brzmienie pytania do modelu

Pojedyncze decyzje parametrów wysłane wprost do tego samego serwera (ten sam format promptu
co backend `openai_compatible`, `logprobs`, jeden przebieg), na poleceniach ze zbioru.
Wariant „neutralne” zastępuje pytanie dla użytkownika (np. „Czy wycinek ma zawierać NMT
(teren) czy NMPT (pokrycie terenu)?”) pytaniem o to, **co wymienia polecenie** (np. „Jakiego
rodzaju dane wymienia polecenie?”); opisy opcji bez zmian.

| Parametr | Pytanie dla użytkownika: trafne / pewne ≥ 0,9 | Pytanie neutralne: trafne / pewne ≥ 0,9 | Błędne ≥ 0,9 (przed → po) |
| --- | --- | --- | --- |
| `product` | 17/34 / 4 | **32/34 / 21** | 0 → 0 |
| `format` | 12/15 / 3 | 14/15 / 8 | 0 → 0 |
| `vertical_crs` | 36/40 / 14 | 37/40 / 21 | 0 → 0 |
| `resolution` | 19/21 / 10 | 19/21 / 13 | 0 → 0 |
| `target_scale` | 13/15 / 6 | 15/15 / 8 | 0 → 0 |
| `target_crs` | 13/19 / 3 | 14/19 / 6 | 2 → 2 |

Dla `product` sprawdzono też kolejność opcji (`unspecified` jako pierwsza opcja, pytanie
bez zmian): 21/34, pewne ≥ 0,9: 4 — efekt kolejności jest mały wobec brzmienia pytania.

Wnioski: pytania w formie „czy X, czy Y?” są dobre dla użytkownika, ale model odczytuje je
jako niewiadomą i wybiera „nie podano”. Model potrzebuje osobnego pytania o to, co jest
w poleceniu (analogicznie do `label`/`description`, ADR-007). `target_crs` nie poprawia
się — błąd wynika z roli kodu w zdaniu (prostokąt wejściowy vs wynik), nie z pytania.

## Po zmianie: osobne pytanie dla modelu (ADR-008)

Pełny przebieg `retman-eval` na tym samym zbiorze, serwerze i progach, z `model_question`
w `retman/tools/kartograf/pl.toml`:

| Miara | Przed | Po |
| --- | --- | --- |
| Trafność wartości parametrów | 0,55 (90/164) | **0,78 (128/164)** |
| Wartości, o które zapytano mimo podania | 66 | **30** |
| Pokrycie automatyczne poleceń kompletnych | 6/36 | **11/36** |
| Trafne dopytania | 0,85 (35/41) | 0,93 (38/41) |
| Błąd bez pytania (W-02) | 2/137 | 1/174 |
| Trafność operacji / naruszenia W-03 | 0,89 / 0 | 0,89 / 0 (bez zmian — pytanie o operację niezmienione) |
| Zalecany próg parametrów (`--target-error 0.01`) | 0,94 (23/130 decyzji) | 0,97 (39/134 decyzji) |
| Czas planu (mediana / P90) | 11,1 / 14,9 s | 10,9 / 14,6 s |

Decyzje parametrów (trafne / pewne ≥ 0,9): `product` 32/33 / 21, `format` 14/15 / 8,
`vertical_crs` 33/36 / 20, `resolution` 16/17 / 11, `target_scale` 14/14 / 8,
`target_crs` 14/19 / 5. Jedyne ciche zgadywanie: `kartograf-cutout-008` (`target_crs` z kodu
prostokąta wejściowego) — pozostaje do rozwiązania w kodzie (pkt 3 niżej).

## Po zmianie: układ wyniku rozpoznawany w kodzie (ADR-009)

Pełny przebieg na zbiorze rozszerzonym o 4 polecenia z literówkami w układzie
(`kartograf-cutout-020`–`023`, razem 83), ten sam serwer i progi:

| Miara | Po ADR-008 | Po ADR-009 |
| --- | --- | --- |
| Błąd bez pytania (W-02) | 1/174 | **0/189** |
| Ciche zgadywanie | 1 | **0** |
| Trafność wartości parametrów | 0,78 (128/164) | 0,80 (144/179) |
| Pokrycie automatyczne poleceń kompletnych | 11/36 | 14/39 |
| Trafne dopytania | 0,93 (38/41) | 0,95 (40/42) |
| Trafność operacji / naruszenia W-03 | 0,89 / 0 | 0,88 (73/83) / 0 |
| Zalecany próg parametrów (`--target-error 0.01`) | 0,97 (39/134) | **0,67** (104/123, 1 błąd) |
| Czas planu (mediana / P90) | 10,9 / 14,6 s | 10,6 / 11,8 s (o jedno zapytanie mniej przy wycinku) |

`target_crs` zgodny z oczekiwaniem we wszystkich 23 poleceniach wycinka: 15 wartości
z polecenia, w tym z literówkami („wyink w 2180”, „przelic do sjtsk”, „uklad wynikowy
3045”), i 8 pytań — w tym układ zaraz po współrzędnych (`-008`, `-009`, `-015`, `-019`)
i literówka w kodzie (`-023`). Zalecany próg parametrów spadł, bo zniknęły błędy `target_crs`
z wysoką pewnością; 104 decyzje ponad progiem to granica wymaganej liczby (≥ 100), więc
zalecenie jest słabo potwierdzone. Nowe błędy operacji: `-022` (polecenie bez czasownika)
i dalej `-018`.

## Wnioski i następne kroki

1. Progi do decyzji autora: operacja ok. 0,70 (66–70 decyzji ponad progiem, bez błędów);
   parametry po ADR-009 — 0,67 (1 błąd na 104), do potwierdzenia przebiegiem `--repeat 3`.
2. Strojenie: opis operacji arkuszy potomnych (6 z 10 błędów operacji); `product`
   i `format` naprawione przez ADR-008. Każda zmiana sprawdzana przebiegiem (ok. 14 min).
3. `target_crs`: rozwiązane w kodzie (ADR-009) — 0 cichych zgadnięć.
4. Przegląd zbioru przez autora, potem przebieg z `--repeat 3` (stabilność) i większym
   zbiorem, by potwierdzić błąd ≤ 1% (≥ 100 decyzji ponad progiem).
