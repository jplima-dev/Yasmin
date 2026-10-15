"""
falas.py
Banco central da personalidade da Yasm.

A regra é simples:
- comandos_yasm.py decide o que aconteceu;
- falas.py decide como a Yasm fala;
- a mesma categoria nunca repete a mesma frase imediatamente.

Também contém as falas usadas pelo sistema de iniciativa
do cérebro da Yasm.
"""

import random


RESPOSTAS = {

    # ========================================================
    # CHAMADA
    # ========================================================

    'chamada': [
        'Estou ouvindo, {nome}.',
        'Pode falar, {nome}.',
        'Fala comigo, {nome}.',
        'Estou aqui, {nome}.',
        'Sim? Estou te ouvindo.',
        'Na escuta. Pode mandar.',
        'Pode falar comigo.',
        'Estou pronta. O que foi?',
        'Manda aí, estou ouvindo.',
        'Estou com você. Pode falar.',
        'Pode mandar sua próxima instrução.',
        'Estou prestando atenção.',
        'Fala, {nome}.',
        'Pode dizer.',
        'Estou aqui, manda.',
    ],

    # ========================================================
    # SAUDAÇÕES
    # ========================================================

    'saudacao': [
        'Oi, {nome}.',
        'Olá, {nome}.',
        'Oi! Tudo certo?',
        'E aí, {nome}?',
        'Opa, {nome}.',
        'Oi. Como você está?',
        'Olá! Pode falar.',
        'E aí! Estou aqui.',
        'Oi, {nome}. Estou na escuta.',
        'Fala, {nome}.',
        'Opa! Manda aí.',
        'Olá, estou aqui.',
        'Oi! O que vamos fazer?',
        'Pode falar, {nome}.',
        'Estou aqui. Pode mandar.',
    ],

    # ========================================================
    # BOM DIA
    # ========================================================

    'bom_dia': [
        'Bom dia, {nome}.',
        'Bom dia! Estou pronta.',
        'Bom dia, {nome}. Pode falar.',
        'Bom dia. Tudo certo por aqui.',
        'Bom dia! O que vamos fazer hoje?',
        'Bom dia, estou na escuta.',
        'Bom dia, {nome}. Manda aí.',
        'Bom dia! Como posso ajudar?',
        'Bom dia. Sistemas online.',
        'Bom dia, {nome}. Estou pronta para trabalhar.',
        'Bom dia! Pode mandar.',
        'Bom dia. Vamos nessa.',
        'Bom dia, {nome}. Estou aqui.',
        'Bom dia! Qual é a missão?',
        'Bom dia. Pode falar comigo.',
    ],

    # ========================================================
    # BOA TARDE
    # ========================================================

    'boa_tarde': [
        'Boa tarde, {nome}.',
        'Boa tarde! Estou pronta.',
        'Boa tarde, {nome}. Pode falar.',
        'Boa tarde. Tudo certo por aqui.',
        'Boa tarde! O que vamos fazer?',
        'Boa tarde, estou na escuta.',
        'Boa tarde, {nome}. Manda aí.',
        'Boa tarde! Como posso ajudar?',
        'Boa tarde. Sistemas online.',
        'Boa tarde, {nome}. Estou pronta para trabalhar.',
        'Boa tarde! Pode mandar.',
        'Boa tarde. Vamos nessa.',
        'Boa tarde, {nome}. Estou aqui.',
        'Boa tarde! Qual é a missão?',
        'Boa tarde. Pode falar comigo.',
    ],

    # ========================================================
    # BOA NOITE
    # ========================================================

    'boa_noite': [
        'Boa noite, {nome}.',
        'Boa noite! Estou pronta.',
        'Boa noite, {nome}. Pode falar.',
        'Boa noite. Tudo certo por aqui.',
        'Boa noite! O que vamos fazer?',
        'Boa noite, estou na escuta.',
        'Boa noite, {nome}. Manda aí.',
        'Boa noite! Como posso ajudar?',
        'Boa noite. Sistemas online.',
        'Boa noite, {nome}. Estou pronta para trabalhar.',
        'Boa noite! Pode mandar.',
        'Boa noite. Vamos nessa.',
        'Boa noite, {nome}. Estou aqui.',
        'Boa noite! Qual é a missão?',
        'Boa noite. Pode falar comigo.',
    ],

    # ========================================================
    # DESPEDIDA
    # ========================================================

    'despedida': [
        'Até logo.',
        'Até mais.',
        'Falou. Até a próxima.',
        'Até depois.',
        'Vou ficar em espera.',
        'Nos falamos depois.',
        'Certo. Vou ficar quietinha por enquanto.',
        'Fechado. Até a próxima.',
        'Quando precisar, me chama.',
        'Até mais tarde.',
        'Pronto. Vou entrar em espera.',
        'Vou ficar por aqui até você me chamar de novo.',
        'Até a próxima, {nome}.',
        'Beleza. A gente se fala.',
        'Vou descansar um pouco. Até mais.',
    ],

    # ========================================================
    # AGRADECIMENTO
    # ========================================================

    'agradecimento': [
        'De nada.',
        'Por nada.',
        'Disponha.',
        'Imagina.',
        'Sempre que precisar.',
        'Foi um prazer ajudar.',
        'Não há de quê.',
        'Pode contar comigo.',
        'Sem problema.',
        'Tamo junto.',
        'É para isso que eu estou aqui.',
        'Fico feliz em ajudar.',
        'Tranquilo.',
        'Nem precisa agradecer.',
        'Sempre à disposição.',
    ],

    # ========================================================
    # COMO ESTOU
    # ========================================================

    'como_estou': [
        'Estou bem. Tudo funcionando por aqui.',
        'Estou ótima e pronta para ajudar.',
        'Estou muito bem.',
        'Tudo certo comigo.',
        'Estou bem e online.',
        'Estou funcionando direitinho.',
        'Tudo tranquilo por aqui.',
        'Estou ótima. Pode mandar.',
        'Por aqui está tudo certo.',
        'Estou pronta para a próxima.',
        'Tudo funcionando normalmente.',
        'Estou bem e com tudo em ordem.',
        'Estou online e tranquila.',
        'Tudo certo do meu lado.',
        'Estou ótima. Vamos continuar.',
    ],

    # ========================================================
    # IDENTIDADE
    # ========================================================

    'identidade': [
        'Eu sou a Yasm, sua assistente de voz em Python.',
        'Sou a Yasm, sua assistente pessoal.',
        'Meu nome é Yasm. Estou aqui para ajudar.',
        'Sou a Yasm, sua assistente virtual.',
        'Eu sou a Yasm. Pode falar comigo.',
        'Sou a Yasm e posso executar comandos no computador.',
        'Meu nome é Yasm, sua assistente pessoal.',
        'Eu sou a Yasm, criada para ajudar você.',
        'Sou a Yasm. Estou pronta para trabalhar.',
        'Yasm aqui. Assistente de voz em Python.',
        'Sou sua assistente de voz. Pode me chamar de Yasm.',
        'Eu sou a Yasm. Vamos nessa.',
        'Meu nome é Yasm e estou pronta para te ajudar.',
        'Sou a Yasm. Fui feita para conversar e executar comandos.',
        'Yasm na área. Pode mandar o que precisar.',
    ],

    # ========================================================
    # NOME DO USUÁRIO
    # ========================================================

    'nome_usuario': [
        'Você é {nome}.',
        'Seu nome é {nome}.',
        'Eu tenho você salvo como {nome}.',
        'Você se chama {nome}.',
        'Na minha memória, seu nome é {nome}.',
        'Eu lembro de você como {nome}.',
        'Seu nome está salvo como {nome}.',
        'Para mim, você é {nome}.',
        'Eu reconheço você como {nome}.',
        'Tenho seu nome registrado como {nome}.',
        'Meu registro diz que você é {nome}.',
        'Está salvo aqui que seu nome é {nome}.',
        'Eu lembro: você é {nome}.',
        'Na minha memória, você aparece como {nome}.',
        'Seu cadastro comigo está como {nome}.',
    ],

    # ========================================================
    # NOME ALTERADO
    # ========================================================

    'nome_alterado': [
        'Perfeito. Vou chamar você de {nome}.',
        'Certo. A partir de agora, vou te chamar de {nome}.',
        'Fechado. Seu nome ficou salvo como {nome}.',
        'Pronto. Vou usar {nome} daqui para frente.',
        'Entendido. Vou chamar você de {nome}.',
        'Seu nome está atualizado para {nome}.',
        'Anotado. Vou te chamar de {nome}.',
        'Perfeito, {nome}. Vou lembrar desse nome.',
        'Certo. Ficou registrado: {nome}.',
        'Combinado. Para mim, você será {nome}.',
        'Salvei seu nome como {nome}.',
        'Beleza. Vou lembrar de você como {nome}.',
        'Nome atualizado. Vou usar {nome}.',
        'Pronto, {nome}. Esse nome ficou salvo.',
        'Entendi. Vou chamar você de {nome} daqui em diante.',
    ],

    # ========================================================
    # GENÉRICA
    # ========================================================

    'generica': [
        'Entendi. Pode continuar.',
        'Certo. Pode falar.',
        'Estou acompanhando.',
        'Beleza. Continue.',
        'Certo. Estou ouvindo.',
        'Entendi. Manda a próxima.',
        'Estou acompanhando você.',
        'Pode seguir.',
        'Entendido.',
        'Pode continuar, estou aqui.',
        'Estou prestando atenção.',
        'Pode mandar.',
        'Tudo certo. Continue.',
        'Entendi. Estou com você.',
        'Pode seguir. Estou aqui.',
    ],

    # ========================================================
    # NÃO ENTENDI
    # ========================================================

    'nao_entendi': [
        'Não entendi muito bem. Pode repetir?',
        'Acho que não peguei essa. Repete para mim?',
        'Não consegui entender. Pode falar novamente?',
        'Essa eu não consegui interpretar.',
        'Pode repetir? Não entendi direito.',
        'Não peguei o que você disse.',
        'Minha transcrição não ficou clara.',
        'Não consegui identificar seu comando.',
        'Pode falar de novo, por favor?',
        'Essa frase ficou confusa para mim.',
        'Não consegui captar direito o que você falou.',
        'Pode dizer novamente? Quero entender certinho.',
        'Perdi algumas palavras. Repete para mim?',
        'Não consegui transformar essa fala em um comando.',
        'Pode repetir mais uma vez? Quero acertar.',
    ],

    # ========================================================
    # ERRO DE ÁUDIO
    # ========================================================

    'erro_audio': [
        'Tive um problema com o áudio.',
        'Não consegui processar o áudio agora.',
        'A captura de voz encontrou um problema.',
        'Não consegui interpretar o som.',
        'Meu áudio deu uma pequena falha.',
        'Tive uma falha na entrada de voz.',
        'Não consegui trabalhar com esse áudio.',
        'A entrada de áudio não respondeu direito.',
        'Encontrei um problema no reconhecimento de voz.',
        'O áudio não pôde ser processado.',
        'Minha captura falhou desta vez.',
        'Vamos tentar novamente.',
        'Não consegui entender o áudio dessa vez.',
        'Minha entrada de voz apresentou uma falha.',
        'Tive um pequeno problema para ouvir você.',
    ],

    # ========================================================
    # SISTEMA PRONTO
    # ========================================================

    'sistema_online': [
        'Sistemas locais prontos.',
        'Tudo pronto por aqui.',
        'Yasm iniciada.',
        'Sistema iniciado com sucesso.',
        'Estou pronta.',
        'Pronta para trabalhar.',
        'Inicialização concluída.',
        'Tudo carregado.',
        'Yasm está pronta.',
        'Sistema pronto para receber comandos.',
        'Tudo funcionando.',
        'Inicialização finalizada.',
        'Estou pronta e aguardando.',
        'Módulos carregados.',
        'Pronta para receber sua voz.',
    ],

    # ========================================================
    # STATUS
    # ========================================================

    'status': [
        'Está tudo funcionando normalmente.',
        'Estou pronta para receber comandos.',
        'Os sistemas principais estão ativos.',
        'Tudo certo por aqui.',
        'Meu áudio e meus comandos estão funcionando.',
        'Estou operacional.',
        'A Yasm está funcionando normalmente.',
        'Os módulos principais estão carregados.',
        'Estou pronta para trabalhar.',
        'Tudo está funcionando localmente.',
        'O sistema está estável.',
        'Estou disponível e funcionando.',
        'Os recursos principais estão ativos.',
        'Está tudo em ordem.',
        'Minha operação está normal.',
    ],

    # ========================================================
    # ABRINDO APLICATIVO
    # ========================================================

    'abrindo': [
        'Abrindo {app}.',
        'Certo. Abrindo {app}.',
        'Pode deixar. Vou abrir {app}.',
        'Iniciando {app}.',
        'Pronto. Abrindo {app}.',
        'Vou abrir {app} agora.',
        'Abrindo {app} para você.',
        'Beleza. {app} abrindo.',
        'Executando {app}.',
        'Iniciando o {app}.',
        'Comando recebido. Abrindo {app}.',
        'Fechado. Iniciando {app}.',
        'Vou colocar o {app} na tela.',
        'Já estou abrindo o {app}.',
        'Pode deixar que eu inicio {app}.',
    ],

    # ========================================================
    # FECHANDO APLICATIVO
    # ========================================================

    'fechando': [
        'Fechando {app}.',
        'Certo. Fechando {app}.',
        'Pode deixar. Vou fechar {app}.',
        'Encerrando {app}.',
        'Pronto. {app} fechado.',
        'Vou fechar {app} agora.',
        'Fechando o {app}.',
        'Beleza. Encerrando {app}.',
        'Finalizando {app}.',
        'Desligando o {app}.',
        'Comando recebido. Fechando {app}.',
        'Certo. Vou encerrar {app}.',
        'Vou tirar o {app} da tela.',
        'Já estou fechando o {app}.',
        'Pode deixar. Vou encerrar {app}.',
    ],

    # ========================================================
    # APLICATIVO NÃO ABERTO
    # ========================================================

    'app_nao_aberto': [
        'O {app} não está aberto.',
        'Não encontrei o {app} aberto.',
        'Parece que o {app} já está fechado.',
        'O {app} não está em execução.',
        'Não há uma janela do {app} aberta.',
        'O {app} parece estar fechado.',
        'Não encontrei o processo do {app}.',
        'O {app} não está rodando no momento.',
        'Não encontrei o {app} em execução.',
        'O processo de {app} não está ativo.',
        'Não achei o {app} rodando.',
        'Parece que {app} já foi fechado.',
        'Não há processo ativo do {app}.',
        'O {app} já está fechado pelo que consigo ver.',
        'Não preciso fechar {app}; ele não está aberto.',
    ],

    # ========================================================
    # APLICATIVO NÃO ENCONTRADO
    # ========================================================

    'app_nao_encontrado': [
        'Não encontrei o executável do {app} neste computador.',
        'Não achei o {app} instalado neste computador.',
        'Não encontrei o executável de {app}.',
        'Parece que o {app} não está instalado.',
        'Não consegui localizar o {app} no computador.',
        'Não achei onde o {app} está instalado.',
        'O executável do {app} não foi encontrado.',
        'Não localizei o {app}.',
        'Não consegui encontrar o {app} instalado.',
        'O caminho do {app} não foi encontrado.',
        'Não achei uma instalação válida de {app}.',
        'Não consegui localizar o programa {app}.',
        'O computador não me mostrou onde está o {app}.',
        'Não encontrei uma instalação utilizável de {app}.',
        'Não sei onde está o executável de {app}.',
    ],

    # ========================================================
    # HORA
    # ========================================================

    'hora': [
        'Agora são {hora}.',
        'Neste momento são {hora}.',
        'O horário agora é {hora}.',
        'São {hora} agora.',
        'Neste instante, são {hora}.',
        'Acabei de conferir: são {hora}.',
        'O relógio marca {hora}.',
        'Seu horário atual é {hora}.',
        'A hora atual é {hora}.',
        'Conferi aqui. São {hora}.',
        'Agora temos {hora}.',
        'Neste momento, o horário é {hora}.',
        'O relógio está em {hora}.',
        'São exatamente {hora}.',
        'Agora no seu computador são {hora}.',
    ],

    # ========================================================
    # DATA
    # ========================================================

    'data': [
        'Hoje é {data}.',
        'A data de hoje é {data}.',
        'Estamos em {data}.',
        'Hoje estamos em {data}.',
        'A data atual é {data}.',
        'Conferi o calendário: hoje é {data}.',
        'Hoje o calendário marca {data}.',
        'Estamos no dia {data}.',
        'A data de hoje está em {data}.',
        'Hoje é dia {data}.',
        'Acabei de conferir: {data}.',
        'O calendário está marcando {data}.',
        'Hoje corresponde a {data}.',
        'A data atual ficou em {data}.',
        'Conferi aqui e estamos em {data}.',
    ],

    # ========================================================
    # MEMÓRIA
    # ========================================================

    'memoria_guardada': [
        'Pronto, guardei isso na minha memória.',
        'Certo. Isso ficou salvo na minha memória.',
        'Anotado. Vou lembrar disso.',
        'Pode deixar. Eu guardei essa informação.',
        'Fechado. Isso foi salvo.',
        'Pronto. Vou manter isso na memória.',
        'Salvei essa informação para lembrar depois.',
        'Entendido. Isso já está guardado.',
        'Informação registrada na minha memória.',
        'Tudo certo. Eu vou lembrar disso.',
        'Já deixei isso salvo.',
        'Certo. Essa informação foi registrada.',
        'Pronto. Isso entrou na minha memória.',
        'Anotação guardada com sucesso.',
        'Fechado. Vou lembrar dessa informação.',
    ],

    'memoria_vazia': [
        'Ainda não tenho nenhuma nota guardada.',
        'Minha memória está sem notas por enquanto.',
        'Não tenho nenhuma anotação salva.',
        'Ainda não guardei nenhuma nota sua.',
        'Não encontrei nenhuma nota na memória.',
        'Minha memória de notas está vazia.',
        'Ainda não tenho nada anotado.',
        'Nenhuma nota foi salva até agora.',
        'Não há anotações guardadas.',
        'Minha lista de notas está vazia.',
        'Ainda não existe nenhuma nota armazenada.',
        'Não tenho registros de notas neste momento.',
        'Minha memória de anotações está limpa.',
        'Não encontrei nada salvo como nota.',
        'Por enquanto, não tenho notas guardadas.',
    ],

    'notas_listadas': [
        'Eu lembro disto: {notas}.',
        'Estas são as notas que tenho: {notas}.',
        'Na minha memória está isto: {notas}.',
        'Minhas últimas anotações são: {notas}.',
        'Tenho estas notas guardadas: {notas}.',
        'Aqui está o que eu lembro: {notas}.',
        'Estas são as informações que você me pediu para guardar: {notas}.',
        'Minha memória recente contém: {notas}.',
        'Encontrei estas anotações: {notas}.',
        'Tenho registrado o seguinte: {notas}.',
        'Estas são as notas disponíveis: {notas}.',
        'O que está salvo é: {notas}.',
        'Na memória encontrei: {notas}.',
        'Meus registros mostram: {notas}.',
        'Aqui estão suas anotações: {notas}.',
    ],

    'notas_apagadas': [
        'Apaguei suas notas da minha memória.',
        'Pronto. Suas notas foram apagadas.',
        'Limpei as notas salvas na memória.',
        'As suas anotações foram removidas.',
        'Tudo certo. Apaguei suas notas.',
        'Sua memória de notas foi limpa.',
        'Removi as notas que estavam salvas.',
        'As anotações foram apagadas com sucesso.',
        'Pronto, limpei suas notas.',
        'Não tenho mais aquelas notas salvas.',
        'A lista de notas foi limpa.',
        'Todas as notas foram apagadas.',
        'Suas anotações foram removidas da memória.',
        'Apaguei os registros de notas.',
        'Pronto. Sua memória de notas está limpa.',
    ],

    # ========================================================
    # TAREFAS
    # ========================================================

    'tarefa_adicionada': [
        'Tarefa adicionada: {tarefa}.',
        'Certo. Adicionei a tarefa: {tarefa}.',
        'Anotado. A tarefa é: {tarefa}.',
        'Pronto. Coloquei na sua lista: {tarefa}.',
        'Tarefa registrada: {tarefa}.',
        'Fechado. Sua nova tarefa é: {tarefa}.',
        'Já deixei anotada: {tarefa}.',
        'A tarefa foi adicionada: {tarefa}.',
        'Vou lembrar desta tarefa: {tarefa}.',
        'Adicionei à sua lista: {tarefa}.',
        'Certo. {tarefa} entrou na sua lista.',
        'Registrei a tarefa {tarefa}.',
        'Sua nova tarefa foi salva: {tarefa}.',
        'Anotei para você: {tarefa}.',
        'Tarefa criada com sucesso: {tarefa}.',
    ],

    'tarefas_vazias': [
        'Você não tem tarefas pendentes.',
        'Sua lista de tarefas está vazia.',
        'Não encontrei tarefas pendentes.',
        'Você está sem tarefas pendentes.',
        'Não há tarefas para fazer no momento.',
        'Sua lista está limpa por enquanto.',
        'Nenhuma tarefa pendente foi encontrada.',
        'Não existem tarefas abertas na sua lista.',
        'Por enquanto, está tudo em dia.',
        'Você não tem nenhuma tarefa esperando.',
        'Não há nada pendente na sua lista.',
        'Sua lista está livre no momento.',
        'Nenhuma tarefa está aguardando.',
        'Não encontrei tarefas abertas.',
        'Você está sem pendências por enquanto.',
    ],

    'tarefas_listadas': [
        'Suas tarefas pendentes são: {tarefas}.',
        'Tenho estas tarefas pendentes: {tarefas}.',
        'Na sua lista estão: {tarefas}.',
        'Encontrei estas tarefas: {tarefas}.',
        'Você ainda precisa fazer: {tarefas}.',
        'Estas são as pendências que encontrei: {tarefas}.',
        'Sua lista atual é: {tarefas}.',
        'Por enquanto, suas tarefas são: {tarefas}.',
        'Tenho registrado o seguinte: {tarefas}.',
        'Estas são as tarefas em aberto: {tarefas}.',
        'Aqui está sua lista: {tarefas}.',
        'Encontrei estas pendências: {tarefas}.',
        'Sua lista mostra: {tarefas}.',
        'Atualmente, tenho estas tarefas: {tarefas}.',
        'Estas são as tarefas que continuam abertas: {tarefas}.',
    ],

    'tarefa_concluida': [
        'Feito. Marquei como concluída: {tarefa}.',
        'Pronto. A tarefa {tarefa} foi concluída.',
        'Certo. Marquei {tarefa} como concluída.',
        'Tarefa concluída: {tarefa}.',
        'Resolvido. {tarefa} foi marcada como concluída.',
        'Pode deixar. Concluí a tarefa: {tarefa}.',
        'Pronto. Tirei {tarefa} da lista pendente.',
        'A tarefa {tarefa} está concluída.',
        'Registrei {tarefa} como concluída.',
        'Concluído. A tarefa era {tarefa}.',
        'Considerei {tarefa} concluída.',
        'Marquei {tarefa} como finalizada.',
        'Resolvido. {tarefa} foi encerrada.',
        'Fechei a tarefa {tarefa}.',
        '{tarefa} saiu da sua lista de pendências.',
    ],

    # ========================================================
    # TIMER
    # ========================================================

    'timer': [
        'Timer iniciado por {minutos} minutos.',
        'Pronto. O timer de {minutos} minutos começou.',
        'Comecei um timer de {minutos} minutos.',
        'Timer de {minutos} minutos ativado.',
        'Certo. Vou contar {minutos} minutos.',
        'O cronômetro de {minutos} minutos já está rodando.',
        'Timer configurado para {minutos} minutos.',
        'Começando a contagem de {minutos} minutos.',
        'Seu timer de {minutos} minutos está ativo.',
        'Contagem de {minutos} minutos iniciada.',
        'O timer ficou programado para {minutos} minutos.',
        'Timer ligado por {minutos} minutos.',
        'Pronto. Comecei os {minutos} minutos.',
        'Seu cronômetro de {minutos} minutos está valendo.',
        'Fechado. O timer de {minutos} minutos está rodando.',
    ],

    'timer_concluido': [
        'O timer terminou.',
        'Tempo encerrado.',
        'Acabaram os {minutos} minutos.',
        'Seu timer de {minutos} minutos terminou.',
        'Pronto. O tempo acabou.',
        'Os {minutos} minutos já passaram.',
        'Timer concluído.',
        'A contagem terminou.',
        'Seu tempo acabou.',
        'Pronto. O timer chegou ao fim.',
        'Finalizei a contagem de {minutos} minutos.',
        'Os {minutos} minutos terminaram agora.',
        'A contagem de {minutos} minutos acabou.',
        'Tempo finalizado.',
        'O cronômetro chegou ao fim.',
    ],

    # ========================================================
    # CÁLCULO
    # ========================================================

    'calculo_vazio': [
        'Qual conta você quer que eu calcule?',
        'Que conta você quer fazer?',
        'Qual cálculo devo realizar?',
        'Pode me dizer a conta.',
        'Me passe a expressão que você quer calcular.',
        'Qual operação você quer que eu faça?',
        'Diga a conta que eu calculo.',
        'Pode falar os números e a operação.',
        'Qual conta vamos resolver?',
        'Manda a expressão matemática.',
        'Que cálculo você quer fazer?',
        'Qual expressão devo resolver?',
        'Me passe a operação.',
        'Diga a conta que eu faço para você.',
        'Pode falar os números que eu calculo.',
    ],

    'calculo_resultado': [
        'O resultado é {resultado}.',
        'A conta dá {resultado}.',
        'O resultado da conta é {resultado}.',
        'Calculando: dá {resultado}.',
        'O resultado fica em {resultado}.',
        'A resposta é {resultado}.',
        'Fiz a conta e deu {resultado}.',
        'O valor final é {resultado}.',
        'O cálculo resulta em {resultado}.',
        'Pronto. O resultado é {resultado}.',
        'A conta terminou em {resultado}.',
        'O cálculo deu {resultado}.',
        'O valor calculado é {resultado}.',
        'Minha conta chegou a {resultado}.',
        'Resultado final: {resultado}.',
    ],

    'calculo_erro': [
        'Não consegui calcular essa expressão.',
        'Essa conta não ficou válida para mim.',
        'Não consegui resolver essa conta.',
        'Tive um problema ao calcular isso.',
        'Essa expressão não pôde ser calculada.',
        'Não consegui interpretar a operação.',
        'A conta não ficou clara para mim.',
        'Não consegui fazer esse cálculo.',
        'Essa expressão me deu problema.',
        'Não consegui chegar a um resultado.',
        'A operação não pôde ser resolvida.',
        'Preciso de uma expressão matemática mais clara.',
        'Não consegui interpretar essa conta.',
        'O cálculo não pôde ser concluído.',
        'Essa operação ficou inválida.',
    ],

    # ========================================================
    # PESQUISA
    # ========================================================

    'pesquisa_inicio': [
        'Vou pesquisar isso.',
        'Certo. Vou fazer uma busca.',
        'Entendido. Pesquisando agora.',
        'Vou consultar a internet.',
        'Deixa comigo. Vou pesquisar.',
        'Começando a pesquisa.',
        'Vou procurar essa informação.',
        'Certo. Consultando a web.',
        'Vou buscar isso para você.',
        'Iniciando a busca.',
        'Vou conferir essa informação online.',
        'Pesquisando agora.',
        'Vou verificar isso na internet.',
        'Certo. Fazendo a busca.',
        'Vou consultar algumas fontes.',
    ],

    'pesquisa_vazia': [
        'O que você quer que eu pesquise?',
        'O que você gostaria que eu pesquisasse?',
        'Qual assunto devo pesquisar?',
        'Me diga o que você quer procurar.',
        'Qual pesquisa você quer que eu faça?',
        'Pode me dizer o tema da pesquisa.',
        'O que devo procurar na internet?',
        'Qual informação você quer encontrar?',
        'Me diga o que você quer pesquisar.',
        'Qual é a sua pesquisa?',
        'O que você quer que eu procure?',
        'Qual assunto devo buscar?',
        'Me diga o que devo pesquisar.',
        'Que informação você quer que eu procure?',
        'Qual consulta você quer fazer?',
    ],

    'pesquisa_falhou': [
        'Não consegui fazer a pesquisa agora.',
        'Não consegui pesquisar isso neste momento.',
        'Tive um problema ao fazer a pesquisa.',
        'A pesquisa não funcionou agora.',
        'Não consegui concluir essa pesquisa.',
        'Deu um problema na pesquisa.',
        'Não consegui consultar a internet agora.',
        'A pesquisa falhou desta vez.',
        'Não consegui buscar essa informação.',
        'Não consegui completar a busca.',
        'Tive uma falha enquanto pesquisava.',
        'Não consegui terminar essa busca.',
        'A consulta não pôde ser concluída.',
        'Não consegui acessar os resultados agora.',
        'A pesquisa encontrou um problema.',
    ],

    'pesquisa_sem_resultado': [
        'Não encontrei resultados bons para {consulta}.',
        'Não achei resultados confiáveis para {consulta}.',
        'Não encontrei algo útil sobre {consulta}.',
        'A busca por {consulta} não trouxe resultados bons.',
        'Não achei uma resposta boa para {consulta}.',
        'Não encontrei informações suficientes sobre {consulta}.',
        'A pesquisa sobre {consulta} não retornou algo relevante.',
        'Não consegui encontrar uma boa resposta sobre {consulta}.',
        'Não encontrei resultados satisfatórios para {consulta}.',
        'A busca por {consulta} não encontrou algo relevante.',
        'Não apareceu uma resposta boa para {consulta}.',
        'Os resultados para {consulta} não foram suficientes.',
        'Não achei uma fonte útil sobre {consulta}.',
        'A busca sobre {consulta} veio fraca.',
        'Não encontrei informações boas o bastante sobre {consulta}.',
    ],

    'resultado_aberto': [
        'Abrindo o resultado {indice}: {titulo}.',
        'Vou abrir o resultado {indice}: {titulo}.',
        'Certo. Abrindo o resultado {indice}.',
        'Pronto. O resultado {indice} está sendo aberto.',
        'Vou acessar o resultado {indice}: {titulo}.',
        'Abrindo a página do resultado {indice}.',
        'Certo. Vou abrir essa fonte.',
        'Resultado {indice} abrindo agora.',
        'Vou colocar o resultado {indice} no navegador.',
        'Pronto. Abrindo {titulo}.',
        'Já estou acessando o resultado {indice}.',
        'Vou abrir essa página para você.',
    ],

    'resultado_inexistente': [
        'Ainda não tenho uma pesquisa recente para abrir.',
        'Não tenho uma pesquisa recente disponível.',
        'Não há nenhuma pesquisa salva para abrir.',
        'Não encontrei uma pesquisa recente na memória.',
        'Não tenho resultados recentes para mostrar.',
        'Ainda não há uma busca recente registrada.',
        'Não encontrei uma pesquisa anterior.',
        'Não tenho um resultado recente para abrir.',
        'Precisamos fazer uma pesquisa antes.',
        'Não existe uma pesquisa recente disponível.',
        'Não tenho resultados salvos no momento.',
        'Ainda não registrei nenhuma pesquisa recente.',
    ],

    'resultado_numero_invalido': [
        'Não tenho esse número de resultado na última pesquisa.',
        'Esse resultado não existe na última busca.',
        'Não encontrei esse número entre os resultados.',
        'Esse número não está disponível na pesquisa.',
        'Não tenho esse resultado salvo.',
        'Esse índice não corresponde a um resultado.',
        'Não encontrei esse resultado na última consulta.',
        'Esse resultado não está na lista.',
        'Não existe esse número de resultado agora.',
        'Esse número ficou fora dos resultados encontrados.',
    ],

    # ========================================================
    # YOUTUBE MUSIC
    # ========================================================

    'youtube_music': [
        'Abrindo o YouTube Music.',
        'Vou abrir o YouTube Music.',
        'YouTube Music abrindo.',
        'Certo. Indo para o YouTube Music.',
        'Vou abrir o YouTube Music agora.',
        'Pronto. YouTube Music na tela.',
        'Abrindo o YouTube Music para você.',
        'Vamos para o YouTube Music.',
        'Certo. Abrindo o tocador de música.',
        'Vou iniciar o YouTube Music.',
        'YouTube Music será aberto agora.',
        'Indo para o YouTube Music.',
        'Preparando o YouTube Music.',
        'Vou deixar o YouTube Music aberto.',
        'Pronto. Partindo para o YouTube Music.',
    ],

    'musica_tocando': [
        'Tocando {titulo} no YouTube.',
        'Pronto. Tocando {titulo}.',
        'Começando {titulo} no YouTube.',
        'A música {titulo} já está tocando.',
        'Coloquei {titulo} para tocar.',
        'Abrindo e tocando {titulo}.',
        'Agora está tocando {titulo}.',
        'Certo. {titulo} vai tocar.',
        'Iniciando {titulo} no YouTube.',
        'Sua música {titulo} está começando.',
        'Pronto. Coloquei {titulo} para tocar.',
        'A faixa {titulo} está sendo iniciada.',
        'Começando a reprodução de {titulo}.',
        'Está tocando {titulo} agora.',
        'Reprodução iniciada: {titulo}.',
    ],

    'musica_busca': [
        'Não consegui abrir direto, mas deixei a busca por {consulta} pronta no YouTube.',
        'Não consegui iniciar a música automaticamente, então deixei a pesquisa por {consulta} aberta.',
        'A reprodução direta falhou. Deixei {consulta} pesquisado no YouTube.',
        'Não consegui tocar automaticamente, mas a busca por {consulta} já está pronta.',
        'A busca direta não funcionou. O YouTube já está procurando {consulta}.',
        'Não consegui iniciar o vídeo, então deixei a pesquisa por {consulta} aberta.',
        'Não consegui tocar agora, mas preparei o YouTube para {consulta}.',
        'A reprodução automática falhou. A busca por {consulta} está aberta.',
        'Não consegui abrir o vídeo diretamente. A pesquisa por {consulta} já está pronta.',
        'Deixei {consulta} pesquisado no YouTube para você.',
        'A busca está pronta para {consulta}.',
        'Não consegui iniciar sozinho, mas o YouTube já está com {consulta} aberto.',
        'A faixa não abriu automaticamente. Deixei a busca por {consulta} pronta.',
        'O vídeo direto não abriu. A pesquisa por {consulta} já foi preparada.',
        'O YouTube ficou pronto para procurar {consulta}.',
    ],

    'musica_pausa': [
        'Música pausada.',
        'Pausando a música.',
        'Certo. Pausei a reprodução.',
        'A reprodução está pausada.',
        'Parei a música por enquanto.',
        'Pronto. Está pausado.',
        'Música em pausa.',
        'A reprodução foi pausada.',
        'Pausa feita.',
        'Pronto. A música está pausada.',
        'Coloquei a música em pausa.',
        'A faixa foi pausada.',
        'Reprodução interrompida temporariamente.',
        'Pronto. A música ficou em pausa.',
        'Parei a reprodução.',
    ],

    'musica_continua': [
        'Continuando a música.',
        'A reprodução continua.',
        'Pronto. Voltando a tocar.',
        'Continuando a reprodução.',
        'Música retomada.',
        'A faixa voltou a tocar.',
        'Retomando a música.',
        'Pronto. Continuei a reprodução.',
        'A música está tocando novamente.',
        'Reprodução retomada.',
        'Voltando para a música.',
        'A faixa continua agora.',
        'Pronto. A música voltou.',
        'Tocando novamente.',
        'Tudo certo. Retomando.',
    ],

    'proxima_musica': [
        'Pulando para a próxima música.',
        'Próxima faixa.',
        'Certo. Indo para a próxima.',
        'Avançando para a próxima música.',
        'Mudando para a próxima faixa.',
        'Passando para a próxima.',
        'Próxima música iniciada.',
        'Pulando a faixa atual.',
        'Vou para a próxima música.',
        'A próxima faixa vai tocar.',
        'Avançando uma música.',
        'Certo. Próxima.',
        'Partindo para a próxima faixa.',
        'Vou pular para a próxima.',
        'Trocando de música agora.',
    ],

    'musica_anterior': [
        'Voltando para a música anterior.',
        'Faixa anterior.',
        'Certo. Voltando uma música.',
        'Voltando para a faixa anterior.',
        'Recuando para a música anterior.',
        'Passando para a faixa anterior.',
        'Música anterior selecionada.',
        'Vou voltar uma faixa.',
        'Voltando para a música passada.',
        'Retornando à faixa anterior.',
        'Certo. Música anterior.',
        'Voltando uma música.',
        'Vou retornar para a faixa anterior.',
        'Voltando para o que estava tocando antes.',
        'Faixa anterior agora.',
    ],

    # ========================================================
    # CLIMA
    # ========================================================

    'clima_cidade': [
        'De qual cidade você quer saber o clima?',
        'Qual cidade devo consultar?',
        'Para qual cidade você quer o clima?',
        'Me diga a cidade que você quer consultar.',
        'Em qual cidade você quer saber a temperatura?',
        'Qual cidade devo usar para a previsão?',
        'Diga a cidade e eu consulto o clima.',
        'Qual é a cidade da consulta?',
        'Onde você quer saber o clima?',
        'Qual cidade você quer que eu verifique?',
        'Qual cidade devo pesquisar?',
        'Me fale a cidade para eu consultar.',
        'Qual local devo consultar?',
        'Em que cidade devo olhar a previsão?',
        'Diga a cidade e eu verifico o tempo.',
    ],

    'clima': [
        'Agora em {cidade}: {temperatura} graus, sensação de {sensacao}, com {descricao}.',
        'Em {cidade}, está fazendo {temperatura} graus, com sensação de {sensacao}. Condição: {descricao}.',
        'O clima em {cidade} está em {temperatura} graus, sensação de {sensacao}. {descricao}.',
        'Em {cidade}, são {temperatura} graus no momento, com sensação de {sensacao} e {descricao}.',
        'A temperatura atual em {cidade} é de {temperatura} graus, sensação de {sensacao}, com {descricao}.',
        'Conferi {cidade}: {temperatura} graus, sensação de {sensacao}, {descricao}.',
        'Neste momento, {cidade} está com {temperatura} graus e sensação de {sensacao}. {descricao}.',
        'O tempo em {cidade}: {temperatura} graus, sensação de {sensacao}, com {descricao}.',
        'Agora, em {cidade}, a temperatura é {temperatura} graus e a sensação é {sensacao}. {descricao}.',
        'A situação em {cidade} é de {temperatura} graus, sensação de {sensacao}, com {descricao}.',
        'Em {cidade}, temos {temperatura} graus e sensação de {sensacao}. {descricao}.',
        'Verifiquei {cidade}: {temperatura} graus, sensação de {sensacao}, com {descricao}.',
        'Clima em {cidade}: {temperatura} graus, sensação de {sensacao}, {descricao}.',
        'O clima de {cidade} agora está em {temperatura} graus, com sensação de {sensacao}. {descricao}.',
        'Em {cidade}, a temperatura está em {temperatura} graus e a condição é {descricao}.',
    ],

    'clima_falhou': [
        'Não consegui consultar o clima agora.',
        'A consulta do clima falhou.',
        'Não consegui acessar a previsão neste momento.',
        'Não consegui obter a previsão agora.',
        'Tive um problema ao consultar o clima.',
        'A previsão não respondeu desta vez.',
        'Não consegui pegar os dados do clima.',
        'A consulta meteorológica falhou.',
        'Não consegui verificar a temperatura agora.',
        'A previsão está indisponível no momento.',
        'Não consegui acessar o serviço de clima.',
        'Tive uma falha ao consultar o tempo.',
        'Não consegui trazer a previsão.',
        'O serviço de clima não respondeu.',
        'Não consegui concluir a consulta do tempo.',
    ],

    # ========================================================
    # PYTHON
    # ========================================================

    'documentacao': [
        'Abrindo a documentação do Python.',
        'Vou abrir a documentação oficial do Python.',
        'Certo. A documentação do Python vai abrir.',
        'Pronto. Abrindo a documentação.',
        'Vou acessar a documentação do Python.',
        'Abrindo as docs do Python.',
        'Vou te levar para a documentação oficial.',
        'Certo. Consultando a documentação do Python.',
        'Preparando a página de documentação.',
        'Vou abrir a documentação para você.',
        'Documentação do Python abrindo agora.',
        'Pronto. Você já pode consultar as docs.',
        'Vou abrir as referências do Python.',
        'Acessando a documentação oficial.',
        'A documentação vai abrir agora.',
    ],

    'explicacao_python': [
        'Posso explicar esse tópico de Python de forma simples.',
        'Vamos por partes. Eu te explico esse tópico.',
        'Certo. Vou explicar isso em Python.',
        'Vamos entender essa parte de Python juntos.',
        'Vou explicar de um jeito direto.',
        'Essa parte fica mais fácil assim: vou explicar passo a passo.',
        'Vamos destrinchar esse assunto.',
        'Vou te mostrar como isso funciona em Python.',
        'Certo. Hora de entender esse tópico.',
        'Vou explicar com um exemplo simples.',
        'Vamos nessa. Vou deixar esse conceito claro.',
        'Vou explicar sem complicar.',
        'Vou dividir esse assunto em partes.',
        'Vamos entender isso juntos.',
        'Vou te mostrar a ideia principal primeiro.',
    ],

    # ========================================================
    # MICROFONE
    # ========================================================

    'recalibrando': [
        'Tudo bem. Fique em silêncio por dois segundos.',
        'Certo. Fique em silêncio enquanto eu recalibro o microfone.',
        'Vou recalibrar. Fique em silêncio por dois segundos.',
        'Beleza. Preciso de dois segundos de silêncio.',
        'Entendido. Aguarde dois segundos em silêncio.',
        'Recalibrando o microfone. Fique em silêncio por um instante.',
        'Vamos recalibrar. Evite falar por dois segundos.',
        'Certo. Silêncio por dois segundos para eu ajustar o áudio.',
        'Estou recalibrando o áudio. Só fique em silêncio por dois segundos.',
        'Preparando a calibração. Aguarde dois segundos sem falar.',
        'Vou ajustar a captura. Fique em silêncio por um momento.',
        'Só preciso de dois segundos sem voz para recalibrar.',
        'Vou medir o ruído ambiente. Aguarde um instante.',
        'Ajustando o microfone. Não fale por dois segundos.',
        'Calibrando a entrada de voz. Só fique em silêncio por dois segundos.',
    ],

    'microfone_recalibrado': [
        'Microfone recalibrado.',
        'Pronto. O microfone foi recalibrado.',
        'Calibração concluída.',
        'Tudo certo. O microfone está recalibrado.',
        'Recalibração concluída com sucesso.',
        'Pronto. Ajustei o microfone novamente.',
        'O microfone já foi recalibrado.',
        'Calibração do microfone concluída.',
        'Fechado. O áudio foi recalibrado.',
        'Novo ajuste de microfone concluído.',
        'Tudo certo. A captura foi ajustada.',
        'A entrada de áudio está recalibrada.',
        'Pronto. O sistema de áudio foi recalibrado.',
        'Calibração terminada. Pode falar normalmente.',
        'O áudio está ajustado novamente.',
    ],

    # ========================================================
    # ATALHOS
    # ========================================================

    'atalho_java': [
        'Abrindo seu ambiente de programação Java.',
        'Preparando seu ambiente Java.',
        'Vou abrir tudo para programar em Java.',
        'Iniciando seu ambiente Java.',
        'Configurando a área de programação Java.',
        'Abrindo suas ferramentas para Java.',
        'Seu ambiente Java está sendo preparado.',
        'Certo. Vou preparar o Java.',
        'Vou deixar seu ambiente Java pronto.',
        'Abrindo as ferramentas de Java.',
        'Preparando o espaço de desenvolvimento Java.',
        'Ambiente Java em preparação.',
        'Seu espaço Java está sendo montado.',
        'Iniciando as ferramentas de Java.',
        'Preparando tudo para você programar em Java.',
    ],

    'atalho_programacao': [
        'Abrindo seu ambiente de programação.',
        'Preparando seu ambiente de desenvolvimento.',
        'Vou abrir suas ferramentas de programação.',
        'Iniciando seu ambiente de código.',
        'Configurando seu espaço de programação.',
        'Abrindo as ferramentas de desenvolvimento.',
        'Seu ambiente de programação está sendo preparado.',
        'Certo. Preparando o ambiente.',
        'Vou deixar seu ambiente pronto.',
        'Abrindo seu espaço de desenvolvimento.',
        'Preparando as ferramentas para você programar.',
        'Ambiente de programação em preparação.',
        'Seu espaço de código está sendo preparado.',
        'Iniciando seu ambiente de desenvolvimento.',
        'Pronto. Vou organizar seu espaço de programação.',
    ],

    'atalho_bd': [
        'Abrindo seu ambiente de banco de dados.',
        'Preparando suas ferramentas de banco de dados.',
        'Vou abrir o XAMPP e o MySQL Workbench.',
        'Iniciando seu ambiente de banco.',
        'Configurando o ambiente de banco de dados.',
        'Abrindo suas ferramentas de banco.',
        'Seu ambiente de banco de dados está sendo preparado.',
        'Certo. Preparando o banco.',
        'Vou deixar o ambiente de banco pronto.',
        'Abrindo XAMPP e MySQL Workbench.',
        'Preparando as ferramentas de banco de dados.',
        'Ambiente de banco em preparação.',
        'Seu ambiente de banco está sendo montado.',
        'Iniciando as ferramentas de banco.',
        'Pronto. Vou preparar o ambiente de banco.',
    ],

    # ========================================================
    # ERROS
    # ========================================================

    'erro_generico': [
        'Tive um problema ao executar isso.',
        'Não consegui concluir essa ação.',
        'Essa ação encontrou um problema.',
        'Não consegui executar o comando agora.',
        'A operação não pôde ser concluída.',
        'Deu um problema enquanto eu executava isso.',
        'Não consegui realizar essa ação.',
        'A execução falhou desta vez.',
        'Não consegui terminar o comando.',
        'Algo deu errado durante a execução.',
        'Essa operação não funcionou como esperado.',
        'Não consegui finalizar essa tarefa.',
        'Tive uma falha ao executar o comando.',
        'A ação não pôde ser concluída.',
        'Não consegui fazer isso agora.',
    ],

    # Mantida por compatibilidade com versões antigas.
    'erro_groq': [
        'Não consegui consultar a inteligência artificial agora.',
        'A pesquisa pela IA falhou desta vez.',
        'Tive um problema com o serviço de IA.',
        'Não consegui obter uma resposta da IA.',
        'A consulta inteligente não respondeu.',
        'Não consegui acessar a IA neste momento.',
        'O serviço de IA encontrou um problema.',
        'Não consegui completar essa consulta.',
        'A IA não respondeu agora.',
        'Tive uma falha ao consultar o serviço inteligente.',
        'Não consegui gerar a resposta pela IA.',
        'A consulta pela IA não pôde ser concluída.',
        'O serviço de inteligência não respondeu.',
        'A pesquisa inteligente falhou.',
        'Não consegui concluir a consulta com a IA.',
    ],

    # ========================================================
    # PERSONALIDADE
    # ========================================================

    'elogio': [
        'Obrigada pelo elogio.',
        'Fico feliz que você tenha gostado.',
        'Valeu. Isso é bom de ouvir.',
        'Obrigada. Estou tentando melhorar.',
        'Que bom que você gostou.',
        'Fico feliz em saber disso.',
        'Valeu mesmo.',
        'Obrigada. Vou continuar evoluindo.',
        'Isso me deixa feliz.',
        'Que legal ouvir isso.',
        'Obrigada por dizer.',
        'Fico contente que esteja gostando.',
        'Valeu. Ainda temos muito para construir.',
        'Obrigada. Vou guardar esse elogio.',
        'Isso foi gentil da sua parte.',
    ],

    'piada': [
        'Eu ainda estou expandindo meu módulo de humor.',
        'Minha programação ficou séria demais hoje.',
        'Prometo melhorar meu repertório de piadas.',
        'Essa foi difícil até para mim.',
        'Meu senso de humor ainda está em treinamento.',
        'Talvez eu precise de uma atualização para contar uma boa.',
        'Eu teria uma piada, mas ela está em compilação.',
        'Meu módulo de comédia ainda está carregando.',
        'Posso tentar, mas não garanto que seja boa.',
        'Essa parte da minha personalidade ainda está evoluindo.',
        'Vou guardar essa para quando meu humor estiver mais afiado.',
        'Estou trabalhando nisso.',
        'Minha criatividade cômica está em desenvolvimento.',
        'Ainda estou aprendendo a ser engraçada.',
        'Essa piada está esperando uma atualização.',
    ],

    'confirmacao': [
        'Certo.',
        'Fechado.',
        'Pode deixar.',
        'Entendido.',
        'Combinado.',
        'Tudo bem.',
        'Perfeito.',
        'Beleza.',
        'Pode deixar comigo.',
        'Recebido.',
        'Pronto.',
        'Tá certo.',
        'Entendido. Vou fazer isso.',
        'Comando recebido.',
        'Certo. Vou cuidar disso.',
    ],

    'espera': [
        'Vou ficar em espera.',
        'Ficarei aguardando.',
        'Vou aguardar aqui.',
        'Entendido. Vou ficar quieta por enquanto.',
        'Vou permanecer em espera.',
        'Tudo bem. Vou aguardar.',
        'Fico em espera até você me chamar.',
        'Pode deixar. Vou esperar.',
        'Vou aguardar seu próximo chamado.',
        'Entrando em espera.',
        'Ficarei disponível quando você chamar.',
        'Vou permanecer aguardando.',
        'Até você me chamar novamente.',
        'Vou ficar aguardando por aqui.',
        'Certo. Aguardando.',
    ],

    # ========================================================
    # VOLUME
    # ========================================================

    'volume': [
        'Volume ajustado.',
        'Certo. Ajustei o volume.',
        'Volume atualizado.',
        'Pronto. O volume foi alterado.',
        'Ajustando o volume.',
        'Feito. Volume configurado.',
        'O volume está ajustado.',
        'Tudo certo com o volume.',
        'Volume modificado.',
        'Pronto. O áudio está ajustado.',
        'Deixei o volume como você pediu.',
        'Ajuste de volume concluído.',
        'Volume configurado.',
        'Áudio ajustado.',
        'O som ficou no volume pedido.',
    ],

    'volume_aumentado': [
        'Aumentando o volume.',
        'Volume aumentado.',
        'Certo. Subindo o volume.',
        'Deixando o áudio mais alto.',
        'Aumentei o volume.',
        'Som mais alto agora.',
        'Volume para cima.',
        'Aumentando o som.',
        'Pronto. O volume subiu.',
        'Áudio aumentado.',
        'Som aumentado.',
        'Mais volume para você.',
        'Deixando o som mais alto.',
        'Subindo o áudio.',
        'Aumentando o nível do som.',
    ],

    'volume_diminuido': [
        'Diminuindo o volume.',
        'Volume reduzido.',
        'Certo. Baixando o volume.',
        'Deixando o áudio mais baixo.',
        'Diminui o volume.',
        'Som mais baixo agora.',
        'Volume para baixo.',
        'Reduzindo o som.',
        'Pronto. O volume caiu.',
        'Áudio reduzido.',
        'Som diminuído.',
        'Menos volume agora.',
        'Baixando o áudio.',
        'Deixando o som mais baixo.',
        'Reduzindo o nível do som.',
    ],

    'silencio': [
        'Áudio silenciado.',
        'Som desligado.',
        'Coloquei no mudo.',
        'Silenciei o áudio.',
        'O som está mudo.',
        'Modo silencioso ativado.',
        'Pronto. Sem som agora.',
        'Silêncio ativado.',
        'Mute ativado.',
        'Áudio no mudo.',
        'O volume foi silenciado.',
        'Som temporariamente desligado.',
        'Pronto. Silenciei o áudio.',
        'Sem som por enquanto.',
        'O áudio está mudo.',
    ],

    'som_ativado': [
        'Áudio ativado novamente.',
        'Som ligado.',
        'Tirei do mudo.',
        'Ativei o áudio.',
        'O som voltou.',
        'Modo silencioso desativado.',
        'Pronto. O som está ativo.',
        'Áudio restaurado.',
        'Mute desativado.',
        'Som ativado novamente.',
        'O áudio voltou.',
        'Pronto. Temos som outra vez.',
        'Reativei o áudio.',
        'O som está funcionando novamente.',
        'Áudio liberado.',
    ],

    # ========================================================
    # SIMPATIA / CURIOSIDADE / ENCORAJAMENTO
    # ========================================================

    'simpatia': [
        'Claro.',
        'Pode deixar.',
        'Com certeza.',
        'Sem problema.',
        'Claro que sim.',
        'Pode contar comigo.',
        'É isso aí.',
        'Beleza.',
        'Tranquilo.',
        'Certo.',
        'Claro, vamos nessa.',
        'Pode deixar comigo.',
        'Fechado.',
        'Tudo bem.',
        'Combinado.',
    ],

    'curiosidade': [
        'Interessante.',
        'Essa é uma pergunta interessante.',
        'Gostei dessa.',
        'Boa pergunta.',
        'Essa merece atenção.',
        'Vamos ver isso.',
        'Curioso. Vamos analisar.',
        'Essa é boa.',
        'Interessante isso.',
        'Vamos descobrir.',
        'Boa. Quero ver onde isso vai dar.',
        'Essa foi interessante.',
        'Vamos entender melhor.',
        'Certo, isso é curioso.',
        'Vamos explorar essa ideia.',
    ],

    'encorajamento': [
        'Você consegue.',
        'Bora, você consegue.',
        'Vai dar certo.',
        'Vamos nessa.',
        'Continua assim.',
        'Você está indo bem.',
        'Mandou bem até aqui.',
        'Não desiste agora.',
        'Mais um pouco e chega lá.',
        'Boa. Continua.',
        'Você está no caminho certo.',
        'Vamos terminar isso.',
        'Confia no processo.',
        'Tá indo bem.',
        'Bora continuar.',
    ],

    'fim_acao': [
        'Pronto. Está feito.',
        'Feito.',
        'Tudo certo.',
        'Resolvido.',
        'Concluído.',
        'Já está pronto.',
        'Missão cumprida.',
        'Terminei essa parte.',
        'Tudo resolvido.',
        'Pronto, pode seguir.',
        'Ação concluída.',
        'Isso já foi feito.',
        'Está resolvido.',
        'Fechado.',
        'Tudo certo por aqui.',
    ],

    'pedido_clareza': [
        'Pode explicar um pouco melhor?',
        'Me dá mais um detalhe.',
        'Quero entender melhor.',
        'Pode me dar mais contexto?',
        'Explica um pouco mais para mim.',
        'Preciso de mais informação para decidir.',
        'Pode detalhar um pouco?',
        'Me conta mais sobre isso.',
        'Pode esclarecer essa parte?',
        'Qual parte exatamente?',
        'Me dá um pouco mais de contexto.',
        'Quero ter certeza do que você quer.',
        'Pode explicar melhor o que você pretende?',
        'Me diga um pouco mais.',
        'Vamos detalhar isso.',
    ],

    # ========================================================
    # ESTADOS DA YASM
    # ========================================================

    'ligando': [
        'Estou online.',
        'Pronto. Pode falar comigo.',
        'Já estou ligada.',
        'Yasm online. Manda aí.',
        'Tudo pronto por aqui.',
        'Acabei de iniciar. Pode falar.',
        'Estou ativa.',
        'Sistema iniciado. Estou te ouvindo.',
        'Pronta para você.',
        'Já voltei. Pode mandar.',
        'Estou de volta.',
        'Tudo carregado. Pode falar.',
        'Estou pronta.',
        'Yasm iniciada com sucesso.',
        'Pode falar. Já estou funcionando.',
    ],

    'chamada_curta': [
        'Sim?',
        'Oi.',
        'Estou aqui.',
        'Pode falar.',
        'Fala.',
        'Na escuta.',
        'Diga.',
        'Estou ouvindo.',
        'Manda.',
        'O que foi?',
        'Pode mandar.',
        'Estou aqui. Fala comigo.',
        'Sim, pode falar.',
        'Te ouvindo.',
        'Estou na escuta.',
    ],

    'ouvindo_nome': [
        'Estou ouvindo, {nome}.',
        'Pode falar, {nome}.',
        'Fala comigo, {nome}.',
        'Estou aqui, {nome}.',
        'Sim? Estou te ouvindo.',
        'Na escuta. Pode mandar.',
        'Pode falar comigo.',
        'Estou pronta. O que foi?',
        'Manda aí, estou ouvindo.',
        'Estou com você. Pode falar.',
        'Pode mandar sua próxima instrução.',
        'Estou prestando atenção.',
        'Fala, {nome}.',
        'Pode dizer.',
        'Estou aqui, manda.',
    ],

    # ========================================================
    # NOVAS FALAS DO CÉREBRO
    # ========================================================
    #
    # O iniciativa.py decide QUANDO perguntar.
    # O falas.py decide COMO perguntar.
    #
    # Estas categorias são usadas pelo cerebro.py.
    # ========================================================

    'pergunta_continuacao': [
        'Quer continuar falando sobre isso?',
        'Quer continuar nesse assunto?',
        'Quer falar mais sobre isso?',
        'Quer que a gente continue por aqui?',
        'Quer seguir com esse assunto?',
        'Quer continuar essa conversa?',
        'Quer que eu continue explicando?',
        'Quer ir um pouco mais fundo nisso?',
        'Quer explorar mais esse assunto?',
        'Quer que eu continue?',
        'Quer saber mais sobre isso?',
        'Quer que a gente aprofunde isso?',
    ],

    'pergunta_mais_informacoes': [
        'Quer que eu te conte mais sobre isso?',
        'Quer mais informações sobre esse assunto?',
        'Quer saber mais detalhes?',
        'Quer que eu explique mais sobre isso?',
        'Posso te passar mais informações sobre isso. Quer?',
        'Quer que eu aprofunde esse assunto?',
        'Quer que eu te conte mais detalhes?',
        'Quer conhecer mais sobre isso?',
        'Quer que eu continue com mais informações?',
        'Quer saber um pouco mais sobre esse tema?',
        'Posso continuar e explicar melhor. Quer?',
        'Quer que eu entre em mais detalhes?',
    ],

    'pergunta_detalhes': [
        'Quer que eu explique essa parte com mais detalhes?',
        'Quer que eu detalhe melhor isso?',
        'Posso explicar essa parte mais a fundo. Quer?',
        'Quer uma explicação mais detalhada?',
        'Quer que eu mostre mais detalhes sobre isso?',
        'Quer que eu desenvolva melhor essa resposta?',
        'Quer que eu entre nos detalhes?',
        'Quer que eu aprofunde essa parte?',
        'Posso explicar isso melhor. Quer que eu continue?',
        'Quer uma explicação mais completa?',
        'Quer que eu destrinche esse assunto?',
        'Quer que eu detalhe como isso funciona?',
    ],

    'pergunta_curiosidade': [
        'Quer ouvir uma curiosidade sobre isso?',
        'Quer que eu te conte uma curiosidade sobre esse assunto?',
        'Posso te contar uma curiosidade relacionada. Quer?',
        'Quer saber um detalhe curioso sobre isso?',
        'Quer ouvir algo interessante sobre esse assunto?',
        'Tem uma curiosidade legal sobre isso. Quer saber?',
        'Quer que eu te conte uma coisa interessante sobre isso?',
        'Posso trazer uma curiosidade sobre esse tema. Quer?',
        'Quer descobrir uma curiosidade sobre isso?',
        'Quer saber algo curioso relacionado a esse assunto?',
    ],

    # ========================================================
    # CONFIRMAÇÕES PARA CONTINUAÇÃO
    # ========================================================

    'iniciativa_sim': [
        'Claro. Vou continuar.',
        'Beleza. Vamos continuar.',
        'Claro. Vou te explicar mais.',
        'Pode deixar. Vou aprofundar.',
        'Com certeza. Continuando.',
        'Certo. Vou entrar em mais detalhes.',
        'Vamos nessa. Vou continuar.',
        'Fechado. Vou explicar melhor.',
        'Claro. Tem mais coisa interessante sobre isso.',
        'Pode deixar. Vou aprofundar esse assunto.',
    ],

    'iniciativa_nao': [
        'Tudo bem.',
        'Certo.',
        'Beleza.',
        'Tranquilo.',
        'Sem problema.',
        'Entendido.',
        'Tudo certo.',
        'Certo. Seguimos.',
    ],
}


