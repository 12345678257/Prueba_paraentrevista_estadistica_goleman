
# -*- coding: utf-8 -*-
# Prueba Técnica Interactiva — Excel Avanzado, Python Básico y SQL Básico
# Autor: ChatGPT
# Uso: streamlit run app_prueba_tecnica.py
#
# Características:
# - Registro de participantes (nombre, correo, documento).
# - MCQs (Excel, Python, SQL).
# - Prácticos: Fórmulas Excel (validación por string), Python (tests), SQL (tests con SQLite demo).
# - Puntaje automático.
# - Dashboard de administrador con resumen y descarga de resultados.
# - Admin key via st.secrets["ADMIN_KEY"] o variable de entorno ADMIN_KEY (default: admin123).
#
# Repositorio: basta con incluir este archivo, la plantilla "Cuestionario_Prueba_Tecnica.xlsx",
# requirements.txt y README.md. En Streamlit Cloud, añade ADMIN_KEY en "Secrets".

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
st.caption("Registro de candidatos, ejecución de prueba y tablero administrador — profesional y compacto.")

# ------------- Utilidades generales -------------
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
    # Asegurar tipos básicos
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
    con.commit()
    return con

def create_demo_sqlite():
    # Crea BD en memoria para evaluación de SQL
    mem = sqlite3.connect(":memory:")
    cur = mem.cursor()
    cur.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, city TEXT)")
    cur.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT)")
    cur.execute("CREATE TABLE order_items(id INTEGER PRIMARY KEY, order_id INTEGER, product TEXT, qty INTEGER, price REAL)")
    customers = [
        (1, "Acme SAS", "Bogotá"),
        (2, "Nova Ltda", "Medellín"),
        (3, "Zetta SA", "Cali"),
        (4, "Orion SA", "Bogotá"),
    ]
    orders = [
        (100, 1, "2024-01-15"),
        (101, 1, "2024-02-10"),
        (102, 2, "2024-01-20"),
        (103, 2, "2024-03-05"),
        (104, 3, "2024-03-22"),
        (105, 4, "2024-02-11"),
    ]
    items = [
        (1, 100, "Mouse",   2,  50.0),
        (2, 100, "Teclado", 1, 120.0),
        (3, 101, "Monitor", 1, 800.0),
        (4, 102, "Laptop",  1, 3000.0),
        (5, 103, "Silla",   2, 400.0),
        (6, 104, "Dock",    3, 200.0),
        (7, 105, "Webcam",  4, 150.0),
    ]
    cur.executemany("INSERT INTO customers VALUES (?,?,?)", customers)
    cur.executemany("INSERT INTO orders VALUES (?,?,?)", orders)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)
    mem.commit()
    return mem

def score_formula(user_input: str, golden_variants: list) -> bool:
    u = norm_text(user_input).replace(" ", "")
    for g in golden_variants:
        v = norm_text(g).replace(" ", "")
        if u == v:
            return True
    return False

def get_golden_variants(resp_correcta: str):
    # variantes separadas por '|'
    parts = [p.strip() for p in str(resp_correcta).split("|") if p.strip()]
    return parts

# ------------- Carga de preguntas -------------
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

# ------------- Registro -------------
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
            st.session_state["is_admin"] = True
            st.success("Bienvenido, Administrador.")
    else:
        if not name or not email or not doc:
            st.error("Complete nombre, correo y documento.")
        else:
            cur = con.cursor()
            cur.execute("INSERT INTO users(name,email,doc,created_at) VALUES (?,?,?,?)",
                        (name, email, doc, datetime.utcnow().isoformat()))
            con.commit()
            st.session_state["user_id"] = cur.lastrowid
            st.session_state["started_at"] = time.time()
            st.success("Registro exitoso. ¡Puedes iniciar la prueba!")

