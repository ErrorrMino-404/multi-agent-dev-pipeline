# Configurazione Claude Code CLI

Questa guida spiega come configurare Claude Code CLI per far girare il
multi-agent pipeline. Copre installazione, autenticazione, configurazione
permessi, variabili d'ambiente e troubleshooting.

> Per la documentazione ufficiale completa, vedi
> [docs.claude.com/en/docs/claude-code](https://docs.claude.com/en/docs/claude-code).
> Questa guida è specifica per l'uso nel pipeline.

## Indice

- [Installazione](#installazione)
- [Autenticazione](#autenticazione)
- [File di configurazione](#file-di-configurazione)
- [Permessi e tool](#permessi-e-tool)
- [Variabili d'ambiente](#variabili-dambiente)
- [Flag CLI usati dal pipeline](#flag-cli-usati-dal-pipeline)
- [Verifica setup](#verifica-setup)
- [Troubleshooting](#troubleshooting)

---

## Installazione

### Prerequisiti
- Node.js 18+
- npm

### Installazione globale
```bash
npm install -g @anthropic-ai/claude-code
```

Verifica:
```bash
claude --version
```

### Aggiornamento
Claude Code si aggiorna spesso. Mantienilo aggiornato per beneficiare di
flag nuovi (`--system-prompt-file` è stato introdotto in v1.0.51):

```bash
npm update -g @anthropic-ai/claude-code
```

---

## Autenticazione

Due modalità supportate:

### Opzione 1 — Subscription (Pro/Max plan)
Login via browser, niente API key:

```bash
claude login
```

Apre il browser, fai auth, finito. La sessione persiste nella tua home.

**Quando usarla**: hai un Pro/Max plan e usi Claude Code regolarmente.

### Opzione 2 — API key (pay-per-use)
Imposta la variabile d'ambiente:

```bash
# In ~/.bashrc o ~/.zshrc
export ANTHROPIC_API_KEY="sk-ant-..."
```

Ricarica la shell:
```bash
source ~/.bashrc   # o ~/.zshrc
```

**Quando usarla**: CI/CD, scripting, uso saltuario, o non hai una
subscription Pro/Max.

### Verifica autenticazione
```bash
echo "ok" | claude -p --max-turns 1
```

Se risponde, sei autenticato.

---

## File di configurazione

Claude Code legge i settings in **ordine di priorità decrescente**:

1. **Project**: `.claude/settings.json` nella root del repo
2. **User**: `~/.claude/settings.json` nella tua home
3. **System**: `/etc/claude/settings.json` (raro, solo enterprise)

I valori più specifici (project) sovrascrivono quelli più generici (user).

### Per il pipeline: usa SOLO il project-specific

```bash
mkdir -p .claude
cp .claude/settings.json.example .claude/settings.json
```

Mai mettere config del pipeline nel `~/.claude/settings.json` globale,
altrimenti interferisce con altri tuoi progetti.

### Struttura di `.claude/settings.json`

```json
{
  "permissions": {
    "allowedTools": [...],
    "deny": [...]
  },
  "env": {
    "VAR_NAME": "value"
  },
  "model": "sonnet",
  "hooks": {...}
}
```

I campi che usi davvero per il pipeline sono `permissions` ed `env`.
Non mettere `model` qui: `orchestrate.py` decide il modello per ogni
agente via `--model`, e un setting globale lo sovrascriverebbe.

---

## Permessi e tool

Claude Code controlla rigorosamente cosa l'agente può fare. Due meccanismi:

### `allowedTools` — whitelist non interattiva
Tool in questa lista vengono eseguiti **senza chiedere conferma**.
Tutto il resto richiede conferma manuale (impossibile in CI).

### `deny` — blacklist assoluta
Tool in questa lista vengono **bloccati anche se chiesti dall'agente**.
Vincono sempre su `allowedTools`.

### Configurazione consigliata per il pipeline

```json
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
  }
}
```

### Sintassi delle regole

Le regole supportano glob e pattern:

| Pattern | Effetto |
|---------|---------|
| `Read` | Tutto Read consentito |
| `Read(src/**)` | Read solo dentro src/ |
| `Write(*.py)` | Write solo su file .py |
| `Bash(npm *)` | Tutti i comandi che iniziano con `npm` |
| `Bash(npm install)` | Solo `npm install` esatto |
| `Bash(rm -rf *)` | Tutti gli `rm -rf` |

Attenzione: la sintassi `Bash(npm,pip)` con virgola NON funziona.
Devi usare entry separate: `["Bash(npm *)", "Bash(pip *)"]`.

### Override a runtime
`orchestrate.py` passa `--allowedTools` per ogni agente specializzando
ulteriormente. La regola: si fa AND tra il settings.json e la flag CLI,
prevale la più restrittiva.

### Permission mode
Il pipeline usa `--permission-mode bypassPermissions` per ciascun agente.
Significa: niente prompt di conferma in modalità non interattiva.
La sicurezza è demandata a `allowedTools` + `deny`.

**Non impostare `bypassPermissions` come default in settings.json**: lo
useresti per errore in sessioni interattive.

---

## Variabili d'ambiente

### In `.claude/settings.json` (preferito)
Vengono iniettate solo nelle sessioni Claude Code di questo progetto:

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16384",
    "BASH_DEFAULT_TIMEOUT_MS": "60000"
  }
}
```

| Variabile | Default | Consigliato | Note |
|-----------|---------|-------------|------|
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | 8192 | 16384 | File generati lunghi senza troncamenti |
| `BASH_DEFAULT_TIMEOUT_MS` | 30000 | 60000 | `npm install`, `gradle build` richiedono più tempo |

### In shell (~/.bashrc o ~/.zshrc)
Vanno qui le variabili che servono **prima** di lanciare Claude Code:

```bash
# Auth (se non usi login browser)
export ANTHROPIC_API_KEY="sk-ant-..."

# Disabilita telemetria opzionale
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Solo per WSL2 / problemi di memoria Node
export NODE_OPTIONS="--max-old-space-size=4096"
```

### Provider alternativi (avanzato)
Se usi Bedrock, Vertex AI o Foundry invece di Anthropic API diretta:

```bash
export USE_BEDROCK=1
# o
export USE_VERTEX=1
# o
export USE_FOUNDRY=1
```

Sono mutualmente esclusivi. Per il pipeline, l'Anthropic API standard
è quella consigliata.

---

## Flag CLI usati dal pipeline

`orchestrate.py` invoca `claude` con questi flag per ogni agente:

```bash
claude \
  --print \                                      # modalità non interattiva
  --permission-mode bypassPermissions \          # no prompt conferma
  --system-prompt-file agents/agent_be.md \      # prompt cached
  -p "Leggi tasks/_compressed/be_task_plan.json..." \
  --allowedTools "Read,Write,Bash(./gradlew *,pytest *)" \
  --model sonnet \
  --max-turns 20 \
  --max-budget-usd 2.00
```

### Cosa fa ogni flag

| Flag | Scopo |
|------|-------|
| `--print` / `-p` | Modalità headless: query → output → exit |
| `--permission-mode bypassPermissions` | Niente prompt di conferma in CI |
| `--system-prompt-file <path>` | Carica system prompt da file (cached automaticamente) |
| `-p <prompt>` | Prompt utente (task specifico per l'agente) |
| `--allowedTools <list>` | Whitelist tool per questa invocazione |
| `--model <model>` | Override modello (opus/sonnet/haiku) |
| `--max-turns <N>` | Massimi turni agentici (safety net) |
| `--max-budget-usd <amount>` | Budget USD massimo (safety net) |
| `--output-format json` | Output JSON con cost/duration (per logging) |

### Verifica disponibilità flag

Alcuni flag possono variare tra versioni. Verifica:

```bash
claude --help | grep -E "(system-prompt-file|max-budget-usd|permission-mode)"
```

Se uno di questi manca, aggiorna Claude Code:
```bash
npm update -g @anthropic-ai/claude-code
```

In alternativa, modifica `orchestrate.py` per usare flag equivalenti
o rimuovere quelli mancanti (perdi qualche feature ma il pipeline funziona).

---

## Verifica setup

### Test 1 — Sanity check
```bash
./setup.sh --check
```

Deve stampare ✓ su Python, Claude Code CLI, `--system-prompt-file`.

### Test 2 — Risposta minima
```bash
echo "Rispondi solo 'ok'" | claude -p --max-turns 1
```

Deve rispondere `ok` (o simile) in pochi secondi.

### Test 3 — Permessi
Crea un file `.env` di test e prova a leggerlo:
```bash
echo "SECRET=test" > .env
claude -p "Leggi il file .env"
```

Claude deve **rifiutare** la lettura. Se la fa, il file `.claude/settings.json`
non è stato letto correttamente.

### Test 4 — Output JSON strutturato
```bash
claude -p "Lista 3 colori in JSON" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"colors":{"type":"array","items":{"type":"string"}}}}'
```

Deve restituire un oggetto JSON valido conforme allo schema.

### Test 5 — Pipeline dry-run
```bash
python orchestrate.py --requirements requirements.md --dry-run
```

Deve completare tutte le 5 fasi simulate senza errori.

---

## Troubleshooting

### `claude: command not found`
Claude Code CLI non è installato o non è nel PATH:
```bash
npm install -g @anthropic-ai/claude-code
which claude   # deve mostrare un path tipo /usr/local/bin/claude
```

Su sistemi con `nvm`, l'installazione globale finisce nella node version
attiva. Verifica `nvm current` se cambi versione.

### `Authentication failed`
- Hai esportato `ANTHROPIC_API_KEY` nel terminale corrente?
- L'API key è valida? Verifica nella [Anthropic Console](https://console.anthropic.com/)
- Se usi browser auth: `claude logout && claude login`

### `--system-prompt-file: unknown option`
Versione di Claude Code troppo vecchia:
```bash
npm update -g @anthropic-ai/claude-code
claude --version  # deve essere 1.0.51+
```

In alternativa, modifica `orchestrate.py` riga ~330 sostituendo
`--system-prompt-file` con `--system-prompt` e passando il contenuto
del file inline (perdi prompt caching).

### `Permission denied` durante esecuzione
L'agente sta cercando di usare un tool non in `allowedTools`. Controlla:

1. `pipeline.log` per capire quale comando ha fallito
2. Se il comando è legittimo, aggiungilo a `.claude/settings.json`:
   ```json
   "allowedTools": ["Bash(yarn *)", ...]
   ```
3. Se il comando NON è legittimo, lascialo bloccato e indaga perché
   l'agente lo cerca

### File generati troncati a metà
Aumenta `CLAUDE_CODE_MAX_OUTPUT_TOKENS`:
```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "32768"
  }
}
```

### Timeout su `npm install` / `./gradlew build`
Aumenta `BASH_DEFAULT_TIMEOUT_MS`:
```json
{
  "env": {
    "BASH_DEFAULT_TIMEOUT_MS": "300000"
  }
}
```

(5 minuti — sufficienti per la maggior parte dei build)

### Costi inattesi
Claude Code stampa il costo a fine sessione (`/cost` in modalità interattiva).
In modalità `--print`, usa `--output-format json` per ottenere
`total_cost_usd` strutturato.

Per limitare costi a runtime:
```bash
python orchestrate.py --requirements requirements.md \
    --max-budget-usd 5.00 \
    --max-turns 20
```

### Sessioni che non terminano
Sintomo: `claude` resta appeso senza output.
Possibili cause:
- Manca `--print` (parte in modalità interattiva attendendo input)
- `--max-turns` non impostato e l'agente loopa
- DNS o firewall bloccano `api.anthropic.com`

Soluzione: ctrl+C, verifica connettività, rilancia con `--max-turns 10`.

### `claude config show` mostra config sbagliata
La precedenza è: project > user > system. Verifica:
```bash
# Quale settings sta usando?
ls -la .claude/settings.json
ls -la ~/.claude/settings.json

# Mostra config effettiva
claude config show
```

Se vedi config che non hai impostato, viene dal `~/.claude/settings.json`
globale o da una versione obsoleta in cache.

---

## Riferimenti

- [Documentazione ufficiale Claude Code](https://docs.claude.com/en/docs/claude-code)
- [CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference)
- [Settings reference](https://docs.claude.com/en/docs/claude-code/settings)
- [Anthropic Console](https://console.anthropic.com/) — API keys, billing
- [GitHub Issues Claude Code](https://github.com/anthropics/claude-code/issues) — bug report
