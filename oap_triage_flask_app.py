from __future__ import annotations

import io
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template_string, request, send_file, url_for, redirect
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "drhnid")
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash("ChangeMe123!")
)

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USERNAME:
        return User(ADMIN_USERNAME)
    return None
DATABASE = "oap_triage.db"
DEFAULT_SERVICE = "Service des urgences - Salle de déchocage - Hôpital Provincial CHPI"
AUTHOR_NAME = "Dr. Karim Hnid, MD"
AUTHOR_TITLE = "Emergency Physician | Medical Author and Researcher | Morocco"
AUTHOR_EMAIL = "hniddata@gmail.com"
AUTHOR_ORCID = "0000-0003-0122-2783"
AUTHOR_RESEARCHER_ID = "R-3425-2018"
AUTHOR_YOUTUBE = "https://www.youtube.com/@hnid68"
PROSPERO_TITLE = "Poor pharmaceutical quality, medicinal impurities, and cancer risk"
PROSPERO_ID = "CRD420261335075"
PROSPERO_URL = "https://www.crd.york.ac.uk/PROSPERO/view/CRD420261335075"
PROTOCOL_URL = "https://www.crd.york.ac.uk/PROSPEROFILES/e58ed2a98e3ba4232a889eeee508a377.pdf"
PROSPERO_NOTE = (
    "Dr. Hnid is currently leading an ongoing PROSPERO-registered systematic review entitled "
    "‘Poor pharmaceutical quality, medicinal impurities, and cancer risk’ (CRD420261335075), "
    "an oncology-relevant evidence synthesis project focused on potentially carcinogenic exposure pathways "
    "linked to medicine quality. This project reflects his expanding commitment to structured evidence synthesis "
    "in an area of direct relevance to global oncology, drug safety, and public health in resource-constrained settings. "
    "It is intended not only as a systematic review, but also as a foundation for future collaborative work in cancer risk assessment, "
    "methodological strengthening, and internationally connected research development. Given the scope of the review, the project would "
    "particularly benefit from institutional bibliographic access, full-text literature support, methodological mentorship, screening and "
    "data-extraction infrastructure, and ideally financial or in-kind support to ensure comprehensive and rigorous completion."
)

DISCLAIMER = (
    "Prototype d’aide à la décision clinique uniquement. Ne remplace pas le jugement médical. "
    "Toute détresse respiratoire, instabilité hémodynamique, suspicion de syndrome coronarien aigu, "
    "trouble du rythme grave, ou aggravation après traitement initial impose une réévaluation médicale urgente "
    "et la considération d’un transfert vers un niveau de soins supérieur."
)

DISPOSITION_LABELS = {
    "TRANSFER_CHU_SAMU": "Transfert CHU / SAMU",
    "LOCAL_DECHOCAGE_STRICT": "Déchoquage local strict",
    "LOCAL_OBSERVATION_AND_REASSESS": "Observation locale + réévaluation",
    "OUT_OF_SCOPE_ALT_DIAGNOSIS": "Hors périmètre / diagnostic alternatif",
}

BOOL_FIELDS = [
    "known_hf",
    "valvular_disease_moderate_severe",
    "altered_mental_status",
    "cold_extremities",
    "oliguria",
    "lactate_high",
    "stemi_or_ongoing_ischemia",
    "malignant_arrhythmia",
    "av_block_high_grade",
    "troponin_positive",
    "niv_started",
    "intubation_needed",
    "fever_or_sepsis_suspicion",
    "reassessment_done",
    "dyspnea_improved",
    "able_3min_walk_test",
    "walk_test_failed",
]

FLOAT_FIELDS = [
    "sbp",
    "dbp",
    "map_value",
    "hr",
    "rr",
    "spo2",
    "creatinine_mg_dl",
    "spo2_after",
    "rr_after",
    "sbp_after",
]

TEXT_FIELDS = [
    "visit_date",
    "service_name",
    "duty_physician",
    "duty_anesthetist",
    "patient_code",
    "full_name",
    "sex",
    "notes",
    "medical_history",
    "current_medications",
    "treated_pathologies",
]

INPUT_FIELDS = TEXT_FIELDS + BOOL_FIELDS + FLOAT_FIELDS + ["age"]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, column_name: str, column_def: str) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(patients)").fetchall()}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE patients ADD COLUMN {column_name} {column_def}")


