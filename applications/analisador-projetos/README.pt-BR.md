<p align="center">
  <img src="assets/screenshots/logo.png" alt="Logo do Project Analyzer" width="96">
</p>

# Project Analyzer

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![pywebview](https://img.shields.io/badge/pywebview-Desktop%20UI-blue)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)
![MIT License](https://img.shields.io/badge/License-MIT-green)

[Instalador para Windows](https://github.com/ink-creator/Analisador-de-projetos/releases) · [Vídeo de demonstração](assets/demo/project-analyzer-demo.mp4) · [English](README.md)

Analise projetos de programação locais através de um painel desktop com estatísticas de arquivos, distribuição de linguagens, estrutura do projeto, marcadores de código e informações úteis — sem modificar os arquivos originais.

![Visão geral do Project Analyzer](assets/screenshots/overview.png)

## Demonstração

[![Assistir à demonstração do Project Analyzer](assets/screenshots/overview.png)](assets/demo/project-analyzer-demo.mp4)

[Assistir ou baixar o vídeo de demonstração](assets/demo/project-analyzer-demo.mp4)

## Funcionalidades

- Selecione e analise projetos de programação locais por uma interface desktop nativa.
- Conte arquivos, pastas, linhas, tamanho total e tamanho médio dos arquivos.
- Detecte linguagens de programação e compare sua distribuição por linhas.
- Navegue pelo projeto através de uma árvore de arquivos interativa.
- Pesquise arquivos e pastas por nome ou caminho.
- Consulte informações de arquivos como linguagem, tamanho, quantidade de linhas e caminho.
- Detecte os maiores arquivos e diretórios.
- Calcule a profundidade do projeto e encontre diretórios vazios.
- Detecte marcadores de código como `TODO`, `FIXME` e `HACK`.
- Destaque arquivos grandes, vazios e não classificados.
- Ignore pastas geradas comuns, como `.git`, `node_modules`, `.venv`, `dist` e `build`.
- Execute análises pela linha de comando e retorne o resultado em JSON.
- Analise projetos em modo somente leitura: os arquivos do projeto nunca são modificados.

### Visão Geral do Projeto

Depois que uma pasta é selecionada, o Project Analyzer analisa o projeto e reúne suas informações mais úteis em um único painel.

A visão geral mostra quantidade de arquivos e pastas, total de linhas, tamanho do projeto, distribuição de linguagens e destaques como o maior arquivo, extensão mais comum, profundidade máxima e marcadores de código encontrados.

![Painel do Project Analyzer](assets/screenshots/overview.png)

### Explorador de Arquivos

Navegue pelo projeto analisado através de uma árvore interativa e pesquise arquivos ou pastas por nome ou caminho.

Ao selecionar um arquivo, o programa mostra informações úteis como linguagem detectada, tamanho, quantidade de linhas e localização dentro do projeto.

![Explorador de arquivos do projeto](assets/screenshots/files.png)

### Estrutura e Estatísticas

O Project Analyzer também resume a estrutura do projeto, incluindo as extensões encontradas e os maiores diretórios.

Essas estatísticas facilitam a compreensão de como uma base de código está organizada e onde a maior parte dos arquivos e do armazenamento está concentrada.

![Estatísticas da estrutura do projeto](assets/screenshots/insights.png)

## Análise Somente Leitura

O Project Analyzer apenas lê o projeto selecionado.

Ele não edita, renomeia, move ou exclui arquivos do projeto. A interface apenas exibe as informações geradas pelo analisador em Python.

## Modo CLI

O analisador também pode ser utilizado sem a interface gráfica.

Analise um projeto:

```bash
python main.py --cli "C:\Projetos\MeuProjeto"
```

Retorne a análise completa em JSON:

```bash
python main.py --cli "C:\Projetos\MeuProjeto" --json
```

O analisador em modo CLI utiliza apenas a biblioteca padrão do Python.

## Executando Localmente

Clone o repositório:

```bash
git clone https://github.com/ink-creator/Analisador-de-projetos.git
cd Analisador-de-projetos
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Linux / macOS

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

O aplicativo abre em uma janela desktop nativa através do `pywebview`.

## Testes

Execute os testes automatizados com:

```bash
python -m unittest discover -s tests -v
```

## Como Funciona

```text
Pasta do projeto selecionada
        ↓
   Scanner em Python
        ↓
  Análise e estatísticas
        ↓
 Resultado serializável
        ↓
      pywebview
        ↓
Interface HTML / CSS / JavaScript
```

## Tecnologias

Python, pywebview, HTML, CSS e JavaScript, utilizando a biblioteca padrão do Python para a análise principal e `unittest` para testes automatizados.

<details>
<summary>Estrutura do Projeto</summary>

```text
Analisador-de-projetos/
├── assets/
│   ├── demo/
│   │   └── project-analyzer-demo.mp4
│   └── screenshots/
│       ├── logo.png
│       ├── overview.png
│       ├── files.png
│       └── insights.png
├── backend/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── scanner.py
│   ├── languages.py
│   ├── statistics.py
│   ├── content.py
│   └── config.py
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js
│   │   └── charts.js
│   └── assets/
├── tests/
│   └── test_analyzer.py
├── build_exe.bat
├── ProjectAnalyzer.spec
├── main.py
├── requirements.txt
├── README.md
├── README.pt-BR.md
└── LICENSE
```

</details>

## Licença

Distribuído sob a [Licença MIT](LICENSE).
