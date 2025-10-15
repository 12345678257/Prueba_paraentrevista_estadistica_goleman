
# -*- coding: utf-8 -*-
# Prueba Técnica Interactiva — Excel Avanzado, Python Básico y SQL Básico (modo candidato sin respuestas)
# Autor: ChatGPT
# Uso: streamlit run app_prueba_tecnica.py

import os, re, io, json, time, sqlite3, unicodedata, textwrap
from datetime import datetime
import pandas as pd
import streamlit as st

APP_TITLE = "🧪 Prueba Técnica — Excel, Python, SQL"
EXCEL_QUIZ_FILE = "Cuestionario_Prueba_Tecnica.xlsx"
DB_FILE = "quiz.db"
ADMIN_KEY = st.secrets.get("ADMIN_KEY", os.environ.get("ADMIN_KEY", "admin123"))

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Registro de candidatos, ejecución de prueba sin revelar respuestas y tablero administrador con resultados.")

# ---------------- Utilidades ----------------
def norm_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.upper()

@st.cache_data
def load_questions(path: str):
    xls = pd.ExcelFile(path)
    preguntas = pd.read_excel(xls, "Preguntas")
    preguntas["id"] = preguntas["id"].astype(int)
    preguntas["categoria"] = preguntas["categoria"].astype(str)
    preguntas["tipo"] = preguntas["tipo"].astype(str)
    preguntas["puntos"] = preguntas["puntos"].astype(int)
    preguntas["enunciado"] = preguntas["enunciado"].astype(str)
    preguntas["opciones"] = preguntas["opciones"].fillna("")
    preguntas["respuesta_correcta"] = preguntas["respuesta_correcta"].fillna("")
    return preguntas