def init_db() -> None:
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            visit_date TEXT,
            service_name TEXT,
            duty_physician TEXT,
            duty_anesthetist TEXT,
            patient_code TEXT,
            full_name TEXT,
            age INTEGER,
            sex TEXT,
            known_hf INTEGER,
            valvular_disease_moderate_severe INTEGER,
            sbp REAL,
            dbp REAL,
            map_value REAL,
            hr REAL,
            rr REAL,
            spo2 REAL,
            altered_mental_status INTEGER,
            cold_extremities INTEGER,
            oliguria INTEGER,
            lactate_high INTEGER,
            stemi_or_ongoing_ischemia INTEGER,
            malignant_arrhythmia INTEGER,
            av_block_high_grade INTEGER,
            creatinine_mg_dl REAL,
            troponin_positive INTEGER,
            niv_started INTEGER,
            intubation_needed INTEGER,
            fever_or_sepsis_suspicion INTEGER,
            reassessment_done INTEGER,
            spo2_after REAL,
            rr_after REAL,
            sbp_after REAL,
            dyspnea_improved INTEGER,
            able_3min_walk_test INTEGER,
            walk_test_failed INTEGER,
            notes TEXT,
            medical_history TEXT,
            current_medications TEXT,
            treated_pathologies TEXT,
            disposition TEXT,
            score INTEGER,
            reasons TEXT,
            red_flags TEXT,
            reassessment_failure TEXT
        )
        """
    )
    # Migration de sécurité si la base existe déjà
    ensure_column(conn, "visit_date", "TEXT")
    ensure_column(conn, "service_name", "TEXT")
    ensure_column(conn, "duty_physician", "TEXT")
    ensure_column(conn, "duty_anesthetist", "TEXT")
    ensure_column(conn, "medical_history", "TEXT")
    ensure_column(conn, "current_medications", "TEXT")
    ensure_column(conn, "treated_pathologies", "TEXT")
    conn.commit()
    conn.close()


def now_local_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y", "on", "oui"):
        return True
    if s in ("false", "0", "no", "n", "off", "non", ""):
        return False
    return None


def bool_to_db(v: Optional[bool]) -> Optional[int]:
    if v is None:
        return None
    return 1 if v else 0


def db_to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    return bool(v)


def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def build_input(data: Dict[str, Any]) -> Dict[str, Any]:
    visit_date = str(data.get("visit_date", "")).strip() or now_local_str()
    service_name = str(data.get("service_name", "")).strip() or DEFAULT_SERVICE
    return {
        "visit_date": visit_date,
        "service_name": service_name,
        "duty_physician": str(data.get("duty_physician", "")).strip(),
        "duty_anesthetist": str(data.get("duty_anesthetist", "")).strip(),
        "patient_code": str(data.get("patient_code", "")).strip(),
        "full_name": str(data.get("full_name", "")).strip(),
        "age": to_int(data.get("age")),
        "sex": str(data.get("sex", "")).strip(),
        "known_hf": to_bool(data.get("known_hf")),
        "valvular_disease_moderate_severe": to_bool(data.get("valvular_disease_moderate_severe")),
        "sbp": to_float(data.get("sbp")),
        "dbp": to_float(data.get("dbp")),
        "map_value": to_float(data.get("map_value")),
        "hr": to_float(data.get("hr")),
        "rr": to_float(data.get("rr")),
        "spo2": to_float(data.get("spo2")),
        "altered_mental_status": to_bool(data.get("altered_mental_status")),
        "cold_extremities": to_bool(data.get("cold_extremities")),
        "oliguria": to_bool(data.get("oliguria")),
        "lactate_high": to_bool(data.get("lactate_high")),
        "stemi_or_ongoing_ischemia": to_bool(data.get("stemi_or_ongoing_ischemia")),
        "malignant_arrhythmia": to_bool(data.get("malignant_arrhythmia")),
        "av_block_high_grade": to_bool(data.get("av_block_high_grade")),
        "creatinine_mg_dl": to_float(data.get("creatinine_mg_dl")),
        "troponin_positive": to_bool(data.get("troponin_positive")),
        "niv_started": to_bool(data.get("niv_started")),
        "intubation_needed": to_bool(data.get("intubation_needed")),
        "fever_or_sepsis_suspicion": to_bool(data.get("fever_or_sepsis_suspicion")),
        "reassessment_done": to_bool(data.get("reassessment_done")),
        "spo2_after": to_float(data.get("spo2_after")),
        "rr_after": to_float(data.get("rr_after")),
        "sbp_after": to_float(data.get("sbp_after")),
        "dyspnea_improved": to_bool(data.get("dyspnea_improved")),
        "able_3min_walk_test": to_bool(data.get("able_3min_walk_test")),
        "walk_test_failed": to_bool(data.get("walk_test_failed")),
        "medical_history": str(data.get("medical_history", "")).strip(),
        "current_medications": str(data.get("current_medications", "")).strip(),
        "treated_pathologies": str(data.get("treated_pathologies", "")).strip(),
        "notes": str(data.get("notes", "")).strip(),
    }


def compute_score(inp: Dict[str, Any]) -> int:
    score = 0
    if inp["valvular_disease_moderate_severe"] is True:
        score += 1
    if inp["hr"] is not None and inp["hr"] >= 110:
        score += 1
    if inp["creatinine_mg_dl"] is not None and inp["creatinine_mg_dl"] >= 1.8:
        score += 1
    if inp["troponin_positive"] is True:
        score += 1
    if inp["spo2"] is not None and inp["spo2"] < 90:
        score += 1
    if inp["rr"] is not None and inp["rr"] >= 30:
        score += 1
    if inp["sbp"] is not None and 90 <= inp["sbp"] < 100:
        score += 1
    return score


def failed_reassessment(inp: Dict[str, Any]) -> tuple[bool, List[str]]:
    failures: List[str] = []
    if inp["reassessment_done"] is not True:
        failures.append("Réévaluation non réalisée")
        return True, failures
    if inp["spo2_after"] is not None and inp["spo2_after"] < 90:
        failures.append("Hypoxémie persistante après traitement initial")
    if inp["rr_after"] is not None and inp["rr_after"] >= 28:
        failures.append("Tachypnée persistante après traitement initial")
    if inp["sbp_after"] is not None and inp["sbp_after"] < 100:
        failures.append("PAS basse après traitement initial")
    if inp["dyspnea_improved"] is False:
        failures.append("Dyspnée non améliorée après traitement initial")
    if inp["walk_test_failed"] is True:
        failures.append("Échec du test de marche")
    if inp["able_3min_walk_test"] is False:
        failures.append("Impossible de réaliser le test de marche")
    return len(failures) > 0, failures


def explain_decision(inp: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    red_flags: List[str] = []

    if inp["stemi_or_ongoing_ischemia"] is True:
        red_flags.append("Suspicion d’ischémie en cours / STEMI")
    if inp["malignant_arrhythmia"] is True:
        red_flags.append("Trouble du rythme malin")
    if inp["av_block_high_grade"] is True:
        red_flags.append("Bloc AV de haut degré")
    if inp["sbp"] is not None and inp["sbp"] < 90:
        red_flags.append("PAS < 90 mmHg")
    if inp["map_value"] is not None and inp["map_value"] < 60:
        red_flags.append("PAM < 60 mmHg")
    if inp["altered_mental_status"] is True:
        red_flags.append("Altération de l’état mental")
    if inp["cold_extremities"] is True:
        red_flags.append("Extrémités froides / hypoperfusion")
    if inp["oliguria"] is True:
        red_flags.append("Oligurie")
    if inp["lactate_high"] is True:
        red_flags.append("Lactate élevé / hypoperfusion possible")
    if inp["niv_started"] is True:
        red_flags.append("VNI requise")
    if inp["intubation_needed"] is True:
        red_flags.append("Intubation requise")

    score = compute_score(inp)

    if inp["valvular_disease_moderate_severe"] is True:
        reasons.append("Valvulopathie modérée/sévère")
    if inp["hr"] is not None and inp["hr"] >= 110:
        reasons.append("Fréquence cardiaque ≥ 110/min")
    if inp["creatinine_mg_dl"] is not None and inp["creatinine_mg_dl"] >= 1.8:
        reasons.append("Créatinine ≥ 1,8 mg/dL")
    if inp["troponin_positive"] is True:
        reasons.append("Troponine positive")
    if inp["spo2"] is not None and inp["spo2"] < 90:
        reasons.append("SpO2 < 90 %")
    if inp["rr"] is not None and inp["rr"] >= 30:
        reasons.append("Fréquence respiratoire ≥ 30/min")
    if inp["sbp"] is not None and 90 <= inp["sbp"] < 100:
        reasons.append("PAS entre 90 et 99 mmHg")

    if red_flags:
        return {
            "disposition": "TRANSFER_CHU_SAMU",
            "score": score,
            "reasons": reasons,
            "red_flags": red_flags,
            "reassessment_failure": [],
            "disclaimer": DISCLAIMER,
        }

    alt_diagnosis_likely = inp["fever_or_sepsis_suspicion"] is True and inp["known_hf"] is not True
    if alt_diagnosis_likely:
        return {
            "disposition": "OUT_OF_SCOPE_ALT_DIAGNOSIS",
            "score": score,
            "reasons": [
                "Un sepsis ou un processus infectieux peut être le diagnostic dominant plutôt qu’un OAP cardiogénique"
            ],
            "red_flags": [],
            "reassessment_failure": [],
            "disclaimer": DISCLAIMER,
        }

    failed, reassessment_failure = failed_reassessment(inp)
    if failed:
        return {
            "disposition": "TRANSFER_CHU_SAMU",
            "score": score,
            "reasons": reasons,
            "red_flags": [],
            "reassessment_failure": reassessment_failure,
            "disclaimer": DISCLAIMER,
        }

    disposition = "LOCAL_DECHOCAGE_STRICT" if score >= 3 else "LOCAL_OBSERVATION_AND_REASSESS"
    return {
        "disposition": disposition,
        "score": score,
        "reasons": reasons,
        "red_flags": [],
        "reassessment_failure": [],
        "disclaimer": DISCLAIMER,
    }


def serialize_decision_list(items: List[str]) -> str:
    return " | ".join(items)


def yn(name: str, form: Optional[Dict[str, Any]] = None) -> str:
    form = form or {}
    current = str(form.get(name, ""))

    def opt(value: str, label: str) -> str:
        selected = "selected" if current == value else ""
        return f'<option value="{value}" {selected}>{label}</option>'

    return (
        f'<select name="{name}">'
        + opt("", "Inconnu")
        + opt("true", "Oui")
        + opt("false", "Non")
        + "</select>"
    )


def save_patient(inp: Dict[str, Any], decision: Dict[str, Any]) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO patients (
            created_at, updated_at, visit_date, service_name, duty_physician, duty_anesthetist,
            patient_code, full_name, age, sex,
            known_hf, valvular_disease_moderate_severe, sbp, dbp, map_value, hr, rr, spo2,
            altered_mental_status, cold_extremities, oliguria, lactate_high,
            stemi_or_ongoing_ischemia, malignant_arrhythmia, av_block_high_grade,
            creatinine_mg_dl, troponin_positive, niv_started, intubation_needed,
            fever_or_sepsis_suspicion, reassessment_done, spo2_after, rr_after, sbp_after,
            dyspnea_improved, able_3min_walk_test, walk_test_failed,
            notes, medical_history, current_medications, treated_pathologies,
            disposition, score, reasons, red_flags, reassessment_failure
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        """,
        (
            now,
            now,
            inp["visit_date"],
            inp["service_name"],
            inp["duty_physician"],
            inp["duty_anesthetist"],
            inp["patient_code"],
            inp["full_name"],
            inp["age"],
            inp["sex"],
            bool_to_db(inp["known_hf"]),
            bool_to_db(inp["valvular_disease_moderate_severe"]),
            inp["sbp"],
            inp["dbp"],
            inp["map_value"],
            inp["hr"],
            inp["rr"],
            inp["spo2"],
            bool_to_db(inp["altered_mental_status"]),
            bool_to_db(inp["cold_extremities"]),
            bool_to_db(inp["oliguria"]),
            bool_to_db(inp["lactate_high"]),
            bool_to_db(inp["stemi_or_ongoing_ischemia"]),
            bool_to_db(inp["malignant_arrhythmia"]),
            bool_to_db(inp["av_block_high_grade"]),
            inp["creatinine_mg_dl"],
            bool_to_db(inp["troponin_positive"]),
            bool_to_db(inp["niv_started"]),
            bool_to_db(inp["intubation_needed"]),
            bool_to_db(inp["fever_or_sepsis_suspicion"]),
            bool_to_db(inp["reassessment_done"]),
            inp["spo2_after"],
            inp["rr_after"],
            inp["sbp_after"],
            bool_to_db(inp["dyspnea_improved"]),
            bool_to_db(inp["able_3min_walk_test"]),
            bool_to_db(inp["walk_test_failed"]),
            inp["notes"],
            inp["medical_history"],
            inp["current_medications"],
            inp["treated_pathologies"],
            decision["disposition"],
            decision["score"],
            serialize_decision_list(decision["reasons"]),
            serialize_decision_list(decision["red_flags"]),
            serialize_decision_list(decision["reassessment_failure"]),
        ),
    )
    conn.commit()
    patient_id = cur.lastrowid
    conn.close()
    return int(patient_id)


