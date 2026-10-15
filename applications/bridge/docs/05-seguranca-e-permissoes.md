# Segurança, identidade e permissões

## Modelo de confiança atual

Cada Core e agente gera uma chave persistente. No primeiro contato, o Core mostra
um código de seis dígitos somente em sua própria janela. O código vale por 10
minutos, aceita no máximo cinco tentativas e não volta na resposta da API. Depois
da confirmação, o Core emite um token aleatório exclusivo, guarda somente seu
hash e exige autenticação nas APIs e no WebSocket. Comandos nativos também
carregam assinatura Ed25519 do Core, e os agentes rejeitam assinatura inválida.
A revogação invalida imediatamente o ID e o token.

Os seis dígitos são confirmação humana, não senha permanente. O navegador guarda
o token em cookie `HttpOnly`; agentes nativos o guardam em sua configuração
local. Na internet, use Tailscale ou TLS. HTTP puro em Wi-Fi pública permite
interceptação e não deve ser usado.

Depois de atualizar uma instalação anterior a esta versão, pareie cada navegador
e agente uma vez para receber seu token. Registros antigos sem token não conseguem
usar as rotas protegidas.

## Permissões independentes

| Permissão | Efeito | Padrão recomendado |
|---|---|---|
| `clipboard` | ler texto no Windows e enviar | desligada |
| `photos` | receber/oferecer foto escolhida | ligada, ação explícita |
| `remote_ring` | tocar alerta | ligada em aparelhos pessoais |
| `remote_lock` | bloquear sessão/tela | desligada até configurar |
| `screen_share` | aceitar solicitação; OS ainda confirma | ligada para pedidos em web/Windows |
| `remote_control` | injetar mouse/teclado no Windows durante uma sessão aprovada | desligada até configurar |
| `remote_actions` | URL, notificação, pasta permitida | desligada |

Uma permissão no banco não substitui a permissão local. O Windows Agent e o
Android checam novamente antes de executar.

No painel web, cada aparelho só pode alterar as próprias permissões. Para tela,
`screen_share=true` permite receber a solicitação, mas não concede captura
permanente: `getDisplayMedia` abre o seletor do navegador a cada sessão. O
receptor só processa ofertas WebRTC que correspondam a uma solicitação iniciada
por ele, e ambos os lados podem encerrar a conexão.

O controle remoto tem uma segunda autorização local, independente da captura.
O Core cria um token temporário associado ao visualizador, encaminha apenas
eventos normalizados e assinados ao agente Windows e invalida a sessão quando o
vídeo termina. Ele não tenta atravessar UAC ou a tela segura. Para reduzir erro
de coordenadas, o usuário deve compartilhar a tela inteira.

Comandos de URL aceitam apenas endereços completos HTTP(S), limitam o tamanho e
recusam credenciais embutidas. No painel web, o destino vê o endereço e precisa
clicar para abrir uma nova guia; a página do Bridge não é substituída.

## Ações sensíveis

`lock`, `screen_start`, exclusão e alteração de configuração exigem desafio de
uso único com expiração de dois minutos. Solicitação, recusa, envio e resultado
entram no histórico de segurança. Eventos de segurança não podem ser apagados
pela rota comum de limpeza.

## TLS

Defina certificado e chave PEM antes de iniciar:

```powershell
$env:BRIDGE_TLS_CERT='C:\bridge-certs\bridge.crt'
$env:BRIDGE_TLS_KEY='C:\bridge-certs\bridge.key'
$env:BRIDGE_PUBLIC_URL='https://bridge.exemplo:8876'
.\.venv\Scripts\python.exe run.py
```

Certificado autoassinado exige instalar a CA em cada aparelho. Para Tailscale,
prefira `tailscale cert`. Não exponha diretamente o Uvicorn na internet pública;
use proxy TLS, autenticação de usuário, rate limiting e hardening antes.

## Resposta a perda de aparelho

1. Revogue o dispositivo no painel.
2. Desative/remova o aparelho da tailnet Tailscale.
3. Consulte **Histórico > Só segurança**.
4. Se a chave do Core vazou, pare o serviço, guarde logs, substitua
   `.data/identity.pem` e refaça todos os pareamentos.
