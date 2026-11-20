"""
Module d'analyse, classification et synthèse par LLM (Gemini / OpenAI).
Gère :
  - Le filtrage strict sur les revues à fort impact (IF > 10 + Journal of Human Immunity)
  - La rédaction au format exact « Inbox Immunologie » (3 Take-Home Messages, Contexte,
    Principales conclusions, Implications en pratique clinique)
  - Le mapping exact vers la base Notion « 🧬 Maladies IUIS 2024 » (617 entrées) ou les 12 dossiers thématiques
  - L'écriture du script de podcast audio expert en français
"""

import json
import os
from typing import Dict, List, Optional, Tuple


# Liste canonique des sections pour le dossier "Veille immunologie"
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


def _format_iuis_catalog(iuis_rows: Optional[List[Dict]], thematic_folders: Optional[Dict[str, str]]) -> str:
    parts = []
    if iuis_rows:
        lines = [
            f"{r['id']} | {r['title']} | Gene: {r.get('gene', '') or '-'} | {r.get('table', '')}"
            for r in iuis_rows
        ]
        parts.append("=== BASE '🧬 Maladies IUIS 2024' (format: ID | Maladie | Gene | Table IUIS) ===\n" + "\n".join(lines))
    if thematic_folders:
        flines = [f"{fid} | {fname}" for fname, fid in thematic_folders.items()]
        parts.append("=== DOSSIERS THÉMATIQUES (pour articles transversaux hors maladie unique) ===\n" + "\n".join(flines))
    return "\n\n".join(parts)


def _enrich_pubmed_metadata(classified: List[Dict], raw_articles: List[Dict]) -> List[Dict]:
    """Réinjecte pmcid/doi depuis les articles PubMed bruts au cas où le LLM les omettrait."""
    by_url = {a.get("url", ""): a for a in raw_articles if a.get("url")}
    by_title = {a.get("title", "").lower().strip(): a for a in raw_articles if a.get("title")}
    for item in classified:
        src = by_url.get(item.get("url", "")) or by_title.get((item.get("original_title") or "").lower().strip())
        if src:
            if not item.get("pmcid") and src.get("pmcid"):
                item["pmcid"] = src["pmcid"]
            if not item.get("doi") and src.get("doi"):
                item["doi"] = src["doi"]
            if not item.get("url") and src.get("url"):
                item["url"] = src["url"]
    return classified


