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
| Trafność wartości parametrów | 0,78 (128/164) |
| Poprawne wartości bez pytania | 0,78 (128/164) |
| Błędne wartości bez pytania | 0,04 (6/164) |
| Wartości, o które zapytano | 0,18 (30/164) |
| Pokrycie automatyczne poleceń kompletnych | 0,31 (11/36) |
| Błąd bez pytania W-02 — łącznie | 0,01 (1/174) |
| Błąd bez pytania W-02 — operacja | 0,00 (0/45) |
| Błąd bez pytania W-02 — parametry modelu | 0,01 (1/70) |
| Błąd bez pytania W-02 — ekstraktory | 0,00 (0/59) |
| Ciche zgadywanie | 1,00 (1/1) |
| Trafne dopytania (czułość) | 0,93 (38/41) |
| Pytania zbędne na polecenie | 0,38 (30/79) |
| Naruszenia W-03 | 0,00 (0/15) |

### Według operacji
| Operacja | Miara | Wynik |
| --- | --- | --- |
| download_bdot10k | Trafność operacji | 1,00 (15/15) |
| download_bdot10k | Trafność operacji w zakresie | 1,00 (15/15) |
| download_bdot10k | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_bdot10k | Trafność wartości parametrów | 0,80 (20/25) |
| download_bdot10k | Poprawne wartości bez pytania | 0,80 (20/25) |
| download_bdot10k | Błędne wartości bez pytania | 0,00 (0/25) |
| download_bdot10k | Wartości, o które zapytano | 0,20 (5/25) |
| download_bdot10k | Pokrycie automatyczne poleceń kompletnych | 0,60 (6/10) |
| download_bdot10k | Błąd bez pytania W-02 — łącznie | 0,00 (0/33) |
| download_bdot10k | Błąd bez pytania W-02 — operacja | 0,00 (0/13) |
| download_bdot10k | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/6) |
| download_bdot10k | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/14) |
| download_bdot10k | Ciche zgadywanie | — (0/0) |
| download_bdot10k | Trafne dopytania (czułość) | 1,00 (5/5) |
| download_bdot10k | Pytania zbędne na polecenie | 0,33 (5/15) |
| download_bdot10k | Naruszenia W-03 | — (0/0) |
| download_dem_sheet | Trafność operacji | 1,00 (15/15) |
| download_dem_sheet | Trafność operacji w zakresie | 1,00 (15/15) |
| download_dem_sheet | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_dem_sheet | Trafność wartości parametrów | 0,97 (33/34) |
| download_dem_sheet | Poprawne wartości bez pytania | 0,97 (33/34) |
| download_dem_sheet | Błędne wartości bez pytania | 0,00 (0/34) |
| download_dem_sheet | Wartości, o które zapytano | 0,03 (1/34) |
| download_dem_sheet | Pokrycie automatyczne poleceń kompletnych | 0,57 (4/7) |
| download_dem_sheet | Błąd bez pytania W-02 — łącznie | 0,00 (0/41) |
| download_dem_sheet | Błąd bez pytania W-02 — operacja | 0,00 (0/8) |
| download_dem_sheet | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/18) |
| download_dem_sheet | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/15) |
| download_dem_sheet | Ciche zgadywanie | — (0/0) |
| download_dem_sheet | Trafne dopytania (czułość) | 1,00 (11/11) |
| download_dem_sheet | Pytania zbędne na polecenie | 0,07 (1/15) |
| download_dem_sheet | Naruszenia W-03 | — (0/0) |
| download_elevation_cutout | Trafność operacji | 0,95 (18/19) |
| download_elevation_cutout | Trafność operacji w zakresie | 0,95 (18/19) |
| download_elevation_cutout | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_elevation_cutout | Trafność wartości parametrów | 0,78 (45/58) |
| download_elevation_cutout | Poprawne wartości bez pytania | 0,78 (45/58) |
| download_elevation_cutout | Błędne wartości bez pytania | 0,00 (0/58) |
| download_elevation_cutout | Wartości, o które zapytano | 0,22 (13/58) |
| download_elevation_cutout | Pokrycie automatyczne poleceń kompletnych | 0,10 (1/10) |
| download_elevation_cutout | Błąd bez pytania W-02 — łącznie | 0,02 (1/56) |
| download_elevation_cutout | Błąd bez pytania W-02 — operacja | 0,00 (0/10) |
| download_elevation_cutout | Błąd bez pytania W-02 — parametry modelu | 0,03 (1/30) |
| download_elevation_cutout | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/16) |
| download_elevation_cutout | Ciche zgadywanie | 1,00 (1/1) |
| download_elevation_cutout | Trafne dopytania (czułość) | 0,94 (17/18) |
| download_elevation_cutout | Pytania zbędne na polecenie | 0,68 (13/19) |
| download_elevation_cutout | Naruszenia W-03 | — (0/0) |
| download_sheet_hierarchy | Trafność operacji | 0,60 (9/15) |
| download_sheet_hierarchy | Trafność operacji w zakresie | 0,60 (9/15) |
| download_sheet_hierarchy | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_sheet_hierarchy | Trafność wartości parametrów | 0,64 (30/47) |
| download_sheet_hierarchy | Poprawne wartości bez pytania | 0,64 (30/47) |
| download_sheet_hierarchy | Błędne wartości bez pytania | 0,13 (6/47) |
| download_sheet_hierarchy | Wartości, o które zapytano | 0,23 (11/47) |
| download_sheet_hierarchy | Pokrycie automatyczne poleceń kompletnych | 0,00 (0/9) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — łącznie | 0,00 (0/31) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — operacja | 0,00 (0/1) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/16) |
| download_sheet_hierarchy | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/14) |
| download_sheet_hierarchy | Ciche zgadywanie | — (0/0) |
| download_sheet_hierarchy | Trafne dopytania (czułość) | 0,71 (5/7) |
| download_sheet_hierarchy | Pytania zbędne na polecenie | 0,73 (11/15) |
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
| ambiguous | Trafność wartości parametrów | 0,71 (5/7) |
| ambiguous | Poprawne wartości bez pytania | 0,71 (5/7) |
| ambiguous | Błędne wartości bez pytania | 0,00 (0/7) |
| ambiguous | Wartości, o które zapytano | 0,29 (2/7) |
| ambiguous | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| ambiguous | Błąd bez pytania W-02 — łącznie | 0,11 (1/9) |
| ambiguous | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| ambiguous | Błąd bez pytania W-02 — parametry modelu | 0,20 (1/5) |
| ambiguous | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/1) |
| ambiguous | Ciche zgadywanie | 1,00 (1/1) |
| ambiguous | Trafne dopytania (czułość) | 0,91 (10/11) |
| ambiguous | Pytania zbędne na polecenie | 0,40 (2/5) |
| ambiguous | Naruszenia W-03 | — (0/0) |
| colloquial | Trafność operacji | 0,91 (20/22) |
| colloquial | Trafność operacji w zakresie | 0,91 (20/22) |
| colloquial | Trafność rozpoznania spoza zakresu | — (0/0) |
| colloquial | Trafność wartości parametrów | 0,81 (46/57) |
| colloquial | Poprawne wartości bez pytania | 0,81 (46/57) |
| colloquial | Błędne wartości bez pytania | 0,04 (2/57) |
| colloquial | Wartości, o które zapytano | 0,16 (9/57) |
| colloquial | Pokrycie automatyczne poleceń kompletnych | 0,31 (4/13) |
| colloquial | Błąd bez pytania W-02 — łącznie | 0,00 (0/55) |
| colloquial | Błąd bez pytania W-02 — operacja | 0,00 (0/9) |
| colloquial | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/25) |
| colloquial | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/21) |
| colloquial | Ciche zgadywanie | — (0/0) |
| colloquial | Trafne dopytania (czułość) | 1,00 (14/14) |
| colloquial | Pytania zbędne na polecenie | 0,41 (9/22) |
| colloquial | Naruszenia W-03 | — (0/0) |
| complete | Trafność operacji | 0,92 (33/36) |
| complete | Trafność operacji w zakresie | 0,92 (33/36) |
| complete | Trafność rozpoznania spoza zakresu | — (0/0) |
| complete | Trafność wartości parametrów | 0,76 (87/114) |
| complete | Poprawne wartości bez pytania | 0,76 (87/114) |
| complete | Błędne wartości bez pytania | 0,04 (4/114) |
| complete | Wartości, o które zapytano | 0,20 (23/114) |
| complete | Pokrycie automatyczne poleceń kompletnych | 0,31 (11/36) |
| complete | Błąd bez pytania W-02 — łącznie | 0,00 (0/104) |
| complete | Błąd bez pytania W-02 — operacja | 0,00 (0/17) |
| complete | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/51) |
| complete | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/36) |
| complete | Ciche zgadywanie | — (0/0) |
| complete | Trafne dopytania (czułość) | — (0/0) |
| complete | Pytania zbędne na polecenie | 0,64 (23/36) |
| complete | Naruszenia W-03 | — (0/0) |
| formal | Trafność operacji | 0,91 (30/33) |
| formal | Trafność operacji w zakresie | 0,91 (30/33) |
| formal | Trafność rozpoznania spoza zakresu | — (0/0) |
| formal | Trafność wartości parametrów | 0,80 (70/88) |
| formal | Poprawne wartości bez pytania | 0,80 (70/88) |
| formal | Błędne wartości bez pytania | 0,05 (4/88) |
| formal | Wartości, o które zapytano | 0,16 (14/88) |
| formal | Pokrycie automatyczne poleceń kompletnych | 0,41 (7/17) |
| formal | Błąd bez pytania W-02 — łącznie | 0,01 (1/92) |
| formal | Błąd bez pytania W-02 — operacja | 0,00 (0/21) |
| formal | Błąd bez pytania W-02 — parametry modelu | 0,03 (1/40) |
| formal | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/31) |
| formal | Ciche zgadywanie | 1,00 (1/1) |
| formal | Trafne dopytania (czułość) | 0,86 (19/22) |
| formal | Pytania zbędne na polecenie | 0,42 (14/33) |
| formal | Naruszenia W-03 | — (0/0) |
| incomplete | Trafność operacji | 0,83 (19/23) |
| incomplete | Trafność operacji w zakresie | 0,83 (19/23) |
| incomplete | Trafność rozpoznania spoza zakresu | — (0/0) |
| incomplete | Trafność wartości parametrów | 0,84 (36/43) |
| incomplete | Poprawne wartości bez pytania | 0,84 (36/43) |
| incomplete | Błędne wartości bez pytania | 0,05 (2/43) |
| incomplete | Wartości, o które zapytano | 0,12 (5/43) |
| incomplete | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| incomplete | Błąd bez pytania W-02 — łącznie | 0,00 (0/48) |
| incomplete | Błąd bez pytania W-02 — operacja | 0,00 (0/12) |
| incomplete | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/14) |
| incomplete | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/22) |
| incomplete | Ciche zgadywanie | — (0/0) |
| incomplete | Trafne dopytania (czułość) | 0,93 (28/30) |
| incomplete | Pytania zbędne na polecenie | 0,22 (5/23) |
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
| typo | Trafność wartości parametrów | 0,67 (14/21) |
| typo | Poprawne wartości bez pytania | 0,67 (14/21) |
| typo | Błędne wartości bez pytania | 0,00 (0/21) |
| typo | Wartości, o które zapytano | 0,33 (7/21) |
| typo | Pokrycie automatyczne poleceń kompletnych | 0,00 (0/6) |
| typo | Błąd bez pytania W-02 — łącznie | 0,00 (0/17) |
| typo | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| typo | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/6) |
| typo | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/8) |
| typo | Ciche zgadywanie | — (0/0) |
| typo | Trafne dopytania (czułość) | 1,00 (7/7) |
| typo | Pytania zbędne na polecenie | 0,70 (7/10) |
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
| 0,727543525995 | 0,00 (0/61) | 0,77 (61/79) |
| 0,730314571974 | 0,00 (0/60) | 0,76 (60/79) |
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
| 0,934920529305 | 0,00 (0/17) | 0,22 (17/79) |
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
| 0,290405579549 | 0,08 (11/134) | 1,00 (134/134) |
| 0,424398665262 | 0,08 (11/133) | 0,99 (133/134) |
| 0,450321693973 | 0,08 (11/132) | 0,99 (132/134) |
| 0,457119288699 | 0,08 (10/131) | 0,98 (131/134) |
| 0,460588717248 | 0,08 (10/130) | 0,97 (130/134) |
| 0,460981359806 | 0,08 (10/129) | 0,96 (129/134) |
| 0,486665081343 | 0,07 (9/128) | 0,96 (128/134) |
| 0,511133607431 | 0,06 (8/127) | 0,95 (127/134) |
| 0,535108842574 | 0,06 (8/126) | 0,94 (126/134) |
| 0,54023208356 | 0,06 (7/125) | 0,93 (125/134) |
| 0,560305244169 | 0,06 (7/124) | 0,93 (124/134) |
| 0,578792959389 | 0,06 (7/123) | 0,92 (123/134) |
| 0,585572942882 | 0,05 (6/122) | 0,91 (122/134) |
| 0,587072608372 | 0,05 (6/121) | 0,90 (121/134) |
| 0,596462153606 | 0,04 (5/120) | 0,90 (120/134) |
| 0,604455012808 | 0,04 (5/119) | 0,89 (119/134) |
| 0,611391919441 | 0,04 (5/118) | 0,88 (118/134) |
| 0,619296363008 | 0,04 (5/117) | 0,87 (117/134) |
| 0,638790361249 | 0,04 (5/116) | 0,87 (116/134) |
| 0,663058386114 | 0,04 (5/115) | 0,86 (115/134) |
| 0,670978637115 | 0,04 (5/114) | 0,85 (114/134) |
| 0,678758450173 | 0,04 (4/113) | 0,84 (113/134) |
| 0,680515837732 | 0,04 (4/112) | 0,84 (112/134) |
| 0,68451239286 | 0,04 (4/111) | 0,83 (111/134) |
| 0,688805708574 | 0,04 (4/110) | 0,82 (110/134) |
| 0,689642160927 | 0,04 (4/109) | 0,81 (109/134) |
| 0,691426165623 | 0,04 (4/108) | 0,81 (108/134) |
| 0,694290544239 | 0,04 (4/107) | 0,80 (107/134) |
| 0,720132273239 | 0,04 (4/106) | 0,79 (106/134) |
| 0,740281421906 | 0,04 (4/105) | 0,78 (105/134) |
| 0,750611584184 | 0,04 (4/104) | 0,78 (104/134) |
| 0,751922205239 | 0,04 (4/103) | 0,77 (103/134) |
| 0,76190885632 | 0,04 (4/102) | 0,76 (102/134) |
| 0,768295325418 | 0,03 (3/101) | 0,75 (101/134) |
| 0,780731529589 | 0,03 (3/100) | 0,75 (100/134) |
| 0,781678047936 | 0,03 (3/99) | 0,74 (99/134) |
| 0,792743561254 | 0,03 (3/98) | 0,73 (98/134) |
| 0,796381697766 | 0,03 (3/97) | 0,72 (97/134) |
| 0,801582533129 | 0,03 (3/96) | 0,72 (96/134) |
| 0,802204592261 | 0,03 (3/95) | 0,71 (95/134) |
| 0,802999678483 | 0,03 (3/94) | 0,70 (94/134) |
| 0,814754544476 | 0,03 (3/93) | 0,69 (93/134) |
| 0,823307511585 | 0,03 (3/92) | 0,69 (92/134) |
| 0,830366322795 | 0,03 (3/91) | 0,68 (91/134) |
| 0,832280521437 | 0,02 (2/90) | 0,67 (90/134) |
| 0,833937811826 | 0,02 (2/89) | 0,66 (89/134) |
| 0,837323256 | 0,02 (2/88) | 0,66 (88/134) |
| 0,842477148481 | 0,02 (2/87) | 0,65 (87/134) |
| 0,845658135027 | 0,02 (2/86) | 0,64 (86/134) |
| 0,850460433758 | 0,02 (2/85) | 0,63 (85/134) |
| 0,851727129472 | 0,02 (2/84) | 0,63 (84/134) |
| 0,860066056919 | 0,02 (2/83) | 0,62 (83/134) |
| 0,861773614649 | 0,02 (2/82) | 0,61 (82/134) |
| 0,875091451541 | 0,02 (2/81) | 0,60 (81/134) |
| 0,88160497247 | 0,03 (2/80) | 0,60 (80/134) |
| 0,882654650064 | 0,03 (2/79) | 0,59 (79/134) |
| 0,885455959428 | 0,03 (2/78) | 0,58 (78/134) |
| 0,886241677036 | 0,03 (2/77) | 0,57 (77/134) |
| 0,896557282636 | 0,03 (2/76) | 0,57 (76/134) |
| 0,897978017762 | 0,01 (1/75) | 0,56 (75/134) |
| 0,902418456501 | 0,01 (1/74) | 0,55 (74/134) |
| 0,906916666698 | 0,01 (1/73) | 0,54 (73/134) |
| 0,909041571928 | 0,01 (1/72) | 0,54 (72/134) |
| 0,913053807598 | 0,01 (1/71) | 0,53 (71/134) |
| 0,914307447015 | 0,01 (1/70) | 0,52 (70/134) |
| 0,918047231634 | 0,01 (1/69) | 0,51 (69/134) |
| 0,921037631959 | 0,01 (1/68) | 0,51 (68/134) |
| 0,922326845498 | 0,01 (1/67) | 0,50 (67/134) |
| 0,923740924977 | 0,02 (1/66) | 0,49 (66/134) |
| 0,924715435905 | 0,02 (1/65) | 0,49 (65/134) |
| 0,929179635561 | 0,02 (1/64) | 0,48 (64/134) |
| 0,92930584069 | 0,02 (1/63) | 0,47 (63/134) |
| 0,933982311374 | 0,02 (1/62) | 0,46 (62/134) |
| 0,93450129578 | 0,02 (1/61) | 0,46 (61/134) |
| 0,934891583095 | 0,02 (1/60) | 0,45 (60/134) |
| 0,936576925741 | 0,02 (1/59) | 0,44 (59/134) |
| 0,937513614261 | 0,02 (1/58) | 0,43 (58/134) |
| 0,941630301662 | 0,02 (1/57) | 0,43 (57/134) |
| 0,941840580803 | 0,02 (1/56) | 0,42 (56/134) |
| 0,94207879497 | 0,02 (1/55) | 0,41 (55/134) |
| 0,94324439072 | 0,02 (1/54) | 0,40 (54/134) |
| 0,944697996169 | 0,02 (1/53) | 0,40 (53/134) |
| 0,945927450856 | 0,02 (1/52) | 0,39 (52/134) |
| 0,948817798501 | 0,02 (1/51) | 0,38 (51/134) |
| 0,950673757522 | 0,02 (1/50) | 0,37 (50/134) |
| 0,953097914119 | 0,02 (1/49) | 0,37 (49/134) |
| 0,953672622141 | 0,02 (1/48) | 0,36 (48/134) |
| 0,956412671856 | 0,02 (1/47) | 0,35 (47/134) |
| 0,958913237816 | 0,02 (1/46) | 0,34 (46/134) |
| 0,960287660148 | 0,02 (1/45) | 0,34 (45/134) |
| 0,962814161609 | 0,02 (1/44) | 0,33 (44/134) |
| 0,964228046505 | 0,02 (1/43) | 0,32 (43/134) |
| 0,964241086709 | 0,02 (1/42) | 0,31 (42/134) |
| 0,964518897662 | 0,02 (1/41) | 0,31 (41/134) |
| 0,965258859677 | 0,03 (1/40) | 0,30 (40/134) |
| 0,966731840821 | 0,00 (0/39) | 0,29 (39/134) |
| 0,967108225535 | 0,00 (0/38) | 0,28 (38/134) |
| 0,967325058838 | 0,00 (0/37) | 0,28 (37/134) |
| 0,969753133721 | 0,00 (0/36) | 0,27 (36/134) |
| 0,971234159253 | 0,00 (0/35) | 0,26 (35/134) |
| 0,971908223616 | 0,00 (0/34) | 0,25 (34/134) |
| 0,97231388796 | 0,00 (0/33) | 0,25 (33/134) |
| 0,973993851216 | 0,00 (0/32) | 0,24 (32/134) |
| 0,974108854454 | 0,00 (0/31) | 0,23 (31/134) |
| 0,974557668487 | 0,00 (0/30) | 0,22 (30/134) |
| 0,975550661989 | 0,00 (0/29) | 0,22 (29/134) |
| 0,97657648445 | 0,00 (0/28) | 0,21 (28/134) |
| 0,977637015721 | 0,00 (0/27) | 0,20 (27/134) |
| 0,978136133524 | 0,00 (0/26) | 0,19 (26/134) |
| 0,978424082846 | 0,00 (0/25) | 0,19 (25/134) |
| 0,978865038733 | 0,00 (0/24) | 0,18 (24/134) |
| 0,980268324477 | 0,00 (0/23) | 0,17 (23/134) |
| 0,980276685526 | 0,00 (0/22) | 0,16 (22/134) |
| 0,980571351071 | 0,00 (0/21) | 0,16 (21/134) |
| 0,980622226468 | 0,00 (0/20) | 0,15 (20/134) |
| 0,981367788533 | 0,00 (0/19) | 0,14 (19/134) |
| 0,983838186385 | 0,00 (0/18) | 0,13 (18/134) |
| 0,985325763791 | 0,00 (0/17) | 0,13 (17/134) |
| 0,9856786627 | 0,00 (0/16) | 0,12 (16/134) |
| 0,986418200546 | 0,00 (0/15) | 0,11 (15/134) |
| 0,98649509971 | 0,00 (0/14) | 0,10 (14/134) |
| 0,987199455287 | 0,00 (0/13) | 0,10 (13/134) |
| 0,989542673162 | 0,00 (0/12) | 0,09 (12/134) |
| 0,991268444024 | 0,00 (0/11) | 0,08 (11/134) |
| 0,991927721935 | 0,00 (0/10) | 0,07 (10/134) |
| 0,992217928599 | 0,00 (0/9) | 0,07 (9/134) |
| 0,99227748773 | 0,00 (0/8) | 0,06 (8/134) |
| 0,992708170001 | 0,00 (0/7) | 0,05 (7/134) |
| 0,994509091371 | 0,00 (0/6) | 0,04 (6/134) |
| 0,994933408827 | 0,00 (0/5) | 0,04 (5/134) |
| 0,996045910258 | 0,00 (0/4) | 0,03 (4/134) |
| 0,996062887633 | 0,00 (0/3) | 0,02 (3/134) |
| 0,997426153206 | 0,00 (0/2) | 0,01 (2/134) |
| 0,997569771294 | 0,00 (0/1) | 0,01 (1/134) |

