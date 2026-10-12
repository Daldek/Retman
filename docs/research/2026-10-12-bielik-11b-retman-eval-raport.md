# Ocena planowania Retmana

## Konfiguracja

- Retman: 0.1.0.dev0
- Narzędzia: kartograf 0.7.2
- Backend: openai_compatible
- Model: bielik-11b-v3.0-instruct-mlx
- Metoda pewności: logprobs
- Progi: operacja 0.9, parametr 0.9

## Zbiór

Polecenia: 79; przebiegi: 79.

### Polecenia według operacji
| Operacja | Liczba |
| --- | --- |
| download_bdot10k | 15 |
| download_dem_sheet | 15 |
| download_elevation_cutout | 19 |
| download_sheet_hierarchy | 15 |
| out_of_scope | 15 |

### Polecenia według tagu
| Tag | Liczba |
| --- | --- |
| ambiguous | 5 |
| colloquial | 22 |
| complete | 36 |
| formal | 33 |
| incomplete | 23 |
| near_miss | 5 |
| out_of_scope | 10 |
| typo | 10 |

## Miary
| Miara | Wynik |
| --- | --- |
| Trafność operacji | 0,89 (70/79) |
| Trafność operacji w zakresie | 0,89 (57/64) |
| Trafność rozpoznania spoza zakresu | 0,87 (13/15) |
| Trafność wartości parametrów | 0,55 (90/164) |
| Poprawne wartości bez pytania | 0,55 (90/164) |
| Błędne wartości bez pytania | 0,05 (8/164) |
| Wartości, o które zapytano | 0,40 (66/164) |
| Pokrycie automatyczne poleceń kompletnych | 0,17 (6/36) |
| Błąd bez pytania W-02 — łącznie | 0,01 (2/137) |
| Błąd bez pytania W-02 — operacja | 0,00 (0/45) |
| Błąd bez pytania W-02 — parametry modelu | 0,06 (2/33) |
| Błąd bez pytania W-02 — ekstraktory | 0,00 (0/59) |
| Ciche zgadywanie | 1,00 (2/2) |
| Trafne dopytania (czułość) | 0,85 (35/41) |
| Pytania zbędne na polecenie | 0,84 (66/79) |
| Naruszenia W-03 | 0,00 (0/15) |

