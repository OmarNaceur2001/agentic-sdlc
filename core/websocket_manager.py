"""
websocket_manager.py — WebSocket Live Logs
Feature 4 de la feuille de route Agentic SDLC

Fournit :
  1. ConnectionManager      — gère les clients WebSocket connectés
  2. WebSocketLogHandler    — handler Python logging qui broadcast vers WS
  3. Patch orchestrator.py  — instructions pour brancher le handler
  4. Patch dashboard.html   — JS pour remplacer AJAX par WebSocket

INTÉGRATION dans dashboard_app.py :
  from websocket_manager import ConnectionManager, router as ws_router
  app.include_router(ws_router)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


# ─── CONNECTION MANAGER ───────────────────────────────────────────────────────

class ConnectionManager:
    """
    Gère les connexions WebSocket actives.
    Thread-safe : les agents (threads sync) peuvent broadcaster via broadcast_sync().
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Mémorise la boucle asyncio principale.
        Appeler depuis le startup event de FastAPI :

            @app.on_event("startup")
            async def startup():
                manager.set_loop(asyncio.get_event_loop())
        """
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        """Accepte et enregistre une nouvelle connexion WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connecté. Total : {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Supprime une connexion fermée."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WS] Client déconnecté. Restants : {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        Envoie un message JSON à tous les clients connectés (async).
        Supprime automatiquement les connexions mortes.
        """
        payload = json.dumps(message, ensure_ascii=False)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)

    def broadcast_sync(self, message: dict):
        """
        Envoie un message depuis un thread synchrone (orchestrator, agents).
        Utilise run_coroutine_threadsafe pour traverser la frontière async/sync.

        Usage depuis orchestrator.py :
            manager.broadcast_sync({"type": "log", "level": "OK", "msg": "[OK] SCRUM-10 valide"})
        """
        if self._loop is None or self._loop.is_closed():
            return
        if not self.active_connections:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)


# Instance globale — importée dans dashboard_app.py et orchestrator.py
manager = ConnectionManager()


# ─── LOG HANDLER ──────────────────────────────────────────────────────────────

class WebSocketLogHandler(logging.Handler):
    """
    Handler Python logging qui envoie chaque log vers les clients WebSocket.

    Usage dans orchestrator.py :
        from websocket_manager import manager, WebSocketLogHandler
        ws_handler = WebSocketLogHandler(manager)
        log.addHandler(ws_handler)
    """

    LEVEL_MAP = {
        "DEBUG":    "INFO",
        "INFO":     "INFO",
        "WARNING":  "WARN",
        "ERROR":    "ERROR",
        "CRITICAL": "ERROR",
    }

    def __init__(self, ws_manager: ConnectionManager):
        super().__init__()
        self.ws_manager = ws_manager

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            level = self.LEVEL_MAP.get(record.levelname, "INFO")

            # Détecter les transitions de tickets pour déclencher un refresh
            ticket_update = any(kw in msg for kw in ["DONE", "terminé", "Terminé", "SCRUM-"])

            self.ws_manager.broadcast_sync({
                "type": "log",
                "level": level,
                "msg": msg,
                "ts": datetime.now().strftime("%H:%M:%S"),
                "ticket_update": ticket_update
            })
        except Exception:
            self.handleError(record)


# ─── ROUTER FASTAPI ───────────────────────────────────────────────────────────

router = APIRouter()


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """
    Endpoint WebSocket — les clients s'y connectent pour recevoir les logs en temps réel.
    URL : ws://localhost:8000/ws/logs

    Messages envoyés au client :
      {"type": "log", "level": "OK"|"INFO"|"WARN"|"ERROR", "msg": "...", "ts": "HH:MM:SS", "ticket_update": bool}
      {"type": "ping"}  — heartbeat toutes les 30s pour garder la connexion
    """
    await manager.connect(websocket)

    # Message de bienvenue
    await websocket.send_text(json.dumps({
        "type": "log",
        "level": "INFO",
        "msg": "[WS] WebSocket connecte -- logs en temps reel actifs.",
        "ts": datetime.now().strftime("%H:%M:%S"),
        "ticket_update": False
    }))

    try:
        while True:
            # Attendre les messages du client (keepalive) ou la déconnexion
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Optionnel : traiter les messages client (ex: "clear_logs")
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Heartbeat toutes les 30s
                await websocket.send_text(json.dumps({"type": "ping"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─── PATCH DASHBOARD_APP.PY ───────────────────────────────────────────────────
PATCH_DASHBOARD_APP = """
# ══════════════════════════════════════════════════════════════
# PATCH dashboard_app.py — WebSocket Live Logs (Feature 4)
# Ajouter ces blocs dans dashboard_app.py
# ══════════════════════════════════════════════════════════════

# 1. IMPORTS à ajouter en haut :
import asyncio
from websocket_manager import manager, WebSocketLogHandler, router as ws_router

# 2. INCLUSION DU ROUTER (après app = FastAPI()) :
app.include_router(ws_router)

# 3. STARTUP EVENT (après app = FastAPI()) :
@app.on_event("startup")
async def startup_event():
    manager.set_loop(asyncio.get_event_loop())
    print("[WS] ConnectionManager initialisé avec la boucle asyncio.")
"""


# ─── PATCH ORCHESTRATOR.PY ────────────────────────────────────────────────────
PATCH_ORCHESTRATOR = """
# ══════════════════════════════════════════════════════════════
# PATCH orchestrator.py — Brancher le WebSocketLogHandler
# Ajouter après la configuration du logger (après log = logging.getLogger(...))
# ══════════════════════════════════════════════════════════════

try:
    from websocket_manager import manager, WebSocketLogHandler
    ws_handler = WebSocketLogHandler(manager)
    ws_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S"
    ))
    log.addHandler(ws_handler)
    print("[ORCH] WebSocket log handler branché.")
