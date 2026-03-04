from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from typing import Any, Dict
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

game_state: Dict[str, Any] = {"status": "aguardando"}

# Variáveis para gerenciar as placas
mac_to_player: Dict[str, str] = {}
player_counter: int = 1

class JoystickData(BaseModel):
    player_id: str # recebe o MAC Address da placa
    x_pos: int
    y_pos: int

@app.post("/rpc/update_position")
async def update_position(data: JoystickData):
    global player_counter, game_state, mac_to_player
    
    # 1. Verifica se é a primeira vez que esta placa se comunica
    if data.player_id not in mac_to_player:
        assigned_name = f"p{player_counter}"
        mac_to_player[data.player_id] = assigned_name
        game_state[assigned_name] = {"x": 0, "y": 0}
        player_counter += 1
        print(f"\n>>> Nova placa detectada ({data.player_id})! Registrada como {assigned_name} <<<\n")

    # 2. Descobre qual é o "pX" correspondente ao MAC que chegou
    player_name = mac_to_player[data.player_id]

    # 3. Atualiza o estado daquele player específico
    game_state[player_name]["x"] = data.x_pos
    game_state[player_name]["y"] = data.y_pos

    print(f"Estado Global: {game_state}")
    
    return {"assigned_id": player_name, "message": "Posição atualizada", "global_state": game_state}

@app.get("/state")
async def get_state():
    return game_state

@app.get("/")
async def get_index():
    with open("/home/claylton/Documentos/sistemas-distribuidos/server/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)