### Według operacji
| Operacja | Miara | Wynik |
| --- | --- | --- |
| download_bdot10k | Trafność operacji | 1,00 (15/15) |
| download_bdot10k | Trafność operacji w zakresie | 1,00 (15/15) |
| download_bdot10k | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_bdot10k | Trafność wartości parametrów | 0,68 (17/25) |
| download_bdot10k | Poprawne wartości bez pytania | 0,68 (17/25) |
| download_bdot10k | Błędne wartości bez pytania | 0,00 (0/25) |
| download_bdot10k | Wartości, o które zapytano | 0,32 (8/25) |
| download_bdot10k | Pokrycie automatyczne poleceń kompletnych | 0,30 (3/10) |
| download_bdot10k | Błąd bez pytania W-02 — łącznie | 0,00 (0/30) |
| download_bdot10k | Błąd bez pytania W-02 — operacja | 0,00 (0/13) |
| download_bdot10k | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/3) |
| download_bdot10k | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/14) |
| download_bdot10k | Ciche zgadywanie | — (0/0) |
| download_bdot10k | Trafne dopytania (czułość) | 1,00 (5/5) |
| download_bdot10k | Pytania zbędne na polecenie | 0,53 (8/15) |
| download_bdot10k | Naruszenia W-03 | — (0/0) |
| download_dem_sheet | Trafność operacji | 1,00 (15/15) |
| download_dem_sheet | Trafność operacji w zakresie | 1,00 (15/15) |
| download_dem_sheet | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_dem_sheet | Trafność wartości parametrów | 0,85 (29/34) |
| download_dem_sheet | Poprawne wartości bez pytania | 0,85 (29/34) |
| download_dem_sheet | Błędne wartości bez pytania | 0,00 (0/34) |
| download_dem_sheet | Wartości, o które zapytano | 0,15 (5/34) |
| download_dem_sheet | Pokrycie automatyczne poleceń kompletnych | 0,43 (3/7) |
| download_dem_sheet | Błąd bez pytania W-02 — łącznie | 0,00 (0/37) |
| download_dem_sheet | Błąd bez pytania W-02 — operacja | 0,00 (0/8) |
| download_dem_sheet | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/14) |
| download_dem_sheet | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/15) |
| download_dem_sheet | Ciche zgadywanie | — (0/0) |
| download_dem_sheet | Trafne dopytania (czułość) | 1,00 (11/11) |
| download_dem_sheet | Pytania zbędne na polecenie | 0,33 (5/15) |
| download_dem_sheet | Naruszenia W-03 | — (0/0) |
| download_elevation_cutout | Trafność operacji | 0,95 (18/19) |
| download_elevation_cutout | Trafność operacji w zakresie | 0,95 (18/19) |
| download_elevation_cutout | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_elevation_cutout | Trafność wartości parametrów | 0,34 (20/58) |
| download_elevation_cutout | Poprawne wartości bez pytania | 0,34 (20/58) |
| download_elevation_cutout | Błędne wartości bez pytania | 0,00 (0/58) |
| download_elevation_cutout | Wartości, o które zapytano | 0,66 (38/58) |
| download_elevation_cutout | Pokrycie automatyczne poleceń kompletnych | 0,00 (0/10) |
| download_elevation_cutout | Błąd bez pytania W-02 — łącznie | 0,06 (2/32) |
| download_elevation_cutout | Błąd bez pytania W-02 — operacja | 0,00 (0/10) |
| download_elevation_cutout | Błąd bez pytania W-02 — parametry modelu | 0,33 (2/6) |
| download_elevation_cutout | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/16) |
| download_elevation_cutout | Ciche zgadywanie | 1,00 (2/2) |
| download_elevation_cutout | Trafne dopytania (czułość) | 0,89 (16/18) |
| download_elevation_cutout | Pytania zbędne na polecenie | 2,00 (38/19) |
| download_elevation_cutout | Naruszenia W-03 | — (0/0) |
| download_sheet_hierarchy | Trafność operacji | 0,60 (9/15) |
| download_sheet_hierarchy | Trafność operacji w zakresie | 0,60 (9/15) |
| download_sheet_hierarchy | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_sheet_hierarchy | Trafność wartości parametrów | 0,51 (24/47) |
| download_sheet_hierarchy | Poprawne wartości bez pytania | 0,51 (24/47) |
| download_sheet_hierarchy | Błędne wartości bez pytania | 0,17 (8/47) |
| download_sheet_hierarchy | Wartości, o które zapytano | 0,32 (15/47) |
| download_sheet_hierarchy | Pokrycie automatyczne poleceń kompletnych | 0,00 (0/9) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — łącznie | 0,00 (0/25) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — operacja | 0,00 (0/1) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/10) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/14) |
| download_sheet_hierarchy | Ciche zgadywanie | — (0/0) |
| download_sheet_hierarchy | Trafne dopytania (czułość) | 0,43 (3/7) |
| download_sheet_hierarchy | Pytania zbędne na polecenie | 1,00 (15/15) |
| download_sheet_hierarchy | Naruszenia W-03 | — (0/0) |
| out_of_scope | Trafność operacji | 0,87 (13/15) |
| out_of_scope | Trafność operacji w zakresie | — (0/0) |
| out_of_scope | Trafność rozpoznania spoza zakresu | 0,87 (13/15) |
| out_of_scope | Trafność wartości parametrów | — (0/0) |
| out_of_scope | Poprawne wartości bez pytania | — (0/0) |
| out_of_scope | Błędne wartości bez pytania | — (0/0) |
| out_of_scope | Wartości, o które zapytano | — (0/0) |
| out_of_scope | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| out_of_scope | Błąd bez pytania W-02 — łącznie | 0,00 (0/13) |
| out_of_scope | Błąd bez pytania W-02 — operacja | 0,00 (0/13) |
| out_of_scope | Błąd bez pytania W-02 — parametry modelu | — (0/0) |
| out_of_scope | Błąd bez pytania W-02 — ekstraktory | — (0/0) |
| out_of_scope | Ciche zgadywanie | — (0/0) |
| out_of_scope | Trafne dopytania (czułość) | — (0/0) |
| out_of_scope | Pytania zbędne na polecenie | 0,00 (0/15) |
| out_of_scope | Naruszenia W-03 | 0,00 (0/15) |

