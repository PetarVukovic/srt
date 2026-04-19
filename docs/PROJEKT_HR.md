# Dokumentacija Projekta

## 1. Sažetak

Ovaj projekt je FastAPI servis za obradu i prijevod subtitle fileova u `.srt` formatu.

Glavni cilj servisa je:

- prihvatiti jedan ili više `.srt` fileova
- automatski očistiti i spojiti kratke subtitle segmente
- poslati subtitle sadržaj na Gemini Batch API
- spremiti prevedene rezultate u izlazne foldere po jezicima

Projekt je pojednostavljen tako da koristi isključivo Gemini Batch API. OpenAI batch sloj je uklonjen.

## 2. Struktura Projekta

### `app/main.py`

Glavni ulaz u FastAPI aplikaciju.

Odgovoran je za:

- kreiranje aplikacije
- uključivanje routera
- osnovnu konfiguraciju CORS-a
- startup i shutdown log poruke

### `app/core/config.py`

Centralno mjesto za konfiguraciju.

Najvažnije postavke:

- `gemini_api_key`
- `gemini_model`
- `gemini_temperature`
- `gemini_thinking_level`
- `batch_size`
- `max_batch_files`
- `max_concurrent_files`

Ovdje se također definiraju:

- ulazni folder za uploadane `.srt` fileove
- izlazni folder za prevedene fileove
- temp folder za Gemini JSONL batch ulaze
- reports folder za lokalne CSV izvještaje
- default lista ciljanih jezika

### `app/routers/health.py`

Jednostavni status endpointi:

- `GET /`
- `GET /health`

Koriste se za:

- provjeru je li servis živ
- provjeru osnovne konfiguracije
- brz uvid u aktivni Gemini model i limite

### `app/routers/translate.py`

Glavni API sloj za prijevod.

Sadrži dva endpointa:

- `POST /batch/translate/srt`
- `POST /batch/translate/multiple`

Router radi sljedeće:

- validira broj fileova
- validira da su fileovi `.srt`
- sprema fileove na disk
- kreira job konfiguracije
- šalje background taskove za Gemini obradu
- po završetku čisti privremene fileove

Najvažnije helper funkcije u routeru:

- `parse_languages`
- `ensure_runtime_directories`
- `get_translation_service`
- `validate_files_count`
- `save_uploaded_srt_files`

Time je izbjegnuto dupliciranje logike između single i multi endpointa.

### `app/services/srt_merge_preprocessor.py`

Ovo je preprocess sloj za `.srt` fileove.

Nastao je iz tvoje Streamlit merge logike, ali je prebačen u backend servis.

Radi sljedeće:

- normalizira line endinge
- popravlja loše timestampove
- sprječava preklapanje subtitle vremena
- parsira segmente
- spaja kratke i bliske susjedne segmente
- validira segmente
- ponovno zapisuje očišćeni `.srt`

Ovo je važan korak jer Gemini dobiva uredniji i stabilniji ulaz.

### `app/services/gemini/gemini_batch_builder.py`

Ovaj sloj pretvara `.srt` sadržaj u Gemini Batch JSONL format.

Odgovoran je za:

- čitanje `.srt` filea
- detekciju encodinga
- rezanje subtitleova u chunkove
- generiranje jednog JSONL requesta po jeziku i chunku

Svaki request sadrži:

- user prompt za strogi subtitle prijevod
- `response_mime_type=application/json`
- `response_schema`
- `temperature`
- `thinking_config.thinking_level`

### `app/services/gemini/gemini_batch_client.py`

Klijent za komunikaciju s Gemini API-jem.

Odgovoran je za:

- upload JSONL filea na Gemini File API
- kreiranje batch joba
- polling statusa
- preuzimanje rezultata
- eventualno otkazivanje ili brisanje batch joba

### `app/services/gemini/gemini_batch_result_parser.py`

Parser batch rezultata.

Radi sljedeće:

- čita batch output JSONL
- grupira rezultate po jeziku
- sigurno parsira JSON koji vrati Gemini
- validira pokrivenost subtitleova
- primjenjuje prijevod na originalni `.srt`

Važna zaštita:

