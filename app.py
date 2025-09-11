from anyio import sleep
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import gemini_srt_translator as gst
import httpx
from dotenv import load_dotenv
import time
import asyncio

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
]

# --- Učitaj tri API ključa ---
API_KEYS = [
    os.environ.get("GOOGLE_API_KEY"),
    os.environ.get("GOOGLE_API_KEY2"),
    os.environ.get("GOOGLE_API_KEY3"),
]

if not all(API_KEYS):
    raise RuntimeError(
        "Nedostaju jedan ili više ključevа: GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, GOOGLE_API_KEY_3."
    )


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


LANG_BUCKETS = split_languages_equally(target_languages, n_buckets=3)
LANG_TO_KEY = {
    lang: API_KEYS[i] for i, bucket in enumerate(LANG_BUCKETS) for lang in bucket
}


# --- Background Task ---
async def process_translations_in_background(
    input_path: str, base_name: str, folder_id: str
):
    failed_languages = []
    async with httpx.AsyncClient() as client:
        for language in target_languages:
            gst.gemini_api_key = LANG_TO_KEY[language]
            gst.target_language = language
            gst.input_file = input_path
            output_filename = f"{language}__{base_name}.srt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            gst.output_file = output_path
            gst.free_quota = True

            print(
                f"Prevodim: {language}  |  API ključ: {API_KEYS.index(gst.gemini_api_key)+1}"
            )

            try:
                gst.translate()
                print(f"✔️ {language} završeno.")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"❌ Greška u prijevodu {language}: {e}")
                failed_languages.append(language)
                continue

            try:
                with open(
                    output_path, "r", encoding="utf-8", errors="replace"
                ) as translated_file:
                    translated_content = translated_file.read()

                response = await client.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "language": language,
                        "filename": output_filename,
                        "folder_id": folder_id,
                        "content": translated_content,
                    },
                    timeout=30,
                )
                print(f"📤 Poslano na n8n za {language}: {response.status_code}")
                os.remove(output_path)
            except Exception as e:
                print(f"❌ Greška slanja na webhook za {language}: {e}")
                failed_languages.append(language)

    if failed_languages:
        print(f"⚠️ Neuspjeli prijevodi: {', '.join(failed_languages)}")

    try:
        os.remove(input_path)
        print(f"🗑️ Obrisana ulazna datoteka: {input_path}")
    except OSError as e:
        print(f"❌ Greška pri brisanju ulazne datoteke {input_path}: {e}")


# --- Endpoint ---
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

        background_tasks.add_task(
            process_translations_in_background, input_path, base_name, folder_id
        )

        return JSONResponse(
            status_code=202,
            content={
                "message": "✅ Zahtjev primljen. Prevođenje je započelo u pozadini.",
                "filename": file.filename,
                "folder_id": folder_id,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"❌ Greška pri pokretanju procesa: {e}"},
        )
