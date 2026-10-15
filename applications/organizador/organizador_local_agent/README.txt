ORGANIZADOR LOCAL - AGENTE (launcher corrigido)
===============================================

ARQUIVOS QUE DEVEM FICAR NA RAIZ DO PROJETO:
- organizer_agent.pyw
- abrir-organizador.cmd
- diagnostico.cmd
- requirements.txt
- package.json  <- o package.json do SEU projeto Vite

NO SRC DO SEU PROJETO:
- src/organizer-presence.js

No ponto de entrada do Vite (por exemplo src/main.js, src/main.jsx ou src/main.ts),
importe UMA vez:

    import "./organizer-presence.js";

USO NORMAL
----------
Dê dois cliques em abrir-organizador.cmd.

O launcher agora:
1. detecta py/python;
2. verifica/instala websockets se estiver faltando;
3. inicia o agente escondido;
4. espera a porta 5173 realmente ficar acessível;
5. só então abre http://127.0.0.1:5173/#/dashboard.

Se der erro, o CMD permanece aberto e mostra o problema em vez de falhar em
silêncio.

DIAGNÓSTICO
-----------
Se ainda houver problema, dê dois cliques em diagnostico.cmd.
Ele mostra Python, websockets, package.json, npm e executa o agente com o console
visível.

COMPORTAMENTO
-------------
- O agente gera o build e inicia `npm.cmd run serve`, sem recarga automática.
- `npm.cmd run dev` fica reservado ao desenvolvimento com hot reload.
- O site se conecta ao agente por WebSocket.
- Fechar a última aba inicia os 3 minutos.
- Reabrir dentro dos 3 minutos cancela o desligamento.
- Após 3 minutos, o servidor fecha.
- O agente Python continua leve e assume 127.0.0.1:5173 para poder acordar o
  Organizador quando o endereço for aberto novamente.
