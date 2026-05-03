---
name: Run Report
about: Condividi i risultati di un run reale (gradito anche in caso di successo)
title: '[RUN] '
labels: run-report
---

## Stack
- Backend: (Python+FastAPI / Kotlin+Spring)
- Frontend: (React+TS / Vue 3)
- Database: PostgreSQL

## Dimensione progetto
- Endpoint: (numero)
- Entità: (numero)
- Pagine FE: (numero)

## Risultato
- [ ] Build OK al primo ciclo
- [ ] Build OK con N retry (specificare N)
- [ ] Build fallita dopo max retry
- [ ] Pipeline interrotto manualmente

## Costo effettivo
- USD totali: $...
- Tempo totale: ... minuti
- Cicli eseguiti: ...

## Configurazione
```
--max-retries: ...
--max-budget-usd: ...
--max-turns: ...
flag aggiuntivi: ...
```

## Problemi incontrati
Elenca quello che NON ha funzionato come atteso. Anche cose minori
(timeout troppo basso, prompt da migliorare, ecc.).

1. ...
2. ...

## Cosa ha funzionato bene
Cosa ti ha sorpreso positivamente?

## Suggerimenti
Modifiche che proporresti agli agenti o all'orchestratore basate su
questo run?

## Repository del progetto generato (opzionale)
Se l'output è pubblico, link al repo dove l'hai pushato:
