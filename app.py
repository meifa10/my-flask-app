import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from users import check_user, get_user_role, register_user
from db import get_db_connection  # Pastikan Anda punya file db.py untuk koneksi database
import json

# Inisialisasi aplikasi
app = Flask(__name__)
app.secret_key = 'rahasia_super_aman'

# Konfigurasi database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/pabrik_gula'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Konfigurasi upload file
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls', 'csv', 'png', 'jpg', 'jpeg', 'pdf'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inisialisasi database
db = SQLAlchemy(app)

# Import dan register Blueprints
from keuangan.routes import keuangan_bp
from sekum.routes import sekum_bp
from pembukuan.routes import pembukuan_bp
from sdm.routes import sdm_bp
from trhasil.routes import trhasil_bp
from instansi.routes import instansi_bp
from tanaman.routes import tanaman_bp
from pengelolaan.routes import pengelolaan_bp
from ajuan_sppd.routes import ajuan_sppd_bp
from auth import auth_bp

app.register_blueprint(keuangan_bp, url_prefix='/keuangan')
app.register_blueprint(sekum_bp, url_prefix='/sekum')
app.register_blueprint(pembukuan_bp, url_prefix='/pembukuan')
app.register_blueprint(sdm_bp, url_prefix='/sdm')
app.register_blueprint(trhasil_bp, url_prefix='/trhasil')
app.register_blueprint(instansi_bp, url_prefix='/instansi')
app.register_blueprint(tanaman_bp, url_prefix='/tanaman')
app.register_blueprint(pengelolaan_bp, url_prefix='/pengelolaan')
app.register_blueprint(ajuan_sppd_bp, url_prefix='/ajuan_sppd')
app.register_blueprint(auth_bp, url_prefix='/auth')

# ========== LOGIN ==========

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username dan password wajib diisi!', 'warning')
            return redirect(url_for('login'))

        if check_user(username, password):
            session['username'] = username
            role = get_user_role(username)
            session['role'] = role
            flash('Login berhasil.', 'success')

            # Arahkan berdasarkan role
            if role == 'admin':
                return redirect(url_for('dashboard'))
            elif role == 'driver':
                return redirect(url_for('ajuan_sppd.driver_form_lokasi'))  # Arahkan driver ke form lokasi
            else:
                return redirect(url_for('dashboard'))  # default
        else:
            flash('Username atau password salah!', 'danger')
            return redirect(url_for('login'))

    return render_template('auth/login.html')

# ========== REGISTER ==========

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('password_confirmation')

        if not username or not password or not confirm:
            flash('Semua field wajib diisi!', 'warning')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Password dan konfirmasi tidak sama!', 'warning')
            return redirect(url_for('register'))

        success, message = register_user(username, password)
        if success:
            flash('Registrasi berhasil. Silakan login.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'danger')
            return redirect(url_for('register'))

    return render_template('auth/register.html')

# ========== DASHBOARD ==========

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Silakan login terlebih dahulu.', 'warning')
        return redirect(url_for('login'))

    return render_template(
        'dashboard.html',
        username=session.get('username'),
        role=session.get('role')
    )

# ========== LOGOUT ==========

@app.route('/logout')
def logout():
    session.clear()
    flash('Berhasil logout.', 'info')
    return redirect(url_for('login'))

# ========== GANTI PASSWORD ==========

@app.route('/ganti-password', methods=['GET', 'POST'])
def ganti_password():
    if 'username' not in session:
        flash('Silakan login terlebih dahulu.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        from users import check_user, users

        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not check_user(session['username'], old_password):
            flash("Password lama salah", 'danger')
            return redirect(url_for('ganti_password'))

        if new_password != confirm_password:
            flash("Konfirmasi password tidak cocok", 'warning')
            return redirect(url_for('ganti_password'))

        users[session['username']]['password'] = new_password
        flash("Password berhasil diubah", 'success')
        return redirect(url_for('dashboard'))

    return render_template('auth/ganti_password.html')

# ========== DRIVER KIRIM LOKASI ==========

@app.route('/ajuan_sppd/driver/kirim-lokasi', methods=['GET', 'POST'])
def driver_form_lokasi():
    if 'username' not in session or session.get('role') != 'driver':
        flash('Akses ditolak. Login sebagai driver terlebih dahulu.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        ajuan_id = request.form.get('ajuan_id')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not ajuan_id or not latitude or not longitude:
            flash('Semua field wajib diisi.', 'warning')
            return redirect(url_for('driver_form_lokasi'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lokasi_driver (ajuan_id, latitude, longitude)
            VALUES (%s, %s, %s)
        """, (ajuan_id, latitude, longitude))
        conn.commit()
        conn.close()

        flash('Lokasi berhasil dikirim.', 'success')
        return redirect(url_for('driver_form_lokasi'))

    # Ambil semua data ajuan_sppd
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nama, tujuan FROM ajuan_sppd ORDER BY berangkat DESC")
    data = cursor.fetchall()
    conn.close()

    return render_template('ajuan_sppd/driver_kirim_lokasi.html', data=data)

# Jalankan aplikasi
if __name__ == '__main__':
    app.run(debug=True)

