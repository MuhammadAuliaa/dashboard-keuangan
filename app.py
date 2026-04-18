from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file
from datetime import datetime
import os, io, openpyxl
import pandas as pd
import uuid

app = Flask(__name__)

MAX_TABUNGAN = 500_000_000

# ── Data directory ─────────────────────────────────────────────────────────────
DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
GOALS_FILE = os.path.join(DATA_DIR, "savings_goals.xlsx")
DATA_FILE = os.path.join(DATA_DIR, "transactions.xlsx")
os.makedirs(DATA_DIR, exist_ok=True)

# ── Goals: load / save via .xlsx ───────────────────────────────────────────────
GOALS_HEADERS = ["id", "name", "icon", "category", "target", "saved", "deadline", "status", "persen_alokasi"]

def compute_days_left(deadline_str):
    try:
        deadline = datetime.strptime(str(deadline_str).split(" ")[0], "%Y-%m-%d")
        return max(0, (deadline - datetime.now()).days)
    except:
        return 0

def _load_goals() -> list:
    if not os.path.exists(GOALS_FILE):
        return []
    try:
        wb = openpyxl.load_workbook(GOALS_FILE, read_only=True, data_only=True)
        ws = wb.active
        rows_iter  = ws.iter_rows(values_only=True)
        header_raw = next(rows_iter, None)
        if not header_raw:
            return []
        header = [str(h).strip() if h else f"col{i}" for i, h in enumerate(header_raw)]
        goals  = []
        for row in rows_iter:
            if all(v is None for v in row): continue
            g = dict(zip(header, row))
            g["id"]       = int(g.get("id") or 0)
            g["target"]   = int(g.get("target") or 0)
            g["saved"]    = int(g.get("saved")  or 0)
            g["deadline"] = str(g.get("deadline") or "")
            g["status"]   = str(g.get("status")   or "active")
            g["name"]     = str(g.get("name")     or "")
            g["icon"]     = str(g.get("icon")     or "savings")
            g["category"] = str(g.get("category") or "Lainnya")
            g["days_left"] = compute_days_left(g["deadline"])
            raw_pa = g.get("persen_alokasi")
            try:
                g["persen_alokasi"] = float(raw_pa) if raw_pa not in (None, "", "None") else None
            except:
                g["persen_alokasi"] = None
            goals.append(g)
        return goals
    except Exception as e:
        print(f"[WARN] _load_goals error: {e}")
        return []

def _save_goals(goals: list) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Goals"
    ws.append(GOALS_HEADERS)
    for g in goals:
        ws.append([g.get(h) for h in GOALS_HEADERS])
    wb.save(GOALS_FILE)

SAVINGS_GOALS: list = _load_goals()
_next_goal_id: int  = max((g["id"] for g in SAVINGS_GOALS), default=0) + 1

# ── Savings allocation helpers ─────────────────────────────────────────────────
def _get_amount(row: dict) -> float:
    """Extract numeric IDR amount from a transaction row."""
    try:
        return float(str(row.get("IDR", 0) or 0).replace(",", ""))
    except:
        return 0.0

def _is_savings_row(row: dict) -> bool:
    """Return True if this transaction row is a Savings category."""
    return str(row.get("Category", "")).strip().lower() == "savings"

def _allocate_to_goals(amount: float) -> None:
    """Distribute amount to active goals that have persen_alokasi set, proportional to their allocation %.
    Goals without persen_alokasi are skipped. If all eligible goals are 100% complete, skips silently."""
    if amount <= 0:
        return
    # Only goals that are active AND have a non-None persen_alokasi
    eligible = [g for g in SAVINGS_GOALS if g["status"] == "active" and g.get("persen_alokasi") not in (None, 0)]
    if not eligible:
        return
    total_pct = sum(g["persen_alokasi"] for g in eligible)
    if total_pct <= 0:
        return
    for g in eligible:
        share = amount * (g["persen_alokasi"] / total_pct)
        g["saved"] = max(0, g["saved"] + round(share))
        g["status"] = "completed" if g["saved"] >= g["target"] else "active"
        g["days_left"] = compute_days_left(g["deadline"])
    _save_goals(SAVINGS_GOALS)

def _deallocate_from_goals(amount: float) -> None:
    """Remove amount proportionally from active goals that have persen_alokasi set."""
    if amount <= 0:
        return
    eligible = [g for g in SAVINGS_GOALS if g.get("persen_alokasi") not in (None, 0)]
    total_pct = sum(g["persen_alokasi"] for g in eligible)
    if not eligible or total_pct <= 0:
        return
    for g in eligible:
        share = amount * (g["persen_alokasi"] / total_pct)
        g["saved"] = max(0, g["saved"] - round(share))
        g["status"] = "completed" if g["saved"] >= g["target"] else "active"
        g["days_left"] = compute_days_left(g["deadline"])
    _save_goals(SAVINGS_GOALS)

