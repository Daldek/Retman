# Retman

Retman to warstwa poleceń w języku naturalnym dla ekosystemu narzędzi hydrologicznych.
Opisujesz zadanie zwykłym zdaniem po polsku, a Retman rozpoznaje operację, dopytuje
o brakujące dane, pokazuje plan do zatwierdzenia i uruchamia właściwe narzędzie.
Działa jako narzędzie wiersza poleceń (`retman`) i jako biblioteka Python.

Retman nie zastępuje GUI narzędzi i nie zawiera modelu językowego — łączy się przez API
z modelem uruchomionym osobno: domyślnie z basalem
przez basal-serve, a alternatywnie z dowolnym serwerem zgodnym z API OpenAI (np. LM Studio,
Ollama) albo z modelem dostawcy.

Nazwa pochodzi od retmana — dowódcy flisaków, który prowadził załogę i tratwę rzeką do celu.

## Obsługiwane narzędzia

Retman korzysta wyłącznie z publicznego API narzędzi; same narzędzia nic o nim nie wiedzą.

- [Hydrograf](https://github.com/Daldek/Hydrograf) — wyznaczanie zlewni, procedury złożone (planowane, v0.2)
- [Kartograf](https://github.com/Daldek/Kartograf) — dane przestrzenne GUGiK: NMT, NMPT, ortofotomapa, BDOT10k (v0.1, wersja 0.8.0; także obszar z pliku SHP/GPKG)
- [IMGWTools](https://github.com/Daldek/IMGWTools) — dane pomiarowe IMGW-PIB i ČHMÚ: stacje, dane bieżące, PMAXTP, szeregi, archiwa, projekty danych (v0.1, wersja 3.0.0, 26 operacji)
- [Hydrolog](https://github.com/Daldek/Hydrolog) — obliczenia hydrologiczne (planowane, v0.2)
- BasicHydraulics — proste obliczenia hydrauliczne (planowane, v0.2)

W v0.1 działa 30 operacji (4 Kartografa i 26 IMGWTools); ich opis: [docs/USAGE.md](docs/USAGE.md), p. 9.

## Jak to wygląda

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
```

Każde wykonanie wymaga potwierdzenia planu, a do tego momentu Retman nie używa sieci narzędzi:
wiersz z oznaczeniem „podgląd” narzędzie ustaliło offline, a `s` pozwala osobno, za zgodą, sprawdzić,
jakie dane ma źródło (lata, rozdzielczości, pokrycie). Wyniki trafiają do folderu projektu
(`retman-output/`) albo — dla danych Kartografa — do magazynu danych narzędzia, zawsze razem
z dziennikiem pracy i danymi pozwalającymi odtworzyć obliczenia.

## Instalacja (planowana dla v0.1)

Podstawą jest [`uv`](https://docs.astral.sh/uv/). Retman i potrzebne narzędzia instaluje się
w jednym środowisku, a serwer modelu osobno. Do czasu wydania tagów narzędzi (`v0.8.0` Kartografa,
`v3.0.0` IMGWTools) podaje się ich wypchnięte commity:

```bash
uv tool install "git+https://github.com/Daldek/Retman@develop" \
    --with "kartograf @ git+https://github.com/Daldek/Kartograf@8e9bcbb058d11f06afae5a65e62f31870f69d169" \
    --with "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@0d98f3babeeeee49b2146a977b62bfa92114beea"

retman config init    # dopisuje tabele [retman] do nogat.toml i tworzy foldery magazynów narzędzi
retman doctor check   # sprawdza środowisko i podpowiada, co naprawić
```

## Ustawienia

Ustawienia Retmana to tabele `[retman]` pliku `nogat.toml`, wspólnego dla narzędzi Nogat (folder
ustawień użytkownika: w Linuksie `~/.config/nogat/nogat.toml`; inny plik wskazuje `NOGAT_CONFIG` albo
opcja `--config PATH`). Plik jest opcjonalny, a zmienna środowiska przesłania wartość z pliku.
Wartość pochodzi z pierwszego z miejsc: opcja polecenia, `RETMAN_<KLUCZ>` (klucz z kropkami zamienionymi
na `_`, np. `decision.url` to `RETMAN_DECISION_URL`), `NOGAT_<KLUCZ>` (tylko klucze wspólne), tabela
`[retman]`, tabela `[nogat]` (tylko klucze wspólne), wartość domyślna. `retman config show` pokazuje każde
ustawienie z wartością i źródłem. Bez wartości domyślnych jest tylko serwer modelu (`[retman.decision]`).
Klucz zewnętrznego dostawcy modelu nie trafia do pliku: Retman czyta go ze zmiennej, którą nazywa
`decision.api_key_env`.

| Zmienna | Znaczenie |
|---|---|
| `NOGAT_CONFIG` | plik `nogat.toml` (domyślnie w folderze ustawień użytkownika) |
| `RETMAN_LANG`, `NOGAT_LANG` | język pytań i komunikatów: `pl` albo `en` (teksty są tylko po polsku) |
| `RETMAN_LOG_LEVEL`, `NOGAT_LOG_LEVEL` | poziom logu na stderr: `debug`, `info`, `warning` (domyślnie), `error` |
| `RETMAN_DATA_DIR`, `NOGAT_DATA_DIR` | folder magazynów i zbioru poleceń (domyślnie folder danych użytkownika nogat) |
| `RETMAN_CACHE_DIR`, `NOGAT_CACHE_DIR` | folder cache (domyślnie folder cache użytkownika nogat) |
| `RETMAN_DECISION_BACKEND` | `basal` albo `openai_compatible` |
| `RETMAN_DECISION_URL`, `RETMAN_DECISION_MODEL` | adres serwera modelu i nazwa modelu |
| `RETMAN_DECISION_TIMEOUT_S` | ile sekund czekać na serwer modelu |
| `RETMAN_DECISION_API_KEY_ENV` | NAZWA zmiennej z kluczem zewnętrznego dostawcy modelu |
| `RETMAN_DECISION_CONFIDENCE`, `RETMAN_DECISION_CONSISTENCY_RUNS` | metoda pewności i liczba zapytań (backend `openai_compatible`) |
| `RETMAN_DECISION_THRESHOLDS_OPERATION`, `RETMAN_DECISION_THRESHOLDS_PARAMETER` | progi pewności: liczba z (0, 1] albo `auto` (tylko basal) |
| `RETMAN_TEXT_BACKEND` | model tekstowy (na razie `none`) |
| `RETMAN_OUTPUT_RESULTS_DIR` | folder wyników w folderze projektu (domyślnie `retman-output`) |
| `RETMAN_ADAPTERS_ENABLED` | narzędzia do włączenia, po przecinku (domyślnie wszystkie zainstalowane) |
| `RETMAN_TOOLS_KARTOGRAF_STORE_DIR` | magazyn Kartografa (domyślnie `<data_dir>/kartograf`) |
| `RETMAN_TOOLS_KARTOGRAF_CACHE_FILE` | cache metadanych Kartografa (domyślnie `<cache_dir>/kartograf/metadata.db`) |
| `RETMAN_TOOLS_KARTOGRAF_WORKERS`, `RETMAN_TOOLS_KARTOGRAF_UPDATE` | równoległe transfery; tryb aktualizacji `local`, `upgrade` albo `force` |
| `RETMAN_TOOLS_IMGWTOOLS_STORE_DIR` | magazyn IMGWTools (domyślnie `<data_dir>/imgw`) |
| `RETMAN_TOOLS_IMGWTOOLS_REFERENCE_DATA_DIR` | dane referencyjne IMGWTools (domyślnie `<cache_dir>/imgw/reference`) |
| `RETMAN_LOG_JOURNAL_COMMANDS` | czy dziennik projektu zapisuje treść poleceń i odpowiedzi (domyślnie `true`) |
| `RETMAN_PRIVACY_COLLECT_COMMANDS`, `RETMAN_PRIVACY_COLLECT_PATH` | zbiór poleceń ze wszystkich projektów, tylko za zgodą (domyślnie wyłączony), i jego plik |

Magazyny Kartografa i IMGWTools są wersjonowane na dowiązaniach twardych: kopię robi się z ich
zachowaniem (`rsync -aH`), a nie zwykłym kopiowaniem plików; dane usunięte u źródła nie pobiorą się
ponownie (szczegóły w README narzędzia).

## Dokumentacja

| Plik | Zawartość |
|---|---|
| [USAGE.md](docs/USAGE.md) | Praca z Retmanem: polecenia, pytania, plany, wyniki, Python, diagnostyka — z przykładami |
| [PRD.md](docs/PRD.md) | Wymagania produktowe: użytkownicy, scenariusze, zakres wersji |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Projekt techniczny: architektura, adaptery narzędzi, modele, konfiguracja |
| [DECISIONS.md](docs/DECISIONS.md) | Rejestr decyzji architektonicznych (ADR) |
| [CHANGELOG.md](docs/CHANGELOG.md) | Historia zmian per wydanie |
| [PROGRESS.md](docs/PROGRESS.md) | Bieżący stan prac |
| [CLAUDE.md](CLAUDE.md) | Dla deweloperów: zasady pracy, środowisko, testy, mapa dokumentacji |

## Wymagania

Python 3.12+ (instalowany automatycznie przez `uv`); Windows, Linux lub macOS.
Wymagania sprzętowe zależą od wybranego modelu i miejsca, w którym działa — szczegóły
w [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), p. 9.2.

## Licencja

MIT — szczegóły w pliku [LICENSE](LICENSE).

## Autor

[Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/)

## Status

W budowie (przed v0.1.0): działają cztery operacje Kartografa 0.8.0 (NMT dla arkusza lub obszaru z pliku,
arkusze potomne z ortofotomapą w trzech kolorach, wycinek NMT/NMPT, BDOT10k) i 26 operacji IMGWTools 3.0.0
(rozpoznawanie dwustopniowe: grupa, potem operacja) z CLI i z Pythona, z modelem decyzyjnym zgodnym
z API OpenAI (np. Bielik 11B w LM Studio); jest podgląd planu offline, sprawdzenie dostępności danych
na życzenie, `retman doctor check`, `retman eval run` i `retman scaffold`; backend basal jeszcze nie powstał.
Sposób pracy z przykładami: [docs/USAGE.md](docs/USAGE.md).
Wersje 0.x są publicznie dostępne, ale nie są rekomendowane do wdrożeń produkcyjnych przed
wersją 1.0.0.
