// Playbook de aplicação por tecnologia (CV+IA industrial): ciclo
// Requisitos → Desenvolvimento → Validação → Testes → Implementação + equipamentos.
// Conteúdo prescritivo p/ o Manual (alinhado à spec_tecnologia).

export interface TechPlay {
  id: string;
  num: string;
  nome: string;
  requisitos: string[];
  desenvolvimento: string[];
  validacao: string[];
  testes: string[];
  implementacao: string[];
  equipNecessario: string[];
  equipRecomendado: string[];
}

export const PLAYBOOK: TechPlay[] = [
  {
    id: "cnn", num: "3.1", nome: "CNN — classificação de defeito",
    requisitos: ["Defeito com assinatura visual local (risco/trinca/mancha)", "≥300–1000 imagens rotuladas por classe", "Iluminação controlada e FOV fixo", "Tempo de ciclo conhecido (latência-alvo)"],
    desenvolvimento: ["Backbone MobileNet/ResNet/EfficientNet + head custom", "Transfer learning + fine-tune do head no defeito-alvo", "Aumentos (3.7) p/ classes raras", "Calibração de threshold por F1/custo de false-reject"],
    validacao: ["Split treino/val/teste estratificado", "Matriz de confusão + curva precisão-recall", "Revisão humana dos falsos (FP/FN)", "Teste de robustez a iluminação/sujeira"],
    testes: ["Bench de latência em edge (alvo <60 ms)", "Teste de regressão por versão de modelo", "Golden-set fixo a cada deploy", "Drift monitoring em produção"],
    implementacao: ["Quantização INT8/CoreML (scripts/export_model.py)", "Score → threshold → reject bit ao PLC", "Model_Version em todo evento (rollback)", "Retraining loop versionado (OTA)"],
    equipNecessario: ["Câmera area-scan ≥2–5 MP", "Iluminação dedicada (domo/backlight)", "Edge com GPU/NPU (Jetson Orin / Hailo-8)"],
    equipRecomendado: ["Lente telecêntrica p/ medição", "Estroboscópio sincronizado ao trigger", "Frame grabber (GigE Vision) p/ alta taxa"],
  },
  {
    id: "yolo", num: "3.2", nome: "YOLO — detecção/contagem/montagem",
    requisitos: ["Necessidade de localizar/contar (não só classificar)", "Dataset com bounding boxes", "Classes-alvo definidas (BOM/receita)", "FPS-alvo da linha"],
    desenvolvimento: ["Escolher variante (nano/small/medium) por velocidade×acurácia", "Treino com bboxes + ByteTrack p/ contagem", "Definir linha/zona de contagem (ROI)", "Regra de montagem: contagem vs BOM"],
    validacao: ["mAP@0.5 / mAP@0.5:0.95", "Acurácia de contagem por linha/zona", "Teste de oclusão e sobreposição", "Falsos por classe-alvo"],
    testes: ["Latência por resolução/variante", "Estabilidade de track_id (tracking)", "Teste em fluxo real (esteira)", "Cobertura de bordas do FOV"],
    implementacao: ["Edge (já no VisionDesk: DETECTAR/CONTAR)", "Contagem/posição → OK/NOK ao PLC; coords → robô", "Notificar (AGIR) por classe-alvo", "Auto-gravação por detecção"],
    equipNecessario: ["Câmera area-scan ou line-scan (esteira)", "Edge accelerator (Jetson/Hailo)", "Iluminação uniforme"],
    equipRecomendado: ["Line-scan p/ web/bobina contínua", "Trigger de hardware (encoder da esteira)", "Múltiplas câmeras p/ 360°"],
  },
  {
    id: "vit", num: "3.3", nome: "ViT / híbrido — contexto global",
    requisitos: ["Defeito depende de relação espacial de longo alcance", "Dado suficiente OU pré-treino disponível", "Accelerator com TOPS adequado", "Acurácia limitada por CNN local"],
    desenvolvimento: ["ViT-B/16 ou híbrido CNN-Transformer (Area Attention)", "Pré-treino + fine-tune (self-supervised quando possível)", "Fusão textura local (CNN) + contexto (atenção)", "Destilação p/ caber no edge"],
    validacao: ["AUROC / acurácia em defeitos contextuais", "Comparação direta vs CNN pura (ganho real?)", "Mapas de atenção p/ explicabilidade", "Custo×benefício de latência"],
    testes: ["Latência em accelerator dedicado", "Teste de generalização (novos lotes)", "Robustez a variação de pose/escala", "A/B vs baseline CNN"],
    implementacao: ["Substitui o estágio INFER mantendo o pipeline", "Quantização + TensorRT/CoreML", "Fallback p/ CNN se latência estourar", "VLM (3.5) complementa em linguagem"],
    equipNecessario: ["Edge robusto (Jetson Orin NX/AGX)", "Câmera ≥5 MP", "Iluminação controlada"],
    equipRecomendado: ["GPU dedicada p/ treino on-prem", "Armazenamento rápido p/ datasets", "Pipeline MLOps (versionamento)"],
  },
  {
    id: "anomaly", num: "3.4", nome: "Anomalia não supervisionada",
    requisitos: ["Defeito raro/inédito (sem rótulos)", "Conjunto de imagens APENAS normais", "Produto novo (cold start)", "Tolerância a human-in-the-loop inicial"],
    desenvolvimento: ["PatchCore/CLIP-based (AnomalyCLIP/WinCLIP)", "No VisionDesk: embeddings YOLO + banco de normais (τ=μ+3σ)", "Coletar a cena nominal (fit)", "Threshold adaptativo por percentil"],
    validacao: ["AUROC do detector", "Taxa de captura de defeito novo", "Falsos em variação normal (luz/sombra)", "Curva de esforço de rotulagem economizado"],
    testes: ["Injeção de anomalias sintéticas", "Teste de cold-start (produto novo)", "Estabilidade do τ ao longo do dia", "Re-fit periódico"],
    implementacao: ["Score → threshold → reject + flag p/ revisão", "Revisão humana vira rótulo (supervisão futura)", "No VisionDesk: /api/anomaly (fit + score)", "Bom p/ intrusão/segurança"],
    equipNecessario: ["Câmera RGB ≥2 MP", "Edge com NPU", "Iluminação estável (reduz falso-positivo)"],
    equipRecomendado: ["Câmera térmica p/ anomalia de calor", "Estação de revisão (human-in-the-loop)", "Storage p/ banco de normais versionado"],
  },
  {
    id: "vlm", num: "3.5", nome: "VLM / agentes — inteligência de ciclo",
    requisitos: ["Entender o ciclo/processo (não a peça)", "Infra de câmeras já instalada", "Conectividade p/ o modelo (ou edge multimodal)", "ANTHROPIC_API_KEY (ou VSS on-prem)"],
    desenvolvimento: ["No VisionDesk: DESCREVER/ANALISAR (Claude vision)", "Prompts + structured outputs por modo", "Fusão vídeo + telemetria de processo", "Timeline pesquisável de eventos"],
    validacao: ["Concordância com auditor humano", "Precisão de OK/NOK em inspeção subjetiva", "Qualidade do sumário de ciclo", "Custo por inferência (token)"],
    testes: ["Latência a nível de ciclo (segundos)", "Teste de recusa/segurança do modelo", "Cobertura de cenários de processo", "Throttle/custo sob carga"],
    implementacao: ["Snapshot sob demanda (economia)", "Eventos → MES (rework/yield) + SCADA (alarme)", "Insights → BI (OEE/retrabalho)", "AGIR fecha visão→decisão→ação"],
    equipNecessario: ["Câmeras existentes (reaproveita)", "Conectividade ou edge multimodal (Jetson IGX)", "Backend com a chave de API"],
    equipRecomendado: ["VSS/Cosmos/Nemotron on-prem (soberania)", "Microfone/telemetria p/ fusão", "Dashboard executivo (BI)"],
  },
  {
    id: "edge", num: "3.6", nome: "Edge AI — camada de deploy",
    requisitos: ["Decisão síncrona com a linha (split-second)", "Restrição de banda/soberania de dado", "Modelo escolhido (3.1–3.5)", "SLA de latência definido"],
    desenvolvimento: ["Quantização INT8 + runtime otimizado (TensorRT/CoreML)", "Pipeline OTA de versão de modelo", "No VisionDesk: YOLO/Apple Vision locais (sem token)", "Watchdog + telemetria de uptime"],
    validacao: ["Latência p50/p95 sob carga", "Uptime do edge", "Degradação graciosa (fallback)", "Consumo de energia/térmico"],
    testes: ["Teste de stress (FPS máximo)", "Failover/reboot", "Teste térmico prolongado", "Atualização OTA sem parada"],
    implementacao: ["Edge fala fieldbus (PLC) + TCP/IP (MES)", "Nuvem só recebe agregado/modelo", "Métricas Prometheus (/api/metrics)", "Auth + segurança de borda"],
    equipNecessario: ["NVIDIA Jetson Orin / Hailo-8", "Fonte e gabinete industrial (IP)", "Rede determinística (PROFINET/EtherNet-IP)"],
    equipRecomendado: ["Redundância (2 edges)", "UPS/no-break", "Switch gerenciável + VLAN de visão"],
  },
  {
    id: "synthetic", num: "3.7", nome: "Dados sintéticos — treino",
    requisitos: ["Defeito raro/perigoso/caro de reproduzir", "Produto novo sem histórico", "Classes desbalanceadas", "Ferramenta de geração/render"],
    desenvolvimento: ["Augmentations (scripts/synth_data.py) + inpainting de defeito", "Render/simulação 3D quando aplicável", "Validação de domain gap (sim-to-real)", "Balanceamento de classes"],
    validacao: ["Ganho de acurácia com sintético", "Razão sintético/real ótima", "Sem overfit ao domínio sintético", "Teste em dados reais segurados"],
    testes: ["Ablação (com/sem sintético)", "Detecção de artefatos de geração", "Cobertura de variações (luz/pose)", "Re-treino reproduzível"],
    implementacao: ["Alimenta o treino OFFLINE de 3.1–3.4", "Não toca o runtime", "Versionar dataset + seed", "Pipeline de geração em CI"],
    equipNecessario: ["Estação com GPU p/ render/treino", "Amostras reais semente", "Storage de datasets"],
    equipRecomendado: ["Engine de render (Blender/Omniverse)", "Ferramenta de inpainting (difusão)", "Data lake versionado (DVC)"],
  },
  {
    id: "imaging", num: "3.8", nome: "Imageamento avançado — captura",
    requisitos: ["Defeito não-superficial / dimensional / material", "Definir modalidade (térmica/raio-X/3D/hiperespectral)", "Segurança (raio-X) e normas", "Orçamento de sensor (CapEx)"],
    desenvolvimento: ["Trocar o sensor no estágio CAPTURE", "Calibração da modalidade (radiometria/profundidade)", "Pipeline 3.1–3.5 consome o tensor resultante", "No VisionDesk: dia/noite IR real (ONVIF) + simulação de modalidade"],
    validacao: ["Acurácia de detecção sub-superficial", "Precisão dimensional (3D)", "Repetibilidade da medição", "Validação contra padrão (gage R&R)"],
    testes: ["Calibração periódica", "Teste com peças-padrão", "Estabilidade térmica do sensor", "Segurança radiológica (raio-X)"],
    implementacao: ["Integração mecânica + iluminação específica", "Sincronização sensor↔trigger", "Fusão multimodal quando útil", "Manutenção/limpeza programada"],
    equipNecessario: ["Sensor da modalidade (térmica FLIR / raio-X / câmera 3D ToF / hiperespectral)", "Iluminação/fonte específica", "Blindagem/segurança (raio-X)"],
    equipRecomendado: ["Robô p/ bin picking (3D)", "Mesa de calibração", "Câmera line-scan hiperespectral p/ esteira"],
  },
];
