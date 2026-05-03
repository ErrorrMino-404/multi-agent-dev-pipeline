# Multi-Agent Dev Pipeline

Questo repo contiene un sistema di orchestrazione di agenti per sviluppo
software full-stack basato su Claude Code CLI.

## Convenzioni di progetto

### Contract files
I file in `contracts/` e `tasks/` sono il SOLO meccanismo di comunicazione
tra agenti. Ogni agente ha file di sua proprietà esclusiva:

| Agente | Produce | Legge |
|--------|---------|-------|
| Orchestrator | `tasks/task_plan.json` | `requirements.md`, reports, vault context |
| DB | `contracts/db_contract.json`, `db/migrations/*.sql` | `tasks/task_plan.json` |
| BE | `contracts/api_contract.json`, `backend/src/**` | task_plan, db_contract |
| FE | `frontend/src/**` | task_plan, api_contract |
| Test Writer | `tasks/test_manifest.json`, `**/tests/**` | api_contract, codice, review |
| Test Runner | `reports/test_report.json` | test_manifest |
| Review | `reports/static_review.json` | tutti contracts + codice |
| Security | `reports/security_audit.json` | tutti contracts + codice + dipendenze |
| Comments | (modifica in-place codice) | review + test reports (build_ok) |
| Wiki | `wiki/**` | tutti contracts + reports |
| Memory | `vault/**` | tutti contracts + reports |

### Scrittura atomica dei JSON
Tutti i contract files devono essere scritti atomicamente per evitare
race condition quando un altro agente li legge:

```bash
# Sbagliato — il consumer può leggere file parziale
echo "$json" > contracts/api_contract.json

# Giusto — atomic rename
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
