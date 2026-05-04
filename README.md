# Multi-Agent Dev Pipeline

> Sistema di sviluppo full-stack basato su agenti specializzati di
> Claude Code.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-required-8B5CF6.svg)](https://claude.com/claude-code)

## Stato del progetto

Il repo è in **transizione architetturale**:

- **Vecchio approccio (deprecato)**: pipeline Python (`orchestrate.py`)
  che invocava `claude` come sub-process una fase alla volta, con
  handshake via contract files JSON. Tutto il codice di questo
  approccio è ora in [`legacy/`](./legacy/) per riferimento storico
  e riuso opzionale.
- **Nuovo approccio (in corso)**: subagents nativi di Claude Code in
  `.claude/agents/`. L'agente principale delega automaticamente al
  subagent giusto in base alla sua `description`, niente sub-process
  management, niente contract files.

La conversione è progressiva. Backend e Frontend sono già migrati;
gli altri agenti seguono.

## Subagents disponibili

| Subagent | File | Trigger |
|----------|------|---------|
| `backend-expert` | [.claude/agents/backend-expert.md](.claude/agents/backend-expert.md) | Codice backend Kotlin/Spring Boot o Python/FastAPI |
| `frontend-expert` | [.claude/agents/frontend-expert.md](.claude/agents/frontend-expert.md) | Codice frontend React o Vue 3 con TypeScript |
| `db-expert` | [.claude/agents/db-expert.md](.claude/agents/db-expert.md) | Schema PostgreSQL e migration SQL |

I subagents si caricano all'avvio di Claude Code dalla root del repo.
Vengono invocati automaticamente quando il loro `description` matcha,
oppure esplicitamente con `@nome-agente`.

### Esempio d'uso

```
> Voglio aggiungere un endpoint POST /api/v1/users al backend FastAPI
> per registrazione, con email/password e hash bcrypt.

[Claude principale delega automaticamente a @backend-expert]
```

```
> @frontend-expert crea pagina di login con form email+password,
> validazione client e gestione token.
```

## Roadmap conversione

- [x] **Fase 1**: `backend-expert`, `frontend-expert`
- [x] **Fase 2**: `db-expert` (schema PostgreSQL, migration)
- [ ] **Fase 3**: `code-reviewer`, `security-expert`
- [ ] **Fase 4**: `test-expert`, `docs-writer`, `memory-keeper`
- [ ] **Fase 5**: rimozione di `legacy/` quando la nuova architettura
  è validata su 2-3 progetti reali

## Quickstart (nuovo workflow)

### Prerequisiti

- [Claude Code](https://claude.com/claude-code) installato
- Account Anthropic (Pro/Max o API key)

### Uso

```bash
git clone https://github.com/<your-username>/multi-agent-dev-pipeline.git
cd multi-agent-dev-pipeline
claude
```

Poi nella conversazione descrivi quello che vuoi costruire.
Claude principale delegherà ai subagents specializzati.

### Convenzioni

I subagents seguono regole di confine rigide (vedi [CLAUDE.md](./CLAUDE.md)):

- Ogni subagent scrive solo nella sua directory (`backend/`,
  `frontend/`, ecc.)
- Niente cross-write tra agenti
- Logging strutturato obbligatorio
- Niente secret hardcoded
- Bcrypt per le password

## Esempi di requirements

`examples/todo-app/requirements.md` mostra un esempio di prodotto
da costruire (Todo App con auth JWT). Funziona sia con il vecchio
pipeline sia come prompt iniziale per il nuovo workflow.

## Struttura del progetto

```
multi-agent-dev-pipeline/
├── .claude/
│   └── agents/                  # Subagents nativi (nuovo workflow)
│       ├── backend-expert.md
│       ├── frontend-expert.md
│       └── db-expert.md
├── examples/
│   └── todo-app/                # Esempio di requirements.md
├── legacy/                      # Vecchio pipeline orchestrato
│   ├── README.md                # Spiega cos'era e come riusarlo
│   ├── orchestrate.py
│   ├── contract_compressor.py
│   ├── setup.sh
│   ├── pipeline.yaml.example
│   ├── README_CLI_SETUP.md
│   └── agents/                  # 11 system prompt originali
├── CLAUDE.md                    # Istruzioni di progetto per Claude
├── README.md                    # Questo file
└── LICENSE
```

A runtime i subagents creano `backend/`, `frontend/` e (in fasi
successive) `db/`, `wiki/`, `vault/`.

## Contribuire

PR benvenute. Aree utili:

- Conversione dei prossimi subagents (vedi roadmap)
- Test reali su stack diversi (Kotlin/Vue/Mongo) per validare la
  nuova architettura
- Refinement dei prompt in `.claude/agents/` basato su output reale

Prima di aprire una PR, apri una issue per discutere il cambio.
Per modifiche ai subagents, includi un esempio di output prima/dopo.

## License

[MIT](LICENSE) — usalo, modificalo, distribuiscilo.

## Riferimenti

- [Claude Code](https://docs.claude.com/claude-code)
- [Subagents in Claude Code](https://docs.claude.com/claude-code/sub-agents)
- [Anthropic API](https://docs.claude.com/api)

---

## Legacy: pipeline orchestrato

> Questa sezione descrive l'architettura precedente, ora deprecata
> ma ancora funzionante. Il codice è in [`legacy/`](./legacy/).
> Vedi [legacy/README.md](./legacy/README.md) per come riattivarlo.

### Cosa faceva

Dato un `requirements.md`:

1. Analizzava i requisiti e produceva un piano (`task_plan.json`)
2. Progettava lo schema PostgreSQL e generava le migration
3. Implementava Backend e Frontend in parallelo
4. Eseguiva review statica, test automatici e security audit
5. In caso di errori, faceva retry mirato sui file segnalati
6. Documentava tutto in wiki Markdown e knowledge vault Obsidian

### Architettura

```
┌─────────────────┐
│  requirements   │
│      .md        │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Orchestrator   │  Opus → tasks/task_plan.json
└────────┬────────┘
         ▼
┌─────────────────┐
│   Agent DB      │  Sonnet → db/migrations/
└────────┬────────┘
         ├──────────────┐
         ▼              ▼
┌─────────────┐  ┌─────────────┐
│  Agent BE   │  │  Agent FE   │  Sonnet
└──────┬──────┘  └──────┬──────┘
       └────────┬───────┘
                ▼
┌──────────────────────────────────────────┐
│  QA parallelo: Review / Test / Security  │
└────────┬─────────────────────────────────┘
         │ build_ok=false → retry (max 2x)
         ▼
┌──────────────────────────────────────────┐
│  Docs parallelo: Comments / Wiki / Memory│
└──────────────────────────────────────────┘
```

### Idee chiave

- **Contract-driven communication**: gli agenti comunicavano solo via
  `db_contract.json` e `api_contract.json`, mai leggendosi tra loro.
- **Specializzazione**: ogni agente con system prompt focalizzato
  e tool ristretti via `--allowedTools`.
- **Memory cross-pipeline**: knowledge vault Obsidian con ADR
  e pattern, iniettato come contesto nei run successivi.
- **Retry granulare**: in caso di QA fallito, l'orchestratore passava
  un `retry_context` con la lista esatta di file da modificare.
- **Costi controllati**: Opus per orchestrazione, Sonnet per BE/FE,
  Haiku per task meccanici.

### Perché è stato deprecato

I subagents nativi di Claude Code coprono lo stesso caso d'uso con:

- Niente sub-process management
- Niente compressione manuale dei contract files (context isolato)
- Routing dichiarativo via `description`, niente `phase_X()` in Python
- Tool restriction nativa nel frontmatter
- ~50 KB di Python eliminati a favore di Markdown

Vedi [legacy/README.md](./legacy/README.md) per dettagli operativi.
