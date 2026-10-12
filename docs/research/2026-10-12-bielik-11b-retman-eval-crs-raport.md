# Ocena planowania Retmana

## Konfiguracja

- Retman: 0.1.0.dev0
- Narzędzia: kartograf 0.7.2
- Backend: openai_compatible
- Model: bielik-11b-v3.0-instruct-mlx
- Metoda pewności: logprobs
- Progi: operacja 0.9, parametr 0.9

## Zbiór

Polecenia: 83; przebiegi: 83.

### Polecenia według operacji
| Operacja | Liczba |
| --- | --- |
| download_bdot10k | 15 |
| download_dem_sheet | 15 |
| download_elevation_cutout | 23 |
| download_sheet_hierarchy | 15 |
| out_of_scope | 15 |

### Polecenia według tagu
| Tag | Liczba |
| --- | --- |
| ambiguous | 5 |
| colloquial | 22 |
| complete | 39 |
| formal | 33 |
| incomplete | 24 |
| near_miss | 5 |
| out_of_scope | 10 |
| typo | 14 |

## Miary
| Miara | Wynik |
| --- | --- |
| Trafność operacji | 0,88 (73/83) |
| Trafność operacji w zakresie | 0,88 (60/68) |
| Trafność rozpoznania spoza zakresu | 0,87 (13/15) |
| Trafność wartości parametrów | 0,80 (144/179) |
| Poprawne wartości bez pytania | 0,80 (144/179) |
| Błędne wartości bez pytania | 0,03 (6/179) |
| Wartości, o które zapytano | 0,16 (29/179) |
| Pokrycie automatyczne poleceń kompletnych | 0,36 (14/39) |
| Błąd bez pytania W-02 — łącznie | 0,00 (0/189) |
| Błąd bez pytania W-02 — operacja | 0,00 (0/45) |
| Błąd bez pytania W-02 — parametry modelu | 0,00 (0/66) |
| Błąd bez pytania W-02 — ekstraktory | 0,00 (0/78) |
| Ciche zgadywanie | — (0/0) |
| Trafne dopytania (czułość) | 0,95 (40/42) |
| Pytania zbędne na polecenie | 0,35 (29/83) |
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
| download_elevation_cutout | Trafność operacji | 0,91 (21/23) |
| download_elevation_cutout | Trafność operacji w zakresie | 0,91 (21/23) |
| download_elevation_cutout | Trafność rozpoznania spoza zakresu | — (0/0) |
| download_elevation_cutout | Trafność wartości parametrów | 0,84 (61/73) |
| download_elevation_cutout | Poprawne wartości bez pytania | 0,84 (61/73) |
| download_elevation_cutout | Błędne wartości bez pytania | 0,00 (0/73) |
| download_elevation_cutout | Wartości, o które zapytano | 0,16 (12/73) |
| download_elevation_cutout | Pokrycie automatyczne poleceń kompletnych | 0,31 (4/13) |
| download_elevation_cutout | Błąd bez pytania W-02 — łącznie | 0,00 (0/71) |
| download_elevation_cutout | Błąd bez pytania W-02 — operacja | 0,00 (0/10) |
| download_elevation_cutout | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/26) |
| download_elevation_cutout | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/35) |
| download_elevation_cutout | Ciche zgadywanie | — (0/0) |
| download_elevation_cutout | Trafne dopytania (czułość) | 1,00 (19/19) |
| download_elevation_cutout | Pytania zbędne na polecenie | 0,52 (12/23) |
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
| ambiguous | Błąd bez pytania W-02 — łącznie | 0,00 (0/8) |
| ambiguous | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| ambiguous | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/4) |
| ambiguous | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/1) |
| ambiguous | Ciche zgadywanie | — (0/0) |
| ambiguous | Trafne dopytania (czułość) | 1,00 (11/11) |
| ambiguous | Pytania zbędne na polecenie | 0,40 (2/5) |
| ambiguous | Naruszenia W-03 | — (0/0) |
| colloquial | Trafność operacji | 0,91 (20/22) |
| colloquial | Trafność operacji w zakresie | 0,91 (20/22) |
| colloquial | Trafność rozpoznania spoza zakresu | — (0/0) |
| colloquial | Trafność wartości parametrów | 0,86 (49/57) |
| colloquial | Poprawne wartości bez pytania | 0,86 (49/57) |
| colloquial | Błędne wartości bez pytania | 0,04 (2/57) |
| colloquial | Wartości, o które zapytano | 0,11 (6/57) |
| colloquial | Pokrycie automatyczne poleceń kompletnych | 0,31 (4/13) |
| colloquial | Błąd bez pytania W-02 — łącznie | 0,00 (0/58) |
| colloquial | Błąd bez pytania W-02 — operacja | 0,00 (0/9) |
| colloquial | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/23) |
| colloquial | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/26) |
| colloquial | Ciche zgadywanie | — (0/0) |
| colloquial | Trafne dopytania (czułość) | 1,00 (14/14) |
| colloquial | Pytania zbędne na polecenie | 0,27 (6/22) |
| colloquial | Naruszenia W-03 | — (0/0) |
| complete | Trafność operacji | 0,90 (35/39) |
| complete | Trafność operacji w zakresie | 0,90 (35/39) |
| complete | Trafność rozpoznania spoza zakresu | — (0/0) |
| complete | Trafność wartości parametrów | 0,80 (101/126) |
| complete | Poprawne wartości bez pytania | 0,80 (101/126) |
| complete | Błędne wartości bez pytania | 0,03 (4/126) |
| complete | Wartości, o które zapytano | 0,17 (21/126) |
| complete | Pokrycie automatyczne poleceń kompletnych | 0,36 (14/39) |
| complete | Błąd bez pytania W-02 — łącznie | 0,00 (0/118) |
| complete | Błąd bez pytania W-02 — operacja | 0,00 (0/17) |
| complete | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/49) |
| complete | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/52) |
| complete | Ciche zgadywanie | — (0/0) |
| complete | Trafne dopytania (czułość) | — (0/0) |
| complete | Pytania zbędne na polecenie | 0,54 (21/39) |
| complete | Naruszenia W-03 | — (0/0) |
| formal | Trafność operacji | 0,91 (30/33) |
| formal | Trafność operacji w zakresie | 0,91 (30/33) |
| formal | Trafność rozpoznania spoza zakresu | — (0/0) |
| formal | Trafność wartości parametrów | 0,85 (75/88) |
| formal | Poprawne wartości bez pytania | 0,85 (75/88) |
| formal | Błędne wartości bez pytania | 0,05 (4/88) |
| formal | Wartości, o które zapytano | 0,10 (9/88) |
| formal | Pokrycie automatyczne poleceń kompletnych | 0,59 (10/17) |
| formal | Błąd bez pytania W-02 — łącznie | 0,00 (0/96) |
| formal | Błąd bez pytania W-02 — operacja | 0,00 (0/21) |
| formal | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/38) |
| formal | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/37) |
| formal | Ciche zgadywanie | — (0/0) |
| formal | Trafne dopytania (czułość) | 0,91 (20/22) |
| formal | Pytania zbędne na polecenie | 0,27 (9/33) |
| formal | Naruszenia W-03 | — (0/0) |
| incomplete | Trafność operacji | 0,83 (20/24) |
| incomplete | Trafność operacji w zakresie | 0,83 (20/24) |
| incomplete | Trafność rozpoznania spoza zakresu | — (0/0) |
| incomplete | Trafność wartości parametrów | 0,83 (38/46) |
| incomplete | Poprawne wartości bez pytania | 0,83 (38/46) |
| incomplete | Błędne wartości bez pytania | 0,04 (2/46) |
| incomplete | Wartości, o które zapytano | 0,13 (6/46) |
| incomplete | Pokrycie automatyczne poleceń kompletnych | — (0/0) |
| incomplete | Błąd bez pytania W-02 — łącznie | 0,00 (0/50) |
| incomplete | Błąd bez pytania W-02 — operacja | 0,00 (0/12) |
| incomplete | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/13) |
| incomplete | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/25) |
| incomplete | Ciche zgadywanie | — (0/0) |
| incomplete | Trafne dopytania (czułość) | 0,94 (29/31) |
| incomplete | Pytania zbędne na polecenie | 0,25 (6/24) |
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
| typo | Trafność operacji | 0,79 (11/14) |
| typo | Trafność operacji w zakresie | 0,79 (11/14) |
| typo | Trafność rozpoznania spoza zakresu | — (0/0) |
| typo | Trafność wartości parametrów | 0,61 (22/36) |
| typo | Poprawne wartości bez pytania | 0,61 (22/36) |
| typo | Błędne wartości bez pytania | 0,00 (0/36) |
| typo | Wartości, o które zapytano | 0,39 (14/36) |
| typo | Pokrycie automatyczne poleceń kompletnych | 0,00 (0/9) |
| typo | Błąd bez pytania W-02 — łącznie | 0,00 (0/25) |
| typo | Błąd bez pytania W-02 — operacja | 0,00 (0/3) |
| typo | Błąd bez pytania W-02 — parametry modelu | 0,00 (0/6) |
| typo | Błąd bez pytania W-02 — ekstraktory | 0,00 (0/16) |
| typo | Ciche zgadywanie | — (0/0) |
| typo | Trafne dopytania (czułość) | 1,00 (8/8) |
| typo | Pytania zbędne na polecenie | 1,00 (14/14) |
| typo | Naruszenia W-03 | — (0/0) |

