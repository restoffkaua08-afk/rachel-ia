# Arquitetura de voz da Rachel IA

## Objetivo

Manter uma conversa contínua após um único comando de ativação.

## Pipeline principal

1. Captura contínua do microfone.
2. Silero VAD detecta presença de voz.
3. Smart Turn identifica o encerramento real da frase.
4. whisper.cpp transcreve a fala em português.
5. O núcleo da Rachel interpreta a solicitação.
6. O diretor de voz seleciona ritmo, ênfase e estilo.
7. Chatterbox produz áudio no modo qualidade.
8. Piper produz áudio no modo rápido.
9. Pipecat transmite e controla os turnos.
10. O sistema volta automaticamente ao estado de escuta.

## Estados

- DESATIVADO
- OUVINDO
- TRANSCRIBINDO
- PENSANDO
- FALANDO
- INTERROMPIDO
- RECUPERANDO
- ENCERRANDO

## Regras importantes

- Um clique inicia a sessão.
- Um segundo clique encerra a sessão.
- O microfone permanece ativo durante a sessão.
- A fala do usuário pode interromper a resposta da Rachel.
- A saída de áudio anterior deve ser cancelada após interrupção.
- O texto da conversa deve permanecer visível.
- O usuário pode desabilitar o armazenamento da sessão.
- A voz rápida deve ser usada quando o modo qualidade exceder a latência permitida.
