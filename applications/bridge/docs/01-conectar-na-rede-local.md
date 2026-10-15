# Conectar pela rede de casa

## Como conectar

1. Inicie o Bridge no computador.
2. No celular ou notebook, abra o endereço mostrado em **Outros aparelhos**.
3. Dê um nome e toque em **Gerar código de pareamento**.
4. Veja o código de seis dígitos na janela do Bridge Core, digite-o no aparelho
   novo e confirme.

O código vale por 10 minutos, aceita no máximo cinco tentativas e não é mostrado
ao aparelho novo. Cada navegador recebe uma credencial própria depois da
confirmação. O endereço de conexão é o mesmo para todos.

Não use `http://127.0.0.1:8876` no celular. Esse endereço funciona somente no
computador principal.

## Wi-Fi comum e 5 GHz

As faixas de 2,4 GHz e 5 GHz normalmente fazem parte da mesma rede e podem ser
usadas juntas. Se uma delas não funcionar, confira se:

- uma das redes é de convidados;
- o roteador ativou isolamento entre aparelhos;
- as duas redes vêm de roteadores diferentes;
- o Windows classificou a conexão como rede pública.

## Se não abrir

Primeiro confira se os dois aparelhos estão no mesmo roteador e se nenhum deles
usa uma rede de convidados.

Se ainda não abrir, teste no celular:

No celular, abra:

```text
http://IP-DO-COMPUTADOR:8876/api/health
```

Se aparecer `{"status":"ok"}`, o celular alcança o Bridge.

## Se o Windows bloquear

Quando o Windows perguntar, permita o Bridge somente em **Redes privadas**. Se a
pergunta não aparecer, abra o PowerShell como administrador e execute:

```powershell
New-NetFirewallRule -DisplayName 'Bridge Core TCP' -Direction Inbound `
  -Action Allow -Protocol TCP -LocalPort 8876 -Profile Private
```

Não abra essa porta no roteador. Para usar fora de casa, prefira uma rede privada
Tailscale.

## Enviar

Escolha o aparelho, clique em **Enviar arquivo** e selecione o conteúdo. O envio
começa sozinho; o aparelho de destino não precisa confirmar.
