"""
Module d'intégration Notion.
Gère l'arborescence dynamique :
  - Page Racine
    └── Sous-page Section IUIS (ex: "Déficits immunitaires combinés")
        └── Sous-page Pathologie (ex: "Syndrome de Wiskott-Aldrich")
            └── Blocs chronologiques des articles (synthèse incrémentale)
"""

from datetime import datetime
import os
from typing import Dict, List, Optional

try:
    from notion_client import Client
except ImportError:
    Client = None


class NotionImmunoManager:
    def __init__(self, token: Optional[str] = None, root_page_id: Optional[str] = None):
        self.token = token or os.getenv("NOTION_API_KEY")
        self.root_page_id = (root_page_id or os.getenv("NOTION_ROOT_PAGE_ID", "")).replace("-", "")
        if not self.token or not self.root_page_id or not Client:
            if not Client:
                print("⚠️ Package 'notion-client' non installé (pip install notion-client).")
            else:
                print("⚠️ Configuration Notion manquante (NOTION_API_KEY ou NOTION_ROOT_PAGE_ID non définis).")
            self.client = None
        else:
            self.client = Client(auth=self.token)

    def find_or_create_child_page(self, parent_id: str, title: str, icon_emoji: str = "📁") -> str:
        """
        Recherche une page enfant par son titre. Si elle n'existe pas, la crée.
        Gère la pagination des blocs enfants de Notion.
        """
        if not self.client:
            return ""

        cursor = None
        while True:
            params = {"block_id": parent_id}
            if cursor:
                params["start_cursor"] = cursor
            response = self.client.blocks.children.list(**params)
            
            for block in response.get("results", []):
                if block.get("type") == "child_page":
                    page_title = block.get("child_page", {}).get("title", "").strip().lower()
                    if page_title == title.strip().lower():
                        return block["id"]
            
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        # Non trouvée : création de la sous-page
        print(f"✨ Création de la page Notion : '{title}' (Parent: {parent_id[:8]}...)")
        new_page = self.client.pages.create(
            parent={"page_id": parent_id},
            icon={"type": "emoji", "emoji": icon_emoji},
            properties={
                "title": [{"type": "text", "text": {"content": title}}]
            }
        )
        return new_page["id"]

    def append_article_summary(self, disease_page_id: str, article: Dict):
        """
        Ajoute la synthèse d'un article à la fin de la page dédiée à la pathologie.
        """
        if not self.client or not disease_page_id:
            return

        date_str = datetime.now().strftime("%d/%m/%Y")
        title = article.get("title") or article.get("original_title") or "Article sans titre"
        url = article.get("url", "")
        journal = article.get("journal", "Revue scientifique")
        if_est = article.get("impact_factor_est", "")
        gene = article.get("gene_pathway", "Non spécifié")
        take_home = article.get("take_home_message") or article.get("findings", "")
        conclusions = article.get("main_conclusions") or article.get("findings", "")
        impact = article.get("clinical_impact", "")

        link_dict = {"content": "Consulter sur PubMed ↗"}
        if url and url.startswith("http"):
            link_dict["link"] = {"url": url}

        journal_display = f"Revue : {journal} ({if_est})  |  " if if_est else f"Revue : {journal}  |  "

        blocks = [
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"📅 {date_str} — {title[:95]}"}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": journal_display}},
                        {"type": "text", "text": link_dict}
                    ]
                }
            },
            # Callout visuel pour le Take-Home Message pratique
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🎯"},
                    "color": "blue_background",
                    "rich_text": [
                        {"type": "text", "text": {"content": "Take-Home Message : "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": take_home}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Principales conclusions : "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": conclusions}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Gène & Voie moléculaire : "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": gene}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Implications pratiques & Clinique : "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": impact}}
                    ]
                }
            }
        ]

        self.client.blocks.children.append(block_id=disease_page_id, children=blocks)
        print(f"   ↳ Synthèse ajoutée à la page '{article.get('disease_or_topic')}'")

    def sync_all(self, classified_articles: List[Dict]):
        """
        Orchestre le rangement hiérarchique de l'ensemble des articles classifiés.
        """
        if not self.client:
            print("⚠️ Synchro Notion ignorée (client non initialisé).")
            return

        print(f"📂 Synchronisation de {len(classified_articles)} articles dans l'arborescence Notion...")
        for article in classified_articles:
            section_title = article.get("section", "Autres erreurs innées de l'immunité")
            disease_title = article.get("disease_or_topic", "Pathologies non classées")

            # 1. Obtenir ou créer la section IUIS
            section_id = self.find_or_create_child_page(self.root_page_id, section_title, icon_emoji="📂")

            # 2. Obtenir ou créer la page de la maladie
            disease_id = self.find_or_create_child_page(section_id, disease_title, icon_emoji="📄")

            # 3. Ajouter la synthèse
            self.append_article_summary(disease_id, article)

        print("✅ Synchronisation Notion terminée avec succès.")
