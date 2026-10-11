# Retman — dokument wymagań produktu (PRD)

> **Status dokumentu:** szkic (2026-10-11) · **Licencja:** MIT · **Język dokumentu:** polski
> **Projekt techniczny:** [ARCHITECTURE.md](ARCHITECTURE.md)

Ten dokument opisuje, **co** Retman ma robić, **dla kogo** i **dlaczego**. Nie opisuje
implementacji — ta jest w ARCHITECTURE.md. Miejsca oznaczone **[DO UZUPEŁNIENIA]** są tematem
trwającego brainstormingu.

Nazwa pochodzi od retmana — dowódcy flisaków, który prowadził załogę i tratwę rzeką do celu.

---

## 1. Problem i kontekst

Ekosystem narzędzi hydrologicznych (Hydrograf, Kartograf, IMGWTools, Hydrolog, BasicHydraulics)
daje dostęp do danych i obliczeń przez API Pythona oraz — w części narzędzi — przez GUI.
Część GUI jeszcze nie istnieje.

**[DO UZUPEŁNIENIA]** Jaki konkretny problem użytkowników rozwiązuje Retman: co dziś robią
ręcznie, ile to trwa, gdzie się mylą lub zatrzymują.

---

## 2. Wizja i rola Retmana

Retman to warstwa poleceń w języku naturalnym dla ekosystemu narzędzi. Użytkownik opisuje
zadanie zwykłym zdaniem po polsku, a Retman rozpoznaje, o co chodzi, zbiera brakujące dane,
pokazuje plan do zatwierdzenia i uruchamia właściwe narzędzie.

**Retman nie zastępuje GUI narzędzi.** To dodatkowa droga dla użytkowników, którzy chcą
uprościć typowe zadania albo wyjść poza to, co oferuje GUI. Docelowo Retman może działać także
jako okno czatu współpracujące z GUI (rozdz. 4, scenariusze S-06 i S-07).

**Narzędzia są niezależne od Retmana.** Każde z nich rozwija się samodzielnie (ewentualnie
dopasowane do Hydrografa), a utrzymanie zgodności z nimi to zadanie Retmana.

**Retman nie zawiera modelu językowego.** Model instaluje się osobno (np. w LM Studio)
albo korzysta się z modelu dostawcy przez API. Retman łączy się z nim przez API, a jego
podstawowa instalacja jest możliwie najmniejsza. Rekomendowane są modele polskie i europejskie
(np. Bielik), ale użytkownik może wpiąć także model frontierowy, jeśli ma do niego dostęp.

**Konfiguracja domyślna:** decyzje podejmuje **basal** przez osobno uruchomiony serwer
**basal-serve**, a opisy wyników po polsku (od 0.2) pisze **Bielik**, uruchomiony np. w LM Studio.
Inne modele, także frontierowe, wpina się zmianą konfiguracji.

---

## 3. Użytkownicy

### 3.1. Priorytety

**Na start:** działające narzędzie w środowisku autora. Wersje 0.x są **publicznie dostępne
na GitHubie**, ale nie są rekomendowane do wdrożeń produkcyjnych przed wersją **1.0.0** —
służą dopracowaniu produktu.

| Grupa | Kto to | Rola |
| --- | --- | --- |
| **Administracja wodna** | np. Wody Polskie, samorządy — weryfikacja opracowań, decyzje | **grupa docelowa** (od 1.0); wymaga niezawodnego produktu |
| **Projektanci** | inżynierowie w biurach projektowych przygotowujący operaty i projekty | **grupa docelowa** (od 1.0), równorzędna z administracją |
| **Studenci i niezależni testerzy** | studenci, dydaktyka, osoby chętne do testów | **testerzy wersji 0.x** — faktyczny priorytet przed 1.0 |

Badacze mogą korzystać z Retmana, ale nie są grupą docelową.

### 3.2. Poziom techniczny

Zróżnicowany — Retman musi obsłużyć **dwie ścieżki**:

| Ścieżka | Dla kogo | Jak pracuje |
| --- | --- | --- |
| **Prosta** | hydrolog bez znajomości Pythona i wiersza poleceń | prosta instalacja (N-09), wpisuje polecenia w oknie czatu — od wersji 0.5 (rozdz. 9) |
| **Zaawansowana** | hydrolog z podstawami Pythona | CLI i biblioteka Pythona (W-11), własne skrypty |

### 3.3. Sposoby uruchomienia i sprzęt