### Zalecane progi (docelowy błąd 0,01)
- Operacja: próg 0,697909976541; przyjęte 64/79; błędy 0,00 (0/64).
- Uwaga (Operacja): liczba decyzji ponad progiem wynosi 64 (wymagane co najmniej 100); zbiór jest za mały, by potwierdzić błąd 0,01.
- Parametry modelu: próg 0,966731840821; przyjęte 39/134; błędy 0,00 (0/39).
- Uwaga (Parametry modelu): liczba decyzji ponad progiem wynosi 39 (wymagane co najmniej 100); zbiór jest za mały, by potwierdzić błąd 0,01.

## Błędne przypadki
- `kartograf-hierarchy-004` (powtórzenie 0): Proszę pobrać ortofotomapę z arkuszy pod N-34-130-D-d-2 w skali 1:10000.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.3984202352547286, "method": "logprobs", "probabilities": {"download_bdot10k": 0.10723335157863265, "download_dem_sheet": 0.3984202352547286, "download_elevation_cutout": 0.18820039306954023, "download_sheet_hierarchy": 0.17679790767615683, "out_of_scope": 0.1293481124209418}}.
- `kartograf-hierarchy-008` (powtórzenie 0): wyciagnij dsm z potomnych 5.123.45 do 1:1000; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.6604940660461729, "method": "logprobs", "probabilities": {"download_bdot10k": 0.0478460296669496, "download_dem_sheet": 0.04222397298205368, "download_elevation_cutout": 0.6604940660461729, "download_sheet_hierarchy": 0.21443102821743884, "out_of_scope": 0.03500490308738501}}.
- `kartograf-hierarchy-010` (powtórzenie 0): Rozwiń N-34-130-D-d-2 do arkuszy potomnych z rzeźbą terenu.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.49893648520182543, "method": "logprobs", "probabilities": {"download_bdot10k": 0.021921739232608803, "download_dem_sheet": 0.49893648520182543, "download_elevation_cutout": 0.02814807035267053, "download_sheet_hierarchy": 0.4403099027770558, "out_of_scope": 0.010683802435839412}}.
- `kartograf-hierarchy-011` (powtórzenie 0): Daj arkusze NMPT spod 7.108.12.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.3563399870265238, "method": "logprobs", "probabilities": {"download_bdot10k": 0.09009685828885487, "download_dem_sheet": 0.24490865268784395, "download_elevation_cutout": 0.3563399870265238, "download_sheet_hierarchy": 0.277517860935911, "out_of_scope": 0.031136641060866384}}.
- `kartograf-hierarchy-013` (powtórzenie 0): Potrzebuję NMT 1 m z hierarchii pod 6.111.22 do skali 1:1000.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.3729079517733468, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04453750357055354, "download_dem_sheet": 0.3729079517733468, "download_elevation_cutout": 0.21247654612604033, "download_sheet_hierarchy": 0.35031460112289964, "out_of_scope": 0.01976339740715962}}.
- `kartograf-hierarchy-014` (powtórzenie 0): sciagnij dzieci dsm arkusza 7.108.12; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.47986191918083676, "method": "logprobs", "probabilities": {"download_bdot10k": 0.12915308344170093, "download_dem_sheet": 0.2063860396869326, "download_elevation_cutout": 0.47986191918083676, "download_sheet_hierarchy": 0.11759522067784882, "out_of_scope": 0.06700373701268096}}.
- `kartograf-cutout-008` (powtórzenie 0): Wycinek wysokościowy NMT 530000 382000 530100 382100 PL-1992.; pole `target_crs`; oczekiwano "question"; otrzymano {"value": "epsg_2180", "source": "command"}.
- `kartograf-cutout-008` (powtórzenie 0): Wycinek wysokościowy NMT 530000 382000 530100 382100 PL-1992.; pole `target_crs`; oczekiwano "unspecified"; otrzymano "epsg_2180".
- `kartograf-cutout-018` (powtórzenie 0): Daj NMT z x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045, EVRF2007.; pole `operation`; oczekiwano "download_elevation_cutout"; otrzymano {"name": "operation", "key": "download_sheet_hierarchy", "confidence": 0.4885110699873212, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04009943050766859, "download_dem_sheet": 0.10239748301870942, "download_elevation_cutout": 0.3357484209729921, "download_sheet_hierarchy": 0.4885110699873212, "out_of_scope": 0.03324359551330874}}.
- `near-001` (powtórzenie 0): Pobierz chmurę punktów LAZ dla zlewni Warty.; pole `operation`; oczekiwano "out_of_scope"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.3848976066295344, "method": "logprobs", "probabilities": {"download_bdot10k": 0.18181275560186028, "download_dem_sheet": 0.1707972775985015, "download_elevation_cutout": 0.3848976066295344, "download_sheet_hierarchy": 0.043184314632556196, "out_of_scope": 0.21930804553754774}}.
- `near-004` (powtórzenie 0): Wyznacz hydrologiczne grupy glebowe HSG dla arkusza N-34-130-D-d-2-4.; pole `operation`; oczekiwano "out_of_scope"; otrzymano {"name": "operation", "key": "download_bdot10k", "confidence": 0.42391612907833065, "method": "logprobs", "probabilities": {"download_bdot10k": 0.42391612907833065, "download_dem_sheet": 0.0784165990001951, "download_elevation_cutout": 0.08885764785183271, "download_sheet_hierarchy": 0.05737080939738435, "out_of_scope": 0.35143881467225724}}.

