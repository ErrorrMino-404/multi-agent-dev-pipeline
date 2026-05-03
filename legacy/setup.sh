#!/usr/bin/env bash
# setup.sh — Setup iniziale per multi-agent dev pipeline
#
# Crea la struttura di directory, il file .claude/settings.json
# project-specific, il CLAUDE.md di context e fa sanity check
# sull'installazione di Claude Code CLI.
#
# Uso:
#   ./setup.sh           # setup completo
#   ./setup.sh --check   # solo sanity check
#   ./setup.sh --force   # sovrascrive file esistenti senza chiedere
#
# Idempotente: può essere eseguito più volte senza side effect.

set -euo pipefail

# ─── Color output ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }
title() { echo -e "\n${BOLD}━━━ $1 ━━━${NC}"; }

# ─── Args parsing ──────────────────────────────────────────────────────────────
MODE="full"
FORCE=false

for arg in "$@"; do
    case $arg in
        --check) MODE="check" ;;
        --force) FORCE=true ;;
        --help|-h)
            head -20 "$0" | tail -n +2 | sed 's/^# *//'
            exit 0
            ;;
        *)
            err "Argomento sconosciuto: $arg"
            exit 1
            ;;
    esac
done

# ─── Helper functions ──────────────────────────────────────────────────────────

confirm_overwrite() {
    local file=$1
    if [[ -f "$file" ]] && ! $FORCE; then
        read -p "  $file esiste. Sovrascrivere? [y/N] " ans
        [[ "$ans" =~ ^[Yy]$ ]]
    else
        true
    fi
}

# ─── Sanity check ──────────────────────────────────────────────────────────────

check_environment() {
    title "Sanity check ambiente"
    local errors=0

    # Python 3.10+
    if command -v python3 &>/dev/null; then
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        local major minor
        major=$(echo "$py_version" | cut -d. -f1)
        minor=$(echo "$py_version" | cut -d. -f2)
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            ok "Python $py_version"
        else
            err "Python $py_version troppo vecchio, serve 3.10+"
            errors=$((errors + 1))
        fi
    else
        err "python3 non trovato"
        errors=$((errors + 1))
    fi

    # Claude Code CLI
    if command -v claude &>/dev/null; then
        local cc_version
        cc_version=$(claude --version 2>&1 | head -1 || echo "unknown")
        ok "Claude Code CLI: $cc_version"
    else
        err "claude CLI non trovato. Installa con: npm i -g @anthropic-ai/claude-code"
        errors=$((errors + 1))
    fi

    # --system-prompt-file flag (introdotto v1.0.51+)
    if command -v claude &>/dev/null; then
        if claude --help 2>&1 | grep -q "system-prompt-file"; then
            ok "--system-prompt-file disponibile (prompt caching abilitato)"
        else
            warn "--system-prompt-file non disponibile in questa versione di Claude Code"
            warn "  L'orchestratore funziona ma senza prompt caching ottimale"
            warn "  Aggiorna con: npm i -g @anthropic-ai/claude-code@latest"
        fi
    fi

    # Auth check
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        ok "ANTHROPIC_API_KEY impostata"
    else
        warn "ANTHROPIC_API_KEY non impostata"
        warn "  Se usi auth via browser (Pro/Max plan), ignora questo warning"
        warn "  Altrimenti: export ANTHROPIC_API_KEY='sk-ant-...'"
    fi

    # Git (per --git flag)
    if command -v git &>/dev/null; then
        ok "git: $(git --version | cut -d' ' -f3)"
    else
        warn "git non trovato (necessario solo per --git flag)"
    fi

    # PyYAML opzionale (per --config YAML)
    if python3 -c 'import yaml' &>/dev/null; then
        ok "PyYAML installato (config YAML supportato)"
    else
        info "PyYAML non installato. Per config YAML: pip install pyyaml"
        info "  Senza PyYAML, usa config.json al posto di config.yaml"
    fi

    # Tool opzionali per security audit
    info "Tool opzionali per security audit (non bloccanti):"
    for tool in pip-audit safety npm; do
        if command -v "$tool" &>/dev/null; then
            ok "  $tool"
        else
            info "  $tool non trovato (security audit ridotto)"
        fi
    done

    if [[ $errors -gt 0 ]]; then
        err "Trovati $errors errori bloccanti. Risolvi prima di procedere."
        return 1
    fi

    ok "Ambiente pronto"
    return 0
}

