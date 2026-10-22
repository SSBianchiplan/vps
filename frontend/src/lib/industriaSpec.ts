// Catálogo de tecnologias de visão industrial (spec_tecnologia.md §3).
// vd = como o VisionDesk implementa hoje (status real do sistema).

export type VdStatus = "ok" | "parcial" | "roadmap";

export interface TechModel {
  id: string;
  num: string;
  icon: string;
  nome: string;
  camada?: string;            // transversal: captura/treino/deploy
  aplicacao: string;
  quandoUsar: string;
  quandoNao: string;
  requisitos: string;
  io: string;                 // entrada → saída
  latencia: string;
  integracao: string;
  kpi: string[];
  vdStatus: VdStatus;
  vd: string;                 // mapeamento p/ VisionDesk
}

export const TECHS: TechModel[] = [
  {
    id: "cnn", num: "3.1", icon: "🧠", nome: "CNN",
    aplicacao: "Inspeção de superfície e classificação de defeitos localizados (riscos, trincas, manchas, falha de solda, contaminação). Cavalo de batalha da inspeção em tempo real.",
    quandoUsar: "Defeito com assinatura visual local/textural; throughput alto; volume razoável de imagens rotuladas; iluminação controlada.",
    quandoNao: "Defeito lógico (peça no lugar errado), relação espacial de longo alcance, ou pouquíssimas amostras de defeito.",
    requisitos: "Backbone ResNet/EfficientNet ou CNN custom; dataset rotulado (classificação ou segmentação pixel-wise); GPU/edge accelerator.",
    io: "Frame normalizado (ROI) → classe + confiança (ou máscara de segmentação).",
    latencia: "~50–60 ms/inferência em edge (ref.: fundição ~57 ms, acc >99%).",
    integracao: "Score → threshold no edge → bit de reject ao PLC.",
    kpi: ["CLD_Defect_Detection_Rate", "CLD_False_Reject_Rate"],
    vdStatus: "ok",
    vd: "Implementado: classificador CNN real (MobileNetV3-Small, torchvision) local e sem token — /api/classify. Em produção: fine-tune do head no defeito-alvo.",
  },
  {
    id: "yolo", num: "3.2", icon: "🎯", nome: "YOLO / Object Detection",
    aplicacao: "Localizar e contar múltiplos objetos/defeitos por frame com bounding boxes — presença/ausência de componentes, contagem, posição, OCR de Data Matrix, verificação de montagem.",
    quandoUsar: "Precisa de onde além de o quê; múltiplos itens por imagem; linha rápida. YOLOv8 anchor-free; YOLOv12 híbrido CNN-Transformer (Area Attention).",
    quandoNao: "Defeito sub-pixel sem forma definida; anomalia sem classe conhecida a priori (use Anomalia 3.4).",
    requisitos: "Dataset com bounding boxes; variante por trade-off velocidade × acurácia (nano/small/medium); edge accelerator.",
    io: "Frame → lista de [classe, bbox, confiança].",
    latencia: "Tempo real (dezenas de ms; varia por variante e resolução).",
    integracao: "Contagem/posição → comparação com receita (BOM) → OK/NOK ao PLC; coords → guiagem de robô.",
    kpi: ["CLD_Assembly_Verification_Rate", "CLD_Mislabel_Rate"],
    vdStatus: "ok",
    vd: "Implementado: modos DETECTAR e CONTAR (Ultralytics YOLO11 + ByteTrack) no edge, sem token. É o núcleo do sistema.",
  },
  {
    id: "vit", num: "3.3", icon: "🔭", nome: "ViT / híbrido CNN-Transformer",
    aplicacao: "Inspeção que depende de relações espaciais de longo alcance e contexto global — defeitos logicamente dependentes, padrões complexos onde CNN pura erra por foco local.",
    quandoUsar: "Acurácia limitada pelo receptive field local; defeitos sutis/contextuais; há dado suficiente ou pré-treino. Híbridos (CNN textura + atenção contexto) = melhor custo-benefício.",
    quandoNao: "Hardware muito restrito + ciclo agressivo sem accelerator (ViT puro é pesado); dataset minúsculo sem pré-treino.",
    requisitos: "Backbone ViT ou híbrido (Area Attention; ViT self-supervised); preferir pré-treino + fine-tune; accelerator com TOPS.",
    io: "Frame (patches) → classe/máscara/score de anomalia.",
    latencia: "Maior que CNN pura; viável em tempo real com edge accelerator dedicado.",
    integracao: "Igual a CNN/YOLO; substitui o estágio INFER mantendo o resto do pipeline.",
    kpi: ["CLD_Complex_Defect_Accuracy", "CLD_AUROC"],
    vdStatus: "ok",
    vd: "Implementado: ViT-B/16 (Vision Transformer, torchvision) local — /api/classify?model=vit. Contexto global por atenção; o VLM (3.5) complementa em linguagem natural.",
  },
  {
    id: "anomaly", num: "3.4", icon: "❓", nome: "Anomalia não supervisionada",
    aplicacao: "Detectar qualquer desvio do normal sem exemplos rotulados de cada defeito. Resolve o gargalo do defeito raro/inédito.",
    quandoUsar: "Defeitos raros/variáveis/desconhecidos; impossível rotular todos; produto novo (cold start). PatchCore, reconstrução, CLIP-based (AnomalyCLIP/WinCLIP) zero/few-shot.",
    quandoNao: "Defeito bem caracterizado e abundante (CNN/YOLO supervisionados são mais baratos e previsíveis).",
    requisitos: "Imagens apenas normais (ou pouquíssimos defeitos); foundation model de visão / encoder CLIP; banco de features de referência.",
    io: "Frame → score de anomalia + mapa de localização (heatmap/máscara).",
    latencia: "Variável; alguns métodos são training-free (deploy rápido em produto novo).",
    integracao: "Score → threshold adaptativo → reject + flag p/ revisão humana (human-in-the-loop nas primeiras semanas).",
    kpi: ["CLD_Anomaly_AUROC", "CLD_Novel_Defect_Catch_Rate", "CLD_Labeling_Effort_Saved"],
    vdStatus: "ok",
    vd: "Implementado: PatchCore-lite (embeddings YOLO + banco de normais, τ=μ+3σ) — treina a cena nominal e pontua desvios sem rótulo. /api/anomaly.",
  },
  {
    id: "vlm", num: "3.5", icon: "💬", nome: "VLM / agentes de visão",
    aplicacao: "Inteligência de produção contextual — analisa cada ciclo (não cada peça), correlaciona vídeo + telemetria + workflow, gera insight e timeline pesquisável. Segurança/conformidade.",
    quandoUsar: "Quer entender por que a linha desviou, não só se a peça está boa; ergonomia/segurança; auditoria de ciclo; reaproveitar câmeras já instaladas.",
    quandoNao: "Decisão binária peça-a-peça em alta velocidade (overkill, latência alta; use 3.1–3.4).",
    requisitos: "Edge compute robusto (Jetson/IGX); modelos multimodais (VSS/Cosmos/Nemotron-style); fusão vídeo + tags de processo.",
    io: "Stream de vídeo + telemetria → eventos estruturados, alertas, sumário de ciclo, timeline.",
    latencia: "Near-real-time a nível de ciclo (segundos), não de peça (ms).",
    integracao: "Eventos → MES (rework/yield/parada) e SCADA (alarme); insights → BI. Pilotos: ~3% yield, ~10% menos retrabalho.",
    kpi: ["CLD_Cycle_Anomaly_Count", "CLD_OEE_Uplift", "CLD_Rework_Reduction"],
    vdStatus: "ok",
    vd: "Implementado: DESCREVER e ANALISAR via Claude vision (structured outputs + thinking). Eventos = timeline pesquisável.",
  },
  {
    id: "edge", num: "3.6", icon: "⚡", nome: "Edge AI", camada: "deploy (transversal)",
    aplicacao: "Onde a inferência roda. Não é tipo de modelo, é estratégia de deploy que habilita 3.1–3.5 com latência mínima.",
    quandoUsar: "Decisão síncrona com a linha; split-second; restrição de banda/conectividade; soberania de dado.",
    quandoNao: "—",
    requisitos: "Accelerator (Jetson Orin, Hailo-8); runtime otimizado (INT8, TensorRT); pipeline OTA de versão de modelo.",
    io: "Frame → inferência local → decisão; telemetria → nuvem (assíncrono).",
    latencia: "Mínima (local). Mede-se em ms por inferência.",
    integracao: "Edge fala fieldbus com PLC (decisão) e TCP/IP com MES (payload). Nuvem só recebe agregado/modelo.",
    kpi: ["CLD_Inference_Latency_ms", "CLD_Edge_Uptime"],
    vdStatus: "ok",
    vd: "Implementado: YOLO11 + Apple Vision OCR rodam locais (sem token). Os 4 modos não-VLM funcionam offline na borda.",
  },
  {
    id: "synthetic", num: "3.7", icon: "🧬", nome: "Dados sintéticos", camada: "treino (transversal)",
    aplicacao: "Gerar dataset de treino — especialmente cenários de defeito raro — via simulação, reduzindo dependência de coleta real.",
    quandoUsar: "Defeito raro/perigoso/caro de reproduzir; produto novo sem histórico; balancear classes.",
    quandoNao: "Há dado real abundante e representativo.",
    requisitos: "Pipeline de geração (render/simulação, augmentations, defeito sintético via inpainting); validação de domain gap (sim-to-real).",
    io: "Especificação de defeito/cena → imagens rotuladas sintéticas.",
    latencia: "Offline (não toca o runtime).",
    integracao: "Alimenta o treino offline (nuvem) dos modelos 3.1–3.4.",
    kpi: ["CLD_Synthetic_Data_Ratio", "CLD_Model_Accuracy_Gain"],
    vdStatus: "ok",
    vd: "Implementado: gerador offline (scripts/synth_data.py — flip/brilho/rotação/ruído/blur) + augmentations no Estudo de caso. Alimenta o treino de 3.1–3.4.",
  },
  {
    id: "imaging", num: "3.8", icon: "🌈", nome: "Imageamento avançado", camada: "captura (transversal)",
    aplicacao: "Detectar o que a câmera RGB não vê: hiperespectral (material), térmica/IR (calor/solda), raio-X (defeito interno), 3D/depth (geometria, bin picking, dimensional).",
    quandoUsar: "Defeito não é superficial-visível; precisa de dimensional/profundidade; precisa de propriedade de material.",
    quandoNao: "Defeito plenamente visível em RGB (não justifica o custo do sensor).",
    requisitos: "Sensor adequado à modalidade (hiperespectral/térmica/raio-X/ToF/line-scan) trocado no estágio CAPTURE.",
    io: "A modalidade troca o sensor; o restante do pipeline (3.1–3.5) consome o tensor resultante.",
    latencia: "Depende do sensor.",
    integracao: "Sensor no CAPTURE; modelos acima consomem o tensor.",
    kpi: ["CLD_Subsurface_Defect_Catch_Rate", "CLD_Dimensional_Accuracy"],
    vdStatus: "parcial",
    vd: "Parcial (limite de hardware): dia/noite IR real via ONVIF + simulação visual de modalidades (térmica/IR/raio-X/depth). Térmica/raio-X/3D/hiperespectral reais = troca de sensor no CAPTURE.",
  },
  {
    id: "tracking", num: "3.9", icon: "🛰", nome: "Rastreamento de Objetos (Tracking)",
    aplicacao: "Manter a IDENTIDADE de cada objeto no tempo (e entre câmeras): trajetória, cruzamento de linha com sentido (IN/OUT), ocupação/dwell de zona (cycle time observado), contagem sem duplicidade e fluxo entre estações.",
    quandoUsar: "Contar sem recontar o mesmo objeto; medir fluxo/sentido/permanência; cycle time observado e WIP por estação; seguir uma peça/veículo/pessoa pela planta.",
    quandoNao: "Frame único basta (presença/ausência); cena sem movimento; sem detector confiável (tracking-by-detection exige boa detecção).",
    requisitos: "Detector por frame (YOLO/3.2) + tracker (ByteTrack/BoT-SORT) — Kalman (predição) + Hungarian/IoU (associação) + ReID (aparência) p/ multi-câmera.",
    io: "Detecções por frame → tracks (id estável) + geometria (linhas/zonas) → eventos semânticos (LINE_CROSSED/ZONE_ENTERED/DWELL_EXCEEDED) + trajetórias.",
    latencia: "Edge ~10 fps (detecção+associação); evento, não vídeo, sobe à rede.",
    integracao: "Eventos semânticos no Event Store (baixo volume); trajetórias no lakehouse (downsampled). Cruzamento = transição de fase; dwell = cycle time → APS.",
    kpi: ["CLD_Throughput", "CLD_Dwell_Time", "CLD_Zone_WIP", "CLD_Track_Continuity", "CLD_Counterflow_Events"],
    vdStatus: "ok",
    vd: "Implementado: modo RASTREAR no Estúdio (YOLO+ByteTrack) — identidade no tempo, linha c/ sentido, zona/dwell + SLA, contagem por ID único, trajetória no overlay, KPIs de fluxo e eventos semânticos na trilha. Vínculo track↔Tag-ID (Fio do movimento) ligado quando a fonte tem Fio aberto. ReID/multi-câmera (handoff) = roadmap T3–T4.",
  },
  {
    id: "facial", num: "3.10", icon: "🙂", nome: "Reconhecimento Facial / Biometria",
    aplicacao: "Identificação CONSENTIDA do operador por face: login rápido, carimbo de autoria nos eventos e controle de acesso à estação — substitui/complementa crachá/PIN. Identificação, não vigilância.",
    quandoUsar: "Amarrar cada evento a um responsável (P05) sem fricção de digitação; controle de acesso por habilitação/RBAC; presença/turno; EPI + identidade.",
    quandoNao: "Sem consentimento ou sem fallback não-biométrico → NÃO implantar (usar PIN/crachá). Vigilância/avaliação de produtividade individual é PROIBIDO.",
    requisitos: "Detecção de face (Haar/SCRFD) + embedding (ArcFace/SFace ONNX) no edge; galeria restrita aos autorizados; liveness/anti-spoof; consentimento registrado e revogável.",
    io: "Frame → face (bbox+landmarks) → liveness → template (vetor) → match cosseno na galeria → operator_id + score.",
    latencia: "Edge, sub-segundo; trafega/armazena o template (vetor), nunca a foto.",
    integracao: "OPERATOR_IDENTIFIED define o operator_id dos eventos seguintes; RBAC por estação; fallback PIN/crachá sempre disponível.",
    kpi: ["CLD_Auth_Success_Rate", "CLD_FAR", "CLD_FRR", "CLD_Liveness_Block_Rate", "CLD_Fallback_Usage"],
    vdStatus: "ok",
    vd: "Implementado: módulo Reconhecimento Facial (cv2 Haar + descritor LBP no edge, sem download de modelo) — cadastro consentido, identificação 1:N, verificação 1:1 (login), liveness-lite (nitidez), galeria revogável, eventos (OPERATOR_IDENTIFIED/ACCESS_*/LIVENESS_FAILED/CONSENT_WITHDRAWN) e KPIs. Privacidade by design (template, não foto). Produção: ArcFace/SFace ONNX (cv2.FaceRecognizerSF).",
  },
  {
    id: "thermo", num: "3.11", icon: "🌡", nome: "Termografia / Manutenção Preditiva",
    aplicacao: "Imagem térmica → hotspots e anomalias de temperatura em ativos (motores, mancais, painéis, conexões): T_max, ΔT entre fases/peças, baseline por ponto e tendência → antecipar falha (preditiva, não corretiva). É o ANALISAR no espectro térmico.",
    quandoUsar: "Condição de ativo elétrico/mecânico; ronda preditiva periódica; ΔT entre fases; tendência de superaquecimento → janela de manutenção antes de quebrar.",
    quandoNao: "Defeito não-térmico (geométrico/superficial) → CNN/YOLO. Sem preservar o dado radiométrico (só JPEG colorido) a medição não é confiável.",
    requisitos: "Câmera radiométrica FLIR (temperatura por pixel) + emissividade/temp. refletida corretas; OpenCV p/ ROI/segmentação/tendência. Sem FLIR: pseudo-radiometria (luminância→°C).",
    io: "Frame radiométrico → correção (emissividade) → ROI por ponto → T_max/ΔT → baseline/tendência → severidade + evento.",
    latencia: "Leitura por ponto rápida; o valor está na série temporal (baseline/tendência), não no frame único.",
    integracao: "HOTSPOT_DETECTED → ocorrência (VPS_07); MAINTENANCE_RECOMMENDED → janela de manutenção no APS; ativo = ASSET Tag-ID (Fio térmico). Série no lakehouse, eventos no Event Store.",
    kpi: ["CLD_Assets_At_Risk", "CLD_Hotspots_By_Severity", "CLD_MTBF_Trend", "CLD_Predictive_Lead_Time", "CLD_Maintenance_Avoided"],
    vdStatus: "parcial",
    vd: "Implementado: módulo Termografia (pseudo-radiometria luminância→°C + colormap) — ativo/baseline/limites, T_max/T_avg/ΔT, severidade (NORMAL→CRÍTICO), tendência (°C/sem) + predição (dias até o limite), eventos (THERMAL_READING/HOTSPOT/TREND/MAINTENANCE_RECOMMENDED), ocorrência VPS e KPIs preditivos. Parcial: medição REAL exige câmera FLIR radiométrica (troca da fonte; pipeline idêntico).",
  },
  {
    id: "metrology", num: "3.12", icon: "📏", nome: "Metrologia / Inspeção Dimensional",
    aplicacao: "Visão como INSTRUMENTO de medição: cotas reais (linear/diâmetro/ângulo/GD&T) com calibração px→mm, tolerância → CONFORME/NÃO CONFORME + incerteza + calibração rastreável. É a forma dimensional do ANALISAR.",
    quandoUsar: "Medir/gauging com tolerância (não 'parece ok' e sim '42,03 mm CONFORME'); aprovação dimensional que habilita marco/faturamento; Cpk por feature.",
    quandoNao: "Defeito de aparência (use CNN/anomalia); sem calibração/óptica adequada a medição não é confiável.",
    requisitos: "Óptica telecêntrica + iluminação controlada (backlight) + câmera calibrada (intrínsecos/distorção); bordas sub-pixel; best-fit (linha/círculo/elipse). OpenCV/Cognex/LabVIEW.",
    io: "Frame calibrado → features (sub-pixel/best-fit) → cotas em mm → comparação com tolerância → veredito + incerteza + evidência.",
    latencia: "Medição por frame rápida; o rigor vem da calibração/óptica, não da velocidade.",
    integracao: "MEAS Tag-ID filho da OP; MEASUREMENT_APPROVED habilita marco/faturamento (APS); REJECTED → retrabalho/ocorrência (VPS_07 §5); medição amarrada à calibração.",
    kpi: ["CLD_Measurement_Pass_Rate", "CLD_Cpk", "CLD_Rework_From_Measurement", "CLD_Calibration_Validity", "CLD_Measurement_Uncertainty"],
    vdStatus: "parcial",
    vd: "Implementado: módulo Metrologia (OpenCV) — calibração rastreável px→mm, medição por pontos (linear/diâmetro/ângulo), tolerância → CONFORME/NÃO CONFORME + incerteza, eventos MEASUREMENT_* + CALIBRATION_DONE, ocorrência VPS na rejeição e KPIs (pass rate, Cpk). Parcial: precisão industrial exige óptica telecêntrica + bordas sub-pixel (Cognex/LabVIEW); GD&T/Gage R&R = roadmap.",
  },
  {
    id: "iamac", num: "3.13", icon: "🧠", nome: "Motor de IA Generativa + Aprendizado (iaMAC)",
    aplicacao: "A IA própria do VPS: copiloto que conhece o sistema (specs, eventos, linhagem, gold, fotos), responde com CITAÇÕES (grounding), analisa ganhos/gargalos e fica mais inteligente pelo flywheel (uso → curadoria → fine-tune → eval → deploy).",
    quandoUsar: "Perguntar sobre o sistema/decisões; explicar vínculos (graph-RAG); verificar ganhos de produtividade com evidência; ler fotos (VLM); copiloto no cockpit.",
    quandoNao: "Ações de impacto sem aprovação humana (a IA recomenda, não executa); decisões sem fonte (grounding obrigatório).",
    requisitos: "Modelo open-weight self-hosted (Llama/Mistral/Qwen) + VLM + embeddings; RAG híbrido (pgvector/grafo/SQL/imagem); eval harness; MLOps. No Mac: MLX (lab de fine-tune LoRA), Foundation Models/Vision/Speech como ferramentas.",
    io: "Pergunta/intenção → RAG (vetorial+grafo+SQL+imagem) → resposta lastreada (citações) ou recomendação (human-in-the-loop).",
    latencia: "RAG sub-segundo (extrativo); síntese por LLM conforme serving (vLLM/TGI) ou on-device (MLX).",
    integracao: "Copiloto no menu 🧠 IA; lê Event Store/linhagem/gold/evidências; recomenda ao APS/Projetos; registra model_version (auditável); soberania de dados (LGPD).",
    kpi: ["CLD_Eval_Score", "CLD_Grounding_Rate", "CLD_Task_Success", "CLD_Feedback_Positive", "CLD_Productivity_Impact"],
    vdStatus: "parcial",
    vd: "Implementado: módulo iaMAC — copiloto RAG EXTRATIVO com citações/grounding (sobre as specs + estado ao vivo), flywheel (coleta interações + feedback 👍/👎) + eval harness (golden set → score/grounding = 'verificar ganho'), agente de ganhos/gargalos (ancorado em dado) e status Mac/MLX (Apple Silicon, frameworks). Parcial/roadmap: LLM open-weight self-hosted + fine-tune LoRA (MLX) + pgvector + DPO — Mac=lab, servidor=escala.",
  },
  {
    id: "automation", num: "3.14", icon: "🏭", nome: "Automação Industrial (PLC/IHM)",
    aplicacao: "Conector OT híbrido: lê o estado real do chão (contador, estado de máquina, alarmes, setpoints, I/O) por PROTOCOLO (OPC UA/Modbus/S7/EtherNet-IP/MQTT) onde há, e por VISÃO (OCR/VLM da IHM legada) onde não há → eventos do VPS (OEE/ocorrências/APS).",
    quandoUsar: "Capturar a verdade do equipamento (OEE, contagem, estado, alarme, cycle time); ler IHM legada sem API (caminho B); reconciliar contador do PLC × visão × ERP.",
    quandoNao: "Controle/escrita no PLC (proibido — é observador read-only). Sem conectividade nem acesso visual à IHM.",
    requisitos: "Edge gateway na borda (Purdue/DMZ); OPC UA (SignAndEncrypt) — primário; TIA Openness p/ auto tag-map (Siemens); WinCC Unified/historiador. Caminho B: câmera/screen + OCR/VLM.",
    io: "Tag/nó do PLC (ou ROI da IHM) → normalização (unidade/deadband/qualidade/timestamp da fonte) → evento semântico (MACHINE_STATE/COUNTER_READ/ALARM_RAISED/…).",
    latencia: "Subscription/report-by-exception (não polling agressivo); timestamp na fonte (OPC UA).",
    integracao: "Ativo = ASSET Tag-ID; estado→APS, alarme/IO_FAULT→ocorrência (VPS_07), contador→OEE, cycle time real; reconcilia com visão (Rastreamento) e ERP. ISA-95 nível 2↔3.",
    kpi: ["CLD_OEE", "CLD_Machine_Availability", "CLD_Production_Count", "CLD_Downtime_By_Reason", "CLD_Cycle_Time_Observed", "CLD_IO_Fault_Rate", "CLD_Count_Reconciliation"],
    vdStatus: "parcial",
    vd: "Implementado: módulo Automação Industrial — conector OT read-only com SIMULAÇÃO dos 5 componentes (§14: drive SINAMICS, remota ET 200SP/diagnóstico PROFINET, transmissor de nível, máquina PackML, Comfort Panel legado por VISÃO), eventos semânticos (timestamp da fonte) → trilha + ocorrência VPS, OEE/KPIs. Parcial/roadmap: OPC UA real (lib asyncua + servidor), TIA Openness/WinCC, Modbus/S7/Sparkplug — sem PLC/hardware no ambiente.",
  },
];

