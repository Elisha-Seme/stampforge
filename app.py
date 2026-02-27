"""
app.py — StampForge Flask Application
"""

import os
import csv
import io
import json
import base64
import zipfile
import datetime
from functools import wraps

from flask import (Flask, render_template, request, jsonify, send_file,
                   redirect, url_for, abort)
from werkzeug.utils import secure_filename

import database as db
from database import get_all_e_signatures  # convenience alias used in page route
from stamp_generator import generate_stamp
from pdf_stamper import stamp_pdf, get_pdf_info, generate_pdf_preview
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Ensure storage directories exist
os.makedirs(Config.UPLOAD_FOLDER,    exist_ok=True)
os.makedirs(Config.GENERATED_FOLDER, exist_ok=True)
os.makedirs(Config.FONTS_FOLDER,     exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


def _abs_static(rel_path):
    """Convert a static-relative path to an absolute filesystem path."""
    return os.path.join(app.root_path, "static", rel_path.lstrip("/\\"))


def api_error(msg, code=400):
    return jsonify({"success": False, "error": msg}), code


def api_ok(data=None, msg="OK"):
    payload = {"success": True, "message": msg}
    if data is not None:
        payload["data"] = data
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    stats = db.get_dashboard_stats()
    org   = db.get_organization()
    return render_template("dashboard.html", stats=stats, org=org)


@app.route("/staff")
def staff_page():
    org = db.get_organization()
    return render_template("staff.html", org=org)


@app.route("/generate")
def generate_page():
    org   = db.get_organization()
    staff = db.get_all_staff()
    return render_template("generate.html", org=org, staff_list=staff)


@app.route("/stamp-pdf")
def stamp_pdf_page():
    org   = db.get_organization()
    staff = db.get_all_staff()
    return render_template("stamp_pdf.html", org=org, staff_list=staff)


@app.route("/e-signatures")
def e_signatures_page():
    org   = db.get_organization()
    staff = get_all_e_signatures()
    return render_template("e_signatures.html", org=org, staff_list=staff)


@app.route("/audit-log")
def audit_log_page():
    org = db.get_organization()
    return render_template("audit_log.html", org=org)


@app.route("/settings")
def settings_page():
    org = db.get_organization()
    return render_template("settings.html", org=org)


@app.route("/verify")
def verify_stamp():
    """Simple verification endpoint for QR codes."""
    stamp_id = request.args.get("id", "")
    staff_id = request.args.get("staff", "")
    ts       = request.args.get("ts", "")
    org      = db.get_organization()
    return render_template("verify.html", stamp_id=stamp_id,
                           staff_id=staff_id, ts=ts, org=org)


# ---------------------------------------------------------------------------
# Staff API
# ---------------------------------------------------------------------------

@app.route("/api/staff", methods=["GET"])
def api_get_staff():
    search = request.args.get("search", "").strip()
    dept   = request.args.get("department", "").strip()
    active = request.args.get("active", "1") != "0"
    staff  = db.get_all_staff(
        search=search or None,
        department=dept or None,
        active_only=active
    )
    depts  = db.get_departments()
    return api_ok({"staff": staff, "departments": depts, "total": len(staff)})


@app.route("/api/staff", methods=["POST"])
def api_add_staff():
    data = request.get_json(force=True)
    full_name  = (data.get("full_name", "") or "").strip()
    job_title  = (data.get("job_title", "") or "").strip()
    department = (data.get("department", "") or "").strip()
    email      = (data.get("email", "") or "").strip() or None
    phone      = (data.get("phone", "") or "").strip() or None
    emp_id     = (data.get("employee_id", "") or "").strip()

    if not full_name:
        return api_error("Full name is required")
    if not job_title:
        return api_error("Job title is required")
    if not department:
        return api_error("Department is required")

    if not emp_id:
        emp_id = db.generate_employee_id(full_name, department)

    try:
        staff_id = db.add_staff(emp_id, full_name, job_title, department, email, phone)
        db.log_action("STAFF_ADDED", staff_id=staff_id,
                      details=f"Added staff: {full_name} ({emp_id})")
        return api_ok({"id": staff_id, "employee_id": emp_id}, msg="Staff member added")
    except Exception as e:
        return api_error(f"Could not add staff: {e}")


@app.route("/api/staff/<int:staff_id>", methods=["GET"])
def api_get_staff_member(staff_id):
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)
    return api_ok(member)


