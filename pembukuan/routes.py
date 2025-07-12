from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, session
from werkzeug.utils import secure_filename
from db import get_db_connection
from fpdf import FPDF
import pandas as pd
import os
from datetime import datetime
import pdfplumber

pembukuan_bp = Blueprint('pembukuan', __name__, url_prefix='/pembukuan')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_viewer():
    return session.get('role') == 'viewer'
    
# index data pembukuan
@pembukuan_bp.route('/')
def index():
    keyword = request.args.get('keyword', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM pembukuan WHERE 1=1"
    params = []
    if keyword:
        query += """
            AND (
                tanggal LIKE %s OR
                akun LIKE %s OR
                keterangan LIKE %s
            )
        """
        wildcard = f"%{keyword}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY tanggal DESC"
    cursor.execute(query, tuple(params))
    data = cursor.fetchall()
    conn.close()

    return render_template('pembukuan/index.html', data=data, keyword=keyword, is_viewer=is_viewer())

# tambah data pembukuan
@pembukuan_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk menambah data.", "danger")
        return redirect(url_for('pembukuan.index'))

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        akun = request.form['akun']
        keterangan = request.form['keterangan']
        debit = float(request.form['debit'] or 0)
        kredit = float(request.form['kredit'] or 0)
        saldo = float(request.form['saldo'] or (debit - kredit))  # Bisa isi manual atau default

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pembukuan (tanggal, akun, keterangan, debit, kredit, saldo)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (tanggal, akun, keterangan, debit, kredit, saldo))
        conn.commit()
        conn.close()
        flash("✅ Data berhasil ditambahkan.", "success")
        return redirect(url_for('pembukuan.index'))

    return render_template('pembukuan/create.html') 