### Według tagu
| Tag | Miara | Wynik |
| --- | --- | --- |
| ambiguous | Trafność operacji | 1,00 (5/5) |
| ambiguous | Trafność operacji w zakresie | 1,00 (5/5) |
| ambiguous | Trafność rozpoznania spoza zakresu | — (0/0) |
| ambiguous | Trafność wartości parametrów | 0,14 (1/7) |
| ambiguous | Poprawne wartości bez pytania | 0,14 (1/7) |
| ambiguous | Błędne wartości bez pytania | 0,00 (0/7) |
| ambiguous | Wartości, o które zapytano | 0,86 (6/7) |
| ambiguous | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| ambiguous | Błąd bez pytania W-02 — łącznie | 0,33 (2/6) |
| ambiguous | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| ambiguous | Błąd bez pytania W-02 — parametry modelu | 1,00 (2/2) |
| ambiguous | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/1) |
| ambiguous | Ciche zgadywanie | 1,00 (2/2) |
| ambiguous | Trafne dopytania (czułość) | 0,82 (9/11) |
| ambiguous | Pytania zbędne na polecenie | 1,20 (6/5) |
| ambiguous | Naruszenia W-03 | — (0/0) |
| colloquial | Trafność operacji | 0,91 (20/22) |
| colloquial | Trafność operacji w zakresie | 0,91 (20/22) |
| colloquial | Trafność rozpoznania spoza zakresu | — (0/0) |
| colloquial | Trafność wartości parametrów | 0,60 (34/57) |
| colloquial | Poprawne wartości bez pytania | 0,60 (34/57) |
| colloquial | Błędne wartości bez pytania | 0,04 (2/57) |
| colloquial | Wartości, o które zapytano | 0,37 (21/57) |
| colloquial | Pokrycie automatyczne poleceń kompletnych | 0,15 (2/13) |
| colloquial | Błąd bez pytania W-02 — łącznie | 0,00 (0/43) |
| colloquial | Błąd bez pytania W-02 — operacja | 0,00 (0/9) |
| colloquial | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/13) |
| colloquial | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/21) |
| colloquial | Ciche zgadywanie | — (0/0) |
| colloquial | Trafne dopytania (czułość) | 1,00 (14/14) |
| colloquial | Pytania zbędne na polecenie | 0,95 (21/22) |
| colloquial | Naruszenia W-03 | — (0/0) |
| complete | Trafność operacji | 0,92 (33/36) |
| complete | Trafność operacji w zakresie | 0,92 (33/36) |
| complete | Trafność rozpoznania spoza zakresu | — (0/0) |
| complete | Trafność wartości parametrów | 0,53 (60/114) |
| complete | Poprawne wartości bez pytania | 0,53 (60/114) |
| complete | Błędne wartości bez pytania | 0,05 (6/114) |
| complete | Wartości, o które zapytano | 0,42 (48/114) |
| complete | Pokrycie automatyczne poleceń kompletnych | 0,17 (6/36) |
| complete | Błąd bez pytania W-02 — łącznie | 0,00 (0/77) |
| complete | Błąd bez pytania W-02 — operacja | 0,00 (0/17) |
| complete | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/24) |
| complete | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/36) |
| complete | Ciche zgadywanie | — (0/0) |
| complete | Trafne dopytania (czułość) | — (0/0) |
| complete | Pytania zbędne na polecenie | 1,33 (48/36) |
| complete | Naruszenia W-03 | — (0/0) |
| formal | Trafność operacji | 0,91 (30/33) |
| formal | Trafność operacji w zakresie | 0,91 (30/33) |
| formal | Trafność rozpoznania spoza zakresu | — (0/0) |
| formal | Trafność wartości parametrów | 0,53 (47/88) |
| formal | Poprawne wartości bez pytania | 0,53 (47/88) |
| formal | Błędne wartości bez pytania | 0,07 (6/88) |
| formal | Wartości, o które zapytano | 0,40 (35/88) |
| formal | Pokrycie automatyczne poleceń kompletnych | 0,24 (4/17) |
| formal | Błąd bez pytania W-02 — łącznie | 0,01 (1/69) |
| formal | Błąd bez pytania W-02 — operacja | 0,00 (0/21) |
| formal | Błąd bez pytania W-02 — parametry modelu | 0,06 (1/17) |
| formal | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/31) |
| formal | Ciche zgadywanie | 1,00 (1/1) |
| formal | Trafne dopytania (czułość) | 0,77 (17/22) |
| formal | Pytania zbędne na polecenie | 1,06 (35/33) |
| formal | Naruszenia W-03 | — (0/0) |
| incomplete | Trafność operacji | 0,83 (19/23) |
| incomplete | Trafność operacji w zakresie | 0,83 (19/23) |
| incomplete | Trafność rozpoznania spoza zakresu | — (0/0) |
| incomplete | Trafność wartości parametrów | 0,67 (29/43) |
| incomplete | Poprawne wartości bez pytania | 0,67 (29/43) |
| incomplete | Błędne wartości bez pytania | 0,05 (2/43) |
| incomplete | Wartości, o które zapytano | 0,28 (12/43) |
| incomplete | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| incomplete | Błąd bez pytania W-02 — łącznie | 0,00 (0/41) |
| incomplete | Błąd bez pytania W-02 — operacja | 0,00 (0/12) |
| incomplete | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/7) |
| incomplete | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/22) |
| incomplete | Ciche zgadywanie | — (0/0) |
| incomplete | Trafne dopytania (czułość) | 0,87 (26/30) |
| incomplete | Pytania zbędne na polecenie | 0,52 (12/23) |
| incomplete | Naruszenia W-03 | — (0/0) |
| near_miss | Trafność operacji | 0,60 (3/5) |
| near_miss | Trafność operacji w zakresie | — (0/0) |
| near_miss | Trafność rozpoznania spoza zakresu | 0,60 (3/5) |
| near_miss | Trafność wartości parametrów | — (0/0) |
| near_miss | Poprawne wartości bez pytania | — (0/0) |
| near_miss | Błędne wartości bez pytania | — (0/0) |
| near_miss | Wartości, o które zapytano | — (0/0) |
| near_miss | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| near_miss | Błąd bez pytania W-02 — łącznie | 0,00 (0/3) |
| near_miss | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| near_miss | Błąd bez pytania W-02 — parametry modelu | — (0/0) |
| near_miss | Błąd bez pytania W-02 — ekstraktory | — (0/0) |
| near_miss | Ciche zgadywanie | — (0/0) |
| near_miss | Trafne dopytania (czułość) | — (0/0) |
| near_miss | Pytania zbędne na polecenie | 0,00 (0/5) |
| near_miss | Naruszenia W-03 | 0,00 (0/5) |
| out_of_scope | Trafność operacji | 1,00 (10/10) |
| out_of_scope | Trafność operacji w zakresie | — (0/0) |
| out_of_scope | Trafność rozpoznania spoza zakresu | 1,00 (10/10) |
| out_of_scope | Trafność wartości parametrów | — (0/0) |
| out_of_scope | Poprawne wartości bez pytania | — (0/0) |
| out_of_scope | Błędne wartości bez pytania | — (0/0) |
| out_of_scope | Wartości, o które zapytano | — (0/0) |
| out_of_scope | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| out_of_scope | Błąd bez pytania W-02 — łącznie | 0,00 (0/10) |
| out_of_scope | Błąd bez pytania W-02 — operacja | 0,00 (0/10) |
| out_of_scope | Błąd bez pytania W-02 — parametry modelu | — (0/0) |
| out_of_scope | Błąd bez pytania W-02 — ekstraktory | — (0/0) |
| out_of_scope | Ciche zgadywanie | — (0/0) |
| out_of_scope | Trafne dopytania (czułość) | — (0/0) |
| out_of_scope | Pytania zbędne na polecenie | 0,00 (0/10) |
| out_of_scope | Naruszenia W-03 | 0,00 (0/10) |
| typo | Trafność operacji | 0,80 (8/10) |
| typo | Trafność operacji w zakresie | 0,80 (8/10) |
| typo | Trafność rozpoznania spoza zakresu | — (0/0) |
| typo | Trafność wartości parametrów | 0,48 (10/21) |
| typo | Poprawne wartości bez pytania | 0,48 (10/21) |
| typo | Błędne wartości bez pytania | 0,00 (0/21) |
| typo | Wartości, o które zapytano | 0,52 (11/21) |
| typo | Pokrycie automatyczne poleceń kompletnych | 0,00 (0/6) |
| typo | Błąd bez pytania W-02 — łącznie | 0,07 (1/14) |
| typo | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| typo | Błąd bez pytania W-02 — parametry modelu | 0,33 (1/3) |
| typo | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/8) |
| typo | Ciche zgadywanie | 1,00 (1/1) |
| typo | Trafne dopytania (czułość) | 0,86 (6/7) |
| typo | Pytania zbędne na polecenie | 1,10 (11/10) |
| typo | Naruszenia W-03 | — (0/0) |