| Sposób | Dla kogo | Gdzie działa model |
| --- | --- | --- |
| **Serwer jednostki** | urzędy, uczelnie | na dedykowanym sprzęcie jednostki, w jej sieci wewnętrznej; komputer użytkownika nie potrzebuje GPU. Dostępne od v0.1 — Retman łączy się z serwerem modelu po zmianie adresu w konfiguracji |
| **Lokalnie** | niezależni projektanci z lepszym sprzętem, chętni co najmniej do przetestowania możliwości | na komputerze użytkownika z kartą graficzną NVIDIA lub z procesorem Apple Silicon (N-06) |
| **Środowisko autora** | autor, testerzy wersji 0.x | na sprzęcie autora |

- Systemy operacyjne: **Windows, Linux i macOS**.
- Sam Retman nie ma szczególnych wymagań sprzętowych. Wymagania zależą od wybranego modelu
  i miejsca, w którym działa (lokalnie, serwer jednostki, API dostawcy).
- Tryb CPU (najmniejszy model na procesorze) — opcjonalnie, jeśli pomiary pokażą akceptowalny
  czas odpowiedzi (N-07).

### 3.4. Oczekiwania i bariery

**[DO UZUPEŁNIENIA]** Czego oczekuje każda grupa i co ją zniechęci.

---

## 4. Scenariusze użycia

| ID | Scenariusz | Wersja |
| --- | --- | --- |
| S-01 | **Pojedyncza operacja.** Użytkownik wpisuje jedno zdanie (np. „Pobierz dobowe opady ze stacji Poznań z lat 2000–2020”), widzi plan, zatwierdza go i dostaje pliki z wynikiem. | 0.1 |
| S-02 | **Praca krok po kroku.** Użytkownik wyznacza zlewnię, a następnym poleceniem liczy dla niej przepływ („…dla tej zlewni”). Retman bierze zlewnię z wcześniejszego wyniku w tym projekcie i pokazuje to w planie; jeśli zlewni jest kilka, pyta, której użyć. | 0.1 |
| S-03 | **Polecenie niepełne lub niejednoznaczne.** Retman dopytuje o brakujące dane albo o właściwy odczyt (np. „Q50” — 50% czy okres powtarzalności 50 lat?). | 0.1 |
| S-04 | **Polecenie spoza zakresu.** Retman uczciwie odpowiada, że tego nie potrafi, i pokazuje, co potrafi. | 0.1 |
| S-05 | **Łańcuch operacji.** Jedno polecenie („policz przepływ stuletni dla punktu…”) uruchamia kilka kroków (zlewnia → przepływ) po jednym zatwierdzeniu planu. | 0.2 |
| S-06 | **Czat steruje GUI.** Użytkownik rozmawia z Retmanem, a ten wypełnia formularz w GUI narzędzia. | 0.5+ |
| S-07 | **GUI z podpowiedziami.** Użytkownik wypełnia w GUI to, co wie, a resztę ustala z Retmanem. | 0.5+ |

**[DO UZUPEŁNIENIA]** Scenariusze charakterystyczne dla głównych grup użytkowników (rozdz. 3).

---

## 5. Wymagania funkcjonalne

