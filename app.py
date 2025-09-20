from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import time
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any

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


# ============== SINHRONNI WORKER ==============
def translate_sync_worker(
    input_path: str,
    output_path: str,
    language: str,
    api_key: str,
    free_quota: bool = True,
) -> Dict[str, Any]:
    """
    Jednostavan sinhronni worker za prevođenje jednog jezika.
    """
    try:
        from gemini_srt_translator.main import GeminiSRTTranslator
        
        start_time = time.time()
        
        # Kreiraj translator instancu
        translator = GeminiSRTTranslator(
            gemini_api_key=api_key,
            target_language=language,
            input_file=input_path,
            output_file=output_path,
            free_quota=free_quota,
            use_colors=True,
            resume=True,
        )
        
        # Pokreni prevođenje
        translator.translate()
        
        duration = round(time.time() - start_time)
        
        return {
            "language": language,
            "status": "success",
            "duration": duration,
            "output_path": output_path
        }
    except Exception as e:
        return {
            "language": language,
            "status": "error",
            "error": str(e),
            "output_path": output_path
        }


# ============== SINHRONNI TRANSLATION LOGIKA ==============
def translate_one_language_sync(
    input_path: str,
    base_name: str,
    folder_id: str,
    language: str,
) -> Dict[str, Any]:
    """
    Sinhronno prevodi jedan jezik i šalje na webhook.
    """
    api_key = LANG_TO_KEY[language]
    key_idx = KEY_INDEX[api_key]

    output_filename = f"{language}__{base_name}.srt"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    print(f"▶️ Start: {language} | KEY #{key_idx+1}")
    
    # Prevedi sinhronno
    result = translate_sync_worker(input_path, output_path, language, api_key, True)
    
    if result["status"] == "error":
        print(f"❌ Greška u prijevodu {language}: {result['error']}")
        return result
    
    print(f"✅ Gotovo: {language} za {result['duration']}s | KEY #{key_idx+1}")

    # Pošalji na n8n webhook sinhronno
    try:
        with open(output_path, "r", encoding="utf-8", errors="replace") as f:
            translated_content = f.read()

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                N8N_WEBHOOK_URL,
                json={
                    "language": language,
                    "filename": output_filename,
                    "folder_id": folder_id,
                    "content": translated_content,
                },
            )
        
        print(f"📤 Webhook {language}: {resp.status_code}")
        
        # Obriši fajl nakon slanja
        try:
            os.remove(output_path)
        except OSError:
            pass
            
        return {
            "language": language, 
            "status": "ok", 
            "code": resp.status_code,
            "duration": result["duration"]
        }
        
    except Exception as e:
        print(f"❌ Greška slanja na webhook za {language}: {e}")
        return {
            "language": language, 
            "status": "webhook_error", 
            "error": str(e),
            "duration": result.get("duration", 0)
        }


def process_translations_sync(
    input_path: str, base_name: str, folder_id: str
):
    """
    Sinhronno procesiranje prevoda sa rotacijom ključeva.
    Koristi 3 ključa u rotaciji - svaki jezik se obrađuje sekvencijalno.
    """
    print(f"🚀 Pokretanje sinhronnog prevođenja za {len(target_languages)} jezika...")
    
    results = []
    
    # Obrađuj jezike jedan po jedan sa rotacijom ključeva
    for i, language in enumerate(target_languages):
        key_idx = i % 3  # Rotacija kroz 3 ključa
        print(f"📍 Obrađujem jezik {i+1}/{len(target_languages)}: {language} (KEY #{key_idx+1})")
        
        result = translate_one_language_sync(input_path, base_name, folder_id, language)
        results.append(result)
        
        # Kratka pauza između zahteva
        time.sleep(1)
    
    # Log summary
    successful = [r for r in results if r.get("status") == "ok"]
    failed = [r for r in results if r.get("status") != "ok"]
    
    print(f"✅ Uspešno prevedeno: {len(successful)}/{len(target_languages)} jezika")
    if failed:
        print("⚠️ Neuspešni prevodi:")
        for fail in failed:
            print(f"   - {fail['language']}: {fail.get('error', 'Unknown error')}")
    
    # Obriši ulazni fajl
    try:
        os.remove(input_path)
        print(f"🗑️ Obrisana ulazna datoteka: {input_path}")
    except OSError as e:
        print(f"❌ Greška pri brisanju ulazne datoteke {input_path}: {e}")
    
    return results


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

        # Pokreni sinhronno prevođenje u background task-u
        background_tasks.add_task(
            process_translations_sync, input_path, base_name, folder_id
        )

        return JSONResponse(
            status_code=202,
            content={
                "message": "✅ Zahtjev primljen. Sinhronno prevođenje je pokrenuto u pozadini.",
                "filename": file.filename,
                "folder_id": folder_id,
                "languages_count": len(target_languages),
                "keys_used": 3
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"❌ Greška pri pokretanju procesa: {e}"},
        )
