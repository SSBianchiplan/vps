// Presença de dispositivos (câmeras abertas em cada aparelho conectado).

export interface RemoteCameraInfo {
  label: string;
  width?: number;
  height?: number;
  facing?: string;
}

export interface RemotePeer {
  peer_id: string;
  name: string;
  platform: string;
  camera: RemoteCameraInfo | null; // null = aparelho conectado sem câmera aberta
}
