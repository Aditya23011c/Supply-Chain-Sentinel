"""Auth core (stdlib only): PBKDF2 password hashing, HMAC-signed expiring tokens, tiny JSON user store."""
import base64, hashlib, hmac, json, os, re, secrets, threading, time

USERS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")
SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me").encode()
TOKEN_TTL = 7 * 24 * 3600
_lock = threading.Lock()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _load():
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 150_000).hex()


def public(user):
    return {"name": user["name"], "email": user["email"]}


def create_user(name, email, password):
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    with _lock:
        users = _load()
        if email in users:
            raise ValueError("An account with this email already exists")
        salt = secrets.token_bytes(16)
        users[email] = {"name": (name or email.split("@")[0]).strip()[:60], "email": email,
                        "salt": salt.hex(), "hash": _hash(password, salt), "created": int(time.time())}
        _save(users)
        return users[email]


def authenticate(email, password):
    user = _load().get(email.strip().lower())
    if not user:
        _hash(password, b"0" * 16)  # keep timing similar for unknown emails
        return None
    ok = hmac.compare_digest(user["hash"], _hash(password, bytes.fromhex(user["salt"])))
    return user if ok else None


def get_user(email):
    return _load().get((email or "").strip().lower())


def make_token(email):
    body = base64.urlsafe_b64encode(json.dumps({"e": email, "x": int(time.time()) + TOKEN_TTL}).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token):
    try:
        body, sig = token.split(".")
        expected = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return data["e"] if data["x"] > time.time() else None
    except Exception:
        return None
