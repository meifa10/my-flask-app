from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from db import get_db_connection
from fpdf import FPDF
from datetime import datetime
import pandas as pd
import pdfplumber
import io
import os
import pytz
import re
import requests

ajuan_sppd_bp = Blueprint('ajuan_sppd', __name__, url_prefix='/ajuan_sppd')

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# index data ajuan_sppd
@ajuan_sppd_bp.route('/')
def index():
    cari = request.args.get('cari', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    if cari:
        like = f"%{cari}%"
        cursor.execute("""
            SELECT a.id, a.nama, a.jabatan, a.tujuan, a.berangkat, a.pulang,
                   a.nopol, a.driver, a.lokasi_link,
                   l.latitude, l.longitude
            FROM ajuan_sppd a
            LEFT JOIN lokasi_driver l ON a.id = l.ajuan_id
            WHERE a.nama LIKE %s COLLATE utf8mb4_general_ci
               OR a.jabatan LIKE %s COLLATE utf8mb4_general_ci
               OR a.tujuan LIKE %s COLLATE utf8mb4_general_ci
               OR a.berangkat LIKE %s COLLATE utf8mb4_general_ci
               OR a.pulang LIKE %s COLLATE utf8mb4_general_ci
               OR a.nopol LIKE %s COLLATE utf8mb4_general_ci
               OR a.driver LIKE %s COLLATE utf8mb4_general_ci
            ORDER BY a.berangkat DESC
        """, (like, like, like, like, like, like, like))
    else:
        cursor.execute("""
            SELECT a.id, a.nama, a.jabatan, a.tujuan, a.berangkat, a.pulang,
                   a.nopol, a.driver, a.lokasi_link,
                   l.latitude, l.longitude
            FROM ajuan_sppd a
            LEFT JOIN lokasi_driver l ON a.id = l.ajuan_id
            ORDER BY a.berangkat DESC
        """)

    data = cursor.fetchall()
    conn.close()
    return render_template('ajuan_sppd/index.html', data=data)

# tambah data ajuan_sppd submenu dari sekum
@ajuan_sppd_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if session.get('role') in ['viewer', 'driver']:
        flash("Anda tidak memiliki akses untuk menambah data.", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    if request.method == 'POST':
        nama = request.form.get('nama')
        jabatan = request.form.get('jabatan')
        tujuan = request.form.get('tujuan')
        berangkat = request.form.get('berangkat')
        pulang = request.form.get('pulang')
        nopol = request.form.get('nopol')
        driver = request.form.get('driver')
        lokasi_link = request.form.get('lokasi_link')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ajuan_sppd (nama, jabatan, tujuan, berangkat, pulang, nopol, driver, lokasi_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (nama, jabatan, tujuan, berangkat, pulang, nopol, driver, lokasi_link))
        conn.commit()
        conn.close()
        flash("Data berhasil ditambahkan.", "success")
        return redirect(url_for('ajuan_sppd.index'))

    return render_template('ajuan_sppd/create.html')

# edit data ajuan_sppd submenu dari sekum
@ajuan_sppd_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if session.get('role') in ['viewer', 'driver']:
        flash("Anda tidak memiliki akses untuk mengedit data.", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ajuan_sppd WHERE id = %s", (id,))
    data = cursor.fetchone()

    if not data:
        flash("Data tidak ditemukan.", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    if request.method == 'POST':
        nama = request.form.get('nama')
        jabatan = request.form.get('jabatan')
        tujuan = request.form.get('tujuan')
        berangkat = request.form.get('berangkat')
        pulang = request.form.get('pulang')
        nopol = request.form.get('nopol')
        driver = request.form.get('driver')
        lokasi_link = request.form.get('lokasi_link')

        cursor.execute("""
            UPDATE ajuan_sppd
            SET nama=%s, jabatan=%s, tujuan=%s, berangkat=%s, pulang=%s, nopol=%s, driver=%s, lokasi_link=%s
            WHERE id = %s
        """, (nama, jabatan, tujuan, berangkat, pulang, nopol, driver, lokasi_link, id))
        conn.commit()
        conn.close()
        flash("Data berhasil diperbarui.", "success")
        return redirect(url_for('ajuan_sppd.index'))

    conn.close()
    return render_template('ajuan_sppd/edit.html', row=data)

# hapus data ajuan_sppd submenu dari sekum
@ajuan_sppd_bp.route('/hapus/<int:id>')
def hapus(id):
    if session.get('role') in ['viewer', 'driver']:
        flash("Anda tidak memiliki akses untuk menghapus data.", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Hapus data lokasi_driver terlebih dahulu
        cursor.execute("DELETE FROM lokasi_driver WHERE ajuan_id = %s", (id,))

        # Baru hapus data dari ajuan_sppd
        cursor.execute("DELETE FROM ajuan_sppd WHERE id = %s", (id,))
        conn.commit()
        conn.close()

        flash("✅ Data berhasil dihapus.", "success")

    except Exception as e:
        flash(f"❌ Gagal menghapus data: {e}", "danger")

    return redirect(url_for('ajuan_sppd.index'))

# unduh data pdf ajuan_sppd submenu dari sekum 
@ajuan_sppd_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ajuan_sppd ORDER BY berangkat DESC")
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Laporan Ajuan SPPD", ln=True, align='C')
    pdf.ln(5)

    # Ukuran kolom hemat ruang
    label_width = 30       # Kolom kiri: label
    separator_width = 4    # Untuk titik dua saja
    value_width = 55       # Kolom kanan: isi

    pdf.set_font("Arial", size=9)

    for row in rows:
        labels = ["Nama", "Jabatan", "Tujuan", "Berangkat", "Pulang", "Nopol", "Driver", "Lokasi"]
        values = row[1:]  # Lewati kolom ID (di indeks 0)

        for label, value in zip(labels, values):
            pdf.cell(label_width, 7, label, border=1)
            pdf.cell(separator_width, 7, ":", border=1, align='C')
            pdf.cell(value_width, 7, str(value), border=1, ln=True)

        pdf.ln(3)  # Jarak antar entri

    # Gunakan waktu lokal Indonesia
    waktu = datetime.now(pytz.timezone('Asia/Jakarta'))
    filename = f"{waktu.strftime('%Y-%m-%d')}_ajuan_sppd.pdf"
    filepath = os.path.join('static', filename)
    pdf.output(filepath)
    return send_from_directory('static', filename, as_attachment=True)

# unduh data excel ajuan_sppd submenu dari sekum
@ajuan_sppd_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama, jabatan, tujuan, berangkat, pulang, nopol, driver, lokasi_link FROM ajuan_sppd ORDER BY berangkat DESC")
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=['Nama', 'Jabatan', 'Tujuan', 'Berangkat', 'Pulang', 'Nopol', 'Driver', 'Lokasi'])
    df.insert(0, 'No', range(1, len(df) + 1))  # Tambahkan kolom Nomor 

    waktu = datetime.now(pytz.timezone('Asia/Jakarta'))
    filename = f"{waktu.strftime('%Y-%m-%d')}_ajuan_sppd.xlsx"
    filepath = os.path.join('static', filename)
    df.to_excel(filepath, index=False)
    return send_from_directory('static', filename, as_attachment=True)

# import data excel ajuan_sppd submenu dari sekum
@ajuan_sppd_bp.route('/import_excel', methods=['POST'])
def import_excel():
    if 'role' not in session or session.get('role') in ['viewer', 'driver']:
        flash("❌ Anda tidak memiliki akses untuk mengimpor data Excel!", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash("❌ Tidak ada file yang diunggah!", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    filename = file.filename.lower()

    try:
        # Deteksi berdasarkan ekstensi
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file, engine='openpyxl')

        # Kolom yang diharapkan
        expected = ['Nama', 'Jabatan', 'Tujuan', 'Berangkat', 'Pulang', 'Nopol', 'Driver', 'Lokasi']
        if not all(col in df.columns for col in expected):
            flash("❌ Format kolom tidak sesuai!", "danger")
            return redirect(url_for('ajuan_sppd.index'))

        conn = get_db_connection()
        cursor = conn.cursor()
        inserted = 0

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO ajuan_sppd (nama, jabatan, tujuan, berangkat, pulang, nopol, driver, lokasi_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['Nama'],
                row['Jabatan'],
                row['Tujuan'],
                pd.to_datetime(row['Berangkat']).strftime('%Y-%m-%d'),
                pd.to_datetime(row['Pulang']).strftime('%Y-%m-%d'),
                row['Nopol'],
                row['Driver'],
                row['Lokasi']
            ))
            inserted += 1

        conn.commit()
        conn.close()

        flash(f"✅ Berhasil impor {inserted} data dari file.", "success")

    except Exception as e:
        flash(f"❌ Gagal impor file: {e}", "danger")

    return redirect(url_for('ajuan_sppd.index'))

# import data ajuan_sppd sub menu dari sekum
@ajuan_sppd_bp.route('/import_pdf', methods=['POST'])
def import_pdf():
    if 'role' not in session or session.get('role') in ['viewer', 'driver']:
        flash("❌ Anda tidak memiliki akses untuk mengimpor data PDF!", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash("❌ Tidak ada file PDF diunggah!", "danger")
        return redirect(url_for('ajuan_sppd.index'))

    try:
        rows_inserted = 0
        conn = get_db_connection()
        cursor = conn.cursor()

        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.strip().split("\n")
                entries = []
                current = []
                for line in lines:
                    if line.strip().lower().startswith("nama :") and current:
                        entries.append(current)
                        current = [line]
                    else:
                        current.append(line)
                if current:
                    entries.append(current)

                for entry in entries:
                    data = {}
                    for line in entry:
                        if ':' in line:
                            key, val = line.split(":", 1)
                            data[key.strip().lower()] = val.strip()

                    if all(k in data for k in ['nama', 'jabatan', 'tujuan', 'berangkat', 'pulang', 'nopol', 'driver']):
                        cursor.execute("""
                            INSERT INTO ajuan_sppd (nama, jabatan, tujuan, berangkat, pulang, nopol, driver, lokasi_link)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            data['nama'],
                            data['jabatan'],
                            data['tujuan'],
                            pd.to_datetime(data['berangkat']).strftime('%Y-%m-%d'),
                            pd.to_datetime(data['pulang']).strftime('%Y-%m-%d'),
                            data['nopol'],
                            data['driver'],
                            data.get('lokasi', '')
                        ))
                        rows_inserted += 1

        conn.commit()
        conn.close()

        if rows_inserted > 0:
            flash(f"✅ Berhasil impor {rows_inserted} data dari PDF.", "success")
        else:
            flash("⚠️ Tidak ada data valid ditemukan dari PDF.", "warning")

    except Exception as e:
        flash(f"❌ Gagal impor PDF: {e}", "danger")

    return redirect(url_for('ajuan_sppd.index'))

@ajuan_sppd_bp.route('/update_lokasi', methods=['POST'])
def update_lokasi():
    id = request.form.get('id')
    lat = request.form.get('latitude')
    lng = request.form.get('longitude')

    if not id or not lat or not lng:
        return {"status": "error", "message": "Data tidak lengkap"}, 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE ajuan_sppd
        SET latitude = %s, longitude = %s
        WHERE id = %s
    """, (lat, lng, id))
    conn.commit()
    conn.close()

    return {"status": "success"}, 200

@ajuan_sppd_bp.route('/get-lokasi/<int:ajuan_id>')
def get_lokasi(ajuan_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT latitude, longitude FROM lokasi_driver WHERE ajuan_id = %s", (ajuan_id,))
    data = cursor.fetchone()
    conn.close()
    return jsonify(data or {'latitude': 0, 'longitude': 0})

@ajuan_sppd_bp.route('/lihat_peta/<int:id>')
def lihat_peta(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama, latitude, longitude FROM ajuan_sppd WHERE id = %s", (id,))
    data = cursor.fetchone()
    conn.close()

    if not data or not data[1] or not data[2]:
        flash("Data lokasi tidak tersedia untuk ID tersebut", "warning")
        return redirect(url_for('ajuan_sppd.index'))

    return render_template('ajuan_sppd/peta.html', nama=data[0], lat=data[1], lng=data[2])

@ajuan_sppd_bp.route('/track_driver', methods=['GET', 'POST'])
def track_driver():
    if 'username' not in session or session['role'] != 'driver':
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    ajuan_id = request.args.get("id")

    # Ambil status tracking dari database
    cursor.execute("SELECT tracking_aktif FROM ajuan_sppd WHERE id = %s", (ajuan_id,))
    row = cursor.fetchone()
    tracking_aktif = bool(row[0]) if row else False

    if request.method == 'POST':
        # kode simpan lokasi tetap seperti sebelumnya...
        pass

    return render_template('ajuan_sppd/track_driver.html', id=ajuan_id, tracking_aktif=tracking_aktif)

@ajuan_sppd_bp.route('/peta/<int:id>')
def peta_lokasi(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ambil lokasi terakhir dari tabel lokasi_driver
    cursor.execute("""
        SELECT latitude, longitude 
        FROM lokasi_driver 
        WHERE ajuan_id = %s 
        ORDER BY waktu DESC LIMIT 1
    """, (id,))
    lokasi = cursor.fetchone()

    # Ambil nama driver dari tabel ajuan_sppd
    cursor.execute("SELECT nama FROM ajuan_sppd WHERE id = %s", (id,))
    row = cursor.fetchone()

    conn.close()

    # Jika belum ada lokasi, redirect dengan pesan
    if not lokasi or not lokasi[0] or not lokasi[1]:
        flash("Lokasi belum tersedia untuk ajuan ini", "warning")
        return redirect(url_for('ajuan_sppd.index'))

    # Jika ada nama, tampilkan, jika tidak fallback ke "Driver"
    nama = row[0] if row else "Driver"

    # Kirim data ke template
    return render_template('ajuan_sppd/peta_lokasi.html',
        lat=lokasi[0],
        lon=lokasi[1],
        id=id,
        nama=nama  # ✅ penting agar bisa tampil di template
    )
    
@ajuan_sppd_bp.route('/lapor_lokasi', methods=['POST'])
def lapor_lokasi():
    conn = get_db_connection()
    id_data = request.form.get('id')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')

    if not all([id_data, lat, lon]):
        return jsonify({'status': 'error', 'message': 'Data tidak lengkap'})

    try:
        link = f'https://maps.google.com/?q={lat},{lon}'

        # ✅ Simpan ke lokasi_driver
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lokasi_driver (ajuan_id, latitude, longitude, alamat)
            VALUES (%s, %s, %s, %s)
        """, (id_data, lat, lon, link))

        # ✅ Update juga ke ajuan_sppd
        cursor.execute("""
            UPDATE ajuan_sppd
            SET lokasi_link = %s, latitude = %s, longitude = %s
            WHERE id = %s
        """, (link, lat, lon, id_data))

        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@ajuan_sppd_bp.route('/get_tracking/<int:id>')
def get_tracking(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT latitude, longitude, alamat FROM lokasi_driver
        WHERE ajuan_id = %s ORDER BY waktu ASC
    """, (id,))
    rows = cursor.fetchall()
    conn.close()

    data = []
    for row in rows:
        try:
            lat = float(row[0])
            lng = float(row[1])
            alamat = row[2] or ''
            data.append({"lat": lat, "lng": lng, "alamat": alamat})
        except Exception as e:
            print(f"[PARSE ERROR] {e} => {row}")
            continue

    return jsonify({"data": data})

@ajuan_sppd_bp.route('/driver/kirim-lokasi', methods=['GET', 'POST'])
def driver_form_lokasi():
    if 'username' not in session or session.get('role') != 'driver':
        flash('Akses ditolak. Login sebagai driver terlebih dahulu.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        ajuan_id = request.form.get('ajuan_id')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not ajuan_id or not latitude or not longitude:
            flash('Semua field wajib diisi.', 'warning')
            return redirect(url_for('ajuan_sppd.driver_form_lokasi'))

        # Default jika gagal reverse geocoding
        alamat = "Alamat tidak tersedia"

        # === REVERSE GEOCODING ===
        try:
            import requests
            url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json"
            headers = {"User-Agent": "PabrikGulaApp/1.0"}
            r = requests.get(url, headers=headers)
            print(f"[REVERSE STATUS] {r.status_code}")
            if r.status_code == 200:
                geo_data = r.json()
                alamat = geo_data.get("display_name", "Alamat tidak tersedia")
            else:
                print(f"[REVERSE ERROR] status {r.status_code}")
        except Exception as e:
            print(f"[REVERSE GEOCODE EXCEPTION] {e}")

        print(f"[DEBUG] Lokasi dikirim: ID={ajuan_id}, LAT={latitude}, LNG={longitude}, ALAMAT={alamat}")

        cursor.execute("""
            INSERT INTO lokasi_driver (ajuan_id, latitude, longitude, alamat)
            VALUES (%s, %s, %s, %s)
        """, (ajuan_id, latitude, longitude, alamat))

        conn.commit()
        flash('✅ Lokasi berhasil dikirim.', 'success')
        return redirect(url_for('ajuan_sppd.driver_form_lokasi'))

    # GET: Ambil semua data ajuan_sppd
    cursor.execute("SELECT id, nama, tujuan FROM ajuan_sppd ORDER BY berangkat DESC")
    rows = cursor.fetchall()
    conn.close()

    data = []
    for row in rows:
        data.append({
            'id': row[0],
            'nama': row[1],
            'tujuan': row[2]
        })

    return render_template('ajuan_sppd/kirim_lokasi.html', data=data)

@ajuan_sppd_bp.route('/pantau-lokasi/<int:ajuan_id>')
def pantau_lokasi(ajuan_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM ajuan_sppd WHERE id = %s", (ajuan_id,))
    row = cursor.fetchone()
    conn.close()

    nama = row[0] if row else "Driver"
    return render_template('ajuan_sppd/peta_lokasi.html', ajuan_id=ajuan_id, nama=nama)

def get_address_from_coords(lat, lng):
    try:
        response = requests.get(
            f'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lng, 'format': 'json'},
            headers={'User-Agent': 'PabrikGulaApp/1.0'}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('display_name', 'Alamat tidak ditemukan')
    except Exception as e:
        print("Reverse geocoding error:", e)
    return 'Alamat tidak ditemukan'

@ajuan_sppd_bp.route('/mulai_tracking/<int:id>', methods=['POST'])
def mulai_tracking(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE ajuan_sppd SET tracking_aktif = TRUE WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@ajuan_sppd_bp.route('/stop_tracking/<int:id>', methods=['POST'])
def stop_tracking(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE ajuan_sppd SET tracking_aktif = FALSE WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})
