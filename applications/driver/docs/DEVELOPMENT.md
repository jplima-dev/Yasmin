# Desenvolvimento

## Ambiente local

```bash
python -m venv .venv
```

Linux/macOS/Termux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Instale o núcleo e testes:

```bash
pip install -r requirements.txt
pip install pytest httpx
```

Para todos os extras:

```bash
pip install -r requirements-full.txt
```

## Testes

```bash
pytest -q
```

## Executar

```bash
python run.py
```

Healthcheck:

```bash
python scripts/healthcheck.py
```

## Regras do projeto

- Nenhum blob no SQLite.
- Não capturar exceções genéricas para escondê-las.
- Operações destrutivas devem ter etapa de recuperação sempre que possível.
- O scanner não deve recalcular todos os hashes a cada ciclo.
- Componentes opcionais não podem quebrar o núcleo se suas bibliotecas não estiverem instaladas.
- Não adicionar framework frontend pesado sem uma necessidade real.
