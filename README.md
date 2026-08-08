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
- `GET /api/v1/spots/{id}/fishability` — indice de pêchabilité (cf. ci-dessous)
- `GET/POST /api/v1/catches`, `GET/PATCH/DELETE /api/v1/catches/{id}` (scopés à l'utilisateur authentifié)
- `GET /api/v1/species`, `GET /api/v1/species/{id}`

## Indice de pêchabilité

`GET /api/v1/spots/{id}/fishability?at=<iso8601>&species_id=<id>`

Note de 0 à 100 les conditions de pêche sur un spot. `at` vaut maintenant par
défaut et accepte tout horodatage de la fenêtre de prévision (la veille à J+7) ;
au-delà, l'API répond `422`. L'endpoint est public, comme la consultation d'un spot.

La météo vient d'[Open-Meteo](https://open-meteo.com) (gratuite, sans clé d'API),
mise en cache une heure par secteur d'environ 1 km. Si la source est injoignable,
l'API répond `503` plutôt que de renvoyer un score inventé.

Le score agrège sept facteurs pondérés, chacun détaillé dans la réponse — un
pêcheur ne fait pas confiance à un chiffre nu, il veut savoir pourquoi :

| Facteur | Poids | Optimum |
| --- | --- | --- |
| Tendance barométrique | 25 | baisse régulière (~1,5 hPa/3 h) |
| Moment de la journée | 18 | lever et coucher du soleil |
| Couverture nuageuse | 14 | 50–85 % |
| Vent | 14 | 8–18 km/h |
| Température | 14 | 14–19 °C |
| Précipitations | 10 | pluie fine (~0,3 mm/h) |
| Phase lunaire | 5 | nouvelle et pleine lune |

Préciser `species_id` ajoute les avis de saison et de taille légale. **Une espèce
hors saison force le score à 0** avec un avis `blocking` : la question posée est
« est-ce que je vais pêcher ça ici maintenant », et la réponse est non quelle que
soit la pression atmosphérique.

Limites connues, à lever quand la donnée le permettra :

- la température de l'eau est approximée par celle de l'air (Open-Meteo ne
  fournit pas de température d'eau en intérieur des terres) ;
- les pondérations et les optima sont empiriques, tirés des règles usuelles de la
  pêche en eau douce, et non calés sur des captures réelles — le champ
  `conditions` des captures est justement là pour permettre ce recalage ;
- la phase lunaire utilise un mois lunaire moyen, précis à environ un jour ;
- le cache est propre à chaque processus (pas de cache partagé entre workers).

La logique métier restante (gestion des favoris, upload de photos, amis et
compétitions, etc.) n'est pas implémentée : la base reste volontairement minimale
et extensible.
