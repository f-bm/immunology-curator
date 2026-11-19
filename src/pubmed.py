"""
Module de récupération des publications scientifiques sur PubMed via les E-utilities du NCBI.
Cible spécifiquement l'immunologie clinique, les erreurs innées de l'immunité (DIP/IEI)
et les maladies auto-inflammatoires.
"""

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

try:
    import requests
except ImportError:
    requests = None


def _http_get(url: str, params: dict = None) -> bytes:
    """Requête HTTP GET compatible avec requests ou urllib standard."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    if requests:
        resp = requests.get(url, timeout=25)
        resp.raise_for_status()
        return resp.content
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "ImmunologyCurator/1.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            return response.read()


def fetch_recent_immunology_papers(days: int = 7, max_results: int = 60) -> List[Dict]:
    """
    Interroge l'API PubMed pour récupérer les articles peer-reviewed des derniers 'days' jours.
    Augmente le volume de récupération initial (max_results=60) pour permettre un filtrage
    strict sur les revues à fort impact (IF > 10).
    """
    query = (
        '("Inborn Errors of Immunity"[Mesh] OR "Primary Immunodeficiency Diseases"[Mesh] '
        'OR "Autoinflammatory Diseases"[Mesh] OR "autoinflammatory"[Title/Abstract] '
        'OR "inborn errors of immunity"[Title/Abstract] OR "monogenic autoinflammatory"[Title/Abstract]) '
        'AND "Journal Article"[Publication Type]'
    )

    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "reldate": days,
        "datetype": "edat",
        "retmax": max_results,
        "retmode": "json",
    }

    print(f"🔍 Recherche PubMed en cours (derniers {days} jours)...")
    try:
        content = _http_get(esearch_url, search_params)
        search_data = json.loads(content.decode("utf-8"))
    except Exception as e:
        print(f"❌ Erreur lors de l'appel ESearch PubMed : {e}")
        return []

    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    print(f"📄 {len(id_list)} articles identifiés.")

    if not id_list:
        return []

    efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml",
    }

    try:
        xml_content = _http_get(efetch_url, fetch_params)
        root = ET.fromstring(xml_content)
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction EFetch PubMed : {e}")
        return []

    articles = []
    for article_node in root.findall(".//PubmedArticle"):
        title = article_node.findtext(".//ArticleTitle", default="Sans titre").strip()
        
        # Concaténation de tous les paragraphes d'AbstractText
        abstract_nodes = article_node.findall(".//AbstractText")
        abstract_parts = []
        for node in abstract_nodes:
            label = node.get("Label")
            text = node.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            elif text:
                abstract_parts.append(text)
        abstract = "\n".join(abstract_parts).strip()

        journal = article_node.findtext(".//Journal/Title", default="Revue inconnue").strip()
        pmid = article_node.findtext(".//MedlineCitation/PMID", default="").strip()

        # Récupération du DOI si disponible
        doi = ""
        for article_id in article_node.findall(".//ArticleId"):
            if article_id.get("IdType") == "doi":
                doi = article_id.text or ""
                break

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else "")

        # On ne conserve que les publications qui ont un résumé analysable
        if abstract and len(abstract) > 100:
            articles.append({
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "journal": journal,
                "abstract": abstract,
                "url": url,
            })

    print(f"✅ {len(articles)} articles complets avec abstract prêts pour l'analyse.")
    return articles