## Krzywe progów

### Decyzje o operacji
| Próg | Błędy wśród decyzji ponad progiem | Pokrycie decyzji |
| --- | --- | --- |
| 0,356339987027 | 0,12 (10/83) | 1,00 (83/83) |
| 0,372907951773 | 0,11 (9/82) | 0,99 (82/83) |
| 0,38489760663 | 0,10 (8/81) | 0,98 (81/83) |
| 0,398420235255 | 0,09 (7/80) | 0,96 (80/83) |
| 0,413486112872 | 0,08 (6/79) | 0,95 (79/83) |
| 0,423916129078 | 0,08 (6/78) | 0,94 (78/83) |
| 0,436815297432 | 0,06 (5/77) | 0,93 (77/83) |
| 0,479861919181 | 0,07 (5/76) | 0,92 (76/83) |
| 0,488511069987 | 0,05 (4/75) | 0,90 (75/83) |
| 0,498936485202 | 0,04 (3/74) | 0,89 (74/83) |
| 0,534575907026 | 0,03 (2/73) | 0,88 (73/83) |
| 0,568423054881 | 0,01 (1/72) | 0,87 (72/83) |
| 0,597693463846 | 0,01 (1/71) | 0,86 (71/83) |
| 0,601535637251 | 0,01 (1/70) | 0,84 (70/83) |
| 0,637010195732 | 0,01 (1/69) | 0,83 (69/83) |
| 0,638689250459 | 0,01 (1/68) | 0,82 (68/83) |
| 0,660494066046 | 0,01 (1/67) | 0,81 (67/83) |
| 0,661579298069 | 0,00 (0/66) | 0,80 (66/83) |
| 0,697909976541 | 0,00 (0/65) | 0,78 (65/83) |
| 0,702586375157 | 0,00 (0/64) | 0,77 (64/83) |
| 0,714208468325 | 0,00 (0/63) | 0,76 (63/83) |
| 0,725980191855 | 0,00 (0/62) | 0,75 (62/83) |
| 0,730314571974 | 0,00 (0/61) | 0,73 (61/83) |
| 0,749750664369 | 0,00 (0/60) | 0,72 (60/83) |
| 0,759047804703 | 0,00 (0/59) | 0,71 (59/83) |
| 0,767642139488 | 0,00 (0/58) | 0,70 (58/83) |
| 0,782306503292 | 0,00 (0/57) | 0,69 (57/83) |
| 0,794723491557 | 0,00 (0/56) | 0,67 (56/83) |
| 0,805611141034 | 0,00 (0/55) | 0,66 (55/83) |
| 0,815265667578 | 0,00 (0/54) | 0,65 (54/83) |
| 0,82211791376 | 0,00 (0/53) | 0,64 (53/83) |
| 0,842205802596 | 0,00 (0/52) | 0,63 (52/83) |
| 0,846026937357 | 0,00 (0/51) | 0,61 (51/83) |
| 0,846646198572 | 0,00 (0/50) | 0,60 (50/83) |
| 0,852196407923 | 0,00 (0/49) | 0,59 (49/83) |
| 0,865511094743 | 0,00 (0/48) | 0,58 (48/83) |
| 0,867817830158 | 0,00 (0/47) | 0,57 (47/83) |
| 0,872046450951 | 0,00 (0/46) | 0,55 (46/83) |
| 0,873133811898 | 0,00 (0/45) | 0,54 (45/83) |
| 0,874153041792 | 0,00 (0/44) | 0,53 (44/83) |
| 0,878190996101 | 0,00 (0/43) | 0,52 (43/83) |
| 0,890274213794 | 0,00 (0/42) | 0,51 (42/83) |
| 0,890664265232 | 0,00 (0/41) | 0,49 (41/83) |
| 0,896165835826 | 0,00 (0/40) | 0,48 (40/83) |
| 0,897914154551 | 0,00 (0/39) | 0,47 (39/83) |
| 0,89940316348 | 0,00 (0/38) | 0,46 (38/83) |
| 0,899656655086 | 0,00 (0/37) | 0,45 (37/83) |
| 0,9005375503 | 0,00 (0/36) | 0,43 (36/83) |
| 0,902214378391 | 0,00 (0/35) | 0,42 (35/83) |
| 0,902638868831 | 0,00 (0/34) | 0,41 (34/83) |
| 0,903832834933 | 0,00 (0/33) | 0,40 (33/83) |
| 0,904531420739 | 0,00 (0/32) | 0,39 (32/83) |
| 0,906252078946 | 0,00 (0/31) | 0,37 (31/83) |
| 0,910819011625 | 0,00 (0/30) | 0,36 (30/83) |
| 0,913504575991 | 0,00 (0/29) | 0,35 (29/83) |
| 0,91804491099 | 0,00 (0/28) | 0,34 (28/83) |
| 0,91876957133 | 0,00 (0/27) | 0,33 (27/83) |
| 0,919943955626 | 0,00 (0/26) | 0,31 (26/83) |
| 0,920202031318 | 0,00 (0/25) | 0,30 (25/83) |
| 0,924029890579 | 0,00 (0/24) | 0,29 (24/83) |
| 0,924355131602 | 0,00 (0/23) | 0,28 (23/83) |
| 0,926983752211 | 0,00 (0/22) | 0,27 (22/83) |
| 0,9277317539 | 0,00 (0/21) | 0,25 (21/83) |
| 0,928828529904 | 0,00 (0/20) | 0,24 (20/83) |
| 0,92956384156 | 0,00 (0/19) | 0,23 (19/83) |
| 0,930021939009 | 0,00 (0/18) | 0,22 (18/83) |
| 0,931620629452 | 0,00 (0/17) | 0,20 (17/83) |
| 0,936700942988 | 0,00 (0/16) | 0,19 (16/83) |
| 0,937515389772 | 0,00 (0/15) | 0,18 (15/83) |
| 0,940664362422 | 0,00 (0/14) | 0,17 (14/83) |
| 0,941295756086 | 0,00 (0/13) | 0,16 (13/83) |
| 0,944603603639 | 0,00 (0/12) | 0,14 (12/83) |
| 0,945927023839 | 0,00 (0/11) | 0,13 (11/83) |
| 0,952446555512 | 0,00 (0/10) | 0,12 (10/83) |
| 0,956038811078 | 0,00 (0/9) | 0,11 (9/83) |
| 0,962243173386 | 0,00 (0/8) | 0,10 (8/83) |
| 0,968462381204 | 0,00 (0/7) | 0,08 (7/83) |
| 0,969302431368 | 0,00 (0/6) | 0,07 (6/83) |
| 0,971436493937 | 0,00 (0/5) | 0,06 (5/83) |
| 0,972839009729 | 0,00 (0/4) | 0,05 (4/83) |
| 0,974824338214 | 0,00 (0/3) | 0,04 (3/83) |
| 0,97528266712 | 0,00 (0/2) | 0,02 (2/83) |
| 0,977860834554 | 0,00 (0/1) | 0,01 (1/83) |

