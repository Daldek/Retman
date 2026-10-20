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

retman init     # tworzy plik konfiguracyjny i foldery magazynów danych narzędzi
retman doctor   # sprawdza środowisko i podpowiada, co naprawić
```

## Dokumentacja

| Plik | Zawartość |
|---|---|
| [USAGE.md](docs/USAGE.md) | Praca z Retmanem: polecenia, pytania, plany, wyniki, Python, diagnostyka — z przykładami |
| [PRD.md](docs/PRD.md) | Wymagania produktowe: użytkownicy, scenariusze, zakres wersji |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Projekt techniczny: architektura, adaptery narzędzi, modele, konfiguracja |
| [DECISIONS.md](docs/DECISIONS.md) | Rejestr decyzji architektonicznych (ADR) |
| [CHANGELOG.md](docs/CHANGELOG.md) | Historia zmian per wydanie |
| [PROGRESS.md](docs/PROGRESS.md) | Bieżący stan prac |
| [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) | Dla deweloperów: środowisko, testy, konwencje, workflow |

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
na życzenie, `retman doctor`, `retman-eval` i `retman-scaffold`; backend basal jeszcze nie powstał.
Sposób pracy z przykładami: [docs/USAGE.md](docs/USAGE.md).
Wersje 0.x są publicznie dostępne, ale nie są rekomendowane do wdrożeń produkcyjnych przed
wersją 1.0.0.
