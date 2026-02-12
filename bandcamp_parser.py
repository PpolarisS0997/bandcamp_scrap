"""Module d'analyse des emails Bandcamp pour détecter les nouvelles sorties."""

import re
from dataclasses import dataclass
from bs4 import BeautifulSoup

# Pattern pour les URLs Bandcamp (albums et tracks)
BANDCAMP_URL_PATTERN = re.compile(
    r'https?://[\w-]+\.bandcamp\.com/(?:album|track)/[\w-]+'
)

# Mots-clés indiquant une nouvelle sortie musicale
NEW_RELEASE_KEYWORDS = [
    # Anglais
    "new release",
    "new album",
    "new track",
    "new single",
    "new ep",
    "just released",
    "has released",
    "released a new",
    "new music from",
    "check out the new",
    "now available",
    "out now",
    "is out!",
    "just dropped",
    "new from",
    # Français
    "nouvelle sortie",
    "nouvel album",
    "nouveau single",
    "vient de sortir",
    "maintenant disponible",
]

# Sujets typiques des emails de nouvelles sorties Bandcamp
RELEASE_SUBJECT_PATTERNS = [
    re.compile(r"new\s+(album|track|single|ep|release)", re.IGNORECASE),
    re.compile(r"just\s+released", re.IGNORECASE),
    re.compile(r"has\s+released", re.IGNORECASE),
    re.compile(r"released\s+.+\s+on\s+bandcamp", re.IGNORECASE),
    re.compile(r"out\s+now", re.IGNORECASE),
    re.compile(r"is\s+out!", re.IGNORECASE),
]

# Patterns de sujets qu'on veut exclure (pas des nouvelles sorties)
EXCLUDE_SUBJECT_PATTERNS = [
    re.compile(r"receipt", re.IGNORECASE),
    re.compile(r"purchase", re.IGNORECASE),
    re.compile(r"order\s+(confirm|receipt)", re.IGNORECASE),
    re.compile(r"payment", re.IGNORECASE),
    re.compile(r"download\s+ready", re.IGNORECASE),
    re.compile(r"your\s+collection", re.IGNORECASE),
]


@dataclass
class BandcampRelease:
    """Représente une sortie musicale Bandcamp."""
    artist: str
    title: str
    url: str
    release_type: str  # "album" ou "track"
    email_date: str
    email_subject: str


def is_new_release_email(subject, body_text):
    """Détermine si un email annonce une nouvelle sortie musicale."""
    # Exclure les emails de type reçu d'achat, etc.
    for pattern in EXCLUDE_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return False

    combined = f"{subject} {body_text}".lower()

    # Vérifier les mots-clés
    for keyword in NEW_RELEASE_KEYWORDS:
        if keyword in combined:
            return True

    # Vérifier les patterns de sujet
    for pattern in RELEASE_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return True

    return False


def extract_releases(email_message):
    """Extrait les informations de sortie Bandcamp depuis un email."""
    releases = []
    html = email_message.body_html or email_message.body_text
    if not html:
        return releases

    soup = BeautifulSoup(html, "html.parser")

    # Collecter toutes les URLs Bandcamp uniques
    urls = set()

    # Depuis les liens <a href="...">
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = BANDCAMP_URL_PATTERN.search(href)
        if match:
            urls.add(match.group(0))

    # Depuis le texte brut du HTML (URLs parfois en clair)
    for match in BANDCAMP_URL_PATTERN.finditer(html):
        urls.add(match.group(0))

    # Essayer d'extraire artiste/titre enrichis depuis le contenu de l'email
    enriched_info = _extract_enriched_info(soup, email_message.subject)

    for url in urls:
        artist, title, release_type = _parse_bandcamp_url(url)

        # Enrichir avec les infos extraites de l'email si disponibles
        if enriched_info.get("artist"):
            artist = enriched_info["artist"]
        if enriched_info.get("title") and len(urls) == 1:
            title = enriched_info["title"]

        releases.append(BandcampRelease(
            artist=artist,
            title=title,
            url=url,
            release_type=release_type,
            email_date=email_message.date,
            email_subject=email_message.subject,
        ))

    return releases


def _parse_bandcamp_url(url):
    """Extrait artiste, titre et type depuis une URL Bandcamp."""
    match = re.match(
        r'https?://([\w-]+)\.bandcamp\.com/(album|track)/([\w-]+)', url
    )
    if match:
        artist = match.group(1).replace("-", " ").title()
        release_type = match.group(2)
        title = match.group(3).replace("-", " ").title()
        return artist, title, release_type
    return "Inconnu", "Inconnu", "track"


def _extract_enriched_info(soup, subject):
    """Tente d'extraire artiste et titre depuis le contenu structuré de l'email."""
    info = {"artist": None, "title": None}

    # Bandcamp utilise souvent des patterns dans le sujet :
    # "ArtistName just released AlbumName"
    # "New release from ArtistName"
    subject_patterns = [
        re.compile(r"^(.+?)\s+(?:just\s+released|has\s+released)\s+(.+)", re.IGNORECASE),
        re.compile(r"new\s+(?:release|album|track|single)\s+from\s+(.+)", re.IGNORECASE),
    ]

    for pattern in subject_patterns:
        match = pattern.search(subject)
        if match:
            groups = match.groups()
            if len(groups) >= 1:
                info["artist"] = groups[0].strip()
            if len(groups) >= 2:
                info["title"] = groups[1].strip()
            break

    # Chercher dans les éléments HTML structurés
    # Bandcamp met souvent l'artiste en gras ou dans un <h2>
    for tag in soup.find_all(["h1", "h2", "h3", "strong", "b"]):
        text = tag.get_text(strip=True)
        if text and not info["artist"] and 3 < len(text) < 60:
            # Vérifier que c'est probablement un nom d'artiste
            if not any(kw in text.lower() for kw in ["bandcamp", "click", "view", "http"]):
                info["artist"] = text
                break

    return info
