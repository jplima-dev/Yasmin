Yasm - sistema de aplicativos

1. Coloque apps_yas.py na mesma pasta dos outros arquivos.
2. Execute iniciar_yasm.bat na pasta superior, ou python yas.py nesta pasta.
3. Exemplos:
   - Yasmin, abra o Chrome.
   - Yasm, abrir VS Code.
   - Yasmin, inicia o Discord.
   - Yasm, abre a calculadora.

Para adicionar outro programa, edite APLICATIVOS em apps_yas.py.
Adicione aliases e caminhos possiveis do .exe.

O inicializador usa caminhos relativos ao projeto. Para escolher outro Python,
defina YASM_PYTHON com o caminho completo do executavel. Ele tambem reconhece
o ambiente .venv na pasta superior. Consulte launcher.log se a inicializacao falhar.

As instrucoes de verificacao estao no README.md da pasta superior.
