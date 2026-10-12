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

- [Hydrograf](https://github.com/Daldek/Hydrograf) — wyznaczanie zlewni, procedury złożone
- [Kartograf](https://github.com/Daldek/Kartograf) — dane przestrzenne
- [IMGWTools](https://github.com/Daldek/IMGWTools) — dane pomiarowe IMGW
- [Hydrolog](https://github.com/Daldek/Hydrolog) — obliczenia hydrologiczne
- BasicHydraulics — proste obliczenia hydrauliczne

Lista pierwszych operacji (v0.1) jest jeszcze ustalana.

## Jak to wygląda

```
$ retman "ściągnij opady z poznania"
Rozumiem: pobranie danych pomiarowych IMGW (opad).

? Za jaki okres pobrać dane?
  np. „2000–2020”, „ostatnie 10 lat”, „od 2015”
> od 2010 do 2020

Plan:
  Operacja:      Pobranie danych pomiarowych IMGW
  Rodzaj:        opad
  Krok czasowy:  dobowy   ← wartość domyślna, nie podano w poleceniu
  Stacja:        Poznań-Ławica
  Okres:         2010-01-01 – 2020-12-31
Wykonać? [t]ak / [n]ie / [z]mień
```

Każde wykonanie wymaga potwierdzenia planu. Wyniki trafiają do folderu projektu
(`retman-output/`) razem z dziennikiem pracy i danymi pozwalającymi odtworzyć obliczenia.

## Instalacja (planowana dla v0.1)

Podstawą jest [`uv`](https://docs.astral.sh/uv/). Retman i potrzebne narzędzia instaluje się
w jednym środowisku, a serwer modelu osobno:

```bash
uv tool install "git+https://github.com/Daldek/Retman" \
    --with "git+https://github.com/Daldek/IMGWTools" \
    --with "git+https://github.com/Daldek/Hydrolog"

retman init     # tworzy plik konfiguracyjny
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

W budowie (przed v0.1.0): działają cztery operacje Kartografa 0.7.2 (NMT dla arkusza,
arkusze potomne, wycinek NMT/NMPT, BDOT10k) z CLI i z Pythona, z modelem decyzyjnym
zgodnym z API OpenAI (np. Bielik 11B w LM Studio); są `retman doctor` i `retman-eval`;
backend basal jeszcze nie powstał. Sposób pracy z przykładami: [docs/USAGE.md](docs/USAGE.md).
Wersje 0.x są publicznie dostępne, ale nie są rekomendowane do wdrożeń produkcyjnych przed
wersją 1.0.0.
