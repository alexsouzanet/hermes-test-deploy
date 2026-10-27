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
| Logo | `horizontal_branco.png`, 300 px, canto superior direito, 92% opacidade, sombra suave |
| Selo de local | Canto superior esquerdo, "DIA N · CIDADE", entra deslizando em 0,45 s |
| Cartão de nome | Acima da legenda (y≈1030), nome + cargo · organização, entra em 0,5 s, sai em 0,4 s |
| Legendas | Linha de base a 30% da base (y=1340). Largura máx. 860 px; texto maior encolhe sozinho |
| Texto da legenda | Português escrito: "Cê"→"Você", "dum"→"de um". O áudio fica como foi falado |
| Zona segura Reels | Nada importante acima de y=250, abaixo de y=1500 nem nos 140 px da direita |

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

## Aprovações

Escolhas do usuário a partir do vídeo-catálogo (`examples/build_catalog.py`).
Atualizar esta seção quando ele responder.

- Legenda: _pendente_
- Abertura com cartão de título: _pendente_
- Zoom de corte: _pendente_
- Cor: _pendente_ (padrão provisório: neutra)
- Isolamento de voz: _pendente_
- Música: _pendente_
- Encerramento: _pendente_
