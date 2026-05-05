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

| Subagent | File | Trigger | Output |
|----------|------|---------|--------|
| `backend-expert` | [.claude/agents/backend-expert.md](.claude/agents/backend-expert.md) | Codice backend Kotlin/Spring Boot o Python/FastAPI | `backend/` |
| `frontend-expert` | [.claude/agents/frontend-expert.md](.claude/agents/frontend-expert.md) | Codice frontend React o Vue 3 con TypeScript | `frontend/` |
| `db-expert` | [.claude/agents/db-expert.md](.claude/agents/db-expert.md) | Schema PostgreSQL e migration SQL | `db/` |
| `code-reviewer` | [.claude/agents/code-reviewer.md](.claude/agents/code-reviewer.md) | Review qualità codice, logging, gestione errori, validazione | report testuale |
| `security-expert` | [.claude/agents/security-expert.md](.claude/agents/security-expert.md) | Audit OWASP, secret scanning, dipendenze vulnerabili | report testuale |
| `memory-keeper` | [.claude/agents/memory-keeper.md](.claude/agents/memory-keeper.md) | Knowledge vault Obsidian (entità, ADR, pattern, run) | `vault/` |

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
- [x] **Fase 3**: `code-reviewer`, `security-expert`, `memory-keeper`
- [ ] **Fase 4**: `test-expert`, `docs-writer`
- [ ] **Fase 5**: rimozione di `legacy/` quando la nuova architettura
  è validata su 2-3 progetti reali

## Prerequisiti

### Base (sempre richiesti)

| Requisito | Versione | Note |
|-----------|----------|------|
| [Claude Code](https://claude.com/claude-code) | latest | CLI o IDE extension |
| Account Anthropic | Pro/Max o API key | I subagents girano su modello `sonnet` |
| Git | 2.x+ | Per `git status` / `git diff` usati dai subagents |
| Bash / sh | qualsiasi | Per i comandi di analisi (grep, find) |

### Per `backend-expert`

A seconda dello stack scelto nel tuo progetto:

| Stack | Tool | Versione consigliata |
|-------|------|----------------------|
| Kotlin / Spring Boot | JDK | 17+ |
| Kotlin / Spring Boot | Gradle o Maven | Gradle 8+ / Maven 3.9+ |
| Python / FastAPI | Python | 3.10+ |
| Python / FastAPI | pip / poetry / uv | a scelta |

Il subagent **non installa** runtime per te: aspetta di trovare il
tool già presente quando esplora la codebase. Se il task richiede
una nuova dipendenza (es. `spring-boot-starter-security`), l'agente
la aggiunge a `pom.xml` / `build.gradle.kts` / `pyproject.toml` /
`requirements.txt` ma **non esegue `install`**: lo fai tu.

### Per `frontend-expert`

| Stack | Tool | Versione consigliata |
|-------|------|----------------------|
| React + TS / Vue 3 + TS | Node.js | 18 LTS o 20 LTS |
| React + TS / Vue 3 + TS | npm / pnpm / yarn | a scelta |
| React + TS / Vue 3 + TS | Vite | 5+ (default consigliato) |

Stessa logica di `backend-expert`: aggiunge dipendenze a
`package.json` ma non lancia `npm install`.

### Per `db-expert`

| Tool | Versione | Note |
|------|----------|------|
| PostgreSQL | 14+ | Solo se vuoi testare le migration localmente |
| `psql` (client CLI) | 14+ | Opzionale, utile per validare gli SQL prodotti |

Il subagent produce solo file `.sql` in `db/migrations/`.
**Non si connette a un database**: l'esecuzione delle migration
(via Flyway, Liquibase, `psql -f`, Alembic, ecc.) è responsabilità tua.

Estensioni PostgreSQL usate dal default del subagent:
- `pgcrypto` (per `gen_random_uuid()`)

### Per `code-reviewer`

Nessun tool aggiuntivo oltre alla base. Esegue solo `Read`, `Grep`,
`Glob` e `Bash` non distruttivo (grep, git status, git diff).
Non installa nulla, non modifica file.

### Per `security-expert`

| Tool | Quando serve | Installazione |
|------|--------------|---------------|
| `pip-audit` | progetti Python | `pip install pip-audit` |
| `safety` | alternativa a pip-audit | `pip install safety` |
| `npm` (con `npm audit`) | progetti JS/TS | incluso in Node.js |
| `gradle` con plugin `org.owasp.dependencycheck` | progetti Gradle | configurato in `build.gradle.kts` |
| `mvn` con `org.owasp:dependency-check-maven` | progetti Maven | configurato in `pom.xml` |

Tutti questi tool sono **opzionali**: se non sono installati il
subagent procede con secret scanning (basato su `grep`, sempre
disponibile) e checklist statica OWASP, e documenta nel report
quali scanner non erano disponibili.

### Per `memory-keeper`

| Tool | Quando serve |
|------|--------------|
| [Obsidian](https://obsidian.md/) | Solo per **leggere** il vault con UI grafica e wikilink. Non serve per generarlo. |

Il subagent scrive solo file Markdown con frontmatter YAML in
`vault/`. Sono leggibili anche con un editor di testo qualunque o
con Claude stessa nella sessione successiva.

### Setup minimo end-to-end

```bash
# Tool base
node --version    # >= 18
python --version  # >= 3.10 (se usi FastAPI)
java --version    # >= 17 (se usi Spring Boot)
psql --version    # >= 14 (se vuoi testare DB localmente)

# Security scanner Python (opzionale ma consigliato)
pip install pip-audit

# Avvio
git clone https://github.com/<your-username>/multi-agent-dev-pipeline.git
cd multi-agent-dev-pipeline
claude
```

## Quickstart (nuovo workflow)

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
│       ├── db-expert.md
│       ├── code-reviewer.md
│       ├── security-expert.md
│       └── memory-keeper.md
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

A runtime i subagents creano `backend/`, `frontend/`, `db/`, `vault/`
(e in fase 4 anche `wiki/`).

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
