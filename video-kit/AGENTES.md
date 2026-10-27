# Instruções para outros agentes (Hermes, Codex, etc.)

Objetivo: gerar Reels da Missão China 2026 **idênticos** aos feitos no Claude Code.
O padrão visual está no código deste kit, não só no texto. Por isso:

> **Use os scripts deste repositório. Não recrie o visual do zero.**
> Valores aproximados (outra fonte, outro tamanho, outra posição) produzem um vídeo diferente.

Repositório: `https://github.com/alexsouzanet/hermes-test-deploy`
Branch com o kit: `claude/video-use-setup-squgb8` (pasta `video-kit/`).

## Caminho 1 (obrigatório quando o agente roda Python e ffmpeg)

1. Requisitos: Python 3.12+, `ffmpeg`/`ffprobe` com `libass`, `zscale` e `tonemap`; fonte **Inter**
   instalada em `/usr/share/fonts/opentype/inter/` (arquivos `Inter-Black.otf`, `Inter-ExtraBold.otf`,
   `Inter-Bold.otf`, `Inter-SemiBold.otf`, `Inter-Medium.otf`). Download: https://github.com/rsms/inter/releases
   Se a fonte ficar em outro lugar, ajuste `FONT_DIR` em `scripts/kit.py`.
2. Instalar o video-use em `~/Developer/video-use` (`git clone https://github.com/browser-use/video-use`, `uv sync`)
   e criar `~/Developer/video-use/.env` com `ELEVENLABS_API_KEY=...` (pedir ao usuário; nunca commitar).
3. Para cada vídeo:
   ```bash
   python ~/Developer/video-use/helpers/transcribe_batch.py /caminho/da/pasta
   python ~/Developer/video-use/helpers/pack_transcripts.py --edit-dir /caminho/da/pasta/edit
   # ler edit/takes_packed.md, propor cortes, esperar aprovação do usuário
   ~/Developer/video-use/.venv/bin/python video-kit/scripts/make_reel.py reel.json
   ```
   Modelos de `reel.json`: `examples/alibaba_v2.json` (mais recente), `examples/embarque_60s.json`, `examples/modelo_30s.json`.

## Caminho 2 (só se o agente não puder rodar os scripts): especificação exata

Tela 1080×1920, 30 fps. Coordenadas em pixels a partir do canto superior esquerdo.

### Cores e fonte
| Nome | Valor |
|---|---|
| Azul escuro | `#005EB8` |
| Azul claro | `#40B9FF` |
| Branco | `#FFFFFF` |
| Tinta (texto escuro / contorno do karaokê) | `#081428` |
| Fonte | Inter (Black, ExtraBold, Bold, SemiBold, Medium). Nunca Arial/Helvetica |

### Logo (canto superior direito)
- Arquivo `assets/logos/horizontal_branco.png`, largura **300 px**, opacidade **92%**.
- Sombra preta 55% deslocada (2, 3) px, desfoque gaussiano 6 px.
- Posição: borda direita do logo a **64 px** da margem direita; centralizado verticalmente na faixa do selo (topo do selo em **y=140**, altura 76).
- Visível o vídeo todo, exceto abertura e encerramento.

### Selo de local (canto superior esquerdo)
- Pílula de altura **76 px**, raio 38, em **x=48, y=140**.
- Metade esquerda: fundo `#005EB8` (opacidade 92%), ícone de pino `#40B9FF` 30 px, texto **"DIA 3"** em Inter Black 40, branco.
- Metade direita: fundo branco (96%), texto **"HANGZHOU"** em Inter ExtraBold 40, `#005EB8`. Tudo em caixa alta.
- Entra deslizando da esquerda em **0,45 s** (ease-out cúbico), começa em 0,2 s da fala, fica até 6 s e some em 0,3 s.
- Fora do roteiro: "EMBARQUE · GUARULHOS".