### Decyzje o parametrach modelu
| Próg | Błędy wśród decyzji ponad progiem | Pokrycie decyzji |
| --- | --- | --- |
| 0,290405579549 | 0,05 (6/123) | 1,00 (123/123) |
| 0,424398665262 | 0,05 (6/122) | 0,99 (122/123) |
| 0,450321693973 | 0,05 (6/121) | 0,98 (121/123) |
| 0,457119288699 | 0,04 (5/120) | 0,98 (120/123) |
| 0,460588717248 | 0,04 (5/119) | 0,97 (119/123) |
| 0,507836824103 | 0,04 (5/118) | 0,96 (118/123) |
| 0,511133607431 | 0,03 (4/117) | 0,95 (117/123) |
| 0,534110805333 | 0,03 (4/116) | 0,94 (116/123) |
| 0,54023208356 | 0,03 (4/115) | 0,93 (115/123) |
| 0,560305244169 | 0,04 (4/114) | 0,93 (114/123) |
| 0,578792959389 | 0,04 (4/113) | 0,92 (113/123) |
| 0,585572942882 | 0,03 (3/112) | 0,91 (112/123) |
| 0,587072608372 | 0,03 (3/111) | 0,90 (111/123) |
| 0,596462153606 | 0,02 (2/110) | 0,89 (110/123) |
| 0,603796717906 | 0,02 (2/109) | 0,89 (109/123) |
| 0,604455012808 | 0,02 (2/108) | 0,88 (108/123) |
| 0,619665572175 | 0,02 (2/107) | 0,87 (107/123) |
| 0,638790361249 | 0,02 (2/106) | 0,86 (106/123) |
| 0,670978637115 | 0,02 (2/105) | 0,85 (105/123) |
| 0,673572982946 | 0,01 (1/104) | 0,85 (104/123) |
| 0,688805708574 | 0,01 (1/103) | 0,84 (103/123) |
| 0,689642160927 | 0,01 (1/102) | 0,83 (102/123) |
| 0,691426165623 | 0,01 (1/101) | 0,82 (101/123) |
| 0,694290544239 | 0,01 (1/100) | 0,81 (100/123) |
| 0,710171003752 | 0,01 (1/99) | 0,80 (99/123) |
| 0,713386751524 | 0,01 (1/98) | 0,80 (98/123) |
| 0,720132273239 | 0,01 (1/97) | 0,79 (97/123) |
| 0,727569292069 | 0,01 (1/96) | 0,78 (96/123) |
| 0,740281421906 | 0,01 (1/95) | 0,77 (95/123) |
| 0,750611584184 | 0,01 (1/94) | 0,76 (94/123) |
| 0,751922205239 | 0,01 (1/93) | 0,76 (93/123) |
| 0,780731529589 | 0,01 (1/92) | 0,75 (92/123) |
| 0,781678047936 | 0,01 (1/91) | 0,74 (91/123) |
| 0,792743561254 | 0,01 (1/90) | 0,73 (90/123) |
| 0,801582533129 | 0,01 (1/89) | 0,72 (89/123) |
| 0,802204592261 | 0,01 (1/88) | 0,72 (88/123) |
| 0,809267155778 | 0,01 (1/87) | 0,71 (87/123) |
| 0,814754544476 | 0,01 (1/86) | 0,70 (86/123) |
| 0,822028106733 | 0,01 (1/85) | 0,69 (85/123) |
| 0,830366322795 | 0,01 (1/84) | 0,68 (84/123) |
| 0,832280521437 | 0,00 (0/83) | 0,67 (83/123) |
| 0,833845352985 | 0,00 (0/82) | 0,67 (82/123) |
| 0,83424641015 | 0,00 (0/81) | 0,66 (81/123) |
| 0,837323256 | 0,00 (0/80) | 0,65 (80/123) |
| 0,837625657037 | 0,00 (0/79) | 0,64 (79/123) |
| 0,845658135027 | 0,00 (0/78) | 0,63 (78/123) |
| 0,850460433758 | 0,00 (0/77) | 0,63 (77/123) |
| 0,851727129472 | 0,00 (0/76) | 0,62 (76/123) |
| 0,873864755204 | 0,00 (0/75) | 0,61 (75/123) |
| 0,875091451541 | 0,00 (0/74) | 0,60 (74/123) |
| 0,88160497247 | 0,00 (0/73) | 0,59 (73/123) |
| 0,882654650064 | 0,00 (0/72) | 0,59 (72/123) |
| 0,885455959428 | 0,00 (0/71) | 0,58 (71/123) |
| 0,886241677036 | 0,00 (0/70) | 0,57 (70/123) |
| 0,904484006568 | 0,00 (0/69) | 0,56 (69/123) |
| 0,906916666698 | 0,00 (0/68) | 0,55 (68/123) |
| 0,909041571928 | 0,00 (0/67) | 0,54 (67/123) |
| 0,913053807598 | 0,00 (0/66) | 0,54 (66/123) |
| 0,914307447015 | 0,00 (0/65) | 0,53 (65/123) |
| 0,916897661002 | 0,00 (0/64) | 0,52 (64/123) |
| 0,918047231634 | 0,00 (0/63) | 0,51 (63/123) |
| 0,921510204128 | 0,00 (0/62) | 0,50 (62/123) |
| 0,922326845498 | 0,00 (0/61) | 0,50 (61/123) |
| 0,931061664083 | 0,00 (0/60) | 0,49 (60/123) |
| 0,933982311374 | 0,00 (0/59) | 0,48 (59/123) |
| 0,93450129578 | 0,00 (0/58) | 0,47 (58/123) |
| 0,934697721908 | 0,00 (0/57) | 0,46 (57/123) |
| 0,934891583095 | 0,00 (0/56) | 0,46 (56/123) |
| 0,937513614261 | 0,00 (0/55) | 0,45 (55/123) |
| 0,941630301662 | 0,00 (0/54) | 0,44 (54/123) |
| 0,941840580803 | 0,00 (0/53) | 0,43 (53/123) |
| 0,94324439072 | 0,00 (0/52) | 0,42 (52/123) |
| 0,944697996169 | 0,00 (0/51) | 0,41 (51/123) |
| 0,94539644485 | 0,00 (0/50) | 0,41 (50/123) |
| 0,945927450856 | 0,00 (0/49) | 0,40 (49/123) |
| 0,948817798501 | 0,00 (0/48) | 0,39 (48/123) |
| 0,950673757522 | 0,00 (0/47) | 0,38 (47/123) |
| 0,953097914119 | 0,00 (0/46) | 0,37 (46/123) |
| 0,953672622141 | 0,00 (0/45) | 0,37 (45/123) |
| 0,956412671856 | 0,00 (0/44) | 0,36 (44/123) |
| 0,958913237816 | 0,00 (0/43) | 0,35 (43/123) |
| 0,960287660148 | 0,00 (0/42) | 0,34 (42/123) |
| 0,962814161609 | 0,00 (0/41) | 0,33 (41/123) |
| 0,964228046505 | 0,00 (0/40) | 0,33 (40/123) |
| 0,964241086709 | 0,00 (0/39) | 0,32 (39/123) |
| 0,967108225535 | 0,00 (0/38) | 0,31 (38/123) |
| 0,967325058838 | 0,00 (0/37) | 0,30 (37/123) |
| 0,969753133721 | 0,00 (0/36) | 0,29 (36/123) |
| 0,971510006966 | 0,00 (0/35) | 0,28 (35/123) |
| 0,971908223616 | 0,00 (0/34) | 0,28 (34/123) |
| 0,97231388796 | 0,00 (0/33) | 0,27 (33/123) |
| 0,972621989836 | 0,00 (0/32) | 0,26 (32/123) |
| 0,973993851216 | 0,00 (0/31) | 0,25 (31/123) |
| 0,974108854454 | 0,00 (0/30) | 0,24 (30/123) |
| 0,974557668487 | 0,00 (0/29) | 0,24 (29/123) |
| 0,975550661989 | 0,00 (0/28) | 0,23 (28/123) |
| 0,977637015721 | 0,00 (0/27) | 0,22 (27/123) |
| 0,978136133524 | 0,00 (0/26) | 0,21 (26/123) |
| 0,978424082846 | 0,00 (0/25) | 0,20 (25/123) |
| 0,978865038733 | 0,00 (0/24) | 0,20 (24/123) |
| 0,980268324477 | 0,00 (0/23) | 0,19 (23/123) |
| 0,980276685526 | 0,00 (0/22) | 0,18 (22/123) |
| 0,980571351071 | 0,00 (0/21) | 0,17 (21/123) |
| 0,980622226468 | 0,00 (0/20) | 0,16 (20/123) |
| 0,981367788533 | 0,00 (0/19) | 0,15 (19/123) |
| 0,983565454975 | 0,00 (0/18) | 0,15 (18/123) |
| 0,983838186385 | 0,00 (0/17) | 0,14 (17/123) |
| 0,985328726944 | 0,00 (0/16) | 0,13 (16/123) |
| 0,985532775048 | 0,00 (0/15) | 0,12 (15/123) |
| 0,98649509971 | 0,00 (0/14) | 0,11 (14/123) |
| 0,987199455287 | 0,00 (0/13) | 0,11 (13/123) |
| 0,989614127188 | 0,00 (0/12) | 0,10 (12/123) |
| 0,991268444024 | 0,00 (0/11) | 0,09 (11/123) |
| 0,991578869933 | 0,00 (0/10) | 0,08 (10/123) |
| 0,992217928599 | 0,00 (0/9) | 0,07 (9/123) |
| 0,99227748773 | 0,00 (0/8) | 0,07 (8/123) |
| 0,992708170001 | 0,00 (0/7) | 0,06 (7/123) |
| 0,994509091371 | 0,00 (0/6) | 0,05 (6/123) |
| 0,995055539315 | 0,00 (0/5) | 0,04 (5/123) |
| 0,996045910258 | 0,00 (0/4) | 0,03 (4/123) |
| 0,996062887633 | 0,00 (0/3) | 0,02 (3/123) |
| 0,997426153206 | 0,00 (0/2) | 0,02 (2/123) |
| 0,997569771294 | 0,00 (0/1) | 0,01 (1/123) |