def _recalculate_goals_from_transactions() -> None:
    """Recompute goals saved from scratch; only goals with persen_alokasi get a share."""
    total_savings = sum(_get_amount(r) for r in UPLOADED_TRANSACTIONS if _is_savings_row(r))
    for g in SAVINGS_GOALS:
        g["saved"] = 0
    if total_savings <= 0:
        _save_goals(SAVINGS_GOALS)
        return
    eligible = [g for g in SAVINGS_GOALS if g.get("persen_alokasi") not in (None, 0)]
    total_pct = sum(g["persen_alokasi"] for g in eligible)
    if eligible and total_pct > 0:
        for g in eligible:
            share = total_savings * (g["persen_alokasi"] / total_pct)
            g["saved"] = round(share)
            g["status"] = "completed" if g["saved"] >= g["target"] else "active"
            g["days_left"] = compute_days_left(g["deadline"])
    _save_goals(SAVINGS_GOALS)

# def save_transactions(data):
#     df = pd.DataFrame(data)
#     df.to_excel(DATA_FILE, index=False)

def save_transactions(data):
    for row in data:
        if "id" not in row:
            row["id"] = str(uuid.uuid4())
    df = pd.DataFrame(data)
    df.to_excel(DATA_FILE, index=False)

def load_transactions():
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        return df.to_dict(orient="records")
    return []

# UPLOADED_TRANSACTIONS: list = []
UPLOADED_TRANSACTIONS = load_transactions()

MONTHLY_INCOME_DATA = {
    2024: {
        "labels": ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Ags","Sep","Okt","Nov","Des"],
        "income":  [0,0,0,0,0,0,0,0,0,0,0,0],
        "outcome":  [0,0,0,0,0,0,0,0,0,0,0,0],
    },
    2025: {
        "labels": ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Ags","Sep","Okt","Nov","Des"],
        "income":  [0,0,0,0,0,0,0,0,0,0,0,0],
        "outcome":  [0,0,0,0,0,0,0,0,0,0,0,0],
    },
    2026: {
        "labels": ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Ags","Sep","Okt","Nov","Des"],
        "income":  [0,0,0,0,0,0,0,0,0,0,0,0],
        "outcome":  [0,0,0,0,0,0,0,0,0,0,0,0],
    },
}

DASHBOARD_DATA = {
    "user": {
        "name": "Rizky Pratama",
        "avatar": "https://ui-avatars.com/api/?name=Rizky+Pratama&background=00A86B&color=fff&size=64",
    },
    "summary": {"total_tabungan": 125000000, "max_tabungan": MAX_TABUNGAN, "income": 15000000, "outcome": 5000000, "total_goals": 7},
    "monthly_goal": {"target": 5000000, "saved": 0, "avg_daily": 266000, "forecast_pct": 92},
    "recent_activity": [
        {"id":1,"type":"Deposit","icon":"vertical_align_bottom","description":"Added Rp 20.000 to Travel Fund","date":"10:42 AM","status":"completed"},
        {"id":2,"type":"Deposit","icon":"vertical_align_bottom","description":"Added Rp 50.000 to Laptop Fund","date":"09:15 AM","status":"in_progress"},
        {"id":3,"type":"Withdrawal","icon":"vertical_align_top","description":"Withdrew Rp 100.000 from Emergency Fund","date":"Kemarin","status":"completed"},
        {"id":4,"type":"Transfer","icon":"swap_horiz","description":"Transfer ke Vacation Fund","date":"Kemarin","status":"in_progress"},
    ],
}

def format_rupiah(amount) -> str:
    return f"Rp {int(amount):,}".replace(",", ".")

@app.template_filter('rupiah')
def rupiah_filter(value):
    try:
        return f"Rp {int(value):,}".replace(",", ".")
    except:
        return "Rp 0"

def persen_tabungan(total: int) -> int:
    return min(100, round(total / MAX_TABUNGAN * 100))

def enrich_goals(goals: list) -> list:
    out = []
    for g in goals:
        pct = min(100, round(g["saved"] / g["target"] * 100)) if g["target"] else 0
        pa = g.get("persen_alokasi")
        out.append({**g,
            "target_fmt":    format_rupiah(g["target"]),
            "saved_fmt":     format_rupiah(g["saved"]),
            "remaining":     max(0, g["target"] - g["saved"]),
            "remaining_fmt": format_rupiah(max(0, g["target"] - g["saved"])),
            "persen":        pct,
            "persen_alokasi": pa,
        })
    return out

