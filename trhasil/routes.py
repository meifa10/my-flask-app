from flask import Blueprint, render_template, request, redirect, url_for, send_file, send_from_directory, flash, session
from werkzeug.utils import secure_filename
from db import get_db_connection
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import io
import pdfplumber 

trhasil_bp = Blueprint('trhasil', __name__, url_prefix='/trhasil')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Halaman utama
@trhasil_bp.route('/')
def index():
    keyword = request.args.get('keyword', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    if keyword:
        wildcard = f"%{keyword}%"
        cursor.execute("""
            SELECT * FROM tr_hasil 
            WHERE tanggal LIKE %s OR jenis LIKE %s OR jumlah LIKE %s
            ORDER BY tanggal DESC
        """, (wildcard, wildcard, wildcard))
    else:
        cursor.execute("SELECT * FROM tr_hasil ORDER BY tanggal DESC")

    data = cursor.fetchall()
    conn.close()
    return render_template('trhasil/index.html', data=data, keyword=keyword)

# tambah data trhasil
@trhasil_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki akses untuk menambah data.", "danger")
        return redirect(url_for('trhasil.index'))

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        jenis = request.form['jenis']
        jumlah = request.form['jumlah']
        satuan = request.form['satuan']
        keterangan = request.form['keterangan']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tr_hasil (tanggal, jenis, jumlah, satuan, keterangan)
            VALUES (%s, %s, %s, %s, %s)
        """, (tanggal, jenis, jumlah, satuan, keterangan))
        conn.commit()
        conn.close()
        flash("✅ Data berhasil ditambahkan.", "success")
        return redirect(url_for('trhasil.index'))

    return render_template('trhasil/create.html')

# edit data trhasil
@trhasil_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki akses untuk mengedit data.", "danger")
        return redirect(url_for('trhasil.index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        jenis = request.form['jenis']
        jumlah = request.form['jumlah']
        satuan = request.form['satuan']
        keterangan = request.form['keterangan']

        cursor.execute("""
            UPDATE tr_hasil SET tanggal=%s, jenis=%s, jumlah=%s, satuan=%s, keterangan=%s WHERE id=%s
        """, (tanggal, jenis, jumlah, satuan, keterangan, id))
        conn.commit()
        conn.close()
        flash("✅ Data berhasil diupdate.", "success")
        return redirect(url_for('trhasil.index'))

    cursor.execute("SELECT * FROM tr_hasil WHERE id=%s", (id,))
    row = cursor.fetchone()
    conn.close()
    return render_template('trhasil/edit.html', row=row)

# hapus data trhasil
@trhasil_bp.route('/hapus/<int:id>')
def hapus(id):
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki akses untuk menghapus data.", "danger")
        return redirect(url_for('trhasil.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tr_hasil WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("🗑️ Data berhasil dihapus.", "success")
    return redirect(url_for('trhasil.index'))

# unduh excel data trhasil
@trhasil_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, jenis, jumlah, satuan, keterangan FROM tr_hasil ORDER BY tanggal ASC")
    rows = cursor.fetchall()
    conn.close()

    # Buat DataFrame dan tambahkan kolom No (1, 2, 3,...)
    df = pd.DataFrame(rows, columns=['Tanggal', 'Jenis', 'Jumlah', 'Satuan', 'Keterangan'])
    df.insert(0, 'No', range(1, len(df) + 1))

    tanggal_sekarang = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_sekarang}_trhasil_laporan.xlsx'
    xlsx_path = os.path.join('static', filename)

    df.to_excel(xlsx_path, index=False)
    return send_from_directory('static', filename, as_attachment=True)

# unduh pdf data trhasil
@trhasil_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, jenis, jumlah, satuan, keterangan FROM tr_hasil ORDER BY tanggal ASC")
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Laporan TR Hasil", ln=True, align='C')
    pdf.ln(5)

    # Header tabel PDF
    headers = ['No', 'Tanggal', 'Jenis', 'Jumlah', 'Satuan', 'Keterangan']
    col_widths = [10, 30, 35, 25, 25, 60]

    pdf.set_font("Arial", 'B', 10)
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 10, headers[i], border=1)
    pdf.ln()

    pdf.set_font("Arial", '', 10)
    for idx, row in enumerate(rows, 1):
        pdf.cell(col_widths[0], 10, str(idx), border=1)  # No
        pdf.cell(col_widths[1], 10, str(row[0])[:20], border=1)  # Tanggal
        pdf.cell(col_widths[2], 10, str(row[1])[:20], border=1)  # Jenis
        pdf.cell(col_widths[3], 10, str(row[2]), border=1)       # Jumlah
        pdf.cell(col_widths[4], 10, str(row[3]), border=1)       # Satuan
        pdf.cell(col_widths[5], 10, str(row[4])[:30], border=1)  # Keterangan
        pdf.ln()

    filename = f"{datetime.now().strftime('%Y-%m-%d')}_trhasil_laporan.pdf"
    pdf_path = os.path.join('static', filename)
    pdf.output(pdf_path)
    return send_from_directory('static', filename, as_attachment=True)

# upload excel data trhasil (.xlsx, .xls, .csv)
@trhasil_bp.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki akses untuk mengupload data.", "danger")
        return redirect(url_for('trhasil.index'))

    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                ext = filename.rsplit('.', 1)[1].lower()
                if ext == 'csv':
                    df = pd.read_csv(path)
                else:
                    df = pd.read_excel(path)

                df.columns = df.columns.str.strip().str.title()  # pastikan kapitalisasi

                required_columns = ['Tanggal', 'Jenis', 'Jumlah', 'Satuan', 'Keterangan']
                for col in required_columns:
                    if col not in df.columns:
                        flash(f"❌ Kolom '{col}' tidak ditemukan di file.", "danger")
                        return redirect(url_for('trhasil.upload_excel'))

                conn = get_db_connection()
                cursor = conn.cursor()

                for _, row in df.iterrows():
                    if pd.isna(row['Tanggal']) or pd.isna(row['Jenis']) or pd.isna(row['Jumlah']):
                        continue

                    tanggal = pd.to_datetime(row['Tanggal']).strftime('%Y-%m-%d')
                    jenis = str(row['Jenis'])
                    jumlah = str(row['Jumlah'])
                    satuan = str(row['Satuan']) if not pd.isna(row['Satuan']) else ''
                    keterangan = str(row['Keterangan']) if not pd.isna(row['Keterangan']) else ''

                    cursor.execute("""
                        INSERT INTO tr_hasil (tanggal, jenis, jumlah, satuan, keterangan)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (tanggal, jenis, jumlah, satuan, keterangan))

                conn.commit()
                conn.close()
                flash("✅ Data berhasil diimpor dari file!", "success")

            except Exception as e:
                flash(f"❌ Gagal mengimpor file: {e}", "danger")
        else:
            flash("❗ Format file tidak valid. Harap unggah file .xlsx, .xls, atau .csv", "warning")

        return redirect(url_for('trhasil.index'))

    return render_template('trhasil/upload_excel.html')

