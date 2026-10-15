# Conectar aparelhos distantes com Tailscale

Tailscale cria uma rede privada entre seus aparelhos. O Bridge continua usando o
mesmo protocolo; nenhuma porta precisa ser aberta no roteador.

## 1. Instalar e entrar

1. Instale Tailscale no computador do Core e no aparelho remoto a partir do site
   ou loja oficial.
2. Entre com a mesma conta/tailnet, ou compartilhe apenas a máquina necessária.
3. Confirme que os dois aparelhos aparecem como conectados no painel Tailscale.

No computador do Core:

```powershell
tailscale status
tailscale ip -4
```

Anote o endereço `100.x.y.z`. Se MagicDNS estiver ativo, também pode usar o nome
`nome-do-pc.seu-tailnet.ts.net`.

## 2. Anunciar o endereço correto

Inicie o Core assim:

```powershell
$env:BRIDGE_PUBLIC_URL='http://100.x.y.z:8876'
.\scripts\start.ps1
```

No agente Windows remoto:

```powershell
.\.venv\Scripts\python.exe .\windows-agent\agent.py `
  --server http://100.x.y.z:8876 --pair
```

No Android, informe a mesma URL no campo servidor. Teste antes no navegador:
`http://100.x.y.z:8876/api/health`.

## 3. Firewall e ACL

Você não precisa criar port forwarding. Ainda assim, o firewall local precisa
aceitar TCP 8876 na interface Tailscale. Prefira uma regra limitada ao range:

```powershell
New-NetFirewallRule -DisplayName 'Bridge via Tailscale' -Direction Inbound `
  -Action Allow -Protocol TCP -LocalPort 8876 -RemoteAddress 100.64.0.0/10
```

Em uma tailnet compartilhada, crie ACL/grant que permita somente os seus aparelhos
chegarem à porta 8876. Não use `0.0.0.0/0`.

## 4. Verificar ponta a ponta

```powershell
tailscale ping 100.x.y.z
Test-NetConnection 100.x.y.z -Port 8876
```

Depois, pareie, envie um texto e um arquivo pequeno. O painel deve indicar rede
`tailscale` quando o agente consegue identificá-la. A descoberta UDP não atravessa
Tailscale; use o endereço ou MagicDNS. Isso é esperado.

## HTTPS opcional e recomendado

Dentro da tailnet, `tailscale cert nome.ts.net` pode emitir certificado. Defina:

```powershell
$env:BRIDGE_TLS_CERT='C:\certs\nome.ts.net.crt'
$env:BRIDGE_TLS_KEY='C:\certs\nome.ts.net.key'
$env:BRIDGE_PUBLIC_URL='https://nome.ts.net:8876'
.\scripts\start.ps1
```

Use `https://` também nos agentes. Nunca copie a chave TLS para outro aparelho.