## Krzywe progów

### Decyzje o operacji
| Próg | Błędy wśród decyzji ponad progiem | Pokrycie decyzji |
| --- | --- | --- |
| 0,356339987027 | 0,11 (9/79) | 1,00 (79/79) |
| 0,372907951773 | 0,10 (8/78) | 0,99 (78/79) |
| 0,38489760663 | 0,09 (7/77) | 0,97 (77/79) |
| 0,398420235255 | 0,08 (6/76) | 0,96 (76/79) |
| 0,413486112872 | 0,07 (5/75) | 0,95 (75/79) |
| 0,423916129078 | 0,07 (5/74) | 0,94 (74/79) |
| 0,436815297432 | 0,05 (4/73) | 0,92 (73/79) |
| 0,479861919181 | 0,06 (4/72) | 0,91 (72/79) |
| 0,488511069987 | 0,04 (3/71) | 0,90 (71/79) |
| 0,498936485202 | 0,03 (2/70) | 0,89 (70/79) |
| 0,568423054881 | 0,01 (1/69) | 0,87 (69/79) |
| 0,597693463846 | 0,01 (1/68) | 0,86 (68/79) |
| 0,601535637251 | 0,01 (1/67) | 0,85 (67/79) |
| 0,638689250459 | 0,02 (1/66) | 0,84 (66/79) |
| 0,660494066046 | 0,02 (1/65) | 0,82 (65/79) |
| 0,697909976541 | 0,00 (0/64) | 0,81 (64/79) |
| 0,714208468325 | 0,00 (0/63) | 0,80 (63/79) |
| 0,725980191855 | 0,00 (0/62) | 0,78 (62/79) |
| 0,730314571974 | 0,00 (0/61) | 0,77 (61/79) |
| 0,749750664369 | 0,00 (0/60) | 0,76 (60/79) |
| 0,759047804703 | 0,00 (0/59) | 0,75 (59/79) |
| 0,767642139488 | 0,00 (0/58) | 0,73 (58/79) |
| 0,782306503292 | 0,00 (0/57) | 0,72 (57/79) |
| 0,794723491557 | 0,00 (0/56) | 0,71 (56/79) |
| 0,805611141034 | 0,00 (0/55) | 0,70 (55/79) |
| 0,815265667578 | 0,00 (0/54) | 0,68 (54/79) |
| 0,82211791376 | 0,00 (0/53) | 0,67 (53/79) |
| 0,842205802596 | 0,00 (0/52) | 0,66 (52/79) |
| 0,846026937357 | 0,00 (0/51) | 0,65 (51/79) |
| 0,846646198572 | 0,00 (0/50) | 0,63 (50/79) |
| 0,852196407923 | 0,00 (0/49) | 0,62 (49/79) |
| 0,865511094743 | 0,00 (0/48) | 0,61 (48/79) |
| 0,867817830158 | 0,00 (0/47) | 0,59 (47/79) |
| 0,872046450951 | 0,00 (0/46) | 0,58 (46/79) |
| 0,873133811898 | 0,00 (0/45) | 0,57 (45/79) |
| 0,874153041792 | 0,00 (0/44) | 0,56 (44/79) |
| 0,878190996101 | 0,00 (0/43) | 0,54 (43/79) |
| 0,890274213794 | 0,00 (0/42) | 0,53 (42/79) |
| 0,890664265232 | 0,00 (0/41) | 0,52 (41/79) |
| 0,896165835826 | 0,00 (0/40) | 0,51 (40/79) |
| 0,897914154551 | 0,00 (0/39) | 0,49 (39/79) |
| 0,89940316348 | 0,00 (0/38) | 0,48 (38/79) |
| 0,899656655086 | 0,00 (0/37) | 0,47 (37/79) |
| 0,9005375503 | 0,00 (0/36) | 0,46 (36/79) |
| 0,902214378391 | 0,00 (0/35) | 0,44 (35/79) |
| 0,902638868831 | 0,00 (0/34) | 0,43 (34/79) |
| 0,903832834933 | 0,00 (0/33) | 0,42 (33/79) |
| 0,904531420739 | 0,00 (0/32) | 0,41 (32/79) |
| 0,906252078946 | 0,00 (0/31) | 0,39 (31/79) |
| 0,910819011625 | 0,00 (0/30) | 0,38 (30/79) |
| 0,913504575991 | 0,00 (0/29) | 0,37 (29/79) |
| 0,91804491099 | 0,00 (0/28) | 0,35 (28/79) |
| 0,91876957133 | 0,00 (0/27) | 0,34 (27/79) |
| 0,919943955626 | 0,00 (0/26) | 0,33 (26/79) |
| 0,920202031318 | 0,00 (0/25) | 0,32 (25/79) |
| 0,924029890579 | 0,00 (0/24) | 0,30 (24/79) |
| 0,924355131602 | 0,00 (0/23) | 0,29 (23/79) |
| 0,924449810566 | 0,00 (0/22) | 0,28 (22/79) |
| 0,926983752211 | 0,00 (0/21) | 0,27 (21/79) |
| 0,928828529904 | 0,00 (0/20) | 0,25 (20/79) |
| 0,92956384156 | 0,00 (0/19) | 0,24 (19/79) |
| 0,930021939009 | 0,00 (0/18) | 0,23 (18/79) |
| 0,935240795539 | 0,00 (0/17) | 0,22 (17/79) |
| 0,936700942988 | 0,00 (0/16) | 0,20 (16/79) |
| 0,937515389772 | 0,00 (0/15) | 0,19 (15/79) |
| 0,940664362422 | 0,00 (0/14) | 0,18 (14/79) |
| 0,941295756086 | 0,00 (0/13) | 0,16 (13/79) |
| 0,944603603639 | 0,00 (0/12) | 0,15 (12/79) |
| 0,945927023839 | 0,00 (0/11) | 0,14 (11/79) |
| 0,952446555512 | 0,00 (0/10) | 0,13 (10/79) |
| 0,956038811078 | 0,00 (0/9) | 0,11 (9/79) |
| 0,962243173386 | 0,00 (0/8) | 0,10 (8/79) |
| 0,968462381204 | 0,00 (0/7) | 0,09 (7/79) |
| 0,969302431368 | 0,00 (0/6) | 0,08 (6/79) |
| 0,971436493937 | 0,00 (0/5) | 0,06 (5/79) |
| 0,972839009729 | 0,00 (0/4) | 0,05 (4/79) |
| 0,974824338214 | 0,00 (0/3) | 0,04 (3/79) |
| 0,97528266712 | 0,00 (0/2) | 0,03 (2/79) |
| 0,977860834554 | 0,00 (0/1) | 0,01 (1/79) |

