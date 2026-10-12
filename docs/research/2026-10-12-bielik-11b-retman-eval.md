# Bielik 11B w `retman-eval` — pierwszy przebieg (2026-10-12)

**Status:** przebieg roboczy na **szkicu** zbioru poleceń (przed przeglądem autora, spec.
`docs/specs/2026-10-11-retman-eval.md` rozdz. 10 pkt 2).
**Pełny raport z narzędzia:** `2026-10-12-bielik-11b-retman-eval-raport.md` (miary, krzywe
progów, błędne przypadki, czasy).

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

## Wnioski i następne kroki

1. Progi do decyzji autora: operacja 0,70 jest dobrze uzasadniona danymi; parametry 0,94
   oznaczają bardzo dużo pytań — lepiej najpierw poprawić trafność `product`/`format`.
2. Strojenie opisów: `product` (najpilniejsze), `format`, opis operacji arkuszy potomnych;
   każda zmiana sprawdzana przebiegiem na tym samym zbiorze (ok. 14 min).
3. `target_crs`: rozważyć rozpoznawanie kodu układu wyniku w kodzie (ADR) — model myli kod
   prostokąta z układem wyniku z wysoką pewnością.
4. Przegląd zbioru przez autora, potem przebieg z `--repeat 3` (stabilność) i większym
   zbiorem, by potwierdzić błąd ≤ 1% (≥ 100 decyzji ponad progiem).
