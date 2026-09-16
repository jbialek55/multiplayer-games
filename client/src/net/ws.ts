/// Thin WebSocket wrapper: connect, auto-reconnect, message dispatch.
/// Owns transport concerns only. Identity decisions (hello vs rejoin) are
/// made by the app in `onOpen`; this class just reports events.

import type { Envelope, MessageType } from "../protocol";

export class WsConnection {
  private ws: WebSocket | null = null;
  private seq = 0;
  private reconnectAttempts = 0;
  private readonly url: string;

  onMessage: (message: Envelope) => void = () => {};
  onStatus: (status: string) => void = () => {};
  onOpen: () => void = () => {};

  constructor() {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    this.url = `${scheme}://${location.host}/ws`;
  }

  connect(): void {
    this.onStatus("connecting…");
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onStatus("connected");
      this.onOpen();
    };

    this.ws.onmessage = (evt) => {
      try {
        this.onMessage(JSON.parse(evt.data) as Envelope);
      } catch (err) {
        console.error("failed to parse ws message", err);
      }
    };

    this.ws.onclose = () => {
      this.onStatus("disconnected — reconnecting…");
      const delay = Math.min(500 * 2 ** this.reconnectAttempts, 5000);
      this.reconnectAttempts += 1;
      setTimeout(() => this.connect(), delay);
    };

    this.ws.onerror = () => {
      /* onclose follows */
    };
  }

  send(type: MessageType, payload: Record<string, unknown> = {}): number {
    const seq = ++this.seq;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, seq, payload }));
    }
    return seq;
  }
}