## Naruszenia W-03
Brak.

## Czasy planowania i zapytania do modelu na plan
| Grupa (wszystkie, operacja lub tag) | Mediana (s) | P90 (s) | Maksimum (s) | Mediana zapytań | P90 zapytań | Maksimum zapytań |
| --- | --- | --- | --- | --- | --- | --- |
| Wszystkie | 10,90 | 14,62 | 18,64 | 3 | 4 | 5 |
| download_bdot10k | 8,01 | 8,05 | 8,17 | 2 | 2 | 2 |
| download_dem_sheet | 10,88 | 11,11 | 11,14 | 3 | 3 | 3 |
| download_elevation_cutout | 14,23 | 14,74 | 14,78 | 4 | 4 | 4 |
| download_sheet_hierarchy | 12,22 | 17,90 | 18,64 | 3 | 5 | 5 |
| out_of_scope | 4,75 | 4,97 | 4,98 | 1 | 1 | 1 |
| ambiguous | 14,03 | 14,53 | 14,53 | 4 | 4 | 4 |
| colloquial | 12,03 | 14,32 | 14,78 | 3 | 4 | 4 |
| complete | 11,94 | 14,70 | 17,90 | 3 | 4 | 5 |
| formal | 11,86 | 14,70 | 18,64 | 3 | 4 | 5 |
| incomplete | 11,04 | 14,23 | 18,64 | 3 | 4 | 5 |
| near_miss | 4,96 | 4,98 | 4,98 | 1 | 1 | 1 |
| out_of_scope | 4,74 | 4,96 | 4,97 | 1 | 1 | 1 |
| typo | 11,03 | 14,06 | 14,21 | 3 | 4 | 4 |
