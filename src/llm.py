"""
Module d'analyse, classification et synthèse par LLM (Gemini / OpenAI).
Gère la classification IUIS stricte, la structuration par pathologie,
et l'écriture du script de podcast audio en français.
"""

import json
import os
from typing import Dict, List, Tuple


# Liste canonique des sections selon la classification officielle IUIS
IUIS_SECTIONS = [
    "Déficits immunitaires combinés",
    "Déficits immunitaires avec anomalies syndromiques",
    "Déficits à prédominance humorale",
    "Maladies de la dérégulation immunitaire",
    "Défauts congénitaux des phagocytes",
    "Maladies auto-inflammatoires",
    "Déficits de l'immunité innée et intrinsèque",
    "Déficits du complément",
    "Insuffisances médullaires et phénocopies",
]


def synthesize_and_classify(articles: List[Dict]) -> Tuple[List[Dict], str, str]:
    """
    Analyse les articles avec Gemini (ou OpenAI si configuré).
    Retourne :
      - classified_articles : liste d'articles classifiés (section, maladie, synthèse clinique)
      - audio_script : script du podcast oralisé en français
      - weekly_overview : vue d'ensemble écrite de la semaine
    """
    if not articles:
        return [], "", "Aucun article identifié cette semaine."

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    prompt = f"""
Tu es un médecin spécialiste de référence en immunologie clinique pédiatrique et adulte,
expert international des erreurs innées de l'immunité (DIP/IEI) et des pathologies auto-inflammatoires.

Voici la liste des articles scientifiques récents ({len(articles)} articles) récupérés sur PubMed :
{json.dumps(articles, indent=2, ensure_ascii=False)}

Effectue une sélection et une analyse rigoureuses respectant les contraintes suivantes :

🚨 CRITÈRE STRICT DE FILTRAGE DES REVUES :
Ne retiens QUE les articles parus dans :
1. Des revues prestigieuses à HAUT FACTEUR D'IMPACT (Impact Factor > 10). Exemples typiques :
   - N Engl J Med, Lancet, JAMA, Nature, Science, Cell
   - Nature Immunology, Immunity, Science Immunology, J Exp Med (JEM)
   - J Allergy Clin Immunol (JACI), Blood, Annals of the Rheumatic Diseases (ARD)
   - Nature Medicine, Journal of Clinical Investigation (JCI), Science Translational Medicine
   - Lancet Rheumatology, Nature Communications, Leukemia, Gut, Gastroenterology
2. OU la revue spécialisée "Journal of Human Immunity" (ou "Human Immunology").
ÉCARTE SYSTÉMATIQUEMENT toutes les revues avec un IF < 10 (exclure les revues de case reports mineurs comme 'Journal of Medical Case Reports', les revues prédatrices ou secondaires).
Si aucun article de la semaine ne dépasse IF > 10, sélectionne les 2 à 3 meilleures études des revues de référence les plus proches de ce seuil.

Effectue une analyse approfondie et produis un objet JSON contenant :

1. "classified_articles" : Liste des articles sélectionnés (idéalement 3 à 7 articles de haute volée).
   Pour chaque article :
   - "title": Titre clair en français
   - "original_title": Titre original
   - "journal": Revue de publication
   - "impact_factor_est": Estimation de l'Impact Factor (ex: "IF ~14", "IF > 20")
   - "url": URL PubMed ou DOI
   - "section": DOIT ÊTRE STRICTEMENT l'une des catégories IUIS suivantes :
{json.dumps(IUIS_SECTIONS, indent=4, ensure_ascii=False)}
   - "disease_or_topic": Nom canonique et précis de la pathologie en français (ex: "Syndrome de Wiskott-Aldrich", "Déficit en ADA2 (DADA2)", "Syndrome VEXAS", "FMF", "DICV").
   - "take_home_message": LE message clé pratique et immédiat pour le clinicien (1 à 2 phrases percutantes, actionnables).
   - "main_conclusions": Les 2 ou 3 conclusions majeures démontrées dans l'étude (résultats chiffrés, cohorte, mécanisme prouvé).
   - "clinical_impact": Implications concrètes en pratique (diagnostic précoce, nouvelle cible moléculaire, posologie/biothérapie, pronostic).
   - "gene_pathway": Gène(s) muté(s) et voie de signalisation intracellulaire.

2. "weekly_overview": Vue d'ensemble synthétique des grandes tendances de la semaine (format Markdown).

3. "audio_script": Script de podcast audio de HAUT NIVEAU MÉDICAL (destiné aux immunologistes, internistes et hématologues) :
   - Ton : Rigueur académique, direct, professionnel, rythmé et captivant.
   - Pas de vulgarisation simpliste : utiliser la terminologie exacte (cytokines, récepteurs, voies JAK/STAT, inflammasomes NLRP3, voies NF-kB, etc.).
   - Structure pour chaque article présenté :
     a. L'enjeu clinique ou physiopathologique
     b. Les principales conclusions
     c. Le "Take-Home Message" explicite pour la pratique courante.
   - Durée : environ 5 à 7 minutes de parole fluide.

RÉPONDS EXCLUSIVEMENT AVEC UN OBJET JSON VALIDE respectant ce schéma :
{{
  "classified_articles": [...],
  "weekly_overview": "...",
  "audio_script": "..."
}}
"""

    if gemini_key:
        print("🧠 Analyse et synthèse via Gemini API...")
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            
            # Modèles disponibles selon l'état du serveur
            candidate_models = [
                "gemini-3.1-flash-lite",
                "gemini-3.8-flash",
                "gemini-3.1-pro-preview",
                "gemini-flash-latest",
                "gemini-pro-latest"
            ]
            
            response = None
            last_err = None
            for model_name in candidate_models:
                try:
                    print(f"   ↳ Essai avec {model_name}...")
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    if res and res.text:
                        response = res
                        print(f"   ✅ Réponse obtenue avec succès via {model_name}.")
                        break
                except Exception as model_err:
                    print(f"   ⚠️ Échec sur {model_name} : {model_err}")
                    last_err = model_err
                    continue
            
            if not response or not response.text:
                raise last_err or RuntimeError("Aucune réponse générée par Gemini.")

            # Nettoyage au cas où des backticks markdown entourent le JSON
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            data = json.loads(raw_text)
            return (
                data.get("classified_articles", []),
                data.get("audio_script", ""),
                data.get("weekly_overview", "")
            )
        except Exception as e:
            print(f"⚠️ Erreur avec google-genai : {e}")

    if openai_key:
        print("🧠 Analyse et synthèse via OpenAI API...")
        import urllib.request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
                                     data=json.dumps(body).encode("utf-8"),
                                     headers=headers)
        with urllib.request.urlopen(req) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            content = res_body["choices"][0]["message"]["content"]
            data = json.loads(content)
            return (
                data.get("classified_articles", []),
                data.get("audio_script", ""),
                data.get("weekly_overview", "")
            )

    if not gemini_key and not openai_key:
        print("💡 Aucune clé API LLM détectée. Utilisation d'une classification de démonstration...")
        mock_classified = [
            {
                "title": "Thérapie génique lentivirale pour le syndrome de Wiskott-Aldrich : Résultats cliniques et immunologiques à long terme",
                "original_title": articles[0].get("title", ""),
                "journal": articles[0].get("journal", "Blood"),
                "url": articles[0].get("url", ""),
                "section": "Déficits immunitaires combinés",
                "disease_or_topic": "Syndrome de Wiskott-Aldrich",
                "gene_pathway": "Gène WAS (Xp11.23), régulateur de la polymérisation de l'actine et du cytosquelette.",
                "findings": "Survie globale de 94 % sur 8,5 ans de suivi après thérapie génique lentivirale autologue. Correction stable de la microthrombopénie et résolution durable de l'eczéma et des infections sévères.",
                "clinical_impact": "Confirme la thérapie génique comme alternative thérapeutique pérenne et sécurisée à la greffe de moelle osseuse allogénique (sans maladie du greffon contre l'hôte)."
            }
        ]
        if len(articles) > 1:
            mock_classified.append({
                "title": "L'inhibition précoce du TNF prévient les AVC ischémiques récurrents dans le déficit en adénosine désaminase 2 (DADA2)",
                "original_title": articles[1].get("title", ""),
                "journal": articles[1].get("journal", "JACI"),
                "url": articles[1].get("url", ""),
                "section": "Maladies auto-inflammatoires",
                "disease_or_topic": "Déficit en ADA2 (DADA2)",
                "gene_pathway": "Gène ADA2 (CECR1, 22q11.1), différenciation macrophagique et intégrité endothéliale.",
                "findings": "Zéro récidive d'accident vasculaire cérébral après initiation des anti-TNF (adalimumab/étanercept) sur 180 patients-années, contre 1,8 AVC/an avant traitement.",
                "clinical_impact": "Les anti-TNF constituent le traitement de référence de première intention pour neutraliser le risque neurovasculaire létal chez les patients pédiatriques atteints de DADA2."
            })
        
        mock_overview = (
            "Cette semaine met en lumière des avancées thérapeutiques majeures : la confirmation à très long terme (8 ans) "
            "de l'efficacité de la thérapie génique dans le syndrome de Wiskott-Aldrich, et le rôle protecteur absolu des anti-TNF "
            "face au risque d'AVC dans le déficit en ADA2 (DADA2)."
        )
        mock_script = (
            "Bonjour et bienvenue dans votre point de veille hebdomadaire en immunologie clinique et maladies auto-inflammatoires. "
            "Au programme cette semaine : deux avancées thérapeutiques déterminantes. "
            "D'abord, dans les déficits immunitaires combinés, une étude majeure publiée dans Blood confirme l'efficacité durable à plus de 8 ans "
            "de la thérapie génique lentivirale autologue pour les enfants atteints du syndrome de Wiskott-Aldrich. Les plaquettes se normalisent "
            "et les épisodes infectieux sévères disparaissent sans risque de maladie du greffon. "
            "Ensuite, du côté des maladies auto-inflammatoires, le Journal of Allergy and Clinical Immunology rapporte une cohorte pédiatrique "
            "dans le déficit en adénosine désaminase 2, le DADA2. L'instauration précoce d'un anti-TNF comme l'adalimumab a totalement éliminé "
            "le risque d'accident vasculaire cérébral ischémique récidivant. "
            "Merci pour votre écoute, et à la semaine prochaine pour de nouvelles découvertes scientifiques."
        )
        return mock_classified, mock_script, mock_overview

    raise ValueError("Aucune clé API configurée. Veuillez renseigner GEMINI_API_KEY ou OPENAI_API_KEY.")