def _total_allocated_pct(exclude_id: int = None) -> float:
    """Sum persen_alokasi of all active goals, optionally excluding one by id."""
    return sum(
        (g.get("persen_alokasi") or 0)
        for g in SAVINGS_GOALS
        if g["status"] == "active" and g.get("id") != exclude_id
    )

def upcoming_deadlines():
    active = [g for g in SAVINGS_GOALS if g["status"] == "active"]
    active.sort(key=lambda g: g["days_left"])
    return enrich_goals(active[:3])

def _tabungan_transactions() -> list:
    CATS = {"tabungan", "savings"}
    rows = [r for r in UPLOADED_TRANSACTIONS if str(r.get("Category","")).strip().lower() in CATS]
    rows.sort(key=lambda r: str(r.get("Period","") or ""), reverse=True)
    return rows

def calculate_financial_summary(transactions):
    total_income = 0
    total_expense = 0

    for r in transactions:
        jenis = str(r.get("Income/Expense", "")).strip()
        amount = r.get("IDR", 0)

        try:
            amount = float(str(amount).replace(",", ""))
        except:
            amount = 0

        # Card pemasukan hanya menghitung data dengan value tepat 'Income'
        if jenis == "Income":
            total_income += amount
        elif jenis.lower().startswith("exp"):
            total_expense += amount

    return total_income, total_expense

def calculate_monthly_savings(transactions):
    """Sum IDR from Category='Savings' rows for the current month."""
    now = datetime.now()
    total = 0
    for r in transactions:
        cat = str(r.get("Category", "")).strip().lower()
        if cat != "savings":
            continue
        period_raw = str(r.get("Period", "") or "")
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(period_raw[:10], "%Y-%m-%d")
            if dt.year == now.year and dt.month == now.month:
                total += float(str(r.get("IDR", 0)).replace(",", ""))
        except:
            pass
    return int(total)

def calculate_total_tabungan(transactions):
    """Accumulate IDR from rows where Category is 'Savings' (case-insensitive)."""
    total = 0
    for r in transactions:
        cat = str(r.get("Category", "")).strip().lower()
        if cat == "savings":
            try:
                total += float(str(r.get("IDR", 0)).replace(",", ""))
            except:
                pass
    return int(total)

def calculate_analytics_from_transactions(transactions):
    """
    Build monthly income/expense data from transactions.
    Income/Expense column: 'Income' (exact match) → income, 'Exp.' → expense.
    Data dengan value selain 'Income' tidak dihitung sebagai pemasukan.
    Returns dict keyed by year with labels, income, outcome arrays.
    """
    from collections import defaultdict
    MONTHS_ID = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Ags","Sep","Okt","Nov","Des"]

    # bucket: year -> month_idx -> {income, outcome}
    data = defaultdict(lambda: {"income": [0]*12, "outcome": [0]*12})

    for r in transactions:
        period_raw = str(r.get("Period", "") or "")
        jenis = str(r.get("Income/Expense", "")).strip()
        try:
            amount = float(str(r.get("IDR", 0)).replace(",", ""))
        except:
            amount = 0

        # parse year & month from period string (e.g. "2026-04-15 12:23:06")
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(period_raw[:10], "%Y-%m-%d")
            year = dt.year
            month = dt.month - 1  # 0-indexed
        except:
            continue

        # Card pemasukan hanya menghitung data dengan value tepat 'Income'
        if jenis == "Income":
            data[year]["income"][month] += amount
        elif jenis.lower().startswith("exp"):
            data[year]["outcome"][month] += amount

    result = {}
    for year, d in data.items():
        result[year] = {
            "labels": MONTHS_ID,
            "income":  [int(v) for v in d["income"]],
            "outcome": [int(v) for v in d["outcome"]],
        }
    return result

def count_active_goals():
    if not os.path.exists(GOALS_FILE):
        return 0

    df = pd.read_excel(GOALS_FILE)
    df.columns = [c.strip().lower() for c in df.columns]

    if "status" not in df.columns:
        return 0

    return len(df[df["status"].str.lower() == "active"])



# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    data  = {**DASHBOARD_DATA}

    # =========================
    # Dynamic calculations
    # =========================
    total_income, total_expense = calculate_financial_summary(UPLOADED_TRANSACTIONS)
    total_goals = count_active_goals()
    total_tabungan_from_data = calculate_total_tabungan(UPLOADED_TRANSACTIONS)

    # inject ke summary
    data["summary"]["income"] = total_income
    data["summary"]["outcome"] = total_expense
    data["summary"]["total_goals"] = total_goals
    data["summary"]["total_tabungan"] = total_tabungan_from_data
    # =========================

    s     = data["summary"]
    total = s["total_tabungan"]

    s["total_tabungan_fmt"] = format_rupiah(total)
    s["persen_completed"]   = persen_tabungan(total)
    s["max_fmt"]            = format_rupiah(MAX_TABUNGAN)

    mg = data["monthly_goal"]
    # Auto-calculate "sudah ditabung bulan ini" from transactions Category=Savings
    monthly_savings_from_tx = calculate_monthly_savings(UPLOADED_TRANSACTIONS)
    if monthly_savings_from_tx > 0:
        mg["saved"] = monthly_savings_from_tx
    mg["persen"]        = min(100, round(mg["saved"] / mg["target"] * 100)) if mg["target"] else 0
    mg["target_fmt"]    = format_rupiah(mg["target"])
    mg["saved_fmt"]     = format_rupiah(mg["saved"])
    mg["avg_daily_fmt"] = f"Rp {mg['avg_daily'] // 1000}k"
    mg["sisa_fmt"]      = format_rupiah(mg["target"] - mg["saved"])

    data["upcoming_deadlines"]    = upcoming_deadlines()
    # Build available_years from transaction Period field (relative to actual data)
    tx_years = set()
    for r in UPLOADED_TRANSACTIONS:
        period_raw = str(r.get("Period", "") or "")
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(period_raw[:10], "%Y-%m-%d")
            tx_years.add(dt.year)
        except:
            pass
    # Merge with MONTHLY_INCOME_DATA keys so chart still works if tx is empty
    all_avail_years = tx_years | set(MONTHLY_INCOME_DATA.keys()) if tx_years else set(MONTHLY_INCOME_DATA.keys())
    data["available_years"]       = sorted(all_avail_years, reverse=True)
    data["tabungan_transactions"] = _tabungan_transactions()

    return render_template("dashboard.html", data=data)


@app.route("/savings-goals")
def savings_goals_page():
    all_goals = enrich_goals(SAVINGS_GOALS)
    active    = [g for g in all_goals if g["status"] == "active"]
    completed = [g for g in all_goals if g["status"] == "completed"]
    cat_map   = {}
    for g in active:
        cat = g["category"]
        if cat not in cat_map:
            cat_map[cat] = {"category": cat, "count": 0, "total_target": 0, "total_saved": 0}
        cat_map[cat]["count"] += 1
        cat_map[cat]["total_target"] += g["target"]
        cat_map[cat]["total_saved"]  += g["saved"]
    categories = []
    for cat, v in cat_map.items():
        pct = round(v["total_saved"] / v["total_target"] * 100) if v["total_target"] else 0
        categories.append({**v, "persen": pct,
                           "total_target_fmt": format_rupiah(v["total_target"]),
                           "total_saved_fmt":  format_rupiah(v["total_saved"])})
    return render_template("savings_goals.html",
                           data=DASHBOARD_DATA,
                           active_goals=active,
                           completed_goals=completed,
                           categories=categories,
                           success=request.args.get("success"),
                           error=request.args.get("error"))


@app.route("/savings-goals/upload", methods=["POST"])
def savings_goals_upload():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".xlsx", ".xls")):
        return redirect(url_for("savings_goals_page") + "?error=Format+file+harus+.xlsx")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(f.read()), read_only=True, data_only=True)
        ws = wb.active
        rows_iter  = ws.iter_rows(values_only=True)
        header_raw = next(rows_iter, None)
        if not header_raw:
            return redirect(url_for("savings_goals_page") + "?error=File+kosong")
        header = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(header_raw)]
        global SAVINGS_GOALS, _next_goal_id
        new_goals = []
        max_id    = 0
        for row in rows_iter:
            if all(v is None for v in row): continue
            g = dict(zip(header, row))
            g["id"]       = int(g.get("id") or 0)
            g["target"]   = int(g.get("target") or 0)
            g["saved"]    = int(g.get("saved")  or 0)
            g["deadline"] = str(g.get("deadline") or "")
            g["status"]   = str(g.get("status")   or "active")
            g["name"]     = str(g.get("name")     or "")
            g["icon"]     = str(g.get("icon")     or "savings")
            g["category"] = str(g.get("category") or "Lainnya")
            g["days_left"] = compute_days_left(g["deadline"])
            raw_pa = g.get("persen_alokasi")
            try:
                g["persen_alokasi"] = float(raw_pa) if raw_pa not in (None, "", "None") else None
            except:
                g["persen_alokasi"] = None
            new_goals.append(g)
            if g["id"] > max_id: max_id = g["id"]
        SAVINGS_GOALS.clear()
        SAVINGS_GOALS.extend(new_goals)
        _next_goal_id = max_id + 1
        _save_goals(SAVINGS_GOALS)
        DASHBOARD_DATA["summary"]["total_goals"] = len([g for g in SAVINGS_GOALS if g["status"] == "active"])
        return redirect(url_for("savings_goals_page") + f"?success={len(new_goals)}")
    except Exception as e:
        return redirect(url_for("savings_goals_page") + f"?error={str(e)[:80]}")


