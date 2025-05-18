from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PIL import Image
import zipfile
import tempfile
import subprocess
from io import BytesIO
import os
import time

# === CONFIG ===
SECRET_TOKEN = "supersecrettoken123"  # Ganti sesuai kebutuhan

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Sesuaikan ini jika frontend di hosting spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Middleware Log ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    print(f"{request.method} {request.url.path} -> {response.status_code} [{duration}ms]")
    return response

# === Simple GET Check ===
@app.get("/")
def root():
    return {"message": "API is running"}

# === Auth Checker ===
def verify_token(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth.split(" ")[1]
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

# === Convert Batch Endpoint ===
@app.post("/convert-batch")
async def convert_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    format: str = Form(...),
    _: None = Depends(verify_token)
):
    if format not in {"webp", "avif"}:
        return JSONResponse({"error": "Unsupported format"}, status_code=400)

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for file in files:
            try:
                img_bytes = await file.read()
                img = Image.open(BytesIO(img_bytes)).convert("RGBA")
                filename_base = os.path.splitext(file.filename)[0]

                if format == "webp":
                    out = BytesIO()
                    img.save(out, format="WEBP", quality=95, method=6)
                    out.seek(0)
                    zipf.writestr(f"{filename_base}.webp", out.read())

                elif format == "avif":
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_in:
                        img.save(temp_in, format="PNG")
                        temp_in_path = temp_in.name
                    temp_out_path = temp_in_path.replace(".png", ".avif")

                    try:
                        subprocess.run(
                            ["avifenc", "--min", "40", "--max", "60", temp_in_path, temp_out_path],
                            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        with open(temp_out_path, "rb") as f:
                            zipf.writestr(f"{filename_base}.avif", f.read())
                    except subprocess.CalledProcessError:
                        raise HTTPException(status_code=500, detail=f"AVIF encoding failed for {file.filename}")
                    finally:
                        os.remove(temp_in_path)
                        if os.path.exists(temp_out_path):
                            os.remove(temp_out_path)
            except Exception as e:
                return JSONResponse({"error": f"Failed processing {file.filename}: {str(e)}"}, status_code=500)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=converted_images.zip"}
    )