except ImportError:
    print("[ORCH] websocket_manager non disponible — logs WebSocket désactivés.")
"""


# ─── PATCH DASHBOARD.HTML (JS) ────────────────────────────────────────────────
PATCH_DASHBOARD_JS = """
// ══════════════════════════════════════════════════════════════
// PATCH dashboard.html — Remplacer setInterval par WebSocket
// Ajouter dans la section <script>, remplacer les lignes INIT
// ══════════════════════════════════════════════════════════════

// REMPLACER la ligne : setInterval(loadTicketsFromJira, 30000);
// PAR CE BLOC COMPLET :

let ws = null;
let wsReconnectDelay = 2000;

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/logs`);

    ws.onopen = () => {
        console.log('[WS] Connecté');
        wsReconnectDelay = 2000; // reset backoff
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'log') {
                addLog(data.level || 'INFO', data.msg || '');
                // Si le message indique une mise à jour de ticket, rafraîchir
                if (data.ticket_update) {
                    loadTicketsFromJira();
                    loadScreenshots();
                }
            } else if (data.type === 'ping') {
                ws.send('ping'); // keepalive
            }
        } catch (e) {
            console.warn('[WS] Message non-JSON :', event.data);
        }
    };

    ws.onclose = () => {
        console.warn('[WS] Déconnecté — reconnexion dans', wsReconnectDelay, 'ms');
        setTimeout(connectWebSocket, wsReconnectDelay);
        wsReconnectDelay = Math.min(wsReconnectDelay * 1.5, 30000); // backoff exponentiel
    };

    ws.onerror = (err) => {
        console.error('[WS] Erreur :', err);
        ws.close();
    };
}

// Démarrer WebSocket + polling de secours (au cas où WS indisponible)
connectWebSocket();
setInterval(loadTicketsFromJira, 60000); // fallback moins fréquent (1 min au lieu de 30s)
"""


if __name__ == "__main__":
    print("=== websocket_manager.py ===")
    print()
    print("Ce fichier fournit l'infrastructure WebSocket pour les live logs.")
    print()
    print("INTÉGRATION :")
    print(PATCH_DASHBOARD_APP)
    print()
    print("Dans orchestrator.py :")
    print(PATCH_ORCHESTRATOR)
    print()
    print("Dans dashboard.html (JS) :")
    print(PATCH_DASHBOARD_JS)