### Decyzje o parametrach modelu
| Próg | Błędy wśród decyzji ponad progiem | Pokrycie decyzji |
| --- | --- | --- |
| 0,286429977218 | 0,24 (31/130) | 1,00 (130/130) |
| 0,325922025795 | 0,24 (31/129) | 0,99 (129/130) |
| 0,384148807476 | 0,24 (31/128) | 0,98 (128/130) |
| 0,389218559429 | 0,24 (30/127) | 0,98 (127/130) |
| 0,433908056456 | 0,23 (29/126) | 0,97 (126/130) |
| 0,461041593585 | 0,23 (29/125) | 0,96 (125/130) |
| 0,469987198716 | 0,23 (28/124) | 0,95 (124/130) |
| 0,47011280358 | 0,23 (28/123) | 0,95 (123/130) |
| 0,475011720578 | 0,23 (28/122) | 0,94 (122/130) |
| 0,476511771891 | 0,23 (28/121) | 0,93 (121/130) |
| 0,492022458072 | 0,23 (27/120) | 0,92 (120/130) |
| 0,49447353579 | 0,22 (26/119) | 0,92 (119/130) |
| 0,500147797073 | 0,21 (25/118) | 0,91 (118/130) |
| 0,502913839985 | 0,21 (24/117) | 0,90 (117/130) |
| 0,505303478704 | 0,21 (24/116) | 0,89 (116/130) |
| 0,51152552441 | 0,20 (23/115) | 0,88 (115/130) |
| 0,514920783456 | 0,20 (23/114) | 0,88 (114/130) |
| 0,517522276763 | 0,20 (23/113) | 0,87 (113/130) |
| 0,523254991006 | 0,21 (23/112) | 0,86 (112/130) |
| 0,526805510278 | 0,20 (22/111) | 0,85 (111/130) |
| 0,532250045087 | 0,20 (22/110) | 0,85 (110/130) |
| 0,546260317967 | 0,19 (21/109) | 0,84 (109/130) |
| 0,549248600843 | 0,19 (20/108) | 0,83 (108/130) |
| 0,556081460582 | 0,18 (19/107) | 0,82 (107/130) |
| 0,558865885027 | 0,18 (19/106) | 0,82 (106/130) |
| 0,561355386689 | 0,18 (19/105) | 0,81 (105/130) |
| 0,574534781217 | 0,18 (19/104) | 0,80 (104/130) |
| 0,589418671411 | 0,17 (18/103) | 0,79 (103/130) |
| 0,599061308809 | 0,18 (18/102) | 0,78 (102/130) |
| 0,605406218082 | 0,18 (18/101) | 0,78 (101/130) |
| 0,607935225647 | 0,18 (18/100) | 0,77 (100/130) |
| 0,616631213108 | 0,18 (18/99) | 0,76 (99/130) |
| 0,637462018826 | 0,17 (17/98) | 0,75 (98/130) |
| 0,638790361249 | 0,18 (17/97) | 0,75 (97/130) |
| 0,642237160117 | 0,17 (16/96) | 0,74 (96/130) |
| 0,644652551426 | 0,17 (16/95) | 0,73 (95/130) |
| 0,653997039179 | 0,17 (16/94) | 0,72 (94/130) |
| 0,655388519448 | 0,16 (15/93) | 0,72 (93/130) |
| 0,656465741166 | 0,16 (15/92) | 0,71 (92/130) |
| 0,66276243697 | 0,15 (14/91) | 0,70 (91/130) |
| 0,665529083943 | 0,14 (13/90) | 0,69 (90/130) |
| 0,671455587871 | 0,15 (13/89) | 0,68 (89/130) |
| 0,672147318518 | 0,15 (13/88) | 0,68 (88/130) |
| 0,672185649765 | 0,15 (13/87) | 0,67 (87/130) |
| 0,675754965849 | 0,14 (12/86) | 0,66 (86/130) |
| 0,676213435612 | 0,14 (12/85) | 0,65 (85/130) |
| 0,676595665857 | 0,14 (12/84) | 0,65 (84/130) |
| 0,68974431274 | 0,14 (12/83) | 0,64 (83/130) |
| 0,690109012939 | 0,15 (12/82) | 0,63 (82/130) |
| 0,693531040066 | 0,15 (12/81) | 0,62 (81/130) |
| 0,695496868513 | 0,15 (12/80) | 0,62 (80/130) |
| 0,702370217269 | 0,14 (11/79) | 0,61 (79/130) |
| 0,712353337512 | 0,14 (11/78) | 0,60 (78/130) |
| 0,717900666035 | 0,14 (11/77) | 0,59 (77/130) |
| 0,733344006661 | 0,13 (10/76) | 0,58 (76/130) |
| 0,739203748719 | 0,13 (10/75) | 0,58 (75/130) |
| 0,740568565138 | 0,14 (10/74) | 0,57 (74/130) |
| 0,740798223624 | 0,14 (10/73) | 0,56 (73/130) |
| 0,759531851707 | 0,14 (10/72) | 0,55 (72/130) |
| 0,770399613802 | 0,14 (10/71) | 0,55 (71/130) |
| 0,772584161292 | 0,14 (10/70) | 0,54 (70/130) |
| 0,774965138996 | 0,14 (10/69) | 0,53 (69/130) |
| 0,776965749335 | 0,13 (9/68) | 0,52 (68/130) |
| 0,781358409105 | 0,12 (8/67) | 0,52 (67/130) |
| 0,784041676573 | 0,12 (8/66) | 0,51 (66/130) |
| 0,785454463773 | 0,12 (8/65) | 0,50 (65/130) |
| 0,785940822651 | 0,11 (7/64) | 0,49 (64/130) |
| 0,790246625653 | 0,11 (7/63) | 0,48 (63/130) |
| 0,793122337238 | 0,11 (7/62) | 0,48 (62/130) |
| 0,795189844625 | 0,10 (6/61) | 0,47 (61/130) |
| 0,795303455923 | 0,10 (6/60) | 0,46 (60/130) |
| 0,799433159337 | 0,10 (6/59) | 0,45 (59/130) |
| 0,801961657497 | 0,10 (6/58) | 0,45 (58/130) |
| 0,805401838478 | 0,11 (6/57) | 0,44 (57/130) |
| 0,82364342539 | 0,11 (6/56) | 0,43 (56/130) |
| 0,849233994027 | 0,11 (6/55) | 0,42 (55/130) |
| 0,855715257581 | 0,11 (6/54) | 0,42 (54/130) |
| 0,856850845517 | 0,11 (6/53) | 0,41 (53/130) |
| 0,864685927052 | 0,12 (6/52) | 0,40 (52/130) |
| 0,865158202615 | 0,12 (6/51) | 0,39 (51/130) |
| 0,866490610754 | 0,12 (6/50) | 0,38 (50/130) |
| 0,869933060758 | 0,12 (6/49) | 0,38 (49/130) |
| 0,874620645045 | 0,12 (6/48) | 0,37 (48/130) |
| 0,875791545512 | 0,13 (6/47) | 0,36 (47/130) |
| 0,876592261101 | 0,11 (5/46) | 0,35 (46/130) |
| 0,880767665185 | 0,11 (5/45) | 0,35 (45/130) |
| 0,882411332539 | 0,09 (4/44) | 0,34 (44/130) |
| 0,884051843419 | 0,09 (4/43) | 0,33 (43/130) |
| 0,885045814974 | 0,10 (4/42) | 0,32 (42/130) |
| 0,88825839924 | 0,10 (4/41) | 0,32 (41/130) |
| 0,888610718124 | 0,10 (4/40) | 0,31 (40/130) |
| 0,888762932191 | 0,10 (4/39) | 0,30 (39/130) |
| 0,889822208087 | 0,08 (3/38) | 0,29 (38/130) |
| 0,894950498136 | 0,08 (3/37) | 0,28 (37/130) |
| 0,89764340673 | 0,06 (2/36) | 0,28 (36/130) |
| 0,898278131159 | 0,06 (2/35) | 0,27 (35/130) |
| 0,909820419004 | 0,06 (2/34) | 0,26 (34/130) |
| 0,911183095496 | 0,06 (2/33) | 0,25 (33/130) |
| 0,912719030551 | 0,06 (2/32) | 0,25 (32/130) |
| 0,915583549072 | 0,06 (2/31) | 0,24 (31/130) |
| 0,921869630088 | 0,07 (2/30) | 0,23 (30/130) |
| 0,925434532606 | 0,07 (2/29) | 0,22 (29/130) |
| 0,927992472324 | 0,04 (1/28) | 0,22 (28/130) |
| 0,929967304165 | 0,04 (1/27) | 0,21 (27/130) |
| 0,935257774606 | 0,04 (1/26) | 0,20 (26/130) |
| 0,939851136684 | 0,04 (1/25) | 0,19 (25/130) |
| 0,943175424714 | 0,04 (1/24) | 0,18 (24/130) |
| 0,943582195148 | 0,00 (0/23) | 0,18 (23/130) |
| 0,948159442184 | 0,00 (0/22) | 0,17 (22/130) |
| 0,953850191084 | 0,00 (0/21) | 0,16 (21/130) |
| 0,955149187855 | 0,00 (0/20) | 0,15 (20/130) |
| 0,955648997042 | 0,00 (0/19) | 0,15 (19/130) |
| 0,959163195658 | 0,00 (0/18) | 0,14 (18/130) |
| 0,960044571834 | 0,00 (0/17) | 0,13 (17/130) |
| 0,962129272752 | 0,00 (0/16) | 0,12 (16/130) |
| 0,963690873424 | 0,00 (0/15) | 0,12 (15/130) |
| 0,964219677151 | 0,00 (0/14) | 0,11 (14/130) |
| 0,964789680364 | 0,00 (0/13) | 0,10 (13/130) |
| 0,965937848977 | 0,00 (0/12) | 0,09 (12/130) |
| 0,966457544745 | 0,00 (0/11) | 0,08 (11/130) |
| 0,967733369374 | 0,00 (0/10) | 0,08 (10/130) |
| 0,968039553537 | 0,00 (0/9) | 0,07 (9/130) |
| 0,968908816573 | 0,00 (0/8) | 0,06 (8/130) |
| 0,973451551208 | 0,00 (0/7) | 0,05 (7/130) |
| 0,977012881556 | 0,00 (0/6) | 0,05 (6/130) |
| 0,97831401811 | 0,00 (0/5) | 0,04 (5/130) |
| 0,980096809285 | 0,00 (0/4) | 0,03 (4/130) |
| 0,984494339778 | 0,00 (0/3) | 0,02 (3/130) |
| 0,985303099942 | 0,00 (0/2) | 0,02 (2/130) |
| 0,986422204408 | 0,00 (0/1) | 0,01 (1/130) |

