# 🎯 X-HEC Interview Coach

Agent IA voice-to-voice pour s'entraîner aux entretiens du Master X-HEC Entrepreneurs.

## Fonctionnalités

- **Upload de dossier** : CV (PDF) + Questions préparées (Excel)
- **2 modes d'entraînement** :
  - **Question par Question** : Feedback immédiat après chaque réponse
  - **Simulation 20 min** : Entretien complet avec debrief global à la fin
- **Voice-to-voice** : Parle directement avec le coach via ton micro
- **Feedback constructif** : Le coach détecte les tics verbaux, le manque d'exemples, l'absence de lien avec X-HEC
- **Résumé final** : Points forts, axes d'amélioration, key learnings
- **Transcript téléchargeable** : Garde une trace de ta session

## Installation locale

### Prérequis

- Python 3.11+
- Clé API Mistral ([console.mistral.ai](https://console.mistral.ai/))

### Setup

```bash
# Clone le repo
cd "Mistral API"

# Crée un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installe les dépendances
pip install -r requirements.txt

# Configure les variables d'environnement
cp .env.example .env
# Édite .env et ajoute ta clé MISTRAL_API_KEY

# Lance l'app
python main.py
```

L'app sera disponible sur [http://localhost:8000](http://localhost:8000)

## Déploiement sur Render

1. Push ton code sur GitHub
2. Connecte-toi à [Render.com](https://render.com)
3. Crée un nouveau "Web Service"
4. Connecte ton repo GitHub
5. Configure les variables d'environnement :
   - `MISTRAL_API_KEY` : Ta clé API Mistral
6. Deploy !

Le fichier `render.yaml` configure automatiquement le déploiement.

## Format du fichier Excel

Le fichier Excel des questions doit avoir au minimum une colonne `question` :

| question | reponse (optionnel) | theme (optionnel) |
|----------|---------------------|-------------------|
| Pourquoi X-HEC ? | Ma réponse préparée... | Motivation |
| Parle-moi de ton projet | ... | Projet |

## Structure du projet

```
Mistral API/
├── main.py                 # FastAPI app
├── requirements.txt        # Dépendances
├── services/
│   ├── mistral_agent.py    # Logique IA Mistral
│   ├── file_parser.py      # Parsing PDF/Excel
│   ├── scraper.py          # Scraper pineurs.com
│   └── session.py          # Gestion des sessions
├── data/
│   └── master_context.json # Contexte X-HEC scrapé
├── static/
│   ├── index.html          # Interface web
│   ├── style.css           # Styles
│   └── app.js              # Logique front + voice
├── prompts/
│   └── coach_prompt.py     # Prompts système
└── uploads/                # Fichiers temporaires
```

## API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Interface web |
| `/api/upload` | POST | Upload CV + Questions |
| `/api/session/create` | POST | Créer une session |
| `/api/interview/start` | POST | Démarrer l'entretien |
| `/api/interview/respond` | POST | Soumettre une réponse |
| `/api/interview/next-question` | POST | Question suivante |
| `/api/interview/summary` | POST | Générer le résumé |
| `/api/interview/transcript/{id}` | GET | Télécharger le transcript |
| `/admin/rescrape` | POST | Forcer le re-scrape de pineurs.com |
| `/health` | GET | Health check |

## Technologies

- **Backend** : FastAPI (Python)
- **Frontend** : HTML/CSS/JS vanilla
- **IA** : Mistral AI
- **Voice** : Web Speech API (STT + TTS)
- **Scraping** : BeautifulSoup

## Notes importantes

- Le voice-to-voice nécessite **Chrome ou Edge** (Web Speech API)
- Le site doit être en **HTTPS** pour que le micro fonctionne (automatique sur Render)
- Le contexte X-HEC est scrapé depuis [pineurs.com](https://www.pineurs.com/en)

## Contribuer

Feel free to open issues ou PRs pour améliorer le coach !

---

Made with 🎯 pour les futurs X-HEC Entrepreneurs
