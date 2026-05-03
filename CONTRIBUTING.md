# Contributing

Grazie per voler contribuire! Questo progetto è **alpha** e beneficia
particolarmente di feedback su run reali.

## Come iniziare

1. Fai un fork del repo
2. Clona il tuo fork: `git clone https://github.com/<tuo-user>/multi-agent-dev-pipeline.git`
3. Esegui `./setup.sh --check` per verificare l'ambiente
4. Crea un branch: `git checkout -b feature/nome-feature`
5. Apri una issue prima di lavori grossi per discutere l'approccio

## Aree dove l'aiuto è particolarmente utile

### Test su stack diversi
Il pipeline supporta in teoria Kotlin/Spring + Python/FastAPI per BE e
React/Vue per FE, ma è stato pensato principalmente per Python+React.
Se testi su Kotlin o Vue, condividi i risultati: probabilmente serviranno
aggiustamenti ai prompt degli agenti.

### Documentazione di run reali
Apri una issue con tag `run-report` includendo:
- Stack scelto
- Numero di endpoint/entità
- Costo effettivo del run
- Numero di retry
- Esito (build_ok finale)
- Problemi incontrati e fix applicati

Questi dati ci aiutano a tarare le stime di costo e i timeout di default.

### Miglioramenti agli system prompt
I prompt degli agenti (in `agents/*.md`) sono il cuore del sistema.
Per modifiche:
1. Identifica il problema (es. "agent_be dimentica logging su PUT/DELETE")
2. Trova un esempio concreto di output errato
3. Modifica il prompt
4. Documenta nel PR esempio prima/dopo

### Nuovi agenti specializzati
Idee in roadmap:
- Performance audit (analisi query, N+1, hot path)
- Accessibility audit (WCAG su FE)
- API breaking change detector

Per aggiungere un agente nuovo:
1. Crea `agents/agent_<nome>.md` seguendo il template degli esistenti
2. Aggiungi una `phase_X_<nome>()` o integralo in fase esistente in `orchestrate.py`
3. Aggiorna `DEFAULT_TIMEOUTS` e `DEFAULT_MODELS`
4. Aggiungi la voce in `CLAUDE.md`

### Bug fix nell'orchestratore
Per modifiche a `orchestrate.py`:
- Mantieni la sintassi Python 3.10+ compatibile
- Verifica con `python3 -m py_compile orchestrate.py`
- Esegui `--dry-run` per smoke test
- Aggiungi log strutturato per nuove operazioni significative

## Convenzioni

### Commit
Usa [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(agent): aggiunto agent_performance`
- `fix(orchestrator): timeout race condition`
- `docs(readme): aggiunte stime costo per Vue`
- `refactor(compressor): semplifica logica pruning`

### Pull Request
- Una PR = un cambio logico
- Descrizione chiara con motivazione
- Se cambi system prompt, includi esempio di output prima/dopo
- Se aggiungi flag CLI, aggiorna README e setup.sh
- Verifica che `./setup.sh --check` passi

### Coding style
- Python: PEP 8, type hints dove sensato
- Bash: `set -euo pipefail` in cima, virgolette intorno alle variabili
- Markdown: line wrap a 80 colonne nei file di prompt (più leggibili)

## Cosa NON includere nelle PR

- Output reali di run (codice generato, contracts, reports): vanno in
  un repo separato di esempi, non qui
- File `.env` o credenziali (dovrebbe esserci `.gitignore`, ma controlla)
- Modifiche al `CLAUDE.md` se non riguardano il progetto stesso
- Aumenti dei timeout di default oltre i valori sensati (15 min)

## Discussioni e supporto

Per domande generiche, usa **GitHub Discussions** invece di aprire una issue.
Le issue sono per bug riproducibili e feature request specifiche.

## Code of Conduct

Sii rispettoso, costruttivo e paziente. Questo progetto è sperimentale e
le opinioni divergenti sull'architettura sono benvenute, ma motivate da
dati o esempi concreti, non da preferenze.
