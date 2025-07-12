import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

# === Konstanta ===
USERS_FILE = 'users.json'
DEFAULT_ROLE = 'viewer'

# Daftar user yang tidak bisa dihapus atau diubah password-nya tanpa izin khusus
PROTECTED_USERS = {
    'admin', 'keuangan_user', 'pembukuan_user',
    'pengelolaan_user', 'sdm_user', 'trhasil_user',
    'sekum_user', 'instansi_user', 'driver_user'
}

# Role yang diperbolehkan dalam sistem
VALID_ROLES = [
    'admin', 'keuangan', 'pembukuan', 'pengelolaan',
    'sdm', 'trhasil', 'sekum', 'instansi', 'viewer', 'driver'
]

# === Fungsi untuk Memuat User ===
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    else:
        # User default pertama kali, dengan password yang sudah di-hash
        return {
            'admin': {'password': generate_password_hash('admin123'), 'role': 'admin'},
            'keuangan_user': {'password': generate_password_hash('keuangan123'), 'role': 'keuangan'},
            'pembukuan_user': {'password': generate_password_hash('pembukuan123'), 'role': 'pembukuan'},
            'pengelolaan_user': {'password': generate_password_hash('pengelolaan123'), 'role': 'pengelolaan'},
            'sdm_user': {'password': generate_password_hash('sdm123'), 'role': 'sdm'},
            'trhasil_user': {'password': generate_password_hash('trhasil123'), 'role': 'trhasil'},
            'sekum_user': {'password': generate_password_hash('sekum123'), 'role': 'sekum'},
            'instansi_user': {'password': generate_password_hash('instansi123'), 'role': 'instansi'},
            'driver_user': {'password': generate_password_hash('driver123'), 'role': 'driver'}
        }

# === Simpan ke File ===
def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

# === Inisialisasi ===
users = load_users()

# === Fungsi Pemeriksaan User ===
def is_protected_user(username):
    return username in PROTECTED_USERS

def check_user(username, password):
    return (
        username in users and
        check_password_hash(users[username]['password'], password)
    )

def get_user_role(username):
    if username in users:
        return users[username]['role']
    return None

# === Fungsi Registrasi ===
def register_user(username, password, role=DEFAULT_ROLE):
    if username in users:
        return False, "Username sudah terdaftar!"
    if role not in VALID_ROLES:
        return False, "Role tidak valid!"

    users[username] = {
        'password': generate_password_hash(password),
        'role': role
    }
    save_users(users)
    return True, "Registrasi berhasil!"

# === Update Password ===
def update_password(username, new_password, from_lupa=False):
    if username in users:
        if not from_lupa and username in PROTECTED_USERS:
            return False  # Tidak bisa ganti password user dilindungi tanpa akses khusus
        users[username]['password'] = generate_password_hash(new_password)
        save_users(users)
        return True
    return False

# === Dapatkan Semua Pengguna ===
def get_all_users():
    return {u: info['role'] for u, info in users.items()}

# === Validasi Role ===
def is_valid_role(role):
    return role in VALID_ROLES