@app.route("/savings-goals/download")
def savings_goals_download():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Goals"
    ws.append(GOALS_HEADERS)
    for g in SAVINGS_GOALS:
        ws.append([g.get(h) for h in GOALS_HEADERS])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"savings_goals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/transactions", methods=["GET"])
def transactions():
    return render_template("transactions.html",
                           data=DASHBOARD_DATA,
                           rows=UPLOADED_TRANSACTIONS,
                           success=request.args.get("success"),
                           error=request.args.get("error"),
                           anchor=request.args.get("anchor", ""))

@app.route("/transactions/upload", methods=["POST"])
def transactions_upload():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".xlsx", ".xls")):
        return redirect(url_for("transactions") + "?error=Format+file+harus+.xlsx")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(f.read()), read_only=True, data_only=True)
        ws = wb.active
        rows_iter  = ws.iter_rows(values_only=True)
        header_raw = next(rows_iter, None)
        if not header_raw:
            return redirect(url_for("transactions") + "?error=File+kosong")
        header = [str(h).strip() if h is not None else f"Kolom{i+1}" for i, h in enumerate(header_raw)]
        new_rows = []
        for row in rows_iter:
            if all(v is None for v in row): continue
            d = dict(zip(header, row))
            for k, v in d.items():
                if isinstance(v, datetime): d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            new_rows.append(d)
        # UPLOADED_TRANSACTIONS.clear()
        # UPLOADED_TRANSACTIONS.extend(new_rows)
        # save_transactions(UPLOADED_TRANSACTIONS)

        # ambil data lama dari Excel (biar sync)
        existing_data = load_transactions()

        # gabungkan
        combined = existing_data + new_rows

        # update memory
        UPLOADED_TRANSACTIONS.clear()
        UPLOADED_TRANSACTIONS.extend(combined)

        # save ke Excel
        save_transactions(UPLOADED_TRANSACTIONS)

        # Alokasi baris Savings baru ke goals
        savings_amount = sum(_get_amount(r) for r in new_rows if _is_savings_row(r))
        if savings_amount > 0:
            _allocate_to_goals(savings_amount)

        return redirect(url_for("transactions") + f"?success={len(new_rows)}&anchor=data-table-section")
    except Exception as e:
        return redirect(url_for("transactions") + f"?error={str(e)[:80]}")

@app.route("/transactions/delete/<int:index>", methods=["POST"])
def transaction_delete(index):
    if 0 <= index < len(UPLOADED_TRANSACTIONS):
        row = UPLOADED_TRANSACTIONS[index]
        amount = _get_amount(row) if _is_savings_row(row) else 0
        UPLOADED_TRANSACTIONS.pop(index)
        save_transactions(UPLOADED_TRANSACTIONS)
        if amount > 0:
            _deallocate_from_goals(amount)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Index tidak valid"}), 400

@app.route("/transactions/edit-by-index/<int:index>", methods=["POST"])
def transaction_edit_by_index(index):
    body = request.get_json(silent=True) or {}
    if 0 <= index < len(UPLOADED_TRANSACTIONS):
        row = UPLOADED_TRANSACTIONS[index]

        # Catat kondisi sebelum edit
        was_savings = _is_savings_row(row)
        old_amount  = _get_amount(row) if was_savings else 0

        # Terapkan perubahan
        for key, val in body.items():
            row[key] = val

        # Kondisi setelah edit
        is_savings  = _is_savings_row(row)
        new_amount  = _get_amount(row) if is_savings else 0

        save_transactions(UPLOADED_TRANSACTIONS)

        # Sesuaikan goals berdasarkan delta
        delta = new_amount - old_amount
        if delta > 0:
            _allocate_to_goals(delta)
        elif delta < 0:
            _deallocate_from_goals(abs(delta))

        return jsonify({"success": True, "row": row})
    return jsonify({"success": False, "message": "Index tidak valid"}), 404

@app.route("/transactions/edit/<string:row_id>", methods=["POST"])
def transaction_edit(row_id):
    body = request.get_json(silent=True) or {}

    for i, row in enumerate(UPLOADED_TRANSACTIONS):
        if str(row.get("id")) == row_id:
            for key, val in body.items():
                if key in row:
                    row[key] = val

            save_transactions(UPLOADED_TRANSACTIONS)
            return jsonify({"success": True, "row": row})

    return jsonify({"success": False, "message": "ID tidak ditemukan"}), 404

