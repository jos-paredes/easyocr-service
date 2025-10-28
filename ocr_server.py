# ocr_server.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import easyocr
import io
from PIL import Image, ImageOps, ImageFilter
import re
from typing import List, Dict

app = FastAPI(title="OCR EasyOCR Service")

# Permitir CORS (ajusta origins en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crea el reader una vez (costoso)
reader = easyocr.Reader(['en'], gpu=False)  # gpu=True si tu host tiene CUDA

def preprocess_pil_image(pil_image: Image.Image) -> Image.Image:
    img = pil_image.convert("RGB")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.convert("L")  # grayscale
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img

def clean_text(text: str) -> str:
    s = text.replace("ºC", "C").replace("°C", "C")
    s = s.replace("|", " ").replace("l", " ").replace("I", " ")
    s = re.sub(r'[^A-Za-z0-9,.\sC°º]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)) -> Dict[str, List[Dict[str, str]]]:
    if file.content_type.split('/')[0] != 'image':
        raise HTTPException(status_code=400, detail="Archivo no es una imagen")

    try:
        bytes_img = await file.read()
        pil_img = Image.open(io.BytesIO(bytes_img))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error abriendo imagen: {e}")

    pil_proc = preprocess_pil_image(pil_img)

    try:
        results = reader.readtext(pil_proc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en EasyOCR: {e}")

    lines = [res[1] for res in results]
    text_all = " ".join(lines)
    text_clean = clean_text(text_all)

    # Regex para zonas y temperaturas
    zona_pattern = re.compile(r'\b[BL8]T?\d{1,2}\b', re.IGNORECASE)
    temp_pattern = re.compile(r'\b\d{2,3}[,\.]\d\s*[Cc]?\b')

    zonas = zona_pattern.findall(text_clean)
    temps = temp_pattern.findall(text_clean)

    # Normalizar zonas
    zonas_norm = []
    for z in zonas:
        z_up = z.upper()
        z_up = re.sub(r'^[8L]', 'B', z_up)
        z_up = re.sub(r'^BB', 'B', z_up)
        zonas_norm.append(z_up)

    # Normalizar temps
    temps_norm = [t.replace('C','').replace('c','').replace(',','.') .strip() for t in temps]

    # Emparejar por orden
    paired = []
    n = min(len(zonas_norm), len(temps_norm))
    for i in range(n):
        paired.append({"zona": zonas_norm[i], "valor": temps_norm[i]})

    return {"results": paired}
