# media_service/main.py
import io
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
from rembg import remove
from PIL import Image

app = FastAPI(title="Media Service - Background Removal")

@app.get("/")
async def health_check():
    return {"status": "ok", "service": "background-removal"}

@app.post("/process/background-removal")
async def process_background_removal(image: UploadFile = File(...)):
    """
    Accepts an image and returns a PNG with the background removed.
    This service does NOT save files to disk; everything is in-memory.
    """
    try:
        contents = await image.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty image content.")

        # Load image with Pillow
        input_image = Image.open(io.BytesIO(contents)).convert("RGBA")

        # Remove background using rembg
        output_image = remove(input_image)

        # Dump result to bytes
        buf = io.BytesIO()
        output_image.save(buf, format="PNG")
        buf.seek(0)

        return Response(content=buf.getvalue(), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Background removal error: {e}")
