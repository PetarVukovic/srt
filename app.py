from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import gemini_srt_translator as gst
import httpx
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gst.gemini_api_key = os.environ.get("GOOGLE_API_KEY")

INPUT_FOLDER = "srt-files"
OUTPUT_FOLDER = "srt-prijevodi"

os.makedirs(INPUT_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL")

target_languages = [
    "English",
    "Mandarin Chinese",
    "Hindi",
]


@app.post("/translate-srt/")
async def translate_srt(folder_id: str, file: UploadFile = File(...)):
    input_path = os.path.join(INPUT_FOLDER, file.filename)
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    base_name = os.path.splitext(file.filename)[0]

    failed_languages = []

    async with httpx.AsyncClient() as client:
        for language in target_languages:
            output_filename = f"{language}__{base_name}.srt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)

            gst.target_language = language
            gst.input_file = input_path
            gst.output_file = output_path
            print("N8N_WEBHOOK_URL =", N8N_WEBHOOK_URL)

            print(f"Prevodim: {language}")
            try:
                gst.translate()
                print(f"✔️ Prijevod za {language} završen.")
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
                    timeout=10,
                )
                print(f"📤 Poslano na n8n za {language}: {response.status_code}")
            except Exception as e:
                print(f"❌ Greška slanja na webhook za {language}: {e}")
                failed_languages.append(language)

    # Ako je bilo neuspjeha, pokušaj ponovo za sve fajlove u OUTPUT_FOLDER
    if failed_languages:
        print("🔁 Pokušavam ponovo slati sve prevedene fajlove...")
        for filename in os.listdir(OUTPUT_FOLDER):
            file_path = os.path.join(OUTPUT_FOLDER, filename)
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                response = await client.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "filename": filename,
                        "status": "resent",
                        "content": content,
                        "folder_id": folder_id,
                    },
                    timeout=10,
                )
                print(f"📤 Ponovno poslano: {filename} ({response.status_code})")
                os.remove(file_path)
                print(f"🗑️ Obrisano: {filename}")
            except Exception as e:
                print(f"❌ Neuspjeh slanja fajla {filename}: {e}")

    return JSONResponse(
        {
            "message": "✅ Translations done. Resent failed if needed.",
            "CONTENT": content,
        }
    )