def synthesize_and_classify(
    articles: List[Dict],
    iuis_rows: Optional[List[Dict]] = None,
    thematic_folders: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict], str, str]:
    """
    Analyse les articles avec Gemini (ou OpenAI si configuré).
    Retourne :
      - classified_articles : liste d'articles au format complet Inbox Immunologie + mapping IUIS 2024
      - audio_script : script du podcast oralisé en français (niveau expert)
      - weekly_overview : vue d'ensemble écrite de la semaine
    """
    if not articles:
        return [], "", "Aucun article identifié cette semaine."

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    catalog_text = _format_iuis_catalog(iuis_rows, thematic_folders)

    prompt = f"""
Tu es un médecin spécialiste de référence en immunologie clinique pédiatrique et adulte,
expert international des erreurs innées de l'immunité (DIP/IEI) et des pathologies auto-inflammatoires.

Voici la liste des articles scientifiques récents ({len(articles)} articles) récupérés sur PubMed :
{json.dumps(articles, indent=2, ensure_ascii=False)}

{catalog_text}

Effectue une sélection et une analyse rigoureuses respectant les contraintes suivantes :

🚨 CRITÈRE STRICT DE FILTRAGE DES REVUES :
Ne retiens QUE les articles parus dans :
1. Des revues prestigieuses à HAUT FACTEUR D'IMPACT (Impact Factor > 10). Exemples typiques :
   - N Engl J Med, Lancet, JAMA, Nature, Science, Cell
   - Nature Immunology, Immunity, Science Immunology, J Exp Med (JEM)
   - J Allergy Clin Immunol (JACI), Blood, Annals of the Rheumatic Diseases (ARD)
   - Nature Medicine, Journal of Clinical Investigation (JCI), Science Translational Medicine
   - Lancet Rheumatology, Nature Communications, Leukemia, Gut, Gastroenterology
2. OU la revue spécialisée "Journal of Human Immunity" (ou "Human Immunology" / "Journal of Clinical Immunology" si proche du seuil).
ÉCARTE SYSTÉMATIQUEMENT toutes les revues mineures (exclure les journaux de case reports de bas rang comme 'Journal of Medical Case Reports', les revues prédatrices ou secondaires).
Si aucun article de la semaine ne dépasse IF > 10, sélectionne les 2 à 3 meilleures études des revues de référence les plus proches de ce seuil.

Effectue une analyse approfondie au STANDARD EXACT DE LA BIBLIOTHÈQUE « 🛡️ Immunologie » et produis un objet JSON contenant :

1. "classified_articles" : Liste des articles sélectionnés (idéalement 3 à 7 articles de haute volée).
   Pour CHAQUE article :
   - "title": Titre scientifique complet et propre en français
   - "original_title": Titre original exact de PubMed
   - "journal": Revue de publication
   - "impact_factor_est": Estimation de l'Impact Factor (ex: "IF ~16", "IF > 20")
   - "url": URL PubMed exacte
   - "doi": DOI si disponible (sinon "")
   - "pmcid": PMCID si disponible (sinon "")
   - "section": DOIT ÊTRE STRICTEMENT l'une des catégories suivantes (pour le dossier Veille immunologie) :
{json.dumps(IUIS_SECTIONS, indent=4, ensure_ascii=False)}
   - "disease_or_topic": Nom canonique et précis de la pathologie en français (ex: "Syndrome de Wiskott-Aldrich", "Déficit en ADA2 (DADA2)", "Syndrome VEXAS", "FMF", "DICV").
   - "take_home_messages": Liste de EXACTEMENT 3 points clés cliniques percutants et directement actionnables (format court, concret).
   - "context": Contexte physiopathologique, gène/voie moléculaire impliquée et objectif de l'étude (2 à 3 phrases précises).
   - "key_findings": Liste de 3 à 4 conclusions majeures / résultats chiffrés ou mécanismes démontrés dans l'étude.
   - "clinical_practice": Implications concrètes pour le diagnostic, le bilan biologique/génétique (NGS, tests fonctionnels) et la prise en charge thérapeutique (2 à 3 phrases).
   - "gene_pathway": Gène(s) muté(s) et voie de signalisation intracellulaire.
   - "iuis_dest_id": L'ID EXACT (UUID) copié depuis la BASE '🧬 Maladies IUIS 2024' ci-dessus si l'article porte sur une maladie/gène/groupe immunologique, OU depuis les DOSSIERS THÉMATIQUES si l'article est transversal (hors maladie spécifique).
   - "iuis_dest_type": "iuis_row" (si l'ID vient de la base IUIS 2024) ou "thematic_folder" (si l'ID vient d'un dossier thématique).
   - "iuis_dest_name": Nom exact de la maladie IUIS ou du dossier thématique correspondant à cet ID.
   - "iuis_table_name": Nom exact de la Table IUIS (ex: "07. Autoinflammatory disorders") si iuis_dest_type == "iuis_row", sinon "".

2. "weekly_overview": Vue d'ensemble synthétique des grandes tendances de la semaine (format Markdown).

3. "audio_script": Script de podcast audio de HAUT NIVEAU MÉDICAL (destiné aux immunologistes, internistes et hématologues) :
   - Ton : Rigueur académique, direct, professionnel, rythmé et captivant.
   - Pas de vulgarisation simpliste : utiliser la terminologie exacte (cytokines, récepteurs, voies JAK/STAT, inflammasomes NLRP3, voies NF-kB, panels NGS, etc.).
   - Structure pour chaque article présenté :
     a. L'enjeu clinique ou physiopathologique
     b. Les principales conclusions démontrées
     c. Les "Take-Home Messages" explicites pour la pratique courante.
   - Durée : environ 5 à 7 minutes de parole fluide.

RÉPONDS EXCLUSIVEMENT AVEC UN OBJET JSON VALIDE respectant ce schéma :
{{
  "classified_articles": [...],
  "weekly_overview": "...",
  "audio_script": "..."
}}
"""

    if gemini_key:
        print("🧠 Analyse, synthèse Inbox-grade & mapping IUIS 2024 via Gemini API...")
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)

            candidate_models = [
                "gemini-3.1-flash-lite",
                "gemini-3.8-flash",
                "gemini-3.1-pro-preview",
                "gemini-flash-latest",
                "gemini-pro-latest",
            ]

            response = None
            last_err = None
            for model_name in candidate_models:
                try:
                    print(f"   ↳ Essai avec {model_name}...")
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={"response_mime_type": "application/json"},
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

            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            data = json.loads(raw_text)
            classified = _enrich_pubmed_metadata(data.get("classified_articles", []), articles)
            return (
                classified,
                data.get("audio_script", ""),
                data.get("weekly_overview", ""),
            )
        except Exception as e:
            print(f"⚠️ Erreur avec google-genai : {e}")

    if openai_key:
        print("🧠 Analyse et synthèse via OpenAI API...")
        import urllib.request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}",
        }
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            content = res_body["choices"][0]["message"]["content"]
            data = json.loads(content)
            classified = _enrich_pubmed_metadata(data.get("classified_articles", []), articles)
            return (
                classified,
                data.get("audio_script", ""),
                data.get("weekly_overview", ""),
            )

    if not gemini_key and not openai_key:
        print("💡 Aucune clé API LLM détectée. Utilisation d'une classification de démonstration...")
        mock_classified = [
            {
                "title": "Thérapie génique lentivirale pour le syndrome de Wiskott-Aldrich : Résultats cliniques et immunologiques à long terme",
                "original_title": articles[0].get("title", ""),
                "journal": articles[0].get("journal", "Blood"),
                "impact_factor_est": "IF ~21",
                "url": articles[0].get("url", ""),
                "section": "Déficits immunitaires avec anomalies syndromiques",
                "disease_or_topic": "Syndrome de Wiskott-Aldrich",
                "take_home_messages": [
                    "La thérapie génique lentivirale autologue offre une survie globale de 94 % à 8,5 ans dans le syndrome de Wiskott-Aldrich.",
                    "Reconstitution hématopoïétique polyclonale stable sans oncogenèse insertionnelle ni maladie du greffon contre l'hôte.",
                    "Alternative pérenne de choix chez les patients sans donneur HLA-identique.",
                ],
                "context": "Le syndrome de Wiskott-Aldrich (gène WAS, Xp11.23) associe microthrombopénie, eczéma, infections sévères et auto-immunité. Cette étude multicentrique évalue la sécurité et l'efficacité à long terme d'un vecteur lentiviral autologue.",
                "key_findings": [
                    "Cohorte de 35 patients suivis sur une médiane de 8,5 ans (survie globale : 94 %).",
                    "Amélioration durable du taux plaquettaire et disparition des infections sévères et de l'eczéma.",
                    "Absence de dominance clonale ou de leucémogenèse à l'analyse des sites d'intégration.",
                ],
                "clinical_practice": "Positionne la thérapie génique lentivirale comme une option curative validée à long terme dans le WAS en l'absence de donneur géno-identique.",
                "gene_pathway": "Gène WAS (Xp11.23) / Polymérisation de l'actine et cytosquelette.",
                "iuis_dest_id": "",
                "iuis_dest_type": "iuis_row",
                "iuis_dest_name": "Wiskott-Aldrich syndrome",
                "iuis_table_name": "02. CID with syndromic features",
            }
        ]
        mock_overview = "Confirmation à long terme (8,5 ans) de l'efficacité et de la sécurité de la thérapie génique dans le syndrome de Wiskott-Aldrich."
        mock_script = "Bonjour à tous. Cette semaine, Blood confirme les résultats à plus de 8 ans de la thérapie génique lentivirale dans le syndrome de Wiskott-Aldrich."
        return mock_classified, mock_script, mock_overview

    raise ValueError("Aucune clé API configurée. Veuillez renseigner GEMINI_API_KEY ou OPENAI_API_KEY.")
