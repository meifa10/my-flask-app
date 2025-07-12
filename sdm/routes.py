from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, session
from db import get_db_connection
import os
import pandas as pd
from fpdf import FPDF
from werkzeug.utils import secure_filename
import pdfplumber
import re
from datetime import datetime

sdm_bp = Blueprint('sdm', __name__)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper untuk menampilkan data berdasarkan status
def fetch_by_status(status, template, keyword=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if keyword:
        keyword = f"%{keyword}%"
        query = """
            SELECT * FROM sdm
            WHERE status = %s AND (no_kontrak LIKE %s OR data_diri LIKE %s)
            ORDER BY tanggal DESC
        """
        cursor.execute(query, (status, keyword, keyword))
    else:
        query = "SELECT * FROM sdm WHERE status = %s ORDER BY tanggal DESC"
        cursor.execute(query, (status,))
    data = cursor.fetchall()
    conn.close()
    return render_template('sdm/index.html', data=data, status=status)

# Halaman utama SDM
@sdm_bp.route('/<status>')
def index(status):
    keyword = request.args.get('cari')
    return fetch_by_status(status, 'sdm/index.html', keyword)

# tambah data SDM
@sdm_bp.route('/tambah/<status>', methods=['GET', 'POST'])
def tambah(status):
    if session.get('role') == 'viewer':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('sdm.index', status=status))

    if request.method == 'POST':
        no_kontrak = request.form['no_kontrak']
        data_diri = request.form['data_diri']
        tanggal = request.form['tanggal']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sdm (no_kontrak, data_diri, tanggal, status)
            VALUES (%s, %s, %s, %s)
        """, (no_kontrak, data_diri, tanggal, status))
        conn.commit()
        conn.close()

        flash("Data berhasil ditambahkan.", "success")
        return redirect(url_for('sdm.index', status=status))

    return render_template('sdm/create.html', status=status)

# edit data SDM
@sdm_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if session.get('role') == 'viewer':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sdm WHERE id=%s", (id,))
    row = cursor.fetchone()

    if not row:
        return "Data tidak ditemukan", 404

    if request.method == 'POST':
        no_kontrak = request.form['no_kontrak']
        data_diri = request.form['data_diri']
        tanggal = request.form['tanggal']
        status = request.form['status']

        cursor.execute("""
            UPDATE sdm SET no_kontrak=%s, data_diri=%s, tanggal=%s, status=%s WHERE id=%s
        """, (no_kontrak, data_diri, tanggal, status, id))
        conn.commit()
        conn.close()

        flash("Data berhasil diperbarui.", "success")
        return redirect(url_for('sdm.index', status=status))

    conn.close()
    return render_template('sdm/edit.html', row=row, status=row[4])

# hapus data SDM
@sdm_bp.route('/hapus/<int:id>')
def hapus(id):
    if session.get('role') == 'viewer':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM sdm WHERE id = %s", (id,))
    result = cursor.fetchone()
    if not result:
        return "Data tidak ditemukan", 404

    status = result[0]
    cursor.execute("DELETE FROM sdm WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    flash("Data berhasil dihapus.", "success")
    return redirect(url_for('sdm.index', status=status))

# unduh excel data SDM
@sdm_bp.route('/unduh_excel/<status>')
def unduh_excel(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT no_kontrak, data_diri, tanggal FROM sdm WHERE status = %s ORDER BY tanggal DESC", (status,))
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=['No. Kontrak', 'Data Diri', 'Tanggal'])
    df.insert(0, 'No', range(1, len(df) + 1))

    # Gunakan tanggal hari ini
    today_str = datetime.now().strftime('%Y-%m-%d')
    filename = f'{today_str}_{status}_sdm.xlsx'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    df.to_excel(filepath, index=False)

    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

# unduh pdf data SDM
@sdm_bp.route('/unduh_pdf/<status>')
def unduh_pdf(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT no_kontrak, data_diri, tanggal FROM sdm WHERE status = %s ORDER BY tanggal DESC", (status,))
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Laporan SDM - {status.upper()}", ln=True, align='C')
    pdf.ln(5)

    headers = ['No', 'No. Kontrak', 'Data Diri', 'Tanggal']
    widths = [10, 50, 170, 40]

    pdf.set_font("Arial", 'B', 10)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 10, h, 1, align='C')
    pdf.ln()

    pdf.set_font("Arial", '', 9)
    for idx, row in enumerate(rows, start=1):
        pdf.cell(widths[0], 10, str(idx), 1, align='C')
        for i, val in enumerate(row):
            val_str = str(val)
            if len(val_str) > (widths[i + 1] // 2):
                val_str = val_str[:(widths[i + 1] // 2) - 3] + "..."
            pdf.cell(widths[i + 1], 10, val_str, 1)
        pdf.ln()

    today_str = datetime.now().strftime('%Y-%m-%d')
    filename = f'{today_str}_{status}_sdm.pdf'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    pdf.output(filepath)

    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

# upload excel data SDM 
@sdm_bp.route('/upload_excel/<status>', methods=['GET'])
def upload_excel_form(status):
    return render_template('sdm/upload_excel.html', status=status)

@sdm_bp.route('/import_excel/<status>', methods=['POST'])
def import_excel(status):
    if session.get('role') == 'viewer':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('sdm.index', status=status))

    file = request.files.get('excel_file')
    if not file or file.filename == '':
        flash("❌ Tidak ada file yang dipilih!", 'danger')
        return redirect(url_for('sdm.upload_excel_form', status=status))

    filename = file.filename.lower()

    try:
        # Reset file cursor ke awal agar bisa dibaca ulang
        file.seek(0)

        # Baca file sesuai jenis
        if filename.endswith('.xlsx'):
            df = pd.read_excel(file, engine='openpyxl')
        elif filename.endswith('.xls'):
            df = pd.read_excel(file, engine='xlrd')
        elif filename.endswith('.csv'):
            try:
                df = pd.read_csv(file, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file, encoding='latin1')
        else:
            flash("❌ Format file tidak didukung. Gunakan .xlsx, .xls, atau .csv", 'danger')
            return redirect(url_for('sdm.upload_excel_form', status=status))

        # Normalisasi kolom
        df.columns = [c.strip().lower().replace('.', '').replace(' ', '_') for c in df.columns]

        # Validasi kolom wajib
        if not all(col in df.columns for col in ['no_kontrak', 'data_diri', 'tanggal']):
            flash("❌ Kolom wajib 'No. Kontrak', 'Data Diri', dan 'Tanggal' tidak ditemukan!", "danger")
            return redirect(url_for('sdm.upload_excel_form', status=status))

        conn = get_db_connection()
        cursor = conn.cursor()

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO sdm (no_kontrak, data_diri, tanggal, status)
                VALUES (%s, %s, %s, %s)
            """, (
                str(row['no_kontrak']),
                str(row['data_diri']),
                str(row['tanggal']),
                status
            ))

        conn.commit()
        conn.close()
        flash("✅ Data berhasil diimpor dari file!", "success")

    except Exception as e:
        flash(f"❌ Gagal mengimpor: {e}", "danger")

    return redirect(url_for('sdm.index', status=status))

