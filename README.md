# polish-dataset-translator

Produkcyjny pipeline do tłumaczenia datasetów z angielskiego na polski. Pierwszym adapterem jest BFCL (Berkeley Function Calling Leaderboard), którego dane są wieloma plikami JSONL, a nie standardowym datasetem kompatybilnym z `datasets.load_dataset`.

## Zakres BFCL

Adapter obsługuje rekordy single-turn, multi-turn, live, agentic (`web_search`, `memory`) i `format_sensitivity`. Rozpoznaje kategorię z `id` oraz nazwy pliku. Tłumaczy tylko `question` i jawnie natural-language opisy w `function`; chroni nazwy, klucze, typy JSON Schema, enumy, URL-e, kod, `initial_config`, `ground_truth` i `possible_answer`. Dla multi-turn zachowuje role i strukturę wiadomości. Kategorie `web_search` i `memory` są traktowane jako wrażliwe: tekst scenariusza jest tłumaczony, ale konfiguracja narzędzia, stan i wartości wykonywalne nie.

Stan BFCL został zweryfikowany względem repozytorium Gorilla i karty HF: dane są JSONL per kategoria, aktualne grupy obejmują `single_turn`, `multi_turn`, `live`, `memory`, `web_search` i `format_sensitivity`, licencja datasetu to Apache-2.0. Oficjalny evaluator instaluje się jako `bfcl-eval` i korzysta z własnych plików danych; ten projekt nie używa `load_dataset`.

## Uruchomienie

Wymagany jest Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
az login
```

```powershell
polish-dataset-translator translate --input data\raw --output data\translated\bfcl.jsonl --report reports\bfcl.json
```

Domyślnie pipeline wysyła `20` tekstów w jednym requestcie. Możesz zmienić rozmiar paczki:

```powershell
polish-dataset-translator translate --input data\raw --output data\translated\bfcl.jsonl --report reports\bfcl.json --batch-size 20
```

Pobranie danych BFCL bez `load_dataset`:

```powershell
polish-dataset-translator download --output data\raw
```

Pipeline przyjmuje plik lub katalog. Wznawianie działa przez plik `<output>.checkpoint.json`; rekordy zakończone poprawnie są pomijane na podstawie ID i fingerprintu wejścia.

## Azure Foundry

Provider używa OpenAI SDK z endpointem Azure Foundry i `DefaultAzureCredential`, więc lokalnie działa przez `az login`, a w środowisku produkcyjnym przez managed identity. Model zwraca wyłącznie JSON `{ "translations": ["..."] }`; każdy request zawiera jeden fragment naturalnego języka, bez ground truth i schematów.

## Walidacja i raporty

Pipeline sprawdza niezmienność pól technicznych, ID, struktury wiadomości, JSON Schema oraz ground truth. Raport zawiera rekordy przetworzone, pominięte, błędne i wymagające ręcznego przeglądu. `bfcl-eval` można doinstalować przez `python -m pip install -e ".[bfcl]"` i uruchomić smoke test na wybranych kategoriach.
