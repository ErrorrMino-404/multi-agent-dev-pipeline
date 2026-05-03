# Multi-Agent Dev Pipeline

> Pipeline automatica per lo sviluppo full-stack con Claude Code CLI.
> Da `requirements.md` a un'app funzionante (DB + Backend + Frontend + test + docs)
> orchestrando agenti specializzati con handshake via contract files.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-required-8B5CF6.svg)](https://claude.com/claude-code)

⚠️ **Status: alpha / proof of concept** — l'architettura è completa ma il sistema
non è ancora stato testato end-to-end. Vedi [Roadmap](#roadmap).

---

## Cosa fa

Dato un file `requirements.md` con descrizione del prodotto da costruire,
la pipeline:

1. Analizza i requisiti e produce un piano strutturato (`task_plan.json`)
2. Progetta lo schema PostgreSQL e genera le migration
3. Implementa Backend (Kotlin/Spring o Python/FastAPI) e Frontend (React) **in parallelo**
4. Esegue review statica, test automatici e security audit
5. In caso di errori, fa retry mirato modificando solo i file segnalati
6. Documenta tutto: KDoc/docstring nel codice, wiki Markdown, knowledge vault Obsidian

Tutto orchestrato da un solo comando:

```bash
python orchestrate.py --requirements requirements.md
```

## Idee chiave

- **Contract-driven communication**: gli agenti non si leggono tra loro, comunicano
  solo via file `db_contract.json` e `api_contract.json`. Questo elimina ambiguità
  e permette parallelismo reale.
- **Specializzazione**: ogni agente ha un system prompt focalizzato (`agents/*.md`)
  e tool ristretti (`--allowedTools`). Niente agent multi-purpose.
- **Memory cross-pipeline**: l'agente Memory mantiene un knowledge vault Obsidian
  con ADR, pattern e storia dei run, iniettato come contesto nei run successivi.
- **Retry granulare**: in caso di QA fallito, l'orchestratore passa un `retry_context`
  con la lista esatta di file da modificare. Niente regenerazione full.
- **Costi controllati**: Opus solo per orchestrazione, Sonnet per task complessi
  (BE/FE), Haiku per task meccanici (commenti, wiki).

## Architettura

```
┌─────────────────┐
│  requirements   │
│      .md        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator   │  Claude Opus
│   (Phase 0)     │  → tasks/task_plan.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Agent DB      │  Claude Sonnet
│   (Phase 1)     │  → db/migrations/, contracts/db_contract.json
└────────┬────────┘
         │
         ├──────────────┬─────────────┐
         ▼              ▼             ▼
┌─────────────┐  ┌─────────────┐
│  Agent BE   │  │  Agent FE   │  Claude Sonnet
│ (Phase 2)   │  │ (Phase 2)   │  → backend/src/, frontend/src/,
│             │  │ aspetta     │     contracts/api_contract.json
│             │  │ api_contract│
└──────┬──────┘  └──────┬──────┘
       │                │
       └────────┬───────┘
                ▼
┌──────────────────────────────────────────┐
│  QA — parallelo (Phase 3)                │
│  ┌──────────┐ ┌──────────────┐ ┌───────┐ │  Sonnet/Haiku
│  │  Review  │ │ Test Writer  │ │Security│ │
│  │  Static  │ │ → Runner     │ │ Audit │ │
│  └──────────┘ └──────────────┘ └───────┘ │
└────────┬─────────────────────────────────┘
         │
         │ build_ok=false → retry (max 2x)
         │ build_ok=true ↓
         ▼
┌──────────────────────────────────────┐
│  Docs — parallelo (Phase 4)          │
│  ┌──────────┐ ┌──────┐ ┌─────────┐  │  Haiku/Sonnet
│  │ Comments │ │ Wiki │ │ Memory  │  │
│  └──────────┘ └──────┘ └─────────┘  │
└──────────────────────────────────────┘
```

## Quickstart

### Prerequisiti

- Python 3.10+
- [Claude Code CLI](https://claude.com/claude-code) installato e autenticato
- Un account Anthropic (Pro/Max o API key)

> Per la configurazione dettagliata di Claude Code CLI (permessi, autenticazione,
> troubleshooting, flag), vedi [README_CLI_SETUP.md](./README_CLI_SETUP.md).

### Installazione

```bash
git clone https://github.com/<your-username>/multi-agent-dev-pipeline.git
cd multi-agent-dev-pipeline

# Setup automatico: directory, .claude/settings.json, CLAUDE.md, sanity check
./setup.sh

# In alternativa, solo sanity check
./setup.sh --check
```

### Primo run

```bash
# 1. Scrivi i tuoi requisiti
cp examples/todo-app/requirements.md ./requirements.md
$EDITOR requirements.md

# 2. Lancia la pipeline
python orchestrate.py --requirements requirements.md

# 3. Output generati in:
#    db/migrations/   ← SQL schema
#    backend/src/     ← codice backend
#    frontend/src/    ← codice frontend
#    wiki/            ← documentazione human-readable
#    vault/           ← knowledge vault Obsidian
#    pipeline.log     ← log completo del run
```

### Modalità

```bash
# Dry-run: valida task_plan.json senza chiamare worker pesanti
python orchestrate.py --requirements requirements.md --dry-run

# Salta i test (solo review statica)
python orchestrate.py --requirements requirements.md --skip-tests

# Salta security audit
python orchestrate.py --requirements requirements.md --skip-security

# Disabilita compressione contract (debug)
python orchestrate.py --requirements requirements.md --no-compress

# Mantieni i file compressi a fine pipeline (debug)
python orchestrate.py --requirements requirements.md --keep-compressed

# Commit automatico per fase su branch pipeline/cycle-N
python orchestrate.py --requirements requirements.md --git

# Configurazione custom (timeouts, retry, models)
python orchestrate.py --requirements requirements.md --config pipeline.yaml

# Limita budget e turni per controllo costi
python orchestrate.py --requirements requirements.md \
    --max-budget-usd 5.00 --max-turns 30

# Più retry sui QA failure
python orchestrate.py --requirements requirements.md --max-retries 4
```

### Esempio config (pipeline.yaml)

```yaml
max_retries: 3
timeouts:
  orchestrator: 240
  db: 240
  be: 900            # progetti grandi possono richiedere più tempo
  fe: 600
  review: 300
  test: 600
  comments: 300
  wiki: 300
  memory: 300
```

## Esempio: requirements.md

````markdown
# Requirements — Todo App

## Tech Stack
- Backend: Python (FastAPI)
- Frontend: React + TypeScript
- Database: PostgreSQL

## Entità

### User
- id, email (unico), password, created_at, updated_at

### Todo
- id, title, description (opzionale), completed,
  user_id (FK → User), created_at, updated_at

## Endpoint

### Auth
- POST /auth/register
- POST /auth/login → JWT

### Todos (autenticati)
- GET    /todos
- POST   /todos
- PUT    /todos/{id}
- DELETE /todos/{id}

## Requisiti non funzionali
- Logging strutturato su tutti gli endpoint
- Password hashate con bcrypt
- JWT con scadenza 24h
- Validazione input
- Error response uniforme: { "error": string, "details": object }
````

Vedi `examples/todo-app/` per l'esempio completo.

## Struttura del progetto

```
multi-agent-dev-pipeline/
├── agents/                    # System prompt degli agenti
│   ├── orchestrator.md
│   ├── agent_db.md
│   ├── agent_be.md
│   ├── agent_fe.md
│   ├── agent_review_static.md
│   ├── agent_test_writer.md   # scrive i test
│   ├── agent_test_runner.md   # esegue i test
│   ├── agent_security.md
│   ├── agent_comments.md
│   ├── agent_wiki.md
│   └── agent_memory.md
├── examples/
│   └── todo-app/              # Requirements di esempio
├── orchestrate.py             # Script di orchestrazione
├── contract_compressor.py     # Compressione contract per agente
├── setup.sh                   # Setup automatico (directory + config)
├── pipeline.yaml.example      # Config di esempio
├── requirements.txt           # Dipendenze Python (minime)
├── CLAUDE.md                  # Context per chi lavora sul progetto stesso
├── README.md                  # Overview del progetto
├── README_CLI_SETUP.md        # Configurazione Claude Code CLI
└── LICENSE
```

A runtime, l'orchestratore crea anche:

```
contracts/        # Handshake tra agenti (gitignorabile)
  _compressed/    # File contract compressi per agente (rimossi a fine run)
tasks/            # Piano di esecuzione
  _compressed/    # Task plan compressi per agente
reports/          # Output di QA
  _compressed/    # Report compressi per agenti dipendenti
db/migrations/    # Generato da agent_db
backend/src/      # Generato da agent_be
frontend/src/     # Generato da agent_fe
wiki/             # Generato da agent_wiki
vault/            # Generato da agent_memory
pipeline.log      # Log del run
```

## Modello di costi

Stime approssimative per un'app medio-piccola (Todo-like, ~6 endpoint, 2 entità):

| Fase | Modello | Costo stimato/run |
|------|---------|-------------------|
| Orchestrator | Opus | ~$0.15 |
| DB | Sonnet | ~$0.10 |
| BE | Sonnet | ~$0.50 |
| FE | Sonnet | ~$0.50 |
| Review Static | Sonnet | ~$0.15 |
| Test Writer | Sonnet | ~$0.20 |
| Test Runner | Haiku | ~$0.03 |
| Security | Sonnet | ~$0.15 |
| Comments | Haiku | ~$0.05 |
| Wiki | Haiku | ~$0.05 |
| Memory | Sonnet | ~$0.10 |
| **Totale single-cycle** | | **~$1.98** |
| **Con 1 retry** | | **~$3.40** |

Il prompt caching dei system prompt (>90% sconto su cache hit) può ridurre
i costi del 40-60% sui run successivi al primo.

> Nota: stime indicative basate sul listino pubblico di Anthropic.
> I costi reali variano in base alla complessità del progetto e al numero di retry.

### Ottimizzazioni token attive

La pipeline applica due ottimizzazioni token automatiche:

1. **Prompt caching dei system prompt agente** via `--system-prompt-file`.
   I file `.md` degli agenti sono stabili tra run, quindi vengono cached dalla
   CLI con sconto fino al 90% sui token di input.

2. **Compressione contract per agente** (`contract_compressor.py`).
   Ogni agente riceve solo le sezioni di `task_plan.json` e dei contract
   files che gli servono. Esempi misurati su Todo App:

   | Agente   | Contract originale | Compresso | Risparmio |
   |----------|-------------------:|----------:|----------:|
   | DB       | 2.2 KB             | 0.6 KB    | -74%      |
   | BE       | 2.6 KB             | 1.9 KB    | -28%      |
   | FE       | 3.6 KB             | 1.4 KB    | -60%      |
   | Review   | 4.0 KB             | 3.1 KB    | -23%      |
   | Memory   | 4.0 KB             | 3.3 KB    | -17%      |

   I file compressi finiscono in `contracts/_compressed/` e `tasks/_compressed/`,
   vengono rimossi a fine pipeline (usa `--keep-compressed` per debug).
   Disabilita con `--no-compress` se sospetti perdita di contesto.

## Estendere la pipeline

### Aggiungere un nuovo agente

1. Crea `agents/agent_mio.md` con il system prompt seguendo il template:
   - Sezione `## Ruolo`
   - Sezione `## Input che leggi` (file specifici, niente glob aperti)
   - Sezione `## Output che produci`
   - Sezione `## Processo` con step numerati
   - Sezione `## Regole` con confini chiari
2. Aggiungi una `phase_X_mio()` in `orchestrate.py`
3. Definisci i tool permessi: `--allowedTools "Read,Write,Bash(comando *)"`
4. Aggiorna `CLAUDE.md` con il nuovo agente

### Cambiare tech stack

Modifica `requirements.md` con il nuovo stack. Gli agenti BE e FE supportano già:
- BE: Kotlin/Spring Boot, Python/FastAPI
- FE: React + TypeScript, Vue 3 + TypeScript
- DB: PostgreSQL (in roadmap: SQLite, MongoDB, Redis)

## Roadmap

- [x] Architettura agenti + system prompt
- [x] Orchestratore con retry granulare e dry-run
- [x] Agente Memory con knowledge vault Obsidian
- [x] Agente Security separato
- [x] Compressione contract files per agente (-30% to -75% token input)
- [x] Prompt caching nativo via `--system-prompt-file`
- [ ] **Test end-to-end su Todo App** (next)
- [ ] Supporto MongoDB, SQLite, Redis come DB target
- [ ] Supporto Vue 3 e Angular come FE target
- [ ] CI/CD: GitHub Action wrapper su `orchestrate.py`
- [ ] Web UI per monitorare i run in tempo reale
- [ ] Sandbox Docker per esecuzione test in ambiente pulito

## Limitazioni note

- **Mai testato in produzione**: il sistema è alpha, aspettati edge case.
- **Nessuna garanzia di compilabilità**: gli agenti producono codice
  plausibile ma il primo run quasi mai gira al 100%. Il retry esiste apposta.
- **Costi variabili**: progetti grandi possono superare $10/run. Usa `--max-budget-usd`
  e `--max-turns` per limitare.
- **Race condition sui contract**: se un agente scrive non atomicamente
  un contract file, il consumer può leggerne una versione parziale.
  Mitigato dal `validate_contract()` ma non eliminato.
- **No rollback automatico**: se il pipeline fallisce a metà FASE 4, i file
  intermedi restano. Usa `--git` per avere rollback puliti via git reset.

## Contribuire

Le PR sono benvenute. Aree dove l'aiuto è particolarmente utile:

- Test end-to-end con stack diversi (Kotlin, Vue, Mongo)
- Refinement dei system prompt basato su output reale
- Nuovi agenti specializzati (es. Performance audit, Accessibility audit)
- Documentazione di run reali con costi e tempi misurati

Prima di aprire una PR:
1. Apri una issue per discutere il cambio
2. Per modifiche ai system prompt, includi un esempio di output prima/dopo
3. Per modifiche all'orchestratore, aggiungi un test in `tests/`

## FAQ

**Q: Posso usarlo senza Claude Code CLI, con solo l'API?**
A: Non al momento. L'orchestratore usa la CLI per la gestione di tool permessi
e isolamento. Il porting all'SDK Python è in roadmap.

**Q: Funziona offline?**
A: No, ogni agente è una chiamata a Claude. Serve connessione e crediti API.

**Q: Posso usare modelli diversi (Opus per BE, Haiku per DB)?**
A: Sì, configurabile via `--model` nel `run_agent()`. Vedi `orchestrate.py`.
Una config per-agente è in roadmap.

**Q: Cosa succede se un agente "impazzisce" e modifica file fuori dal suo scope?**
A: Per questo serve `--allowedTools` con scope ristretto (es. `Write(backend/**)`)
e idealmente eseguire la pipeline in un sandbox/worktree.

**Q: Come integrare con il mio codebase esistente invece che generare da zero?**
A: Non supportato out-of-the-box. Il sistema è pensato per greenfield.
Per brownfield serve un agente "Code Analyzer" iniziale che mappi il codebase
esistente nei contract files (in roadmap).

## License

[MIT](LICENSE) — usalo, modificalo, distribuiscilo. Nessuna garanzia.

## Riferimenti

- [Claude Code Documentation](https://docs.claude.com/claude-code)
- [Anthropic API Reference](https://docs.claude.com/api)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OWASP Top 10](https://owasp.org/Top10/) (per agent_security)
- [Obsidian](https://obsidian.md/) (per leggere il knowledge vault)