# upload pdf data SDM 
@sdm_bp.route('/upload_pdf/<status>', methods=['GET'])
def upload_pdf_form(status):
    return render_template('sdm/upload_pdf.html', status=status)

@sdm_bp.route('/import_pdf/<status>', methods=['POST'])
def import_pdf(status):
    if session.get('role') == 'viewer':
        flash("Akses ditolak.", "danger")
        return redirect(url_for('sdm.index', status=status))

    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        flash("❌ Harap unggah file PDF yang valid!", "danger")
        return redirect(url_for('sdm.upload_pdf_form', status=status))

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        rows_inserted = 0
        conn = get_db_connection()
        cursor = conn.cursor()

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                lines = text.split('\n')

                for line in lines:
                    # Match: No [spasi] NoKontrak [spasi] Data Diri [spasi] Tanggal
                    match = re.match(r"^\d+\s+(\S+)\s+(.+)\s+(\d{4}-\d{2}-\d{2})$", line.strip())
                    if match:
                        no_kontrak, data_diri, tanggal_raw = match.groups()
                        try:
                            tanggal = pd.to_datetime(tanggal_raw).strftime('%Y-%m-%d')
                            cursor.execute("""
                                INSERT INTO sdm (no_kontrak, data_diri, tanggal, status)
                                VALUES (%s, %s, %s, %s)
                            """, (no_kontrak.strip(), data_diri.strip(), tanggal, status))
                            rows_inserted += 1
                        except Exception as e:
                            print("[SKIP]", line, e)
                            continue

        conn.commit()
        conn.close()

        if rows_inserted > 0:
            flash(f"✅ Berhasil mengimpor {rows_inserted} baris dari PDF.", "success")
        else:
            flash("⚠️ Tidak ada data valid dari PDF.", "warning")

    except Exception as e:
        flash(f"❌ Gagal memproses PDF: {e}", "danger")

    return redirect(url_for('sdm.index', status=status))