- nepotpuni prijevodi se ne spremaju kao finalni output

### `app/services/gemini/gemini_batch_translation_service.py`

Orkestrator cijelog poslovnog toka.

Tok rada:

1. preprocess `.srt` filea
2. batch JSONL build
3. upload na Gemini
4. create batch job
5. čekanje završetka
6. download rezultata
7. parsiranje po jezicima
8. validacija pokrivenosti
9. spremanje prevedenih `.srt` fileova
10. izračun cijene
11. spremanje lokalnog CSV izvještaja za request i globalni history CSV

Također podržava i više fileova paralelno preko `translate_multiple_files`.

### `app/services/local_report_store.py`

Lokalni persistence sloj za CSV izvještaje.

Radi sljedeće:

- sprema CSV po requestu
- vodi agregirani `translation_history.csv`
- zapisuje status po jeziku
- zapisuje tokene i procijenjenu cijenu requesta

## 3. Trenutni API tok

### `POST /batch/translate/srt`

Namjena:

- jedan ili više `.srt` fileova
- jednostavan scheduling

Ulaz:

- `files` kao multipart upload
- opcionalno `languages`
- opcionalno `folder_id`

Izlaz:

- status da su jobovi prihvaćeni
- lista prihvaćenih i odbijenih fileova
- broj jezika

### `POST /batch/translate/multiple`

Namjena:

- više fileova odjednom
- kontrolirani concurrency

Ulaz:

- `files`
- `languages`
- `folder_id`
- `max_concurrent`

Izlaz:

- status prihvata
- processing mode
- broj fileova
- konfigurirani concurrency

## 4. Konfiguracija preko `.env`

Primjer:

```env
GEMINI_API_KEY=your_gemini_api_key
DEPLOYMENT=local
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_TEMPERATURE=1.0
GEMINI_THINKING_LEVEL=low
```

Napomena:

- trenutno `gemini_temperature` i `gemini_thinking_level` imaju default vrijednosti u kodu
- ako želiš, lako ih kasnije možemo pretvoriti u eksplicitne env varijable s aliasima

## 5. Spremanje rezultata

Ulazni fileovi:

- lokalno: `./app/srt_input`
- produkcija: `/opt/render/project/src/app/srt_input`

Batch JSONL:

- lokalno: `./app/batch_inputs`
- produkcija: `/opt/render/project/src/app/batch_inputs`

Izlazni prijevodi:

- lokalno: `./app/batch_output/<folder_id ili default>/<language>/<filename>.srt`
- produkcija: `/opt/render/project/src/app/batch_output/<folder_id ili default>/<language>/<filename>.srt`

CSV izvještaji:

- lokalno: `./app/reports`
- produkcija: `/opt/render/project/src/app/reports`

Per-request CSV:

- `./app/reports/<folder_id ili default>/<base_name>_<timestamp>.csv`

Globalni history CSV:

- `./app/reports/translation_history.csv`

## 6. Gemini model i pricing

Trenutni default:

- `gemini-3-flash-preview`

Trenutni obračun batch cijene:

- input: `$0.25 / 1,000,000` tokena
- output: `$1.50 / 1,000,000` tokena

Pricing se računa u `gemini_batch_translation_service.py`.

## 7. Što je pojednostavljeno

U odnosu na prijašnje stanje:

- projekt više ne koristi OpenAI batch sloj
- projekt više ne koristi `n8n` ni webhook slanje
- router više nema provider grananja
- health endpoint sad pokazuje stvarnu konfiguraciju
- duplirani kod u translate routeru je izvučen u helper funkcije
- merge logika iz vanjske Streamlit skripte je prebačena u interni servis
- rezultati i potrošnja spremaju se lokalno u CSV
- dokumentacija je usklađena sa stvarnim stanjem projekta

## 8. Preporučeni sljedeći koraci

- dodati Pydantic response modele za API odgovore
- dodati persistent storage za job status umjesto samo background taskova
- dodati testove za:
  - merge preprocess
  - batch builder
  - batch result parser
  - translate router helper funkcije
- dodati opcionalno gašenje preprocess merge koraka preko konfiguracije