// §7 — matriz de decisão
export const DECISAO: { q: string; tech: string }[] = [
  { q: "Defeito superficial, bem caracterizado, dado abundante?", tech: "CNN (3.1)" },
  { q: "Localizar/contar múltiplos itens, verificar montagem?", tech: "YOLO (3.2)" },
  { q: "Seguir identidade no tempo, fluxo, dwell, contar sem duplicar?", tech: "Rastreamento (3.9)" },
  { q: "Identificar o operador (login/autoria/acesso), com consentimento?", tech: "Reconhecimento Facial (3.10)" },
  { q: "Antecipar falha por calor (hotspot/ΔT/tendência) em ativos?", tech: "Termografia (3.11)" },
  { q: "Medir dimensão real com tolerância (gauging/Cpk)?", tech: "Metrologia (3.12)" },
  { q: "Perguntar ao sistema, explicar vínculos, verificar ganhos?", tech: "iaMAC — Motor de IA (3.13)" },
  { q: "Ler PLC/IHM (estado/contador/alarme), OEE — sem controlar?", tech: "Automação Industrial (3.14)" },
  { q: "Defeito depende de contexto global / longo alcance?", tech: "ViT / híbrido (3.3)" },
  { q: "Defeito raro/desconhecido, poucos rótulos?", tech: "Anomalia (3.4)" },
  { q: "Entender o ciclo/processo/segurança, não a peça?", tech: "VLM / agente (3.5)" },
  { q: "Defeito interno / material / geometria?", tech: "Imageamento avançado (3.8)" },
  { q: "Decisão síncrona com a linha?", tech: "Edge AI (3.6) — sempre" },
  { q: "Faltam dados de defeito para treinar?", tech: "Dados sintéticos (3.7)" },
];

export const STATUS_LABEL: Record<VdStatus, { txt: string; cls: string }> = {
  ok: { txt: "✅ no VisionDesk", cls: "bg-ok/20 text-ok" },
  parcial: { txt: "◐ parcial", cls: "bg-warn/20 text-warn" },
  roadmap: { txt: "○ roadmap", cls: "bg-edge text-muted" },
};