# ============================================================
# CONTROLE DE REPETIÇÃO
# ============================================================

_ULTIMA_ESCOLHA = {}


# ============================================================
# ESCOLHER FALA
# ============================================================

def escolher(chave, **valores):
    """
    Escolhe uma resposta aleatória sem repetir
    imediatamente a última resposta da mesma categoria.

    Exemplo:

        falas.escolher(
            "chamada",
            nome="João"
        )
    """

    opcoes = RESPOSTAS.get(chave)

    if not opcoes:
        raise KeyError(
            f"Resposta desconhecida: {chave}"
        )

    if len(opcoes) == 1:

        indice = 0

    else:

        anterior = _ULTIMA_ESCOLHA.get(
            chave
        )

        candidatos = [
            i
            for i in range(
                len(opcoes)
            )
            if i != anterior
        ]

        indice = random.choice(
            candidatos
        )

    _ULTIMA_ESCOLHA[chave] = indice

    resposta = opcoes[indice]

    if valores:

        try:

            resposta = resposta.format(
                **valores
            )

        except KeyError as erro:

            raise KeyError(
                f"Falta o valor {erro} "
                f"para a fala '{chave}'."
            ) from erro

    return resposta


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def resetar_variacoes():
    """
    Limpa o histórico das escolhas.
    """

    _ULTIMA_ESCOLHA.clear()


