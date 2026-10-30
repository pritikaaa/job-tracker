import sqlite3
from datetime import date
from flask import Flask, g, render_template, request, redirect, url_for, abort

DB = "jobs.db"
STATUSES = ["Applied", "Heard Back", "Interviewing", "Offered", "Rejected"]

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB)
    db.execute(
        """CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Applied',
            applied_on TEXT,
            link TEXT,
            contact TEXT,
            notes TEXT,
            updated_on TEXT
        )"""
    )
    db.commit()
    db.close()


def form_values():
    status = request.form.get("status", "Applied")
    if status not in STATUSES:
        status = "Applied"
    return (
        request.form["company"].strip(),
        request.form["role"].strip(),
        status,
        request.form.get("applied_on") or None,
        request.form.get("link", "").strip(),
        request.form.get("contact", "").strip(),
        request.form.get("notes", "").strip(),
        date.today().isoformat(),
    )


@app.route("/")
def index():
    db = get_db()
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM applications WHERE 1=1"
    args = []
    if status in STATUSES:
        sql += " AND status = ?"
        args.append(status)
    if q:
        sql += " AND (company LIKE ? OR role LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY applied_on DESC, id DESC"
    rows = db.execute(sql, args).fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in db.execute("SELECT status, COUNT(*) c FROM applications GROUP BY status"):
        counts[r["status"]] = r["c"]
    total = sum(counts.values())
    return render_template(
        "index.html", rows=rows, counts=counts, total=total,
        statuses=STATUSES, current=status, q=q,
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        db = get_db()
        db.execute(
            "INSERT INTO applications (company, role, status, applied_on, link, contact, notes, updated_on)"
            " VALUES (?,?,?,?,?,?,?,?)",
            form_values(),
        )
        db.commit()
        return redirect(url_for("index"))
    return render_template(
        "form.html", job=None, statuses=STATUSES, today=date.today().isoformat()
    )


@app.route("/edit/<int:job_id>", methods=["GET", "POST"])
def edit(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM applications WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        abort(404)
    if request.method == "POST":
        db.execute(
            "UPDATE applications SET company=?, role=?, status=?, applied_on=?, link=?,"
            " contact=?, notes=?, updated_on=? WHERE id=?",
            (*form_values(), job_id),
        )
        db.commit()
        return redirect(url_for("index"))
    return render_template("form.html", job=job, statuses=STATUSES, today="")


@app.route("/status/<int:job_id>", methods=["POST"])
def set_status(job_id):
    status = request.form.get("status")
    if status in STATUSES:
        db = get_db()
        db.execute(
            "UPDATE applications SET status=?, updated_on=? WHERE id=?",
            (status, date.today().isoformat(), job_id),
        )
        db.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:job_id>", methods=["POST"])
def delete(job_id):
    db = get_db()
    db.execute("DELETE FROM applications WHERE id = ?", (job_id,))
    db.commit()
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