def ensure_db():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, doc TEXT,
        role TEXT,  -- 'candidato' o 'administrador'
        created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS submissions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        started_at TEXT,
        finished_at TEXT,
        duration_sec REAL,
        score_total REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS answers(
        submission_id INTEGER,
        qid INTEGER,
        response_text TEXT,
        is_correct INTEGER,
        score_awarded REAL,
        FOREIGN KEY(submission_id) REFERENCES submissions(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS coding(
        submission_id INTEGER,
        task_type TEXT,   -- 'PY' o 'SQL'
        task_id INTEGER,
        passed_tests INTEGER,
        total_tests INTEGER,
        details TEXT,
        score_awarded REAL,
        FOREIGN KEY(submission_id) REFERENCES submissions(id)
    )""")
    # Borradores (auto-guardado)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS draft_answers(
        user_id INTEGER,
        qid INTEGER,
        response_text TEXT,
        updated_at TEXT,
        PRIMARY KEY(user_id, qid)
    )""")
    con.commit()
    return con

def save_drafts(con, user_id: int, answers: dict):
    cur = con.cursor()
    now = datetime.utcnow().isoformat()
    for qid, resp in answers.items():
        cur.execute("""
            INSERT INTO draft_answers(user_id, qid, response_text, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(user_id, qid) DO UPDATE SET response_text=excluded.response_text, updated_at=excluded.updated_at
        """, (user_id, int(qid), str(resp), now))
    con.commit()

def load_drafts(con, user_id: int) -> dict:
    cur = con.cursor()
    rows = cur.execute("SELECT qid, response_text FROM draft_answers WHERE user_id=?", (user_id,)).fetchall()
    return {int(qid): resp for (qid, resp) in rows}

def score_formula(user_input: str, golden_variants: list) -> bool:
    u = norm_text(user_input).replace(" ", "")
    for g in golden_variants:
        v = norm_text(g).replace(" ", "")
        if u == v:
            return True
    return False

def get_golden_variants(resp_correcta: str):
    parts = [p.strip() for p in str(resp_correcta).split("|") if p.strip()]
    return parts

# ---------------- Carga de preguntas ----------------
if not os.path.exists(EXCEL_QUIZ_FILE):
    st.error(f"No se encuentra {EXCEL_QUIZ_FILE}. Sube el archivo desde la barra lateral.")
else:
    st.success(f"Plantilla detectada: {EXCEL_QUIZ_FILE}")

with st.sidebar:
    st.header("⚙️ Configuración")
    up = st.file_uploader("Subir nueva plantilla Excel (opcional)", type=["xlsx"])
    if up:
        with open(EXCEL_QUIZ_FILE, "wb") as f:
            f.write(up.read())
        st.success("Plantilla reemplazada.")

    st.markdown("**Admin Key**: configura `ADMIN_KEY` en *Secrets* o variable de entorno.")

preguntas = load_questions(EXCEL_QUIZ_FILE)
con = ensure_db()

# ---------------- Registro ----------------
st.subheader("🪪 Registro")
with st.form("registro"):
    col1, col2, col3 = st.columns(3)
    name = col1.text_input("Nombre completo", key="name")
    email = col2.text_input("Correo", key="email")
    doc = col3.text_input("Documento/N° ID", key="doc")
    role = st.selectbox("Rol", ["candidato", "administrador"], key="role")
    key_admin = st.text_input("Admin key (si es administrador)", type="password", key="adminkey") if role == "administrador" else ""
    start = st.form_submit_button("Ingresar")

if start:
    if role == "administrador":
        if key_admin != ADMIN_KEY:
            st.error("Admin key inválida.")
        else:
            cur = con.cursor()
            cur.execute("INSERT INTO users(name,email,doc,role,created_at) VALUES (?,?,?,?,?)",
                        (name or "Admin", email or "admin@example.com", doc or "-", "administrador", datetime.utcnow().isoformat()))
            con.commit()
            st.session_state["is_admin"] = True
            st.session_state["admin_user_id"] = cur.lastrowid
            st.success("Bienvenido, Administrador.")
    else:
        if not name or not email or not doc:
            st.error("Complete nombre, correo y documento.")
        else:
            cur = con.cursor()
            cur.execute("INSERT INTO users(name,email,doc,role,created_at) VALUES (?,?,?,?,?)",
                        (name, email, doc, "candidato", datetime.utcnow().isoformat()))
            con.commit()
            st.session_state["user_id"] = cur.lastrowid
            st.session_state["started_at"] = time.time()
            st.session_state.setdefault("buffer_answers", {})
            st.success("Registro exitoso. ¡Puedes iniciar la prueba!")

# ---------------- Prefill de borradores ----------------
def prefill_from_drafts(user_id: int):
    drafts = load_drafts(con, user_id)
    st.session_state.setdefault("buffer_answers", {})
    st.session_state["buffer_answers"].update(drafts)

if st.session_state.get("user_id") and "prefilled" not in st.session_state:
    prefill_from_drafts(st.session_state["user_id"])
    st.session_state["prefilled"] = True

# ---------------- UI de la prueba (sin feedback) ----------------
if st.session_state.get("user_id"):
    st.markdown("---")
    st.subheader("📋 Prueba (no se muestran respuestas correctas)")
    tabs = st.tabs(["Excel", "Python", "SQL"])

    buffer = st.session_state.setdefault("buffer_answers", {})

    # ---- Excel ----
    with tabs[0]:
        st.markdown("### Preguntas de Excel")
        excel_mcq = preguntas[(preguntas["categoria"]=="Excel") & (preguntas["tipo"]=="MCQ")]
        excel_form = preguntas[(preguntas["categoria"]=="Excel") & (preguntas["tipo"]=="FORMULA_EXCEL")]

        for _, row in excel_mcq.iterrows():
            qkey = f"q_{row.id}_mcq"
            st.write(f"**[{row.id}]** {row.enunciado}")
            opciones = [o.strip() for o in str(row.opciones).split("|") if o.strip()]
            saved = buffer.get(row.id, "")
            saved_idx = None
            if saved:
                for i, opt in enumerate(opciones):
                    if opt.upper().startswith(saved.upper()[:1] + ")"):
                        saved_idx = i
                        break
            choice = st.radio(
                "Selecciona una opción:",
                opciones,
                index=saved_idx if saved_idx is not None else None,
                key=qkey,
                horizontal=False
            )
            if choice:
                buffer[row.id] = choice[:1]
            st.divider()

        st.markdown("### Fórmulas (ingresa solo la fórmula)")
        for _, row in excel_form.iterrows():
            qkey = f"q_{row.id}_formula"
            st.write(f"**[{row.id}]** {row.enunciado}")
            if qkey not in st.session_state and row.id in buffer:
                st.session_state[qkey] = buffer[row.id]
            ans = st.text_input("Tu fórmula:", key=qkey, placeholder="Ej: SUMAR.SI.CONJUNTO(...)", label_visibility="visible")
            buffer[row.id] = ans
            st.divider()

    # ---- Python ----
    with tabs[1]:
        st.markdown("### Preguntas de Python")
        py_mcq = preguntas[(preguntas["categoria"]=="Python") & (preguntas["tipo"]=="MCQ")]
        for _, row in py_mcq.iterrows():
            qkey = f"q_{row.id}_mcq"
            st.write(f"**[{row.id}]** {row.enunciado}")
            opciones = [o.strip() for o in str(row.opciones).split("|") if o.strip()]
            saved = buffer.get(row.id, "")
            saved_idx = None
            if saved:
                for i, opt in enumerate(opciones):
                    if opt.upper().startswith(saved.upper()[:1] + ")"):
                        saved_idx = i
                        break
            choice = st.radio(
                "Selecciona una opción:",
                opciones,
                index=saved_idx if saved_idx is not None else None,
                key=qkey
            )
            if choice:
                buffer[row.id] = choice[:1]
            st.divider()

        st.markdown("### Prácticas de Python (escribe tu solución)")
        st.write("**[301]** Implementa `fizzbuzz(n)` según enunciado.")
        key301 = "code_301"
        if key301 not in st.session_state and 301 in buffer:
            st.session_state[key301] = buffer[301]
        code_301 = st.text_area("Tu código (define fizzbuzz):", height=180, key=key301,
                                placeholder="def fizzbuzz(n):\n    # tu código aquí\n    ...")
        buffer[301] = code_301

        st.write("**[302]** Implementa `flatten_list(lst)` para aplanar listas anidadas.")
        key302 = "code_302"
        if key302 not in st.session_state and 302 in buffer:
            st.session_state[key302] = buffer[302]
        code_302 = st.text_area("Tu código (define flatten_list):", height=200, key=key302,
                                placeholder="def flatten_list(lst):\n    # tu código aquí\n    ...")
        buffer[302] = code_302

        st.caption("Nota: No se muestran resultados de tests durante la prueba. El administrador verá el puntaje posteriormente.")

    # ---- SQL ----
    with tabs[2]:
        st.markdown("### Preguntas de SQL")
        sql_mcq = preguntas[(preguntas["categoria"]=="SQL") & (preguntas["tipo"]=="MCQ")]
        for _, row in sql_mcq.iterrows():
            qkey = f"q_{row.id}_mcq"
            st.write(f"**[{row.id}]** {row.enunciado}")
            opciones = [o.strip() for o in str(row.opciones).split("|") if o.strip()]
            saved = buffer.get(row.id, "")
            saved_idx = None
            if saved:
                for i, opt in enumerate(opciones):
                    if opt.upper().startswith(saved.upper()[:1] + ")"):
                        saved_idx = i
                        break
            choice = st.radio(
                "Selecciona una opción:",
                opciones,
                index=saved_idx if saved_idx is not None else None,
                key=qkey
            )
            if choice:
                buffer[row.id] = choice[:1]
            st.divider()

        st.markdown("### Prácticas de SQL (escribe tu consulta)")
        st.caption("Describe tus consultas. Serán evaluadas por el administrador.")
        key501 = "sql_501"
        if key501 not in st.session_state and 501 in buffer:
            st.session_state[key501] = buffer[501]
        code_501 = st.text_area("**[501]** TOP 3 clientes por total vendido (customer, total):", height=160, key=key501,
                                placeholder="-- Escribe aquí tu SQL")
        buffer[501] = code_501

        key502 = "sql_502"
        if key502 not in st.session_state and 502 in buffer:
            st.session_state[key502] = buffer[502]
        code_502 = st.text_area("**[502]** Total vendido por mes 2024 (mes YYYY-MM, total):", height=160, key=key502,
                                placeholder="-- Escribe aquí tu SQL")
        buffer[502] = code_502

    # ---- Guardado y Envío ----
    colg1, colg2 = st.columns([1,1])
    if colg1.button("💾 Guardar progreso"):
        save_drafts(con, st.session_state["user_id"], buffer)
        st.success("Progreso guardado. Puedes cerrar y volver luego para continuar.")

    if colg2.button("📤 Enviar prueba", type="primary"):
        user_id = st.session_state["user_id"]
        started_at = st.session_state.get("started_at", time.time())
        finished_at = time.time()
        duration = finished_at - started_at

        df = preguntas.copy()
        total_score = 0.0
        rows_answers = []

        mcq_form = df[df["tipo"].isin(["MCQ","FORMULA_EXCEL"])].copy()
        for _, row in mcq_form.iterrows():
            ans = buffer.get(row.id, "")
            is_ok = 0
            awarded = 0.0
            if row["tipo"] == "MCQ":
                correct = str(row["respuesta_correcta"]).strip().upper()[:1]
                sel = str(ans).strip().upper()[:1]
                is_ok = 1 if sel == correct else 0
                awarded = float(row["puntos"]) if is_ok else 0.0
            else:
                golds = [p.strip() for p in str(row["respuesta_correcta"]).split("|") if p.strip()]
                is_ok = 1 if score_formula(str(ans), golds) else 0
                awarded = float(row["puntos"]) if is_ok else 0.0
            total_score += awarded
            rows_answers.append((row.id, ans, is_ok, awarded))

        cur = con.cursor()
        cur.execute("INSERT INTO submissions(user_id, started_at, finished_at, duration_sec, score_total) VALUES (?,?,?,?,?)",
                    (user_id, datetime.utcfromtimestamp(started_at).isoformat(),
                              datetime.utcfromtimestamp(finished_at).isoformat(),
                              duration, total_score))
        sub_id = cur.lastrowid
        for qid, ans, ok, pts in rows_answers:
            cur.execute("INSERT INTO answers(submission_id,qid,response_text,is_correct,score_awarded) VALUES (?,?,?,?,?)",
                        (sub_id, qid, str(ans), int(ok), pts))
        con.commit()

        st.success("Entrega registrada. Gracias por completar la prueba.")
        st.info("El administrador verá tu puntaje y comparativo.")

# ---------------- Admin Dashboard ----------------
st.markdown("---")
st.subheader("🛡️ Administrador")
colA, colB = st.columns([1,3])
with colA:
    admin_try = st.text_input("Admin key", type="password", key="adminkey2")
    check = st.button("Entrar a Dashboard", key="admin_enter")
if (check and admin_try == ADMIN_KEY) or st.session_state.get("is_admin"):
    st.session_state["is_admin"] = True
    con2 = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = con2.cursor()
    st.success("Acceso administrador concedido.")

    # KPI
    k1, k2, k3, k4 = st.columns(4)
    total_users = cur.execute("SELECT COUNT(*) FROM users WHERE role='candidato'").fetchone()[0]
    total_subs  = cur.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    avg_score   = cur.execute("SELECT COALESCE(AVG(score_total),0) FROM submissions").fetchone()[0]
    avg_dur     = cur.execute("SELECT COALESCE(AVG(duration_sec),0) FROM submissions").fetchone()[0]
    k1.metric("Candidatos", total_users)
    k2.metric("Entregas", total_subs)
    k3.metric("Promedio (MCQ+Fórmulas)", round(avg_score,2))
    k4.metric("Duración Prom. (min)", round(avg_dur/60,2))

    # Datos base
    df_users = pd.read_sql_query("SELECT * FROM users", con2)
    df_subs  = pd.read_sql_query("SELECT * FROM submissions", con2)
    df_ans   = pd.read_sql_query("SELECT * FROM answers", con2)
    df_code  = pd.read_sql_query("SELECT * FROM coding", con2)
    preguntas_df = load_questions(EXCEL_QUIZ_FILE)

    if not df_subs.empty:
        # Conteo buenas/malas
        if not df_ans.empty:
            agg = df_ans.groupby("submission_id").agg(
                buenas=("is_correct", lambda s: int((s==1).sum())),
                malas=("is_correct", lambda s: int((s==0).sum())),
                puntos_obtenidos=("score_awarded", "sum")
            ).reset_index()
        else:
            agg = pd.DataFrame(columns=["submission_id","buenas","malas","puntos_obtenidos"])

        if not df_code.empty:
            code_agg = df_code.groupby("submission_id").agg(
                tests_ok=("passed_tests", "sum"),
                tests_total=("total_tests", "sum"),
                puntos_code=("score_awarded","sum")
            ).reset_index()
        else:
            code_agg = pd.DataFrame(columns=["submission_id","tests_ok","tests_total","puntos_code"])

        df_join = df_subs.merge(df_users, left_on="user_id", right_on="id", suffixes=("_sub","_user"), how="left")
        df_join = df_join.merge(agg, left_on="id_sub", right_on="submission_id", how="left")
        df_join = df_join.merge(code_agg, left_on="id_sub", right_on="submission_id", how="left")
        df_join["tests_ok"] = df_join["tests_ok"].fillna(0).astype(int)
        df_join["tests_total"] = df_join["tests_total"].fillna(0).astype(int)
        df_join["puntos_code"] = df_join["puntos_code"].fillna(0.0)
        df_join["puntos_obtenidos"] = df_join["puntos_obtenidos"].fillna(0.0)
        df_join["score_total_final"] = df_join["score_total"].fillna(0.0) + df_join["puntos_code"]

        st.markdown("### Resumen por candidato")
        st.dataframe(df_join[[
            "id_sub","name","email","doc","buenas","malas","puntos_obtenidos","tests_ok","tests_total","score_total_final","duration_sec","started_at","finished_at"
        ]].rename(columns={"id_sub":"submission_id"}), use_container_width=True)

        with st.expander("Comparativo por pregunta (con respuesta correcta)"):
            if not df_ans.empty:
                df_comp = df_ans.merge(preguntas_df[["id","enunciado","categoria","tipo","respuesta_correcta","puntos"]],
                                       left_on="qid", right_on="id", how="left")
                st.dataframe(df_comp.sort_values(["submission_id","qid"]), use_container_width=True)
            else:
                st.info("Sin respuestas MCQ/Fórmulas registradas.")

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            csv = df_join.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar resultados (CSV)", csv, "resultados.csv", "text/csv")
        with bcol2:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                df_join.to_excel(writer, sheet_name="Submissions", index=False)
                if not df_ans.empty:
                    df_ans.to_excel(writer, sheet_name="Answers", index=False)
                if 'df_comp' in locals():
                    df_comp.to_excel(writer, sheet_name="Comparativo", index=False)
                if not df_code.empty:
                    df_code.to_excel(writer, sheet_name="Coding", index=False)
            st.download_button("⬇️ Descargar resultados (XLSX)", out.getvalue(), "resultados.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Aún no hay entregas registradas.")
else:
    st.info("Ingrese Admin key para ver el Dashboard.")
