# Diagnóstico de conexão

## O painel não abre em outro aparelho

1. No Core, confirme `http://127.0.0.1:8876/api/health`.
2. Confira o IP com `Get-NetIPAddress -AddressFamily IPv4`.
3. No outro Windows, rode `Test-NetConnection IP -Port 8876`.
4. Confirme que a rede do host está como Privada: `Get-NetConnectionProfile`.
5. Revise as regras: `Get-NetFirewallRule -DisplayName 'Bridge*'`.
6. Desative temporariamente VPNs conflitantes, nunca o firewall inteiro.
7. Verifique se o Wi-Fi de convidados isola clientes.

## Descoberta mostra zero pares

UDP broadcast costuma ser bloqueado entre VLANs, Tailscale e redes corporativas.
Isso não impede conexão manual. Use a URL/IP direto. Na mesma LAN, confira UDP
48765 e se ambos estão na mesma sub-rede.

## WebSocket cai repetidamente

- confira se proxy/rede aceita Upgrade WebSocket;
- use `ws://` com HTTP e `wss://` com HTTPS;
- ajuste o endereço salvo em `%LOCALAPPDATA%\Bridge\agent.json`;
- verifique relógio e suspensão de energia dos aparelhos;
- no Android, remova restrição de bateria apenas se necessário.

## API responde 401 depois da atualização

Esta versão exige um token individual nas APIs e no WebSocket. Navegadores e
agentes pareados por versões antigas ainda não possuem esse token. Gere um novo
código no aparelho, digite os seis dígitos mostrados na janela do Bridge Core e
conclua o pareamento uma vez. Não apague `.data` nem `identity.pem`.

## Transferência para em `integrity_failed`

O arquivo temporário fica em `.data/chunks`. Não renomeie manualmente. Repita a
oferta e confira se o cliente calcula SHA-256 sobre os mesmos bytes. O Core nunca
move um arquivo com hash divergente para `received/`.

## Reset controlado

Para desfazer um único aparelho, use **Revogar** e pareie novamente. Para um reset
total de desenvolvimento, pare o Core, faça backup e mova `.data` e `received`
para outro diretório. Não apague a identidade em uma instalação real sem planejar
o novo pareamento de todos os aparelhos.

## Logs e banco

O histórico operacional fica no SQLite `.data/bridge.sqlite3`. Consulte sem
alterar:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('.data/bridge.sqlite3'); print(c.execute('select kind,status,created_at from events order by created_at desc limit 20').fetchall())"
```
