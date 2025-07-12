from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, session
from db import get_db_connection
from fpdf import FPDF
import os
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import pdfplumber

# Blueprint setup
tanaman_bp = Blueprint('tanaman', __name__, url_prefix='/tanaman')

# Upload config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# INDEX + SEARCH DATA TANAMAN
@tanaman_bp.route('/')
def index():
    keyword = request.args.get('q', '')
    conn = get_db_connection()
    cursor = conn.cursor()

    if keyword:
        pattern = f"%{keyword}%"
        query = """
            SELECT * FROM tanaman
            WHERE `Nama Tanaman` LIKE %s OR `Luas Lahan` LIKE %s OR `Tanggal Tanam` LIKE %s OR `Hasil Panen` LIKE %s
            ORDER BY `Tanggal Tanam` DESC
        """
        cursor.execute(query, (pattern, pattern, pattern, pattern))
    else:
        cursor.execute("SELECT * FROM tanaman ORDER BY `Tanggal Tanam` DESC")

    data = cursor.fetchall()
    conn.close()
    return render_template('tanaman/index.html', data=data, keyword=keyword)

# tambah data tanaman
@tanaman_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki izin untuk menambah data.", "danger")
        return redirect(url_for('tanaman.index'))

    if request.method == 'POST':
        nama = request.form['nama_tanaman']
        luas = request.form['luas_lahan']
        tanam = request.form['tanggal_tanam']
        panen = request.form['estimasi_panen']
        hasil = request.form['hasil_panen']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tanaman (`Nama Tanaman`, `Luas Lahan`, `Tanggal Tanam`, `Estimasi Panen`, `Hasil Panen`)
            VALUES (%s, %s, %s, %s, %s)
        """, (nama, luas, tanam, panen, hasil))
        conn.commit()
        conn.close()
        return redirect(url_for('tanaman.index'))
    return render_template('tanaman/create.html')

# edit data tanaman
@tanaman_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki izin untuk mengedit data.", "danger")
        return redirect(url_for('tanaman.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        nama = request.form['nama_tanaman']
        luas = request.form['luas_lahan']
        tanam = request.form['tanggal_tanam']
        panen = request.form['estimasi_panen']
        hasil = request.form['hasil_panen']

        cursor.execute("""
            UPDATE tanaman 
            SET `Nama Tanaman`=%s, `Luas Lahan`=%s, `Tanggal Tanam`=%s, `Estimasi Panen`=%s, `Hasil Panen`=%s
            WHERE `ID`=%s
        """, (nama, luas, tanam, panen, hasil, id))
        conn.commit()
        conn.close()
        return redirect(url_for('tanaman.index'))
    else:
        cursor.execute("SELECT * FROM tanaman WHERE `ID`=%s", (id,))
        row = cursor.fetchone()
        conn.close()
        return render_template('tanaman/edit.html', row=row)

# hapus data tanaman
@tanaman_bp.route('/hapus/<int:id>')
def hapus(id):
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki izin untuk menghapus data.", "danger")
        return redirect(url_for('tanaman.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tanaman WHERE `ID`=%s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('tanaman.index'))

# unduh excel data tanaman
@tanaman_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT `Nama Tanaman`, `Luas Lahan`, `Tanggal Tanam`, `Estimasi Panen`, `Hasil Panen` FROM tanaman ORDER BY `Tanggal Tanam` DESC")
    rows = cursor.fetchall()
    conn.close()

    columns = ['Nama Tanaman', 'Luas Lahan', 'Tanggal Tanam', 'Estimasi Panen', 'Hasil Panen']
    df = pd.DataFrame(rows, columns=columns)

    df.insert(0, 'No', range(1, len(df) + 1))  # Tambahkan kolom No
    df = df.astype(str)

    tanggal_sekarang = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_sekarang}_tanaman_laporan.xlsx'
    path = os.path.join('static', filename)

    df.to_excel(path, index=False)
    return send_from_directory('static', filename, as_attachment=True)

# unduh pdf data tanaman
@tanaman_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT `Nama Tanaman`, `Luas Lahan`, `Tanggal Tanam`, `Estimasi Panen`, `Hasil Panen` FROM tanaman ORDER BY `Tanggal Tanam` DESC")
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Laporan Data Tanaman", ln=True, align='C')
    pdf.ln(5)

    headers = ['No', 'Nama Tanaman', 'Luas Lahan (Ha)', 'Tanggal Tanam', 'Estimasi Panen', 'Hasil Panen (Ton)']
    col_widths = [10, 50, 35, 35, 35, 40]

    pdf.set_font("Arial", 'B', 11)
    for i in range(len(headers)):
        pdf.cell(col_widths[i], 10, headers[i], border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", size=10)
    for idx, row in enumerate(rows, start=1):
        pdf.cell(col_widths[0], 10, str(idx), border=1)  # Kolom No
        for i in range(len(row)):
            text = str(row[i])
            if len(text) > (col_widths[i + 1] // 2):
                text = text[:int(col_widths[i + 1] // 2) - 3] + '...'
            pdf.cell(col_widths[i + 1], 10, text, border=1)
        pdf.ln()

    filename = f'{datetime.now().strftime("%Y-%m-%d")}_tanaman_laporan.pdf'
    pdf_path = os.path.join('static', filename)
    pdf.output(pdf_path)

    return send_from_directory('static', filename, as_attachment=True)

# upload excel data tanaman
@tanaman_bp.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki izin untuk upload data.", "danger")
        return redirect(url_for('tanaman.index'))

    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            try:
                df = pd.read_excel(path)
                required_columns = ['Nama Tanaman', 'Luas Lahan', 'Tanggal Tanam', 'Estimasi Panen', 'Hasil Panen']
                if not all(col in df.columns for col in required_columns):
                    flash("❌ Kolom Excel tidak sesuai.", "danger")
                    return redirect(url_for('tanaman.upload_excel'))
                conn = get_db_connection()
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    if pd.isna(row['Nama Tanaman']) or pd.isna(row['Luas Lahan']):
                        continue
                    nama = str(row['Nama Tanaman'])
                    luas = str(row['Luas Lahan'])
                    tanam = pd.to_datetime(row['Tanggal Tanam']).strftime('%Y-%m-%d') if not pd.isna(row['Tanggal Tanam']) else None
                    panen = pd.to_datetime(row['Estimasi Panen']).strftime('%Y-%m-%d') if not pd.isna(row['Estimasi Panen']) else None
                    hasil = str(row['Hasil Panen']) if not pd.isna(row['Hasil Panen']) else "0"
                    cursor.execute("""
                        INSERT INTO tanaman (`Nama Tanaman`, `Luas Lahan`, `Tanggal Tanam`, `Estimasi Panen`, `Hasil Panen`)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (nama, luas, tanam, panen, hasil))
                conn.commit()
                conn.close()
                flash("✅ Data berhasil diimpor dari Excel!", "success")
            except Exception as e:
                flash(f"❌ Gagal mengimpor Excel: {e}", "danger")
        else:
            flash("❗ Harap unggah file Excel (.xlsx)", "warning")
        return redirect(url_for('tanaman.index'))
    return render_template('tanaman/upload_excel.html')