### Cartão de nome (lower third)
- Topo em **y=1030**, altura **150 px**, a partir de x=48.
- Barra vertical `#40B9FF` de 12 px cresce de baixo para cima em 0,3 s.
- Painel `#005EB8` (opacidade 88%) abre da esquerda em 0,5 s (começa em 0,15 s).
- Nome: Inter ExtraBold **54**, branco, em (x=92, y=1058). Cargo · Organização: Inter SemiBold **40**, `#40B9FF`, em (x=92, y=1124).
- Texto sobe 22 px e aparece em 0,45 s (começa em 0,35 s). Sai em 0,4 s. Duração 4,5 s, começando em 0,8 s da fala.

### Legenda (estilo C, karaokê, o aprovado)
- Inter Black **84**, caixa alta, branco, contorno `#081428` de **7 px**, sombra 3 px preta 50%.
- Linha de base em **y=1340** (centralizada, margens laterais 100 px). Largura máxima do texto **860 px**; se passar, reduzir a fonte proporcionalmente.
- 2 a 3 palavras por vez. Quebra em pontuação, pausa ≥ 0,3 s e **sempre em cada corte**.
- A palavra sendo falada fica em `#40B9FF` e 106% do tamanho.
- Português escrito: cê→você, tô→estou, tá→está, pra→para, pro→para o, tamos→estamos, dum→de um. "né" não aparece na legenda.
- Nunca separar "Startup Summit". Corrigir nomes: Tsinghua, CEIA, Qwen, Llama, Scale IA, Sebrae Startups.

### Abertura (2,4 s)
- Fundo: quadro do vídeo desfocado 28 px, misturado 72% com `#005EB8`, escurecendo para `#00122D` na base.
- Símbolo branco 150 px de largura, centro x, topo em y≈430.
- Linha pequena (ex.: "MISSÃO CHINA") Inter Bold 40, `#40B9FF`, centro em y=650.
- Título em até 3 linhas, Inter Black **112**, branco, caixa alta, centro da 1ª linha em y=760, entrelinha 122.
- Etiqueta (ex.: "DIA 2 · HANGZHOU") Inter ExtraBold 54, texto `#081428` em pílula `#40B9FF`.
- Elementos entram um depois do outro (0 / 0,25 / 0,5 / 0,85 s), subindo 40 px em 0,5 s.

### Encerramento (2,8 s)
- Mesmo fundo da abertura. Logo `horizontal_fundo_escuro.png` com 760 px de largura, topo em y=640.
- "MISSÃO CHINA 2026 · SCALE IA" Inter ExtraBold 50, branco, centro y=860; traço `#40B9FF` 120×6 px em y=920.
- "@sebraestartups" e "@alexsouzanet" Inter Bold 46, `#40B9FF`, centros y=1010 e y=1080.

### Cortes, zoom e cor
- Cortar **só entre frases**. Não cortar gaguejos no meio da frase.
- Folga em cada corte: até 0,2 s antes da 1ª palavra e 0,3 s depois da última, sem invadir palavra vizinha.
- Fade de áudio de 30 ms em cada emenda.
- Zoom: alterna 100% e **118%** (recorte centrado na horizontal, 28% de cima na vertical). Troca em toda emenda e em pausas ≥ 0,18 s, com trechos de no mínimo 2,2 s.
- Cor: correção automática sutil (contraste/gama/saturação, no máximo ±8%). Sem filtro criativo.

### Áudio
- Voz isolada (ElevenLabs Audio Isolation) + **25%** do som original + EQ `equalizer=f=3500:t=q:w=1.2:g=3,highshelf=f=8000:g=2`.
- Loudness final **−14 LUFS**, pico **−1 dBTP** (loudnorm em duas passagens).
- Sem música no arquivo (adicionada no Instagram).

### Exportação
- H.264 CRF 20, preset medium, yuv420p, 30 fps; AAC 192 kbps, 48 kHz, estéreo; `+faststart`.
- HDR do iPhone (HLG/PQ) convertido para SDR Rec.709 antes de tudo.
