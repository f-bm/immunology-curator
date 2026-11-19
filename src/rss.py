"""
Module de gestion du flux Podcast RSS (compatible Apple Podcasts, Pocket Casts, Overcast, etc.).
Met à jour le fichier feed.xml à chaque nouvel épisode hebdomadaire.
"""

from datetime import datetime, timezone
import os
from typing import Optional
import xml.etree.ElementTree as ET

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)


def update_or_create_podcast_feed(
    feed_path: str,
    episode_title: str,
    episode_description: str,
    audio_url: str,
    audio_file_path: str,
    podcast_title: str = "Veille Hebdomadaire : Immunologie Clinique & DIP",
    podcast_description: str = "Revue hebdomadaire de la littérature scientifique en immunologie clinique, déficits immunitaires primitifs (IEI) et maladies auto-inflammatoires.",
    podcast_author: str = "Dr. Veille Immunologie",
    podcast_cover_url: Optional[str] = None
) -> str:
    """
    Crée ou enrichit un flux RSS 2.0 avec l'extension iTunes/Podcast.
    """
    file_size = os.path.getsize(audio_file_path) if os.path.exists(audio_file_path) else 10000000
    pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    # Si le fichier existe et est corrompu ou illisible, on repart d'une base propre
    tree = None
    if os.path.exists(feed_path):
        try:
            tree = ET.parse(feed_path)
            rss = tree.getroot()
            channel = rss.find("channel")
        except Exception:
            tree = None

    if tree is None or channel is None:
        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = podcast_title
        ET.SubElement(channel, "link").text = audio_url.rsplit("/", 1)[0]
        ET.SubElement(channel, "description").text = podcast_description
        ET.SubElement(channel, "language").text = "fr"
        ET.SubElement(channel, f"{{{ITUNES_NS}}}author").text = podcast_author
        ET.SubElement(channel, f"{{{ITUNES_NS}}}summary").text = podcast_description
        
        category = ET.SubElement(channel, f"{{{ITUNES_NS}}}category", attrib={"text": "Science"})
        ET.SubElement(category, f"{{{ITUNES_NS}}}category", attrib={"text": "Medicine"})

        if podcast_cover_url:
            ET.SubElement(channel, f"{{{ITUNES_NS}}}image", attrib={"href": podcast_cover_url})

    # Création du nouvel épisode (<item>)
    item = ET.Element("item")
    ET.SubElement(item, "title").text = episode_title
    ET.SubElement(item, "description").text = episode_description
    ET.SubElement(item, "pubDate").text = pub_date
    ET.SubElement(item, "guid").text = audio_url
    
    ET.SubElement(item, "enclosure", attrib={
        "url": audio_url,
        "length": str(file_size),
        "type": "audio/mpeg"
    })

    ET.SubElement(item, f"{{{ITUNES_NS}}}title").text = episode_title
    ET.SubElement(item, f"{{{ITUNES_NS}}}summary").text = episode_description[:400]

    # Insérer le nouvel épisode au début du channel
    first_item_index = None
    for idx, child in enumerate(list(channel)):
        if child.tag == "item":
            first_item_index = idx
            break

    if first_item_index is not None:
        channel.insert(first_item_index, item)
    else:
        channel.append(item)

    # Sauvegarde indentée
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    tree.write(feed_path, encoding="utf-8", xml_declaration=True)
    print(f"📡 Flux RSS mis à jour dans : {feed_path}")
    return feed_path
