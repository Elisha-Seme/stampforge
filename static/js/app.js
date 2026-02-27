/* =========================================================
   StampForge — app.js
   Frontend logic for all pages
   ========================================================= */

"use strict";

/* ---- Global state ---- */
const SF = {
  selectedSize:      "medium",
  selectedStyle:     "A",
  selectedColor:     null,
  selectedPlacement: "bottom-right",
  selectedPages:     "all",
  pdfPath:           null,
  pdfTotalPages:     1,
  pdfCurrentPage:    0,
  csvFile:           null,
};

/* =========================================================
   Toast notifications
   ========================================================= */
function toast(msg, type = "info") {
  const icons = { success: "fa-circle-check", error: "fa-circle-xmark",
                  warning: "fa-triangle-exclamation", info: "fa-circle-info" };
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${msg}</span>`;
  document.getElementById("toastContainer").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

/* =========================================================
   API helpers
   ========================================================= */
async function apiFetch(url, opts = {}) {
  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...opts.headers },
      ...opts,
    });
    const json = await res.json();
    return json;
  } catch (e) {
    return { success: false, error: e.message };
  }
}

/* =========================================================
   SIDEBAR TOGGLE
   ========================================================= */
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("sidebarToggle");
  const sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
  }

  // Style card radio clicks
  document.querySelectorAll(".style-card").forEach(card => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".style-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      card.querySelector("input[type=radio]").checked = true;
      SF.selectedStyle = card.dataset.style;
      renderColorOptions(SF.selectedStyle);
    });
  });
});

/* =========================================================
   STAFF PAGE
   ========================================================= */
function loadStaff() {
  const search = (document.getElementById("staffSearch") || {}).value || "";
  const dept   = (document.getElementById("deptFilter")  || {}).value || "";
  const active = !(document.getElementById("showInactive") || {}).checked;

  fetch(`/api/staff?search=${encodeURIComponent(search)}&department=${encodeURIComponent(dept)}&active=${active ? 1 : 0}`)
    .then(r => r.json())
    .then(json => {
      if (!json.success) { toast(json.error || "Failed to load staff", "error"); return; }
      renderStaffTable(json.data.staff);
      renderDeptFilter(json.data.departments);
      const countEl = document.getElementById("staffCount");
      if (countEl) countEl.textContent = json.data.total;
    });
}

function filterStaff() { loadStaff(); }

function renderStaffTable(staff) {
  const wrap = document.getElementById("staffTableWrap");
  if (!wrap) return;
  if (!staff.length) {
    wrap.innerHTML = '<p class="empty-state">No staff members found. Add one using the button above.</p>';
    return;
  }
  wrap.innerHTML = `
    <table class="data-table">
      <thead><tr>
        <th>Employee ID</th><th>Name</th><th>Title</th>
        <th>Department</th><th>Email</th><th>Status</th><th>Actions</th>
      </tr></thead>
      <tbody>${staff.map(s => `
        <tr>
          <td><code>${s.employee_id}</code></td>
          <td><strong>${esc(s.full_name)}</strong></td>
          <td>${esc(s.job_title)}</td>
          <td>${esc(s.department)}</td>
          <td>${s.email ? `<a href="mailto:${esc(s.email)}">${esc(s.email)}</a>` : '—'}</td>
          <td><span class="${s.is_active ? 'status-active' : 'status-inactive'}">
            ${s.is_active ? '● Active' : '○ Inactive'}
          </span></td>
          <td><div class="action-cell">
            <button class="btn btn-sm btn-ghost" onclick="openEditStaff(${s.id})" title="Edit">
              <i class="fa-solid fa-pen"></i>
            </button>
            <a href="/generate?staff=${s.id}" class="btn btn-sm btn-ghost" title="Generate stamp">
              <i class="fa-solid fa-stamp"></i>
            </a>
            <button class="btn btn-sm btn-ghost" onclick="deleteStaff(${s.id}, '${esc(s.full_name)}')" title="Delete">
              <i class="fa-solid fa-trash" style="color:var(--red)"></i>
            </button>
          </div></td>
        </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderDeptFilter(depts) {
  const sel = document.getElementById("deptFilter");
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">All Departments</option>' +
    depts.map(d => `<option value="${esc(d)}" ${d === current ? 'selected' : ''}>${esc(d)}</option>`).join("");

  // Also populate datalist in modal
  const dl = document.getElementById("deptSuggestions");
  if (dl) dl.innerHTML = depts.map(d => `<option value="${esc(d)}"/>`).join("");
}

/* Staff modal */
function openAddStaffModal() {
  document.getElementById("staffModalTitle").textContent = "Add Staff Member";
  document.getElementById("editStaffId").value = "";
  document.getElementById("staffForm").reset();
  document.getElementById("staffModal").classList.remove("hidden");
}

function openEditStaff(id) {
  fetch(`/api/staff/${id}`)
    .then(r => r.json())
    .then(json => {
      if (!json.success) { toast(json.error, "error"); return; }
      const s = json.data;
      document.getElementById("staffModalTitle").textContent = "Edit Staff Member";
      document.getElementById("editStaffId").value = id;
      document.getElementById("f_fullname").value = s.full_name || "";
      document.getElementById("f_title").value    = s.job_title  || "";
      document.getElementById("f_dept").value     = s.department || "";
      document.getElementById("f_empid").value    = s.employee_id || "";
      document.getElementById("f_email").value    = s.email || "";
      document.getElementById("f_phone").value    = s.phone || "";
      document.getElementById("staffModal").classList.remove("hidden");
    });
}

function closeStaffModal() {
  document.getElementById("staffModal").classList.add("hidden");
}

async function submitStaffForm(e) {
  e.preventDefault();
  const id = document.getElementById("editStaffId").value;
  const payload = {
    full_name:   document.getElementById("f_fullname").value.trim(),
    job_title:   document.getElementById("f_title").value.trim(),
    department:  document.getElementById("f_dept").value.trim(),
    employee_id: document.getElementById("f_empid").value.trim(),
    email:       document.getElementById("f_email").value.trim(),
    phone:       document.getElementById("f_phone").value.trim(),
  };

  const url    = id ? `/api/staff/${id}` : "/api/staff";
  const method = id ? "PUT" : "POST";
  const btn    = document.getElementById("staffSubmitBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving…';

  const json = await apiFetch(url, { method, body: JSON.stringify(payload) });
  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save';

  if (json.success) {
    toast(json.message, "success");
    closeStaffModal();
    loadStaff();
  } else {
    toast(json.error || "Save failed", "error");
  }
}

async function deleteStaff(id, name) {
  if (!confirm(`Remove "${name}" from active staff?`)) return;
  const json = await apiFetch(`/api/staff/${id}`, { method: "DELETE" });
  if (json.success) { toast(json.message, "success"); loadStaff(); }
  else toast(json.error, "error");
}

/* CSV Import */
function openImportModal() {
  document.getElementById("importModal").classList.remove("hidden");
  document.getElementById("importResult").classList.add("hidden");
  document.getElementById("importBtn").disabled = true;
  SF.csvFile = null;
}
function closeImportModal() {
  document.getElementById("importModal").classList.add("hidden");
}
function handleCSVFile(e) {
  SF.csvFile = e.target.files[0];
  const p = document.querySelector("#csvDropzone p");
  if (p && SF.csvFile) p.textContent = SF.csvFile.name;
  document.getElementById("importBtn").disabled = !SF.csvFile;
}

async function uploadCSV() {
  if (!SF.csvFile) return;
  const fd = new FormData();
  fd.append("file", SF.csvFile);
  const btn = document.getElementById("importBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Importing…';

  try {
    const res  = await fetch("/api/staff/import-csv", { method: "POST", body: fd });
    const json = await res.json();
    const el   = document.getElementById("importResult");
    el.classList.remove("hidden", "success", "error");
    if (json.success) {
      el.classList.add("success");
      let html = `<strong>Imported ${json.data.imported} staff member(s).</strong>`;
      if (json.data.errors.length) {
        html += `<br>Errors:<ul>${json.data.errors.map(e2 => `<li>${esc(e2)}</li>`).join("")}</ul>`;
      }
      el.innerHTML = html;
      toast(json.message, "success");
      loadStaff();
    } else {
      el.classList.add("error");
      el.textContent = json.error || "Import failed";
      toast(json.error || "Import failed", "error");
    }
  } catch (err) {
    toast("Import error: " + err.message, "error");
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-upload"></i> Import';
}

/* =========================================================
   GENERATE STAMPS PAGE
   ========================================================= */
const STYLE_COLORS = {
  A: [
    { hex: "#1a2b5e", label: "Navy"   },
    { hex: "#7c3aed", label: "Purple" },
    { hex: "#065f46", label: "Green"  },
    { hex: "#7f1d1d", label: "Red"    },
  ],
  B: [
    { key: "green",  hex: "#16a34a", label: "Approved" },
    { key: "red",    hex: "#dc2626", label: "Rejected" },
    { key: "blue",   hex: "#2563eb", label: "Reviewed" },
    { key: "orange", hex: "#ea580c", label: "Pending"  },
  ],
  C: [
    { hex: "#1a2b5e", label: "Navy"   },
    { hex: "#7c3aed", label: "Purple" },
    { hex: "#065f46", label: "Green"  },
  ],
  D: [
    { hex: "#1a2b5e", label: "Navy"   },
    { hex: "#7c3aed", label: "Purple" },
    { hex: "#0f766e", label: "Teal"   },
  ],
};

function initGeneratePage() {
  renderColorOptions("A");
  SF.selectedColor = STYLE_COLORS["A"][0].hex;

  // Pre-select staff from URL param
  const params = new URLSearchParams(location.search);
  const staffParam = params.get("staff");
  if (staffParam) {
    const sel = document.getElementById("gen_staff");
    if (sel) { sel.value = staffParam; onStaffChange(); }
  }
}

function renderColorOptions(style) {
  const wrap = document.getElementById("colorOptions");
  if (!wrap) return;
  const colors = STYLE_COLORS[style] || STYLE_COLORS["A"];
  SF.selectedColor = colors[0].key || colors[0].hex;
  wrap.innerHTML = colors.map((c, i) => `
    <div class="color-swatch ${i === 0 ? 'active' : ''}"
         style="background:${c.hex}"
         title="${c.label}"
         onclick="selectColor(this, '${c.key || c.hex}')"></div>
  `).join("");
}

function selectColor(el, value) {
  document.querySelectorAll(".color-swatch").forEach(s => s.classList.remove("active"));
  el.classList.add("active");
  SF.selectedColor = value;
}

function setSize(size) {
  SF.selectedSize = size;
  document.querySelectorAll(".btn-toggle[data-size]").forEach(b => {
    b.classList.toggle("active", b.dataset.size === size);
  });
}

function onStaffChange() {
  const sel    = document.getElementById("gen_staff");
  const staffId = sel.value;
  if (!staffId) return;
  loadStampHistory(staffId);
}

async function generateStamp() {
  const staffId = (document.getElementById("gen_staff") || {}).value;
  if (!staffId) { toast("Please select a staff member", "warning"); return; }

  const style   = SF.selectedStyle;
  const color   = SF.selectedColor;
  const size    = SF.selectedSize;
  const options = {
    show_date:    document.getElementById("opt_date")?.checked ?? true,
    show_logo:    document.getElementById("opt_logo")?.checked ?? true,
    custom_label: document.getElementById("opt_custom_label")?.value?.trim() || null,
  };

  const wrap = document.getElementById("stampPreviewWrap");
  wrap.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><br>Generating stamp…</div>';

  const json = await apiFetch("/api/stamps/generate", {
    method: "POST",
    body: JSON.stringify({ staff_id: parseInt(staffId), style, color, size, options }),
  });

  if (json.success) {
    const url = json.data.image_url;
    wrap.innerHTML = `<img src="${url}?t=${Date.now()}" alt="Stamp Preview" id="generatedStampImg"/>`;
    document.getElementById("previewActions")?.classList.remove("hidden");
    const dl = document.getElementById("downloadLink");
    if (dl) { dl.href = url; dl.download = `stamp_style${style}.png`; }
    toast("Stamp generated!", "success");
    loadStampHistory(staffId);
  } else {
    wrap.innerHTML = '<div class="preview-placeholder"><i class="fa-solid fa-triangle-exclamation fa-2x" style="color:var(--red)"></i><p>Generation failed</p></div>';
    toast(json.error || "Stamp generation failed", "error");
  }
}

async function loadStampHistory(staffId) {
  const panel = document.getElementById("stampHistoryPanel");
  const grid  = document.getElementById("stampHistoryGrid");
  if (!panel || !grid) return;

  const json = await apiFetch(`/api/stamps/${staffId}`);
  if (!json.success || !json.data.stamps.length) { panel.style.display = "none"; return; }

  panel.style.display = "block";
  grid.innerHTML = json.data.stamps.slice(0, 12).map(s => `
    <div class="stamp-thumb" onclick="showStampBig('${s.stamp_image_path}', '${s.stamp_style}')">
      <img src="/static/${s.stamp_image_path}?t=${Date.now()}" alt="${s.stamp_style}" loading="lazy"/>
    </div>`).join("");
}

function showStampBig(path, style) {
  const wrap = document.getElementById("stampPreviewWrap");
  if (wrap) {
    wrap.innerHTML = `<img src="/static/${path}?t=${Date.now()}" alt="Stamp ${style}"/>`;
    document.getElementById("previewActions")?.classList.remove("hidden");
    const dl = document.getElementById("downloadLink");
    if (dl) { dl.href = `/static/${path}`; dl.download = `stamp_${style}.png`; }
  }
}

/* Batch */
function openBatchModal() {
  document.getElementById("batchModal")?.classList.remove("hidden");
}
function batchSelectAll() {
  document.querySelectorAll(".batch-check").forEach(c => c.checked = true);
}
function batchSelectNone() {
  document.querySelectorAll(".batch-check").forEach(c => c.checked = false);
}

async function runBatch() {
  const ids = [...document.querySelectorAll(".batch-check:checked")].map(c => parseInt(c.value));
  if (!ids.length) { toast("Select at least one staff member", "warning"); return; }

  const btn = document.getElementById("batchRunBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating…';

  const payload = {
    staff_ids: ids,
    style:  SF.selectedStyle,
    color:  SF.selectedColor,
    size:   SF.selectedSize,
    options: { show_date: true, show_logo: true },
  };

  try {
    const res = await fetch("/api/stamps/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url; a.download = "stamps_batch.zip"; a.click();
      URL.revokeObjectURL(url);
      toast(`ZIP downloaded (${ids.length} stamps)`, "success");
      document.getElementById("batchModal")?.classList.add("hidden");
    } else {
      const json = await res.json();
      toast(json.error || "Batch failed", "error");
    }
  } catch (e) {
    toast("Batch error: " + e.message, "error");
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-download"></i> Generate & Download ZIP';
}

/* =========================================================
   STAMP PDF PAGE
   ========================================================= */
function initStampPDFPage() {}

async function handlePDFUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);

  document.getElementById("pdfDropText").textContent = "Uploading…";

  try {
    const res  = await fetch("/api/pdf/upload", { method: "POST", body: fd });
    const json = await res.json();
    if (json.success) {
      SF.pdfPath       = json.data.file_path;
      SF.pdfTotalPages = json.data.info.pages || 1;
      SF.pdfCurrentPage = 0;

      document.getElementById("pdfDropzone").classList.add("hidden");
      document.getElementById("pdfInfo").classList.remove("hidden");
      document.getElementById("pdfName").textContent  = json.data.filename;
      document.getElementById("pdfPages").textContent = ` — ${SF.pdfTotalPages} page(s)`;
      document.getElementById("step1Check")?.classList.remove("hidden");

      if (SF.pdfTotalPages > 1) document.getElementById("pdfNavRow")?.classList.remove("hidden");
      await loadPDFPreview(0);
      toast("PDF uploaded!", "success");
    } else {
      toast(json.error || "Upload failed", "error");
      document.getElementById("pdfDropText").textContent = "Click or drag a PDF here";
    }
  } catch (err) {
    toast("Upload error: " + err.message, "error");
  }
}

function clearPDF() {
  SF.pdfPath = null;
  SF.pdfTotalPages = 1;
  SF.pdfCurrentPage = 0;
  document.getElementById("pdfDropzone").classList.remove("hidden");
  document.getElementById("pdfInfo").classList.add("hidden");
  document.getElementById("pdfDropText").textContent = "Click or drag a PDF here";
  document.getElementById("pdfNavRow")?.classList.add("hidden");
  document.getElementById("step1Check")?.classList.add("hidden");
  document.getElementById("pdfPreviewArea").innerHTML = `
    <div class="preview-placeholder">
      <i class="fa-solid fa-file-pdf fa-3x"></i><p>Upload a PDF to preview</p>
    </div>`;
  document.getElementById("stampedResult")?.classList.add("hidden");
  document.getElementById("pdfFileInput").value = "";
}

async function loadPDFPreview(page) {
  if (!SF.pdfPath) return;
  SF.pdfCurrentPage = Math.max(0, Math.min(page, SF.pdfTotalPages - 1));
  document.getElementById("pageIndicator").textContent = `Page ${SF.pdfCurrentPage + 1} / ${SF.pdfTotalPages}`;

  const area = document.getElementById("pdfPreviewArea");
  area.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-spinner fa-spin"></i> Loading preview…</div>';

  const json = await apiFetch("/api/pdf/preview", {
    method: "POST",
    body: JSON.stringify({ pdf_path: SF.pdfPath, page: SF.pdfCurrentPage }),
  });
  if (json.success) {
    area.innerHTML = `<img src="${json.data.preview_url}?t=${Date.now()}" alt="PDF Preview"/>`;
  } else {
    area.innerHTML = `<div class="preview-placeholder"><i class="fa-solid fa-triangle-exclamation"></i><p>${json.error}</p></div>`;
  }
}

function previewPage(dir) {
  loadPDFPreview(SF.pdfCurrentPage + dir);
}

function setPlacement(pos) {
  SF.selectedPlacement = pos;
  document.querySelectorAll(".place-btn").forEach(b => b.classList.toggle("active", b.dataset.pos === pos));
  const customRow = document.getElementById("customCoordsRow");
  if (customRow) customRow.classList.toggle("hidden", pos !== "custom");
}

function setPages(pages) {
  SF.selectedPages = pages;
  document.querySelectorAll(".btn-toggle[data-pages]").forEach(b => {
    b.classList.toggle("active", b.dataset.pages === pages);
  });
  const customInput = document.getElementById("customPages");
  if (customInput) customInput.classList.toggle("hidden", pages !== "custom-pages");
}

async function applyStamp() {
  if (!SF.pdfPath) { toast("Please upload a PDF first", "warning"); return; }
  const staffId = (document.getElementById("pdf_staff") || {}).value;
  if (!staffId) { toast("Please select a staff member", "warning"); return; }

  const style    = document.getElementById("pdf_style").value;
  const color    = document.getElementById("pdf_color").value;
  const size     = document.getElementById("pdf_size").value;
  const stampW   = parseInt(document.getElementById("stampWidthRange").value);
  const pages    = SF.selectedPages === "custom-pages"
                   ? (document.getElementById("customPages")?.value || "all")
                   : SF.selectedPages;
  const customX  = SF.selectedPlacement === "custom" ? document.getElementById("custom_x")?.value : null;
  const customY  = SF.selectedPlacement === "custom" ? document.getElementById("custom_y")?.value : null;

  const btn = document.getElementById("applyStampBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Applying…';

  const json = await apiFetch("/api/pdf/stamp", {
    method: "POST",
    body: JSON.stringify({
      staff_id:    parseInt(staffId),
      style, color, size,
      pdf_path:    SF.pdfPath,
      placement:   SF.selectedPlacement,
      pages, opacity: 0.9,
      stamp_width: stampW,
      custom_x:    customX ? parseFloat(customX) : null,
      custom_y:    customY ? parseFloat(customY) : null,
      options:     { show_date: true, show_logo: true },
    }),
  });

  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-stamp"></i> Apply Stamp to PDF';

  if (json.success) {
    toast("PDF stamped successfully!", "success");
    const result = document.getElementById("stampedResult");
    const dl     = document.getElementById("downloadStampedPDF");
    if (result) result.classList.remove("hidden");
    if (dl) { dl.href = json.data.output_url; dl.download = "stamped_document.pdf"; }
  } else {
    toast(json.error || "Stamping failed", "error");
  }
}

/* =========================================================
   AUDIT LOG PAGE
   ========================================================= */
let logPage = 0;
const LOG_LIMIT = 25;

function initAuditLog() {
  loadLog();
}

async function loadLog() {
  const search = (document.getElementById("logSearch") || {}).value || "";
  const offset = logPage * LOG_LIMIT;

  document.getElementById("logTableWrap").innerHTML =
    '<div class="loading-spinner"><i class="fa-solid fa-spinner fa-spin"></i> Loading…</div>';

  const json = await apiFetch(
    `/api/audit-log?search=${encodeURIComponent(search)}&limit=${LOG_LIMIT}&offset=${offset}`
  );
  if (!json.success) { toast(json.error, "error"); return; }

  const entries = json.data.entries;
  document.getElementById("logCount").textContent = entries.length;

  if (!entries.length) {
    document.getElementById("logTableWrap").innerHTML =
      '<p class="empty-state">No log entries found.</p>';
  } else {
    document.getElementById("logTableWrap").innerHTML = `
      <table class="data-table">
        <thead><tr>
          <th>#</th><th>Action</th><th>Staff</th><th>Department</th>
          <th>Document</th><th>Details</th><th>Timestamp</th>
        </tr></thead>
        <tbody>${entries.map(e => `
          <tr>
            <td class="text-muted">${e.id}</td>
            <td><span class="action-badge action-${(e.action||'').toLowerCase().replace(/_/g,'-')}">${e.action}</span></td>
            <td>${e.staff_name ? esc(e.staff_name) : '—'}</td>
            <td>${e.department ? esc(e.department) : '—'}</td>
            <td>${e.document_name ? esc(e.document_name) : '—'}</td>
            <td class="text-muted text-sm">${e.details ? esc(e.details) : '—'}</td>
            <td class="text-muted text-sm">${e.created_at}</td>
          </tr>`).join("")}
        </tbody>
      </table>`;
  }

  document.getElementById("pageInfo").textContent = `Page ${logPage + 1}`;
  document.getElementById("prevPage").disabled = logPage === 0;
  document.getElementById("nextPage").disabled = entries.length < LOG_LIMIT;
}

let logSearchTimer;
function searchLog() {
  clearTimeout(logSearchTimer);
  logSearchTimer = setTimeout(() => { logPage = 0; loadLog(); }, 350);
}

function changePage(dir) {
  logPage = Math.max(0, logPage + dir);
  loadLog();
}

/* =========================================================
   SETTINGS PAGE
   ========================================================= */
function initSettingsPage() {
  // Sync color inputs
  const primaryPicker = document.getElementById("org_primary");
  const primaryHex    = document.getElementById("org_primary_hex");
  const accentPicker  = document.getElementById("org_accent");
  const accentHex     = document.getElementById("org_accent_hex");

  if (primaryPicker && primaryHex) {
    primaryPicker.addEventListener("input", () => primaryHex.value = primaryPicker.value);
    primaryHex.addEventListener("change", () => {
      if (/^#[0-9a-f]{6}$/i.test(primaryHex.value)) primaryPicker.value = primaryHex.value;
    });
  }
  if (accentPicker && accentHex) {
    accentPicker.addEventListener("input", () => accentHex.value = accentPicker.value);
    accentHex.addEventListener("change", () => {
      if (/^#[0-9a-f]{6}$/i.test(accentHex.value)) accentPicker.value = accentHex.value;
    });
  }
}

function syncColor(pickerId, hexId) {
  const picker = document.getElementById(pickerId);
  const hex    = document.getElementById(hexId);
  if (picker && hex && /^#[0-9a-f]{6}$/i.test(hex.value)) picker.value = hex.value;
}

async function saveOrgSettings(e) {
  e.preventDefault();
  const payload = {
    name:          document.getElementById("org_name")?.value?.trim(),
    primary_color: document.getElementById("org_primary_hex")?.value,
    accent_color:  document.getElementById("org_accent_hex")?.value,
  };
  const json = await apiFetch("/api/settings/org", { method: "POST", body: JSON.stringify(payload) });
  if (json.success) toast("Settings saved!", "success");
  else toast(json.error || "Save failed", "error");
}

async function uploadLogo(e) {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);

  try {
    const res  = await fetch("/api/settings/logo", { method: "POST", body: fd });
    const json = await res.json();
    if (json.success) {
      toast("Logo uploaded!", "success");
      // Show preview
      const resultDiv = document.getElementById("logoResult");
      if (resultDiv) {
        resultDiv.innerHTML = `<img src="${json.data.logo_url}?t=${Date.now()}" class="logo-preview" alt="Logo"/>
                               <p class="text-muted text-sm">Logo updated. Refresh to see it on stamps.</p>`;
      }
    } else {
      toast(json.error || "Upload failed", "error");
    }
  } catch (err) {
    toast("Upload error: " + err.message, "error");
  }
}

function confirmClearGenerated() {
  if (!confirm("Delete all generated stamp images? This cannot be undone.")) return;
  toast("Clear function: remove static/generated/*.png manually or add a server endpoint.", "info");
}

/* =========================================================
   E-SIGNATURE PAGE
   ========================================================= */

const SIG = {
  staffId:      null,
  canvas:       null,
  ctx:          null,
  drawing:      false,
  lastX:        0,
  lastY:        0,
  penColor:     "#1a2b5e",
  penSize:      3,
  strokes:      [],       // array of ImageData snapshots for undo
  hasSig:       false,
  sigPdfPath:   null,

  // Trackpad mode state
  trackpadMode: false,
  liftTimer:    null,
  liftDelay:    450,       // ms of stillness before pen lifts
  liftBarTimer: null,
};

function initESignaturePage() {
  // Auto-select first staff member if list has items
  const first = document.querySelector(".sig-staff-item");
  if (first) selectStaff(first);
}

/* ---- Staff selection ---- */
function filterSigStaff() {
  const q = (document.getElementById("sigStaffSearch")?.value || "").toLowerCase();
  document.querySelectorAll(".sig-staff-item").forEach(li => {
    const name = (li.dataset.name || "").toLowerCase();
    li.style.display = name.includes(q) ? "" : "none";
  });
}

function selectStaff(el) {
  document.querySelectorAll(".sig-staff-item").forEach(li => li.classList.remove("active"));
  el.classList.add("active");

  SIG.staffId   = parseInt(el.dataset.id);
  const name    = el.dataset.name;
  const title   = el.dataset.title;
  const dept    = el.dataset.dept;
  const hasSig  = el.dataset.hasSig === "1";

  // Update info bar
  document.getElementById("sigFullName").textContent = name;
  document.getElementById("sigMeta").textContent     = `${title} · ${dept}`;
  document.getElementById("sigActionRow").style.display = "";
  document.getElementById("sigPlaceholder").style.display = "none";

  if (hasSig) {
    loadSavedSignature();
  } else {
    showPadToRedraw();
  }
}

/* ---- Show the canvas pad ---- */
function showPadToRedraw() {
  document.getElementById("savedSigPanel").style.display = "none";
  document.getElementById("sigPadPanel").style.display   = "";

  if (!SIG.canvas) {
    initCanvas();
  } else {
    clearPad();
  }

  // Always render guidance when pad is shown
  _renderGuidance(SIG.trackpadMode);
}

/* ---- Canvas init ---- */
function initCanvas() {
  const canvas = document.getElementById("sigCanvas");
  SIG.canvas   = canvas;
  SIG.ctx      = canvas.getContext("2d");

  // High-DPI scaling
  const wrap = document.getElementById("sigCanvasWrap");
  const dpr  = window.devicePixelRatio || 1;
  const rect = wrap.getBoundingClientRect();
  const cssW = rect.width || 600;
  const cssH = 220;

  canvas.width  = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width  = cssW + "px";
  canvas.style.height = cssH + "px";
  SIG.ctx.scale(dpr, dpr);

  SIG.ctx.lineCap    = "round";
  SIG.ctx.lineJoin   = "round";
  SIG.ctx.lineWidth  = SIG.penSize;
  SIG.ctx.strokeStyle = SIG.penColor;

  // Mouse events
  canvas.addEventListener("mousedown",  onPadDown);
  canvas.addEventListener("mousemove",  onPadMove);
  canvas.addEventListener("mouseup",    onPadUp);
  canvas.addEventListener("mouseleave", onPadLeave);

  // Touch events
  canvas.addEventListener("touchstart", onTouchDown, { passive: false });
  canvas.addEventListener("touchmove",  onTouchMove, { passive: false });
  canvas.addEventListener("touchend",   onTouchUp);
}

function canvasPos(e) {
  const rect = SIG.canvas.getBoundingClientRect();
  return {
    x: (e.clientX ?? e.touches[0].clientX) - rect.left,
    y: (e.clientY ?? e.touches[0].clientY) - rect.top,
  };
}

/* ---- Normal mouse mode handlers ---- */
function onPadDown(e) {
  if (SIG.trackpadMode) return;   // trackpad mode uses mousemove only
  SIG.drawing = true;
  const { x, y } = canvasPos(e);
  SIG.lastX = x; SIG.lastY = y;
  _snapshotForUndo();
  _hideHint();
  SIG.ctx.beginPath();
  SIG.ctx.moveTo(x, y);
}

function onPadMove(e) {
  if (SIG.trackpadMode) {
    _tpDraw(e);       // delegate to trackpad drawing logic
    return;
  }
  if (!SIG.drawing) return;
  _drawSegment(canvasPos(e));
}

function onPadUp() {
  if (SIG.trackpadMode) return;
  SIG.drawing = false;
  SIG.ctx.beginPath();
}

function onPadLeave() {
  if (SIG.trackpadMode) {
    // Leaving the canvas in trackpad mode: lift immediately
    _tpLiftNow();
    return;
  }
  SIG.drawing = false;
  SIG.ctx.beginPath();
}

function onTouchDown(e) { e.preventDefault(); onPadDown(e.touches[0]); }
function onTouchMove(e) { e.preventDefault(); onPadMove(e.touches[0]); }
function onTouchUp(e)   { onPadUp(); }

/* ---- Shared draw helpers ---- */
function _drawSegment({ x, y }) {
  SIG.ctx.lineWidth    = SIG.penSize;
  SIG.ctx.strokeStyle  = SIG.penColor;
  SIG.ctx.lineCap      = "round";
  SIG.ctx.lineJoin     = "round";
  SIG.ctx.lineTo(x, y);
  SIG.ctx.stroke();
  SIG.ctx.beginPath();
  SIG.ctx.moveTo(x, y);
  SIG.lastX = x; SIG.lastY = y;
}

function _snapshotForUndo() {
  SIG.strokes.push(
    SIG.ctx.getImageData(0, 0, SIG.canvas.width, SIG.canvas.height)
  );
}

function _hideHint() {
  document.getElementById("sigCanvasHint")?.classList.add("hidden");
}

/* =========================================================
   TRACKPAD MODE
   ========================================================= */

function toggleTrackpadMode() {
  SIG.trackpadMode = !SIG.trackpadMode;
  const btn  = document.getElementById("tpModeBtn");
  const wrap = document.getElementById("sigCanvasWrap");
  const badge    = document.getElementById("tpStatusBadge");
  const delayRow = document.getElementById("tpDelayRow");

  if (SIG.trackpadMode) {
    btn.classList.add("active");
    document.getElementById("tpModeBtnLabel").textContent = "Trackpad: ON";
    wrap.classList.add("trackpad-active");
    badge?.classList.remove("hidden");
    delayRow?.classList.remove("hidden");
    // Ensure any in-progress normal-mode drawing is cancelled
    SIG.drawing = false;
    SIG.ctx.beginPath();
    _setTpStatus("idle");
    _renderGuidance(true);
    // Update canvas hint
    const hint = document.getElementById("sigCanvasHintText");
    if (hint) hint.textContent = "Move your finger on the trackpad to draw";
  } else {
    btn.classList.remove("active");
    document.getElementById("tpModeBtnLabel").textContent = "Trackpad Mode";
    wrap.classList.remove("trackpad-active", "tp-drawing", "tp-lifted");
    badge?.classList.add("hidden");
    delayRow?.classList.add("hidden");
    // Clean up any pending lift timer
    _tpLiftNow();
    _renderGuidance(false);
    const hint = document.getElementById("sigCanvasHintText");
    if (hint) hint.textContent = "Click and drag to sign";
  }
}

/* Called on every mousemove in trackpad mode */
function _tpDraw(e) {
  const { x, y } = canvasPos(e);
  const wrap = document.getElementById("sigCanvasWrap");

  if (!SIG.drawing) {
    // Finger started moving → begin a new stroke
    SIG.drawing = true;
    _snapshotForUndo();
    _hideHint();
    SIG.ctx.beginPath();
    SIG.ctx.moveTo(x, y);
    wrap.classList.remove("tp-lifted");
    wrap.classList.add("tp-drawing");
    _setTpStatus("drawing");
    _startLiftBar();
  }

  _drawSegment({ x, y });

  // Reset the lift countdown every time movement is detected
  clearTimeout(SIG.liftTimer);
  _resetLiftBar();
  SIG.liftTimer = setTimeout(_tpLiftPen, SIG.liftDelay);
}

/* Pen lift triggered by the pause timer */
function _tpLiftPen() {
  if (!SIG.drawing) return;
  SIG.drawing = false;
  SIG.ctx.beginPath();
  const wrap = document.getElementById("sigCanvasWrap");
  wrap.classList.remove("tp-drawing");
  wrap.classList.add("tp-lifted");
  _setTpStatus("lifted");
  _drainLiftBar();
}

/* Immediate lift (on mouseleave or mode toggle off) */
function _tpLiftNow() {
  clearTimeout(SIG.liftTimer);
  SIG.drawing = false;
  SIG.ctx.beginPath();
  const wrap = document.getElementById("sigCanvasWrap");
  if (wrap) {
    wrap.classList.remove("tp-drawing", "tp-lifted");
  }
  _resetLiftBar();
}

/* ---- Lift countdown bar ---- */
function _startLiftBar() {
  const bar = document.getElementById("tpLiftBar");
  if (!bar) return;
  // Snap to full instantly, no transition
  bar.style.transition = "none";
  bar.style.width      = "100%";
}

function _resetLiftBar() {
  // Called on every new movement — snap back to full
  const bar = document.getElementById("tpLiftBar");
  if (!bar) return;
  bar.style.transition = "none";
  bar.style.width      = "100%";
}

function _drainLiftBar() {
  // Called when pen lifts — smoothly drain to 0 over liftDelay
  const bar = document.getElementById("tpLiftBar");
  if (!bar) return;
  // Force a reflow so the transition fires from 100%
  bar.offsetWidth;  // eslint-disable-line
  bar.style.transition = `width ${SIG.liftDelay}ms linear`;
  bar.style.width      = "0%";
}

/* ---- Status badge ---- */
const TP_STATUS = {
  idle:    { cls: "status-idle",    text: "Move finger to draw" },
  drawing: { cls: "status-drawing", text: "Drawing…" },
  lifted:  { cls: "status-lifted",  text: "Pen lifted — reposition and move to continue" },
};

function _setTpStatus(state) {
  const badge = document.getElementById("tpStatusBadge");
  const text  = document.getElementById("tpStatusText");
  if (!badge || !text) return;
  badge.classList.remove("status-idle", "status-drawing", "status-lifted");
  const s = TP_STATUS[state] || TP_STATUS.idle;
  badge.classList.add(s.cls);
  text.textContent = s.text;
}

/* ---- Lift delay slider ---- */
function updateLiftDelay() {
  SIG.liftDelay = parseInt(document.getElementById("tpDelaySlider")?.value || "450");
  document.getElementById("tpDelayLabel").textContent = SIG.liftDelay + " ms";
}

/* ---- Adaptive guidance card ---- */
function _renderGuidance(trackpadMode) {
  const el = document.getElementById("sigGuidance");
  if (!el) return;

  if (trackpadMode) {
    el.className = "sig-guidance tp-mode";
    el.innerHTML = `
      <div class="guidance-title">
        <i class="fa-solid fa-hand-pointer"></i> Trackpad Mode — How to sign
      </div>
      <ul class="guidance-steps">
        <li class="guidance-step">
          <span class="step-num-badge">1</span>
          <span class="step-text">
            <strong>Move your finger</strong> on the trackpad over the canvas below —
            drawing starts immediately, no clicking required.
          </span>
        </li>
        <li class="guidance-step">
          <span class="step-num-badge">2</span>
          <span class="step-text">
            <strong>Pause briefly</strong> to lift the pen (the bar at the bottom
            of the canvas drains — when it empties, the stroke ends).
          </span>
        </li>
        <li class="guidance-step">
          <span class="step-num-badge">3</span>
          <span class="step-text">
            <strong>Reposition your finger</strong> anywhere on the trackpad, then
            move again to start the next stroke.
          </span>
        </li>
        <li class="guidance-step">
          <span class="step-num-badge">4</span>
          <span class="step-text">
            Adjust the <strong>pen-lift delay</strong> slider below the canvas to
            control how long you need to pause — longer for a steadier hand,
            shorter for faster signing.
          </span>
        </li>
      </ul>`;
  } else {
    el.className = "sig-guidance";
    el.innerHTML = `
      <div class="guidance-title">
        <i class="fa-solid fa-computer-mouse"></i> Mouse / Touch Mode — How to sign
      </div>
      <ul class="guidance-steps">
        <li class="guidance-step">
          <span class="step-num-badge">1</span>
          <span class="step-text">
            <strong>Click and hold</strong> on the canvas (or press and drag on a
            touchscreen), then move to draw your signature.
          </span>
        </li>
        <li class="guidance-step">
          <span class="step-num-badge">2</span>
          <span class="step-text">
            <strong>Release the button</strong> to lift the pen, then click again
            in a new position to continue.
          </span>
        </li>
        <li class="guidance-step">
          <span class="step-num-badge">3</span>
          <span class="step-text">
            Use <strong>Undo</strong> to remove the last stroke, or
            <strong>Clear</strong> to start over.
            Switch to <strong>Trackpad Mode</strong> if clicking while dragging
            is awkward on your laptop.
          </span>
        </li>
      </ul>`;
  }
}

/* ---- Pad controls ---- */
function clearPad() {
  if (!SIG.canvas) return;
  _tpLiftNow();
  SIG.ctx.clearRect(0, 0, SIG.canvas.width, SIG.canvas.height);
  SIG.strokes = [];
  document.getElementById("sigCanvasHint")?.classList.remove("hidden");
  if (SIG.trackpadMode) _setTpStatus("idle");
}

function undoStroke() {
  if (!SIG.canvas || !SIG.strokes.length) return;
  _tpLiftNow();
  const prev = SIG.strokes.pop();
  SIG.ctx.putImageData(prev, 0, 0);
  if (!SIG.strokes.length) {
    document.getElementById("sigCanvasHint")?.classList.remove("hidden");
    if (SIG.trackpadMode) _setTpStatus("idle");
  }
}

function updatePen() {
  SIG.penColor = document.getElementById("penColor")?.value || "#1a2b5e";
  SIG.penSize  = parseInt(document.getElementById("penSize")?.value || "3");
  document.getElementById("penSizeLabel").textContent = SIG.penSize + "px";
}

/* ---- Save drawn signature ---- */
async function saveSignature() {
  if (!SIG.canvas || !SIG.staffId) return;

  // Check canvas has actual drawing
  const pixelData = SIG.ctx.getImageData(0, 0, SIG.canvas.width, SIG.canvas.height).data;
  const hasInk = pixelData.some((v, i) => i % 4 === 3 && v > 0);
  if (!hasInk) { toast("Canvas is empty — please draw your signature first", "warning"); return; }

  const imageData = SIG.canvas.toDataURL("image/png");
  const btn = document.getElementById("saveSigBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving…';

  const json = await apiFetch(`/api/e-signature/${SIG.staffId}`, {
    method: "POST",
    body: JSON.stringify({ image_data: imageData }),
  });

  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Signature';

  if (json.success) {
    toast("Signature saved!", "success");
    // Update the dot in the staff list
    const li = document.querySelector(`.sig-staff-item[data-id="${SIG.staffId}"]`);
    if (li) {
      li.dataset.hasSig = "1";
      li.querySelector(".sig-status-dot")?.classList.add("has-sig");
    }
    loadSavedSignature();
  } else {
    toast(json.error || "Save failed", "error");
  }
}

/* ---- Load and display a saved signature ---- */
async function loadSavedSignature() {
  const json = await apiFetch(`/api/e-signature/${SIG.staffId}`);
  if (!json.success || !json.data.signature) {
    showPadToRedraw();
    return;
  }
  const sig = json.data.signature;
  document.getElementById("sigPadPanel").style.display   = "none";
  document.getElementById("savedSigPanel").style.display = "";
  document.getElementById("savedSigImg").src = sig.image_url + "?t=" + Date.now();
  SIG.hasSig = true;
}

/* ---- Delete a saved signature ---- */
async function deleteSignature() {
  if (!SIG.staffId) return;
  if (!confirm("Delete this signature? This cannot be undone.")) return;
  const json = await apiFetch(`/api/e-signature/${SIG.staffId}`, { method: "DELETE" });
  if (json.success) {
    toast("Signature deleted", "success");
    SIG.hasSig = false;
    const li = document.querySelector(`.sig-staff-item[data-id="${SIG.staffId}"]`);
    if (li) {
      li.dataset.hasSig = "0";
      li.querySelector(".sig-status-dot")?.classList.remove("has-sig");
    }
    document.getElementById("savedSigPanel").style.display = "none";
    document.getElementById("generatedSigStampWrap")?.classList.add("hidden");
    showPadToRedraw();
  } else {
    toast(json.error || "Delete failed", "error");
  }
}

/* ---- Generate Style C stamp with the drawn signature ---- */
async function generateSigStamp() {
  if (!SIG.staffId) return;
  const btn = document.getElementById("genSigStampBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating…';

  const json = await apiFetch(`/api/e-signature/${SIG.staffId}/stamp`, {
    method: "POST",
    body: JSON.stringify({
      color:   document.getElementById("sigStampColor")?.value || "#1a2b5e",
      size:    document.getElementById("sigStampSize")?.value  || "medium",
      options: { show_date: true },
    }),
  });

  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-stamp"></i> Generate Stamp Image';

  if (json.success) {
    const wrap = document.getElementById("generatedSigStampWrap");
    const img  = document.getElementById("generatedSigStampImg");
    const dl   = document.getElementById("downloadSigStamp");
    img.src    = json.data.image_url + "?t=" + Date.now();
    dl.href    = json.data.image_url;
    dl.download = "esignature_stamp.png";
    wrap?.classList.remove("hidden");
    toast("Signature stamp generated!", "success");
  } else {
    toast(json.error || "Generation failed", "error");
  }
}

/* ---- Apply raw signature to PDF ---- */
function handleSigPDF(e) {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);

  document.getElementById("sigPdfLabel").textContent = "Uploading…";
  document.getElementById("applySigPDFBtn").disabled = true;

  fetch("/api/pdf/upload", { method: "POST", body: fd })
    .then(r => r.json())
    .then(json => {
      if (json.success) {
        SIG.sigPdfPath = json.data.file_path;
        document.getElementById("sigPdfLabel").textContent = json.data.filename;
        document.getElementById("applySigPDFBtn").disabled = false;
        toast("PDF ready — click Apply & Download", "success");
      } else {
        toast(json.error || "Upload failed", "error");
        document.getElementById("sigPdfLabel").textContent = "Click to upload PDF";
      }
    });
}

async function applySigToPDF() {
  if (!SIG.staffId || !SIG.sigPdfPath) return;
  const btn = document.getElementById("applySigPDFBtn");
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Applying…';

  const json = await apiFetch(`/api/e-signature/${SIG.staffId}/apply-pdf`, {
    method: "POST",
    body: JSON.stringify({
      pdf_path:    SIG.sigPdfPath,
      placement:   document.getElementById("sigPlacement")?.value || "bottom-right",
      pages:       "all",
      stamp_width: 100,
    }),
  });

  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-file-signature"></i> Apply & Download PDF';

  if (json.success) {
    // Auto-download
    const a = document.createElement("a");
    a.href = json.data.output_url;
    a.download = "signed_document.pdf";
    a.click();
    toast("Signed PDF downloaded!", "success");
  } else {
    toast(json.error || "Apply failed", "error");
  }
}

/* =========================================================
   Utility
   ========================================================= */
function esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
