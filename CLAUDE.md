# Multi-Agent Dev Pipeline

Questo repo è in transizione da una pipeline Python orchestrata a
**subagents nativi di Claude Code**. Il vecchio pipeline è
preservato in `legacy/` per riferimento; lo sviluppo nuovo va sui
subagents in `.claude/agents/`.

## Architettura attuale (subagents nativi)

I subagents sono file Markdown con frontmatter YAML in
`.claude/agents/`. L'agente principale di Claude Code li delega
automaticamente in base al campo `description`, oppure puoi
invocarli esplicitamente con `@nome-agente`.

Subagents disponibili (fase 1 della conversione):

| Subagent | Trigger | Scope |
|----------|---------|-------|
| `backend-expert` | Codice backend Kotlin/Spring o Python/FastAPI | `backend/` |
| `frontend-expert` | Codice frontend React/Vue + TypeScript | `frontend/` |

Da convertire (fase 2+):

- `db-expert` — schema PostgreSQL, migration
- `code-reviewer` — review statica
- `security-expert` — audit OWASP, dipendenze
- `test-expert` — scrittura ed esecuzione test
- `docs-writer` — wiki Markdown, KDoc/docstring
- `memory-keeper` — knowledge vault Obsidian

## Come lavorare con i subagents

### Invocazione automatica

Il routing è guidato dal campo `description` nel frontmatter.
Frasi come "MUST BE USED per..." e "Use proactively per..." aumentano
la probabilità che l'agente principale deleghi senza che tu debba
chiederlo esplicitamente.

### Invocazione esplicita

Nel prompt:

```
@backend-expert aggiungi endpoint POST /auth/register con bcrypt
```

### Context isolato

Ogni subagent ha la sua finestra di contesto. Comunica con l'agente
principale **via testo** (input nel prompt, output nel report finale).
Niente file condivisi tipo `tasks/task_plan.json` o
`contracts/api_contract.json`.

### Output strutturato

Ogni subagent deve restituire un report con:

- Cosa ha creato/modificato (con path file)
- Dipendenze aggiunte
- Variabili d'ambiente richieste
- Note per altri agenti (cosa il prossimo deve sapere)
- Cosa ha lasciato fuori scope (e perché)

## Convenzioni di progetto

### Isolamento delle directory di output

Ogni agente scrive SOLO nella sua directory:

- `db-expert` → `db/`
- `backend-expert` → `backend/`
- `frontend-expert` → `frontend/`
- `docs-writer` → `wiki/`
- `memory-keeper` → `vault/`

Mai cross-write. Se un agente ha bisogno del lavoro di un altro,
chiede all'agente principale di delegare.

### Logging e sicurezza

- MAI loggare password, token, API key, anche in stacktrace.
  Usa `<redacted>` come placeholder.
- Le password vanno hashate con bcrypt (mai SHA1/MD5/SHA256 raw).
- Ogni endpoint REST deve avere logging strutturato all'inizio.
- Niente secret hardcoded: tutto via env var.

### Scrittura atomica dei JSON

Quando un agente produce file JSON che altri leggono (es. report,
metadati), scrivili atomicamente per evitare race condition:

```bash
# Sbagliato — il consumer può leggere file parziale
echo "$json" > reports/test_report.json

# Giusto — atomic rename
echo "$json" > reports/test_report.json.tmp
mv reports/test_report.json.tmp reports/test_report.json
```

## Roadmap conversione

- [x] Fase 1: `backend-expert`, `frontend-expert`
- [ ] Fase 2: `db-expert`
- [ ] Fase 3: `code-reviewer`, `security-expert`
- [ ] Fase 4: `test-expert`, `docs-writer`, `memory-keeper`
- [ ] Fase 5: rimozione di `legacy/` se la nuova architettura regge

## Legacy

Il vecchio pipeline orchestrato (`orchestrate.py` + `agents/*.md` +
`contract_compressor.py`) vive in `legacy/`. Vedi
[legacy/README.md](legacy/README.md) per come riusarlo se serve un
benchmark o un fallback.