@app.route("/transactions/clear", methods=["POST"])
def clear_transactions():
    global UPLOADED_TRANSACTIONS

    # 1. clear memory
    UPLOADED_TRANSACTIONS.clear()

    # 2. hapus file Excel
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)

    # 3. reset semua saved goals ke 0 karena semua transaksi dihapus
    for g in SAVINGS_GOALS:
        g["saved"] = 0
        g["status"] = "active" if g["target"] > 0 else g["status"]
        g["days_left"] = compute_days_left(g["deadline"])
    _save_goals(SAVINGS_GOALS)

    return redirect(url_for("transactions"))

@app.route("/transactions/add", methods=["POST"])
def transactions_add_manual():
    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"success": False, "message": "Data tidak valid"}), 400
    # Ensure datetime fields are strings
    for k, v in body.items():
        if isinstance(v, datetime):
            body[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    body["id"] = str(uuid.uuid4())
    UPLOADED_TRANSACTIONS.append(body)
    save_transactions(UPLOADED_TRANSACTIONS)
    # Allocate savings if category is Savings
    if _is_savings_row(body):
        amt = _get_amount(body)
        if amt > 0:
            _allocate_to_goals(amt)
    return jsonify({"success": True, "message": "Transaksi berhasil ditambahkan", "row": body, "index": len(UPLOADED_TRANSACTIONS)-1})

@app.route("/transactions/download")
def transactions_download():
    if not UPLOADED_TRANSACTIONS:
        return redirect(url_for("transactions") + "?error=Tidak+ada+data+untuk+diunduh")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Histori Transaksi"
    headers = list(UPLOADED_TRANSACTIONS[0].keys())
    ws.append(headers)
    for row in UPLOADED_TRANSACTIONS:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"histori_transaksi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/analytics")
def api_analytics():
    year = request.args.get("year", type=int, default=2026)
    mode = request.args.get("mode", "both")

    # Try to build from real transactions first
    tx_analytics = calculate_analytics_from_transactions(UPLOADED_TRANSACTIONS)

    # Merge with static data (static as fallback base, tx overrides)
    merged = {}
    all_years = set(MONTHLY_INCOME_DATA.keys()) | set(tx_analytics.keys())
    for y in all_years:
        if y in tx_analytics and any(v > 0 for v in tx_analytics[y]["income"] + tx_analytics[y]["outcome"]):
            # Use real transaction data when available
            merged[y] = tx_analytics[y]
        elif y in MONTHLY_INCOME_DATA:
            merged[y] = MONTHLY_INCOME_DATA[y]

    data = merged.get(year, MONTHLY_INCOME_DATA.get(2026))
    result = {"labels": data["labels"], "year": year}
    if mode in ("income", "both"):  result["income"]  = data["income"]
    if mode in ("outcome", "both"): result["outcome"] = data["outcome"]
    return jsonify(result)

@app.route("/api/analytics/years")
def api_analytics_years():
    tx_analytics = calculate_analytics_from_transactions(UPLOADED_TRANSACTIONS)
    all_years = set(MONTHLY_INCOME_DATA.keys()) | set(tx_analytics.keys())
    return jsonify(sorted(all_years, reverse=True))

@app.route("/api/activity")
def api_activity():
    f    = request.args.get("filter", "newest")
    acts = DASHBOARD_DATA["recent_activity"]
    if f == "active": acts = [a for a in acts if a["status"] == "in_progress"]
    return jsonify(acts)

@app.route("/api/summary")
def api_summary():
    s     = DASHBOARD_DATA["summary"]
    total = s["total_tabungan"]
    return jsonify({**s, "total_tabungan_fmt": format_rupiah(total), "persen_completed": persen_tabungan(total)})

@app.route("/api/max-tabungan", methods=["POST"])
def api_set_max_tabungan():
    global MAX_TABUNGAN
    body = request.get_json(silent=True) or {}
    new_max = int(body.get("max_tabungan", 0))
    if new_max < 1_000_000:
        return jsonify({"success": False, "message": "Nilai terlalu kecil"}), 400
    MAX_TABUNGAN = new_max
    total = calculate_total_tabungan(UPLOADED_TRANSACTIONS)
    persen = min(100, round(total / MAX_TABUNGAN * 100)) if MAX_TABUNGAN else 0
    return jsonify({
        "success": True,
        "max_tabungan": MAX_TABUNGAN,
        "max_fmt": format_rupiah(MAX_TABUNGAN),
        "persen": persen,
    })

@app.route("/api/monthly-goal", methods=["GET"])
def api_monthly_goal_get():
    mg = DASHBOARD_DATA["monthly_goal"]
    return jsonify({"target": mg["target"], "saved": mg["saved"]})

