from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import time
import asyncio
import httpx
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

# ------------- CONFIG -------------
# koliko paralelnih prijevoda dozvoliti po API ključu (fine-tunaj po potrebi)
MAX_CONCURRENCY_PER_KEY = 3
# max workers za cijeli proces pool (mrežno vezano pa ne treba preveliko)
MAX_WORKERS = max(4, (os.cpu_count() or 4))

# umjesto: PROCESS_POOL = ProcessPoolExecutor(max_workers=MAX_WORKERS)
PROCESS_POOL = ProcessPoolExecutor(
    max_workers=MAX_WORKERS, mp_context=mp.get_context("spawn")
)

# ------------- APP SETUP ----------
load_dotenv()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INPUT_FOLDER = "srt-files"
OUTPUT_FOLDER = "srt-prijevodi"
os.makedirs(INPUT_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL")

target_languages = [
    "English",
    "Mandarin Chinese",
    "Hindi",
    "Spanish",
    "Arabic",
    "Bengali",
    "Portuguese",
    "Russian",
    "Urdu",
    "Indonesian",
    "Standard German",
    "Japanese",
    "Swahili",
    "Marathi",
    "Telugu",
    "Turkish",
    "French",
    "Vietnamese",
    "Korean",
    "Tamil",
    "Yue Chinese (Cantonese)",
    "Italian",
    "Thai",
    "Gujarati",
    "Javanese",
    "Polish",
    "Western Punjabi",
    "Ukrainian",
    "Persian (Farsi)",
    "Malayalam",
    "Slovenian",
    "Serbian (on Српски!)",
    "Macedonian (on Македонски!)",
]
# --- Učitaj tri API ključa (obavezno) ---
API_KEYS = [
    os.environ.get("GOOGLE_API_KEY"),
    os.environ.get("GOOGLE_API_KEY2"),
    os.environ.get("GOOGLE_API_KEY3"),
]
if not all(API_KEYS):
    raise RuntimeError(
        "Nedostaju ključevi: GOOGLE_API_KEY, GOOGLE_API_KEY2, GOOGLE_API_KEY3."
    )


# --- Raspodjela jezika na 3 ključa (ravnomjerno) ---
def split_languages_equally(langs, n_buckets=3):
    total = len(langs)
    per_bucket_base = total // n_buckets
    buckets_with_extra = total % n_buckets
    buckets = []
    start = 0
    for i in range(n_buckets):
        size = per_bucket_base + (1 if i < buckets_with_extra else 0)
        buckets.append(langs[start : start + size])
        start += size
    return buckets


LANG_BUCKETS = split_languages_equally(target_languages, 3)
LANG_TO_KEY = {
    lang: API_KEYS[i] for i, bucket in enumerate(LANG_BUCKETS) for lang in bucket
}
KEY_INDEX = {k: i for i, k in enumerate(API_KEYS)}

# --- Semafori po ključu za rate-limit friendly concurrency ---
KEY_SEMAPHORES = [asyncio.Semaphore(MAX_CONCURRENCY_PER_KEY) for _ in API_KEYS]


# ============== WORKER (u posebnom procesu) ==============
def translate_worker(
    input_path: str,
    output_path: str,
    language: str,
    api_key: str,
    free_quota: bool = True,
):
    """
    Ovaj se kod izvršava u zasebnom procesu. Namjerno importamo modul ovdje
    kako bi globalne varijable bile izolirane per-proces.
    """
    import gemini_srt_translator as gst  # izolirano unutar child procesa

    gst.gemini_api_key = api_key
    gst.target_language = language
    gst.input_file = input_path
    gst.output_file = output_path
    gst.free_quota = free_quota
    start = time.time()
    gst.translate()
    return round(time.time() - start)


# ============== CORE ASYNC LOGIKA ==============
async def translate_one_language(
    client: httpx.AsyncClient,
    input_path: str,
    base_name: str,
    folder_id: str,
    language: str,
):
    api_key = LANG_TO_KEY[language]
    key_idx = KEY_INDEX[api_key]
    sem = KEY_SEMAPHORES[key_idx]

    output_filename = f"{language}__{base_name}.srt"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    async with sem:  # ograniči broj paralelnih poziva po ključu
        print(f"▶️ Start: {language} | KEY #{key_idx+1}")
        loop = asyncio.get_running_loop()
        # pozovi CPU/mrežni blokirajući kod u zasebnom procesu
        try:
            duration_sec = await loop.run_in_executor(
                PROCESS_POOL,
                translate_worker,
                input_path,
                output_path,
                language,
                api_key,
                True,
            )
            print(f"✅ Gotovo: {language} za {duration_sec}s | KEY #{key_idx+1}")
        except Exception as e:
            print(f"❌ Greška u prijevodu {language}: {e}")
            return {"language": language, "status": "translate_error", "error": str(e)}

    # Pošalji na n8n i obriši file
    try:
        # čitanje sync je ok (mali SRT u odnosu na mrežu); po želji zamijeni s aiofiles
        with open(output_path, "r", encoding="utf-8", errors="replace") as f:
            translated_content = f.read()

        resp = await client.post(
            N8N_WEBHOOK_URL,
            json={
                "language": language,
                "filename": output_filename,
                "folder_id": folder_id,
                "content": translated_content,
            },
            timeout=60,
        )
        print(f"📤 Webhook {language}: {resp.status_code}")
        try:
            os.remove(output_path)
        except OSError:
            pass
        return {"language": language, "status": "ok", "code": resp.status_code}
    except Exception as e:
        print(f"❌ Greška slanja na webhook za {language}: {e}")
        return {"language": language, "status": "webhook_error", "error": str(e)}


async def process_translations_in_background(
    input_path: str, base_name: str, folder_id: str
):
    """
    Maks asinkrono:
    - paralelizacija po jezicima
    - ograničenje po API ključu (semafori)
    - izolacija globalnih varijabli preko ProcessPoolExecutor-a
    - thread-safe i multi-request safe
    """
    async with httpx.AsyncClient() as client:
        tasks = [
            translate_one_language(client, input_path, base_name, folder_id, lang)
            for lang in target_languages
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    # Log summary + čišćenje inputa
    failed = [r for r in results if r.get("status") != "ok"]
    if failed:
        print("⚠️ Neuspjeli:", failed)
    try:
        os.remove(input_path)
        print(f"🗑️ Obrisana ulazna datoteka: {input_path}")
    except OSError as e:
        print(f"❌ Greška pri brisanju ulazne datoteke {input_path}: {e}")


# ============== ENDPOINT ==============
@app.post("/translate-srt/")
async def translate_srt(
    background_tasks: BackgroundTasks,
    folder_id: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        input_path = os.path.join(INPUT_FOLDER, file.filename)
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        base_name = os.path.splitext(file.filename)[0]

        # svaki HTTP request dobiva vlastiti set async taskova;
        # dijele globalni pool + semafore -> sigurno za multiple requests
        background_tasks.add_task(
            process_translations_in_background, input_path, base_name, folder_id
        )

        return JSONResponse(
            status_code=202,
            content={
                "message": "✅ Zahtjev primljen. Prevođenje je pokrenuto u pozadini.",
                "filename": file.filename,
                "folder_id": folder_id,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"❌ Greška pri pokretanju procesa: {e}"},
        )