| ID | Wymaganie | Wersja | Kryterium akceptacji |
| --- | --- | --- | --- |
| W-01 | Retman rozpoznaje operację na podstawie polecenia po polsku. | 0.1 | Trafność na zbiorze testowym ≥ **[DO UZUPEŁNIENIA]** |
| W-02 | Retman dopytuje o dane brakujące, niepewne i niejednoznaczne, zamiast zgadywać. W CLI ma to formę rozmowy w terminalu — jedno pytanie naraz. | 0.1 | Wśród decyzji podjętych bez dopytywania błędnych jest ≤ **1%** (wstępnie, dla konfiguracji domyślnej; do weryfikacji na zbiorze testowym) |
| W-03 | Polecenie spoza zakresu kończy się informacją, co Retman potrafi. | 0.1 | Polecenia spoza zakresu ze zbioru testowego nie uruchamiają żadnej operacji |
| W-04 | Przed wykonaniem Retman pokazuje plan; wartości domyślne i wzięte z wcześniejszych wyników są oznaczone. | 0.1 | Każda wartość w planie ma widoczne źródło |
| W-05 | Każde wykonanie wymaga potwierdzenia użytkownika. | 0.1 | Nie istnieje ścieżka wykonania bez potwierdzenia |
| W-06 | Każde narzędzie jest dostępne samodzielnie; użytkownik widzi operacje tylko zainstalowanych narzędzi. | 0.1 | Instalacja jednego narzędzia wystarcza do pracy z jego operacjami |
| W-07 | Retman korzysta z wyników poprzednich poleceń w obrębie projektu i z plików wskazanych przez użytkownika; gdy pasuje więcej niż jeden wynik, pyta, którego użyć. | 0.1 | Scenariusz S-02 działa bez podawania ścieżek; przy kilku pasujących wynikach Retman nigdy nie wybiera sam |
| W-08 | Prawdopodobieństwo można podać jako dowolną liczbę w typowych zapisach (1%, Q1%, „stuletnia”, T = 100 lat); zapisy niejednoznaczne wywołują pytanie. | 0.1 | Wszystkie formy z ARCHITECTURE p. 4.4 rozpoznawane poprawnie |
| W-09 | Wynik to pliki w katalogu wyników plus krótkie podsumowanie. | 0.1 | **[DO UZUPEŁNIENIA]** (formaty plików) |
| W-10 | Retman diagnozuje środowisko i podpowiada, jak naprawić problemy. | 0.1 | Każdy wykryty problem ma podpowiedź naprawy |
| W-11 | Interfejsy: wiersz poleceń (CLI) w formie rozmowy w terminalu — pojedyncze polecenie albo sesja wielu poleceń — oraz biblioteka Pythona. | 0.1 | — |
| W-12 | Łańcuchy operacji (scenariusz S-05). | 0.2 | — |
| W-13 | Współpraca z GUI narzędzi (scenariusze S-06, S-07). | 0.5+ | — |
| W-14 | Doinstalowanie znanego narzędzia jednym poleceniem (`retman add-tool`), po potwierdzeniu. | 0.5+ | Narzędzie trafia do środowiska Retmana w obsługiwanej wersji; `retman doctor` widzi je bez dodatkowych kroków |
| W-15 | Dziennik pracy i ślad audytowy: każdy wynik zawiera informacje pozwalające odtworzyć, czym i jak go policzono, a projekt ma dziennik wszystkich poleceń, pytań, planów i decyzji — także odrzuconych i przerwanych. | 0.1 | Z samego folderu projektu da się ustalić dla każdego wyniku: użyte wartości i ich źródła, wersje Retmana i narzędzi, model i pewność decyzji, a przy ustawieniu `journal_commands = true` (domyślnym; ARCHITECTURE p. 5.4 i 9.1) także treść polecenia i odpowiedzi na pytania |

---

## 6. Wymagania niefunkcjonalne

| ID | Wymaganie | Wartość docelowa |
| --- | --- | --- |
| N-01 | **Własne zasoby jako droga domyślna.** Retman działa z modelem uruchomionym lokalnie lub w sieci jednostki i nie wymaga płatnych API. | — |
| N-02 | **Modele wymienne bez zmian w kodzie.** Domyślnie modele polskie: basal (decyzje) i Bielik (opisy wyników); możliwe także inne modele, w tym frontierowe przez API, jeśli użytkownik ma do nich dostęp. | — |
| N-03 | **Niezależność narzędzi.** Narzędzia nie zawierają nic związanego z Retmanem; zgodność utrzymuje Retman. | — |
| N-04 | **Prywatność.** Dane nie opuszczają skonfigurowanych usług; domyślnie wszystko działa lokalnie; polecenia nie są przekazywane ani gromadzone poza projektem bez wyraźnej zgody (dziennik projektu jest częścią pracy użytkownika i zostaje w jego folderze, W-15). O tym, gdzie działa model, decyduje użytkownik w konfiguracji; `retman doctor` pokazuje adres każdego modelu. | — |
| N-05 | **Wiarygodność ponad wygodę.** Retman woli dopytać, niż się pomylić — w każdej konfiguracji, także z modelem bez skalibrowanej pewności (ARCHITECTURE p. 3.3.3). | patrz W-02 |
| N-06 | **Minimalny sprzęt.** | lokalnie zalecane: karta NVIDIA z ok. 6–8 GB pamięci albo Apple Silicon z ok. 16 GB pamięci. Sam model domyślny (basal-1.5-mini) potrzebuje ok. 3 GB; opisy wyników przez Bielika (od 0.2) — więcej, zależnie od wielkości modelu (ARCHITECTURE p. 9.2). Przy serwerze jednostki komputer użytkownika nie potrzebuje GPU (p. 3.3) |
| N-07 | **Czas odpowiedzi** (od wpisania polecenia do pokazania planu). | **[DO UZUPEŁNIENIA]** |
| N-08 | **Otwartość.** Licencja MIT; kod po angielsku, dokumentacja po polsku. | — |
| N-09 | **Instalacja.** | Podstawą jest `uv` (Windows, Linux, macOS). Retman i narzędzia z GitHuba (publikacja na PyPI nie jest planowana), w jednym środowisku; model osobno (N-10). **Wersja trudna (0.x):** polecenia `uv` + osobno uruchomiony serwer modelu. **Wersja łatwa (0.5+):** skrypt instalacyjny, kreator `retman init`, `retman add-tool` (W-14). Bez kompilacji po stronie użytkownika; sprawdza to test instalacji w CI (ARCHITECTURE p. 9.4) |
| N-10 | **Brak modelu w pakiecie.** Retman nie jest dystrybuowany z żadnym modelem językowym; łączy się z modelem przez API (np. LM Studio, Ollama, basal-serve, API dostawcy). Podstawowa instalacja jest możliwie najmniejsza. Dotyczy to także basala: basal-serve jest osobnym programem, a nie zależnością Retmana. | — |
| N-11 | **Konfiguracja.** Ustawienia niezależne od projektu (m.in. modele, progi pewności, język, prywatność) są w jednym centralnym pliku na komputerze, bez ukrytych wartości domyślnych. Wyniki należą do projektu i są zapisywane w jego folderze. | — |

