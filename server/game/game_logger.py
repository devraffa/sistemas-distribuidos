"""
game_logger.py — Logger de Eventos de Jogo
-------------------------------------------
Grava cada ação dos jogadores e resultados em:
  - Console (stdout)
  - Arquivo: server/logs/game_YYYYMMDD.log  (JSON-lines)

Cada linha do arquivo é um JSON independente para facilitar
análise e importação em ferramentas externas.
"""

import json
import os
import time
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


def _log_path() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_DIR, f"game_{date_str}.log")


def log_event(event_type: str, room_id: str, data: dict, lamport_ts: int = 0):
    """
    Grava um evento no arquivo de log e imprime no console.

    Parâmetros:
        event_type  : ex. "round_start", "player_move", "player_eliminated"
        room_id     : ID da sala
        data        : dict com detalhes do evento
        lamport_ts  : timestamp lógico de Lamport no momento do evento
    """
    entry = {
        "ts":         time.time(),
        "datetime":   datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "lamport":    lamport_ts,
        "room":       room_id,
        "event":      event_type,
        **data,
    }
    line = json.dumps(entry, ensure_ascii=False)

    # Console
    console_msg = (
        f"[LOG][L={lamport_ts:>4}][{entry['datetime']}] "
        f"[{room_id}] {event_type}"
    )
    # Adiciona resumo legível por tipo
    if event_type == "player_move":
        ok = "✓" if data.get("correct") else "✗"
        console_msg += f" | {data.get('player_name','?')} → {data.get('direction','?')} (esperado: {data.get('expected','?')}) {ok}"
    elif event_type == "round_start":
        console_msg += f" | rodada {data.get('round','?')} | vez de {data.get('current_player_name','?')} | {data.get('sequence_length','?')} seta(s)"
    elif event_type in ("player_eliminated", "move_correct"):
        console_msg += f" | {data.get('player_name', data.get('player', {}).get('name','?'))}"
    elif event_type == "game_over":
        w = data.get("winner") or {}
        console_msg += f" | vencedor: {w.get('name','nenhum')} | {data.get('total_rounds','?')} rodadas"
    elif event_type == "room_reset":
        console_msg += f" | solicitado por {data.get('requested_by','?')}"

    print(console_msg)

    # Arquivo
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[LOG] Erro ao gravar log: {e}")
