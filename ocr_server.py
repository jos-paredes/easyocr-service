# ocr_server.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import easyocr
import io
from PIL import Image, ImageOps, ImageFilter
import re
from typing import List, Dict
import logging

app = FastAPI(title="OCR EasyOCR Service")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar EasyOCR de forma lazy (cuando se necesite)
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        logger.info("Inicializando EasyOCR...")
        # Configuración optimizada para memoria
        _reader = easyocr.Reader(
            ['en'], 
            gpu=False,
            model_storage_directory='./model',
            download_enabled=True,
            detector=True,
            recognizer=True
        )
        logger.info("EasyOCR inicializado")
    return _reader

def preprocess_pil_image(pil_image: Image.Image) -> Image.Image:
    """Preprocesamiento optimizado"""
    img = pil_image.convert("L")  # Grayscale directamente
    img = ImageOps.autocontrast(img, cutoff=2)
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
    if not file.content_type or file.content_type.split('/')[0] != 'image':
        raise HTTPException(status_code=400, detail="Archivo no es una imagen")

    try:
        bytes_img = await file.read()
        # Limitar tamaño de imagen (optimización memoria)
        if len(bytes_img) > 10 * 1024 * 1024:  # 10MB max
            raise HTTPException(status_code=400, detail="Imagen demasiado grande")
            
        pil_img = Image.open(io.BytesIO(bytes_img))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error abriendo imagen: {e}")

    pil_proc = preprocess_pil_image(pil_img)

    try:
        reader = get_reader()  # Lazy initialization
        results = reader.readtext(pil_proc, detail=0)  # Solo texto, menos detalle
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en EasyOCR: {e}")

    text_all = " ".join(results)
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
    temps_norm = [t.replace('C','').replace('c','').replace(',','.').strip() for t in temps]

    # Emparejar por orden
    paired = []
    n = min(len(zonas_norm), len(temps_norm))
    for i in range(n):
        paired.append({"zona": zonas_norm[i], "valor": temps_norm[i]})

    return {"results": paired}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "OCR EasyOCR Service"}
