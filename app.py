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
    "Arabic",
    "Bengali",
    "Portuguese",
    "Russian",
    "Japanese",
    "Punjabi",
    "Javanese",
    "Korean",
    "Vietnamese",
    "Telugu",
    "Turkish",
    "Marathi",
    "Tamil",
    "Urdu",
    "Persian",
    "Swahili",
    "Hausa",
    "Thai",
    "Gujarati",
    "Polish",
    "Ukrainian",
    "Malay",
    "Romanian",
    "German",
    "French",
    "Italian",
    "Spanish",
    "Dutch",
]


@app.post("/translate-srt/")
async def translate_srt(file: UploadFile = File(...)):
    input_path = os.path.join(INPUT_FOLDER, file.filename)
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    base_name = os.path.splitext(file.filename)[0]

    async with httpx.AsyncClient() as client:
        for language in target_languages:
            output_filename = f"{language}__{base_name}.srt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)

            gst.target_language = language
            gst.input_file = input_path
            gst.output_file = output_path

            # Prijevod
            gst.translate()

            # Pročitaj sadržaj prevedenog fajla
            with open(output_path, "r", encoding="utf-8") as translated_file:
                translated_content = translated_file.read()

            # Pošalji sadržaj na n8n webhook
            await client.post(
                N8N_WEBHOOK_URL,
                json={
                    "language": language,
                    "filename": output_filename,
                    "status": "translated",
                    "content": translated_content,  # Dodano
                },
            )

    return JSONResponse({"message": "✅ All translations complete."})