@app.route("/api/staff/<int:staff_id>", methods=["PUT"])
def api_update_staff(staff_id):
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)
    data = request.get_json(force=True)
    allowed = {"full_name", "job_title", "department", "email", "phone",
               "employee_id", "is_active"}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    try:
        db.update_staff(staff_id, **kwargs)
        db.log_action("STAFF_UPDATED", staff_id=staff_id,
                      details=f"Updated fields: {list(kwargs.keys())}")
        return api_ok(msg="Staff member updated")
    except Exception as e:
        return api_error(f"Could not update staff: {e}")


@app.route("/api/staff/<int:staff_id>", methods=["DELETE"])
def api_delete_staff(staff_id):
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)
    db.delete_staff(staff_id)
    db.log_action("STAFF_DELETED", staff_id=staff_id,
                  details=f"Soft-deleted: {member['full_name']}")
    return api_ok(msg="Staff member removed")


@app.route("/api/staff/import-csv", methods=["POST"])
def api_import_csv():
    if "file" not in request.files:
        return api_error("No file provided")
    f = request.files["file"]
    if not f.filename or not allowed_file(f.filename, Config.ALLOWED_CSV_EXTENSIONS):
        return api_error("Please upload a CSV file")

    content  = f.read().decode("utf-8-sig")
    reader   = csv.DictReader(io.StringIO(content))
    imported = 0
    errors   = []

    for i, row in enumerate(reader, start=2):
        full_name  = (row.get("full_name") or row.get("Full Name") or "").strip()
        job_title  = (row.get("job_title") or row.get("Job Title") or "").strip()
        department = (row.get("department") or row.get("Department") or "").strip()
        email      = (row.get("email") or row.get("Email") or "").strip() or None
        phone      = (row.get("phone") or row.get("Phone") or "").strip() or None
        emp_id     = (row.get("employee_id") or row.get("Employee ID") or "").strip()

        if not full_name or not job_title or not department:
            errors.append(f"Row {i}: missing required fields")
            continue

        if not emp_id:
            emp_id = db.generate_employee_id(full_name, department)

        try:
            sid = db.add_staff(emp_id, full_name, job_title, department, email, phone)
            db.log_action("STAFF_IMPORTED", staff_id=sid,
                          details=f"CSV import: {full_name}")
            imported += 1
        except Exception as e:
            errors.append(f"Row {i} ({full_name}): {e}")

    return api_ok({"imported": imported, "errors": errors},
                  msg=f"Imported {imported} staff member(s)")


# ---------------------------------------------------------------------------
# Stamp generation API
# ---------------------------------------------------------------------------

@app.route("/api/stamps/generate", methods=["POST"])
def api_generate_stamp():
    data     = request.get_json(force=True)
    staff_id = data.get("staff_id")
    style    = str(data.get("style", "A")).upper()
    color    = data.get("color")
    size     = data.get("size", "medium")
    options  = data.get("options", {})

    if not staff_id:
        return api_error("staff_id is required")

    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)

    org = db.get_organization()

    try:
        rel_path = generate_stamp(member, org, style=style, color=color,
                                  size=size, options=options)
        stamp_id = db.save_stamp(staff_id, f"Style {style}", rel_path,
                                 color=color, size=size, options=options)
        db.log_action("STAMP_GENERATED", staff_id=staff_id, stamp_id=stamp_id,
                      details=f"Style {style}, size={size}, color={color}")
        return api_ok({
            "stamp_id":  stamp_id,
            "image_url": f"/static/{rel_path}",
            "style":     style,
        }, msg="Stamp generated successfully")
    except Exception as e:
        return api_error(f"Stamp generation failed: {e}")


@app.route("/api/stamps/batch", methods=["POST"])
def api_batch_stamps():
    data      = request.get_json(force=True)
    staff_ids = data.get("staff_ids", [])
    style     = str(data.get("style", "A")).upper()
    color     = data.get("color")
    size      = data.get("size", "medium")
    options   = data.get("options", {})

    if not staff_ids:
        return api_error("staff_ids is required")

    org = db.get_organization()

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    results    = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for sid in staff_ids:
            member = db.get_staff_by_id(sid)
            if not member:
                results.append({"staff_id": sid, "error": "Not found"})
                continue
            try:
                rel_path = generate_stamp(member, org, style=style,
                                          color=color, size=size, options=options)
                stamp_id = db.save_stamp(sid, f"Style {style}", rel_path,
                                         color=color, size=size, options=options)
                db.log_action("STAMP_GENERATED", staff_id=sid, stamp_id=stamp_id,
                              details=f"Batch: Style {style}")
                abs_path = _abs_static(rel_path)
                safe_name = secure_filename(
                    f"{member['employee_id']}_{member['full_name']}_style{style}.png"
                )
                zf.write(abs_path, safe_name)
                results.append({"staff_id": sid, "name": member["full_name"],
                                 "file": safe_name})
            except Exception as e:
                results.append({"staff_id": sid, "error": str(e)})

    zip_buffer.seek(0)
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"stamps_batch_{ts}.zip"

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name
    )


