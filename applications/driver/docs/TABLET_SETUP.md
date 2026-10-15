# Instalação completa no tablet Android

Verificado em **21/09/2026** contra a documentação oficial atual do Termux, Android e Tailscale.

> Recomendação: faça a primeira instalação sem R2 e sem Gmail. Primeiro confirme que o tablet serve arquivos pelo Tailscale; depois ative os módulos opcionais.

## 1. Instalar o Termux

### AÇÃO NO ANDROID

Instale o Termux por uma fonte oficial. A documentação do projeto recomenda F-Droid ou os releases oficiais no GitHub. **Não misture Termux e add-ons instalados de fontes/assinaturas diferentes.**

Fonte recomendada para este guia: **F-Droid**.

- Termux: https://f-droid.org/packages/com.termux/
- Projeto oficial: https://github.com/termux/termux-app

Abra o Termux uma vez após instalar.

## 2. Atualizar pacotes

### COMANDO NO TABLET

```bash
pkg update
pkg upgrade
```

Confirme com `y` quando solicitado.

## 3. Instalar Python e Git

### COMANDO NO TABLET

```bash
pkg install python git
```

Teste:

```bash
python --version
git --version
```

O Drive2 requer Python 3.11 ou mais recente.

## 4. Dar acesso ao armazenamento compartilhado

O Drive2 funciona dentro do armazenamento privado do Termux sem esta etapa. Execute-a se quiser permitir que o Termux acesse o armazenamento compartilhado do Android.

### COMANDO NO TABLET

```bash
termux-setup-storage
```

### AÇÃO NO ANDROID

Aceite a permissão de arquivos/mídia mostrada pelo Android. Depois o Termux cria atalhos em:

```text
$HOME/storage/
```

Para a primeira instalação, é mais seguro deixar `DRIVE2_STORAGE_ROOT=data/files`. O SQLite deve continuar em armazenamento privado do Termux, não em uma pasta compartilhada.

## 5. Obter o Drive2

Se o projeto estiver em um repositório Git:

### COMANDO NO TABLET

```bash
cd "$HOME"
git clone <URL_DO_REPOSITORIO> drive2
cd drive2
```

Se você copiou o ZIP manualmente para o tablet, extraia-o e deixe a pasta final como:

```text
$HOME/drive2
```

## 6. Criar ambiente virtual

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Isso instala apenas o núcleo leve. Não instale `requirements-full.txt` ainda se não for usar R2/Gmail.

## 7. Criar o `.env`

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
cp .env.example .env
nano .env
```

Para a primeira execução, deixe pelo menos:

```env
DRIVE2_HOST=0.0.0.0
DRIVE2_PORT=8000
DRIVE2_STORAGE_ROOT=data/files
DRIVE2_TAILSCALE_ONLY=true
R2_ENABLED=false
GMAIL_ENABLED=false
DRIVE2_AUTH_ENABLED=false
```

Salve no `nano` com `Ctrl+O`, Enter e saia com `Ctrl+X`.

## 8. Iniciar o Drive2

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python run.py
```

Deixe essa sessão aberta durante o primeiro teste.

## 9. Testar localmente

### COMANDO NO TABLET

