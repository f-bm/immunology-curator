"""
Module d'intégration Notion unifié (Veille Immunologie + Bibliothèque IUIS 2024).

Pour chaque article sélectionné lors de la veille hebdomadaire :
  1. Crée une fiche structurée identique au format « Inbox Immunologie » :
     - Callout gris métadonnées (date, revue, IF, lien PubMed)
     - Callout bleu 🎯 Take-Home Messages (3 points clés actionnables)
     - 🧬 Contexte & Objectif
     - 🔬 Principales conclusions & Résultats clés
     - 💊 Implications en Pratique Clinique
     - 📎 PDF natif (si Open Access PMC disponible) ou 🔗 Lien direct PubMed/DOI
  2. Publie cette fiche à DEUX endroits :
     - Dans le dossier « Veille immunologie » (Section IUIS > Pathologie > 📄 Article)
     - Dans la bibliothèque « 🧬 Maladies IUIS 2024 » (fiche maladie exacte) ou le dossier thématique adapté
  3. Met automatiquement à jour le Statut de la maladie IUIS à « 📝 Notes disponibles »
     et rafraîchit l'index cliquable de la section IUIS (01 à 10) correspondante.
"""

from collections import defaultdict
from datetime import datetime
import io
import json
import math
import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

try:
    from notion_client import Client
except ImportError:
    Client = None

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "iuis_config.json")


def load_iuis_config() -> Dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def call_with_retry(fn, *args, max_retries: int = 5, **kwargs):
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ["rate_limited", "429", "500", "502", "503", "504", "timeout", "connection", "reset", "conflict"]):
                time.sleep((attempt + 1) * 2.5)
            elif attempt < max_retries - 1:
                time.sleep(1.5)
            else:
                raise e


def fetch_open_access_pdf(pmcid: str) -> Optional[bytes]:
    """Tente de télécharger le PDF Open Access depuis Europe PMC si un PMCID est présent."""
    if not pmcid:
        return None
    clean_pmc = pmcid.strip().upper()
    if not clean_pmc.startswith("PMC"):
        clean_pmc = f"PMC{clean_pmc}"
    url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={clean_pmc}&blobtype=pdf"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ImmunologyCurator/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            if data[:4] == b"%PDF" and len(data) > 10000:
                print(f"   📥 PDF Open Access récupéré ({len(data)//1024} Ko) pour {clean_pmc}")
                return data
    except Exception:
        pass
    return None


def upload_pdf_bytes(client: Client, clean_name: str, pdf_bytes: bytes) -> str:
    """Téléverse un PDF sur Notion via file_uploads (single ou multi_part)."""
    safe_base = re.sub(r"[^a-zA-Z0-9_-]+", "_", clean_name).strip("_")[:90] or "article"
    filename = safe_base + ".pdf"
    size = len(pdf_bytes)
    chunk_size = 10 * 1024 * 1024

    if size <= 19 * 1024 * 1024:
        fu = call_with_retry(
            client.file_uploads.create,
            mode="single_part",
            filename=filename,
            content_type="application/pdf",
        )
        fu_id = fu["id"]
        bio = io.BytesIO(pdf_bytes)
        bio.name = filename
        call_with_retry(client.file_uploads.send, fu_id, file=(filename, bio, "application/pdf"))
        return fu_id
    else:
        num_parts = math.ceil(size / chunk_size)
        fu = call_with_retry(
            client.file_uploads.create,
            mode="multi_part",
            filename=filename,
            content_type="application/pdf",
            number_of_parts=num_parts,
        )
        fu_id = fu["id"]
        for part_idx in range(num_parts):
            chunk = pdf_bytes[part_idx * chunk_size : (part_idx + 1) * chunk_size]
            bio = io.BytesIO(chunk)
            bio.name = filename
            call_with_retry(
                client.file_uploads.send,
                fu_id,
                file=(filename, bio, "application/pdf"),
                part_number=str(part_idx + 1),
            )
        call_with_retry(client.file_uploads.complete, fu_id)
        return fu_id


