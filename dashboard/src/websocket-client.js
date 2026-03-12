/**
 * WebSocket Client — manages connection to tracking server
 * with auto-reconnect and event dispatching.
 */

const RECONNECT_DELAY_MS = 2000;

export class WebSocketClient {
  /**
   * @param {string} url  WebSocket URL (e.g. "ws://localhost:8765")
   */
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.isConnected = false;
    this._listeners = {}; // event-name -> [callbacks]
    this._reconnectTimer = null;
    this._shouldReconnect = true;
  }

  /* ---- public API ---- */

  /** Start the connection (will auto-reconnect on drop). */
  connect() {
    this._shouldReconnect = true;
    this._open();
  }

  /** Permanently close the connection. */
  disconnect() {
    this._shouldReconnect = false;
    clearTimeout(this._reconnectTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Subscribe to a message type.
   * @param {"tracking_update"|"system_status"|"connection_ack"|"open"|"close"} event
   * @param {Function} callback
   */
  on(event, callback) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(callback);
  }

  /* ---- internals ---- */

  _emit(event, data) {
    const cbs = this._listeners[event];
    if (cbs) cbs.forEach((cb) => cb(data));
  }

  _open() {
    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      console.error("[WS] Failed to create WebSocket:", err);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("[WS] Connected to", this.url);
      this.isConnected = true;
      this._emit("open");
    };

    this.ws.onclose = () => {
      console.log("[WS] Disconnected");
      this.isConnected = false;
      this._emit("close");
      this._scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.warn("[WS] Error:", err);
    };

    this.ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        const type = msg.type;
        if (type) this._emit(type, msg);
      } catch (e) {
        console.warn("[WS] Bad JSON:", e);
      }
    };
  }

  _scheduleReconnect() {
    if (!this._shouldReconnect) return;
    clearTimeout(this._reconnectTimer);
    this._reconnectTimer = setTimeout(() => {
      console.log("[WS] Reconnecting...");
      this._open();
    }, RECONNECT_DELAY_MS);
  }
}