@app.route("/api/stamps/<int:staff_id>", methods=["GET"])
def api_get_stamps(staff_id):
    stamps = db.get_stamps_for_staff(staff_id)
    return api_ok({"stamps": stamps})


# ---------------------------------------------------------------------------
# PDF stamping API
# ---------------------------------------------------------------------------

@app.route("/api/pdf/upload", methods=["POST"])
def api_upload_pdf():
    if "file" not in request.files:
        return api_error("No file provided")
    f = request.files["file"]
    if not f.filename or not allowed_file(f.filename, Config.ALLOWED_PDF_EXTENSIONS):
        return api_error("Please upload a PDF file")

    filename = secure_filename(f.filename)
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    saved    = f"{ts}_{filename}"
    abs_path = os.path.join(Config.UPLOAD_FOLDER, saved)
    f.save(abs_path)

    info     = get_pdf_info(abs_path)
    rel_path = f"uploads/{saved}"

    return api_ok({
        "file_path": rel_path,
        "filename":  filename,
        "info":      info,
    }, msg="PDF uploaded")


@app.route("/api/pdf/stamp", methods=["POST"])
def api_stamp_pdf():
    data      = request.get_json(force=True)
    staff_id  = data.get("staff_id")
    style     = str(data.get("style", "A")).upper()
    color     = data.get("color")
    size      = data.get("size", "medium")
    options   = data.get("options", {})
    pdf_path  = data.get("pdf_path", "")  # relative from static/
    placement = data.get("placement", "bottom-right")
    pages     = data.get("pages", "all")
    opacity   = float(data.get("opacity", 0.85))
    stamp_w   = float(data.get("stamp_width", 120))
    custom_x  = data.get("custom_x")
    custom_y  = data.get("custom_y")

    if not staff_id:
        return api_error("staff_id is required")
    if not pdf_path:
        return api_error("pdf_path is required")

    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)

    org = db.get_organization()

    # Generate stamp
    try:
        stamp_rel = generate_stamp(member, org, style=style, color=color,
                                   size=size, options=options)
        stamp_id  = db.save_stamp(staff_id, f"Style {style}", stamp_rel,
                                   color=color, size=size, options=options)
    except Exception as e:
        return api_error(f"Stamp generation failed: {e}")

    # Apply to PDF
    abs_pdf   = _abs_static(pdf_path)
    abs_stamp = _abs_static(stamp_rel)

    if not os.path.exists(abs_pdf):
        return api_error("PDF file not found")
    if not os.path.exists(abs_stamp):
        return api_error("Stamp image not found")

    try:
        out_rel = stamp_pdf(
            abs_pdf, abs_stamp,
            placement=placement, pages=pages,
            opacity=opacity, stamp_width_pt=stamp_w,
            custom_x=custom_x, custom_y=custom_y
        )
        doc_name = os.path.basename(pdf_path)
        db.log_action("PDF_STAMPED", staff_id=staff_id, stamp_id=stamp_id,
                      document_name=doc_name,
                      details=f"placement={placement}, pages={pages}, style={style}")
        return api_ok({
            "output_url": f"/static/{out_rel}",
            "stamp_url":  f"/static/{stamp_rel}",
        }, msg="PDF stamped successfully")
    except Exception as e:
        return api_error(f"PDF stamping failed: {e}")


@app.route("/api/pdf/preview", methods=["POST"])
def api_pdf_preview():
    data     = request.get_json(force=True)
    pdf_path = data.get("pdf_path", "")
    page     = int(data.get("page", 0))

    abs_pdf  = _abs_static(pdf_path)
    if not os.path.exists(abs_pdf):
        return api_error("PDF not found", 404)

    try:
        rel = generate_pdf_preview(abs_pdf, page=page)
        return api_ok({"preview_url": f"/static/{rel}"})
    except Exception as e:
        return api_error(str(e))


