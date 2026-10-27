# Kit de vídeo · Missão China 2026 (SCALE IA)

Reels de 30, 60 ou 90 s para @alexsouzanet e @sebraestartups (mesmo vídeo, post em collab).
Edição feita pelo skill [video-use](https://github.com/browser-use/video-use) + os gráficos deste kit.

## Restaurar numa sessão nova (cerca de 5 min)

1. Instalar o video-use:
   ```bash
   mkdir -p ~/Developer && git clone https://github.com/browser-use/video-use ~/Developer/video-use
   cd ~/Developer/video-use && uv sync
   mkdir -p ~/.claude/skills && ln -sfn ~/Developer/video-use ~/.claude/skills/video-use
   ```
2. Pedir ao usuário a chave do ElevenLabs e gravar em `~/Developer/video-use/.env`
   (`ELEVENLABS_API_KEY=...`, `chmod 600`). Nunca commitar a chave.
   A chave precisa das permissões **Speech to Text**, **Audio Isolation** e, se for usar, **Music** e **Sound Effects**.
3. Domínios liberados na rede do ambiente: `api.elevenlabs.io`, `drive.google.com`, `drive.usercontent.google.com`.
4. Vídeos brutos chegam na pasta **video-use** do Google Drive
   (id `1ooeecva1PgD63rTTvJDyZ8gYN_tDTaVK`). Listar com o conector do Drive e baixar com:
   ```bash
   curl -sSL -o <arquivo> "https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t"
   ```
5. A lista da delegação (nomes e cargos) fica no PDF `Logos/Briefing_Videos_Missao_China_2026.pdf`
   no mesmo Drive. Não fica neste repositório porque ele é público.

## Padrões visuais

| Item | Padrão |
|---|---|
| Formato | 1080×1920, 30 fps, H.264, áudio AAC 48 kHz, −14 LUFS / −1 dBTP |
| Cores | Azul escuro `#005EB8`, azul claro `#40B9FF`, branco |
| Fonte | Inter (ExtraBold / Black nos títulos e legendas) |
| Logo | `horizontal_branco.png`, 300 px, canto superior direito (y=140, mesma linha do selo), 92% opacidade, sombra suave |
| Selo de local | Canto superior esquerdo (y=140), "DIA N · CIDADE", entra deslizando em 0,45 s |
| Cartão de nome | Acima da legenda (y≈1030), nome + cargo · organização, entra em 0,5 s, sai em 0,4 s |
| Legendas | Linha de base a 30% da base (y=1340). Largura máx. 860 px; texto maior encolhe sozinho |
| Texto da legenda | Português escrito: "Cê"→"Você", "dum"→"de um". O áudio fica como foi falado |
| Zona segura Reels | Selo e logo ficam em y=140, acima do rosto (pedido do usuário). Na aba Reels, a barra do app pode encostar neles. Nada importante abaixo de y=1500 nem nos 140 px da direita |

Estilos de legenda em `scripts/kit.py`: **A** caixa alta 2–3 palavras, **B** frase com caixa escura,
**C** karaokê com a palavra falada em `#40B9FF`, **PT+EN** para traduções.

## Selos da missão (horário local)

| Dia | Data | Selo |
|---|---|---|
| 1 | 31/10 | Xangai → Hangzhou |
| 2 | 01/11 | Hangzhou |
| 3 | 02/11 | Hangzhou |
| 4 | 03/11 | Hangzhou |
| 5 | 04/11 | Hangzhou, Wuzhen ou Jiaxing (conforme o local da gravação) |
| 6 | 05/11 | Xangai |
| 7 | 06/11 | Jiaxing |
| 8 | 07/11 | Jiaxing → Xangai |

Antes do Dia 1: vídeo de embarque com `"tag_day": "Embarque", "place": "São Paulo"`
(selo "EMBARQUE · SÃO PAULO"). `tag_day` substitui "Dia N" em qualquer vídeo fora do roteiro.

## Aprovações (27/10/2026)

| Recurso | Decisão |
|---|---|
| Abertura | Cartão de título (símbolo, kicker, título em até 3 linhas, selo do dia), 2,4 s |
| Legenda | **C · karaokê**: caixa alta, 2–3 palavras, palavra falada em `#40B9FF` |
| Selo de local | Sim, nos primeiros 6 s da fala |
| Zoom de corte | Sim, alterna 100% / 118% nas pausas, trechos de no mínimo 2,2 s |
| Cartão de nome | Sim, para quem fala (lista no briefing do Drive) |
| Cor | **Neutra** (correção automática sutil, ±8%) |
| Isolamento de voz | Sim, quando houver ruído (`"isolate_voice": true`). Mistura 25% do som original (`"original_mix"`) + realce de presença, para a voz não ficar abafada |
| Tradução | PT pequeno em cima, EN grande embaixo (`.ass` escrito à mão, passado em `"captions"`) |
| Encerramento | Logo + "Missão China 2026 · SCALE IA" + @sebraestartups e @alexsouzanet, 2,8 s |
| Música | **Nenhuma no arquivo.** Adicionada no app do Instagram (biblioteca livre de direitos), 10–15% do volume da voz |
| Duração | Alvo pedido pelo usuário (30, 60 ou 90 s são os formatos usuais, não um limite) |
| Cortes | **Só entre frases.** Não cortar gaguejos no meio da frase (fica truncado). Folga automática de até 0,2 s antes e 0,3 s depois, sem invadir palavras. Cada corte troca o enquadramento (100% ↔ 118%) |

## Fluxo de cada vídeo

1. Baixar os brutos do Drive para `/root/footage/<pasta>/`.
2. Transcrever: `python ~/Developer/video-use/helpers/transcribe_batch.py /root/footage/<pasta>`.
3. Ler `edit/takes_packed.md` (gerado por `pack_transcripts.py`), propor o corte e **esperar aprovação**.
4. Escrever o JSON do Reel (modelo: `examples/modelo_30s.json`) e rodar:
   `~/Developer/video-use/.venv/bin/python scripts/make_reel.py reel.json` (use `--draft` para conferir cortes).
5. Conferir quadros nos cortes, legendas e volume (−14 LUFS) antes de enviar.
6. Entregar o MP4 na conversa e, se pedido, salvar na pasta **video-use** do Drive.

Opções do JSON além do modelo (ver `examples/embarque_60s.json`):
- `"fixes"`: nomes que a transcrição erra. Token exato vence (`{"Startup,": "Startups,"}` não mexe em "Startup Summit").
  Erros já vistos: Tsinghua, CEIA, Qwen.
- `"isolate_voice": true`: isola a voz do arquivo inteiro uma vez (cache em `edit/isolated/`) e depois corta.
- `"blur_band": [0.72, 0.84]`: desfoca uma faixa da imagem (fração da altura), para esconder legenda antiga gravada no vídeo.
- `"tag_day"`: texto no lugar de "Dia N" (ex.: "Embarque").