# upload pdf data trhasil
@trhasil_bp.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki akses untuk mengupload data.", "danger")
        return redirect(url_for('trhasil.index'))

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.pdf'):
            flash("❗ Harap unggah file PDF yang valid.", "danger")
            return redirect(url_for('trhasil.upload_pdf'))

        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
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
                        if line.strip().startswith("No "):  # skip header
                            continue
                        parts = line.strip().split()
                        if len(parts) >= 6:
                            try:
                                # Ambil kolom dari format "1 2025-07-15 gula 25.0 ton keterangan..."
                                tanggal = pd.to_datetime(parts[1]).strftime('%Y-%m-%d')
                                jenis = parts[2]
                                jumlah = parts[3]
                                satuan = parts[4]
                                keterangan = " ".join(parts[5:])

                                cursor.execute("""
                                    INSERT INTO tr_hasil (tanggal, jenis, jumlah, satuan, keterangan)
                                    VALUES (%s, %s, %s, %s, %s)
                                """, (tanggal, jenis, jumlah, satuan, keterangan))
                                rows_inserted += 1
                            except Exception as e:
                                print(f"Skip line error: {e}")
                                continue

            conn.commit()
            conn.close()

            if rows_inserted > 0:
                flash(f"✅ Berhasil mengimpor {rows_inserted} data dari PDF!", "success")
            else:
                flash("⚠️ Tidak ada baris valid ditemukan dalam PDF.", "warning")

        except Exception as e:
            flash(f"❌ Gagal membaca file PDF: {e}", "danger")

        return redirect(url_for('trhasil.index'))

    return render_template('trhasil/upload_pdf.html')
