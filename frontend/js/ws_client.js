/**
 * ws_client.js — Abstração WebSocket para o Browser
 * ---------------------------------------------------
 * O usuário da aplicação NUNCA manipula WebSockets diretamente.
 * Toda comunicação passa por este middleware que:
 *   - Gerencia conexão/reconexão
 *   - Injeta timestamps de Lamport em cada mensagem enviada
 *   - Atualiza o relógio local ao receber eventos
 *   - Despacha eventos customizados no document
 */

export class GameWSClient {
    constructor(serverUrl) {
        this.serverUrl = serverUrl;
        this.ws = null;
        this.playerId = null;
        this.lamportClock = 0;
        this._handlers = {};
        this._reconnectAttempts = 0;
        this._maxReconnects = 3;
    }

    /** Gera um ID único para este cliente.
     *  crypto.randomUUID() só funciona em HTTPS/localhost.
     *  Aqui usamos crypto.getRandomValues() que funciona em HTTP também. */
    static generatePlayerId() {
        try {
            // Funciona em HTTP e HTTPS (não precisa de secure context)
            const arr = new Uint8Array(8);
            crypto.getRandomValues(arr);
            return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
        } catch {
            // Fallback absoluto para ambientes sem crypto
            return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
        }
    }

    /** Conecta ao servidor WebSocket. */
    connect(playerId, playerName, deviceType = 'browser') {
        this.playerId = playerId;
        const url = `${this.serverUrl}/ws/${playerId}`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('[WS] Conectado ao servidor.');
            this._reconnectAttempts = 0;
            this._send({ type: 'identify', name: playerName, device_type: deviceType });
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            // Atualiza relógio de Lamport: max(local, received) + 1
            const remoteClock = msg.lamport_ts || 0;
            this.lamportClock = Math.max(this.lamportClock, remoteClock) + 1;
            this._dispatch(msg.type, msg);
        };

        this.ws.onclose = (event) => {
            console.warn('[WS] Conexão encerrada:', event.code);
            this._dispatch('disconnected', { code: event.code });
            this._attemptReconnect(playerName, deviceType);
        };

        this.ws.onerror = (err) => {
            console.error('[WS] Erro:', err);
        };
    }

    /** Retry com backoff exponencial (1s, 2s, 4s). */
    _attemptReconnect(playerName, deviceType) {
        if (this._reconnectAttempts >= this._maxReconnects) {
            console.error('[WS] Máximo de reconexões atingido.');
            this._dispatch('reconnect_failed', {});
            return;
        }
        this._reconnectAttempts++;
        const delay = 1000 * Math.pow(2, this._reconnectAttempts - 1);
        console.log(`[WS] Tentando reconectar em ${delay}ms (tentativa ${this._reconnectAttempts})...`);
        setTimeout(() => this.connect(this.playerId, playerName, deviceType), delay);
    }

    /** Envia mensagem ao servidor com timestamp de Lamport. */
    _send(data) {
        this.lamportClock++;
        const payload = { ...data, lamport_ts: this.lamportClock };
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(payload));
        }
    }

    /** API pública: enviar mensagens de jogo. */
    createRoom() { this._send({ type: 'create_room' }); }
    joinRoom(roomId) { this._send({ type: 'join_room', room_id: roomId }); }
    startGame() { this._send({ type: 'start_game' }); }
    sendMove(direction) { this._send({ type: 'player_move', direction }); }
    ping() { this._send({ type: 'ping' }); }

    /** Registra handler para um tipo de mensagem. */
    on(type, handler) {
        if (!this._handlers[type]) this._handlers[type] = [];
        this._handlers[type].push(handler);
        return this; // chainable
    }

    _dispatch(type, data) {
        (this._handlers[type] || []).forEach(fn => fn(data));
        (this._handlers['*'] || []).forEach(fn => fn(type, data));
    }

    get clock() { return this.lamportClock; }

    disconnect() {
        this._maxReconnects = 0;
        this.ws?.close();
    }
}
