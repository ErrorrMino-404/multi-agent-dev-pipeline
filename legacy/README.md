# Legacy: pipeline orchestrato

Questa cartella contiene la prima versione del progetto: una pipeline
Python (`orchestrate.py`) che invocava Claude Code CLI come sub-process,
una fase alla volta, con handshake via contract files JSON.

## Cos'era

Un orchestratore esterno che:

1. Leggeva `requirements.md`
2. Lanciava `claude` in modalità non-interattiva con `--system-prompt-file`
   puntato a uno degli `agents/agent_*.md`
3. Comprimeva i contract files per agente (`contract_compressor.py`) per
   ridurre i token in input
4. Gestiva retry granulare leggendo `reports/static_review.json`,
   `reports/test_report.json`, `reports/security_audit.json`
5. Faceva commit automatici per fase con `--git`

I file di prompt degli agenti sono in `agents/`:

| File | Ruolo |
|------|-------|
| `orchestrator.md` | Pianifica il lavoro in `tasks/task_plan.json` |
| `agent_db.md` | Schema PostgreSQL + migration |
| `agent_be.md` | Backend Kotlin/Spring o Python/FastAPI |
| `agent_fe.md` | Frontend React/Vue + TypeScript |
| `agent_review_static.md` | Review statica del codice |
| `agent_test_writer.md` | Scrittura test |
| `agent_test_runner.md` | Esecuzione test |
| `agent_security.md` | Security audit OWASP |
| `agent_comments.md` | Commenti KDoc/docstring |
| `agent_wiki.md` | Documentazione Markdown |
| `agent_memory.md` | Knowledge vault Obsidian |

## Perché è stato deprecato

Claude Code supporta nativamente i **subagents** via file Markdown in
`.claude/agents/`. Vantaggi rispetto al pipeline orchestrato:

- **Niente sub-process management**: l'agente principale delega ai
  subagent direttamente, senza dover gestire stdin/stdout di una CLI.
- **Context isolation gratuita**: ogni subagent ha la sua finestra di
  contesto, niente compressione manuale dei contract files.
- **Routing automatico**: la `description` del subagent guida la
  delegazione, niente hardcoding di "phase_X" in Python.
- **Tool restriction nativa**: il frontmatter YAML supporta `tools:`,
  niente più stringhe `--allowedTools "Read,Write,Bash(...)"`.
- **Meno codice da mantenere**: ~50 KB di Python eliminati, sostituiti
  da Markdown dichiarativo.

La nuova architettura vive in `.claude/agents/` nella root del repo.
Vedi il [README principale](../README.md) e il [CLAUDE.md](../CLAUDE.md)
per il workflow corrente.

## Come riusarlo se serve

Se vuoi rimettere in piedi il vecchio pipeline (per benchmark,
A/B test contro la nuova architettura, o porting su un altro tool):

```bash
# Dalla root del repo
cp legacy/orchestrate.py .
cp legacy/contract_compressor.py .
cp legacy/setup.sh .
cp legacy/pipeline.yaml.example .
cp -r legacy/agents .
chmod +x setup.sh

./setup.sh
python orchestrate.py --requirements requirements.md --dry-run
```

I prompt in `agents/` non dipendono dal codice Python e possono essere
riutilizzati come riferimento testuale anche fuori dal pipeline.

## Cosa non c'è qui

- `examples/` resta nella root: gli esempi di `requirements.md` sono
  validi anche per il nuovo workflow.
- `.github/` resta nella root: i template di issue/PR non sono legati
  al pipeline.
- `requirements.txt` resta nella root: il nuovo workflow non ne ha
  bisogno, ma non costa nulla tenerlo.