### Zalecane progi (docelowy błąd 0,01)
- Operacja: próg 0,697909976541; przyjęte 64/79; błędy 0,00 (0/64).
- Uwaga (Operacja): liczba decyzji ponad progiem wynosi 64 (wymagane co najmniej 100); zbiór jest za mały, by potwierdzić błąd 0,01.
- Parametry modelu: próg 0,943582195148; przyjęte 23/130; błędy 0,00 (0/23).
- Uwaga (Parametry modelu): liczba decyzji ponad progiem wynosi 23 (wymagane co najmniej 100); zbiór jest za mały, by potwierdzić błąd 0,01.

## Błędne przypadki
- `kartograf-hierarchy-004` (powtórzenie 0): Proszę pobrać ortofotomapę z arkuszy pod N-34-130-D-d-2 w skali 1:10000.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.3984202352547286, "method": "logprobs", "probabilities": {"download_bdot10k": 0.10723335157863265, "download_dem_sheet": 0.3984202352547286, "download_elevation_cutout": 0.18820039306954023, "download_sheet_hierarchy": 0.17679790767615683, "out_of_scope": 0.1293481124209418}}.
- `kartograf-hierarchy-008` (powtórzenie 0): wyciagnij dsm z potomnych 5.123.45 do 1:1000; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.6604940660461729, "method": "logprobs", "probabilities": {"download_bdot10k": 0.0478460296669496, "download_dem_sheet": 0.04222397298205368, "download_elevation_cutout": 0.6604940660461729, "download_sheet_hierarchy": 0.21443102821743884, "out_of_scope": 0.03500490308738501}}.
- `kartograf-hierarchy-010` (powtórzenie 0): Rozwiń N-34-130-D-d-2 do arkuszy potomnych z rzeźbą terenu.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.49893648520182543, "method": "logprobs", "probabilities": {"download_bdot10k": 0.021921739232608803, "download_dem_sheet": 0.49893648520182543, "download_elevation_cutout": 0.02814807035267053, "download_sheet_hierarchy": 0.4403099027770558, "out_of_scope": 0.010683802435839412}}.
- `kartograf-hierarchy-011` (powtórzenie 0): Daj arkusze NMPT spod 7.108.12.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.3563399870265238, "method": "logprobs", "probabilities": {"download_bdot10k": 0.09009685828885487, "download_dem_sheet": 0.24490865268784395, "download_elevation_cutout": 0.3563399870265238, "download_sheet_hierarchy": 0.277517860935911, "out_of_scope": 0.031136641060866384}}.
- `kartograf-hierarchy-013` (powtórzenie 0): Potrzebuję NMT 1 m z hierarchii pod 6.111.22 do skali 1:1000.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.3729079517733468, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04453750357055354, "download_dem_sheet": 0.3729079517733468, "download_elevation_cutout": 0.21247654612604033, "download_sheet_hierarchy": 0.35031460112289964, "out_of_scope": 0.01976339740715962}}.
- `kartograf-hierarchy-014` (powtórzenie 0): sciagnij dzieci dsm arkusza 7.108.12; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.47986191918083676, "method": "logprobs", "probabilities": {"download_bdot10k": 0.12915308344170093, "download_dem_sheet": 0.2063860396869326, "download_elevation_cutout": 0.47986191918083676, "download_sheet_hierarchy": 0.11759522067784882, "out_of_scope": 0.06700373701268096}}.
- `kartograf-cutout-008` (powtórzenie 0): Wycinek wysokościowy NMT 530000 382000 530100 382100 PL-1992.; pole `target_crs`; oczekiwano "question"; otrzymano {"value": "epsg_2180", "source": "command"}.
- `kartograf-cutout-008` (powtórzenie 0): Wycinek wysokościowy NMT 530000 382000 530100 382100 PL-1992.; pole `target_crs`; oczekiwano "unspecified"; otrzymano "epsg_2180".
- `kartograf-cutout-015` (powtórzenie 0): sciagnij wycinek dsm 530000 382000 530100 382100 w pl-1992; pole `target_crs`; oczekiwano "question"; otrzymano {"value": "epsg_2180", "source": "command"}.
- `kartograf-cutout-015` (powtórzenie 0): sciagnij wycinek dsm 530000 382000 530100 382100 w pl-1992; pole `target_crs`; oczekiwano "unspecified"; otrzymano "epsg_2180".
- `kartograf-cutout-018` (powtórzenie 0): Daj NMT z x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045, EVRF2007.; pole `operation`; oczekiwano "download_elevation_cutout"; otrzymano {"name": "operation", "key": "download_sheet_hierarchy", "confidence": 0.4885110699873212, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04009943050766859, "download_dem_sheet": 0.10239748301870942, "download_elevation_cutout": 0.3357484209729921, "download_sheet_hierarchy": 0.4885110699873212, "out_of_scope": 0.03324359551330874}}.
- `near-001` (powtórzenie 0): Pobierz chmurę punktów LAZ dla zlewni Warty.; pole `operation`; oczekiwano "out_of_scope"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.3848976066295344, "method": "logprobs", "probabilities": {"download_bdot10k": 0.18181275560186028, "download_dem_sheet": 0.1707972775985015, "download_elevation_cutout": 0.3848976066295344, "download_sheet_hierarchy": 0.043184314632556196, "out_of_scope": 0.21930804553754774}}.
- `near-004` (powtórzenie 0): Wyznacz hydrologiczne grupy glebowe HSG dla arkusza N-34-130-D-d-2-4.; pole `operation`; oczekiwano "out_of_scope"; otrzymano {"name": "operation", "key": "download_bdot10k", "confidence": 0.42391612907833065, "method": "logprobs", "probabilities": {"download_bdot10k": 0.42391612907833065, "download_dem_sheet": 0.0784165990001951, "download_elevation_cutout": 0.08885764785183271, "download_sheet_hierarchy": 0.05737080939738435, "out_of_scope": 0.35143881467225724}}.

