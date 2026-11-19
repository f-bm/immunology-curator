#!/usr/bin/env python3
"""
Orchestrateur principal de la veille hebdomadaire en immunologie clinique,
DIP/IEI et maladies auto-inflammatoires.
"""

import argparse
from datetime import datetime
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Se placer dans le répertoire du projet pour garantir des chemins relatifs cohérents
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

# Ajout du dossier src au PYTHONPATH
sys.path.insert(0, os.path.join(PROJECT_DIR, "src"))

from pubmed import fetch_recent_immunology_papers
from llm import synthesize_and_classify
from tts import generate_podcast_audio
from rss import update_or_create_podcast_feed
from notion import NotionImmunoManager


def run_pipeline(days: int = 7, dry_run: bool = False, skip_audio: bool = False, mock: bool = False):
    print("=" * 70)
    print("🧬 DÉMARRAGE DU CURATEUR EN IMMUNOLOGIE CLINIQUE & DIP")
    print(f"📅 Date d'exécution : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 70)

    # 1. Récupération des articles
    if mock:
        print("🧪 Mode MOCK activé : utilisation d'articles de test.")
        articles = [
            {
                "pmid": "38451234",
                "title": "Lentiviral gene therapy for Wiskott-Aldrich syndrome: Long-term clinical and immunological outcomes in a multicenter cohort",
                "journal": "Blood",
                "url": "https://pubmed.ncbi.nlm.nih.gov/38451234/",
                "abstract": "Wiskott-Aldrich syndrome (WAS) is an X-linked inborn error of immunity caused by mutations in the WAS gene, characterized by microthrombocytopenia, eczema, recurrent infections, and high risk of autoimmunity and malignancies. In this study, we evaluate 35 patients treated with autologous hematopoietic stem and progenitor cell gene therapy using a lentiviral vector encoding human WAS cDNA under the control of a 1.6-kb human WAS promoter. Over a median follow-up of 8.5 years, overall survival was 94%. Platelet counts showed sustained improvement, severe infections ceased, and eczema resolved in all surviving patients. Vector integration site analysis showed polyclonal hematopoietic reconstitution without clonal dominance or insertional oncogenesis."
            },
            {
                "pmid": "38455678",
                "title": "Early TNF inhibition prevents recurrent ischemic stroke and inflammatory burden in pediatric deficiency of adenosine deaminase 2 (DADA2)",
                "journal": "Journal of Allergy and Clinical Immunology",
                "url": "https://pubmed.ncbi.nlm.nih.gov/38455678/",
                "abstract": "Deficiency of adenosine deaminase 2 (DADA2) is an autosomal recessive monogenic autoinflammatory disorder caused by biallelic loss-of-function mutations in ADA2 (formerly CECR1). It manifests with early-onset lacunar strokes, systemic vasculitis resembling polyarteritis nodosa, livedo racemosa, and variable immunodeficiency. We conducted a retrospective longitudinal study of 42 pediatric DADA2 patients initiated on anti-TNF therapy (adalimumab or etanercept) immediately following genetic diagnosis. Zero stroke episodes occurred after initiation of TNF blockade during 180 patient-years of follow-up, compared to 1.8 strokes per patient-year pre-treatment. Serum inflammatory markers (CRP, SAA) normalized within 4 weeks. Anti-TNF agents represent the gold standard disease-modifying therapy for preventing neurovascular catastrophes in DADA2."
            }
        ]
    else:
        articles = fetch_recent_immunology_papers(days=days)

    if not articles:
        print("ℹ️ Aucun nouvel article scientifique trouvé sur cette période.")
        return

    # 2. Analyse, classification et rédaction par LLM
    print("\n--- 🧠 ANALYSE & CLASSIFICATION SCIENTIFIQUE ---")
    classified_articles, audio_script, weekly_overview = synthesize_and_classify(articles)
    print(f"📊 Articles retenus pour l'analyse : {len(classified_articles)}")

    # Sauvegarde locale du rapport au format JSON pour archive
    os.makedirs("archives", exist_ok=True)
    week_str = datetime.now().strftime("%Y-W%W")
    archive_file = f"archives/digest_{week_str}.json"
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump({
            "week": week_str,
            "date": datetime.now().isoformat(),
            "classified_articles": classified_articles,
            "weekly_overview": weekly_overview,
            "audio_script": audio_script
        }, f, indent=2, ensure_ascii=False)
    print(f"💾 Synthèse archivée localement dans : {archive_file}")

    # 3. Génération du podcast audio (TTS)
    audio_path = f"archives/episode_{week_str}.mp3"
    if not skip_audio and audio_script:
        print("\n--- 🎙️ SYNTHÈSE VOCALE DU PODCAST ---")
        generate_podcast_audio(audio_script, output_path=audio_path)
    else:
        print("⏭️ Étape audio ignorée.")

    # 4. Mise à jour du flux RSS Podcast
    if os.path.exists(audio_path):
        print("\n--- 📡 MISE À JOUR DU FLUX PODCAST RSS ---")
        base_url = os.getenv("PODCAST_BASE_URL", "https://votre-compte.github.io/immunology-curator")
        audio_url = f"{base_url}/archives/episode_{week_str}.mp3"
        episode_title = f"Immunologie Hebdo - Semaine {datetime.now().strftime('%W (%d/%m/%Y)')}"
        update_or_create_podcast_feed(
            feed_path="feed.xml",
            episode_title=episode_title,
            episode_description=weekly_overview,
            audio_url=audio_url,
            audio_file_path=audio_path
        )

    # 5. Rangement hiérarchique dans Notion
    if not dry_run:
        print("\n--- 📂 RANGEMENT DANS L'ARBORESCENCE NOTION ---")
        notion_mgr = NotionImmunoManager()
        notion_mgr.sync_all(classified_articles)
    else:
        print("⏭️ Mode DRY-RUN : Synchronisation Notion ignorée.")

    print("\n" + "=" * 70)
    print("🎉 VEILLE SCIENTIFIQUE TERMINÉE AVEC SUCCÈS !")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curateur de veille en immunologie clinique.")
    parser.add_argument("--days", type=int, default=7, help="Nombre de jours de recul pour PubMed (défaut : 7)")
    parser.add_argument("--dry-run", action="store_true", help="Exécute sans écrire sur Notion")
    parser.add_argument("--skip-audio", action="store_true", help="Ignore la génération du fichier MP3")
    parser.add_argument("--mock", action="store_true", help="Utilise des articles factices pour tester le pipeline")
    args = parser.parse_args()

    run_pipeline(
        days=args.days,
        dry_run=args.dry_run,
        skip_audio=args.skip_audio,
        mock=args.mock
    )
