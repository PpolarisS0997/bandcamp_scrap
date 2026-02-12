#!/usr/bin/env python3
"""
Bandcamp Email Scraper - Point d'entrée principal.

Scrape une boîte mail pour identifier les emails Bandcamp annonçant
de nouvelles sorties musicales et génère une playlist HTML interactive.

Usage:
    python bandcamp_scraper.py
    python bandcamp_scraper.py --limit 50 --output ma_playlist.html
    python bandcamp_scraper.py --no-embed --folder "INBOX"
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from email_reader import EmailReader
from bandcamp_parser import is_new_release_email, extract_releases
from playlist_generator import generate_playlist_html


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Scrape les emails Bandcamp et génère une playlist HTML."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("IMAP_HOST", "imap.gmail.com"),
        help="Serveur IMAP (défaut: imap.gmail.com)",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("EMAIL_ADDRESS"),
        help="Adresse email (ou variable EMAIL_ADDRESS dans .env)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("EMAIL_PASSWORD"),
        help="Mot de passe / App Password (ou variable EMAIL_PASSWORD dans .env)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("IMAP_PORT", "993")),
        help="Port IMAP (défaut: 993)",
    )
    parser.add_argument(
        "--folder",
        default=os.getenv("IMAP_FOLDER", "INBOX"),
        help="Dossier mail à scanner (défaut: INBOX)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre max d'emails à traiter (les plus récents)",
    )
    parser.add_argument(
        "--output",
        default="playlist.html",
        help="Chemin du fichier HTML de sortie (défaut: playlist.html)",
    )
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Ne pas récupérer les lecteurs intégrés (plus rapide)",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Exporter aussi les données en JSON vers ce fichier",
    )
    parser.add_argument(
        "--list-folders",
        action="store_true",
        help="Lister les dossiers disponibles et quitter",
    )
    parser.add_argument(
        "--no-ssl",
        action="store_true",
        help="Désactiver SSL (non recommandé)",
    )

    args = parser.parse_args()

    if not args.email or not args.password:
        print("Erreur : adresse email et mot de passe requis.")
        print()
        print("Options :")
        print("  1. Créez un fichier .env (voir .env.example)")
        print("  2. Passez --email et --password en arguments")
        print()
        print("Pour Gmail, utilisez un 'App Password' :")
        print("  https://myaccount.google.com/apppasswords")
        sys.exit(1)

    # Connexion
    print(f"Connexion à {args.host}:{args.port}...")
    reader = EmailReader(
        host=args.host,
        email_address=args.email,
        password=args.password,
        port=args.port,
        use_ssl=not args.no_ssl,
    )

    try:
        reader.connect()
        print("Connecté.")
    except Exception as e:
        print(f"Erreur de connexion : {e}")
        sys.exit(1)

    try:
        # Lister les dossiers si demandé
        if args.list_folders:
            print("\nDossiers disponibles :")
            for folder in reader.list_folders():
                print(f"  - {folder}")
            return

        # Récupérer les emails Bandcamp
        print(f"\nRecherche des emails Bandcamp dans '{args.folder}'...")
        emails = reader.fetch_bandcamp_emails(folder=args.folder, limit=args.limit)
        print(f"  {len(emails)} emails Bandcamp trouvés.")

        if not emails:
            print("\nAucun email Bandcamp trouvé. Vérifiez le dossier ou les filtres.")
            return

        # Filtrer les nouvelles sorties
        print("\nAnalyse des emails pour les nouvelles sorties...")
        all_releases = []
        release_email_count = 0

        for msg in emails:
            if is_new_release_email(msg.subject, msg.body_text):
                release_email_count += 1
                releases = extract_releases(msg)
                all_releases.extend(releases)

        print(f"  {release_email_count} emails de nouvelles sorties identifiés.")
        print(f"  {len(all_releases)} releases extraites.")

        if not all_releases:
            print("\nAucune nouvelle sortie détectée dans les emails.")
            print("Conseil : essayez d'augmenter --limit ou vérifiez un autre --folder.")
            return

        # Export JSON optionnel
        if args.export_json:
            data = [
                {
                    "artist": r.artist,
                    "title": r.title,
                    "url": r.url,
                    "type": r.release_type,
                    "email_date": r.email_date,
                    "email_subject": r.email_subject,
                }
                for r in all_releases
            ]
            with open(args.export_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\nDonnées JSON exportées : {args.export_json}")

        # Générer la playlist HTML
        print("\nGénération de la playlist HTML...")
        path, count = generate_playlist_html(
            all_releases,
            output_path=args.output,
            fetch_embeds=not args.no_embed,
        )
        print(f"\nPlaylist générée : {path}")
        print(f"  {count} sorties uniques dans la playlist.")
        print(f"\nOuvrez le fichier dans un navigateur pour écouter :")
        print(f"  file://{os.path.abspath(path)}")

    finally:
        reader.disconnect()
        print("\nDéconnexion. Terminé.")


if __name__ == "__main__":
    main()
