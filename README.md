
# Prueba Técnica — Excel Avanzado, Python Básico y SQL Básico (Streamlit)

Este paquete contiene:
- `app_prueba_tecnica.py`: App Streamlit (registro, prueba, scoring y dashboard admin).
- `Cuestionario_Prueba_Tecnica.xlsx`: Banco de preguntas y datos SQL de ejemplo.
- `requirements.txt`: Dependencias mínimas.

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app_prueba_tecnica.py
```

> **Admin Key**: define una variable de entorno `ADMIN_KEY` o en `.streamlit/secrets.toml`:
```
# .streamlit/secrets.toml
ADMIN_KEY = "cambia-esta-clave"
```

## Estructura de la plantilla Excel

- **Instrucciones**: guía rápida.
- **Preguntas**: columnas: id, categoria, tipo, puntos, enunciado, opciones, respuesta_correcta.
- **Claves**: respuestas correctas (ocultar al compartir).
- **Datos_SQL_***: tablas de ejemplo para ejercicios SQL.

Tipos de pregunta:
- `MCQ`: opción múltiple (opciones en formato `A) ... | B) ... | C) ... | D) ...`).
- `FORMULA_EXCEL`: valida variantes equivalentes (se aceptan español/inglés).
- `CODIGO_PY`: se evalúa con tests (fizzbuzz y flatten_list).
- `SQL_QUERY`: se evalúa en SQLite en memoria vs resultado esperado.

## Despliegue en Streamlit Cloud / GitHub

1. Sube estos archivos a tu repositorio:
   - `app_prueba_tecnica.py`
   - `Cuestionario_Prueba_Tecnica.xlsx`
   - `requirements.txt`
   - (Opcional) `.streamlit/secrets.toml` con `ADMIN_KEY`.

2. En Streamlit, configura el repo y la variable `ADMIN_KEY` en **Secrets**.

3. La app creará `quiz.db` (SQLite) para resultados. En Streamlit Cloud el almacenamiento es efímero;
   para persistencia real, considera conectar una base externa (p. ej., Google Sheets, Supabase o Postgres gestionado).

## Notas

- La hoja **Claves** contiene respuestas; **ocúltala** si compartes el Excel con candidatos.
- La validación de fórmulas compara cadenas normalizadas (insensible a mayúsculas/acentos).
- El sandbox de Python no permite `import`, dunders ni operaciones peligrosas.
- El SQL se ejecuta en una base **demo** en memoria.
