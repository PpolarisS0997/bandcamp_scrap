"""Module de connexion IMAP et récupération des emails Bandcamp."""

import imaplib
import email
from email.header import decode_header
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Représente un email parsé."""
    subject: str
    sender: str
    date: str
    body_html: str
    body_text: str
    uid: str


class EmailReader:
    """Gère la connexion IMAP et la récupération des emails."""

    def __init__(self, host, email_address, password, port=993, use_ssl=True):
        self.host = host
        self.email_address = email_address
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.connection = None

    def connect(self):
        if self.use_ssl:
            self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self.connection = imaplib.IMAP4(self.host, self.port)
        self.connection.login(self.email_address, self.password)

    def disconnect(self):
        if self.connection:
            try:
                self.connection.logout()
            except imaplib.IMAP4.error:
                pass

    def list_folders(self):
        """Liste les dossiers disponibles dans la boîte mail."""
        status, folders = self.connection.list()
        if status != "OK":
            return []
        result = []
        for folder in folders:
            decoded = folder.decode()
            # Extraire le nom du dossier (dernier élément entre guillemets ou après le délimiteur)
            parts = decoded.split(' "/" ')
            if len(parts) == 2:
                result.append(parts[1].strip('"'))
            else:
                parts = decoded.split(" ")
                result.append(parts[-1].strip('"'))
        return result

    def fetch_bandcamp_emails(self, folder="INBOX", limit=None):
        """Récupère tous les emails provenant de Bandcamp."""
        status, _ = self.connection.select(folder, readonly=True)
        if status != "OK":
            raise ConnectionError(f"Impossible d'ouvrir le dossier '{folder}'")

        # Chercher les emails provenant de bandcamp.com
        status, data = self.connection.search(None, '(FROM "bandcamp.com")')
        if status != "OK":
            return []

        email_ids = data[0].split()
        if not email_ids:
            return []

        # Limiter si demandé (prendre les plus récents)
        if limit:
            email_ids = email_ids[-limit:]

        messages = []
        total = len(email_ids)
        for i, eid in enumerate(email_ids, 1):
            if i % 20 == 0 or i == total:
                print(f"  Lecture email {i}/{total}...")

            status, msg_data = self.connection.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = self._decode_header(msg["Subject"])
            sender = self._decode_header(msg["From"])
            date_str = msg["Date"] or ""

            body_html, body_text = self._extract_body(msg)

            messages.append(EmailMessage(
                subject=subject,
                sender=sender,
                date=date_str,
                body_html=body_html,
                body_text=body_text,
                uid=eid.decode(),
            ))

        return messages

    def _extract_body(self, msg):
        """Extrait le corps HTML et texte d'un email."""
        body_html = ""
        body_text = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                # Ignorer les pièces jointes
                if part.get("Content-Disposition") and "attachment" in str(
                    part.get("Content-Disposition")
                ):
                    continue
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if content_type == "text/html":
                    body_html = decoded
                elif content_type == "text/plain":
                    body_text = decoded
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if content_type == "text/html":
                    body_html = decoded
                else:
                    body_text = decoded

        return body_html, body_text

    def _decode_header(self, header):
        """Décode un en-tête email potentiellement encodé."""
        if header is None:
            return ""
        decoded_parts = decode_header(header)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)