# ─── Directory structure ───────────────────────────────────────────────────────

create_directories() {
    title "Creazione struttura directory"

    local dirs=(
        "agents"
        "contracts"
        "tasks"
        "reports"
        "wiki"
        "vault"
        "db/migrations"
        "backend/src"
        "frontend/src"
        ".claude"
        "examples"
    )

    for d in "${dirs[@]}"; do
        if [[ -d "$d" ]]; then
            info "$d (esiste)"
        else
            mkdir -p "$d"
            ok "$d"
        fi
    done
}

# ─── .gitignore ────────────────────────────────────────────────────────────────

create_gitignore() {
    title "Setup .gitignore"

    local gitignore_content
    gitignore_content=$(cat << 'EOF'
# Output runtime del pipeline
contracts/_compressed/
tasks/_compressed/
reports/_compressed/
reports/_raw/
pipeline.log
*.pyc
__pycache__/

# History dei retry (utile in debug, non in repo)
_history/

# Python
.venv/
*.egg-info/
.pytest_cache/

# Node
node_modules/
.npm/

# Build output
build/
dist/
target/
.gradle/

# IDE
.vscode/
.idea/
*.swp
.DS_Store

# Secrets
.env
.env.*
!.env.example

# Claude Code session data
.claude/sessions/
EOF
)

    if [[ -f .gitignore ]] && ! $FORCE; then
        info ".gitignore esiste, aggiungo solo le regole mancanti"
        local added=0
        while IFS= read -r line; do
            if [[ -z "$line" ]] || [[ "$line" =~ ^# ]]; then
                continue
            fi
            if ! grep -Fxq "$line" .gitignore 2>/dev/null; then
                echo "$line" >> .gitignore
                added=$((added + 1))
            fi
        done <<< "$gitignore_content"
        ok ".gitignore aggiornato ($added regole aggiunte)"
    else
        echo "$gitignore_content" > .gitignore
        ok ".gitignore creato"
    fi
}

# ─── .claude/settings.json ────────────────────────────────────────────────────

create_claude_settings() {
    title "Setup .claude/settings.json"

    local settings_file=".claude/settings.json"

    if ! confirm_overwrite "$settings_file"; then
        info "Saltato $settings_file"
        return
    fi

    cat > "$settings_file" << 'EOF'
{
  "permissions": {
    "allowedTools": [
      "Read",
      "Write",
      "Edit",
      "Bash(psql *)",
      "Bash(./gradlew *)",
      "Bash(pytest *)",
      "Bash(npm *)",
      "Bash(node *)",
      "Bash(pip-audit *)",
      "Bash(safety *)",
      "Bash(mkdir *)",
      "Bash(mv *)",
      "Bash(cat *)",
      "Bash(grep *)",
      "Bash(ls *)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/secrets/**)",
      "Read(**/*.pem)",
      "Read(**/*.key)",
      "Write(/etc/**)",
      "Write(~/.ssh/**)",
      "Write(.env)",
      "Write(.env.*)",
      "Bash(rm -rf *)",
      "Bash(sudo *)",
      "Bash(curl * | sh)",
      "Bash(wget * | sh)"
    ]
  },
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16384",
    "BASH_DEFAULT_TIMEOUT_MS": "60000"
  }
}
EOF
    ok "$settings_file creato"
    info "  Modifica questo file per personalizzare permessi/env"
}

# ─── CLAUDE.md ─────────────────────────────────────────────────────────────────

create_claude_md() {
    title "Setup CLAUDE.md"

    if ! confirm_overwrite "CLAUDE.md"; then
        info "Saltato CLAUDE.md"
        return
    fi

    cat > "CLAUDE.md" << 'EOF'
# Multi-Agent Dev Pipeline

Questo repo contiene un sistema di orchestrazione di agenti per sviluppo
software full-stack basato su Claude Code CLI.

## Convenzioni di progetto

### Contract files
I file in `contracts/` e `tasks/` sono il SOLO meccanismo di comunicazione
tra agenti. Ogni agente ha file di sua proprietà esclusiva:

| Agente | Produce | Legge |
|--------|---------|-------|
| Orchestrator | `tasks/task_plan.json` | `requirements.md`, reports |
| DB | `contracts/db_contract.json`, `db/migrations/*.sql` | `tasks/task_plan.json` |
| BE | `contracts/api_contract.json`, `backend/src/**` | task_plan, db_contract |
| FE | `frontend/src/**` | task_plan, api_contract |
| Test Writer | `tasks/test_manifest.json`, `**/tests/**` | api_contract, codice |
| Test Runner | `reports/test_report.json` | test_manifest |
| Review | `reports/static_review.json` | tutti contracts + codice |
| Security | `reports/security_audit.json` | tutti contracts + codice |
| Memory | `vault/**` | tutti contracts + reports |

### Scrittura atomica dei JSON
Tutti i contract files devono essere scritti atomicamente per evitare
race condition quando un altro agente li legge:

```bash
# Sbagliato
echo "$json" > contracts/api_contract.json

# Giusto
echo "$json" > contracts/api_contract.json.tmp
mv contracts/api_contract.json.tmp contracts/api_contract.json
```

### Isolamento delle directory di output
Ogni agente scrive SOLO nella sua directory:
- DB → `db/`
- BE → `backend/`
- FE → `frontend/`
- Wiki → `wiki/`
- Memory → `vault/`

Mai cross-write. Se hai bisogno di leggere il lavoro di un altro agente,
fallo via contract file, mai leggendo direttamente i suoi sorgenti
(con eccezione di review e security che sono review-only).

### Logging e sicurezza
- MAI loggare password, token, API key, anche in stacktrace
- Usa `<redacted>` come placeholder
- Le password vanno hashate con bcrypt (mai SHA1/MD5/SHA256 raw)
- Ogni endpoint REST deve avere logging strutturato all'inizio

## Comandi utili

```bash
# Test del piano senza chiamare worker pesanti (gratis)
python orchestrate.py --requirements requirements.md --dry-run

# Primo run con safety net su costi
python orchestrate.py --requirements requirements.md \
    --max-budget-usd 3.00 \
    --max-turns 20 \
    --keep-compressed

# Run con commit automatico per fase
python orchestrate.py --requirements requirements.md --git

# Solo struttura, niente test né security (debug rapido)
python orchestrate.py --requirements requirements.md \
    --skip-tests --skip-security
```

## Debug

Se un run fallisce, controlla in ordine:
1. `pipeline.log` — log strutturato del pipeline
2. `reports/static_review.json` — errori bloccanti rilevati
3. `reports/test_report.json` — test falliti
4. `reports/security_audit.json` — vulnerabilità critical
5. `contracts/_compressed/` (se `--keep-compressed`) — cosa è stato passato
   ai singoli agenti

## Trigger di retry

Il pipeline rifà la FASE 0+1+2 quando in FASE 3:
- `static_review.json` ha `build_ok: false` (errori bloccanti nel codice)
- `test_report.json` ha `build_ok: false` (test falliti, NON skipped)
- `security_audit.json` ha `build_ok: false` (almeno un finding critical)

Default: max 2 retry. Configurabile con `--max-retries N`.
EOF
    ok "CLAUDE.md creato"
}

# ─── Requirements esempio ──────────────────────────────────────────────────────

create_example_requirements() {
    title "Setup requirements.md di esempio"

    if [[ -f "requirements.md" ]]; then
        info "requirements.md esiste, non lo sovrascrivo"
        return
    fi

    cat > "requirements.md" << 'EOF'
# Requirements — Todo App

## Descrizione
Applicazione per la gestione di task personali con autenticazione utente.

## Tech Stack
- Backend: Python (FastAPI)
- Frontend: React + TypeScript
- Database: PostgreSQL

## Entità

### User
- id, email (unico), password, created_at, updated_at

### Todo
- id, title (obbligatorio), description (opzionale),
  completed (boolean, default false),
  user_id (FK → User), created_at, updated_at

## Endpoint

### Auth
- POST /auth/register → registra nuovo utente
- POST /auth/login → ritorna JWT

### Todos (autenticati)
- GET    /todos → lista todo dell'utente loggato
- POST   /todos → crea nuovo todo
- PUT    /todos/{id} → aggiorna (solo proprietario)
- DELETE /todos/{id} → elimina (solo proprietario)

## Requisiti non funzionali
- Logging strutturato su tutti gli endpoint
- Password hashate con bcrypt
- JWT con scadenza 24h
- Validazione input
- Error response uniforme: { "error": string, "details": object }
EOF
    ok "requirements.md creato"
}

# ─── Verify agent files ────────────────────────────────────────────────────────

verify_agent_files() {
    title "Verifica file agenti"

    local required=(
        "orchestrator.md"
        "agent_db.md"
        "agent_be.md"
        "agent_fe.md"
        "agent_review_static.md"
        "agent_test_writer.md"
        "agent_test_runner.md"
        "agent_security.md"
        "agent_comments.md"
        "agent_wiki.md"
        "agent_memory.md"
    )

    local missing=0
    for f in "${required[@]}"; do
        if [[ -f "agents/$f" ]]; then
            ok "agents/$f"
        else
            err "agents/$f mancante"
            missing=$((missing + 1))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        warn "$missing file agente mancanti. Copiali in agents/ prima di lanciare il pipeline."
    fi
}

# ─── Smoke test ────────────────────────────────────────────────────────────────

run_smoke_test() {
    title "Smoke test pipeline"

    if [[ ! -f orchestrate.py ]]; then
        warn "orchestrate.py non trovato in questa directory"
        return
    fi

    if [[ ! -f requirements.md ]]; then
        warn "requirements.md non trovato"
        return
    fi

    info "Esecuzione: python orchestrate.py --requirements requirements.md --dry-run"
    if python3 orchestrate.py --requirements requirements.md --dry-run &>/tmp/pipeline_smoke_test.log; then
        ok "Smoke test passato"
    else
        err "Smoke test fallito. Vedi /tmp/pipeline_smoke_test.log"
        return 1
    fi
}

# ─── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo -e "${BOLD}Setup Multi-Agent Dev Pipeline${NC}\n"

    if [[ "$MODE" == "check" ]]; then
        check_environment
        verify_agent_files
        exit 0
    fi

    check_environment || exit 1
    create_directories
    create_gitignore
    create_claude_settings
    create_claude_md
    create_example_requirements
    verify_agent_files

    echo
    title "Prossimi passi"
    cat << 'EOF'

  1. Verifica che tutti i file agente siano in agents/
     ls agents/

  2. Modifica requirements.md con i tuoi requisiti
     $EDITOR requirements.md

  3. Test del piano (gratuito, non chiama worker)
     python orchestrate.py --requirements requirements.md --dry-run

  4. Primo run reale con safety net
     python orchestrate.py --requirements requirements.md \
         --max-budget-usd 3.00 \
         --max-turns 20 \
         --keep-compressed

  5. Controlla l'output
     cat pipeline.log
     ls contracts/ db/migrations/ backend/ frontend/

EOF
    ok "Setup completato"
}

main "$@"