# edit data pembukuan 
@pembukuan_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk mengedit data.", "danger")
        return redirect(url_for('pembukuan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        akun = request.form['akun']
        keterangan = request.form['keterangan']
        debit = float(request.form['debit'] or 0)
        kredit = float(request.form['kredit'] or 0)
        saldo = float(request.form['saldo'] or (debit - kredit))  # Manual atau default hitung

        cursor.execute("""
            UPDATE pembukuan SET tanggal=%s, akun=%s, keterangan=%s,
            debit=%s, kredit=%s, saldo=%s WHERE id=%s
        """, (tanggal, akun, keterangan, debit, kredit, saldo, id))
        conn.commit()
        conn.close()
        flash("✅ Data berhasil diperbarui.", "success")
        return redirect(url_for('pembukuan.index'))

    cursor.execute("SELECT * FROM pembukuan WHERE id=%s", (id,))
    row = cursor.fetchone()
    conn.close()
    return render_template('pembukuan/edit.html', row=row)

# hapus data pembukuan
@pembukuan_bp.route('/hapus/<int:id>', methods=['POST'])
def hapus(id):
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk menghapus data.", "danger")
        return redirect(url_for('pembukuan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pembukuan WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("🗑️ Data berhasil dihapus.", "success")
    return redirect(url_for('pembukuan.index'))

# unduh excel data pembukuan
@pembukuan_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, akun, keterangan, debit, kredit, saldo FROM pembukuan ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=['Tanggal', 'Akun', 'Keterangan', 'Debit', 'Kredit', 'Saldo'])
    df.insert(0, 'No', range(1, len(df) + 1))
    df = df.astype(str)

    tanggal_sekarang = datetime.now().strftime('%Y-%m-%d')
    filename = f"{tanggal_sekarang}_pembukuan_laporan.xlsx"
    xlsx_path = os.path.join('static', filename)
    df.to_excel(xlsx_path, index=False)

    return send_from_directory('static', filename, as_attachment=True)

# unduh pdf data pembukuan
@pembukuan_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, akun, keterangan, debit, kredit, saldo FROM pembukuan ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Laporan Pembukuan", ln=True, align='C')
    pdf.ln(4)

    headers = ['No', 'Tanggal', 'Akun', 'Keterangan', 'Debit', 'Kredit', 'Saldo']
    col_widths = [10, 30, 35, 70, 25, 25, 25]

    pdf.set_font("Arial", 'B', 10)
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 8, headers[i], border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", '', 9)
    for idx, row in enumerate(rows, start=1):
        pdf.cell(col_widths[0], 8, str(idx), border=1)
        pdf.cell(col_widths[1], 8, str(row[0]), border=1)
        pdf.cell(col_widths[2], 8, str(row[1]), border=1)
        pdf.cell(col_widths[3], 8, str(row[2])[:40], border=1)
        pdf.cell(col_widths[4], 8, str(row[3]), border=1, align='R')
        pdf.cell(col_widths[5], 8, str(row[4]), border=1, align='R')
        pdf.cell(col_widths[6], 8, str(row[5]), border=1, align='R')
        pdf.ln()

    filename = f"{datetime.now().strftime('%Y-%m-%d')}_pembukuan_laporan.pdf"
    pdf_output = os.path.join('static', filename)
    pdf.output(pdf_output)

    return send_from_directory('static', filename, as_attachment=True)

# upload excel data pembukuan
@pembukuan_bp.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk mengunggah data.", "danger")
        return redirect(url_for('pembukuan.index'))

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

                df.columns = df.columns.str.strip().str.title()

                required_columns = ['Tanggal', 'Akun', 'Keterangan', 'Debit', 'Kredit', 'Saldo']
                if not all(col in df.columns for col in required_columns):
                    flash("❌ Kolom tidak sesuai. Excel harus berisi: Tanggal, Akun, Keterangan, Debit, Kredit, Saldo", "danger")
                    return redirect(url_for('pembukuan.upload_excel'))

                conn = get_db_connection()
                cursor = conn.cursor()

                for _, row in df.iterrows():
                    if pd.isna(row['Tanggal']) or pd.isna(row['Akun']):
                        continue

                    tanggal = pd.to_datetime(row['Tanggal']).strftime('%Y-%m-%d')
                    akun = str(row['Akun'])
                    keterangan = str(row['Keterangan']) if not pd.isna(row['Keterangan']) else ""
                    debit = float(row['Debit']) if not pd.isna(row['Debit']) else 0
                    kredit = float(row['Kredit']) if not pd.isna(row['Kredit']) else 0
                    saldo = float(row['Saldo']) if not pd.isna(row['Saldo']) else 0

                    cursor.execute("""
                        INSERT INTO pembukuan (tanggal, akun, keterangan, debit, kredit, saldo)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (tanggal, akun, keterangan, debit, kredit, saldo))

                conn.commit()
                conn.close()
                flash("✅ Data berhasil diimpor dari file!", "success")

            except Exception as e:
                flash(f"❌ Gagal mengimpor file: {e}", "danger")
        else:
            flash("❗ Format file tidak didukung. Harap unggah file .xlsx, .xls, atau .csv", "warning")

        return redirect(url_for('pembukuan.index'))

    return render_template('pembukuan/upload_excel.html')

# upload pdf data pembukuan 
@pembukuan_bp.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk mengunggah data.", "danger")
        return redirect(url_for('pembukuan.index'))

    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                rows_inserted = 0
                conn = get_db_connection()
                cursor = conn.cursor()

                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue

                        lines = text.split('\n')
                        for line in lines:
                            if line.strip().startswith("No") or line.strip() == "":
                                continue

                            parts = line.strip().split()
                            if len(parts) < 7:
                                continue

                            try:
                                tanggal = pd.to_datetime(parts[1]).strftime('%Y-%m-%d')
                                akun = parts[2]
                                keterangan = parts[3]
                                debit = float(parts[4].replace(',', ''))
                                kredit = float(parts[5].replace(',', ''))
                                saldo = float(parts[6].replace(',', ''))

                                cursor.execute("""
                                    INSERT INTO pembukuan (tanggal, akun, keterangan, debit, kredit, saldo)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (tanggal, akun, keterangan, debit, kredit, saldo))
                                rows_inserted += 1
                            except Exception as e:
                                print("⛔ Error parsing baris:", line)
                                continue

                conn.commit()
                conn.close()

                if rows_inserted > 0:
                    flash(f"✅ Berhasil mengimpor {rows_inserted} data dari PDF.", "success")
                else:
                    flash("⚠️ Tidak ada baris valid ditemukan dalam PDF.", "warning")

            except Exception as e:
                flash(f"❌ Gagal memproses PDF: {e}", "danger")

            return redirect(url_for('pembukuan.index'))

        else:
            flash("❗ Harap unggah file berformat .pdf", "danger")
            return redirect(url_for('pembukuan.upload_pdf'))

    return render_template('pembukuan/upload_pdf.html')

# submenu admin hasil data pembukuan
@pembukuan_bp.route('/admin_hasil')
def admin_hasil():
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk mengakses halaman ini.", "danger")
        return redirect(url_for('pembukuan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM pembukuan 
        WHERE akun LIKE %s 
        ORDER BY tanggal DESC
    """, ('%hasil%',))
    data = cursor.fetchall()
    conn.close()

    return render_template('pembukuan/index.html', data=data, keyword="hasil", is_viewer=is_viewer())

# submenu admin gula data pembukuan
@pembukuan_bp.route('/admin_gula')
def admin_gula():
    if is_viewer():
        flash("🚫 Anda tidak memiliki izin untuk mengakses halaman ini.", "danger")
        return redirect(url_for('pembukuan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM pembukuan 
        WHERE akun LIKE %s 
        ORDER BY tanggal DESC
    """, ('%gula%',))
    data = cursor.fetchall()
    conn.close()

    return render_template('pembukuan/index.html', data=data, keyword="gula", is_viewer=is_viewer())