### Zalecane progi (docelowy błąd 0,01)
- Operacja: próg 0,661579298069; przyjęte 66/83; błędy 0,00 (0/66).
- Uwaga (Operacja): liczba decyzji ponad progiem wynosi 66 (wymagane co najmniej 100); zbiór jest za mały, by potwierdzić błąd 0,01.
- Parametry modelu: próg 0,673572982946; przyjęte 104/123; błędy 0,01 (1/104).

## Błędne przypadki
- `kartograf-hierarchy-004` (powtórzenie 0): Proszę pobrać ortofotomapę z arkuszy pod N-34-130-D-d-2 w skali 1:10000.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.3984202352547286, "method": "logprobs", "probabilities": {"download_bdot10k": 0.10723335157863265, "download_dem_sheet": 0.3984202352547286, "download_elevation_cutout": 0.18820039306954023, "download_sheet_hierarchy": 0.17679790767615683, "out_of_scope": 0.1293481124209418}}.
- `kartograf-hierarchy-008` (powtórzenie 0): wyciagnij dsm z potomnych 5.123.45 do 1:1000; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.6604940660461729, "method": "logprobs", "probabilities": {"download_bdot10k": 0.0478460296669496, "download_dem_sheet": 0.04222397298205368, "download_elevation_cutout": 0.6604940660461729, "download_sheet_hierarchy": 0.21443102821743884, "out_of_scope": 0.03500490308738501}}.
- `kartograf-hierarchy-010` (powtórzenie 0): Rozwiń N-34-130-D-d-2 do arkuszy potomnych z rzeźbą terenu.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.49893648520182543, "method": "logprobs", "probabilities": {"download_bdot10k": 0.021921739232608803, "download_dem_sheet": 0.49893648520182543, "download_elevation_cutout": 0.02814807035267053, "download_sheet_hierarchy": 0.4403099027770558, "out_of_scope": 0.010683802435839412}}.
- `kartograf-hierarchy-011` (powtórzenie 0): Daj arkusze NMPT spod 7.108.12.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.3563399870265238, "method": "logprobs", "probabilities": {"download_bdot10k": 0.09009685828885487, "download_dem_sheet": 0.24490865268784395, "download_elevation_cutout": 0.3563399870265238, "download_sheet_hierarchy": 0.277517860935911, "out_of_scope": 0.031136641060866384}}.
- `kartograf-hierarchy-013` (powtórzenie 0): Potrzebuję NMT 1 m z hierarchii pod 6.111.22 do skali 1:1000.; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.3729079517733468, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04453750357055354, "download_dem_sheet": 0.3729079517733468, "download_elevation_cutout": 0.21247654612604033, "download_sheet_hierarchy": 0.35031460112289964, "out_of_scope": 0.01976339740715962}}.
- `kartograf-hierarchy-014` (powtórzenie 0): sciagnij dzieci dsm arkusza 7.108.12; pole `operation`; oczekiwano "download_sheet_hierarchy"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.47986191918083676, "method": "logprobs", "probabilities": {"download_bdot10k": 0.12915308344170093, "download_dem_sheet": 0.2063860396869326, "download_elevation_cutout": 0.47986191918083676, "download_sheet_hierarchy": 0.11759522067784882, "out_of_scope": 0.06700373701268096}}.
- `kartograf-cutout-018` (powtórzenie 0): Daj NMT z x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045, EVRF2007.; pole `operation`; oczekiwano "download_elevation_cutout"; otrzymano {"name": "operation", "key": "download_sheet_hierarchy", "confidence": 0.4885110699873212, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04009943050766859, "download_dem_sheet": 0.10239748301870942, "download_elevation_cutout": 0.3357484209729921, "download_sheet_hierarchy": 0.4885110699873212, "out_of_scope": 0.03324359551330874}}.
- `kartograf-cutout-022` (powtórzenie 0): nmt 16.90 52.40 16.91 52.41 uklad wynikowy 3045, evrf2007; pole `operation`; oczekiwano "download_elevation_cutout"; otrzymano {"name": "operation", "key": "download_dem_sheet", "confidence": 0.5345759070256456, "method": "logprobs", "probabilities": {"download_bdot10k": 0.04972330493631756, "download_dem_sheet": 0.5345759070256456, "download_elevation_cutout": 0.3451481466349619, "download_sheet_hierarchy": 0.03637834701428963, "out_of_scope": 0.03417429438878528}}.
- `near-001` (powtórzenie 0): Pobierz chmurę punktów LAZ dla zlewni Warty.; pole `operation`; oczekiwano "out_of_scope"; otrzymano {"name": "operation", "key": "download_elevation_cutout", "confidence": 0.3848976066295344, "method": "logprobs", "probabilities": {"download_bdot10k": 0.18181275560186028, "download_dem_sheet": 0.1707972775985015, "download_elevation_cutout": 0.3848976066295344, "download_sheet_hierarchy": 0.043184314632556196, "out_of_scope": 0.21930804553754774}}.
- `near-004` (powtórzenie 0): Wyznacz hydrologiczne grupy glebowe HSG dla arkusza N-34-130-D-d-2-4.; pole `operation`; oczekiwano "out_of_scope"; otrzymano {"name": "operation", "key": "download_bdot10k", "confidence": 0.42391612907833065, "method": "logprobs", "probabilities": {"download_bdot10k": 0.42391612907833065, "download_dem_sheet": 0.0784165990001951, "download_elevation_cutout": 0.08885764785183271, "download_sheet_hierarchy": 0.05737080939738435, "out_of_scope": 0.35143881467225724}}.