# upload pdf data tanaman
@tanaman_bp.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if session.get('role') == 'viewer':
        flash("❌ Anda tidak memiliki izin untuk upload data.", "danger")
        return redirect(url_for('tanaman.index'))

    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                all_rows = []
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue
                        lines = text.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.lower().startswith("no") or line.lower().startswith("laporan"):
                                continue

                            parts = line.split()
                            if len(parts) < 6:
                                continue

                            # Kolom: No Nama Luas1 Luas2 TglTanam TglPanen [Hasil]
                            nama = parts[1]
                            luas = parts[2] + ' ' + parts[3]
                            tanam = parts[4]
                            panen = parts[5]
                            hasil = parts[6] if len(parts) > 6 else '0'

                            try:
                                tanggal_tanam = pd.to_datetime(tanam).strftime('%Y-%m-%d')
                                estimasi_panen = pd.to_datetime(panen).strftime('%Y-%m-%d')
                            except:
                                continue

                            all_rows.append((nama, luas, tanggal_tanam, estimasi_panen, hasil))

                if not all_rows:
                    flash("❌ Tidak ada data valid ditemukan dalam PDF.", "danger")
                    return redirect(url_for('tanaman.upload_pdf'))

                conn = get_db_connection()
                cursor = conn.cursor()
                for row in all_rows:
                    cursor.execute("""
                        INSERT INTO tanaman (`Nama Tanaman`, `Luas Lahan`, `Tanggal Tanam`, `Estimasi Panen`, `Hasil Panen`)
                        VALUES (%s, %s, %s, %s, %s)
                    """, row)
                conn.commit()
                conn.close()

                flash("✅ Data berhasil diimpor dari PDF!", "success")
            except Exception as e:
                flash(f"❌ Gagal membaca PDF: {e}", "danger")
        else:
            flash("❌ File tidak valid. Harap unggah file PDF (.pdf)", "danger")

        return redirect(url_for('tanaman.index'))

    return render_template('tanaman/upload_pdf.html')
