# Requirements — Todo App

## Descrizione
Applicazione per la gestione di task personali con autenticazione utente.

## Tech Stack
- Backend: Python (FastAPI)
- Frontend: React + TypeScript
- Database: PostgreSQL

## Entità del dominio

### User
- id, email (unico), password, created_at, updated_at

### Todo
- id, title (obbligatorio), description (opzionale),
  completed (boolean, default false),
  user_id (FK → User), created_at, updated_at

## Endpoint richiesti

### Auth
- POST /auth/register → registra nuovo utente
- POST /auth/login → ritorna JWT token

### Todos (autenticati)
- GET    /todos → lista tutti i todo dell'utente loggato
- POST   /todos → crea nuovo todo
- PUT    /todos/{id} → aggiorna todo (solo il proprietario)
- DELETE /todos/{id} → elimina todo (solo il proprietario)

## Requisiti non funzionali
- Tutti gli endpoint devono avere logging strutturato
- Le password vanno hashate con bcrypt
- JWT con scadenza 24h
- Validazione input su tutti gli endpoint
- Gestione errori uniforme: { "error": string, "details": object }
