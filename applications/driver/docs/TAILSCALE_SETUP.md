# Configuração do Tailscale

Verificado em **21/09/2026** contra a documentação oficial do Tailscale.

## 1. Criar a tailnet

### AÇÃO NO COMPUTADOR

Acesse https://tailscale.com/ e selecione **Get Started**. Entre com um provedor SSO compatível. Ao cadastrar o primeiro dispositivo, a sua rede privada Tailscale (tailnet) é criada.

## 2. Instalar no tablet

### AÇÃO NO ANDROID

Instale Tailscale pela Google Play Store ou pela página oficial de download. O cliente atual suporta Android 8.0 ou mais recente.

Abra o app:

1. toque em **Get Started**;
2. aceite a criação da configuração VPN;
3. entre com a mesma identidade usada na tailnet.

O tablet deverá aparecer na página **Machines** do admin console.

## 3. Instalar no computador

### AÇÃO NO COMPUTADOR

Instale o cliente oficial correspondente ao seu sistema em:

https://tailscale.com/download

Entre na mesma tailnet.

## 4. Identificar o tablet

### AÇÃO NO COMPUTADOR

Na página **Machines**, localize o tablet. Anote:

- nome da máquina;
- endereço Tailscale `100.x.y.z`;
- nome DNS completo, se desejar.

## 5. Testar conectividade

Com o Drive2 rodando no tablet em `0.0.0.0:8000` e `DRIVE2_TAILSCALE_ONLY=true`:

### AÇÃO NO COMPUTADOR

No navegador:

```text
http://100.x.y.z:8000
```

Se o comando Tailscale estiver disponível no computador:

```bash
tailscale ping nome-do-tablet
```

Um `ping` ICMP comum pode ser bloqueado pelo sistema; `tailscale ping` é o teste preferível quando disponível.

## 6. MagicDNS

MagicDNS registra nomes para os dispositivos da tailnet e está disponível em todos os planos. Segundo a documentação atual, tailnets criadas desde 20/10/2022 já vêm com MagicDNS habilitado por padrão.

Com MagicDNS ativo, tente:

```text
http://nome-do-tablet:8000
```

Se não funcionar, confirme a configuração na página **DNS** do admin console.

## 7. Segurança

O Drive2 inclui um filtro próprio de origem:

```env
DRIVE2_TAILSCALE_ONLY=true
```

Quando ativo, somente localhost e as faixas oficiais usadas pelos endereços de dispositivos Tailscale são aceitas (`100.64.0.0/10` e `fd7a:115c:a1e0::/48`). O servidor ainda pode escutar em `0.0.0.0`, mas uma conexão direta da LAN, como `192.168.x.x`, recebe `403`.

Se desativar esse filtro para usar o Drive2 pela LAN, habilite a autenticação interna e trate aquela rede como uma superfície adicional de acesso.

Não abra a porta 8000 no roteador. Tailscale cria conexão privada entre dispositivos e evita expor o FastAPI diretamente à internet.

Se outras pessoas/dispositivos participarem da mesma tailnet, ative também a autenticação interna do Drive2 (`docs/SECURITY.md`) e considere regras de acesso do Tailscale.

## 8. Problemas comuns

### Tablet aparece offline

- abra o app Tailscale;
- confirme que a VPN está conectada;
- retire Tailscale do modo de bateria `Restricted`;
- confirme internet no tablet.

### Tailscale funciona, mas porta 8000 não abre

No Termux:

```bash
curl http://127.0.0.1:8000/api/health
```

Se local funciona, confirme `.env`:

```env
DRIVE2_HOST=0.0.0.0
DRIVE2_PORT=8000
```

Reinicie o Drive2.

### Nome MagicDNS não resolve

Use temporariamente o IP `100.x.y.z` e confira a página DNS/MagicDNS no admin console.

## 9. Dispositivo perdido

### AÇÃO NO COMPUTADOR

No admin console:

1. abra **Machines**;
2. encontre o dispositivo;
3. abra o menu `…`;
4. selecione **Remove**;
5. confirme **Remove machine**.

A documentação atual informa que a remoção corta imediatamente o acesso do dispositivo aos recursos da tailnet.

## Fontes oficiais

- Android: https://tailscale.com/docs/install/android
- Quickstart: https://tailscale.com/docs/how-to/quickstart
- MagicDNS: https://tailscale.com/docs/features/magicdns
- Remover dispositivo: https://tailscale.com/docs/features/access-control/device-management/how-to/remove
- Endereços Tailscale: https://tailscale.com/docs/concepts/tailscale-ip-addresses
- IPv6 Tailscale: https://tailscale.com/docs/concepts/ipv6
