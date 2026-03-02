"""
Camada de Persistência — SQLite via aiosqlite
----------------------------------------------
Armazena histórico de partidas e placar global.
Protegida pelo Circuit Breaker: se o banco falhar repetidamente,
o jogo continua sem persistência temporariamente.
"""

import aiosqlite
import os
from middleware.circuit_breaker import db_circuit_breaker, CircuitBreakerOpenError

DB_PATH = os.path.join(os.path.dirname(__file__), "game.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                winner_name TEXT,
                total_rounds INTEGER,
                player_count INTEGER,
                started_at REAL,
                ended_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                player_name TEXT NOT NULL,
                rounds_survived INTEGER,
                score INTEGER,
                device_type TEXT,
                FOREIGN KEY (game_id) REFERENCES games(id)
            )
        """)
        await db.commit()
    print("[DB] Banco de dados inicializado.")


async def save_game(game_id: str, room_id: str, winner_name: str,
                    total_rounds: int, player_count: int,
                    started_at: float, ended_at: float):
    async def _do():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO games VALUES (?,?,?,?,?,?,?)",
                (game_id, room_id, winner_name, total_rounds, player_count, started_at, ended_at)
            )
            await db.commit()

    try:
        await db_circuit_breaker.call(_do())
    except CircuitBreakerOpenError as e:
        print(f"[DB] {e} — jogo prossegue sem persistência.")
    except Exception as e:
        print(f"[DB] Erro ao salvar partida: {e}")


async def save_score(game_id: str, player_name: str, rounds_survived: int,
                     score: int, device_type: str):
    async def _do():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO scores (game_id, player_name, rounds_survived, score, device_type) VALUES (?,?,?,?,?)",
                (game_id, player_name, rounds_survived, score, device_type)
            )
            await db.commit()

    try:
        await db_circuit_breaker.call(_do())
    except CircuitBreakerOpenError as e:
        print(f"[DB] {e} — score não persistido.")
    except Exception as e:
        print(f"[DB] Erro ao salvar score: {e}")


async def get_scoreboard(limit: int = 20) -> list[dict]:
    async def _do():
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT player_name, SUM(score) as total_score,
                       SUM(rounds_survived) as total_rounds,
                       COUNT(*) as games_played,
                       MAX(rounds_survived) as best_run
                FROM scores
                GROUP BY player_name
                ORDER BY total_score DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    try:
        return await db_circuit_breaker.call(_do())
    except CircuitBreakerOpenError as e:
        print(f"[DB] {e} — retornando scoreboard vazio.")
        return []
    except Exception as e:
        print(f"[DB] Erro ao buscar scoreboard: {e}")
        return []
