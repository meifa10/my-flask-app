from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, session
from db import get_db_connection
import csv
import os
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import pdfplumber
import re

sekum_bp = Blueprint('sekum', __name__, url_prefix='/sekum')

JENIS_MAPPING = {
    'prpo': 'PR/PO',
    'surat_keluar': 'Surat Keluar',
    'surat_masuk': 'Surat Masuk',
    'berita_acara': 'Berita Acara',
    'lain_lain': 'Lain-Lain'
}

def fetch_and_render(jenis_urlkey):
    jenis_nama = JENIS_MAPPING.get(jenis_urlkey)
    if not jenis_nama:
        return "Jenis tidak ditemukan", 404

    cari = request.args.get('cari', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    if cari:
        like_value = f"%{cari}%"
        query = """
            SELECT * FROM sekum 
            WHERE jenis = %s 
              AND (nomor_surat LIKE %s COLLATE utf8mb4_general_ci 
                   OR vendor LIKE %s COLLATE utf8mb4_general_ci)
            ORDER BY tanggal DESC
        """
        cursor.execute(query, (jenis_nama, like_value, like_value))
    else:
        cursor.execute("SELECT * FROM sekum WHERE jenis = %s ORDER BY tanggal DESC", (jenis_nama,))

    data = cursor.fetchall()
    conn.close()
    return render_template('sekum/index.html', data=data, jenis=jenis_nama, jenis_url=jenis_urlkey)

def get_jenis_urlkey_from_nama(jenis_nama):
    for key, val in JENIS_MAPPING.items():
        if val == jenis_nama:
            return key
    return None

@sekum_bp.route('/<jenis_urlkey>')
def index_jenis(jenis_urlkey):
    return fetch_and_render(jenis_urlkey)

# tambah data sekum
@sekum_bp.route('/tambah/<jenis_urlkey>', methods=['GET', 'POST'])
def tambah(jenis_urlkey):
    if session.get('role') == 'viewer':
        flash("Anda tidak memiliki akses untuk menambah data.", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    jenis_nama = JENIS_MAPPING.get(jenis_urlkey)
    if not jenis_nama:
        return "Jenis tidak ditemukan", 404

    if request.method == 'POST':
        tanggal = request.form.get('tanggal')
        nomor_surat = request.form.get('nomor_surat')
        vendor = request.form.get('vendor')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sekum (tanggal, nomor_surat, jenis, vendor)
            VALUES (%s, %s, %s, %s)
        """, (tanggal, nomor_surat, jenis_nama, vendor))
        conn.commit()
        conn.close()
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    return render_template('sekum/create.html', jenis=jenis_nama, jenis_url=jenis_urlkey)

# edit data sekum
@sekum_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if session.get('role') == 'viewer':
        flash("Anda tidak memiliki akses untuk mengedit data.", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey='lain_lain'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sekum WHERE id = %s", (id,))
    row = cursor.fetchone()

    if not row:
        return "Data tidak ditemukan", 404

    if request.method == 'POST':
        tanggal = request.form.get('tanggal')
        nomor_surat = request.form.get('nomor_surat')
        vendor = request.form.get('vendor')
        jenis = row[4]

        cursor.execute("""
            UPDATE sekum SET tanggal=%s, nomor_surat=%s, vendor=%s WHERE id=%s
        """, (tanggal, nomor_surat, vendor, id))
        conn.commit()
        conn.close()

        jenis_urlkey = get_jenis_urlkey_from_nama(jenis)
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    jenis_nama = row[4]
    jenis_urlkey = get_jenis_urlkey_from_nama(jenis_nama)
    conn.close()
    return render_template('sekum/edit.html', row=row, jenis=jenis_nama, jenis_url=jenis_urlkey)

# hapus data sekum
@sekum_bp.route('/hapus/<int:id>')
def hapus(id):
    if session.get('role') == 'viewer':
        flash("Anda tidak memiliki akses untuk menghapus data.", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey='lain_lain'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT jenis FROM sekum WHERE id = %s", (id,))
    result = cursor.fetchone()

    if not result:
        return "Data tidak ditemukan", 404

    jenis_nama = result[0]
    jenis_urlkey = get_jenis_urlkey_from_nama(jenis_nama)

    cursor.execute("DELETE FROM sekum WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

# unduh excel data sekum
@sekum_bp.route('/unduh_excel/<jenis_urlkey>')
def unduh_excel(jenis_urlkey):
    jenis_nama = JENIS_MAPPING.get(jenis_urlkey)
    if not jenis_nama:
        return "Jenis tidak ditemukan", 404

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, nomor_surat, vendor FROM sekum WHERE jenis = %s ORDER BY tanggal DESC", (jenis_nama,))
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=['Tanggal', 'Nomor Surat', 'Vendor'])
    df.insert(0, 'No', range(1, len(df) + 1))

    tanggal_str = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_str}_sekum_{jenis_urlkey}.xlsx'
    filepath = os.path.join('static', filename)

    df.to_excel(filepath, index=False)
    return send_from_directory('static', filename, as_attachment=True)

# unduh pdf data sekum
@sekum_bp.route('/unduh_pdf/<jenis_urlkey>')
def unduh_pdf(jenis_urlkey):
    jenis_nama = JENIS_MAPPING.get(jenis_urlkey)
    if not jenis_nama:
        return "Jenis tidak ditemukan", 404

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, nomor_surat, vendor FROM sekum WHERE jenis = %s ORDER BY tanggal DESC", (jenis_nama,))
    rows = cursor.fetchall()
    conn.close()

    tanggal_str = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_str}_sekum_{jenis_urlkey}.pdf'
    filepath = os.path.join('static', filename)

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Laporan Sekum - {jenis_nama}", ln=True, align='C')
    pdf.ln(4)

    headers = ['No', 'Tanggal', 'Nomor Surat', 'Vendor']
    col_widths = [10, 30, 60, 160]

    pdf.set_font("Arial", 'B', 11)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", '', 10)
    for idx, row in enumerate(rows, 1):
        pdf.cell(col_widths[0], 10, str(idx), border=1)
        for i in range(len(row)):
            text = str(row[i]) if row[i] else ''
            if len(text) > (col_widths[i + 1] // 2):
                text = text[:int(col_widths[i + 1] // 2) - 3] + '...'
            pdf.cell(col_widths[i + 1], 10, text, border=1)
        pdf.ln()

    pdf.output(filepath)
    return send_from_directory('static', filename, as_attachment=True)

# import excel data sekum
@sekum_bp.route('/import_excel/<jenis_urlkey>', methods=['POST'])
def import_excel(jenis_urlkey):
    jenis_nama = JENIS_MAPPING.get(jenis_urlkey)
    if not jenis_nama:
        flash("Jenis tidak ditemukan", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    file = request.files.get('file')
    if not file:
        flash("File tidak ditemukan", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    try:
        filename = file.filename.lower()
        if filename.endswith('.xlsx'):
            df = pd.read_excel(file)
        elif filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            flash("Format file tidak didukung", "danger")
            return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

        print("[DEBUG] Kolom Excel:", df.columns.tolist())
        if not all(col in df.columns for col in ['Tanggal', 'Nomor Surat', 'Vendor']):
            flash("Kolom tidak sesuai", "danger")
            return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

        conn = get_db_connection()
        cursor = conn.cursor()
        inserted = 0

        for _, row in df.iterrows():
            try:
                tanggal = pd.to_datetime(row['Tanggal']).strftime('%Y-%m-%d')
                nomor_surat = str(row['Nomor Surat']).strip()
                vendor = str(row['Vendor']).strip()
                print(f"[INSERT EXCEL] {tanggal} | {nomor_surat} | {vendor}")
                cursor.execute("""
                    INSERT INTO sekum (tanggal, nomor_surat, jenis, vendor)
                    VALUES (%s, %s, %s, %s)
                """, (tanggal, nomor_surat, jenis_nama, vendor))
                inserted += 1
            except Exception as e:
                print("[ERROR ROW]", e)

        conn.commit()
        conn.close()
        flash(f"Berhasil mengimpor {inserted} baris dari Excel", "success")

    except Exception as e:
        print("[ERROR IMPORT EXCEL]", e)
        flash(f"Gagal impor: {e}", "danger")

    return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

# import pdf data sekum
@sekum_bp.route('/import_pdf/<jenis_urlkey>', methods=['POST'])
def import_pdf(jenis_urlkey):
    if session.get('role') == 'viewer':
        flash("Anda tidak memiliki akses untuk impor PDF.", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    jenis_nama = JENIS_MAPPING.get(jenis_urlkey)
    if not jenis_nama:
        flash("Jenis tidak ditemukan.", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey='lain_lain'))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash("❌ Tidak ada file PDF diunggah!", "danger")
        return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))

    try:
        rows_inserted = 0
        conn = get_db_connection()
        cursor = conn.cursor()

        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                lines = text.split("\n")

                for line in lines:
                    match = re.match(r"^\d+\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s+(.+)$", line.strip())
                    if match:
                        tanggal_raw, nomor_surat, vendor = match.groups()
                        try:
                            tanggal = pd.to_datetime(tanggal_raw).strftime('%Y-%m-%d')
                        except Exception:
                            continue
                        cursor.execute("""
                            INSERT INTO sekum (tanggal, nomor_surat, jenis, vendor)
                            VALUES (%s, %s, %s, %s)
                        """, (tanggal, nomor_surat, jenis_nama, vendor.strip()))
                        rows_inserted += 1

        conn.commit()
        conn.close()

        if rows_inserted > 0:
            flash(f"✅ Berhasil mengimpor {rows_inserted} data dari PDF.", "success")
        else:
            flash("⚠️ Tidak ada baris valid dari PDF.", "warning")

    except Exception as e:
        flash(f"❌ Gagal memproses PDF: {e}", "danger")

    return redirect(url_for('sekum.index_jenis', jenis_urlkey=jenis_urlkey))
