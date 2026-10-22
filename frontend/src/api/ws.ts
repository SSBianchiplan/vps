import type { ServerMessage, TaskConfig } from "../types";

type OnMessage = (msg: ServerMessage) => void;
type OnOpenState = (open: boolean) => void;

export class VisionSocket {
  private ws: WebSocket | null = null;
  private closedByUser = false;
  private reconnectTimer: number | null = null;

  constructor(
    private url: string,
    private onMessage: OnMessage,
    private onState: OnOpenState,
    private onOpen?: () => void,
  ) {}

  connect(): void {
    this.closedByUser = false;
    this.open();
  }

  private open(): void {
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.onState(true);
      this.onOpen?.(); // permite ao app re-emitir control('start') após reconexão
    };
    ws.onclose = () => {
      this.onState(false);
      if (!this.closedByUser) {
        this.reconnectTimer = window.setTimeout(() => this.open(), 1500);
      }
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (ev) => {
      try {
        this.onMessage(JSON.parse(ev.data) as ServerMessage);
      } catch {
        /* ignora frames malformados */
      }
    };
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private send(obj: unknown): void {
    if (this.isOpen) this.ws!.send(JSON.stringify(obj));
  }

  sendFrame(imageB64: string, frameSeq: number, task: TaskConfig, sourceId?: string): void {
    this.send({
      type: "frame",
      image_b64: imageB64,
      frame_seq: frameSeq,
      task,
      source_id: sourceId ?? null,
    });
  }

  control(action: "start" | "stop" | "ping"): void {
    this.send({ type: "control", action });
  }

  close(): void {
    this.closedByUser = true;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}