# ---------------------------------------------------------------------------
# E-Signature API
# ---------------------------------------------------------------------------

@app.route("/api/e-signature/<int:staff_id>", methods=["GET"])
def api_get_e_signature(staff_id):
    """Return the e-signature record for a staff member."""
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)
    sig = db.get_e_signature(staff_id)
    if not sig:
        return api_ok({"signature": None})
    sig["image_url"] = f"/static/{sig['image_path']}"
    return api_ok({"signature": sig})


@app.route("/api/e-signature/<int:staff_id>", methods=["POST"])
def api_save_e_signature(staff_id):
    """
    Accept a base64-encoded PNG from the canvas pad and save it to disk.
    Body: { "image_data": "data:image/png;base64,..." }
    """
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)

    data       = request.get_json(force=True)
    image_data = data.get("image_data", "")

    if not image_data:
        return api_error("No image data provided")

    # Strip the data-URI prefix
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        raw = base64.b64decode(image_data)
    except Exception:
        return api_error("Invalid base64 image data")

    # Validate it's a real PNG via Pillow and optionally trim whitespace
    try:
        from PIL import Image as PILImage
        import io as _io
        pil_img = PILImage.open(_io.BytesIO(raw)).convert("RGBA")

        # Auto-crop transparent/white borders to keep only the ink
        bbox = pil_img.getbbox()
        if bbox:
            pad_px = 20
            x0 = max(0, bbox[0] - pad_px)
            y0 = max(0, bbox[1] - pad_px)
            x1 = min(pil_img.width,  bbox[2] + pad_px)
            y1 = min(pil_img.height, bbox[3] + pad_px)
            pil_img = pil_img.crop((x0, y0, x1, y1))

        out_buf = _io.BytesIO()
        pil_img.save(out_buf, "PNG", dpi=(300, 300))
        raw = out_buf.getvalue()
    except Exception as e:
        return api_error(f"Invalid image: {e}")

    # Save file
    _ensure_sig_dir()
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sig_{staff_id}_{ts}.png"
    abs_path = os.path.join(Config.GENERATED_FOLDER, filename)
    with open(abs_path, "wb") as f:
        f.write(raw)

    rel_path = f"generated/{filename}"
    db.save_e_signature(staff_id, rel_path)
    db.log_action("SIGNATURE_SAVED", staff_id=staff_id,
                  details=f"E-signature saved for {member['full_name']}")

    return api_ok({
        "image_url":  f"/static/{rel_path}",
        "image_path": rel_path,
    }, msg="Signature saved")


@app.route("/api/e-signature/<int:staff_id>", methods=["DELETE"])
def api_delete_e_signature(staff_id):
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)
    db.delete_e_signature(staff_id)
    db.log_action("SIGNATURE_DELETED", staff_id=staff_id,
                  details=f"E-signature removed for {member['full_name']}")
    return api_ok(msg="Signature deleted")


@app.route("/api/e-signature/<int:staff_id>/apply-pdf", methods=["POST"])
def api_apply_signature_pdf(staff_id):
    """
    Apply the staff member's drawn e-signature directly to a PDF
    (without any stamp border — just the raw signature image).
    """
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)

    sig = db.get_e_signature(staff_id)
    if not sig:
        return api_error("No saved signature for this staff member. Please draw and save one first.")

    data      = request.get_json(force=True)
    pdf_path  = data.get("pdf_path", "")
    placement = data.get("placement", "bottom-right")
    pages     = data.get("pages", "all")
    stamp_w   = float(data.get("stamp_width", 100))
    custom_x  = data.get("custom_x")
    custom_y  = data.get("custom_y")

    if not pdf_path:
        return api_error("pdf_path is required")

    abs_pdf = _abs_static(pdf_path)
    abs_sig = _abs_static(sig["image_path"])

    if not os.path.exists(abs_pdf):
        return api_error("PDF file not found")
    if not os.path.exists(abs_sig):
        return api_error("Signature image not found")

    try:
        out_rel = stamp_pdf(
            abs_pdf, abs_sig,
            placement=placement, pages=pages,
            opacity=1.0, stamp_width_pt=stamp_w,
            custom_x=custom_x, custom_y=custom_y
        )
        db.log_action("SIGNATURE_APPLIED_PDF", staff_id=staff_id,
                      document_name=os.path.basename(pdf_path),
                      details=f"placement={placement}, pages={pages}")
        return api_ok({"output_url": f"/static/{out_rel}"}, msg="Signature applied to PDF")
    except Exception as e:
        return api_error(f"PDF signing failed: {e}")