## Naruszenia W-03
Brak.

## Czasy planowania i zapytania do modelu na plan
| Grupa (wszystkie, operacja lub tag) | Mediana (s) | P90 (s) | Maksimum (s) | Mediana zapytań | P90 zapytań | Maksimum zapytań |
| --- | --- | --- | --- | --- | --- | --- |
| Wszystkie | 11,09 | 14,86 | 15,14 | 3 | 4 | 4 |
| download_bdot10k | 7,99 | 8,01 | 8,02 | 2 | 2 | 2 |
| download_dem_sheet | 11,08 | 11,29 | 11,31 | 3 | 3 | 3 |
| download_elevation_cutout | 14,83 | 15,11 | 15,14 | 4 | 4 | 4 |
| download_sheet_hierarchy | 11,75 | 12,05 | 12,29 | 3 | 3 | 3 |
| out_of_scope | 4,73 | 4,96 | 4,96 | 1 | 1 | 1 |
| ambiguous | 14,63 | 15,04 | 15,04 | 4 | 4 | 4 |
| colloquial | 11,73 | 14,87 | 14,96 | 3 | 4 | 4 |
| complete | 11,68 | 14,87 | 15,14 | 3 | 4 | 4 |
| formal | 11,74 | 14,86 | 15,14 | 3 | 4 | 4 |
| incomplete | 11,13 | 14,72 | 15,11 | 3 | 4 | 4 |
| near_miss | 4,94 | 4,96 | 4,96 | 1 | 1 | 1 |
| out_of_scope | 4,73 | 4,94 | 4,96 | 1 | 1 | 1 |
| typo | 11,08 | 14,69 | 14,89 | 3 | 4 | 4 |