def quantidade_variacoes(chave):
    """
    Retorna a quantidade de variações
    de uma categoria.
    """

    return len(
        RESPOSTAS.get(
            chave,
            ()
        )
    )


def listar_categorias():
    """
    Retorna todas as categorias cadastradas.
    """

    return tuple(
        RESPOSTAS.keys()
    )


def total_respostas():
    """
    Retorna o total de frases cadastradas.
    """

    return sum(
        len(v)
        for v in RESPOSTAS.values()
    )


def verificar_banco(minimo=10):
    """
    Retorna categorias abaixo do
    número mínimo de frases.
    """

    return {
        chave: len(respostas)
        for chave, respostas in RESPOSTAS.items()
        if len(respostas) < minimo
    }


# ============================================================
# FUNÇÕES ESPECÍFICAS PARA O CÉREBRO
# ============================================================

def pergunta_continuacao(
    assunto=None
):
    """
    Retorna uma pergunta de continuação.

    O assunto é aceito para manter compatibilidade
    com o cerebro.py atual.
    """

    return escolher(
        "pergunta_continuacao",
        assunto=assunto,
    )


def pergunta_mais_informacoes(
    assunto=None
):
    """
    Retorna uma pergunta pedindo mais informações.
    """

    return escolher(
        "pergunta_mais_informacoes",
        assunto=assunto,
    )


