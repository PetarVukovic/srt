# Postman Testiranje

U folderu `postman/` nalaze se pripremljeni artefakti za testiranje API-ja:

- `SRT Translation Service.postman_collection.json`
- `SRT Translation Service.local.postman_environment.json`

## 1. Import u Postman

1. Otvori Postman
2. Klikni `Import`
3. Uvezi kolekciju i environment iz foldera `postman/`
4. Aktiviraj environment `SRT Translation Service Local`

## 2. Environment varijable

Najvažnije varijable:

- `base_url`
- `folder_id`
- `max_concurrent`
- `languages_default`

Primjer:

- `base_url = http://127.0.0.1:8000`
- `folder_id = demo-folder-001`
- `max_concurrent = 3`

## 3. Endpointi u kolekciji

### `GET /`

Provjerava:

- je li servis aktivan
- koji endpointi postoje
- koji je model aktivan
- jesu li ključne postavke učitane

### `GET /health`

Najjednostavniji health check.

### `POST /batch/translate/srt`

Koristi se za:

- jedan file
- više fileova bez ručne kontrole concurrencyja

Body tip:

- `form-data`

Polja:

- `files` -> File
- `languages` -> Text
- `folder_id` -> Text

Ako želiš testirati više fileova, dodaj više `files` polja istog imena.

### `POST /batch/translate/multiple`

Koristi se za:

- više fileova
- kontrolu `max_concurrent`

Body tip:

- `form-data`

Polja:

- `files` -> File
- `languages` -> Text
- `folder_id` -> Text
- `max_concurrent` -> Text

## 4. Primjeri test scenarija

### Scenarij A: Health provjera

1. Pokreni servis
2. Pošalji `GET /health`
3. Očekuj status `healthy`

### Scenarij B: Jedan `.srt` file, default jezici

1. Otvori request `POST /batch/translate/srt`
2. U `files` odaberi jedan `.srt`
3. Ostavi `languages` prazno
4. Pošalji request

Očekivano:

- `status = accepted`
- `provider = gemini`
- `languages_count = 33`

### Scenarij C: Jedan `.srt` file, ručno zadani jezici

Primjer vrijednosti za `languages`:

```text
English,German,French,Croatian
```

Očekivano:

- `languages_count = 4`
- `languages` sadrži točno ta 4 jezika

### Scenarij D: Više `.srt` fileova s concurrencyjem

1. Otvori `POST /batch/translate/multiple`
2. Dodaj 2-5 `.srt` fileova
3. Postavi `max_concurrent = 2`
4. Pošalji request

Očekivano:

- `processing_mode = concurrent`
- `max_concurrent = 2`

### Scenarij E: Pogrešan file tip

1. Pošalji `.txt` ili neki drugi file
2. Očekuj da u odgovoru bude upisan u `failed_files`

## 5. Važna napomena za file upload

Za ova dva endpointa nije praktično koristiti `raw JSON`, jer oba endpointa očekuju `multipart/form-data` upload fileova.

Zato su requestovi u Postman kolekciji složeni kao `form-data`.

## 6. Primjeri očekivanih odgovora

### `GET /health`

```json
{
  "status": "healthy",
  "timestamp": 1712345678.123
}
```

### `POST /batch/translate/srt`

```json
{
  "status": "accepted",
  "provider": "gemini",
  "files_count": 1,
  "max_files": 20,
  "accepted_files": [
    "demo.srt"
  ],
  "failed_files": [],
  "languages_count": 4,
  "languages": [
    "English",
    "German",
    "French",
    "Croatian"
  ],
  "message": "Scheduled 1 translation jobs"
}
```

### `POST /batch/translate/multiple`

```json
{
  "status": "accepted",
  "provider": "gemini",
  "processing_mode": "concurrent",
  "files_count": 2,
  "max_files": 20,
  "accepted_files": [
    "episode1.srt",
    "episode2.srt"
  ],
  "failed_files": [],
  "languages_count": 3,
  "languages": [
    "English",
    "German",
    "French"
  ],
  "max_concurrent": 2,
  "message": "Scheduled 2 files for concurrent translation"
}
```

## 7. Gdje gledati rezultate

Prevedeni fileovi se spremaju u:

```text
app/batch_output/<folder_id ili default>/<language>/<original_filename>.srt
```

Primjer:

```text
app/batch_output/demo-folder-001/English/demo.srt
app/batch_output/demo-folder-001/German/demo.srt
app/batch_output/demo-folder-001/French/demo.srt
```

CSV izvještaji se spremaju u:

```text
app/reports/<folder_id ili default>/<base_name>_<timestamp>.csv
app/reports/translation_history.csv
```
