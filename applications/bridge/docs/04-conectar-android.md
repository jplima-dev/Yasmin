# Conectar um aparelho Android

## Estado desta primeira versão

O projeto Kotlin já prova os pontos que dependem de Android: pareamento, serviço
de primeiro plano, bateria/presença, menu Compartilhar para texto/link,
notificações, toque para localizar, bloqueio via Device Admin e consentimento
MediaProjection. Upload binário pelo seletor e streaming WebRTC nativo são
próximos passos; não estão disfarçados como concluídos. Pelo Chrome Android, o
painel já pode assistir e controlar uma tela compartilhada pelo computador.
O Chrome Android não expõe captura da tela do telefone para páginas web; por
isso o celular não aparece como origem de tela no painel.

## 1. Abrir e instalar

1. Abra a pasta `android-app` no Android Studio.
2. Aguarde o Gradle sincronizar e instale os SDKs 28 e 35 se solicitado.
3. Conecte o celular com depuração USB ou escolha um emulador.
4. Execute a configuração `app`.

Para o emulador Android, o PC host é `http://10.0.2.2:8876`. Em aparelho físico na
mesma Wi-Fi, use `http://IP-DO-PC:8876`. A configuração atual aceita cleartext
somente para facilitar desenvolvimento em LAN; produção deve usar HTTPS e uma
network security config restrita.

## 2. Parear

1. Digite a URL do Core e um nome para o aparelho.
2. Toque **Gerar código de pareamento**.
3. Veja os seis dígitos na janela do Bridge Core e digite-os no campo do app.
4. Toque **Confirmar código**.
5. O serviço "Bridge conectado" passa a rodar em primeiro plano.

Depois do primeiro pareamento, o serviço também volta a iniciar após reiniciar o
Android. Alguns fabricantes ainda exigem definir Bridge como **Sem restrições**
na bateria para manter a conexão quando a tela do celular estiver apagada.
O serviço usa o tipo `connectedDevice`, adequado à conexão contínua com outro
aparelho pela rede e sem o limite diário do tipo `dataSync` no Android 15.

Android 13+ pergunta por notificações. Sem essa permissão o serviço ainda pode
conectar, mas ofertas e comandos não terão a experiência prevista.

## 3. Compartilhar texto, link ou clipboard

No app de origem, selecione conteúdo, toque **Compartilhar** e escolha Bridge. O
Android entrega o conteúdo explicitamente à `ShareActivity`, que escolhe o outro
aparelho pareado. O Bridge nunca monitora silenciosamente o clipboard Android.

Para arquivos binários, use por enquanto o painel PWA no Chrome Android. Ele já
faz upload em blocos, progresso e hash. O próximo passo nativo é abrir o `content://`
com `ContentResolver`, ler em chunks e chamar os mesmos endpoints de transferência.

## 4. Permissões especiais

- **Atividade de apps:** o botão abre `Usage Access Settings`. Só conceda se quiser
  mostrar o aplicativo em uso; remova a qualquer momento nas Configurações.
- **Bloqueio remoto:** ativa `Device Admin` para a política `force-lock`. O comando
  ainda exige permissão Bridge, assinatura Ed25519 e confirmação forte no emissor.
- **Ver tela:** Android mostra o diálogo do MediaProjection em toda sessão. A
  implementação não guarda o token e não inicia captura em segundo plano.
- **Controlar o Android:** ainda não está implementado. A versão nativa precisa
  de um `AccessibilityService`, capacidade de gestos, aviso destacado e
  consentimento separado. Acesso à tela e controle são permissões diferentes.
- **Fotos:** não é pedida permissão global. Use o seletor ou menu Compartilhar.

Para revogar tudo: painel Bridge > Ações > Revogar; depois Android > Segurança >
Apps administradores e desative Bridge; por fim desinstale o aplicativo.

## 5. Restrições de bateria

Se o fabricante encerrar o serviço, marque Bridge como "Sem restrições" em
Configurações > Bateria > Bridge. Faça isso apenas se precisar de recebimento em
tempo real. O serviço usa WebSocket com ping de 25 segundos e não faz polling
agressivo.
