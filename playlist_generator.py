"""Module de génération de playlist HTML avec lecteurs Bandcamp intégrés."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime


def fetch_embed_info(url):
    """Récupère l'URL d'intégration du lecteur Bandcamp depuis une page."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BandcampPlaylistGen/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Méthode 1 : méta tag og:video (contient l'URL du lecteur intégré)
        og_video = soup.find("meta", property="og:video")
        if og_video and og_video.get("content"):
            embed_url = og_video["content"]
            # Ajouter nos préférences de style
            if "?" not in embed_url:
                embed_url += "/"
            return embed_url

        # Méthode 2 : chercher l'ID dans les données de la page
        for script in soup.find_all("script"):
            text = script.string or ""
            # Chercher le pattern data-tralbum avec l'ID
            match = re.search(r'"id"\s*:\s*(\d+)', text)
            if match:
                item_id = match.group(1)
                kind = "album" if "/album/" in url else "track"
                return (
                    f"https://bandcamp.com/EmbeddedPlayer/"
                    f"{kind}={item_id}/size=large/bgcol=1a1a2e/"
                    f"linkcol=e99708/tracklist=true/artwork=small/transparent=true/"
                )

        # Méthode 3 : attribut data-tralbum-id
        for attr_name in ["data-tralbum-id", "data-id"]:
            el = soup.find(attrs={attr_name: True})
            if el:
                item_id = el[attr_name]
                kind = "album" if "/album/" in url else "track"
                return (
                    f"https://bandcamp.com/EmbeddedPlayer/"
                    f"{kind}={item_id}/size=large/bgcol=1a1a2e/"
                    f"linkcol=e99708/tracklist=true/artwork=small/transparent=true/"
                )

        # Méthode 4 : chercher l'artwork/cover pour au moins valider la page
        og_image = soup.find("meta", property="og:image")
        og_title = soup.find("meta", property="og:title")
        if og_title:
            # La page existe mais on n'a pas trouvé l'embed, fallback
            return None

    except requests.RequestException:
        pass

    return None


