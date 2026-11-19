"""
Module de synthèse vocale (Text-To-Speech) pour la génération de l'épisode de podcast.
Utilise par défaut 'edge-tts' (Microsoft Neural Voices, 100% gratuit et haute fidélité).
"""

import asyncio
import os
import sys


async def _generate_edge_tts(text: str, output_path: str, voice: str = "fr-FR-HenriNeural"):
    import edge_tts
    # Nettoyage sommaire du texte (retrait des symboles markdown gênants pour la voix)
    clean_text = text.replace("**", "").replace("##", "").replace("`", "")
    
    communicate = edge_tts.Communicate(clean_text, voice=voice, rate="+3%")
    await communicate.save(output_path)


def generate_podcast_audio(script_text: str, output_path: str = "episode.mp3", voice: str = "fr-FR-HenriNeural") -> str:
    """
    Transforme le script texte en fichier audio MP3 de qualité podcast.
    """
    print(f"🎙️ Génération de l'audio podcast ({len(script_text.split())} mots) avec la voix {voice}...")
    try:
        asyncio.run(_generate_edge_tts(script_text, output_path, voice=voice))
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Audio généré avec succès : {output_path} ({size_mb:.2f} Mo)")
        return output_path
    except ImportError:
        print("⚠️ Module 'edge-tts' non présent dans cet environnement Python.")
        print("💡 Créez un fichier audio factice pour valider le pipeline RSS...")
        # Création d'un fichier audio minimaliste valide pour les tests
        with open(output_path, "wb") as f:
            f.write(b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x03Lavf58.29.100\x00")
        print(f"✅ Fichier factice généré pour le test : {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Erreur lors de la génération TTS : {e}")
        raise
