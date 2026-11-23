#!/usr/bin/env python3
"""ExchangeFlow: aplikasi lokal dengan akses berdasarkan peran."""
import hashlib
import hmac
import json
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'exchangeflow.db'
SESSIONS = {}
FIELDS = {
    'eps': ['name', 'contact', 'program', 'destination', 'pic', 'status', 'notes'],
    'opportunities': ['name', 'organization', 'country', 'program', 'deadline', 'status', 'link', 'notes'],
}
ROLES = ('VP', 'Team Leader', 'EP Manager')
EP_STATUSES = ('Open', 'Applied', 'Accepted', 'Approved', 'Realized', 'Finished', 'Completted')


class Database(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect():
    db = sqlite3.connect(DB_PATH, factory=Database)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def init_db():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        for table, fields in FIELDS.items():
            columns = ', '.join(f'"{field}" TEXT NOT NULL DEFAULT \'\'' for field in fields)
            db.execute(f'CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, {columns}, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, username TEXT NOT NULL UNIQUE COLLATE NOCASE, role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL)')
        if 'manager_id' not in [row['name'] for row in db.execute('PRAGMA table_info(eps)')]:
            db.execute('ALTER TABLE eps ADD COLUMN manager_id INTEGER REFERENCES users(id)')
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, manager_id INTEGER REFERENCES users(id), ep_id INTEGER REFERENCES eps(id) ON DELETE SET NULL, title TEXT NOT NULL, due_date TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Belum selesai', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        if 'manager_id' not in [row['name'] for row in db.execute('PRAGMA table_info(tasks)')]:
            db.execute("CREATE TABLE tasks_new (id INTEGER PRIMARY KEY AUTOINCREMENT, manager_id INTEGER REFERENCES users(id), ep_id INTEGER REFERENCES eps(id) ON DELETE SET NULL, title TEXT NOT NULL, due_date TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Belum selesai', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            db.execute('INSERT INTO tasks_new (id, manager_id, ep_id, title, due_date, status, updated_at) SELECT tasks.id, eps.manager_id, tasks.ep_id, tasks.title, tasks.due_date, tasks.status, tasks.updated_at FROM tasks LEFT JOIN eps ON eps.id = tasks.ep_id')
            db.execute('DROP TABLE tasks')
            db.execute('ALTER TABLE tasks_new RENAME TO tasks')


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 240000).hex()


def create_user(db, data, role):
    name, username, password = (str(data.get(k, '')).strip() for k in ('name', 'username', 'password'))
    if not name or not username or len(password) < 8 or role not in ROLES:
        raise ValueError('Isi nama, username, dan password minimal 8 karakter.')
    salt = secrets.token_hex(16)
    return db.execute('INSERT INTO users (name, username, role, salt, password_hash) VALUES (?, ?, ?, ?, ?)', (name, username, role, salt, password_hash(password, salt))).lastrowid


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def current_user(self):
        auth = self.headers.get('Authorization', '')
        user_id = SESSIONS.get(auth[7:]) if auth.startswith('Bearer ') else None
        if user_id is None:
            return None
        with connect() as db:
            row = db.execute('SELECT id, name, username, role FROM users WHERE id = ?', (user_id,)).fetchone()
        return dict(row) if row else None

    def read_data(self):
        if self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
            raise ValueError('Gunakan format JSON.')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 100000:
            raise ValueError('Data tidak valid.')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Data tidak valid.')
        return data

    def endpoint(self):
        parts = urlparse(self.path).path.strip('/').split('/')
        if len(parts) not in (2, 3) or parts[0] != 'api':
            return None, None
        if len(parts) == 3 and not parts[2].isdigit():
            return None, None
        return parts[1], int(parts[2]) if len(parts) == 3 else None

    def require_user(self):
        user = self.current_user()
        if not user:
            self.respond(401, {'error': 'Silakan masuk terlebih dahulu.'})
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html', '/style.css', '/script.js'):
            name = 'index.html' if path == '/' else path.lstrip('/')
            types = {'index.html': 'text/html; charset=utf-8', 'style.css': 'text/css; charset=utf-8', 'script.js': 'application/javascript; charset=utf-8'}
            self.respond(200, (ROOT / 'static' / name).read_bytes(), types[name]); return
        endpoint, item_id = self.endpoint()
        if endpoint == 'setup-status':
            with connect() as db:
                needed = not db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            self.respond(200, {'needed': needed}); return
        user = self.require_user()
        if not user: return
        if endpoint == 'me':
            self.respond(200, user); return
        with connect() as db:
            if endpoint == 'users' and item_id is None and user['role'] in ('VP', 'Team Leader'):
                rows = db.execute('SELECT id, name, username, role FROM users ORDER BY name').fetchall()
            elif endpoint == 'eps' and item_id is None:
                sql = 'SELECT eps.*, users.name AS manager_name FROM eps LEFT JOIN users ON users.id = eps.manager_id'
                rows = db.execute(sql + (' WHERE eps.manager_id = ?' if user['role'] == 'EP Manager' else '') + ' ORDER BY eps.id DESC', (user['id'],) if user['role'] == 'EP Manager' else ()).fetchall()
            elif endpoint == 'opportunities' and item_id is None:
                rows = db.execute('SELECT * FROM opportunities ORDER BY id DESC').fetchall()
            elif endpoint == 'tasks' and item_id is None:
                sql = 'SELECT tasks.*, users.name AS manager_name FROM tasks LEFT JOIN users ON users.id = tasks.manager_id'
                rows = db.execute(sql + (' WHERE tasks.manager_id = ?' if user['role'] == 'EP Manager' else '') + ' ORDER BY tasks.id DESC', (user['id'],) if user['role'] == 'EP Manager' else ()).fetchall()
            else:
                self.respond(403 if endpoint == 'users' else 404, {'error': 'Akses tidak tersedia.'}); return
        self.respond(200, [dict(row) for row in rows])

    def do_POST(self):
        endpoint, item_id = self.endpoint()
        try:
            data = self.read_data()
            if endpoint == 'setup':
                with connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                        self.respond(403, {'error': 'Akun awal sudah dibuat.'}); return
                    create_user(db, data, 'VP')
                self.respond(201, {'ok': True}); return
            if endpoint == 'login':
                with connect() as db:
                    row = db.execute('SELECT * FROM users WHERE username = ?', (str(data.get('username', '')).strip(),)).fetchone()
                if not row or not hmac.compare_digest(row['password_hash'], password_hash(str(data.get('password', '')).strip(), row['salt'])):
                    self.respond(401, {'error': 'Username atau password salah.'}); return
                token = secrets.token_urlsafe(32); SESSIONS[token] = row['id']
                self.respond(200, {'token': token}); return
            user = self.require_user()
            if not user: return
            if endpoint == 'logout':
                SESSIONS.pop(self.headers.get('Authorization', '')[7:], None)
                self.respond(200, {'ok': True}); return
            if endpoint == 'users':
                if user['role'] != 'VP': self.respond(403, {'error': 'Hanya VP dapat membuat akun.'}); return
                with connect() as db: new_id = create_user(db, data, data.get('role'))
                self.respond(201, {'id': new_id}); return
            self.save_record(endpoint, item_id, data, user, False)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.respond(400, {'error': str(exc) or 'Data tidak valid.'})
        except sqlite3.IntegrityError:
            self.respond(400, {'error': 'Username sudah digunakan atau data terkait tidak valid.'})

    def do_PUT(self):
        user = self.require_user()
        if not user: return
        try:
            self.save_record(*self.endpoint(), self.read_data(), user, True)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.respond(400, {'error': str(exc) or 'Data tidak valid.'})
        except sqlite3.IntegrityError:
            self.respond(400, {'error': 'Data terkait tidak valid.'})

    def save_record(self, endpoint, item_id, data, user, updating):
        if endpoint not in ('eps', 'opportunities', 'tasks') or updating != (item_id is not None):
            self.respond(404, {'error': 'Data tidak ditemukan.'}); return
        with connect() as db:
            existing = db.execute(f'SELECT * FROM {endpoint} WHERE id = ?', (item_id,)).fetchone() if updating else None
            if updating and not existing:
                self.respond(404, {'error': 'Data tidak ditemukan.'}); return
            if endpoint == 'tasks':
                assigned_id = data.get('manager_id') or (user['id'] if user['role'] == 'EP Manager' else None)
                assigned_id = int(assigned_id) if assigned_id is not None else None
                if user['role'] == 'EP Manager' and (assigned_id != user['id'] or (existing and existing['manager_id'] != user['id'])):
                    self.respond(403, {'error': 'Anda hanya dapat mengelola tugas sendiri.'}); return
                if assigned_id is not None and not db.execute("SELECT 1 FROM users WHERE id = ? AND role = 'EP Manager'", (assigned_id,)).fetchone():
                    raise ValueError('Pilih EP Manager yang valid.')
                if assigned_id is None and not (existing and existing['manager_id'] is None):
                    raise ValueError('Pilih EP Manager untuk tugas ini.')
                title = str(data.get('title', '')).strip()
                status = data.get('status', 'Belum selesai')
                if not title or status not in ('Belum selesai', 'Selesai'): raise ValueError('Isi judul dan status tugas yang valid.')
                fields = ['manager_id', 'title', 'due_date', 'status']
                values = [assigned_id, title, str(data.get('due_date', '')).strip(), status]
            else:
                if endpoint == 'opportunities' and user['role'] == 'EP Manager':
                    self.respond(403, {'error': 'Hanya VP atau Team Leader dapat mengubah peluang.'}); return
                if endpoint == 'eps' and user['role'] == 'EP Manager':
                    if not existing or existing['manager_id'] != user['id'] or ('manager_id' in data and data['manager_id'] != existing['manager_id']):
                        self.respond(403, {'error': 'Anda tidak dapat mengubah penugasan EP.'}); return
                fields = FIELDS[endpoint][:]
                values = [str(data.get(field, '')).strip() for field in fields]
                if not values[0] or data.get('program') not in ('Global Talent', 'Global Teacher'):
                    raise ValueError('Isi nama dan pilih program yang valid.')
                if endpoint == 'eps':
                    status = data.get('status') or (existing['status'] if existing else 'Open')
                    if status not in EP_STATUSES and not (existing and status == existing['status']):
                        raise ValueError('Pilih status EP yang valid.')
                    values[fields.index('status')] = status
                    manager_id = existing['manager_id'] if user['role'] == 'EP Manager' else data.get('manager_id') or None
                    if manager_id is not None:
                        manager_id = int(manager_id)
                        if not db.execute("SELECT 1 FROM users WHERE id = ? AND role = 'EP Manager'", (manager_id,)).fetchone(): raise ValueError('Pilih EP Manager yang valid.')
                    fields.append('manager_id'); values.append(manager_id)
            if updating:
                assignments = ', '.join(f'"{field}" = ?' for field in fields)
                db.execute(f'UPDATE {endpoint} SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', values + [item_id])
            else:
                columns = ', '.join(f'"{field}"' for field in fields)
                marks = ', '.join('?' for _ in fields)
                item_id = db.execute(f'INSERT INTO {endpoint} ({columns}) VALUES ({marks})', values).lastrowid
        self.respond(200 if updating else 201, {'id': item_id})

    def do_DELETE(self):
        user = self.require_user()
        if not user: return
        endpoint, item_id = self.endpoint()
        if endpoint not in ('eps', 'opportunities', 'tasks') or item_id is None:
            self.respond(404, {'error': 'Data tidak ditemukan.'}); return
        with connect() as db:
            if user['role'] == 'EP Manager':
                if endpoint != 'tasks' or not db.execute('SELECT 1 FROM tasks WHERE id = ? AND manager_id = ?', (item_id, user['id'])).fetchone():
                    self.respond(403, {'error': 'Anda tidak memiliki akses untuk menghapus data ini.'}); return
            result = db.execute(f'DELETE FROM {endpoint} WHERE id = ?', (item_id,))
        self.respond(200 if result.rowcount else 404, {'ok': bool(result.rowcount)})


def make_server(host='127.0.0.1', port=8000):
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == '__main__':
    init_db()
    server = make_server()
    print('ExchangeFlow berjalan di http://127.0.0.1:8000 (tekan Ctrl+C untuk berhenti)', flush=True)
    server.serve_forever()
