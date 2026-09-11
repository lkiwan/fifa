# Foot Quiz - Jeu de quiz football basé sur les données Transfermarkt

Site web responsive (mobile + PC) : une partie entre amis qui passent le téléphone.
Chaque tour, un joueur de foot est affiché et chaque participant répond aux mêmes 4 questions.
À la fin du tour, les bonnes réponses et les scores sont révélés, le plus mauvais est éliminé.
La partie continue jusqu'à ce qu'il ne reste qu'un vainqueur.

## Structure

```
fifa/
├── scraper.py               # scrap Transfermarkt (valeur marchande + profil)
├── scripts/update_data.py   # lance le scrap complet puis insère en base
├── app/
│   ├── main.py              # serveur FastAPI + static
│   ├── config.py            # configuration (base de données, heure du scrap)
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # tables : players, games, rounds, questions, réponses
│   ├── questions.py         # génération des 4 questions + choix proches de la bonne réponse
│   ├── seed.py              # upsert des joueurs scrapés en base
│   ├── scheduler.py         # automatise la mise à jour à 22h00
│   ├── routers/             # API (game + data)
│   └── static/              # interface web (HTML/CSS/JS)
├── Dockerfile
├── docker-compose.yml       # app + PostgreSQL (données persistées en volume)
└── requirements.txt
```

## Démarrage rapide (Docker)

```bash
docker compose up --build
```

- Jeu : http://localhost:8000
- L'application crée les tables puis, si la base est vide, fait un premier scrap (liste
  uniquement) pour que tu puisses jouer immédiatement.
- Le scrap complet (avec profils) se lance automatiquement chaque jour à 22h00.

Mise à jour manuelle à tout moment :

```bash
docker compose exec app python scripts/update_data.py
```

## Démarrage sans Docker (développement)

Il faut PostgreSQL qui tourne en local.

```bash
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/fifa
python scripts/update_data.py     # premier remplissage
uvicorn app.main:app --reload     # serveur sur http://localhost:8000
```

## Règles du jeu

1. On choisit le nombre de joueurs (2 à 12) et on tape leurs noms.
2. Un joueur de foot est choisi : chaque participant doit répondre aux 4 questions
   (âge, valeur marchande, club, nationalité, poste, taille, pied fort...).
3. Les choix proposés sont générés près de la bonne réponse (ex. âge 19 → 18/19/20/17).
4. Les participants se passent le téléphone. Rien n'est révélé avant la fin du tour.
5. À la fin, les bonnes réponses s'affichent une par une, puis les scores.
6. Le(s) plus mauvais est/sont éliminé(s), la manche suivante recommence.
7. Le dernier restant gagne la partie.

## Base de données

- PostgreSQL tourne dans Docker (`db`), les données sont persistées dans le volume
  nommé `footquiz_pgdata` → aucun risque de perte au redémarrage.
- `players` : tous les champs scrapés (valeur marchande, âge, nationalité, club,
  taille, pied, contrat, agent, etc.).

## Scrapping

- `scraper.py` récupère les ~500 joueurs les plus chers de transfermarkt.fr (20 pages).
- Avec `--profiles`, il visite aussi chaque page joueur (données complètes).
- Les liens `portrait_url` utilisent la taille `big`.

```bash
python scraper.py --max-pages 2          # seulement les 2 premières pages
python scraper.py --profiles             # liste + profils détaillés
```