def generate_playlist_html(releases, output_path="playlist.html", fetch_embeds=True):
    """Génère une playlist HTML depuis une liste de BandcampRelease."""

    # Dédupliquer par URL
    seen = set()
    unique_releases = []
    for r in releases:
        if r.url not in seen:
            seen.add(r.url)
            unique_releases.append(r)

    # Trier par date (plus récents en premier)
    unique_releases.sort(key=lambda r: r.email_date or "", reverse=True)

    # Récupérer les URLs d'intégration
    embeds = {}
    if fetch_embeds:
        total = len(unique_releases)
        for i, r in enumerate(unique_releases, 1):
            print(f"  Récupération embed {i}/{total}: {r.artist} - {r.title}...")
            embed_url = fetch_embed_info(r.url)
            if embed_url:
                embeds[r.url] = embed_url

    # Statistiques
    album_count = len([r for r in unique_releases if r.release_type == "album"])
    track_count = len([r for r in unique_releases if r.release_type == "track"])

    # Construire les cartes de release
    items_html = ""
    for idx, r in enumerate(unique_releases):
        embed = embeds.get(r.url)
        if embed:
            player = (
                f'<iframe style="border:0; width:100%; height:142px;" '
                f'src="{_escape_html(embed)}" seamless loading="lazy"></iframe>'
            )
        else:
            player = (
                f'<a href="{_escape_html(r.url)}" target="_blank" '
                f'rel="noopener" class="fallback-link">'
                f'Écouter sur Bandcamp</a>'
            )

        items_html += f"""
        <div class="release" data-index="{idx}"
             data-artist="{_escape_html(r.artist.lower())}"
             data-title="{_escape_html(r.title.lower())}"
             data-type="{r.release_type}">
            <div class="release-info">
                <span class="artist">{_escape_html(r.artist)}</span>
                <span class="separator">—</span>
                <span class="title">{_escape_html(r.title)}</span>
                <span class="type">{r.release_type}</span>
                <span class="date">{_escape_html(r.email_date or 'N/A')}</span>
            </div>
            <div class="player">{player}</div>
        </div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bandcamp - Nouvelles Sorties</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            min-height: 100vh;
        }}
        header {{
            background: #16213e;
            padding: 2rem;
            text-align: center;
            border-bottom: 3px solid #e99708;
        }}
        header h1 {{
            color: #e99708;
            font-size: 1.8rem;
            letter-spacing: 0.5px;
        }}
        header p {{
            color: #888;
            margin-top: 0.5rem;
            font-size: 0.85rem;
        }}
        .toolbar {{
            background: #0f3460;
            padding: 0.8rem 1.5rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 1rem;
            justify-content: center;
        }}
        .toolbar input {{
            padding: 0.5rem 1rem;
            border: 1px solid #233554;
            border-radius: 6px;
            background: #1a1a2e;
            color: #e0e0e0;
            font-size: 0.9rem;
            width: 280px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .toolbar input:focus {{
            border-color: #e99708;
        }}
        .toolbar input::placeholder {{
            color: #555;
        }}
        .filter-btn {{
            padding: 0.4rem 0.9rem;
            border: 1px solid #233554;
            border-radius: 4px;
            background: transparent;
            color: #aaa;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.2s;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: #e99708;
            color: #1a1a2e;
            border-color: #e99708;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            padding: 0.8rem;
            background: #12274a;
            font-size: 0.85rem;
        }}
        .stats strong {{ color: #e99708; }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 1.5rem;
        }}
        .release {{
            background: #16213e;
            border-radius: 8px;
            margin-bottom: 1rem;
            overflow: hidden;
            border: 1px solid #233554;
            transition: border-color 0.3s, transform 0.2s;
        }}
        .release:hover {{
            border-color: #e99708;
            transform: translateY(-1px);
        }}
        .release.hidden {{
            display: none;
        }}
        .release-info {{
            padding: 1rem 1.2rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.5rem;
        }}
        .artist {{
            font-weight: 700;
            color: #e99708;
            font-size: 1.05rem;
        }}
        .separator {{
            color: #444;
        }}
        .title {{
            color: #ccc;
            font-size: 1rem;
        }}
        .type {{
            background: #0f3460;
            padding: 2px 10px;
            border-radius: 4px;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #88a4cc;
        }}
        .date {{
            margin-left: auto;
            color: #555;
            font-size: 0.78rem;
        }}
        .player {{
            padding: 0 1rem 1rem;
        }}
        .fallback-link {{
            display: inline-block;
            color: #e99708;
            text-decoration: none;
            padding: 0.5rem 1.2rem;
            border: 1px solid #e99708;
            border-radius: 6px;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}
        .fallback-link:hover {{
            background: #e99708;
            color: #1a1a2e;
        }}
        .empty {{
            text-align: center;
            padding: 3rem;
            color: #555;
            font-size: 1.1rem;
        }}
        .no-results {{
            text-align: center;
            padding: 2rem;
            color: #555;
            display: none;
        }}
        @media (max-width: 600px) {{
            .toolbar {{ flex-direction: column; align-items: stretch; }}
            .toolbar input {{ width: 100%; }}
            .release-info {{ flex-direction: column; align-items: flex-start; }}
            .date {{ margin-left: 0; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>Bandcamp Nouvelles Sorties</h1>
        <p>Playlist auto-g&eacute;n&eacute;r&eacute;e le {now}</p>
    </header>
    <div class="toolbar">
        <input type="text" id="search" placeholder="Rechercher artiste ou titre..."
               autocomplete="off" />
        <button class="filter-btn active" data-filter="all">Tout</button>
        <button class="filter-btn" data-filter="album">Albums</button>
        <button class="filter-btn" data-filter="track">Tracks</button>
    </div>
    <div class="stats">
        <span><strong>{len(unique_releases)}</strong> sorties</span>
        <span><strong>{album_count}</strong> albums</span>
        <span><strong>{track_count}</strong> tracks</span>
    </div>
    <div class="container" id="releases">
        {items_html if items_html else '<div class="empty">Aucune nouvelle sortie trouv&eacute;e.</div>'}
        <div class="no-results" id="no-results">Aucun r&eacute;sultat pour cette recherche.</div>
    </div>

    <script>
    (function() {{
        const searchInput = document.getElementById('search');
        const releases = document.querySelectorAll('.release');
        const filterBtns = document.querySelectorAll('.filter-btn');
        const noResults = document.getElementById('no-results');
        let activeFilter = 'all';

        function applyFilters() {{
            const query = searchInput.value.toLowerCase().trim();
            let visible = 0;

            releases.forEach(function(el) {{
                const artist = el.dataset.artist || '';
                const title = el.dataset.title || '';
                const type = el.dataset.type || '';

                const matchesSearch = !query
                    || artist.includes(query)
                    || title.includes(query);
                const matchesFilter = activeFilter === 'all'
                    || type === activeFilter;

                if (matchesSearch && matchesFilter) {{
                    el.classList.remove('hidden');
                    visible++;
                }} else {{
                    el.classList.add('hidden');
                }}
            }});

            noResults.style.display = visible === 0 && releases.length > 0
                ? 'block' : 'none';
        }}

        searchInput.addEventListener('input', applyFilters);

        filterBtns.forEach(function(btn) {{
            btn.addEventListener('click', function() {{
                filterBtns.forEach(function(b) {{ b.classList.remove('active'); }});
                btn.classList.add('active');
                activeFilter = btn.dataset.filter;
                applyFilters();
            }});
        }});
    }})();
    </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path, len(unique_releases)


def _escape_html(text):
    """Échappe les caractères spéciaux HTML."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
