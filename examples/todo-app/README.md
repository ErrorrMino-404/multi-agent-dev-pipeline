# Esempio: Todo App

Esempio di requirements completo per testare il pipeline.

## Cosa contiene
- `requirements.md` — descrizione del prodotto da costruire

## Come usarlo

```bash
# Dalla root del repo
cp examples/todo-app/requirements.md .
python orchestrate.py --requirements requirements.md --dry-run
```

Se il dry-run passa, prosegui col primo run reale:

```bash
python orchestrate.py --requirements requirements.md \
    --max-budget-usd 3.00 \
    --max-turns 20 \
    --keep-compressed
```

## Output atteso

Dopo un run completo dovresti avere:

```
db/migrations/V001__create_users.sql
db/migrations/V002__create_todos.sql
backend/
  main.py
  routers/
    auth.py
    todos.py
  models/
    user.py
    todo.py
  schemas/
  dependencies/
  core/
frontend/src/
  pages/
    Login.tsx
    Register.tsx
    Dashboard.tsx
  components/
  services/
    authService.ts
    todoService.ts
  hooks/
    useAuth.ts
  types/
wiki/
  api.md
  database.md
  architecture.md
  changelog.md
vault/
  entities/User.md
  entities/Todo.md
  endpoints/POST_auth-register.md
  ...
```

## Costi attesi

In base alle stime (vedi README principale), un run completo del Todo App
costa circa $1.98 senza retry, $3.40 con un retry.

## Risultati noti

> Questa sezione verrà aggiornata dopo i primi test reali.

- [ ] Run #1: data, costo effettivo, retry, esito
- [ ] Run #2: ...