def fetch_patients() -> List[sqlite3.Row]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def fetch_patient(patient_id: int) -> Optional[sqlite3.Row]:
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return row


def make_excel(rows: List[sqlite3.Row]) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "OAP Triage"
    headers = [
        "ID",
        "Created At",
        "Visit Date",
        "Service",
        "Duty Physician",
        "Duty Anesthetist",
        "Patient Code",
        "Full Name",
        "Age",
        "Sex",
        "Medical History",
        "Current Medications",
        "Treated Pathologies",
        "Disposition",
        "Score",
        "SBP",
        "DBP",
        "MAP",
        "HR",
        "RR",
        "SpO2",
        "Creatinine mg/dL",
        "Troponin Positive",
        "NIV Started",
        "Intubation Needed",
        "Reassessment Done",
        "SpO2 After",
        "RR After",
        "SBP After",
        "Reasons",
        "Red Flags",
        "Reassessment Failure",
        "Notes",
    ]
    ws.append(headers)
    for row in rows:
        ws.append([
            row["id"],
            row["created_at"],
            row["visit_date"],
            row["service_name"],
            row["duty_physician"],
            row["duty_anesthetist"],
            row["patient_code"],
            row["full_name"],
            row["age"],
            row["sex"],
            row["medical_history"],
            row["current_medications"],
            row["treated_pathologies"],
            DISPOSITION_LABELS.get(row["disposition"], row["disposition"]),
            row["score"],
            row["sbp"],
            row["dbp"],
            row["map_value"],
            row["hr"],
            row["rr"],
            row["spo2"],
            row["creatinine_mg_dl"],
            "Oui" if db_to_bool(row["troponin_positive"]) else "Non" if row["troponin_positive"] is not None else "",
            "Oui" if db_to_bool(row["niv_started"]) else "Non" if row["niv_started"] is not None else "",
            "Oui" if db_to_bool(row["intubation_needed"]) else "Non" if row["intubation_needed"] is not None else "",
            "Oui" if db_to_bool(row["reassessment_done"]) else "Non" if row["reassessment_done"] is not None else "",
            row["spo2_after"],
            row["rr_after"],
            row["sbp_after"],
            row["reasons"],
            row["red_flags"],
            row["reassessment_failure"],
            row["notes"],
        ])
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 40)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def make_pdf(row: sqlite3.Row) -> io.BytesIO:
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    x = 15 * mm
    y = height - 18 * mm
    line_gap = 6.5 * mm

    def write_line(label: str, value: Any, bold: bool = False) -> None:
        nonlocal y
        if y < 20 * mm:
            pdf.showPage()
            y = height - 18 * mm
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        pdf.drawString(x, y, f"{label}: {'' if value is None else value}")
        y -= line_gap

    pdf.setTitle(f"OAP_Patient_{row['id']}")
    pdf.setAuthor(AUTHOR_NAME)
    pdf.setSubject("Application prédictive OAP - rapport patient")
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(x, y, "Rapport patient - Application prédictive OAP")
    y -= 9 * mm
    write_line("ID", row["id"], True)
    write_line("Date de saisie", row["created_at"])
    write_line("Date / heure clinique", row["visit_date"])
    write_line("Service", row["service_name"], True)
    write_line("Médecin de garde", row["duty_physician"])
    write_line("Anesthésiste de garde", row["duty_anesthetist"])
    y -= 2 * mm
    write_line("Code patient", row["patient_code"], True)
    write_line("Nom complet", row["full_name"])
    write_line("Âge", row["age"])
    write_line("Sexe", row["sex"])
    y -= 2 * mm
    write_line("Antécédents", row["medical_history"])
    write_line("Médicaments pris", row["current_medications"])
    write_line("Pathologies traitées / en cours", row["treated_pathologies"])
    y -= 2 * mm
    write_line("Disposition", DISPOSITION_LABELS.get(row["disposition"], row["disposition"]), True)
    write_line("Score", row["score"])
    write_line("PAS / PAD / PAM", f"{row['sbp']} / {row['dbp']} / {row['map_value']}")
    write_line("FC / FR / SpO2", f"{row['hr']} / {row['rr']} / {row['spo2']}")
    write_line("Créatinine", row["creatinine_mg_dl"])
    write_line("Facteurs contributifs", row["reasons"])
    write_line("Drapeaux rouges", row["red_flags"])
    write_line("Échec de réévaluation", row["reassessment_failure"])
    write_line("Notes", row["notes"])
    y -= 4 * mm
    pdf.setFont("Helvetica", 8)
    text = pdf.beginText(x, y)
    text.textLines(DISCLAIMER)
    pdf.drawText(text)
    y = y - 18 * mm
    if y < 35 * mm:
        pdf.showPage()
        y = height - 18 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(x, y, AUTHOR_NAME)
    y -= 5 * mm
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x, y, AUTHOR_TITLE)
    y -= 4.5 * mm
    pdf.drawString(x, y, f"Email: {AUTHOR_EMAIL} | ORCID: {AUTHOR_ORCID} | ResearcherID: {AUTHOR_RESEARCHER_ID}")
    y -= 4.5 * mm
    pdf.drawString(x, y, f"YouTube: {AUTHOR_YOUTUBE}")
    y -= 6 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(x, y, f"Ongoing PROSPERO Project: {PROSPERO_ID}")
    y -= 4.5 * mm
    pdf.setFont("Helvetica", 8)
    project_text = pdf.beginText(x, y)
    for line in [
        PROSPERO_TITLE,
        PROSPERO_URL,
        f"Protocol: {PROTOCOL_URL}",
    ]:
        project_text.textLine(line)
    pdf.drawText(project_text)
    pdf.save()
    output.seek(0)
    return output


