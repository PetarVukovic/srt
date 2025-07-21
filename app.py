from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
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


async def process_translations_in_background(
    input_path: str, base_name: str, folder_id: str
):
    """
    Ova funkcija se izvršava u pozadini.
    Prevodi SRT datoteku na sve ciljane jezike i šalje rezultate na n8n webhook.
    """
    failed_languages = []

    async with httpx.AsyncClient() as client:
        for language in target_languages:
            output_filename = f"{language}__{base_name}.srt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)

            gst.target_language = language
            gst.input_file = input_path
            gst.output_file = output_path

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
                    timeout=30,  # Povećan timeout za slanje na webhook
                )
                print(f"📤 Poslano na n8n za {language}: {response.status_code}")
                # Opcionalno: obrišite prevedenu datoteku nakon slanja
                os.remove(output_path)
                print(f"🗑️ Obrisano: {output_filename}")

            except Exception as e:
                print(f"❌ Greška slanja na webhook za {language}: {e}")
                failed_languages.append(language)

    # Opcionalno: logika za ponovno slanje neuspjelih prijevoda
    if failed_languages:
        print(f"Neuspjeli prijevodi za jezike: {', '.join(failed_languages)}")
        # Ovdje možete dodati logiku za obavještavanje ili ponovni pokušaj

    # Očisti ulaznu datoteku nakon što su svi prijevodi obrađeni
    try:
        os.remove(input_path)
        print(f"🗑️ Obrisana ulazna datoteka: {input_path}")
    except OSError as e:
        print(f"❌ Greška pri brisanju ulazne datoteke {input_path}: {e}")


@app.post("/translate-srt/")
async def translate_srt(
    background_tasks: BackgroundTasks,
    folder_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Ovaj endpoint odmah vraća odgovor i pokreće proces prevođenja u pozadini.
    """
    try:
        input_path = os.path.join(INPUT_FOLDER, file.filename)
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        base_name = os.path.splitext(file.filename)[0]

        # Dodaj dugotrajni proces kao pozadinski zadatak
        background_tasks.add_task(
            process_translations_in_background, input_path, base_name, folder_id
        )

        # Odmah vrati odgovor n8n-u
        return JSONResponse(
            status_code=202,  # 202 Accepted je prikladan statusni kod
            content={
                "message": "✅ Zahtjev primljen. Prevođenje je započelo u pozadini.",
                "filename": file.filename,
                "folder_id": folder_id,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "message": f"❌ Došlo je do greške prilikom pokretanja procesa: {e}"
            },
        )