---

## 7. Zakres

### 7.1. W zakresie v0.1

- Pojedyncze, najprostsze operacje (3–5) z co najmniej dwóch narzędzi.
- Scenariusze S-01 do S-04.
- Wymagania W-01 do W-11 oraz W-15.

### 7.2. Pierwsze operacje

Kryteria wyboru:
- operacja często wykonywana przez użytkowników,
- większość wyborów to zamknięte listy, a wartości da się jednoznacznie odczytać z polecenia,
- wynik łatwo sprawdzić na prostych przykładach.

Wybrane (ADR-001; pierwsze narzędzie: Kartograf 0.7.2):

| Operacja | Narzędzie | Obszar w poleceniu |
| --- | --- | --- |
| pobranie NMT dla arkusza | Kartograf | godło arkusza |
| pobranie NMT, NMPT albo ortofotomapy dla arkusza nadrzędnego | Kartograf | godło arkusza |
| wycinek NMT albo NMPT dla obszaru | Kartograf | prostokąt w PL-1992 albo WGS84, plik z geometrią |
| pobranie BDOT10k | Kartograf | kod TERYT powiatu, prostokąt, godło |

**[DO UZUPEŁNIENIA]** Operacja drugiego narzędzia (p. 7.1).

### 7.3. Poza zakresem

- Odpowiadanie na pytania merytoryczne z hydrologii (osobny projekt asystenta).
- Zastępowanie GUI narzędzi.
- Wykonywanie operacji bez potwierdzenia przed wersją 1.0.
- Obsługa głosowa.
- Polecenia po angielsku przed wersją 0.5.

---

## 8. Miary sukcesu

| Obszar | Miara | Cel |
| --- | --- | --- |
| Jakość | trafność rozpoznania operacji | **[DO UZUPEŁNIENIA]** |
| Jakość | błędy wśród decyzji bez dopytywania | **≤ 1%** — wstępnie, do weryfikacji na zbiorze testowym (W-02) |
| Wygoda | odsetek poleceń obsłużonych bez dopytywania | **[DO UZUPEŁNIENIA]** po pierwszych testach — im niższy dopuszczalny błąd, tym częściej Retman dopytuje |
| Produkt | **[DO UZUPEŁNIENIA]** (np. liczba użytkowników, oszczędność czasu, zgłoszenia) | **[DO UZUPEŁNIENIA]** |

---

## 9. Wydania

Wersje 0.x są **publicznie dostępne na GitHubie**, ale nie są rekomendowane do wdrożeń
produkcyjnych. Służą rozwojowi w środowisku autora i testom (studenci, niezależni testerzy).
Pierwsza wersja rekomendowana do wdrożeń produkcyjnych: **1.0.0**.