@app.route("/api/monthly-goal", methods=["POST"])
def api_monthly_goal_update():
    body   = request.get_json(silent=True) or {}
    target = int(body.get("target", 0))
    saved  = int(body.get("saved",  0))
    if target <= 0:
        return jsonify({"success": False, "message": "Target tidak valid"}), 400
    mg = DASHBOARD_DATA["monthly_goal"]
    mg["target"] = target; mg["saved"] = saved
    mg["avg_daily"] = round(saved / 30) if saved else 0
    persen = min(100, round(saved / target * 100))
    return jsonify({"success": True, "message": "Target bulanan berhasil diperbarui",
        "target_fmt": format_rupiah(target), "saved_fmt": format_rupiah(saved),
        "persen": persen, "sisa_fmt": format_rupiah(max(0, target - saved)),
        "avg_daily_fmt": f"Rp {mg['avg_daily'] // 1000}k"})

@app.route("/api/goals", methods=["GET"])
def api_goals_list():
    return jsonify({
        "goals": enrich_goals(SAVINGS_GOALS),
        "total_allocated_pct": _total_allocated_pct()
    })

@app.route("/api/goals", methods=["POST"])
def api_goals_create():
    global _next_goal_id
    body = request.get_json(silent=True) or {}
    for field in ["name", "category", "target", "deadline"]:
        if not body.get(field):
            return jsonify({"success": False, "message": f"Field '{field}' wajib diisi"}), 400
    icon_map = {"Elektronik":"devices","Wisata":"flight","Kendaraan":"directions_car","Properti":"home",
                "Pendidikan":"school","Investasi":"trending_up","Asuransi":"health_and_safety","Lainnya":"savings"}
    # Handle persen_alokasi
    pa_raw = body.get("persen_alokasi")
    try:
        pa = float(pa_raw) if pa_raw not in (None, "", "null") else None
    except:
        pa = None
    # Validate: if pa provided, check total does not exceed 100
    if pa is not None:
        current_total = _total_allocated_pct()
        if current_total >= 100:
            return jsonify({"success": False, "message": f"Total alokasi sudah mencapai 100%. Edit persen dari goal lain terlebih dahulu sebelum menambah goal baru dengan alokasi."}), 400
        if pa <= 0 or pa > 100:
            return jsonify({"success": False, "message": "Persen alokasi harus antara 1–100"}), 400
        if current_total + pa > 100:
            sisa = 100 - current_total
            return jsonify({"success": False, "message": f"Total alokasi akan melebihi 100%. Sisa kapasitas: {sisa:.1f}%"}), 400
    target = int(body["target"]); saved = int(body.get("saved", 0))
    new_goal = {"id":_next_goal_id,"name":body["name"],"icon":icon_map.get(body["category"],"savings"),
                "category":body["category"],"target":target,"saved":saved,"deadline":body["deadline"],
                "days_left":compute_days_left(body["deadline"]),"status":"completed" if saved >= target else "active",
                "persen_alokasi": pa}
    SAVINGS_GOALS.append(new_goal); _next_goal_id += 1
    _save_goals(SAVINGS_GOALS)
    DASHBOARD_DATA["summary"]["total_goals"] = len([g for g in SAVINGS_GOALS if g["status"] == "active"])
    return jsonify({"success": True, "message": f"Goal '{body['name']}' berhasil dibuat", "goal": enrich_goals([new_goal])[0],
                    "total_allocated_pct": _total_allocated_pct()})

@app.route("/api/goals/allocation-info", methods=["GET"])
def api_goals_allocation_info():
    return jsonify({"total_allocated_pct": _total_allocated_pct()})

@app.route("/api/goals/<int:goal_id>", methods=["GET"])
def api_goals_get(goal_id):
    goal = next((g for g in SAVINGS_GOALS if g["id"] == goal_id), None)
    if not goal: return jsonify({"success": False, "message": "Goal tidak ditemukan"}), 404
    return jsonify(enrich_goals([goal])[0])

