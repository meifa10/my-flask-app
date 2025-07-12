from flask import Blueprint, render_template, request, redirect, url_for, send_file, flash, session
from werkzeug.utils import secure_filename
from db import get_db_connection
import pandas as pd
from fpdf import FPDF
import os
from datetime import datetime
import pdfplumber

pengelolaan_bp = Blueprint('pengelolaan', __name__, url_prefix='/pengelolaan')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Halaman utama pengelolaan + Search, index
@pengelolaan_bp.route('/')
def index():
    keyword = request.args.get('q')
    conn = get_db_connection()
    cursor = conn.cursor()

    if keyword:
        pattern = f"%{keyword}%"
        cursor.execute("""
            SELECT * FROM pengelolaan
            WHERE nama_aset LIKE %s OR lokasi LIKE %s OR status LIKE %s 
                  OR jadwal_perawatan LIKE %s OR pic LIKE %s
            ORDER BY jadwal_perawatan DESC
        """, (pattern, pattern, pattern, pattern, pattern))
    else:
        cursor.execute("SELECT * FROM pengelolaan ORDER BY jadwal_perawatan DESC")

    data = cursor.fetchall()
    conn.close()
    return render_template('pengelolaan/index.html', data=data, keyword=keyword)

# tambah data pengelolaan
@pengelolaan_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if session.get('role') == 'viewer':
        return redirect(url_for('pengelolaan.index'))

    if request.method == 'POST':
        nama_aset = request.form['nama_aset']
        lokasi = request.form['lokasi']
        status = request.form['status']
        jadwal_perawatan = request.form['jadwal_perawatan']
        pic = request.form['pic']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pengelolaan (nama_aset, lokasi, status, jadwal_perawatan, pic)
            VALUES (%s, %s, %s, %s, %s)
        """, (nama_aset, lokasi, status, jadwal_perawatan, pic))
        conn.commit()
        conn.close()
        return redirect(url_for('pengelolaan.index'))

    return render_template('pengelolaan/create.html')

# edit data pengelolaan
@pengelolaan_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pengelolaan WHERE id=%s", (id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return redirect(url_for('pengelolaan.index'))

    if request.method == 'POST':
        nama_aset = request.form['nama_aset']
        lokasi = request.form['lokasi']
        status = request.form['status']
        jadwal_perawatan = request.form['jadwal_perawatan']
        pic = request.form['pic']

        cursor.execute("""
            UPDATE pengelolaan
            SET nama_aset=%s, lokasi=%s, status=%s, jadwal_perawatan=%s, pic=%s
            WHERE id=%s
        """, (nama_aset, lokasi, status, jadwal_perawatan, pic, id))
        conn.commit()
        conn.close()
        return redirect(url_for('pengelolaan.index'))

    conn.close()
    return render_template('pengelolaan/edit.html', row=row)

# hapus data pengelolaan
@pengelolaan_bp.route('/hapus/<int:id>')
def hapus(id):
    if session.get('role') == 'viewer':
        return redirect(url_for('pengelolaan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pengelolaan WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('pengelolaan.index'))

# unduh excel data pengelolaan
@pengelolaan_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    df = pd.read_sql("""
        SELECT nama_aset, lokasi, status, jadwal_perawatan, pic
        FROM pengelolaan
        ORDER BY nama_aset ASC
    """, conn)
    conn.close()

    # Rename kolom agar sesuai dengan tabel dan import
    df = df.rename(columns={
        'nama_aset': 'Nama Aset',
        'lokasi': 'Lokasi',
        'status': 'Status',
        'jadwal_perawatan': 'Jadwal Perawatan',
        'pic': 'PIC'
    })

    df = df.astype(str)
    df.insert(0, 'No', range(1, len(df) + 1))  # Tambahkan kolom No

    tanggal_sekarang = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_sekarang}_pengelolaan.xlsx'
    filepath = os.path.join('static', filename)

    df.to_excel(filepath, index=False)
    return send_file(filepath, as_attachment=True)

# unduh pdf data pengelolaan
@pengelolaan_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nama_aset, lokasi, status, jadwal_perawatan, pic
        FROM pengelolaan
        ORDER BY nama_aset ASC
    """)
    data = cursor.fetchall()
    conn.close()

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Data Pengelolaan Aset", ln=True, align='C')
    pdf.ln(8)

    # Header dan lebar kolom
    headers = ["No", "Nama Aset", "Lokasi", "Status", "Jadwal", "PIC"]
    col_widths = [10, 55, 55, 40, 45, 55]

    # Tulis header
    pdf.set_font("Arial", 'B', 10)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, border=1, align='C')
    pdf.ln()

    # Tulis isi data
    pdf.set_font("Arial", size=9)
    for idx, row in enumerate(data, start=1):
        pdf.cell(col_widths[0], 8, str(idx), border=1, align='C')  # No
        for i, item in enumerate(row):
            text = str(item) if item else "-"
            if len(text) > (col_widths[i + 1] // 2):
                text = text[:int(col_widths[i + 1] // 2) - 3] + '...'
            pdf.cell(col_widths[i + 1], 8, text, border=1, align='C')
        pdf.ln()

    filename = f"{datetime.now().strftime('%Y-%m-%d')}_pengelolaan.pdf"
    filepath = os.path.join('static', filename)
    pdf.output(filepath)
    return send_file(filepath, as_attachment=True)


# upload excel data pengelolaan
@pengelolaan_bp.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if session.get('role') == 'viewer':
        return redirect(url_for('pengelolaan.index'))

    if request.method == 'POST':
        file = request.files.get('excel_file')

        if file and file.filename.lower().endswith(('.xlsx', '.xls', '.xlsm')):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                df = pd.read_excel(path)

                # Cetak header yang terbaca dari Excel (debug)
                print("[HEADER EXCEL TERBACA]:", df.columns.tolist())

                # Expected kolom tanpa 'No'
                expected_columns = ['Nama Aset', 'Lokasi', 'Status', 'Jadwal Perawatan', 'PIC']
                actual_columns = [col.strip() for col in df.columns if col.strip() != 'No']

                if actual_columns != expected_columns:
                    flash(f"❌ Format kolom tidak sesuai. Kolom terbaca: {', '.join(df.columns)}<br>Gunakan header: No, Nama Aset, Lokasi, Status, Jadwal Perawatan, PIC", "danger")
                    return redirect(url_for('pengelolaan.upload_excel'))

                if 'No' in df.columns:
                    df = df.drop(columns=['No'])

                conn = get_db_connection()
                cursor = conn.cursor()
                rows_inserted = 0

                for index, row in df.iterrows():
                    try:
                        nama_aset = str(row['Nama Aset']).strip()
                        lokasi = str(row['Lokasi']).strip()
                        status = str(row['Status']).strip()
                        jadwal = pd.to_datetime(row['Jadwal Perawatan']).strftime('%Y-%m-%d')
                        pic = str(row['PIC']).strip()

                        if not (nama_aset and lokasi and status and jadwal):
                            continue

                        cursor.execute("""
                            INSERT INTO pengelolaan (nama_aset, lokasi, status, jadwal_perawatan, pic)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (nama_aset, lokasi, status, jadwal, pic))
                        rows_inserted += 1
                    except Exception as e:
                        print(f"[SKIP BARIS] Baris ke-{index+2} gagal: {e}")
                        continue

                conn.commit()
                conn.close()
                flash(f"✅ Berhasil mengimpor {rows_inserted} baris dari Excel!", "success")

            except Exception as e:
                flash(f"❌ Gagal membaca file Excel: {e}", "danger")
        else:
            flash("❗ File tidak valid. Harap unggah file Excel (.xlsx, .xls, .xlsm)", "warning")

        return redirect(url_for('pengelolaan.index'))

    return render_template('pengelolaan/upload_excel.html')

# upload pdf data pengelolaan
@pengelolaan_bp.route('/upload_pdf', methods=['GET'])
def upload_pdf_form():
    if session.get('role') == 'viewer':
        return redirect(url_for('pengelolaan.index'))
    return render_template('pengelolaan/upload_pdf.html')

# proses import pdf data pengelolaan
@pengelolaan_bp.route('/import_pdf', methods=['POST'])
def import_pdf():
    if session.get('role') == 'viewer':
        return redirect(url_for('pengelolaan.index'))

    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        flash("❌ Harap unggah file PDF yang valid!", "danger")
        return redirect(url_for('pengelolaan.upload_pdf_form'))

    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(filepath)

    # Status yang diperbolehkan sesuai database
    allowed_statuses = ['Aktif', 'Rusak', 'Perawatan']

    try:
        rows_inserted = 0
        conn = get_db_connection()
        cursor = conn.cursor()

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                lines = page.extract_text().split("\n")

                for line in lines:
                    try:
                        parts = line.strip().split()
                        if len(parts) < 6:
                            continue

                        pic = parts[-1]
                        jadwal_raw = parts[-2]

                        try:
                            jadwal = pd.to_datetime(jadwal_raw).strftime('%Y-%m-%d')
                        except:
                            continue

                        # Deteksi status (1 kata saja: Aktif, Rusak, Perawatan)
                        status_candidate = parts[-3]
                        if status_candidate not in allowed_statuses:
                            continue

                        status = status_candidate

                        # Ambil nama aset (1 kata setelah nomor)
                        nama_aset = parts[1]

                        # Lokasi = semua kata di antara nama_aset dan status
                        lokasi_parts = parts[2:-3]
                        lokasi = " ".join(lokasi_parts)

                        # Simpan ke DB
                        cursor.execute("""
                            INSERT INTO pengelolaan (nama_aset, lokasi, status, jadwal_perawatan, pic)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (nama_aset, lokasi, status, jadwal, pic))
                        rows_inserted += 1

                    except Exception as e:
                        print("[SKIP BARIS]", line, e)
                        continue

        conn.commit()
        conn.close()

        if rows_inserted:
            flash(f"✅ Berhasil mengimpor {rows_inserted} data dari PDF.", "success")
        else:
            flash("⚠️ Tidak ada data valid dari PDF.", "warning")

    except Exception as e:
        flash(f"❌ Gagal memproses PDF: {e}", "danger")

    return redirect(url_for('pengelolaan.index'))

