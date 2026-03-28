from flask import Flask, render_template, request, jsonify, send_file
import json, os, io
from datetime import datetime

app = Flask(__name__)

DATA_DIR       = os.path.join(os.path.dirname(__file__), "data")
PRODUCTOS_FILE = os.path.join(DATA_DIR, "productos.json")
INVENTARIO_FILE= os.path.join(DATA_DIR, "inventario.json")
VENTAS_FILE    = os.path.join(DATA_DIR, "ventas.json")

TALLAS = [str(t) for t in range(17, 37)]

# ── Persistencia ──────────────────────────────────────────────────────────────

def cargar(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def guardar(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_productos():  return cargar(PRODUCTOS_FILE,  [])
def get_inventario(): return cargar(INVENTARIO_FILE, [])
def get_ventas():     return cargar(VENTAS_FILE,      [])

# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

# ── API Productos ─────────────────────────────────────────────────────────────

@app.route("/api/productos", methods=["GET"])
def api_get_productos():
    return jsonify(get_productos())

@app.route("/api/productos", methods=["POST"])
def api_crear_producto():
    productos = get_productos()
    data = request.get_json()
    producto = {
        "id":        data["nombre"].strip(),
        "nombre":    data["nombre"].strip(),
        "categoria": data.get("categoria","").strip(),
        "codigo":    data.get("codigo","").strip(),
        "marca":     data.get("marca","").strip(),
        "precio":    float(data.get("precio", 0)),
        "ganancia":  float(data.get("ganancia", 0)),
    }
    if any(p["id"] == producto["id"] for p in productos):
        return jsonify({"error": "Ya existe un producto con ese nombre"}), 400
    productos.append(producto)
    guardar(PRODUCTOS_FILE, productos)
    return jsonify(producto), 201

@app.route("/api/productos/<path:pid>", methods=["PUT"])
def api_editar_producto(pid):
    productos = get_productos()
    data = request.get_json()
    for p in productos:
        if p["id"] == pid:
            p["categoria"] = data.get("categoria","").strip()
            p["codigo"]    = data.get("codigo","").strip()
            p["marca"]     = data.get("marca","").strip()
            p["precio"]    = float(data.get("precio", 0))
            p["ganancia"]  = float(data.get("ganancia", 0))
            guardar(PRODUCTOS_FILE, productos)
            return jsonify(p)
    return jsonify({"error":"Producto no encontrado"}), 404

@app.route("/api/productos/<path:pid>", methods=["DELETE"])
def api_eliminar_producto(pid):
    productos = [p for p in get_productos() if p["id"] != pid]
    guardar(PRODUCTOS_FILE, productos)
    return jsonify({"ok": True})

# ── API Inventario ────────────────────────────────────────────────────────────

@app.route("/api/inventario", methods=["GET"])
def api_get_inventario():
    return jsonify(get_inventario())

@app.route("/api/inventario", methods=["POST"])
def api_crear_item():
    inventario = get_inventario()
    data = request.get_json()
    item = {
        "codigo":      data.get("codigo","").strip(),
        "descripcion": data.get("descripcion","").strip(),
        "categoria":   data.get("categoria","").strip(),
        "tallas":      data.get("tallas", {}),
    }
    inventario.append(item)
    guardar(INVENTARIO_FILE, inventario)
    return jsonify(item), 201

@app.route("/api/inventario/<int:idx>", methods=["PUT"])
def api_editar_item(idx):
    inventario = get_inventario()
    if idx >= len(inventario):
        return jsonify({"error":"No encontrado"}), 404
    data = request.get_json()
    inventario[idx]["codigo"]      = data.get("codigo","").strip()
    inventario[idx]["descripcion"] = data.get("descripcion","").strip()
    inventario[idx]["categoria"]   = data.get("categoria","").strip()
    inventario[idx]["tallas"]      = data.get("tallas", {})
    guardar(INVENTARIO_FILE, inventario)
    return jsonify(inventario[idx])

@app.route("/api/inventario/<int:idx>", methods=["DELETE"])
def api_eliminar_item(idx):
    inventario = get_inventario()
    if idx >= len(inventario):
        return jsonify({"error":"No encontrado"}), 404
    inventario.pop(idx)
    guardar(INVENTARIO_FILE, inventario)
    return jsonify({"ok": True})

# ── API Ventas ────────────────────────────────────────────────────────────────

@app.route("/api/ventas", methods=["GET"])
def api_get_ventas():
    return jsonify(get_ventas())

@app.route("/api/ventas", methods=["POST"])
def api_registrar_venta():
    productos = get_productos()
    ventas    = get_ventas()
    data      = request.get_json()

    pid       = data["producto_id"]
    cant      = int(data["cantidad"])
    fecha     = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")

    producto  = next((p for p in productos if p["id"] == pid), None)
    if not producto:
        return jsonify({"error":"Producto no encontrado"}), 404

    nuevo_id  = max((v["id"] for v in ventas), default=0) + 1
    venta = {
        "id":             nuevo_id,
        "producto_id":    pid,
        "nombre":         producto["nombre"],
        "categoria":      producto["categoria"],
        "codigo":         producto["codigo"],
        "marca":          producto["marca"],
        "precio_unitario":producto["precio"],
        "ganancia":       producto["ganancia"],
        "cantidad":       cant,
        "total":          producto["precio"] * cant,
        "ganancia_total": producto["ganancia"] * cant,
        "fecha":          fecha,
        "hora":           datetime.now().strftime("%H:%M"),
    }
    ventas.insert(0, venta)
    guardar(VENTAS_FILE, ventas)
    return jsonify(venta), 201

@app.route("/api/ventas/<int:vid>", methods=["DELETE"])
def api_eliminar_venta(vid):
    ventas = [v for v in get_ventas() if v["id"] != vid]
    guardar(VENTAS_FILE, ventas)
    return jsonify({"ok": True})

# ── Exportar Excel ────────────────────────────────────────────────────────────

@app.route("/api/exportar/excel")
def exportar_excel():
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        return jsonify({"error":"pip install openpyxl"}), 500

    ventas    = get_ventas()
    productos = get_productos()
    wb        = Workbook()

    hf   = PatternFill("solid", start_color="1a1a18")
    hfnt = Font(bold=True, color="FFFFFF", name="Arial", size=10)
    nfnt = Font(name="Arial", size=10)
    alt  = PatternFill("solid", start_color="F5F4F0")
    bs   = Side(style="thin", color="E2E0D8")
    brd  = Border(left=bs, right=bs, top=bs, bottom=bs)
    ctr  = Alignment(horizontal="center", vertical="center")

    def set_header(ws, headers, widths, row=2):
        ws.merge_cells(f"A1:{chr(64+len(headers))}1")
        ws["A1"] = f"Exportado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        ws["A1"].font = Font(bold=True, name="Arial", size=12)
        ws["A1"].alignment = ctr
        ws.row_dimensions[1].height = 28
        for col, (h, w) in enumerate(zip(headers, widths), 1):
            c = ws.cell(row=row, column=col, value=h)
            c.font = hfnt; c.fill = hf; c.alignment = ctr; c.border = brd
            ws.column_dimensions[c.column_letter].width = w
        ws.row_dimensions[row].height = 20

    # Hoja Ventas
    ws = wb.active
    ws.title = "TABLA DE VENTAS"
    hdrs = ["Fecha","Categoría","Código","Producto","Marca","Precio unit.","Cantidad","Total","Ganancia"]
    wds  = [14,18,12,18,20,14,10,14,14]
    set_header(ws, hdrs, wds)
    total_v = ganancia_v = 0
    for i, v in enumerate(ventas):
        r = i + 3
        row_fill = alt if i % 2 == 0 else PatternFill("solid", start_color="FFFFFF")
        vals = [v["fecha"], v.get("categoria",""), v.get("codigo",""), v["nombre"],
                v.get("marca",""), v["precio_unitario"], v["cantidad"], v["total"],
                v.get("ganancia_total", v.get("ganancia",0)*v["cantidad"])]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=val)
            c.font = nfnt; c.fill = row_fill; c.border = brd; c.alignment = ctr
        total_v    += v["total"]
        ganancia_v += v.get("ganancia_total", 0)
        ws.row_dimensions[r].height = 16
    tr = len(ventas) + 3
    for col, val in enumerate(["","","","","","TOTAL","", total_v, ganancia_v], 1):
        c = ws.cell(row=tr, column=col, value=val)
        c.font = Font(bold=True, name="Arial", size=10)
        c.fill = PatternFill("solid", start_color="EAF3DE"); c.border = brd; c.alignment = ctr

    # Hoja Productos
    ws2 = wb.create_sheet("PRODUCTOS")
    hdrs2 = ["Nombre","Categoría","Código","Marca","Precio","Ganancia/par"]
    wds2  = [18,18,12,22,14,14]
    set_header(ws2, hdrs2, wds2)
    for i, p in enumerate(productos):
        r = i + 3
        row_fill = alt if i % 2 == 0 else PatternFill("solid", start_color="FFFFFF")
        for col, val in enumerate([p["nombre"],p["categoria"],p["codigo"],p["marca"],p["precio"],p["ganancia"]], 1):
            c = ws2.cell(row=r, column=col, value=val)
            c.font = nfnt; c.fill = row_fill; c.border = brd; c.alignment = ctr
        ws2.row_dimensions[r].height = 16

    # Hoja Inventario
    ws3     = wb.create_sheet("INVENTARIO")
    inv     = get_inventario()
    inv_hdrs= ["Código","Descripción","Categoría"] + [str(t) for t in range(17,37)] + ["Total pares"]
    inv_wds = [10,30,12] + [5]*20 + [10]
    set_header(ws3, inv_hdrs, inv_wds)
    for i, item in enumerate(inv):
        r = i + 3
        row_fill = alt if i % 2 == 0 else PatternFill("solid", start_color="FFFFFF")
        base = [item["codigo"], item["descripcion"], item["categoria"]]
        tallas_vals = [item["tallas"].get(str(t), None) for t in range(17,37)]
        total_pares = sum(v for v in tallas_vals if v)
        for col, val in enumerate(base + tallas_vals + [total_pares], 1):
            c = ws3.cell(row=r, column=col, value=val)
            c.font = nfnt; c.fill = row_fill; c.border = brd; c.alignment = ctr
        ws3.row_dimensions[r].height = 16

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    fname = f"ventas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=fname)

# ── Exportar PDF ──────────────────────────────────────────────────────────────

@app.route("/api/exportar/pdf")
def exportar_pdf():
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError:
        return jsonify({"error":"pip install reportlab"}), 500

    ventas = get_ventas()
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=landscape(A4),
                               topMargin=1.5*cm, bottomMargin=1.5*cm,
                               leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles  = getSampleStyleSheet()
    t_style = ParagraphStyle("t", parent=styles["Heading1"], fontSize=14, spaceAfter=4,
                              textColor=colors.HexColor("#1a1a18"))
    s_style = ParagraphStyle("s", parent=styles["Normal"], fontSize=8,
                              textColor=colors.HexColor("#6b6b67"), spaceAfter=12)
    elems   = []
    elems.append(Paragraph("Reporte de Ventas", t_style))
    elems.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_style))

    hdr = ["Fecha","Categoría","Código","Producto","Marca","Precio","Cant.","Total","Ganancia"]
    rows = [hdr]
    total_v = gan_v = 0
    for v in ventas:
        rows.append([v["fecha"], v.get("categoria",""), v.get("codigo",""), v["nombre"],
                     v.get("marca",""), f"${v['precio_unitario']:,.0f}", str(v["cantidad"]),
                     f"${v['total']:,.0f}", f"${v.get('ganancia_total',0):,.0f}"])
        total_v += v["total"]; gan_v += v.get("ganancia_total",0)
    rows.append(["","","","","","TOTAL","", f"${total_v:,.0f}", f"${gan_v:,.0f}"])

    cw  = [2.2*cm,3.2*cm,2*cm,3.5*cm,3.8*cm,2.5*cm,1.5*cm,2.5*cm,2.5*cm]
    t   = Table(rows, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), colors.HexColor("#1a1a18")),
        ("TEXTCOLOR", (0,0),(-1,0), colors.white),
        ("FONTNAME",  (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0),(-1,-1),7),
        ("ALIGN",     (0,0),(-1,-1),"CENTER"),
        ("VALIGN",    (0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.HexColor("#F5F4F0"),colors.white]),
        ("FONTNAME",  (0,1),(-1,-1),"Helvetica"),
        ("GRID",      (0,0),(-1,-1),0.4,colors.HexColor("#E2E0D8")),
        ("ROWHEIGHT", (0,0),(-1,-1),0.55*cm),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EAF3DE")),
        ("FONTNAME",  (7,-1),(8,-1),"Helvetica-Bold"),
    ]))
    elems.append(t)
    doc.build(elems)
    buf.seek(0)
    fname = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=fname)

if __name__ == "__main__":
    print("🚀 Servidor iniciado en http://127.0.0.1:5000")
    app.run(host="0.0.0.0", debug=True)
