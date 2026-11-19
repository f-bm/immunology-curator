# 🧬 Veille Hebdomadaire en Immunologie Clinique, DIP/IEI & Maladies Auto-inflammatoires

Ce projet automatise de bout en bout une veille de littérature scientifique basée exclusivement sur des publications revues par les pairs (*peer-reviewed* sur PubMed) et produit :
1. **Un classement hiérarchique dynamique sur Notion** par sections IUIS et fiches pathologies (ex: *Déficits combinés* > *Syndrome de Wiskott-Aldrich*), avec enrichissement cumulatif au fil des semaines.
2. **Un podcast audio hebdomadaire** généré par synthèse vocale neurale en français.
3. **Un flux RSS standard pour podcast** consultable sur votre application mobile préférée (Apple Podcasts, Pocket Casts, Overcast...).
4. **Une orchestration 100% autonome et gratuite** via GitHub Actions.

---

## 📁 Architecture des Fichiers

```text
immunology-curator/
├── .github/workflows/
│   └── weekly_digest.yml     # Automatisation GitHub Actions (lundi 07h00)
├── src/
│   ├── pubmed.py             # Requêtes ciblées PubMed E-Utilities
│   ├── llm.py                # Classification IUIS & script de podcast
│   ├── tts.py                # Synthèse vocale haute fidélité (Edge-TTS)
│   ├── rss.py                # Gestionnaire du flux Podcast RSS (feed.xml)
│   └── notion.py             # Gestion de l'arborescence dynamique Notion
├── main.py                   # Script orchestrateur
├── requirements.txt          # Dépendances Python
├── .env.example              # Modèle de variables d'environnement
└── README.md                 # Guide d'installation et d'utilisation
```

---

## 🚀 Guide de Configuration Étape par Étape

### 1. Configuration de Notion

1. Rendez-vous sur votre espace Notion et créez une nouvelle page principale (ex: **"Veille Immunologie Clinique"**).
2. Rendez-vous sur [Notion Developers - My Integrations](https://www.notion.so/profile/integrations).
3. Cliquez sur **"+ New integration"**, nommez-la (ex: *Curateur Immunologie*), sélectionnez votre espace de travail et validez.
4. Copiez le **Internal Integration Secret** (commence par `secret_...`). Ce sera votre `NOTION_API_KEY`.
5. Retournez sur votre page Notion créée à l'étape 1 :
   * Cliquez sur les `...` en haut à droite > **Connexions** > Recherchez et ajoutez votre intégration *Curateur Immunologie*.
   * Copiez l'URL de la page. L'identifiant `NOTION_ROOT_PAGE_ID` correspond aux 32 caractères hexadécimaux à la fin de l'URL (sans les tirets).
   * *Exemple d'URL :* `https://www.notion.so/Veille-Immunologie-a1b2c3d4e5f6...` ➔ ID = `a1b2c3d4e5f6...`.

---

### 2. Clé API d'Analyse (Gemini ou OpenAI)

* **Gemini (Recommandé & Gratuit)** : Obtenez une clé sur [Google AI Studio](https://aistudio.google.com/) et définissez-la dans `GEMINI_API_KEY`.
* *(Alternative)* : Vous pouvez aussi définir `OPENAI_API_KEY`.

---

### 3. Test Local sur votre Machine

1. Créez un environnement virtuel et installez les dépendances :
   ```bash
   cd /Users/fred/.gemini/antigravity/scratch/immunology-curator
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Créez votre fichier `.env` à partir de `.env.example` :
   ```bash
   cp .env.example .env
   ```
   Renseignez-y vos clés.

3. **Tester immédiatement en mode simulation (sans consommer d'API et sans écrire sur Notion)** :
   ```bash
   python main.py --mock --dry-run
   ```
   *Ce test va générer un fichier audio `archives/episode_...mp3` et mettre à jour `feed.xml`.*

4. **Lancer la vraie veille des 7 derniers jours** :
   ```bash
   python main.py --days 7
   ```

---

### 4. Automatisation Complète sur GitHub Actions

1. Poussez ce dossier sur un dépôt GitHub (privé ou public).
2. Dans votre dépôt GitHub : **Settings > Secrets and variables > Actions > New repository secret** :
   * `GEMINI_API_KEY`
   * `NOTION_API_KEY`
   * `NOTION_ROOT_PAGE_ID`
3. Activez **GitHub Pages** dans **Settings > Pages** :
   * Source : `Deploy from a branch` (branche `main`, dossier `/ (root)`).
4. **S'abonner au podcast sur votre téléphone** :
   * Votre URL de flux sera :
     `https://<votre-pseudo-github>.github.io/<nom-du-repo>/feed.xml`
   * Dans Apple Podcasts : *Bibliothèque > Suivre une émission par URL*.
   * Dans Pocket Casts / Overcast / AntennaPod : *Rechercher > Coller l'URL du flux*.
