"""Invite-only email/password access; existing project owner IDs never change.

The operator provisions email -> owner mappings. Public requests cannot claim an
owner or create accounts. Recovery uses a configured TLS SMTP relay, never logs
links, and stores only hashes of short-lived single-use recovery credentials.
"""
from email.message import EmailMessage
import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
import time


class AuthUnavailable(Exception):
    pass


class Accounts:
    def __init__(self, control, origin, *, send=None, clock=time.time):
        self.control, self.origin, self.send, self.clock = control, origin, send, clock
        self.dummy = self.hash_password('fictional-dummy-password-not-an-account')
        with control.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS studio_accounts (email TEXT PRIMARY KEY, owner TEXT NOT NULL UNIQUE, password TEXT, version INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS studio_recovery (digest TEXT PRIMARY KEY, email TEXT NOT NULL, expires REAL NOT NULL)')
            db.execute('DELETE FROM studio_recovery WHERE expires < ?', (clock(),))

    @staticmethod
    def email(value):
        if not isinstance(value, str) or len(value) > 254:
            raise ValueError('Invalid email')
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Invalid email')
        return value

    @staticmethod
    def hash_password(password):
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise ValueError('Use 12 to 128 characters')
        salt = secrets.token_bytes(16)
        key = hashlib.scrypt(password.encode(), salt=salt, n=131072, r=8, p=1, dklen=32, maxmem=268435456)
        return salt.hex() + ':' + key.hex()

    @staticmethod
    def check(password, encoded):
        if not isinstance(password, str) or len(password) > 128:
            return False
        salt, expected = encoded.split(':')
        key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=131072, r=8, p=1, dklen=32, maxmem=268435456)
        return hmac.compare_digest(key.hex(), expected)

    def provision(self, email, owner):
        email = self.email(email)
        if not isinstance(owner, str) or not owner:
            raise ValueError('Owner required')
        with self.control.transaction() as db:
            row = db.execute('SELECT owner FROM studio_accounts WHERE email=?', (email,)).fetchone()
            if row and row[0] != owner:
                raise ValueError('Existing account must not be reassigned')
            db.execute('INSERT OR IGNORE INTO studio_accounts(email,owner) VALUES (?,?)', (email, owner))
            if not db.execute('SELECT 1 FROM studio_accounts WHERE email=? AND owner=?', (email,owner)).fetchone():
                raise ValueError('Existing owner has another email')

    def legacy_allowed(self, owner):
        with self.control.transaction() as db:
            return not db.execute('SELECT 1 FROM studio_accounts WHERE owner=? AND password IS NOT NULL', (owner,)).fetchone()

    def authenticate(self, email, password):
        try:
            email = self.email(email)
        except ValueError:
            email = ''
        with self.control.transaction() as db:
            row = db.execute('SELECT owner,password FROM studio_accounts WHERE email=?', (email,)).fetchone()
        valid = self.check(password, row[1] if row and row[1] else self.dummy)
        return row[0] if row and row[1] and valid else None

    def recovery(self, email):
        if self.send is None:
            raise AuthUnavailable()
        email = self.email(email)
        with self.control.transaction() as db:
            found = db.execute('SELECT 1 FROM studio_accounts WHERE email=?', (email,)).fetchone()
        if not found:
            return
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.control.transaction() as db:
            db.execute('DELETE FROM studio_recovery WHERE email=? OR expires < ?', (email, self.clock()))
            db.execute('INSERT INTO studio_recovery VALUES (?,?,?)', (digest,email,self.clock()+1800))
        try:
            self.send(email, self.origin + '/#director/reset/' + token)
        except Exception:
            with self.control.transaction() as db:
                db.execute('DELETE FROM studio_recovery WHERE digest=?', (digest,))
            raise AuthUnavailable() from None

    def reset(self, token, password):
        if not isinstance(token,str) or not 32 <= len(token) <= 128:
            raise ValueError('Invalid or expired link')
        hashed = self.hash_password(password)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.control.transaction() as db:
            row = db.execute('SELECT email FROM studio_recovery WHERE digest=? AND expires>?', (digest,self.clock())).fetchone()
            if not row:
                raise ValueError('Invalid or expired link')
            owner = db.execute('SELECT owner FROM studio_accounts WHERE email=?', row).fetchone()[0]
            db.execute('UPDATE studio_accounts SET password=?,version=version+1 WHERE email=?', (hashed,row[0]))
            db.execute('DELETE FROM studio_recovery WHERE email=?', row)
        return owner


def smtp_sender(env):
    required = ('WAN_SMTP_HOST','WAN_SMTP_USER','WAN_SMTP_PASSWORD','WAN_MAIL_FROM')
    if not all(env.get(k) for k in required):
        return None
    host, user, password, sender = (env[k] for k in required)
    port = int(env.get('WAN_SMTP_PORT','587'))
    if port not in (465,587):
        raise ValueError('Use a TLS mail relay')
    def send(recipient, link):
        message = EmailMessage()
        message['From'], message['To'] = sender, recipient
        message['Subject'] = 'Set your Music Video Studio password'
        message.set_content('Use this link to set or reset your Music Video Studio password.\n\n' + link + '\n\nThis link expires in 30 minutes and works once. If you did not request it, ignore this email.')
        context = ssl.create_default_context()
        connection = smtplib.SMTP_SSL(host,port,timeout=15,context=context) if port==465 else smtplib.SMTP(host,port,timeout=15)
        with connection as smtp:
            if port == 587:
                smtp.starttls(context=context)
            smtp.login(user,password)
            smtp.send_message(message)
    return send