def build_article_blocks(article: Dict, fu_id: Optional[str] = None) -> List[Dict]:
    """
    Construit les blocs Notion au format exact de l'automatisation Inbox Immunologie.
    """
    date_str = datetime.now().strftime("%d/%m/%Y")
    journal = article.get("journal", "Revue scientifique")
    if_est = article.get("impact_factor_est", "")
    url = article.get("url", "")
    doi = article.get("doi", "")

    take_homes = article.get("take_home_messages") or []
    if not take_homes and article.get("take_home_message"):
        take_homes = [article["take_home_message"]]
    thm_text = "\n".join([f"• {m}" for m in take_homes]) if take_homes else "• Synthèse de l'article."

    context = article.get("context") or article.get("gene_pathway") or ""
    findings = article.get("key_findings") or []
    if not findings and article.get("main_conclusions"):
        findings = [article["main_conclusions"]]
    practice = article.get("clinical_practice") or article.get("clinical_impact") or ""

    journal_str = f"{journal} ({if_est})" if if_est else journal
    header_rt = [
        {"type": "text", "text": {"content": f"Veille hebdomadaire du {date_str} — Revue : "}, "annotations": {"bold": True}},
        {"type": "text", "text": {"content": journal_str}},
    ]
    if url and url.startswith("http"):
        header_rt.append({"type": "text", "text": {"content": "  |  "}})
        header_rt.append({"type": "text", "text": {"content": "Consulter sur PubMed ↗", "link": {"url": url}}})

    blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🗂️"},
                "color": "gray_background",
                "rich_text": header_rt,
            },
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🎯"},
                "color": "blue_background",
                "rich_text": [
                    {"type": "text", "text": {"content": "Take-Home Messages\n"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": thm_text[:1900]}},
                ],
            },
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "🧬 Contexte & Objectif"}}]},
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": context[:1950]}}]},
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "🔬 Principales conclusions & Résultats clés"}}]},
        },
    ]

    for f_item in findings[:5]:
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": str(f_item)[:1950]}}]},
        })

    blocks.extend([
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "💊 Implications en Pratique Clinique"}}]},
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": practice[:1950]}}]},
        },
        {"object": "block", "type": "divider", "divider": {}},
    ])

    if fu_id:
        blocks.extend([
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": "📎 Article complet (PDF Open Access)"}}]},
            },
            {
                "object": "block",
                "type": "pdf",
                "pdf": {"type": "file_upload", "file_upload": {"id": fu_id}},
            },
        ])
    else:
        source_rt = [{"type": "text", "text": {"content": f"Revue : {journal_str}"}}]
        if url and url.startswith("http"):
            source_rt.append({"type": "text", "text": {"content": "  —  "}})
            source_rt.append({"type": "text", "text": {"content": "Lien PubMed ↗", "link": {"url": url}}})
        if doi:
            doi_url = f"https://doi.org/{doi}"
            source_rt.append({"type": "text", "text": {"content": "  |  "}})
            source_rt.append({"type": "text", "text": {"content": f"DOI : {doi} ↗", "link": {"url": doi_url}}})
        blocks.extend([
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": "🔗 Source & Accès à l'article"}}]},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": source_rt},
            },
        ])

    return blocks


def _make_disease_bullet(r: Dict) -> Dict:
    has_notes = "Notes disponibles" in r.get("statut", "")
    rt = []
    if has_notes:
        rt.append({"type": "text", "text": {"content": "📝 "}})
    rt.append({"type": "mention", "mention": {"type": "page", "page": {"id": r["id"]}}})
    meta_parts = []
    if r.get("gene"):
        meta_parts.append(r["gene"])
    if r.get("inheritance") and r["inheritance"] != "Unknown":
        meta_parts.append(r["inheritance"])
    if r.get("type") == "Synthèse / Groupe":
        meta_parts.append("Synthèse")
    if meta_parts:
        rt.append({
            "type": "text",
            "text": {"content": "  —  " + " · ".join(meta_parts)},
            "annotations": {"color": "gray"},
        })
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt}}


def _subtable_sort_key(sub: str):
    if sub.startswith("Subtable "):
        parts = sub.split()
        num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 99
        return (0, num, sub.lower())
    if sub == "Polygenic / Multifactorial":
        return (1, 0, sub.lower())
    return (2, 0, sub.lower())