@app.route("/api/goals/<int:goal_id>", methods=["PUT"])
def api_goals_update(goal_id):
    goal = next((g for g in SAVINGS_GOALS if g["id"] == goal_id), None)
    if not goal: return jsonify({"success": False, "message": "Goal tidak ditemukan"}), 404
    body = request.get_json(silent=True) or {}
    icon_map = {"Elektronik":"devices","Wisata":"flight","Kendaraan":"directions_car","Properti":"home",
                "Pendidikan":"school","Investasi":"trending_up","Asuransi":"health_and_safety","Lainnya":"savings"}
    if "name"     in body: goal["name"]     = body["name"]
    if "category" in body: goal["category"] = body["category"]; goal["icon"] = icon_map.get(body["category"], goal["icon"])
    if "target"   in body: goal["target"]   = int(body["target"])
    if "saved"    in body: goal["saved"]    = int(body["saved"])
    if "deadline" in body: goal["deadline"] = body["deadline"]; goal["days_left"] = compute_days_left(body["deadline"])
    if "persen_alokasi" in body:
        pa_raw = body["persen_alokasi"]
        try:
            pa = float(pa_raw) if pa_raw not in (None, "", "null") else None
        except:
            pa = None
        if pa is not None:
            current_total = _total_allocated_pct(exclude_id=goal["id"])
            if pa <= 0 or pa > 100:
                return jsonify({"success": False, "message": "Persen alokasi harus antara 1–100"}), 400
            if current_total + pa > 100:
                sisa = 100 - current_total
                return jsonify({"success": False, "message": f"Total alokasi akan melebihi 100%. Sisa kapasitas: {sisa:.1f}%"}), 400
        goal["persen_alokasi"] = pa
    goal["status"] = "completed" if goal["saved"] >= goal["target"] else "active"
    _save_goals(SAVINGS_GOALS)
    DASHBOARD_DATA["summary"]["total_goals"] = len([g for g in SAVINGS_GOALS if g["status"] == "active"])
    return jsonify({"success": True, "message": f"Goal '{goal['name']}' berhasil diperbarui", "goal": enrich_goals([goal])[0],
                    "total_allocated_pct": _total_allocated_pct()})

@app.route("/api/goals/<int:goal_id>", methods=["DELETE"])
def api_goals_delete(goal_id):
    global SAVINGS_GOALS
    goal = next((g for g in SAVINGS_GOALS if g["id"] == goal_id), None)
    if not goal: return jsonify({"success": False, "message": "Goal tidak ditemukan"}), 404
    SAVINGS_GOALS = [g for g in SAVINGS_GOALS if g["id"] != goal_id]
    _save_goals(SAVINGS_GOALS)
    DASHBOARD_DATA["summary"]["total_goals"] = len([g for g in SAVINGS_GOALS if g["status"] == "active"])
    return jsonify({"success": True, "message": f"Goal '{goal['name']}' berhasil dihapus"})

@app.route("/api/add-funds", methods=["POST"])
def api_add_funds():
    body   = request.get_json(silent=True) or {}
    amount = int(body.get("amount", 0))
    goal   = body.get("goal", "General Savings")
    if amount <= 0: return jsonify({"success": False, "message": "Jumlah tidak valid"}), 400
    new_total = min(MAX_TABUNGAN, DASHBOARD_DATA["summary"]["total_tabungan"] + amount)
    DASHBOARD_DATA["summary"]["total_tabungan"] = new_total
    DASHBOARD_DATA["recent_activity"].insert(0, {"id":len(DASHBOARD_DATA["recent_activity"])+1,"type":"Deposit",
        "icon":"vertical_align_bottom","description":f"Added {format_rupiah(amount)} to {goal}",
        "date":datetime.now().strftime("%H:%M"),"status":"completed"})
    return jsonify({"success":True,"message":f"Berhasil menambahkan {format_rupiah(amount)} ke {goal}",
                    "new_total":new_total,"new_total_fmt":format_rupiah(new_total),"new_persen":persen_tabungan(new_total)})

@app.route("/api/dashboard-summary")
def api_dashboard_summary():
    year = request.args.get("year", type=int, default=2026)
    tx_analytics = calculate_analytics_from_transactions(UPLOADED_TRANSACTIONS)
    if year in tx_analytics and any(v > 0 for v in tx_analytics[year]["income"] + tx_analytics[year]["outcome"]):
        data = tx_analytics[year]
    else:
        data = MONTHLY_INCOME_DATA.get(year, MONTHLY_INCOME_DATA[2026])
    total_income  = sum(v for v in data["income"]  if v)
    total_outcome = sum(v for v in data["outcome"] if v)
    return jsonify({"year":year,"income":total_income,"income_fmt":format_rupiah(total_income),
                    "outcome":total_outcome,"outcome_fmt":format_rupiah(total_outcome)})

@app.route("/api/tabungan-transactions")
def api_tabungan_transactions():
    rows = _tabungan_transactions()
    result = []
    for r in rows:
        result.append({
            "Period":   str(r.get("Period") or ""),
            "Category": str(r.get("Category") or ""),
            "IDR":      r.get("IDR", 0),
            "Note":     str(r.get("Note") or ""),
        })
    return jsonify(result)

app.jinja_env.filters['enumerate'] = enumerate

if __name__ == "__main__":
    app.run(debug=True, port=5000)