| Wersja | Co dostaje użytkownik (tester) |
| --- | --- |
| **0.1** | pojedyncze operacje z CLI i Pythona, dopytywanie, plan z potwierdzeniem, praca krok po kroku, diagnostyka środowiska; model lokalnie lub na serwerze jednostki; dziennik projektu i ślad audytowy |
| 0.2 | łańcuchy operacji, opisy wyników po polsku, wszystkie narzędzia |
| 0.3 | dostęp przez MCP (np. z innych asystentów AI) |
| 0.4 | dostęp do Retmana przez API HTTP (np. dla aplikacji webowej i GUI) |
| 0.5+ | **ścieżka prosta**: okno czatu, skrypt instalacyjny, kreator konfiguracji i `retman add-tool` (Windows, Linux, macOS); współpraca z GUI narzędzi; polecenia po angielsku |
| **1.0.0** | **pierwsza wersja do wdrożeń produkcyjnych** — niezawodny produkt dla administracji i projektantów |

---

## 10. Założenia i ryzyka

**Szkic do przeglądu.**

| Ryzyko | Skutek | Ograniczenie |
| --- | --- | --- |
| basal (model domyślny) to młody projekt jednej osoby | brak rozwoju lub wsparcia modelu | model wymienny (N-02); backend dla modeli generatywnych gotowy od v0.1 jako alternatywa |
| modele generatywne (np. przez LM Studio lub API dostawcy) często nie podają skalibrowanej pewności | trudniej rozpoznać, kiedy dopytać | domyślnie pewność z prawdopodobieństw tokenów (`logprobs`), a gdy serwer ich nie zwraca — ze zgodności kilku odpowiedzi (ARCHITECTURE p. 3.3.3); obowiązkowe potwierdzenie planu (W-05); testy jakości osobno dla każdego rodzaju modelu |
| model zewnętrznego dostawcy | treść poleceń opuszcza komputer lub sieć jednostki | konfiguracja należy do użytkownika, a `retman doctor` pokazuje adres każdego modelu (N-04); droga domyślna to własne zasoby |
| nieznana trafność małego modelu na słownictwie hydrologicznym | dużo dopytywania albo błędy | zbiór testowy od pierwszego dnia, synonimy w opisach, możliwość większego modelu |
| słaby sprzęt użytkowników | Retman za wolny lub nie do uruchomienia | najmniejszy model, diagnostyka, model na serwerze jednostki (od 0.1, p. 3.3) |
| utrzymanie zgodności z pięcioma narzędziami | Retman psuje się po zmianach w narzędziach | testy na wersjach narzędzi i kontrola rozjazdów w CI |
| brak części GUI | integracja z GUI odłożona | plan jako dane od v0.1, decyzja o integracji później |
| laptopy biurowe bez GPU w urzędach i na uczelniach | użytkownicy nie uruchomią modelu lokalnie | serwer jednostki w sieci wewnętrznej (p. 3.3) |
| instalacja z kompilacją po stronie użytkownika | użytkownik utknie na instalacji | model poza pakietem Retmana (N-10); zależności narzędzi sprawdza test instalacji na czystych systemach w CI (N-09) |
| brak informacji zwrotnej od grup docelowych przed 1.0 | produkt dopracowany pod autora, a nie pod administrację i projektantów | testerzy wersji 0.x; **[DO UZUPEŁNIENIA]** czy i jak pokazać Retmana administracji przed 1.0 |

**Założenia:**
- Użytkownicy znają hydrologię i metody, z których korzystają; Retman nie uczy hydrologii.
- Użytkownicy ścieżki prostej nie znają Pythona ani wiersza poleceń.

---

## 11. Otwarte kwestie produktowe

1. Problem, który Retman rozwiązuje, opisany z perspektywy administracji i projektantów (rozdz. 1).
2. Oczekiwania i bariery poszczególnych grup (p. 3.4).
3. Czy i jak pokazać Retmana grupom docelowym przed 1.0 (rozdz. 10).
4. Lista pierwszych operacji (p. 7.2) — operacje Kartografa ustalone (ADR-001); brak operacji drugiego narzędzia.
5. Wartości docelowe: czas odpowiedzi, miary jakości i sukcesu (rozdz. 5, 6 i 8).
6. Współpraca z GUI — decyzja, gdy GUI powstaną.
7. Scenariusze charakterystyczne dla głównych grup użytkowników (rozdz. 4).
8. Formaty plików wynikowych (W-09; strona techniczna: ARCHITECTURE rozdz. 12, pkt 7) — dla Kartografa: ADR-004.