Em outra sessão do Termux:

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/healthcheck.py
```

Esperado:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

Também pode abrir no navegador do próprio tablet:

```text
http://127.0.0.1:8000
```

## 10. Instalar o Tailscale

Veja o passo a passo completo em `docs/TAILSCALE_SETUP.md`.

### AÇÃO NO ANDROID

Instale o app oficial Tailscale pela Google Play Store. O cliente Android atual requer Android 8.0 ou mais recente. Abra o app, aceite a configuração VPN e faça login.

## 11. Descobrir o endereço do tablet

### AÇÃO NO ANDROID

No app Tailscale, localize o endereço `100.x.y.z` do tablet ou o nome do dispositivo.

Também é possível consultar a página **Machines** no admin console do Tailscale.

## 12. Testar pelo computador

### AÇÃO NO COMPUTADOR

Instale Tailscale e entre na **mesma tailnet**. Depois abra:

```text
http://100.x.y.z:8000
```

Com MagicDNS, normalmente também funciona:

```text
http://nome-do-tablet:8000
```

Não abra a porta 8000 no roteador.

Por padrão, `DRIVE2_TAILSCALE_ONLY=true` mantém o FastAPI em `0.0.0.0:8000`, mas o próprio Drive2 rejeita origens que não sejam localhost ou endereços Tailscale. Isso evita que outro aparelho apenas conectado ao mesmo Wi-Fi acesse a interface diretamente. Se precisar testar deliberadamente pela LAN, mude para `false` temporariamente e ative autenticação.

## 13. Manter o servidor ativo

Android pode limitar CPU e rede em segundo plano. Doze/App Standby existem desde Android 6 e fabricantes podem aplicar restrições adicionais.

### AÇÃO NO ANDROID

Abra as configurações de bateria do **Termux** e do **Tailscale** e escolha a opção equivalente a **Sem restrições / Unrestricted**, se seu Android oferecer essa opção. O caminho exato muda por fabricante e versão.

A documentação Android atual descreve os estados `Unrestricted`, `Optimized` e `Restricted`; `Restricted` pode impedir trabalho em segundo plano.

### COMANDO NO TABLET

Para aumentar a confiabilidade enquanto o Termux fica em segundo plano:

```bash
termux-wake-lock
```

Isso aumenta consumo de bateria. Mesmo com wake lock, o Android/OEM ainda pode encerrar processos; por isso a inicialização automática é importante.

## 14. Inicialização automática com Termux:Boot

### AÇÃO NO ANDROID

Instale **Termux:Boot** pela **mesma origem/assinatura do Termux**. Se usou F-Droid para Termux, use F-Droid também para Termux:Boot.

Abra o Termux:Boot **uma vez** pelo ícone depois de instalar; o projeto oficial exige isso para habilitar a execução no boot.

### COMANDO NO TABLET

```bash
mkdir -p "$HOME/.termux/boot"
cp "$HOME/drive2/scripts/termux-boot-drive2" "$HOME/.termux/boot/20-drive2"
chmod +x "$HOME/.termux/boot/20-drive2"
```

O script fornecido assume que o projeto está em `$HOME/drive2`.

Reinicie o tablet e, depois que o Android terminar de iniciar, teste:

```text
http://IP_TAILSCALE:8000
```

## 15. O que acontece se o Android matar o processo

O FastAPI fica indisponível e o scanner/worker param. Nenhum arquivo é considerado sincronizado apenas porque estava em upload: a fila e estados ficam no SQLite e retomam após o servidor voltar.

Se o processo for encerrado, inicie novamente:

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python run.py
```

## 16. Consultar logs

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
tail -f logs/drive2.log
```

Se iniciou pelo Termux:Boot:

```bash
tail -f "$HOME/drive2/logs/boot.log"
```

Ver processo:

```bash
ps -ef | grep '[r]un.py'
```

## 17. Atualizar o Drive2

Antes, faça backup do banco.

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/backup_db.py
git pull
pip install -r requirements.txt
```

Se usa R2/Gmail, reinstale o arquivo de requisitos correspondente.

Reinicie o servidor.

## 18. Backup do SQLite

### COMANDO NO TABLET

```bash
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/backup_db.py
```

As cópias ficam em `backups/`.

## 19. Restaurar o SQLite

Pare o Drive2 antes.

### COMANDO NO TABLET

```bash
pkill -f 'python.*run.py' || true
cd "$HOME/drive2"
source .venv/bin/activate
python scripts/restore_db.py backups/drive2-AAAAMMDD-HHMMSS.db
python run.py
```

## 20. Instalar módulos opcionais depois

R2:

```bash
source .venv/bin/activate
pip install -r requirements-cloud.txt
```

Gmail:

```bash
source .venv/bin/activate
pip install -r requirements-gmail.txt
```

Tudo:

```bash
source .venv/bin/activate
pip install -r requirements-full.txt
```

## Fontes oficiais

- Termux: https://github.com/termux/termux-app
- Termux:Boot: https://github.com/termux/termux-boot
- Android Doze/App Standby: https://developer.android.com/training/monitoring-device-state/doze-standby
- Android background optimization: https://developer.android.com/topic/performance/background-optimization
- Tailscale Android: https://tailscale.com/docs/install/android
