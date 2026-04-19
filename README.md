# SRT Translation Service

Servis za obradu i prijevod `.srt` titlova pomoću Gemini Batch API-ja.

Projekt radi tri glavne stvari:

1. prima jedan ili više `.srt` fileova preko FastAPI-ja
2. prije slanja na Gemini automatski popravi loše timestampove i spoji kratke segmente
3. po završetku batch obrade spremi prevedene `.srt` fileove po jezicima

Detaljna dokumentacija nalazi se u:

- [docs/PROJEKT_HR.md](docs/PROJEKT_HR.md)
- [docs/POSTMAN_HR.md](docs/POSTMAN_HR.md)

## Brzi start

1. Napravi virtualno okruženje i instaliraj ovisnosti:

```bash
python3 -m venv srt-venv
./srt-venv/bin/pip install -r requirements.txt
```

2. Kreiraj `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
DEPLOYMENT=local
GEMINI_MODEL=gemini-3-flash-preview
```

3. Pokreni API:

```bash
./srt-venv/bin/uvicorn app.main:app --reload
```

4. Otvori:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

## Glavni endpointi

- `GET /`
- `GET /health`
- `POST /batch/translate/srt`
- `POST /batch/translate/multiple`

## Postman

U folderu `postman/` nalaze se:

- `SRT Translation Service.postman_collection.json`
- `SRT Translation Service.local.postman_environment.json`

## Napomena

Ovaj servis koristi Gemini Batch API, što znači da obrada nije trenutna. Batch poslovi tipično završe brzo, ali službeni cilj sustava je do 24 sata, ovisno o opterećenju i veličini batcha.

## Lokalni rezultati i izvještaji

Prijevodi se spremaju lokalno u:

```text
app/batch_output/<folder_id ili default>/<language>/<filename>.srt
```

CSV izvještaji o potrošnji i rezultatima spremaju se lokalno u:

```text
app/reports/<folder_id ili default>/
app/reports/translation_history.csv
```
