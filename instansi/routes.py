from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, session
from db import get_db_connection
from werkzeug.utils import secure_filename
from fpdf import FPDF
import os
import pandas as pd
from datetime import datetime 
import pdfplumber

instansi_bp = Blueprint('instansi', __name__, url_prefix='/instansi')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# INDEX + SEARCH DATA INSTANSI
@instansi_bp.route('/')
def index():
    keyword = request.args.get('q')
    conn = get_db_connection()
    cursor = conn.cursor()

    if keyword:
        pattern = f"%{keyword}%"
        cursor.execute("""
            SELECT * FROM instansi 
            WHERE nama LIKE %s OR alamat LIKE %s OR kontak LIKE %s OR struktur_organisasi LIKE %s
            ORDER BY id DESC
        """, (pattern, pattern, pattern, pattern))
    else:
        cursor.execute("SELECT * FROM instansi ORDER BY id DESC")

    data = cursor.fetchall()
    conn.close()
    return render_template('instansi/index.html', data=data, keyword=keyword)

# tambah data instansi
@instansi_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if session.get('role') == 'viewer':
        flash("Akses ditolak. Anda tidak memiliki izin untuk menambahkan data.", "danger")
        return redirect(url_for('instansi.index'))

    if request.method == 'POST':
        nama = request.form['nama']
        alamat = request.form['alamat']
        kontak = request.form['kontak']
        struktur_organisasi = request.form['struktur_organisasi']
        visi = request.form['visi']
        misi = request.form['misi']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO instansi (nama, alamat, kontak, struktur_organisasi, visi, misi)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nama, alamat, kontak, struktur_organisasi, visi, misi))
        conn.commit()
        conn.close()
        return redirect(url_for('instansi.index'))

    return render_template('instansi/create.html')

# edit data instansi
@instansi_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if session.get('role') == 'viewer':
        flash("Akses ditolak. Anda tidak memiliki izin untuk mengedit data.", "danger")
        return redirect(url_for('instansi.index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        nama = request.form['nama']
        alamat = request.form['alamat']
        kontak = request.form['kontak']
        struktur_organisasi = request.form['struktur_organisasi']
        visi = request.form['visi']
        misi = request.form['misi']

        cursor.execute("""
            UPDATE instansi
            SET nama=%s, alamat=%s, kontak=%s, struktur_organisasi=%s, visi=%s, misi=%s
            WHERE id=%s
        """, (nama, alamat, kontak, struktur_organisasi, visi, misi, id))
        conn.commit()
        conn.close()
        return redirect(url_for('instansi.index'))

    cursor.execute("SELECT * FROM instansi WHERE id=%s", (id,))
    row = cursor.fetchone()
    conn.close()
    return render_template('instansi/edit.html', row=row)

# hapus data instansi
@instansi_bp.route('/hapus/<int:id>', methods=['POST'])
def hapus(id):
    if session.get('role') == 'viewer':
        flash("Akses ditolak. Anda tidak memiliki izin untuk menghapus data.", "danger")
        return redirect(url_for('instansi.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM instansi WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("✅ Data berhasil dihapus!", "success")
    return redirect(url_for('instansi.index'))

# unduh excel data instansi
@instansi_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nama, alamat, kontak, struktur_organisasi, visi, misi 
        FROM instansi ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=['Nama', 'Alamat', 'Kontak', 'Struktur Organisasi', 'Visi', 'Misi'])
    df.insert(0, 'No', range(1, len(df) + 1))

    tanggal = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal}_instansi_laporan.xlsx'
    path = os.path.join('static', filename)
    df.to_excel(path, index=False)

    return send_from_directory('static', filename, as_attachment=True)

# unduh pdf data instansi
@instansi_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nama, alamat, kontak, struktur_organisasi, visi, misi 
        FROM instansi ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, 'Laporan Data Instansi', ln=True, align='C')
    pdf.ln(5)

    headers = ['No', 'Nama', 'Alamat', 'Kontak', 'Struktur Organisasi', 'Visi', 'Misi']
    widths = [10, 40, 40, 30, 45, 60, 60]

    pdf.set_font("Arial", 'B', 9)
    for i in range(len(headers)):
        pdf.cell(widths[i], 8, headers[i], border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", '', 8)
    for idx, row in enumerate(rows, 1):
        pdf.cell(widths[0], 8, str(idx), border=1)
        for i, value in enumerate(row):
            text = str(value)[:35]
            pdf.cell(widths[i + 1], 8, text, border=1)
        pdf.ln()

    tanggal = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal}_instansi_laporan.pdf'
    path = os.path.join('static', filename)
    pdf.output(path)

    return send_from_directory('static', filename, as_attachment=True)

# upload excel data instansi
@instansi_bp.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if session.get('role') == 'viewer':
        flash("Akses ditolak. Anda tidak memiliki izin untuk mengimpor data.", "danger")
        return redirect(url_for('instansi.index'))

    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                df = pd.read_excel(path)
                required = ['Nama', 'Alamat', 'Kontak', 'Struktur Organisasi', 'Visi', 'Misi']
                if not all(col in df.columns for col in required):
                    flash("❌ Kolom tidak sesuai. Harus ada: Nama, Alamat, Kontak, Struktur Organisasi, Visi, Misi", "danger")
                    return redirect(url_for('instansi.upload_excel'))

                conn = get_db_connection()
                cursor = conn.cursor()

                for _, row in df.iterrows():
                    if pd.isna(row['Nama']) or pd.isna(row['Alamat']) or pd.isna(row['Kontak']):
                        continue

                    cursor.execute("""
                        INSERT INTO instansi (nama, alamat, kontak, struktur_organisasi, visi, misi)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        str(row['Nama']), str(row['Alamat']), str(row['Kontak']),
                        str(row['Struktur Organisasi']) if not pd.isna(row['Struktur Organisasi']) else '',
                        str(row['Visi']) if not pd.isna(row['Visi']) else '',
                        str(row['Misi']) if not pd.isna(row['Misi']) else ''
                    ))

                conn.commit()
                conn.close()
                flash("✅ Data berhasil diimpor dari Excel!", "success")
            except Exception as e:
                flash(f"❌ Gagal mengimpor: {e}", "danger")
        else:
            flash("❗ File tidak valid. Hanya .xlsx dan .pdf yang didukung.", "warning")

        return redirect(url_for('instansi.index'))

    return render_template('instansi/upload_excel.html')

# upload pdf data instansi
@instansi_bp.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if session.get('role') == 'viewer':
        flash("Akses ditolak. Anda tidak memiliki izin untuk mengimpor data.", "danger")
        return redirect(url_for('instansi.index'))

    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename) and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            try:
                data_rows = []
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        for table in tables:
                            for i, row in enumerate(table):
                                if i == 0:  # Skip header
                                    continue
                                if row and len(row) >= 7:
                                    # Lewati kolom pertama (No)
                                    data_rows.append(row[1:7])

                conn = get_db_connection()
                cursor = conn.cursor()

                for row in data_rows:
                    nama, alamat, kontak, struktur, visi, misi = row
                    cursor.execute("""
                        INSERT INTO instansi (nama, alamat, kontak, struktur_organisasi, visi, misi)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (nama, alamat, kontak, struktur, visi, misi))

                conn.commit()
                conn.close()

                flash(f"✅ {len(data_rows)} data dari PDF berhasil diimpor!", "success")
            except Exception as e:
                flash(f"❌ Gagal memproses PDF: {e}", "danger")

            return redirect(url_for('instansi.index'))
        else:
            flash("❌ File tidak valid. Hanya format .pdf yang didukung.", "danger")

    return render_template('instansi/upload_pdf.html')
