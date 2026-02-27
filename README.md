# StampForge

A full-stack web application for generating, managing, and applying digital e-stamps and e-signatures for organizations and their staff.

## Features

- **Staff Management** — Add, edit, delete staff with CSV bulk import
- **4 Stamp Styles** — Circular Seal (A), Approval Stamp (B), Signature (C), QR-Verified (D)
- **PDF Stamping** — Apply stamps to any PDF with flexible placement options
- **Batch Generation** — Generate stamps for multiple staff at once, download as ZIP
- **Audit Log** — Full searchable history of all stamp and PDF actions
- **Organization Settings** — Upload logo, set colors, configure org name

---

## Quick Setup

### 1. Prerequisites

- Python 3.10 or higher
- pip

### 2. Create a virtual environment

```bash
cd stampforge
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note on PyMuPDF**: If `pip install PyMuPDF` fails, try:
> ```bash
> pip install pymupdf
> ```

### 4. Run the application

```bash
python app.py
```

The app starts at **http://localhost:5000**

The database is created automatically with sample data on first run.

---

## Project Structure

```
stampforge/
├── app.py                  # Flask application & all API routes
├── config.py               # Configuration (paths, sizes, DPI)
├── database.py             # SQLite helpers & ORM-lite layer
├── stamp_generator.py      # Pillow-based stamp generation (4 styles)
├── pdf_stamper.py          # PyMuPDF PDF manipulation
├── requirements.txt
├── README.md
├── static/
│   ├── css/style.css       # All styles
│   ├── js/app.js           # All frontend JavaScript
│   ├── fonts/              # Optional custom fonts (see below)
│   ├── uploads/            # Uploaded PDFs and logo
│   └── generated/          # Generated stamp PNGs
└── templates/
    ├── base.html           # Sidebar layout
    ├── dashboard.html
    ├── staff.html
    ├── generate.html
    ├── stamp_pdf.html
    ├── audit_log.html
    ├── settings.html
    └── verify.html
```

---

## Adding Custom Fonts (Recommended)

For better-looking stamps, place TrueType fonts in `static/fonts/`:

| File | Use |
|------|-----|
| `DejaVuSans.ttf` | Regular text on all stamps |
| `DejaVuSans-Bold.ttf` | Bold text |
| `GreatVibes-Regular.ttf` | Style C signature effect |

Download from [Google Fonts](https://fonts.google.com/) or use system fonts — the app falls back gracefully.

---

## CSV Import Format

The CSV importer accepts the following columns (header row required):

| Column | Required | Description |
|--------|----------|-------------|
| `full_name` | ✅ | Staff member's full name |
| `job_title` | ✅ | Job title |
| `department` | ✅ | Department name |
| `email` | optional | Email address |
| `phone` | optional | Phone number |
| `employee_id` | optional | Custom ID (auto-generated if blank) |

**Example CSV:**
```csv
full_name,job_title,department,email,phone
Alice Martin,CTO,Engineering,alice@example.com,555-0201
Bob Chen,Designer,Creative,bob@example.com,
Carol White,Accountant,Finance,,555-0203
```

---

## Stamp Styles

### Style A — Circular Seal
High-resolution circular seal with the organization name arced at the top, department at the bottom, staff name and title in the center. Optional logo in the center.

### Style B — Rectangular Approval Stamp
Rounded rectangle with status labels: **APPROVED**, **REJECTED**, **REVIEWED**, or **PENDING**. Color-coded by status.

### Style C — Signature Style
Handwriting-style rendering of the staff name with a signature line underneath and title/date below.

### Style D — QR-Verified Stamp
Circular stamp with an embedded QR code that encodes a verification URL with staff ID, stamp ID, and timestamp.

---

## API Reference

### Staff

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/staff` | List all staff (supports `?search=`, `?department=`, `?active=`) |
| POST | `/api/staff` | Add a staff member |
| GET | `/api/staff/<id>` | Get a single staff member |
| PUT | `/api/staff/<id>` | Update a staff member |
| DELETE | `/api/staff/<id>` | Soft-delete (deactivate) a staff member |
| POST | `/api/staff/import-csv` | Bulk import from CSV file |

### Stamps

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/stamps/generate` | Generate a stamp image |
| POST | `/api/stamps/batch` | Batch generate stamps (returns ZIP) |
| GET | `/api/stamps/<staff_id>` | List stamps for a staff member |

### PDF

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/pdf/upload` | Upload a PDF |
| POST | `/api/pdf/stamp` | Apply stamp to uploaded PDF |
| POST | `/api/pdf/preview` | Render a PDF page to PNG |

### Audit & Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/audit-log` | Get audit log entries |
| GET | `/api/audit-log/export` | Download audit log as CSV |
| POST | `/api/settings/org` | Update organization name/colors |
| POST | `/api/settings/logo` | Upload organization logo |

---

## Configuration

Edit `config.py` to change:

- `STAMP_DPI` — Output resolution (default 300 DPI)
- `STAMP_SIZES` — Pixel dimensions per size tier
- `VERIFICATION_BASE_URL` — Base URL for QR code verification links
- `MAX_CONTENT_LENGTH` — Max upload size (default 16 MB)

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'fitz'`**
```bash
pip install pymupdf
```

**`ModuleNotFoundError: No module named 'qrcode'`**
```bash
pip install "qrcode[pil]"
```

**Stamps look blurry**
Place TrueType font files in `static/fonts/` (see above).

**PDF preview not working**
PyMuPDF must be installed. Check with `python -c "import fitz; print(fitz.__version__)"`.

---

## License

MIT — use freely for internal organizational tools.
