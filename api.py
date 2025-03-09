import json
import uuid
import asyncio
import websockets
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://texture-06dbe8.webflow.io", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COMFYUI_SERVER = "rotten-knives-walk.loca.lt"  # Votre URL Localtunnel actuelle

async def open_websocket_connection():
    client_id = str(uuid.uuid4())
    ws = await websockets.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}")
    return ws, client_id

@app.get("/")
async def home():
    return {"message": "API ComfyUI pour génération de textures"}

@app.post("/generate-texture")
async def generate_texture(material: str):  # On garde juste material comme paramètre
    try:
        with open("workflow.json", "r") as f:
            workflow = json.load(f)

        ws, client_id = await open_websocket_connection()
        prompt = {"prompt": workflow, "client_id": client_id}
        response = requests.post(f"http://{COMFYUI_SERVER}/prompt", json=prompt)
        if response.status_code != 200:
            return {"error": f"Erreur ComfyUI : {response.status_code}"}

        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            return {"error": "Aucun prompt_id reçu"}

        output_images = await get_generated_images(prompt_id, ws)
        await ws.close()

        if not output_images:
            return {"error": "Aucune texture générée"}

        return {
            "success": True,
            "diffuse": output_images[0] if output_images else "",
            "normal": output_images[1] if len(output_images) > 1 else "",
            "dis