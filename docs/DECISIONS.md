# Rejestr decyzji — Retman

Każda decyzja architektoniczna lub projektowa jest udokumentowana poniżej.
Format: numer, data, kontekst (dlaczego temat powstał), rozważone opcje, decyzja, konsekwencje.

Treść decyzji opisuje stan w chwili jej podjęcia i nie jest modernizowana.
Późniejsze zmiany faktów i ustalenia dodatkowe są dopisywane na końcu wpisu
jako erraty `**Errata N (RRRR-MM-DD, źródło/powód):**`, numerowane w obrębie
ADR chronologicznie. Szablon nowego wpisu: [Szablon nowego ADR](#szablon-nowego-adr).

**Słownik statusów** (linia `**Status:**` każdego wpisu):
- `Przyjęta` — decyzja obowiązuje w całości;
- `Przyjęta — częściowo zastąpiona przez ADR-x (zakres)` — wskazana część nie obowiązuje;
- `Przyjęta — uzupełniona przez ADR-x (zakres)` — obowiązuje, późniejsza decyzja ją rozszerza;
- `Zastąpiona przez ADR-x` — nie obowiązuje;
- `Odrzucona` — rozważona i nieprzyjęta.

Po średniku status może podać relacje odwrotne (`zastępuje ...`, `uzupełnia ...`);
każda relacja jest zapisana po obu stronach.

## Indeks

| ADR | Tytuł | Data | Status |
|---|---|---|---|

---

## Szablon nowego ADR

Kopiuj poniższy blok przy dodawaniu decyzji: kolejny numer, status ze
słownika na początku pliku, nowy wiersz w indeksie i odsyłacze po obu
stronach relacji. Wpisy dodawaj nad tą sekcją, oddzielone `---`.
Erraty dopisuj na końcu wpisu.

```markdown
## ADR-XXX: Tytuł

**Data:** RRRR-MM-DD
**Status:** Przyjęta | Przyjęta — częściowo zastąpiona przez ADR-YYY (zakres) | Przyjęta — uzupełniona przez ADR-YYY (zakres) | Zastąpiona przez ADR-YYY | Odrzucona

**Kontekst:** Dlaczego temat powstał.

**Opcje:**
- A) ...
- B) ...

**Decyzja:** Która opcja i dlaczego.

**Konsekwencje:** Co z tego wynika (w tym zmiany w PRD.md / ARCHITECTURE.md).

**Errata 1 (RRRR-MM-DD, źródło/powód):** Dopisywane później.
```
