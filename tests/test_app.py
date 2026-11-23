import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import app


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        app.DB_PATH = Path(self.temp.name) / 'test.db'
        app.init_db()
        self.request('setup', 'POST', {'name': 'VP', 'username': 'vp', 'password': 'password123'})
        _, result = self.request('login', 'POST', {'username': 'vp', 'password': 'password123'})
        self.vp = result['token']
        self.tl = self.create_user('leader', 'Team Leader')
        self.manager = self.create_user('manager', 'EP Manager')
        self.other = self.create_user('other', 'EP Manager')

    def tearDown(self):
        self.temp.cleanup()

    def request(self, path, method='GET', data=None, token=None):
        body = json.dumps(data).encode() if data is not None else b''
        handler = object.__new__(app.Handler)
        handler.path = '/api/' + path
        handler.headers = {'Content-Length': str(len(body)), 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token if token else ''}
        handler.rfile = io.BytesIO(body)
        result = {}
        handler.respond = lambda status, payload, content_type='application/json; charset=utf-8': result.update(status=status, data=payload)
        getattr(handler, 'do_' + method)()
        return result['status'], result['data']

    def create_user(self, username, role):
        status, result = self.request('users', 'POST', {'name': username, 'username': username, 'password': 'password123', 'role': role}, self.vp)
        self.assertEqual(status, 201)
        return result['id']

    def login(self, username):
        return self.request('login', 'POST', {'username': username, 'password': 'password123'})[1]['token']

    def test_authentication_and_setup_cannot_repeat(self):
        self.assertEqual(self.request('eps')[0], 401)
        self.assertEqual(self.request('login', 'POST', {'username': 'vp', 'password': 'wrong'})[0], 401)
        self.assertEqual(self.request('setup', 'POST', {'name': 'x', 'username': 'x', 'password': 'password123'})[0], 403)

    def test_assigned_manager_only_sees_own_ep_and_cannot_reassign(self):
        tl_token = self.login('leader')
        manager_token = self.login('manager')
        _, ep = self.request('eps', 'POST', {'name': 'Dina', 'program': 'Global Talent', 'manager_id': self.manager}, tl_token)
        self.request('eps', 'POST', {'name': 'Lina', 'program': 'Global Teacher', 'manager_id': self.other}, tl_token)
        self.assertEqual([x['name'] for x in self.request('eps', token=manager_token)[1]], ['Dina'])
        self.assertEqual(self.request('eps/' + str(ep['id']), 'PUT', {'name': 'Dina', 'program': 'Global Talent', 'manager_id': self.other}, manager_token)[0], 403)
        self.assertEqual(self.request('users', 'POST', {'name': 'x', 'username': 'x', 'password': 'password123', 'role': 'VP'}, tl_token)[0], 403)

    def test_tasks_belong_to_ep_manager_without_a_participant(self):
        tl = self.login('leader'); manager = self.login('manager'); other = self.login('other')
        code, task = self.request('tasks', 'POST', {'manager_id': self.manager, 'title': 'Rapat tim', 'due_date': '2026-11-24'}, tl)
        self.assertEqual(code, 201)
        self.assertEqual(self.request('tasks', token=manager)[1][0]['title'], 'Rapat tim')
        self.assertEqual(self.request('tasks', token=other)[1], [])
        self.assertEqual(self.request('tasks/' + str(task['id']), 'PUT', {'manager_id': self.other, 'title': 'Diambil'}, other)[0], 403)
        self.assertEqual(self.request('tasks', 'POST', {'title': 'Susun laporan'}, manager)[0], 201)
        self.assertEqual(self.request('tasks', 'POST', {'manager_id': self.other, 'title': 'Tugas orang lain'}, manager)[0], 403)

    def test_manager_cannot_access_or_modify_other_records_or_admin_actions(self):
        tl = self.login('leader'); manager = self.login('manager')
        _, ep = self.request('eps', 'POST', {'name': 'Lina', 'program': 'Global Teacher', 'manager_id': self.other}, tl)
        self.assertEqual(self.request('eps/' + str(ep['id']), 'PUT', {'name': 'Diubah', 'program': 'Global Teacher'}, manager)[0], 403)
        self.assertEqual(self.request('eps/' + str(ep['id']), 'DELETE', token=manager)[0], 403)
        self.assertEqual(self.request('opportunities', 'POST', {'name': 'Job', 'program': 'Global Talent'}, manager)[0], 403)
        self.assertEqual(self.request('users', token=manager)[0], 403)
        self.assertEqual(self.request('tasks', 'POST', {'title': 'Task', 'manager_id': self.other}, manager)[0], 403)

    def test_changing_ep_assignment_does_not_transfer_manager_tasks(self):
        tl = self.login('leader'); first = self.login('manager'); second = self.login('other')
        _, ep = self.request('eps', 'POST', {'name': 'Dina', 'program': 'Global Talent', 'manager_id': self.manager}, tl)
        self.request('tasks', 'POST', {'title': 'Rapat tim'}, first)
        self.request('eps/' + str(ep['id']), 'PUT', {'name': 'Dina', 'program': 'Global Talent', 'manager_id': self.other}, tl)
        self.assertEqual(len(self.request('tasks', token=first)[1]), 1)
        self.assertEqual(self.request('tasks', token=second)[1], [])

    def test_ep_status_options_and_legacy_status(self):
        for status in ('Open', 'Applied', 'Accepted', 'Approved', 'Realized', 'Finished', 'Completted'):
            self.assertEqual(self.request('eps', 'POST', {'name': 'EP', 'program': 'Global Talent', 'status': status}, self.vp)[0], 201)
        self.assertEqual(self.request('eps', 'POST', {'name': 'EP', 'program': 'Global Talent', 'status': 'Tidak valid'}, self.vp)[0], 400)
        with app.connect() as db:
            db.execute("INSERT INTO eps (name, program, status) VALUES ('Lama', 'Global Talent', 'Baru')")
            ep_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        self.assertEqual(self.request('eps/' + str(ep_id), 'PUT', {'name': 'Lama', 'program': 'Global Talent', 'status': 'Baru'}, self.vp)[0], 200)

    def test_old_tasks_migrate_to_current_manager_and_survive_ep_removal(self):
        with app.connect() as db:
            db.execute('DROP TABLE tasks')
            db.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, ep_id INTEGER NOT NULL REFERENCES eps(id) ON DELETE CASCADE, title TEXT NOT NULL, due_date TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Belum selesai', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            ep_id = db.execute("INSERT INTO eps (name, program, manager_id) VALUES ('Dina', 'Global Talent', ?)", (self.manager,)).lastrowid
            unassigned_ep = db.execute("INSERT INTO eps (name, program) VALUES ('Lama', 'Global Talent')").lastrowid
            db.execute("INSERT INTO tasks (ep_id, title) VALUES (?, 'Tugas lama')", (ep_id,))
            db.execute("INSERT INTO tasks (ep_id, title) VALUES (?, 'Belum ada PIC')", (unassigned_ep,))
        app.init_db()
        manager_token = self.login('manager')
        self.assertEqual([row['title'] for row in self.request('tasks', token=manager_token)[1]], ['Tugas lama'])
        self.assertEqual(len(self.request('tasks', token=self.vp)[1]), 2)
        self.request('eps/' + str(ep_id), 'DELETE', token=self.vp)
        task = self.request('tasks', token=manager_token)[1][0]
        self.assertEqual(task['title'], 'Tugas lama')
        self.assertIsNone(task['ep_id'])
        app.init_db()
        self.assertEqual(len(self.request('tasks', token=self.vp)[1]), 2)

    def test_old_tracker_rows_survive_migration(self):
        legacy = Path(self.temp.name) / 'legacy.db'
        with sqlite3.connect(legacy) as db:
            db.execute("CREATE TABLE eps (id INTEGER PRIMARY KEY, name TEXT, contact TEXT, program TEXT, destination TEXT, pic TEXT, status TEXT, notes TEXT, updated_at TEXT)")
            db.execute("INSERT INTO eps (name, program, pic) VALUES ('Lama', 'Global Talent', 'PIC lama')")
        app.DB_PATH = legacy
        app.init_db()
        with app.connect() as db:
            row = db.execute('SELECT name, pic, manager_id FROM eps').fetchone()
        self.assertEqual((row['name'], row['pic'], row['manager_id']), ('Lama', 'PIC lama', None))

if __name__ == '__main__':
    unittest.main()
