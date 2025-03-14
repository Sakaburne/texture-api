import json
import uuid
import asyncio
import websockets
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Modèle pour valider le corps de la requête
class TextureRequest(BaseModel):
    material: str

# Initialise l'application FastAPI
app = FastAPI()

# Ajoute le middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://texture-06dbe8.webflow.io", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL de ComfyUI
COMFYUI_SERVER = "https://thirty-masks-serve.loca.lt"  # Ta dernière URL Localtunnel

# Route de test pour la racine
@app.get("/")
async def home():
    return {"message": "API ComfyUI pour génération de textures"}

# Route pour générer une texture
@app.post("/generate-texture")
async def generate_texture(request: TextureRequest):
    try:
        material = request.material
        # Vérifie si material est une chaîne non vide
        if not material or not isinstance(material, str):
            return {"error": "Le paramètre 'material' doit être une chaîne non vide"}
        
        with open("workflow.json", "r") as f:
            workflow = json.load(f)
        workflow["313"]["inputs"]["ckpt_name"] = material

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
            "displacement": output_images[2] if len(output_images) > 2 else ""
        }
    except Exception as e:
        return {"error": f"Erreur : {str(e)}"}

# Fonction pour récupérer les images générées
async def get_generated_images(prompt_id, ws):
    output_images = []
    while True:
        message = await ws.recv()
        message_data = json.loads(message)
        if message_data.get("type") == "executing" and message_data["data"]["node"] is None:
            break
        if message_data.get("type") == "execution_cached":
            history_response = requests.get(f"http://{COMFYUI_SERVER}/history/{prompt_id}")
            if history_response.status_code == 200:
                history_data = history_response.json()
                if prompt_id in history_data:
                    outputs = history_data[prompt_id]["outputs"]
                    for node_id in outputs:
                        if "images" in outputs[node_id]:
                            for img in outputs[node_id]["images"]:
                                img_url = f"http://{COMFYUI_SERVER}/view?filename={img['filename']}&type=output"
                                output_images.append(img_url)
            break
    return output_images

async def open_websocket_connection():
    client_id = str(uuid.uuid4())
    ws = await websockets.connect(f"ws://{COMFYUI_SERVER}/ws?clientId={client_id}")
    return ws, client_id