# ------------- UI de la prueba -------------
if st.session_state.get("user_id"):
    st.markdown("---")
    st.subheader("📋 Prueba")
    tabs = st.tabs(["Excel", "Python", "SQL"])

    # ---- Excel ----
    with tabs[0]:
        st.markdown("### Preguntas de Excel")
        excel_mcq = preguntas[(preguntas["categoria"]=="Excel") & (preguntas["tipo"]=="MCQ")]
        excel_form = preguntas[(preguntas["categoria"]=="Excel") & (preguntas["tipo"]=="FORMULA_EXCEL")]

        user_answers = {}
        for _, row in excel_mcq.iterrows():
            qkey = f"q_{row.id}"
            st.write(f"**[{row.id}]** {row.enunciado}")
            opciones = [o.strip() for o in str(row.opciones).split("|")]
            opciones = [o for o in opciones if o]
            choice = st.radio("Selecciona una opción:", opciones, key=qkey)
            user_answers[row.id] = choice[:1]  # letra (A/B/C/D)
            st.divider()

        st.markdown("### Fórmulas (ingresa solo la fórmula)")
        for _, row in excel_form.iterrows():
            qkey = f"q_{row.id}"
            st.write(f"**[{row.id}]** {row.enunciado}")
            ans = st.text_input("Tu fórmula:", key=qkey)
            user_answers[row.id] = ans
            st.divider()

    # ---- Python ----
    with tabs[1]:
        st.markdown("### Preguntas de Python")
        py_mcq = preguntas[(preguntas["categoria"]=="Python") & (preguntas["tipo"]=="MCQ")]
        for _, row in py_mcq.iterrows():
            qkey = f"q_{row.id}"
            st.write(f"**[{row.id}]** {row.enunciado}")
            opciones = [o.strip() for o in str(row.opciones).split("|")]
            choice = st.radio("Selecciona una opción:", opciones, key=qkey)
            user_answers[row.id] = choice[:1]
            st.divider()

        st.markdown("### Prácticas de Python (edita código)")
        # 301 fizzbuzz
        st.write("**[301]** Implementa `fizzbuzz(n)` según enunciado.")
        code_301 = st.text_area("Tu código (define fizzbuzz):", height=180, key="code_301",
                                placeholder="def fizzbuzz(n):\n    # tu código aquí\n    ...")
        # 302 flatten_list
        st.write("**[302]** Implementa `flatten_list(lst)` para aplanar listas anidadas.")
        code_302 = st.text_area("Tu código (define flatten_list):", height=200, key="code_302",
                                placeholder="def flatten_list(lst):\n    # tu código aquí\n    ...")

        if st.button("Probar código Python", key="test_py_btn"):
            def safe_exec(code, func_names):
                # Sandbox simple: sin imports ni dunders
                if re.search(r"(__|import|open|exec|eval|os\\.|sys\\.)", code):
                    return None, "Código no permitido (import/dunder)."
                g, l = {}, {}
                try:
                    exec(code, g, l)
                except Exception as e:
                    return None, f"Error al ejecutar: {e}"
                for fn in func_names:
                    if fn not in l:
                        return None, f"Falta definir función: {fn}"
                return l, "OK"

            # Tests fizzbuzz
            lns_301, msg1 = safe_exec(code_301, ["fizzbuzz"])
            passed_301 = 0
            total_301 = 6
            det_301 = []
            if lns_301:
                try:
                    f = lns_301["fizzbuzz"]
                    cases = [(1,"1"),(3,"Fizz"),(5,"Buzz"),(15,"FizzBuzz"),(16,"16"),(30,"FizzBuzz")]
                    for n, expect in cases:
                        try:
                            got = str(f(n))
                            ok = (got == expect)
                            passed_301 += 1 if ok else 0
                            det_301.append(f"fizzbuzz({n}) -> {got} | esp: {expect} | {'OK' if ok else 'X'}")
                        except Exception as ex:
                            det_301.append(f"Error en fizzbuzz({n}): {ex}")
                except Exception as e:
                    msg1 = f"Error: {e}"
            else:
                det_301.append(msg1)

            # Tests flatten_list
            lns_302, msg2 = safe_exec(code_302, ["flatten_list"])
            passed_302 = 0
            total_302 = 4
            det_302 = []
            if lns_302:
                try:
                    f = lns_302["flatten_list"]
                    cases = [
                        ([1,2,3],[1,2,3]),
                        ([1,[2,[3,4]],5],[1,2,3,4,5]),
                        ([],[]),
                        ([[[1]],[2,[3,[4]]]], [1,2,3,4]),
                    ]
                    for inp, exp in cases:
                        try:
                            got = f(inp)
                            ok = (got == exp)
                            passed_302 += 1 if ok else 0
                            det_302.append(f"flatten_list({inp}) -> {got} | esp: {exp} | {'OK' if ok else 'X'}")
                        except Exception as ex:
                            det_302.append(f"Error: {ex}")
                except Exception as e:
                    msg2 = f"Error: {e}"
            else:
                det_302.append(msg2)

            st.info("Resultados Python:")
            st.write(f"[301] Tests pasados: {passed_301}/{total_301}")
            st.write("\n".join(det_301))
            st.write(f"[302] Tests pasados: {passed_302}/{total_302}")
            st.write("\n".join(det_302))

            st.session_state["py_results"] = {
                301: {"passed": passed_301, "total": total_301, "details": "\n".join(det_301)},
                302: {"passed": passed_302, "total": total_302, "details": "\n".join(det_302)},
                "codes": {301: code_301, 302: code_302}
            }

    # ---- SQL ----
    with tabs[2]:
        st.markdown("### Preguntas de SQL")
        sql_mcq = preguntas[(preguntas["categoria"]=="SQL") & (preguntas["tipo"]=="MCQ")]
        for _, row in sql_mcq.iterrows():
            qkey = f"q_{row.id}"
            st.write(f"**[{row.id}]** {row.enunciado}")
            opciones = [o.strip() for o in str(row.opciones).split("|")]
            choice = st.radio("Selecciona una opción:", opciones, key=qkey)
            user_answers[row.id] = choice[:1]
            st.divider()

        st.markdown("### Prácticas de SQL (SQLite demo)")
        st.caption("Puedes consultar las tablas: customers(id,name,city), orders(id,customer_id,order_date), order_items(id,order_id,product,qty,price).")
        code_501 = st.text_area("**[501]** TOP 3 clientes por total vendido (customer, total):", height=160, key="sql_501",
                                placeholder="SELECT ...")
        code_502 = st.text_area("**[502]** Total vendido por mes 2024 (mes YYYY-MM, total):", height=160, key="sql_502",
                                placeholder="SELECT ...")
        if st.button("Probar SQL", key="test_sql_btn"):
            def run_tests_sql(sql_text: str, task_id: int):
                mem = create_demo_sqlite()
                try:
                    df_user = pd.read_sql_query(sql_text, mem)
                except Exception as e:
                    return 0, 3, f"Error al ejecutar SQL: {e}"
                # golden
                if task_id == 501:
                    q = """
                    SELECT c.name AS customer, SUM(oi.qty*oi.price) AS total
                    FROM customers c
                    JOIN orders o ON o.customer_id = c.id
                    JOIN order_items oi ON oi.order_id = o.id
                    GROUP BY c.name
                    ORDER BY total DESC
                    LIMIT 3
                    """
                    df_gold = pd.read_sql_query(q, mem)
                    tests = 3
                else:
                    q = """
                    SELECT strftime('%Y-%m', o.order_date) AS mes, SUM(oi.qty*oi.price) AS total
                    FROM orders o
                    JOIN order_items oi ON oi.order_id = o.id
                    WHERE strftime('%Y', o.order_date) = '2024'
                    GROUP BY strftime('%Y-%m', o.order_date)
                    ORDER BY mes ASC
                    """
                    df_gold = pd.read_sql_query(q, mem)
                    tests = 3
                # Comparación básica
                passed = 0
                details = []
                # columnas
                if task_id == 501:
                    expected_cols = ["customer","total"]
                else:
                    expected_cols = ["mes","total"]
                if list(df_user.columns) == expected_cols:
                    passed += 1
                    details.append("Columnas OK.")
                else:
                    details.append(f"Columnas esperadas {expected_cols}, obtenidas {list(df_user.columns)}.")
                # mismas filas
                try:
                    if len(df_user) == len(df_gold):
                        passed += 1
                        details.append("Cantidad de filas OK.")
                    else:
                        details.append(f"Filas esperadas {len(df_gold)}, obtenidas {len(df_user)}.")
                except:
                    details.append("No se pudo comparar cantidad de filas.")
                # igualdad aproximada (orden/valores)
                try:
                    if df_user.round(2).equals(df_gold.round(2)):
                        passed += 1
                        details.append("Contenido coincide.")
                    else:
                        details.append("Contenido distinto al esperado.")
                except Exception as e:
                    details.append(f"No se pudo comparar contenido: {e}")
                return passed, tests, "\n".join(details)

            p501, t501, d501 = run_tests_sql(code_501, 501)
            p502, t502, d502 = run_tests_sql(code_502, 502)
            st.info("Resultados SQL:")
            st.write(f"[501] Tests pasados: {p501}/{t501}")
            st.write(d501)
            st.write(f"[502] Tests pasados: {p502}/{t502}")
            st.write(d502)
            st.session_state["sql_results"] = {
                501: {"passed": p501, "total": t501, "details": d501, "sql": code_501},
                502: {"passed": p502, "total": t502, "details": d502, "sql": code_502},
            }

    # ---- Envío de la prueba ----
    if st.button("📤 Enviar prueba", type="primary", key="submit_btn"):
        user_id = st.session_state["user_id"]
        started_at = st.session_state.get("started_at", time.time())
        finished_at = time.time()
        duration = finished_at - started_at

        # Calcular puntaje MCQ + Fórmulas
        df = preguntas.copy()
        mcq_form = df[df["tipo"].isin(["MCQ","FORMULA_EXCEL"])].copy()
        total_score = 0.0
        rows_answers = []

        for _, row in mcq_form.iterrows():
            ans = user_answers.get(row.id, "")
            is_ok = 0
            awarded = 0.0
            if row["tipo"] == "MCQ":
                correct = str(row["respuesta_correcta"]).strip().upper()[:1]
                sel = str(ans).strip().upper()[:1]
                is_ok = 1 if sel == correct else 0
                awarded = float(row["puntos"]) if is_ok else 0.0
            else:
                golds = get_golden_variants(row["respuesta_correcta"])
                is_ok = 1 if score_formula(str(ans), golds) else 0
                awarded = float(row["puntos"]) if is_ok else 0.0

            total_score += awarded
            rows_answers.append((row.id, ans, is_ok, awarded))

        # Puntaje Python práctico
        py_res = st.session_state.get("py_results", {})
        for tid in [301, 302]:
            if tid in py_res:
                passed = py_res[tid]["passed"]
                total = py_res[tid]["total"]
                # asignar puntaje proporcional
                pts = float(preguntas[preguntas["id"]==tid]["puntos"].iloc[0])
                awarded = pts * (passed / total)
                total_score += awarded

        # Puntaje SQL práctico
        sql_res = st.session_state.get("sql_results", {})
        for tid in [501, 502]:
            if tid in sql_res:
                passed = sql_res[tid]["passed"]
                total = sql_res[tid]["total"]
                pts = float(preguntas[preguntas["id"]==tid]["puntos"].iloc[0])
                awarded = pts * (passed / total)
                total_score += awarded

        # Guardar en DB
        cur = con.cursor()
        cur.execute("INSERT INTO submissions(user_id, started_at, finished_at, duration_sec, score_total) VALUES (?,?,?,?,?)",
                    (user_id, datetime.utcfromtimestamp(started_at).isoformat(),
                              datetime.utcfromtimestamp(finished_at).isoformat(),
                              duration, total_score))
        sub_id = cur.lastrowid
        for qid, ans, ok, pts in rows_answers:
            cur.execute("INSERT INTO answers(submission_id,qid,response_text,is_correct,score_awarded) VALUES (?,?,?,?,?)",
                        (sub_id, qid, str(ans), int(ok), pts))

        # Guardar detalles de coding (Python)
        if py_res:
            for tid in [301,302]:
                if tid in py_res:
                    d = py_res[tid]
                    pts = float(preguntas[preguntas["id"]==tid]["puntos"].iloc[0]) * (d["passed"]/d["total"])
                    cur.execute("INSERT INTO coding(submission_id,task_type,task_id,passed_tests,total_tests,details,score_awarded) VALUES (?,?,?,?,?,?,?)",
                                (sub_id, "PY", tid, d["passed"], d["total"], d["details"], pts))
        # Guardar detalles de SQL
        if sql_res:
            for tid in [501,502]:
                if tid in sql_res:
                    d = sql_res[tid]
                    pts = float(preguntas[preguntas["id"]==tid]["puntos"].iloc[0]) * (d["passed"]/d["total"])
                    cur.execute("INSERT INTO coding(submission_id,task_type,task_id,passed_tests,total_tests,details,score_awarded) VALUES (?,?,?,?,?,?,?)",
                                (sub_id, "SQL", tid, d["passed"], d["total"], d["details"], pts))

        con.commit()
        st.success(f"Entrega registrada. Puntaje total: {round(total_score,2)} puntos. ¡Gracias!")