HTML = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Application prédictive OAP</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f4f6fb; color: #1f2937; }
    .container { max-width: 1280px; margin: auto; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; font-size: 34px; }
    h2 { margin-top: 28px; font-size: 22px; }
    .sub { color: #4b5563; margin-bottom: 18px; }
    .topnav { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
    .navbtn, .button {
      display: inline-block; background: #111827; color: white; text-decoration: none; border: none;
      padding: 12px 16px; border-radius: 12px; font-weight: 700; cursor: pointer;
    }
    .secondary { background: #374151; }
    .lightbtn { background: #e5e7eb; color: #111827; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
    .field { display: flex; flex-direction: column; gap: 6px; }
    label { font-weight: 700; font-size: 14px; }
    input, select, textarea {
      padding: 10px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 14px; background: white;
    }
    textarea { min-height: 92px; resize: vertical; }
    .section { margin-top: 22px; padding-top: 14px; border-top: 1px solid #e5e7eb; }
    .result { margin-top: 28px; padding: 20px; border-radius: 14px; background: #f3f4f6; border-left: 8px solid #9ca3af; }
    .dangerbox { border-left-color: #b91c1c; }
    .okbox { border-left-color: #047857; }
    .warnbox { border-left-color: #b45309; }
    .danger { color: #991b1b; font-weight: 800; font-size: 20px; }
    .ok { color: #065f46; font-weight: 800; font-size: 20px; }
    .warn { color: #92400e; font-weight: 800; font-size: 20px; }
    .small { font-size: 13px; color: #4b5563; }
    ul { margin-top: 6px; }
    .tag { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #e5e7eb; font-size: 12px; font-weight: 700; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .authorbox { margin-top: 22px; padding: 18px; border-radius: 14px; background: #eef2ff; border: 1px solid #c7d2fe; }
    .authorbox h3 { margin-top: 0; }
    .authorbox p { margin: 6px 0; }
    .mutedlink { color: #1d4ed8; text-decoration: none; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; font-size: 14px; }
    th { background: #f9fafb; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } table { display: block; overflow-x: auto; } }
  </style>
</head>
<body>
  <div class="container">
    <h1>Application prédictive OAP</h1>
    <div class="sub">Fiche structurée pour le service des urgences - salle de déchocage - Hôpital Provincial CHPI</div>

    <div class="topnav">
      <a class="navbtn" href="{{ url_for('index') }}">Nouveau patient</a>
      <a class="navbtn secondary" href="{{ url_for('patients_list') }}">Patients enregistrés</a>
      <a class="navbtn lightbtn" href="{{ url_for('export_excel') }}">Exporter Excel</a>
    </div>

    <div class="authorbox">
      <h3>{{ author_name }}</h3>
      <p>{{ author_title }}</p>
      <p><strong>Email:</strong> {{ author_email }}</p>
      <p><strong>ORCID:</strong> {{ author_orcid }}</p>
      <p><strong>Web of Science ResearcherID:</strong> {{ author_researcher_id }}</p>
      <p><strong>YouTube:</strong> <a class="mutedlink" href="{{ author_youtube }}" target="_blank">{{ author_youtube }}</a></p>
      <p><strong>Ongoing PROSPERO Project:</strong> {{ prospero_title }} ({{ prospero_id }})</p>
      <p>{{ prospero_note }}</p>
      <p><strong>PROSPERO record:</strong> <a class="mutedlink" href="{{ prospero_url }}" target="_blank">{{ prospero_url }}</a></p>
      <p><strong>Full protocol:</strong> <a class="mutedlink" href="{{ protocol_url }}" target="_blank">{{ protocol_url }}</a></p>
    </div>

    <form method="post" action="/evaluate">
      <div class="section">
        <h2>1. Contexte de garde</h2>
        <div class="grid">
          <div class="field"><label>Date et heure</label><input type="text" name="visit_date" value="{{ form.get('visit_date','') }}"></div>
          <div class="field"><label>Service</label><input type="text" name="service_name" value="{{ form.get('service_name','') }}"></div>
          <div class="field"><label>Médecin de garde</label><input type="text" name="duty_physician" value="{{ form.get('duty_physician','') }}"></div>
          <div class="field"><label>Anesthésiste de garde</label><input type="text" name="duty_anesthetist" value="{{ form.get('duty_anesthetist','') }}"></div>
          <div class="field"></div>
          <div class="field"></div>
        </div>
      </div>

      <div class="section">
        <h2>2. Identification du malade</h2>
        <div class="grid">
          <div class="field"><label>Code patient</label><input type="text" name="patient_code" value="{{ form.get('patient_code','') }}"></div>
          <div class="field"><label>Nom complet</label><input type="text" name="full_name" value="{{ form.get('full_name','') }}"></div>
          <div class="field"><label>Âge</label><input type="number" name="age" step="1" value="{{ form.get('age','') }}"></div>
          <div class="field"><label>Sexe</label>
            <select name="sex">
              {% set sex = form.get('sex','') %}
              <option value="" {% if sex == '' %}selected{% endif %}>Inconnu</option>
              <option value="Homme" {% if sex == 'Homme' %}selected{% endif %}>Homme</option>
              <option value="Femme" {% if sex == 'Femme' %}selected{% endif %}>Femme</option>
            </select>
          </div>
          <div class="field"><label>Insuffisance cardiaque connue</label>{{ yn('known_hf', form)|safe }}</div>
          <div class="field"><label>Valvulopathie modérée/sévère</label>{{ yn('valvular_disease_moderate_severe', form)|safe }}</div>
        </div>
      </div>

      <div class="section">
        <h2>3. Terrain et traitement habituel</h2>
        <div class="grid">
          <div class="field"><label>Antécédents du malade</label><textarea name="medical_history">{{ form.get('medical_history','') }}</textarea></div>
          <div class="field"><label>Médicaments qu’il prend</label><textarea name="current_medications">{{ form.get('current_medications','') }}</textarea></div>
          <div class="field"><label>Pathologies traitées / en cours de traitement</label><textarea name="treated_pathologies">{{ form.get('treated_pathologies','') }}</textarea></div>
        </div>
      </div>

      <div class="section">
        <h2>4. Évaluation initiale</h2>
        <div class="grid">
          <div class="field"><label>PAS (mmHg)</label><input type="number" name="sbp" step="0.1" value="{{ form.get('sbp','') }}"></div>
          <div class="field"><label>PAD (mmHg)</label><input type="number" name="dbp" step="0.1" value="{{ form.get('dbp','') }}"></div>
          <div class="field"><label>PAM (mmHg)</label><input type="number" name="map_value" step="0.1" value="{{ form.get('map_value','') }}"></div>
          <div class="field"><label>Fréquence cardiaque (/min)</label><input type="number" name="hr" step="0.1" value="{{ form.get('hr','') }}"></div>
          <div class="field"><label>Fréquence respiratoire (/min)</label><input type="number" name="rr" step="0.1" value="{{ form.get('rr','') }}"></div>
          <div class="field"><label>SpO2 (%)</label><input type="number" name="spo2" step="0.1" value="{{ form.get('spo2','') }}"></div>
          <div class="field"><label>Altération de l’état mental</label>{{ yn('altered_mental_status', form)|safe }}</div>
          <div class="field"><label>Extrémités froides / hypoperfusion</label>{{ yn('cold_extremities', form)|safe }}</div>
          <div class="field"><label>Oligurie</label>{{ yn('oliguria', form)|safe }}</div>
          <div class="field"><label>Lactate élevé</label>{{ yn('lactate_high', form)|safe }}</div>
          <div class="field"><label>Suspicion d’ischémie / STEMI</label>{{ yn('stemi_or_ongoing_ischemia', form)|safe }}</div>
          <div class="field"><label>Trouble du rythme malin</label>{{ yn('malignant_arrhythmia', form)|safe }}</div>
          <div class="field"><label>Bloc AV haut degré</label>{{ yn('av_block_high_grade', form)|safe }}</div>
          <div class="field"><label>Créatinine (mg/dL)</label><input type="number" name="creatinine_mg_dl" step="0.01" value="{{ form.get('creatinine_mg_dl','') }}"></div>
          <div class="field"><label>Troponine positive</label>{{ yn('troponin_positive', form)|safe }}</div>
          <div class="field"><label>VNI initiée</label>{{ yn('niv_started', form)|safe }}</div>
          <div class="field"><label>Intubation nécessaire</label>{{ yn('intubation_needed', form)|safe }}</div>
          <div class="field"><label>Fièvre / suspicion de sepsis</label>{{ yn('fever_or_sepsis_suspicion', form)|safe }}</div>
          <div class="field"></div>
        </div>
      </div>

      <div class="section">
        <h2>5. Réévaluation à 30-60 minutes</h2>
        <div class="grid">
          <div class="field"><label>Réévaluation réalisée</label>{{ yn('reassessment_done', form)|safe }}</div>
          <div class="field"><label>SpO2 après traitement (%)</label><input type="number" name="spo2_after" step="0.1" value="{{ form.get('spo2_after','') }}"></div>
          <div class="field"><label>FR après traitement (/min)</label><input type="number" name="rr_after" step="0.1" value="{{ form.get('rr_after','') }}"></div>
          <div class="field"><label>PAS après traitement (mmHg)</label><input type="number" name="sbp_after" step="0.1" value="{{ form.get('sbp_after','') }}"></div>
          <div class="field"><label>Dyspnée améliorée</label>{{ yn('dyspnea_improved', form)|safe }}</div>
          <div class="field"><label>Test de marche 3 min réalisable</label>{{ yn('able_3min_walk_test', form)|safe }}</div>
          <div class="field"><label>Échec du test de marche</label>{{ yn('walk_test_failed', form)|safe }}</div>
          <div class="field"><label>Notes cliniques complémentaires</label><textarea name="notes">{{ form.get('notes','') }}</textarea></div>
          <div class="field"></div>
        </div>
      </div>

      <button class="button" type="submit">Analyser et enregistrer</button>
    </form>

    {% if result %}
    <div class="result {{ box_class }}">
      <h2>Résultat</h2>
      <p class="{{ css_class }}">{{ disposition_label }}</p>
      <p><span class="tag">Score initial : {{ result.score }}</span> <span class="tag">ID patient : {{ saved_patient_id }}</span></p>
      {% if result.red_flags %}
        <h3>Drapeaux rouges immédiats</h3>
        <ul>{% for item in result.red_flags %}<li>{{ item }}</li>{% endfor %}</ul>
      {% endif %}
      {% if result.reasons %}
        <h3>Facteurs de risque contributifs</h3>
        <ul>{% for item in result.reasons %}<li>{{ item }}</li>{% endfor %}</ul>
      {% endif %}
      {% if result.reassessment_failure %}
        <h3>Échec de réévaluation</h3>
        <ul>{% for item in result.reassessment_failure %}<li>{{ item }}</li>{% endfor %}</ul>
      {% endif %}
      <div class="actions">
        <a class="navbtn secondary" href="{{ url_for('patient_detail', patient_id=saved_patient_id) }}">Voir la fiche patient</a>
        <a class="navbtn lightbtn" href="{{ url_for('export_patient_pdf', patient_id=saved_patient_id) }}">Exporter ce patient en PDF</a>
      </div>
      <p class="small"><strong>Message de sécurité :</strong> {{ result.disclaimer }}</p>
    </div>
    {% endif %}
  </div>
</body>
</html>
"""


LIST_HTML = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Patients enregistrés</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f4f6fb; color: #1f2937; }
    .container { max-width: 1300px; margin: auto; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; font-size: 14px; }
    th { background: #f9fafb; }
    .btn { display: inline-block; padding: 8px 12px; border-radius: 10px; text-decoration: none; background: #111827; color: white; font-weight: 700; }
    .btn2 { background: #e5e7eb; color: #111827; }
    .topnav { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Patients enregistrés</h1>
    <div class="topnav">
      <a class="btn" href="{{ url_for('index') }}">Nouveau patient</a>
      <a class="btn btn2" href="{{ url_for('export_excel') }}">Exporter Excel</a>
    </div>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Date</th>
          <th>Service</th>
          <th>Médecin de garde</th>
          <th>Code</th>
          <th>Nom</th>
          <th>Disposition</th>
          <th>Score</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td>{{ row['id'] }}</td>
          <td>{{ row['visit_date'] or row['created_at'] }}</td>
          <td>{{ row['service_name'] or '' }}</td>
          <td>{{ row['duty_physician'] or '' }}</td>
          <td>{{ row['patient_code'] or '' }}</td>
          <td>{{ row['full_name'] or '' }}</td>
          <td>{{ disposition_labels.get(row['disposition'], row['disposition']) }}</td>
          <td>{{ row['score'] }}</td>
          <td>
            <a class="btn" href="{{ url_for('patient_detail', patient_id=row['id']) }}">Voir</a>
            <a class="btn btn2" href="{{ url_for('export_patient_pdf', patient_id=row['id']) }}">PDF</a>
          </td>
        </tr>
        {% else %}
        <tr><td colspan="9">Aucun patient enregistré.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


DETAIL_HTML = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fiche patient</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f4f6fb; color: #1f2937; }
    .container { max-width: 1100px; margin: auto; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .card { background: #f9fafb; padding: 14px; border-radius: 12px; }
    .btn { display: inline-block; padding: 10px 14px; border-radius: 10px; text-decoration: none; background: #111827; color: white; font-weight: 700; margin-right: 8px; }
    .btn2 { background: #e5e7eb; color: #111827; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="container">
    <h1>Fiche patient #{{ row['id'] }}</h1>
    <p><strong>Disposition :</strong> {{ disposition_labels.get(row['disposition'], row['disposition']) }}</p>
    <p><strong>Score :</strong> {{ row['score'] }}</p>
    <a class="btn" href="{{ url_for('patients_list') }}">Retour à la liste</a>
    <a class="btn btn2" href="{{ url_for('export_patient_pdf', patient_id=row['id']) }}">Exporter PDF</a>
    <div class="grid" style="margin-top:18px;">
      <div class="card"><strong>Date / heure clinique</strong><br>{{ row['visit_date'] or '' }}</div>
      <div class="card"><strong>Service</strong><br>{{ row['service_name'] or '' }}</div>
      <div class="card"><strong>Médecin de garde</strong><br>{{ row['duty_physician'] or '' }}</div>
      <div class="card"><strong>Anesthésiste de garde</strong><br>{{ row['duty_anesthetist'] or '' }}</div>
      <div class="card"><strong>Code patient</strong><br>{{ row['patient_code'] or '' }}</div>
      <div class="card"><strong>Nom complet</strong><br>{{ row['full_name'] or '' }}</div>
      <div class="card"><strong>Âge / Sexe</strong><br>{{ row['age'] or '' }} / {{ row['sex'] or '' }}</div>
      <div class="card"><strong>Antécédents</strong><br>{{ row['medical_history'] or '' }}</div>
      <div class="card"><strong>Médicaments pris</strong><br>{{ row['current_medications'] or '' }}</div>
      <div class="card"><strong>Pathologies traitées / en cours</strong><br>{{ row['treated_pathologies'] or '' }}</div>
      <div class="card"><strong>PAS / PAD / PAM</strong><br>{{ row['sbp'] or '' }} / {{ row['dbp'] or '' }} / {{ row['map_value'] or '' }}</div>
      <div class="card"><strong>FC / FR / SpO2</strong><br>{{ row['hr'] or '' }} / {{ row['rr'] or '' }} / {{ row['spo2'] or '' }}</div>
      <div class="card"><strong>Créatinine</strong><br>{{ row['creatinine_mg_dl'] or '' }}</div>
      <div class="card"><strong>Troponine positive</strong><br>{{ 'Oui' if row['troponin_positive'] else 'Non' if row['troponin_positive'] is not none else '' }}</div>
      <div class="card"><strong>Facteurs contributifs</strong><br>{{ row['reasons'] or '' }}</div>
      <div class="card"><strong>Drapeaux rouges</strong><br>{{ row['red_flags'] or '' }}</div>
      <div class="card"><strong>Échec de réévaluation</strong><br>{{ row['reassessment_failure'] or '' }}</div>
      <div class="card"><strong>Notes</strong><br>{{ row['notes'] or '' }}</div>
    </div>
  </div>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            login_user(User(ADMIN_USERNAME))
            return redirect(url_for("index"))
        else:
            error = "Identifiants invalides"

    return render_template_string("""
    <!doctype html>
    <html lang="fr">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Connexion | OAP Triage App</title>
      <style>
        body {
          font-family: Arial, sans-serif;
          background: #eef2f7;
          margin: 0;
          padding: 28px;
          color: #0f172a;
        }
        .wrapper {
          max-width: 1250px;
          margin: auto;
          display: grid;
          grid-template-columns: 420px 1fr;
          gap: 24px;
          align-items: start;
        }
        .login-box, .info-box {
          background: white;
          border-radius: 18px;
          box-shadow: 0 10px 28px rgba(0,0,0,0.08);
          padding: 26px;
        }
        h1 {
          margin-top: 0;
          margin-bottom: 20px;
          font-size: 30px;
          color: #0f172a;
        }
        h2 {
          margin-top: 0;
          font-size: 24px;
          color: #0f172a;
        }
        h3 {
          margin-bottom: 8px;
          font-size: 18px;
          color: #0f172a;
        }
        p {
          line-height: 1.5;
          margin: 8px 0;
        }
        .small {
          font-size: 14px;
          color: #334155;
        }
        label {
          display: block;
          margin-top: 14px;
          font-weight: 700;
          font-size: 15px;
        }
        input {
          width: 100%;
          padding: 12px;
          margin-top: 6px;
          border: 1px solid #cbd5e1;
          border-radius: 12px;
          box-sizing: border-box;
          font-size: 15px;
          background: #fff;
        }
        button {
          margin-top: 20px;
          width: 100%;
          padding: 14px;
          border: none;
          border-radius: 12px;
          background: #0f172a;
          color: white;
          font-weight: 700;
          font-size: 17px;
          cursor: pointer;
        }
        .error {
          color: #b91c1c;
          margin-top: 14px;
          font-weight: 700;
        }
        .card {
          background: #f8fafc;
          border: 1px solid #dbeafe;
          border-radius: 14px;
          padding: 18px;
          margin-top: 16px;
        }
        .creator {
          background: #eef2ff;
          border: 1px solid #c7d2fe;
        }
        .science {
          background: #f8fafc;
          border: 1px solid #cbd5e1;
        }
        .tag {
          display: inline-block;
          background: #e2e8f0;
          color: #0f172a;
          padding: 6px 10px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 700;
          margin-right: 8px;
          margin-top: 8px;
        }
        a {
          color: #2563eb;
          text-decoration: none;
          font-weight: 700;
          word-break: break-word;
        }
        .divider {
          height: 1px;
          background: #e2e8f0;
          margin: 18px 0;
        }
        @media (max-width: 980px) {
          .wrapper {
            grid-template-columns: 1fr;
          }
        }
      </style>
    </head>
    <body>
      <div class="wrapper">
        <div class="login-box">
          <h1>Connexion</h1>
          <p class="small">
            Accès sécurisé à l’application prédictive OAP.
          </p>

          <form method="post">
            <label>Nom d'utilisateur</label>
            <input type="text" name="username" required>

            <label>Mot de passe</label>
            <input type="password" name="password" required>

            <button type="submit">Se connecter</button>
          </form>

          {% if error %}
            <div class="error">{{ error }}</div>
          {% endif %}
        </div>

        <div class="info-box">
          <h2>OAP Triage App</h2>
          <p class="small">
            Interface d’accès | Access portal
          </p>

          <div class="card creator">
            <h3>Concepteur / Developer</h3>
            <p><strong>Dr. Karim Hnid, MD</strong></p>
            <p>Emergency Physician | Medical Author and Researcher | Morocco</p>
            <p><strong>Fabricant de l’application / Application developer:</strong> Dr. Karim Hnid</p>
            <p><strong>Email:</strong> hniddata@gmail.com</p>
            <p><strong>ORCID:</strong> 0000-0003-0122-2783</p>
            <p><strong>Web of Science ResearcherID:</strong> R-3425-2018</p>
            <p><strong>YouTube:</strong> <a href="https://www.youtube.com/@hnid68" target="_blank">https://www.youtube.com/@hnid68</a></p>
            <p><strong>Date de mise en ligne / Initial online deployment:</strong> 11 March 2026</p>
          </div>

          <div class="card">
            <h3>Projet PROSPERO / PROSPERO Project</h3>
            <p><strong>Ongoing PROSPERO Project:</strong> Poor pharmaceutical quality, medicinal impurities, and cancer risk (CRD420261335075)</p>
            <p><strong>PROSPERO record:</strong> <a href="https://www.crd.york.ac.uk/PROSPERO/view/CRD420261335075" target="_blank">https://www.crd.york.ac.uk/PROSPERO/view/CRD420261335075</a></p>
            <p><strong>Full protocol:</strong> <a href="https://www.crd.york.ac.uk/PROSPEROFILES/e58ed2a98e3ba4232a889eeee508a377.pdf" target="_blank">https://www.crd.york.ac.uk/PROSPEROFILES/e58ed2a98e3ba4232a889eeee508a377.pdf</a></p>
          </div>

          <div class="card science">
            <h3>Base scientifique de l’application – Français</h3>
            <p>
              Cette application a été conçue comme un outil structuré d’aide au triage initial des patients présentant une suspicion d’œdème aigu pulmonaire (OAP) cardiogénique.
            </p>
            <p>
              Son architecture clinique repose sur une approche pragmatique intégrant les signes de gravité immédiate, le contexte hémodynamique, la réévaluation précoce après traitement initial, et la décision d’orientation vers un niveau de soins supérieur lorsque cela est nécessaire.
            </p>
            <p>
              Elle a été développée en parallèle avec les grands principes des recommandations internationales utilisées en insuffisance cardiaque aiguë et en évaluation cardiovasculaire d’urgence, notamment les cadres AHA/ACC/HFSA, sans prétendre se substituer à une validation clinique prospective indépendante.
            </p>
            <p>
              Il s’agit d’un prototype décisionnel local destiné à standardiser la collecte des premières données cliniques, améliorer la traçabilité, renforcer la cohérence de l’évaluation initiale, et soutenir le jugement médical.
            </p>
            <p>
              Cette application ne remplace ni le jugement clinique, ni les protocoles institutionnels, ni les recommandations officielles.
            </p>
          </div>

          <div class="card science">
            <h3>Scientific basis of the application – English</h3>
            <p>
              This application was designed as a structured support tool for the initial triage of patients with suspected cardiogenic acute pulmonary edema.
            </p>
            <p>
              Its clinical architecture follows a pragmatic framework integrating immediate severity markers, hemodynamic context, early reassessment after initial treatment, and referral to a higher level of care whenever required.
            </p>
            <p>
              It was developed in conceptual parallel with internationally used principles in acute heart failure and emergency cardiovascular assessment, particularly AHA/ACC/HFSA-oriented frameworks, without claiming to replace independent prospective clinical validation.
            </p>
            <p>
              It should be understood as a local decision-support prototype intended to standardize early data capture, improve traceability, strengthen consistency of first-line assessment, and support clinical judgment.
            </p>
            <p>
              This application does not replace clinical judgment, institutional protocols, or formal guideline-directed care.
            </p>
          </div>

          <div class="divider"></div>

          <span class="tag">Secure login</span>
          <span class="tag">French / English</span>
          <span class="tag">Prototype decision support</span>
          <span class="tag">AHA/ACC/HFSA-aligned principles</span>
        </div>
      </div>
    </body>
    </html>
    """, error=error)
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.get("/")
@login_required
def index():
    form = {
        "visit_date": now_local_str(),
        "service_name": DEFAULT_SERVICE,
        "duty_physician": "",
        "duty_anesthetist": "",
        "patient_code": "",
        "full_name": "",
        "age": "",
        "sex": "",
        "medical_history": "",
        "current_medications": "",
        "treated_pathologies": "",
        "notes": "",
    }
    return render_template_string(
        HTML,
        result=None,
        css_class="",
        box_class="",
        disposition_label="",
        saved_patient_id=None,
        yn=yn,
        form=form,
        author_name=AUTHOR_NAME,
        author_title=AUTHOR_TITLE,
        author_email=AUTHOR_EMAIL,
        author_orcid=AUTHOR_ORCID,
        author_researcher_id=AUTHOR_RESEARCHER_ID,
        author_youtube=AUTHOR_YOUTUBE,
        prospero_title=PROSPERO_TITLE,
        prospero_id=PROSPERO_ID,
        prospero_note=PROSPERO_NOTE,
        prospero_url=PROSPERO_URL,
        protocol_url=PROTOCOL_URL,
    )


@app.post("/evaluate")
def evaluate_form():
    form_data = request.form.to_dict()
    inp = build_input(form_data)
    result = explain_decision(inp)
    patient_id = save_patient(inp, result)
    css_class = "warn"
    box_class = "warnbox"
    if result["disposition"] == "TRANSFER_CHU_SAMU":
        css_class = "danger"
        box_class = "dangerbox"
    elif result["disposition"] == "LOCAL_DECHOCAGE_STRICT":
        css_class = "ok"
        box_class = "okbox"
    return render_template_string(
        HTML,
        result=result,
        css_class=css_class,
        box_class=box_class,
        disposition_label=DISPOSITION_LABELS.get(result["disposition"], result["disposition"]),
        saved_patient_id=patient_id,
        yn=yn,
        form=form_data,
        author_name=AUTHOR_NAME,
        author_title=AUTHOR_TITLE,
        author_email=AUTHOR_EMAIL,
        author_orcid=AUTHOR_ORCID,
        author_researcher_id=AUTHOR_RESEARCHER_ID,
        author_youtube=AUTHOR_YOUTUBE,
        prospero_title=PROSPERO_TITLE,
        prospero_id=PROSPERO_ID,
        prospero_note=PROSPERO_NOTE,
        prospero_url=PROSPERO_URL,
        protocol_url=PROTOCOL_URL,
    )


@app.get("/patients")
def patients_list():
    rows = fetch_patients()
    return render_template_string(LIST_HTML, rows=rows, disposition_labels=DISPOSITION_LABELS)


@app.get("/patients/<int:patient_id>")
def patient_detail(patient_id: int):
    row = fetch_patient(patient_id)
    if row is None:
        return "Patient introuvable", 404
    return render_template_string(DETAIL_HTML, row=row, disposition_labels=DISPOSITION_LABELS)


@app.get("/export/excel")
def export_excel():
    rows = fetch_patients()
    output = make_excel(rows)
    filename = f"oap_patients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/export/patient/<int:patient_id>/pdf")
def export_patient_pdf(patient_id: int):
    row = fetch_patient(patient_id)
    if row is None:
        return "Patient introuvable", 404
    output = make_pdf(row)
    filename = f"patient_{patient_id}_oap.pdf"
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.post("/api/evaluate")
def evaluate_api():
    payload = request.get_json(silent=True) or {}
    inp = build_input(payload)
    result = explain_decision(inp)
    patient_id = save_patient(inp, result)
    result["patient_id"] = patient_id
    result["disposition_label"] = DISPOSITION_LABELS.get(result["disposition"], result["disposition"])
    return jsonify(result)


@app.get("/api/patients")
def api_patients():
    rows = fetch_patients()
    data = []
    for row in rows:
        item = dict(row)
        item["disposition_label"] = DISPOSITION_LABELS.get(row["disposition"], row["disposition"])
        data.append(item)
    return jsonify(data)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "database": DATABASE, "service_default": DEFAULT_SERVICE})
init_db()

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)






