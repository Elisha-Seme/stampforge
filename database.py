import sqlite3
import os
from config import Config


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS organization (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT 'My Organization',
            logo_path TEXT,
            primary_color TEXT DEFAULT '#1a2b5e',
            accent_color TEXT DEFAULT '#2563eb',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY,
            employee_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stamps (
            id INTEGER PRIMARY KEY,
            staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL,
            stamp_style TEXT NOT NULL,
            stamp_image_path TEXT NOT NULL,
            color TEXT,
            size TEXT DEFAULT 'medium',
            options TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            document_name TEXT,
            stamp_id INTEGER REFERENCES stamps(id) ON DELETE SET NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS e_signatures (
            id INTEGER PRIMARY KEY,
            staff_id INTEGER UNIQUE REFERENCES staff(id) ON DELETE CASCADE,
            image_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Ensure at least one organization row exists
    cursor.execute("SELECT COUNT(*) FROM organization")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO organization (name) VALUES (?)",
            ("StampForge Demo Organization",)
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Organization helpers
# ---------------------------------------------------------------------------

def get_organization():
    conn = get_db()
    org = conn.execute("SELECT * FROM organization LIMIT 1").fetchone()
    conn.close()
    return dict(org) if org else {}


def update_organization(name=None, logo_path=None, primary_color=None, accent_color=None):
    conn = get_db()
    org = conn.execute("SELECT id FROM organization LIMIT 1").fetchone()
    if not org:
        conn.execute("INSERT INTO organization (name) VALUES (?)", (name or "My Organization",))
        conn.commit()
        org = conn.execute("SELECT id FROM organization LIMIT 1").fetchone()

    fields, values = [], []
    if name is not None:
        fields.append("name = ?"); values.append(name)
    if logo_path is not None:
        fields.append("logo_path = ?"); values.append(logo_path)
    if primary_color is not None:
        fields.append("primary_color = ?"); values.append(primary_color)
    if accent_color is not None:
        fields.append("accent_color = ?"); values.append(accent_color)

    if fields:
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(org["id"])
        conn.execute(f"UPDATE organization SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Staff helpers
# ---------------------------------------------------------------------------

def generate_employee_id(full_name, department):
    """Generate a unique employee ID."""
    conn = get_db()
    initials = ''.join(w[0].upper() for w in full_name.split() if w)
    dept_code = department[:3].upper()
    base = f"{dept_code}-{initials}"
    existing = conn.execute(
        "SELECT employee_id FROM staff WHERE employee_id LIKE ? ORDER BY employee_id DESC LIMIT 1",
        (f"{base}%",)
    ).fetchone()
    if existing:
        last = existing["employee_id"]
        try:
            num = int(last.split("-")[-1]) + 1
        except ValueError:
            num = 1
        emp_id = f"{base}-{num:03d}"
    else:
        emp_id = f"{base}-001"
    conn.close()
    return emp_id


def get_all_staff(search=None, department=None, active_only=True):
    conn = get_db()
    query = "SELECT * FROM staff WHERE 1=1"
    params = []
    if active_only:
        query += " AND is_active = 1"
    if search:
        query += " AND (full_name LIKE ? OR employee_id LIKE ? OR email LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
    if department:
        query += " AND department = ?"
        params.append(department)
    query += " ORDER BY full_name ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_staff_by_id(staff_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_staff(employee_id, full_name, job_title, department, email=None, phone=None):
    conn = get_db()
    conn.execute(
        """INSERT INTO staff (employee_id, full_name, job_title, department, email, phone)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (employee_id, full_name, job_title, department, email, phone)
    )
    conn.commit()
    staff_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return staff_id


def update_staff(staff_id, **kwargs):
    allowed = {'full_name', 'job_title', 'department', 'email', 'phone', 'is_active', 'employee_id'}
    fields, values = [], []
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(staff_id)
    conn = get_db()
    conn.execute(f"UPDATE staff SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_staff(staff_id):
    conn = get_db()
    conn.execute("UPDATE staff SET is_active = 0 WHERE id = ?", (staff_id,))
    conn.commit()
    conn.close()


def get_departments():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT department FROM staff WHERE is_active = 1 ORDER BY department"
    ).fetchall()
    conn.close()
    return [r["department"] for r in rows]


# ---------------------------------------------------------------------------
# Stamp helpers
# ---------------------------------------------------------------------------

def save_stamp(staff_id, stamp_style, stamp_image_path, color=None, size='medium', options=None):
    import json
    conn = get_db()
    opts = json.dumps(options) if options else None
    conn.execute(
        """INSERT INTO stamps (staff_id, stamp_style, stamp_image_path, color, size, options)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (staff_id, stamp_style, stamp_image_path, color, size, opts)
    )
    conn.commit()
    stamp_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return stamp_id


def get_stamps_for_staff(staff_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM stamps WHERE staff_id = ? ORDER BY created_at DESC",
        (staff_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit log helpers
# ---------------------------------------------------------------------------

def log_action(action, staff_id=None, document_name=None, stamp_id=None, details=None):
    conn = get_db()
    conn.execute(
        """INSERT INTO audit_log (staff_id, action, document_name, stamp_id, details)
           VALUES (?, ?, ?, ?, ?)""",
        (staff_id, action, document_name, stamp_id, details)
    )
    conn.commit()
    conn.close()


def get_audit_log(search=None, limit=100, offset=0):
    conn = get_db()
    query = """
        SELECT al.*, s.full_name as staff_name, s.department
        FROM audit_log al
        LEFT JOIN staff s ON al.staff_id = s.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (al.action LIKE ? OR al.document_name LIKE ? OR s.full_name LIKE ?)"
        sq = f"%{search}%"
        params.extend([sq, sq, sq])
    query += " ORDER BY al.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dashboard_stats():
    conn = get_db()
    stats = {}
    stats['total_staff'] = conn.execute(
        "SELECT COUNT(*) FROM staff WHERE is_active = 1"
    ).fetchone()[0]
    stats['total_stamps'] = conn.execute(
        "SELECT COUNT(*) FROM stamps"
    ).fetchone()[0]
    stats['total_pdfs_stamped'] = conn.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action = 'PDF_STAMPED'"
    ).fetchone()[0]
    stats['recent_activity'] = [dict(r) for r in conn.execute(
        """SELECT al.*, s.full_name as staff_name
           FROM audit_log al
           LEFT JOIN staff s ON al.staff_id = s.id
           ORDER BY al.created_at DESC LIMIT 10"""
    ).fetchall()]
    stats['departments'] = conn.execute(
        """SELECT department, COUNT(*) as count
           FROM staff WHERE is_active = 1 GROUP BY department ORDER BY count DESC"""
    ).fetchall()
    stats['departments'] = [dict(r) for r in stats['departments']]
    conn.close()
    return stats


# ---------------------------------------------------------------------------
# E-Signature helpers
# ---------------------------------------------------------------------------

def save_e_signature(staff_id, image_path):
    """Upsert a drawn e-signature for a staff member."""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM e_signatures WHERE staff_id = ?", (staff_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE e_signatures SET image_path = ?, updated_at = CURRENT_TIMESTAMP WHERE staff_id = ?",
            (image_path, staff_id)
        )
    else:
        conn.execute(
            "INSERT INTO e_signatures (staff_id, image_path) VALUES (?, ?)",
            (staff_id, image_path)
        )
    conn.commit()
    conn.close()


def get_e_signature(staff_id):
    """Return the e-signature record for a staff member, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM e_signatures WHERE staff_id = ?", (staff_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_e_signature(staff_id):
    conn = get_db()
    conn.execute("DELETE FROM e_signatures WHERE staff_id = ?", (staff_id,))
    conn.commit()
    conn.close()


def get_all_e_signatures():
    """Return all staff members with their signature status."""
    conn = get_db()
    rows = conn.execute(
        """SELECT s.id, s.employee_id, s.full_name, s.job_title, s.department,
                  es.image_path, es.updated_at as sig_updated_at
           FROM staff s
           LEFT JOIN e_signatures es ON s.id = es.staff_id
           WHERE s.is_active = 1
           ORDER BY s.full_name ASC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_sample_data():
    """Insert demo staff and audit entries if no staff exist."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    conn.close()
    if count > 0:
        return  # Already seeded

    sample_staff = [
        ("CEO-JD-001",  "Jane Doe",       "Chief Executive Officer", "Executive",   "jane.doe@example.com",    "555-0101"),
        ("ENG-JS-001",  "John Smith",      "Senior Engineer",         "Engineering", "john.smith@example.com",  "555-0102"),
        ("MKT-EJ-001",  "Emily Johnson",   "Marketing Manager",       "Marketing",   "emily.j@example.com",     "555-0103"),
        ("FIN-MB-001",  "Michael Brown",   "Financial Analyst",       "Finance",     "m.brown@example.com",     "555-0104"),
        ("ENG-SW-001",  "Sarah Williams",  "Software Developer",      "Engineering", "s.williams@example.com",  "555-0105"),
        ("HR-DL-001",   "David Lee",       "HR Specialist",           "HR",          "d.lee@example.com",       "555-0106"),
        ("MKT-LT-001",  "Lisa Taylor",     "Content Writer",          "Marketing",   "l.taylor@example.com",    "555-0107"),
        ("FIN-RA-001",  "Robert Anderson", "Accountant",              "Finance",     "r.anderson@example.com",  "555-0108"),
    ]
    for s in sample_staff:
        add_staff(*s)

    log_action("STAMP_GENERATED", staff_id=1, details="Style A - Circular Seal (demo)")
    log_action("STAMP_GENERATED", staff_id=2, details="Style B - Approval Stamp (demo)")
    log_action("PDF_STAMPED",     staff_id=1, document_name="contract_q1.pdf", details="Bottom-right, page 1 (demo)")