# ------------- Admin Dashboard -------------
st.markdown("---")
st.subheader("🛡️ Administrador")
colA, colB = st.columns([1,3])
with colA:
    admin_try = st.text_input("Admin key", type="password", key="adminkey2")
    check = st.button("Entrar a Dashboard", key="admin_enter")
if (check and admin_try == ADMIN_KEY) or st.session_state.get("is_admin"):
    st.session_state["is_admin"] = True
    cur = con.cursor()
    st.success("Acceso administrador concedido.")

    # KPI
    k1, k2, k3, k4 = st.columns(4)
    total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_subs  = cur.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    avg_score   = cur.execute("SELECT COALESCE(AVG(score_total),0) FROM submissions").fetchone()[0]
    avg_dur     = cur.execute("SELECT COALESCE(AVG(duration_sec),0) FROM submissions").fetchone()[0]
    k1.metric("Usuarios", total_users)
    k2.metric("Entregas", total_subs)
    k3.metric("Promedio Puntaje", round(avg_score,2))
    k4.metric("Duración Promedio (min)", round(avg_dur/60,2))

    st.markdown("### Resultados detallados")
    df_users = pd.read_sql_query("SELECT * FROM users", con)
    df_subs  = pd.read_sql_query("SELECT * FROM submissions", con)
    df_ans   = pd.read_sql_query("SELECT * FROM answers", con)
    df_code  = pd.read_sql_query("SELECT * FROM coding", con)

    if not df_subs.empty:
        df_join = df_subs.merge(df_users, left_on="user_id", right_on="id", suffixes=("_sub","_user"))
        st.dataframe(df_join[["id_sub","name","email","doc","score_total","duration_sec","started_at","finished_at"]], use_container_width=True)

        with st.expander("Ver respuestas MCQ/Fórmulas"):
            st.dataframe(df_ans, use_container_width=True)

        with st.expander("Ver resultados de prácticas (Python/SQL)"):
            st.dataframe(df_code, use_container_width=True)

        # Descargas
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            csv = df_join.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar resultados (CSV)", csv, "resultados.csv", "text/csv")
        with bcol2:
            # Excel export
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                df_join.to_excel(writer, sheet_name="Submissions", index=False)
                df_ans.to_excel(writer, sheet_name="Answers", index=False)
                df_code.to_excel(writer, sheet_name="Coding", index=False)
            st.download_button("⬇️ Descargar resultados (XLSX)", out.getvalue(), "resultados.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    else:
        st.info("Aún no hay entregas registradas.")
else:
    st.info("Ingrese Admin key para ver el Dashboard.")