@app.route("/api/e-signature/<int:staff_id>/stamp", methods=["POST"])
def api_signature_as_stamp(staff_id):
    """
    Generate a Style C stamp that composites the drawn e-signature,
    returning the stamp image URL (does not write to a PDF).
    """
    member = db.get_staff_by_id(staff_id)
    if not member:
        return api_error("Staff member not found", 404)

    sig = db.get_e_signature(staff_id)
    org = db.get_organization()

    data    = request.get_json(force=True) or {}
    color   = data.get("color", "#1a2b5e")
    size    = data.get("size",  "medium")
    options = data.get("options", {})

    if sig:
        options["signature_image_path"] = sig["image_path"]

    try:
        rel_path = generate_stamp(member, org, style="C", color=color,
                                  size=size, options=options)
        stamp_id = db.save_stamp(staff_id, "Style C (E-Sig)", rel_path,
                                  color=color, size=size, options=options)
        db.log_action("STAMP_GENERATED", staff_id=staff_id, stamp_id=stamp_id,
                      details="Style C with drawn e-signature")
        return api_ok({
            "stamp_id":  stamp_id,
            "image_url": f"/static/{rel_path}",
        }, msg="Signature stamp generated")
    except Exception as e:
        return api_error(f"Stamp generation failed: {e}")


def _ensure_sig_dir():
    os.makedirs(Config.GENERATED_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Audit log API
# ---------------------------------------------------------------------------

@app.route("/api/audit-log", methods=["GET"])
def api_audit_log():
    search = request.args.get("search", "").strip() or None
    limit  = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    rows   = db.get_audit_log(search=search, limit=limit, offset=offset)
    return api_ok({"entries": rows, "count": len(rows)})


@app.route("/api/audit-log/export", methods=["GET"])
def api_export_audit():
    rows = db.get_audit_log(limit=10000)
    buf  = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Action", "Staff Name", "Department",
                     "Document", "Stamp ID", "Details", "Timestamp"])
    for r in rows:
        writer.writerow([
            r["id"], r["action"], r.get("staff_name", ""),
            r.get("department", ""), r.get("document_name", ""),
            r.get("stamp_id", ""), r.get("details", ""),
            r["created_at"]
        ])
    buf.seek(0)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"audit_log_{ts}.csv"
    )


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

@app.route("/api/settings/org", methods=["POST"])
def api_settings_org():
    data = request.get_json(force=True)
    name          = data.get("name", "").strip() or None
    primary_color = data.get("primary_color", "").strip() or None
    accent_color  = data.get("accent_color", "").strip() or None
    db.update_organization(name=name, primary_color=primary_color,
                           accent_color=accent_color)
    db.log_action("SETTINGS_UPDATED", details="Organization settings updated")
    return api_ok(msg="Settings saved")


@app.route("/api/settings/logo", methods=["POST"])
def api_settings_logo():
    if "file" not in request.files:
        return api_error("No file provided")
    f = request.files["file"]
    if not f.filename or not allowed_file(f.filename, Config.ALLOWED_LOGO_EXTENSIONS):
        return api_error("Invalid file type. Use PNG, JPG, GIF or WEBP.")

    filename = secure_filename(f.filename)
    ext      = filename.rsplit(".", 1)[1].lower()
    saved    = f"logo.{ext}"
    abs_path = os.path.join(Config.UPLOAD_FOLDER, saved)
    f.save(abs_path)

    rel_path = f"uploads/{saved}"
    db.update_organization(logo_path=rel_path)
    db.log_action("LOGO_UPDATED", details=f"Logo uploaded: {saved}")
    return api_ok({"logo_url": f"/static/{rel_path}"}, msg="Logo updated")


# ---------------------------------------------------------------------------
# Serve generated / uploaded files (Flask static serves automatically, but
# we expose a download route for stamped PDFs)
# ---------------------------------------------------------------------------

@app.route("/download/<path:filename>")
def download_file(filename):
    safe = secure_filename(os.path.basename(filename))
    directory = Config.UPLOAD_FOLDER
    path = os.path.join(directory, safe)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()
    db.add_sample_data()
    app.run(debug=True, host="0.0.0.0", port=5000)