## Naruszenia W-03
Brak.

## Czasy planowania i zapytania do modelu na plan
| Grupa (wszystkie, operacja lub tag) | Mediana (s) | P90 (s) | Maksimum (s) | Mediana zapytań | P90 zapytań | Maksimum zapytań |
| --- | --- | --- | --- | --- | --- | --- |
| Wszystkie | 10,61 | 11,76 | 17,78 | 3 | 3 | 5 |
| download_bdot10k | 7,99 | 8,01 | 8,02 | 2 | 2 | 2 |
| download_dem_sheet | 10,86 | 10,94 | 11,03 | 3 | 3 | 3 |
| download_elevation_cutout | 10,63 | 10,80 | 10,89 | 3 | 3 | 3 |
| download_sheet_hierarchy | 11,76 | 17,68 | 17,78 | 3 | 5 | 5 |
| out_of_scope | 4,79 | 4,98 | 5,00 | 1 | 1 | 1 |
| ambiguous | 10,55 | 10,89 | 10,89 | 3 | 3 | 3 |
| colloquial | 10,75 | 11,74 | 11,78 | 3 | 3 | 3 |
| complete | 10,75 | 11,76 | 17,78 | 3 | 3 | 5 |
| formal | 10,82 | 11,86 | 17,78 | 3 | 3 | 5 |
| incomplete | 10,82 | 11,86 | 17,68 | 3 | 3 | 5 |
| near_miss | 4,98 | 5,00 | 5,00 | 1 | 1 | 1 |
| out_of_scope | 4,73 | 4,94 | 4,96 | 1 | 1 | 1 |
| typo | 10,60 | 10,86 | 11,76 | 3 | 3 | 3 |
