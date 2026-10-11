# LM Studio i API zgodne z OpenAI — sprawdzenie 2026-10-11

## Cel i metoda

Sprawdzono otwartą kwestię z `docs/ARCHITECTURE.md` rozdz. 12 pkt 9 na serwerze LM Studio w sieci lokalnej. Wywołano `GET /v1/models` oraz `POST /v1/chat/completions` dla polecenia „Pobierz NMT dla arkusza N-34-130-D-d-2-4” i trzech opcji A/B/C. Sprawdzono cztery warianty: `response_format` z `json_schema` i enumeracją odpowiedzi, `logprobs: true` z `top_logprobs: 3`, oba naraz oraz odpowiedź bez obu parametrów. Czas oznacza czas odpowiedzi HTTP, nie pomiar jakości klasyfikacji. Surowe odpowiedzi JSON znajdują się w `tests/fixtures/openai_compatible/`; pliki nie zawierają adresu serwera.

`GET /v1/models` zakończyło się HTTP 200 w 0,14 s. Na liście były `qwen/qwen3.6-35b-a3b`, `bielik-11b-v3.0-instruct-mlx` i `bielik-4.5b-v3.0-instruct-mlx` (oraz model embeddingowy). Obecność na liście nie oznacza, że model da się załadować.

| Model | Format: obiekt `{"key": enum}` | Same `logprobs` | Obiekt + `logprobs` | Bez wymuszania |
| --- | --- | --- | --- | --- |
| Bielik 11B | HTTP 200, 4,11 s, `{"key": "A"}` | HTTP 200, 1,76 s, odpowiedź `A` i rozkład A/B/C | HTTP 200, 2,31 s, **błędny JSON** `{"ke": "A"}` (pierwsza próba: poprawny JSON, 2,05 s) | HTTP 200, 0,42 s, `A` |
| Bielik 4.5B | HTTP 200, 0,83 s, `{"key": "C"}` | HTTP 200, 0,19 s, odpowiedź `B` i rozkład A/B/C | HTTP 200, 1,77 s, **błędny JSON** `"k": "C}` (pierwsza próba również błędna, 1,70 s) | HTTP 200, 0,21 s, `B` |
| Qwen 3.6 35B | HTTP 400, 0,04 s | HTTP 400, 0,01 s | HTTP 400, 0,01 s | HTTP 400, 0,01 s |

Dla Qwena LM Studio odrzuciło ładowanie modelu z powodu niewystarczających zasobów systemowych (zabezpieczenie przed przeciążeniem). Qwen **nie został uruchomiony ani przetestowany**; nie można stwierdzić, czy zwraca `logprobs`, czy obsługuje enumeracje ani jak formatuje treść rozumowania. Nie zmieniano stanu serwera ani nie wyłączano załadowanych modeli. Odpowiedź błędu zachowano jako fixturę `qwen_unavailable_schema.json`; analogiczny błąd wystąpił dla wszystkich czterech wariantów.

## Dokładniejsza próba enumeracji

Dla Bielików sprawdzono również prostszy schemat `{"type": "string", "enum": ["A", "B", "C"]}` zamiast obiektu z polem `key`. Jest przydatniejszy do odczytu pewności: każda litera jest pojedynczym tokenem, a w `top_logprobs` znajdują się alternatywy A/B/C dla tego tokenu. Ponowny pomiar:

| Model | Enumeracja liter | Enumeracja liter + `logprobs` |
| --- | --- | --- |
| Bielik 11B | HTTP 200, 1,73 s, `"A"` | HTTP 200, 1,67 s, `A` i wartości dla A/B/C |
| Bielik 4.5B | HTTP 200, 0,45 s, `"B"` | HTTP 200, 1,36 s, `B` i wartości dla A/B/C |

Zarówno odpowiedź będąca pojedynczą literą, jak i jej reprezentacja jako łańcucha JSON w cudzysłowie, oznaczają ten sam klucz; backend rozpoznaje tylko te dwa warianty i odrzuca pozostałe. Sam status HTTP 200 **nie gwarantuje**, że struktura odpowiedzi odpowiada deklarowanemu schematowi: wariant obiektowy po połączeniu ze statystykami tokenów wykazał błędy formatu. W odpowiedziach Bielików `reasoning_content` było puste; Qwena nie zbadano. Dla liter A/B/C otrzymano rzeczywiste `top_logprobs`, więc backend może obliczyć względne udziały przez normalizację `exp(logprob)` po opcjach. To nie są prawdopodobieństwa skalibrowane; przy brakujących danych należy użyć zgodności kilku odpowiedzi lub zgłosić brak żądanej metody.

Zaimplementowany backend podaje opcje jako posortowane identyfikatory i opisy z przypisanymi literami; sortowanie utrzymuje przypisanie przy zmianie kolejności wejściowego słownika. Preferuje enumerację liter, a gdy serwer jawnie zgłosi brak obsługi `response_format`, przechodzi na zwykły tekst i nadal sprawdza, czy wynik jest dozwolonym kluczem. Wymuszona odpowiedź jest sprawdzana również przy HTTP 200, bez niejawnych ponowień błędnej decyzji.

Opcjonalny test na żywo (`tests/backends/test_openai_compatible_live.py`) dla Bielika 11B wykonał rzeczywistą decyzję z `logprobs` i przeszedł. Jego URL i nazwa modelu pochodzą wyłącznie z argumentów testu; adres serwera nie jest zapisywany w repozytorium. Test Qwena wymaga zasobów pozwalających na jego uruchomienie — samo udostępnienie identyfikatora przez `/models` nie wystarcza.