class NotionImmunoManager:
    def __init__(self, token: Optional[str] = None, root_page_id: Optional[str] = None):
        self.token = token or os.getenv("NOTION_API_KEY")
        self.root_page_id = (root_page_id or os.getenv("NOTION_ROOT_PAGE_ID", "")).replace("-", "")
        self.cfg = load_iuis_config()
        if not self.token or not self.root_page_id or not Client:
            if not Client:
                print("⚠️ Package 'notion-client' non installé (pip install notion-client).")
            else:
                print("⚠️ Configuration Notion manquante (NOTION_API_KEY ou NOTION_ROOT_PAGE_ID non définis).")
            self.client = None
        else:
            self.client = Client(auth=self.token)

    def query_live_iuis_rows(self) -> List[Dict]:
        """Interroge en direct la base Notion '🧬 Maladies IUIS 2024' (617 entrées)."""
        if not self.client or not self.cfg.get("iuis_ds_id"):
            return []

        rows = []
        cursor = None
        while True:
            params = {"data_source_id": self.cfg["iuis_ds_id"], "page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            res = call_with_retry(self.client.data_sources.query, **params)
            for r in res.get("results", []):
                props = r.get("properties", {})
                title = "".join(t.get("plain_text", "") for t in props.get("Disease", {}).get("title", []))
                gene = "".join(t.get("plain_text", "") for t in props.get("Gene", {}).get("rich_text", []))
                table = (props.get("Table IUIS", {}).get("select") or {}).get("name", "")
                subtable = (props.get("Subtable", {}).get("select") or {}).get("name", "") or "General"
                inh = (props.get("Inheritance", {}).get("select") or {}).get("name", "")
                rtype = (props.get("Type", {}).get("select") or {}).get("name", "")
                statut = (props.get("Statut", {}).get("select") or {}).get("name", "")
                rows.append({
                    "id": r["id"],
                    "title": title,
                    "table": table,
                    "subtable": subtable,
                    "gene": gene,
                    "inheritance": inh,
                    "type": rtype,
                    "statut": statut,
                })
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return rows

    def get_thematic_folders(self) -> Dict[str, str]:
        return self.cfg.get("thematic_folders", {})

    def find_child_page(self, parent_id: str, title: str) -> Optional[str]:
        """Cherche si une sous-page enfant avec ce titre existe déjà."""
        if not self.client or not parent_id:
            return None
        target = title.strip().lower()
        target_no_emoji = target.lstrip("📄📂 ").strip()
        cursor = None
        while True:
            params = {"block_id": parent_id, "page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            response = call_with_retry(self.client.blocks.children.list, **params)
            for block in response.get("results", []):
                if block.get("type") == "child_page":
                    pt = block.get("child_page", {}).get("title", "").strip().lower()
                    pt_no_emoji = pt.lstrip("📄📂 ").strip()
                    if pt == target or pt_no_emoji == target_no_emoji:
                        return block["id"]
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return None

    def find_or_create_child_page(self, parent_id: str, title: str, icon_emoji: str = "📁") -> str:
        """Recherche une page enfant par son titre. Si elle n'existe pas, la crée."""
        if not self.client:
            return ""
        existing = self.find_child_page(parent_id, title)
        if existing:
            return existing
        print(f"✨ Création de la page Notion : '{title}' (Parent: {parent_id[:8]}...)")
        new_page = call_with_retry(
            self.client.pages.create,
            parent={"page_id": parent_id},
            icon={"type": "emoji", "emoji": icon_emoji},
            properties={"title": [{"type": "text", "text": {"content": title}}]},
        )
        return new_page["id"]

    def create_article_page(self, parent_id: str, article: Dict, pdf_bytes: Optional[bytes] = None) -> Optional[str]:
        """
        Crée la sous-page dédiée '📄 <Titre>' avec le format exact Inbox Immunologie.
        Évite les doublons si l'article est déjà présent sous ce parent.
        """
        if not self.client or not parent_id:
            return None
        display_title = (article.get("title") or article.get("original_title") or "Article sans titre").strip()
        page_title = f"📄 {display_title}"[:2000]

        existing = self.find_child_page(parent_id, display_title)
        if existing:
            print(f"   ⏭️ Article déjà présent sous {parent_id[:8]}... ('{display_title[:60]}')")
            return existing

        fu_id = None
        if pdf_bytes:
            try:
                fu_id = upload_pdf_bytes(self.client, display_title, pdf_bytes)
            except Exception as e:
                print(f"   ⚠️ Upload PDF échoué ({e}), bascule vers lien PubMed.")

        blocks = build_article_blocks(article, fu_id=fu_id)
        new_page = call_with_retry(
            self.client.pages.create,
            parent={"page_id": parent_id},
            icon={"type": "emoji", "emoji": "📄"},
            properties={"title": [{"type": "text", "text": {"content": page_title}}]},
            children=blocks,
        )
        return new_page["id"]

    def refresh_section(self, table_name: str, rows: Optional[List[Dict]] = None):
        """Rafraîchit l'index cliquable d'une section IUIS (01 à 10) depuis la base live."""
        if not self.client:
            return
        page_id = self.cfg.get("section_pages", {}).get(table_name)
        if not page_id:
            print(f"⚠️ Section IUIS inconnue pour rafraîchissement : {table_name}")
            return
        if rows is None:
            rows = self.query_live_iuis_rows()

        table_rows = [r for r in rows if r["table"] == table_name]
        with_notes = sorted([r for r in table_rows if "Notes disponibles" in r["statut"]], key=lambda x: x["title"].lower())

        by_sub = defaultdict(list)
        for r in table_rows:
            by_sub[r["subtable"]].append(r)

        # Supprime les anciens blocs d'index (sans jamais toucher aux child_page)
        cursor = None
        old_blocks = []
        while True:
            params = {"block_id": page_id, "page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            res = call_with_retry(self.client.blocks.children.list, **params)
            for b in res.get("results", []):
                if b.get("type") != "child_page":
                    old_blocks.append(b["id"])
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")

        for bid in old_blocks:
            call_with_retry(self.client.blocks.delete, block_id=bid)
            time.sleep(0.15)

        blocks = [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🗂️"},
                    "color": "blue_background",
                    "rich_text": [
                        {"type": "text", "text": {"content": f"Index IUIS 2024 — {len(table_rows)} entrées"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": f" ({len(with_notes)} fiches avec notes/articles 📝, {len(by_sub)} sous-sections). Cliquez sur une maladie pour accéder directement à sa fiche et ses PDF."}},
                    ],
                },
            },
            {"object": "block", "type": "table_of_contents", "table_of_contents": {"color": "gray"}},
            {"object": "block", "type": "divider", "divider": {}},
        ]

        if with_notes:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": f"⭐ Accès rapide — Fiches avec notes & articles ({len(with_notes)})"}}]},
            })
            for r in with_notes:
                blocks.append(_make_disease_bullet(r))
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        for sub in sorted(by_sub.keys(), key=_subtable_sort_key):
            sub_rows = sorted(by_sub[sub], key=lambda x: x["title"].lower())
            sub_notes = sum(1 for r in sub_rows if "Notes disponibles" in r["statut"])
            sub_header = f"📂 {sub} ({len(sub_rows)}" + (f" · {sub_notes} 📝)" if sub_notes else ")")
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": sub_header}}]},
            })
            for r in sub_rows:
                blocks.append(_make_disease_bullet(r))

        for i in range(0, len(blocks), 90):
            call_with_retry(self.client.blocks.children.append, block_id=page_id, children=blocks[i : i + 90])
            time.sleep(0.3)

        print(f"🔄 Index IUIS rafraîchi : {table_name} ({len(table_rows)} entrées, {len(with_notes)} 📝)")

    def _resolve_iuis_destination(
        self, article: Dict, rows_by_id: Dict[str, Dict], folders_by_id: Dict[str, str]
    ) -> Tuple[Optional[str], str, str, str]:
        """
        Valide la destination IUIS renvoyée par le LLM contre les vrais IDs Notion.
        Retourne : (dest_id, dest_type, dest_name, table_name)
        """
        raw_id = (article.get("iuis_dest_id") or "").strip()
        if raw_id in rows_by_id:
            r = rows_by_id[raw_id]
            return r["id"], "iuis_row", r["title"], r["table"]
        if raw_id in folders_by_id:
            return raw_id, "thematic_folder", folders_by_id[raw_id], ""

        # Fallback défensif par correspondance sur le nom ou le gène si l'ID a été légèrement altéré
        dest_name = (article.get("iuis_dest_name") or article.get("disease_or_topic") or "").lower().strip()
        gene_str = (article.get("gene_pathway") or "").upper()
        for r in rows_by_id.values():
            if dest_name and dest_name in r["title"].lower():
                return r["id"], "iuis_row", r["title"], r["table"]
            if r["gene"] and len(r["gene"]) >= 3 and re.search(rf"\b{re.escape(r['gene'].upper())}\b", gene_str):
                return r["id"], "iuis_row", r["title"], r["table"]

        # Dernier recours : dossier thématique Immunologie fondamentale / Classifications IUIS
        fallback_folder = "Immunologie fondamentale — Classifications IUIS & Registres ESID"
        fallback_id = self.cfg.get("thematic_folders", {}).get(fallback_folder)
        return fallback_id, "thematic_folder", fallback_folder, ""

    def sync_all(self, classified_articles: List[Dict], iuis_rows: Optional[List[Dict]] = None):
        """
        Publie chaque article dans :
          1. Le dossier 'Veille immunologie' (Section > Pathologie > 📄 Fiche Inbox)
          2. La bibliothèque '🧬 Classification IUIS 2024' (Fiche maladie IUIS ou Dossier thématique)
        Met à jour le statut IUIS et rafraîchit les index de sections concernés.
        """
        if not self.client:
            print("⚠️ Synchro Notion ignorée (client non initialisé).")
            return

        if iuis_rows is None:
            iuis_rows = self.query_live_iuis_rows()

        rows_by_id = {r["id"]: r for r in iuis_rows}
        folders_by_id = {fid: fname for fname, fid in self.get_thematic_folders().items()}
        tables_to_refresh = set()

        print(f"📂 Synchronisation de {len(classified_articles)} articles (Veille immunologie + Classification IUIS 2024)...")

        for article in classified_articles:
            title = article.get("title") or article.get("original_title") or "Article"
            section_title = article.get("section", "Autres erreurs innées de l'immunité")
            disease_title = article.get("disease_or_topic", "Pathologies non classées")

            # Tentative de récupération du PDF Open Access si PMCID disponible
            pdf_bytes = fetch_open_access_pdf(article.get("pmcid", ""))

            # --- 1. Dossier 'Veille immunologie' ---
            section_id = self.find_or_create_child_page(self.root_page_id, section_title, icon_emoji="📂")
            disease_id = self.find_or_create_child_page(section_id, disease_title, icon_emoji="📄")
            self.create_article_page(disease_id, article, pdf_bytes=pdf_bytes)
            print(f"   ✅ [Veille immunologie] {section_title} ➔ {disease_title} ➔ 📄 {title[:65]}")

            # --- 2. Bibliothèque '🧬 Classification IUIS 2024' (ou Dossier thématique) ---
            dest_id, dest_type, dest_name, table_name = self._resolve_iuis_destination(
                article, rows_by_id, folders_by_id
            )
            if dest_id:
                self.create_article_page(dest_id, article, pdf_bytes=pdf_bytes)
                if dest_type == "iuis_row":
                    print(f"   ✅ [Classification IUIS] {table_name} ➔ {dest_name} ➔ 📄 {title[:65]}")
                    row_info = rows_by_id.get(dest_id, {})
                    if "Notes disponibles" not in row_info.get("statut", ""):
                        call_with_retry(
                            self.client.pages.update,
                            page_id=dest_id,
                            properties={"Statut": {"select": {"name": "📝 Notes disponibles"}}},
                        )
                        row_info["statut"] = "📝 Notes disponibles"
                        print(f"   🟢 Statut IUIS mis à jour -> '📝 Notes disponibles' ({dest_name})")
                        if table_name:
                            tables_to_refresh.add(table_name)
                else:
                    print(f"   ✅ [Dossier thématique IUIS] {dest_name} ➔ 📄 {title[:65]}")

        # Rafraîchissement des index cliquables des sections IUIS modifiées
        if tables_to_refresh:
            fresh_rows = self.query_live_iuis_rows()
            for tname in sorted(tables_to_refresh):
                self.refresh_section(tname, rows=fresh_rows)

        print("✅ Synchronisation Notion (Veille + Classification IUIS 2024) terminée avec succès.")
