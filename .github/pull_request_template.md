# Pull Request

## Cosa cambia
Descrivi brevemente la modifica.

## Motivazione
Quale problema risolve? Se è una feature, perché è utile?

## Tipo di cambio
- [ ] Bug fix
- [ ] Nuova feature
- [ ] Modifica system prompt agente
- [ ] Refactor (no cambio funzionale)
- [ ] Documentazione
- [ ] CI/build
- [ ] Aggiornamento dipendenze

## Modifiche ai system prompt
Se hai modificato uno o più `agents/*.md`:

**Esempio prima della modifica**:
```
output dell'agente con il prompt vecchio
```

**Esempio dopo la modifica**:
```
output dell'agente con il prompt nuovo
```

## Checklist
- [ ] `python -m py_compile orchestrate.py contract_compressor.py` passa
- [ ] `bash -n setup.sh` passa
- [ ] `python orchestrate.py --requirements examples/todo-app/requirements.md --dry-run` passa
- [ ] README aggiornato se ho aggiunto/cambiato flag CLI
- [ ] CLAUDE.md aggiornato se ho cambiato convenzioni
- [ ] CONTRIBUTING.md aggiornato se ho cambiato il workflow di sviluppo

## Test eseguiti
Descrivi cosa hai testato manualmente. Idealmente: un dry-run + un run
parziale (almeno fino a FASE 1 o 2).

## Issue collegate
Closes #...