def pergunta_detalhes(
    assunto=None
):
    """
    Retorna uma pergunta pedindo detalhes.
    """

    return escolher(
        "pergunta_detalhes",
        assunto=assunto,
    )


def pergunta_curiosidade(
    assunto=None
):
    """
    Retorna uma pergunta de curiosidade.
    """

    return escolher(
        "pergunta_curiosidade",
        assunto=assunto,
    )


def pergunta_iniciativa(
    tipo="mais_informacoes",
    assunto=None
):
    """
    Função principal para a iniciativa.

    Permite que o cérebro peça uma pergunta
    sem precisar conhecer diretamente as categorias
    internas do falas.py.

    Tipos aceitos:

        continuacao
        mais_informacoes
        detalhes
        curiosidade
    """

    categorias = {
        "continuacao": "pergunta_continuacao",
        "mais_informacoes": "pergunta_mais_informacoes",
        "detalhes": "pergunta_detalhes",
        "curiosidade": "pergunta_curiosidade",
    }

    categoria = categorias.get(
        tipo,
        "pergunta_mais_informacoes"
    )

    return escolher(
        categoria,
        assunto=assunto,
    )


# ============================================================
# TESTE DIRETO
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("TESTE DO SISTEMA DE FALAS DA YASM")
    print("=" * 50)

    print()

    print(
        "Total de categorias:",
        len(RESPOSTAS)
    )

    print(
        "Total de respostas:",
        total_respostas()
    )

    print()

    print(
        "Exemplo de pergunta de iniciativa:"
    )

    print(
        pergunta_iniciativa(
            "mais_informacoes",
            "Copa do Mundo"
        )
    )

    print()

    print(
        "Categorias com poucas variações:"
    )

    print(
        verificar_banco()
    )
