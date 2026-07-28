# Rivly API

API pour une application de pêche en eau douce. FastAPI + SQLAlchemy (async) + PostgreSQL, typée avec Pydantic v2.

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 (async, `asyncpg`)
- Alembic
- PostgreSQL
- JWT (PyJWT) + bcrypt pour l'auth

## Structure

```
app/
├── main.py          # instanciation FastAPI, montage des routers
├── api.py           # agrégation des routers sous /api/v1
├── core/            # config, session DB, sécurité (JWT/hash), dépendances
├── models/          # modèles SQLAlchemy
├── schemas/         # schémas Pydantic (request/response)
├── routers/         # endpoints HTTP
└── services/        # logique d'accès aux données par entité
alembic/             # migrations
```

## Démarrage local

1. Copier `.env.example` en `.env` et ajuster si besoin (notamment `SECRET_KEY`).
2. Démarrer PostgreSQL :
   ```bash
   docker compose up -d
   ```
3. Créer l'environnement virtuel et installer les dépendances :
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Appliquer les migrations :
   ```bash
   alembic upgrade head
   ```
5. Lancer l'API :
   ```bash
   uvicorn app.main:app --reload
   ```
6. Documentation interactive : http://localhost:8000/docs

## Migrations

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

## Tests

`docker compose up -d` crée aussi, au premier démarrage, une base `rivly_test` dédiée aux tests (via `docker/initdb/`). Les tests recréent le schéma à chaque test et ne touchent jamais à la base de développement.

```bash
pip install -r requirements-dev.txt
pytest -v
```

Un scénario de test manuel via Swagger UI est décrit dans [scenario.md](scenario.md).

## Endpoints scaffoldés

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`
- `GET/POST /api/v1/spots`, `GET/PATCH/DELETE /api/v1/spots/{id}` (filtrage bbox via `min_lat`/`max_lat`/`min_lon`/`max_lon`)
- `GET/POST /api/v1/catches`, `GET/PATCH/DELETE /api/v1/catches/{id}` (scopés à l'utilisateur authentifié)
- `GET /api/v1/species`, `GET /api/v1/species/{id}`

La logique métier avancée (règles de saison, validation de taille légale, gestion des favoris, upload de photos, etc.) n'est pas implémentée : la base est volontairement minimale et extensible.
