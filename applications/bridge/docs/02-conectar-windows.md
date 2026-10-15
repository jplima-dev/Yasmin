# Conectar um computador Windows

## Pré-requisitos

- Bridge Core iniciado em algum computador acessível;
- Python 3.11 ou superior e dependências instaladas por `scripts/setup.ps1`;
- perfil de rede Windows marcado como **Privado** quando estiver em casa.

## Parear o agente

No computador que receberá o agente, copie a pasta do projeto ou apenas
`windows-agent` junto do ambiente/dependências. No PowerShell:

```powershell
cd C:\caminho\para\bridge
.\.venv\Scripts\python.exe .\windows-agent\agent.py `
  --server http://IP-MOSTRADO-PELO-BRIDGE:8876 --pair
```

Quando o agente pedir o código, veja os seis dígitos na janela do Bridge Core,
digite-os no terminal do agente e aguarde "Computador adicionado ao Bridge".
O código vale por 10 minutos e não é devolvido ao agente. A configuração e o
token individual do aparelho vão para:

```text
%LOCALAPPDATA%\Bridge\agent.json
%LOCALAPPDATA%\Bridge\identity.pem
```

Proteja e faça backup de `identity.pem`. Apagá-lo cria outra identidade e exige
novo pareamento.

## Autorizar funções separadamente

O arquivo `agent.json` começa conservador. Edite somente a função desejada:

```json
{
  "permissions": {
    "remote_ring": true,
    "remote_lock": false,
    "screen_share": false,
    "remote_control": false,
    "remote_actions": false,
    "photos": false,
    "clipboard": false
  }
}
```

Reinicie o agente após alterar. O painel também mantém uma cópia das permissões;
as duas camadas devem permitir a ação. Para clipboard PC para Android:

```powershell
.\.venv\Scripts\python.exe .\windows-agent\agent.py --enable-clipboard
```

Isso é opt-in. O agente lê apenas texto, limita o conteúdo a 200 mil caracteres e
manda ao primeiro Android pareado. Para desligar, defina `clipboard_enabled` e a
permissão `clipboard` como `false`.

## Inicialização automática

Teste o agente em primeiro plano antes. Depois abra PowerShell como administrador:

```powershell
.\windows-agent\install-startup.ps1 -EnableScreenShare -EnableRemoteControl
Get-ScheduledTask -TaskName 'Bridge Agent'
```

A tarefa usa `pythonw.exe` do `.venv`, inicia no logon e reinicia após falha. Para
remover:

```powershell
Unregister-ScheduledTask -TaskName 'Bridge Agent' -Confirm:$false
```

## Ações nativas

- **Tocar som:** usa `Beep`; não exige permissão administrativa.
- **Bloquear:** chama `LockWorkStation` somente com `remote_lock=true` e comando
  assinado após confirmação de uso único.
- **Abrir URL:** aceita apenas HTTP(S).
- **Abrir pasta:** limita o caminho ao perfil do usuário; não executa comandos.
- **Ver tela pelo agente:** o agente recebe a solicitação mesmo com Chrome
  fechado e mostra uma notificação com **Abrir Bridge**. Ao clicar, o painel é
  aberto e assume a sessão; então o navegador pede qual tela ou janela deve ser
  compartilhada. Nada é capturado antes desses cliques locais.
- **Controle remoto:** depois da notificação, marque a autorização separada no
  painel e escolha **Tela inteira**. O agente aceita somente eventos assinados da
  sessão ativa. O acesso acaba ao parar o vídeo e não controla UAC, tela de
  bloqueio nem outras áreas seguras do Windows.

## Compartilhar tela pelo painel

1. No computador, abra `http://127.0.0.1:8876` no Chrome ou Edge.
2. Em **Conexões > Compartilhamento de tela**, mantenha os pedidos permitidos.
3. No aparelho que assistirá, abra **Ações** do dispositivo `web` e toque em
   **Ver tela**. Se Chrome estiver fechado, escolha o dispositivo `windows` e
   toque em **Pedir tela por notificação**.
4. No computador, clique em **Compartilhar agora** e escolha a tela ou janela.
   Para também controlar, marque a caixa de mouse/teclado e escolha a tela inteira.

O vídeo usa `RTCPeerConnection`, sem passar pelo banco ou pela pasta `received`.
Cada sessão exige consentimento local. HTTP por um IP comum não libera
`getDisplayMedia`; por isso o computador transmissor deve abrir o painel por
`127.0.0.1` ou HTTPS. O aparelho que assiste pode usar o IP da LAN/Tailscale.

## Empacotar como EXE

O EXE é opcional. Durante o desenvolvimento, prefira executar `agent.py`, pois
cada alteração já vale na próxima execução. Um EXE antigo não recebe mudanças do
código; ele precisa ser gerado novamente.

Depois dos testes:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe --onefile --name BridgeAgent `
  .\windows-agent\agent.py
```

O resultado fica em `dist\BridgeAgent.exe`. A janela deve continuar visível
enquanto o primeiro cadastro pedir o código. Não use `--noconsole` até existir
uma tela própria para digitar o código e configurar o agente.

Assine o executável com um certificado de code-signing antes de distribuição
pública para reduzir alertas do SmartScreen.
