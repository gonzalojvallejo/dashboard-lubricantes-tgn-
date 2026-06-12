import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import io
import os
import base64
import requests
import json

st.set_page_config(
    page_title="TGN · Dashboard Lubricantes",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Login wall ──────────────────────────────────────────────────────────────────
def check_login():
    if st.session_state.get("authenticated"):
        return True

    # Center the login form
    _, col, _ = st.columns([1.5, 2, 1.5])
    with col:
        st.markdown("""
        <div style="text-align:center; padding: 40px 0 20px 0;">
            <img src="https://i.imgur.com/RDfxCkp.jpg" width="120"
                 style="display:block;margin:0 auto 16px auto;">
            <div style="font-size:1.6rem;font-weight:700;color:#e8edf2;">
                Dashboard · Análisis de Lubricantes
            </div>
            <div style="font-size:0.9rem;color:#78909c;margin-top:4px;">
                Transportadora de Gas del Norte S.A.
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_wall"):
            st.markdown("#### Iniciar sesión")
            user = st.text_input("Usuario", placeholder="Ingresá tu usuario")
            pwd  = st.text_input("Contraseña", type="password", placeholder="Ingresá tu contraseña")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)

            if submitted:
                try:
                    users = st.secrets["users"]
                    if user in users and users[user] == pwd:
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = user
                        st.session_state["is_admin"] = (user.lower() == "admin")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error de configuración: {e}")
    return False

if not check_login():
    st.stop()

# ── Constantes ─────────────────────────────────────────────────────────────────
GITHUB_USER   = "gonzalojvallejo"
GITHUB_REPO   = "dashboard-lubricantes-tgn-"
GITHUB_BRANCH = "main"
DB_FILE       = "database.csv"
ADMIN_USER    = "Admin"
ADMIN_PASS    = "Admin"

PLANT_COORDS = {
    "BAL": {"name": "Baldissera",     "lat": -33.532, "lon": -62.300},  # General Baldissera, Córdoba
    "BEA": {"name": "Beazley",        "lat": -33.750, "lon": -66.645},  # Beazley, San Luis (RN146 km183)
    "BEL": {"name": "Leones",         "lat": -32.650, "lon": -62.283},  # San Jerónimo, Córdoba (RN9 km456)
    "COC": {"name": "Cochico",        "lat": -36.250, "lon": -66.930},  # Santa Isabel, La Pampa
    "DEA": {"name": "Dean Funes",     "lat": -30.424, "lon": -64.350},  # Dean Funes, Córdoba
    "CHA": {"name": "Chaján",         "lat": -33.582, "lon": -64.982},  # Chaján, Córdoba (RN8 km692)
    "FER": {"name": "Ferreyra",       "lat": -31.430, "lon": -63.817},  # Capilla de Remedios, Córdoba
    "JER": {"name": "San Jerónimo",   "lat": -32.879, "lon": -61.023},  # San Jerónimo Sud, Santa Fe
    "LCA": {"name": "La Carlota",     "lat": -33.420, "lon": -63.316},  # La Carlota, Córdoba
    "LMR": {"name": "La Mora",        "lat": -35.000, "lon": -66.787},  # La Mora, entre BEA y COC
    "LPZ": {"name": "La Paz",         "lat": -33.467, "lon": -67.550},  # La Paz, Mendoza (ok)
    "LUM": {"name": "Lumbreras",      "lat": -25.033, "lon": -64.733},  # Lumbreras, Salta
    "LAV": {"name": "Lavalle",        "lat": -28.200, "lon": -65.117},  # Lavalle, Santiago del Estero
    "PIC": {"name": "Pichanal",       "lat": -23.317, "lon": -64.217},  # Pichanal, Salta
    "PUE": {"name": "Puelen",         "lat": -37.520, "lon": -67.520},  # Puelen, La Pampa
    "REC": {"name": "Recreo",         "lat": -29.264, "lon": -65.063},  # Recreo, Catamarca
    "RLB": {"name": "Río Las Burras", "lat": -24.695, "lon": -66.178},  # La Poma, Salta
    "TIO": {"name": "Tío Pujio",      "lat": -32.317, "lon": -63.333},  # Tío Pujio, Córdoba

    "TUC": {"name": "Tucumán",        "lat": -26.683, "lon": -65.150},  # Cevil Pozo, Tucumán
}

COLS_NEEDED = {
    "Overall": "overall", "Problem": "problema", "Status": "status",
    "Area": "area", "Machine Common Name": "equipo", "Component": "componente",
    "Fluid": "lubricante", "Sample No.": "muestra", "Sampled": "fecha_muestra",
    "Completed": "fecha_completado", "Fluid Age": "edad_fluido",
    "Mach. Age": "edad_maquina", "UOM": "uom", "Fluid Maint": "mant_fluido",
    "Recommendation": "recomendacion", "Wear": "desgaste",
    "Contamination": "contaminacion", "Oil Condition": "condicion_aceite",
}

COMPONENT_ES = {
    "Turbine": "Turbina", "Natural Gas Engine": "Motor Gas Natural",
    "Natural Gas Compression Engine": "Motor Compresor Gas",
    "Reciprocating Compressor": "Compresor Reciprocante", "Coolant": "Refrigerante",
}

STATUS_ORDER  = {"SEVERE": 0, "ABNORMAL": 1, "MARGINAL": 2, "NORMAL": 3}
STATUS_COLOR  = {"NORMAL": "#4caf50", "MARGINAL": "#f44336", "ABNORMAL": "#ff9800", "SEVERE": "#d32f2f"}
STATUS_MAP_COLOR = {"NORMAL": "green", "MARGINAL": "red", "ABNORMAL": "orange", "SEVERE": "darkred"}

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0b1622; }
[data-testid="stSidebar"] { background-color: #111d2c; }
h1,h2,h3,h4 { color: #e8edf2 !important; }
p, label, div { color: #b0bec5; }
.stTabs [data-baseweb="tab-list"] { background: #111d2c; border-radius: 10px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; color: #78909c; font-weight: 500; padding: 8px 20px; }
.stTabs [aria-selected="true"] { background: #1a3a5c !important; color: #64b5f6 !important; }
[data-testid="stMetric"] { background: #111d2c; border-radius: 10px; padding: 16px 20px; border-left: 4px solid #1a3a5c; }
[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700; }
.equip-card { border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; border-left: 5px solid #555; background: #111d2c; }
.equip-card.NORMAL   { border-color: #4caf50; background: #0f1f12; }
.equip-card.SEVERE   { border-color: #d32f2f; background: #2a0000; }
    .equip-card.MARGINAL { border-color: #f44336; background: #1f0f0f; }
.equip-card.ABNORMAL { border-color: #ff9800; background: #1f1a0f; }
.status-badge { display:inline-block; padding:3px 12px; border-radius:12px; font-weight:700; font-size:0.78rem; }
.badge-NORMAL   { background:#1b5e20; color:#a5d6a7; }
.badge-SEVERE   { background:#7b0000; color:#ff8a80; }
    .badge-MARGINAL { background:#b71c1c; color:#ef9a9a; }
.badge-ABNORMAL { background:#e65100; color:#ffcc80; }
.equip-name   { font-size:1rem; font-weight:600; color:#e0e7ef; }
.equip-detail { font-size:0.82rem; color:#90a4ae; margin-top:4px; }
.equip-rec    { font-size:0.80rem; color:#b0bec5; margin-top:6px; border-top:1px solid #1a2d3d; padding-top:6px; }
.kpi-card { background:#111d2c; border-radius:12px; padding:20px; border:1px solid #1a3a5c; }
hr { border-color: #1a2d3d; }
.stButton>button { background:#1a3a5c; color:#64b5f6; border:1px solid #1a3a5c; border-radius:8px; font-weight:500; }
.stButton>button:hover { background:#1e4a7a; border-color:#64b5f6; }
</style>
""", unsafe_allow_html=True)

# ── GitHub helpers ─────────────────────────────────────────────────────────────
def get_github_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except:
        return None

def load_db_from_github():
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{DB_FILE}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            if "fecha_muestra" in df.columns:
                df["fecha_muestra"] = pd.to_datetime(df["fecha_muestra"], errors="coerce")
            if "fecha_completado" in df.columns:
                df["fecha_completado"] = pd.to_datetime(df["fecha_completado"], errors="coerce")
            return df
    except:
        pass
    return None

def push_db_to_github(df, token):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{DB_FILE}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    csv_content = df.to_csv(index=False)
    encoded = base64.b64encode(csv_content.encode()).decode()
    # Get current SHA
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {"message": f"Actualizar base de datos {datetime.now().strftime('%Y-%m-%d %H:%M')}",
               "content": encoded, "branch": GITHUB_BRANCH}
    if sha:
        payload["sha"] = sha
    r2 = requests.put(url, headers=headers, json=payload)
    return r2.status_code in [200, 201]

def process_excel(uploaded_file):
    df = pd.read_excel(uploaded_file, sheet_name="sample")
    rename = {k: v for k, v in COLS_NEEDED.items() if k in df.columns}
    df = df.rename(columns=rename)
    df = df[[c for c in COLS_NEEDED.values() if c in df.columns]]
    df["planta_cod"]    = df["equipo"].str.extract(r"^([A-Z]{2,4})\s*-")
    df["equipo_tag"]    = df["equipo"].str.extract(r"-\s*(.+)$").fillna(df["equipo"])
    df["componente_es"] = df["componente"].map(COMPONENT_ES).fillna(df["componente"])
    for col in ["fecha_muestra", "fecha_completado"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["overall"] = df["overall"].str.upper().str.strip()
    return df

def merge_dbs(existing, new_data):
    """Merge new data into existing, avoiding duplicates by muestra"""
    if existing is None or existing.empty:
        return new_data
    if "muestra" in existing.columns and "muestra" in new_data.columns:
        existing_muestras = set(existing["muestra"].dropna())
        new_rows = new_data[~new_data["muestra"].isin(existing_muestras)]
        return pd.concat([existing, new_rows], ignore_index=True)
    return pd.concat([existing, new_data], ignore_index=True).drop_duplicates()

def get_latest_per_equipment(df):
    """Keep only the latest analysis per equipment"""
    if df.empty:
        return df
    df = df.copy()
    if "fecha_muestra" in df.columns:
        df["_sort"] = df["fecha_muestra"].fillna(pd.Timestamp.min)
    else:
        df["_sort"] = 0
    df = df.sort_values("_sort", ascending=False)
    df = df.drop_duplicates(subset=["equipo"], keep="first")
    df = df.drop(columns=["_sort"])
    return df

def plant_worst_status(df):
    """Get worst status per plant"""
    latest = get_latest_per_equipment(df)
    result = {}
    for plant, group in latest.groupby("planta_cod"):
        statuses = group["overall"].map(STATUS_ORDER).dropna()
        if not statuses.empty:
            worst_idx = statuses.idxmin()
            result[plant] = group.loc[worst_idx, "overall"]
    return result

def status_badge(status):
    return f'<span class="status-badge badge-{status}">{status}</span>'

# ── Load data ──────────────────────────────────────────────────────────────────
if "selected_tab" not in st.session_state:
    st.session_state["selected_tab"] = 0
if "selected_equipo" not in st.session_state:
    st.session_state["selected_equipo"] = None

if "df" not in st.session_state:
    db = load_db_from_github()
    st.session_state["df"] = db

df_global = st.session_state.get("df")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 10px 0 20px 0;">
    <img src="https://i.imgur.com/RDfxCkp.jpg" width="110" style="margin-bottom:12px;display:block;margin-left:auto;margin-right:auto;">
    <div style="font-size:2.2rem; font-weight:700; color:#e8edf2; letter-spacing:-0.5px;">🛢️ Dashboard · Análisis de Lubricantes</div>
    <div style="font-size:1rem; color:#78909c; margin-top:6px;">
        <b style="color:#90a4ae;">Transportadora de Gas del Norte S.A.</b>
        &nbsp;·&nbsp; Análisis de Condición
        &nbsp;·&nbsp; Gerencia de Mantenimiento
    </div>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

# User info bar
_uname = st.session_state.get("username", "")
_role  = "Administrador" if st.session_state.get("is_admin") else "Operador"
hcol1, hcol2 = st.columns([8, 1])
with hcol2:
    st.markdown(f"""
    <div style="text-align:right;font-size:12px;color:#546e7a;padding-top:4px;">
        👤 <b style="color:#90a4ae">{_uname}</b> · {_role}
    </div>
    """, unsafe_allow_html=True)
    if st.button("🚪 Salir", key="logout_header"):
        st.session_state.clear()
        st.rerun()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_main, tab_detalle, tab_kpi, tab_admin = st.tabs([
    "🗺️  Mapa de Plantas",
    "🔎  Detalle por Equipo",
    "📊  KPIs y Métricas",
    "⚙️  Administración",
])

# ══════════════════════════════════════════════════════════════════════
# TAB A — MAPA
# ══════════════════════════════════════════════════════════════════════
with tab_main:
    if df_global is None or df_global.empty:
        st.info("Sin datos cargados. Cargá un Excel en la pestaña Administración.")
    else:
        import folium
        from streamlit_folium import st_folium

        latest_df = get_latest_per_equipment(df_global)
        plant_status = plant_worst_status(df_global)

        # Build map
        m = folium.Map(
            location=[-34.0, -64.0],
            zoom_start=5,
            tiles=None
        )
        # Base oscura al 60% para mejor visibilidad
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
            attr="© CartoDB © OpenStreetMap",
            opacity=0.55
        ).add_to(m)
        # Labels de capitales/ciudades importantes (CartoDB)
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png",
            attr="© CartoDB",
            opacity=0.7
        ).add_to(m)

        for cod, info in PLANT_COORDS.items():
            status = plant_status.get(cod, "NORMAL")
            color  = STATUS_MAP_COLOR.get(status, "blue")
            plant_data = latest_df[latest_df["planta_cod"] == cod]

            # Build popup HTML
            comp_rows = plant_data[plant_data["area"] == "COMPRESIÓN"] if "area" in plant_data.columns else pd.DataFrame()
            gen_rows  = plant_data[plant_data["area"] == "GENERACIÓN"] if "area" in plant_data.columns else pd.DataFrame()

            def make_rows(rows):
                if rows.empty:
                    return "<tr><td colspan='3' style='color:#888'>Sin datos</td></tr>"
                html = ""
                for _, r in rows.iterrows():
                    s = r.get("overall", "")
                    c = {"NORMAL":"#4caf50","MARGINAL":"#f44336","ABNORMAL":"#ff9800","SEVERE":"#d32f2f"}.get(s,"#aaa")
                    html += f"""<tr>
                        <td style='padding:3px 8px;color:#e0e7ef'>{r.get('equipo_tag','')}</td>
                        <td style='padding:3px 6px;color:#b0bec5'>{r.get('componente_es','')}</td>
                        <td style='padding:3px 6px;color:{c};font-weight:bold'>{s}</td></tr>"""
                return html

            popup_html = f"""
            <div style='font-family:Arial;min-width:380px;background:#1a2535;color:#e0e7ef;border-radius:8px;overflow:hidden'>
              <div style='background:#0f1922;padding:10px 14px;font-size:14px;font-weight:bold;border-bottom:1px solid #2a3d52'>
                Planta {cod}
                <span style='float:right;background:{"#1b5e20" if status=="NORMAL" else "#b71c1c" if status=="MARGINAL" else "#e65100"};color:{"#a5d6a7" if status=="NORMAL" else "#ef9a9a" if status=="MARGINAL" else "#ffcc80"};padding:2px 10px;border-radius:10px;font-size:11px'>{status}</span>
              </div>
              <div style='display:flex;gap:0'>
                <div style='flex:1;padding:10px;border-right:1px solid #2a3d52'>
                  <div style='font-size:11px;color:#90a4ae;margin-bottom:6px'>COMPRESIÓN</div>
                  <table style='width:100%;font-size:11px;border-collapse:collapse'>{make_rows(comp_rows)}</table>
                </div>
                <div style='flex:1;padding:10px'>
                  <div style='font-size:11px;color:#90a4ae;margin-bottom:6px'>GENERACIÓN</div>
                  <table style='width:100%;font-size:11px;border-collapse:collapse'>{make_rows(gen_rows)}</table>
                </div>
              </div>
            </div>
            """

            _sc = {"NORMAL":"#4caf50","MARGINAL":"#f44336","ABNORMAL":"#ff9800","SEVERE":"#d32f2f"}.get(status,"#aaa")
            folium.CircleMarker(
                location=[info["lat"], info["lon"]],
                radius=14,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.95,
                weight=3,
                popup=folium.Popup(popup_html, max_width=420),
                tooltip=folium.Tooltip(
                    f"<b style='font-size:13px'>{cod} — {info['name']}</b><br>"
                    f"<span style='color:{_sc}'>● {status}</span><br>"
                    f"<i style='font-size:10px;color:#90a4ae'>Hacé clic para ver equipos</i>",
                    sticky=True
                ),
            ).add_to(m)

            folium.Marker(
                location=[info["lat"], info["lon"]],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:11px;font-weight:bold;color:#e0e7ef;text-shadow:1px 1px 2px #000;white-space:nowrap;margin-top:16px;margin-left:14px;">{cod}</div>',
                    icon_size=(50, 20), icon_anchor=(0, 0)
                )
            ).add_to(m)

        # Legend
        # Remove white popup border
        popup_css = """<style>
        .leaflet-popup-content-wrapper {
            background:transparent!important;border:none!important;
            box-shadow:none!important;padding:0!important;border-radius:0!important;
        }
        .leaflet-popup-tip-container{display:none!important;}
        .leaflet-popup-content{margin:0!important;}
        </style>"""
        m.get_root().html.add_child(folium.Element(popup_css))

        legend_html = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:#1a2535;
                    border:1px solid #2a3d52;border-radius:8px;padding:10px 14px;font-family:Arial">
          <div style="font-size:12px;font-weight:bold;color:#e0e7ef;margin-bottom:6px">Estado de planta</div>
          <div style="font-size:11px;color:#4caf50">● Normal</div>
          <div style="font-size:11px;color:#ff9800">● Anormal</div>
          <div style="font-size:11px;color:#f44336">● Marginal</div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        st.markdown("#### 🗺️ Estado de plantas — hacé clic en un punto para ver el detalle")
        map_data = st_folium(m, width="100%", height=620, returned_objects=["last_object_clicked_tooltip"])

        # Detect plant click via tooltip
        if map_data and map_data.get("last_object_clicked_tooltip"):
            tooltip_val = map_data["last_object_clicked_tooltip"]
            # tooltip format is "COD — STATUS"
            if " — " in str(tooltip_val):
                clicked_cod = str(tooltip_val).split(" — ")[0].strip()
                if clicked_cod != st.session_state.get("clicked_plant"):
                    st.session_state["clicked_plant"] = clicked_cod
                    st.session_state["selected_equipo"] = None

        # Show plant equipment selector below map
        clicked_plant = st.session_state.get("clicked_plant")
        if clicked_plant and df_global is not None:
            plant_equips = get_latest_per_equipment(df_global)
            plant_equips = plant_equips[plant_equips["planta_cod"] == clicked_plant]
            if not plant_equips.empty:
                st.markdown(f"**Seleccioná un equipo de {clicked_plant}:**")
                eq_options = plant_equips["equipo"].tolist()
                eq_labels = plant_equips["equipo_tag"].tolist()
                cols_eq = st.columns(min(len(eq_options), 4))
                for i, (eq, lbl) in enumerate(zip(eq_options, eq_labels)):
                    row = plant_equips[plant_equips["equipo"] == eq].iloc[0]
                    s = row["overall"]
                    color = STATUS_COLOR.get(s, "#555")
                    with cols_eq[i % 4]:
                        if st.button(f"{lbl}", key=f"eq_btn_{eq}",
                                     help=f"{row.get('componente_es','')} — {s}"):
                            st.session_state["selected_equipo"] = eq
                            st.rerun()

        # Show equipment detail below map when selected
        _sel = st.session_state.get("selected_equipo")
        if _sel and df_global is not None:
            st.markdown("---")
            eq_data = get_latest_per_equipment(df_global)
            eq_data = eq_data[eq_data["equipo"] == _sel]
            if not eq_data.empty:
                row = eq_data.iloc[0]
                status = row["overall"]
                fecha_str = row["fecha_muestra"].strftime("%d/%m/%Y") if pd.notna(row.get("fecha_muestra")) else "—"
                edad_str = f"{int(row['edad_fluido']):,} hrs" if pd.notna(row.get("edad_fluido")) else "—"
                rec = str(row.get("recomendacion","") or "—")
                desgaste = str(row.get("desgaste","") or "")
                contam = str(row.get("contaminacion","") or "")
                cond = str(row.get("condicion_aceite","") or "")
                extras = "".join(
                    f'<div class="equip-rec"><b style="color:#78909c">{lbl}:</b> {txt}</div>'
                    for lbl, txt in [("⚙️ Desgaste", desgaste),("💧 Contaminación", contam),("🧪 Cond. Aceite", cond)]
                    if txt.strip()
                )
                st.markdown(f"""
                <div class="equip-card {status}">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span class="equip-name">📋 {row.get('planta_cod','—')} · {row.get('equipo_tag','—')}</span>
                    <span class="status-badge badge-{status}">{status}</span>
                  </div>
                  <div class="equip-detail">
                    🏭 {row.get('area','—')} &nbsp;|&nbsp;
                    🔩 {row.get('componente_es','—')} &nbsp;|&nbsp;
                    🛢️ {row.get('lubricante','—')} &nbsp;|&nbsp;
                    📅 {fecha_str} &nbsp;|&nbsp; ⏱️ {edad_str}
                  </div>
                  <div class="equip-rec"><b style="color:#78909c">📌 Recomendación:</b> {rec}</div>
                  {extras}
                </div>
                """, unsafe_allow_html=True)
            if st.button("✖ Cerrar detalle"):
                st.session_state["selected_equipo"] = None
                st.rerun()

        # Summary below map
        st.markdown("---")
        pcols = st.columns(len(PLANT_COORDS))
        for i, (cod, info) in enumerate(PLANT_COORDS.items()):
            status = plant_status.get(cod, "—")
            color  = STATUS_COLOR.get(status, "#555")
            with pcols[i]:
                st.markdown(f"""
                <div style='text-align:center;background:#111d2c;border-radius:8px;padding:8px 4px;border-top:3px solid {color}'>
                  <div style='font-size:13px;font-weight:600;color:#e0e7ef'>{cod}</div>
                  <div style='font-size:10px;color:{color};font-weight:bold'>{status}</div>
                </div>
                """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# TAB B — DETALLE
# ══════════════════════════════════════════════════════════════════════
with tab_detalle:
    if df_global is None or df_global.empty:
        st.info("Sin datos. Cargá un Excel en la pestaña Administración.")
    else:
        dff = df_global.copy()
        dff["sort_key"] = dff["overall"].map(STATUS_ORDER).fillna(3)
        dff = dff.sort_values("sort_key")

        # Check if coming from map popup click
        _selected_eq = st.session_state.get("selected_equipo")
        if _selected_eq:
            st.info(f"📍 Mostrando: **{_selected_eq}** — [Ver todos](javascript:void(0))")
            if st.button("✖ Limpiar filtro de mapa"):
                st.session_state["selected_equipo"] = None
                st.query_params.clear()
                st.rerun()

        # Filters
        with st.expander("🔍 Filtros", expanded=not bool(_selected_eq)):
            fc1, fc2, fc3, fc4 = st.columns(4)
            plantas    = sorted(dff["planta_cod"].dropna().unique())
            areas      = sorted(dff["area"].dropna().unique()) if "area" in dff.columns else []
            estados    = ["SEVERE", "ABNORMAL", "MARGINAL", "NORMAL"]
            componentes = sorted(dff["componente_es"].dropna().unique()) if "componente_es" in dff.columns else []

            sel_plantas = fc1.multiselect("Planta", plantas, default=plantas)
            sel_areas   = fc2.multiselect("Área", areas, default=areas)
            sel_estados = fc3.multiselect("Estado", estados, default=estados)
            sel_comp    = fc4.multiselect("Componente", componentes, default=componentes)

            solo_ultimo = st.checkbox("Mostrar solo último análisis por equipo", value=True)

        mask = pd.Series([True] * len(dff), index=dff.index)
        if sel_plantas:
            mask &= dff["planta_cod"].isin(sel_plantas)
        if sel_areas and "area" in dff.columns:
            mask &= dff["area"].isin(sel_areas)
        if sel_estados:
            mask &= dff["overall"].isin(sel_estados)
        if sel_comp and "componente_es" in dff.columns:
            mask &= dff["componente_es"].isin(sel_comp)
        dff = dff[mask]

        if solo_ultimo:
            dff = get_latest_per_equipment(dff)

        # Filter by selected equipment from map
        _selected_eq = st.session_state.get("selected_equipo")
        if _selected_eq:
            dff_equipo = dff[dff["equipo"] == _selected_eq]
            if not dff_equipo.empty:
                dff = dff_equipo

        n_sv = (dff["overall"] == "SEVERE").sum()
        n_ab = (dff["overall"] == "ABNORMAL").sum()
        n_mg = (dff["overall"] == "MARGINAL").sum()
        n_ok = (dff["overall"] == "NORMAL").sum()

        tab_sv, tab_ab, tab_mg, tab_ok, tab_all = st.tabs([
            f"🔴 Severos ({n_sv})",
            f"🟠 Anormales ({n_ab})",
            f"🟡 Marginales ({n_mg})",
            f"🟢 Normales ({n_ok})",
            f"📋 Todos ({len(dff)})"
        ])

        def render_cards(data):
            if data.empty:
                st.info("Sin registros.")
                return
            for _, row in data.iterrows():
                fecha_str = row["fecha_muestra"].strftime("%d/%m/%Y") if pd.notna(row.get("fecha_muestra")) else "—"
                edad_str  = f"{int(row['edad_fluido']):,} hrs" if pd.notna(row.get("edad_fluido")) else "—"
                status    = row["overall"]
                rec       = str(row.get("recomendacion", "") or "—")
                desgaste  = str(row.get("desgaste", "") or "")
                contam    = str(row.get("contaminacion", "") or "")
                cond      = str(row.get("condicion_aceite", "") or "")
                extras    = "".join(
                    f'<div class="equip-rec"><b style="color:#78909c">{lbl}:</b> {txt}</div>'
                    for lbl, txt in [("⚙️ Desgaste", desgaste), ("💧 Contaminación", contam), ("🧪 Cond. Aceite", cond)]
                    if txt.strip()
                )
                st.markdown(f"""
                <div class="equip-card {status}">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span class="equip-name">{row.get('planta_cod','—')} &nbsp;·&nbsp; {row.get('equipo_tag','—')}</span>
                    {status_badge(status)}
                  </div>
                  <div class="equip-detail">
                    🏭 {row.get('area','—')} &nbsp;|&nbsp;
                    🔩 {row.get('componente_es','—')} &nbsp;|&nbsp;
                    🛢️ {row.get('lubricante','—')} &nbsp;|&nbsp;
                    📅 {fecha_str} &nbsp;|&nbsp;
                    ⏱️ {edad_str}
                  </div>
                  <div class="equip-rec"><b style="color:#78909c">📌 Recomendación:</b> {rec}</div>
                  {extras}
                </div>
                """, unsafe_allow_html=True)

        with tab_sv: render_cards(dff[dff["overall"] == "SEVERE"])
        with tab_ab: render_cards(dff[dff["overall"] == "ABNORMAL"])
        with tab_mg: render_cards(dff[dff["overall"] == "MARGINAL"])
        with tab_ok: render_cards(dff[dff["overall"] == "NORMAL"])
        with tab_all: render_cards(dff)

        with st.expander("📄 Tabla completa"):
            show_cols = [c for c in ["planta_cod","equipo_tag","area","componente_es","lubricante",
                                     "overall","problema","fecha_muestra","edad_fluido","recomendacion"] if c in dff.columns]
            st.dataframe(dff[show_cols], use_container_width=True, hide_index=True)
            csv = dff[show_cols].to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar CSV", csv, "resultados.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════
# TAB C — KPIs
# ══════════════════════════════════════════════════════════════════════
with tab_kpi:
    if df_global is None or df_global.empty:
        st.info("Sin datos. Cargá un Excel en la pestaña Administración.")
    else:
        df_k = get_latest_per_equipment(df_global)
        total = len(df_k)
        n_sv  = (df_k["overall"] == "SEVERE").sum()
        n_ab  = (df_k["overall"] == "ABNORMAL").sum()
        n_mg  = (df_k["overall"] == "MARGINAL").sum()
        n_ok  = (df_k["overall"] == "NORMAL").sum()
        pct_ok = round(n_ok / total * 100) if total else 0
        pct_crit = round((n_sv + n_ab + n_mg) / total * 100) if total else 0

        # KPI cards row 1
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("📋 Equipos monitoreados", total)
        k2.metric("🔴 Severos",   n_sv, delta=f"{round(n_sv/total*100)}%" if total else "0%", delta_color="inverse")
        k3.metric("🟠 Anormales", n_ab, delta=f"{round(n_ab/total*100)}%" if total else "0%", delta_color="inverse")
        k4.metric("🟡 Marginales",n_mg, delta=f"{round(n_mg/total*100)}%" if total else "0%", delta_color="inverse")
        k5.metric("🟢 Normales",  n_ok, delta=f"{round(n_ok/total*100)}%" if total else "0%", delta_color="normal")
        k6.metric("✅ Confiabilidad flota", f"{pct_ok}%")

        st.markdown("---")

        # Row 1 charts
        ch1, ch2, ch3 = st.columns(3)

        with ch1:
            st.markdown("##### Estado general de flota")
            pie_data = pd.DataFrame({"Estado": ["SEVERE","ABNORMAL","MARGINAL","NORMAL"],
                                     "Cantidad": [n_sv, n_ab, n_mg, n_ok]})
            pie_data = pie_data[pie_data["Cantidad"] > 0]
            fig = px.pie(pie_data, names="Estado", values="Cantidad",
                         color="Estado",
                         color_discrete_map={"NORMAL":"#4caf50","MARGINAL":"#f44336","ABNORMAL":"#ff9800","SEVERE":"#d32f2f"},
                         hole=0.55)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#b0bec5", showlegend=True,
                              legend=dict(orientation="h", y=-0.2),
                              margin=dict(t=10,b=10,l=10,r=10), height=280)
            fig.update_traces(textfont_color="#fff")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            st.markdown("##### Tipo de problema")
            PROBLEM_COLORS = {"Normal":"#4caf50","Wear":"#ff9800","ISO":"#ff9800",
                              "Insolubles":"#f44336","Degradation":"#f44336","Severe":"#d32f2f"}
            prob_data = df_k["problema"].value_counts().reset_index()
            prob_data.columns = ["Problema","Cantidad"]
            fig2 = px.bar(prob_data, x="Cantidad", y="Problema", orientation="h",
                          color="Problema", color_discrete_map=PROBLEM_COLORS)
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#b0bec5", showlegend=False,
                               margin=dict(t=10,b=10,l=10,r=10), height=280,
                               xaxis=dict(gridcolor="#1a2d3d"))
            fig2.update_traces(marker_line_width=0)
            st.plotly_chart(fig2, use_container_width=True)

        with ch3:
            st.markdown("##### Estado por planta")
            pivot = df_k.groupby(["planta_cod","overall"]).size().unstack(fill_value=0)
            for s in ["SEVERE","ABNORMAL","MARGINAL","NORMAL"]:
                if s not in pivot.columns: pivot[s] = 0
            pivot = pivot[["SEVERE","ABNORMAL","MARGINAL","NORMAL"]].sort_values("SEVERE", ascending=False)
            fig3 = go.Figure()
            for estado, color in [("SEVERE","#d32f2f"),("ABNORMAL","#ff9800"),("MARGINAL","#f44336"),("NORMAL","#4caf50")]:
                fig3.add_trace(go.Bar(name=estado, x=pivot.index, y=pivot[estado],
                                      marker_color=color, marker_line_width=0))
            fig3.update_layout(barmode="stack", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color="#b0bec5",
                               legend=dict(orientation="h", y=-0.3),
                               margin=dict(t=10,b=10,l=10,r=10), height=280,
                               xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
                               yaxis=dict(gridcolor="#1a2d3d"))
            st.plotly_chart(fig3, use_container_width=True)

        st.markdown("---")

        # Row 2 charts
        ch4, ch5 = st.columns(2)

        with ch4:
            st.markdown("##### Estado por tipo de componente")
            if "componente_es" in df_k.columns:
                pivot2 = df_k.groupby(["componente_es","overall"]).size().unstack(fill_value=0)
                for s in ["SEVERE","ABNORMAL","MARGINAL","NORMAL"]:
                    if s not in pivot2.columns: pivot2[s] = 0
                pivot2 = pivot2[["SEVERE","ABNORMAL","MARGINAL","NORMAL"]]
                fig4 = go.Figure()
                for estado, color in [("SEVERE","#d32f2f"),("ABNORMAL","#ff9800"),("MARGINAL","#f44336"),("NORMAL","#4caf50")]:
                    fig4.add_trace(go.Bar(name=estado, y=pivot2.index, x=pivot2[estado],
                                          orientation="h", marker_color=color, marker_line_width=0))
                fig4.update_layout(barmode="stack", paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)", font_color="#b0bec5",
                                   showlegend=True, legend=dict(orientation="h", y=-0.25),
                                   margin=dict(t=10,b=10,l=10,r=10), height=300,
                                   xaxis=dict(gridcolor="#1a2d3d"))
                st.plotly_chart(fig4, use_container_width=True)

        with ch5:
            st.markdown("##### Edad promedio del fluido por estado")
            if "edad_fluido" in df_k.columns:
                edad_data = df_k.groupby("overall")["edad_fluido"].mean().reset_index()
                edad_data.columns = ["Estado","Edad promedio (hrs)"]
                COLOR_MAP = {"NORMAL":"#4caf50","MARGINAL":"#f44336","ABNORMAL":"#ff9800","SEVERE":"#d32f2f"}
                fig5 = px.bar(edad_data, x="Estado", y="Edad promedio (hrs)",
                              color="Estado", color_discrete_map=COLOR_MAP)
                fig5.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font_color="#b0bec5", showlegend=False,
                                   margin=dict(t=10,b=10,l=10,r=10), height=300,
                                   yaxis=dict(gridcolor="#1a2d3d"))
                fig5.update_traces(marker_line_width=0)
                st.plotly_chart(fig5, use_container_width=True)

        st.markdown("---")

        # Row 3 — tiempo entre análisis y distribución área
        ch6, ch7 = st.columns(2)

        with ch6:
            st.markdown("##### Distribución por área")
            if "area" in df_k.columns:
                area_data = df_k["area"].value_counts().reset_index()
                area_data.columns = ["Área","Cantidad"]
                fig6 = px.pie(area_data, names="Área", values="Cantidad",
                              color_discrete_sequence=["#1a6fa5","#2196f3"], hole=0.45)
                fig6.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font_color="#b0bec5", margin=dict(t=10,b=10,l=10,r=10), height=280)
                st.plotly_chart(fig6, use_container_width=True)

        with ch7:
            st.markdown("##### Análisis históricos en el tiempo")
            df_hist = df_global.copy()
            if "fecha_muestra" in df_hist.columns:
                df_hist = df_hist.dropna(subset=["fecha_muestra"])
                df_hist["mes"] = df_hist["fecha_muestra"].dt.to_period("M").astype(str)
                hist_data = df_hist.groupby(["mes","overall"]).size().unstack(fill_value=0).reset_index()
                fig7 = go.Figure()
                for estado, color in [("SEVERE","#d32f2f"),("ABNORMAL","#ff9800"),("MARGINAL","#f44336"),("NORMAL","#4caf50")]:
                    if estado in hist_data.columns:
                        fig7.add_trace(go.Bar(name=estado, x=hist_data["mes"], y=hist_data[estado],
                                              marker_color=color, marker_line_width=0))
                fig7.update_layout(barmode="stack", paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)", font_color="#b0bec5",
                                   legend=dict(orientation="h", y=-0.3),
                                   margin=dict(t=10,b=10,l=10,r=10), height=280,
                                   xaxis=dict(tickangle=-30), yaxis=dict(gridcolor="#1a2d3d"))
                st.plotly_chart(fig7, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════
# TAB D — ADMINISTRACIÓN
# ══════════════════════════════════════════════════════════════════════
with tab_admin:
    if not st.session_state.get("is_admin"):
        st.warning("⚠️ No tenés permisos para acceder a esta sección.")
        st.stop()
    else:
        st.markdown("### ⚙️ Panel de Administración")
        st.success("Sesión iniciada como **Admin**")

        st.markdown("---")
        st.markdown("#### 📤 Cargar nuevo Excel de resultados")
        st.markdown("Los nuevos análisis se agregarán a la base de datos existente. Los duplicados (mismo N° de muestra) serán ignorados.")

        uploaded = st.file_uploader("Seleccioná el archivo Excel (formato WebCheck)", type=["xlsx"])

        if uploaded is not None:
            try:
                new_data = process_excel(uploaded)
                current_db = st.session_state.get("df")
                merged = merge_dbs(current_db, new_data)

                n_nuevos = len(merged) - (len(current_db) if current_db is not None else 0)

                st.markdown(f"**Registros en archivo:** {len(new_data)}")
                st.markdown(f"**Nuevos registros a agregar:** {n_nuevos}")
                st.markdown(f"**Total en base de datos:** {len(merged)}")

                token = get_github_token()

                if st.button("✅ Confirmar y guardar en base de datos"):
                    if token:
                        with st.spinner("Guardando en GitHub..."):
                            ok = push_db_to_github(merged, token)
                        if ok:
                            st.session_state["df"] = merged
                            st.success(f"✅ Base de datos actualizada. {n_nuevos} nuevos registros agregados.")
                            st.rerun()
                        else:
                            st.error("Error al guardar en GitHub. Verificá el token.")
                    else:
                        # Save only to session without GitHub
                        st.session_state["df"] = merged
                        st.warning("⚠️ Token de GitHub no configurado. Los datos se cargaron en esta sesión pero NO se guardaron permanentemente. Configurá GITHUB_TOKEN en Streamlit Secrets para persistencia.")

            except Exception as e:
                st.error(f"Error procesando el archivo: {e}")

        st.markdown("---")
        st.markdown("#### 📊 Estado de la base de datos")
        if df_global is not None and not df_global.empty:
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total de análisis", len(df_global))
            col_b.metric("Equipos únicos", df_global["equipo"].nunique() if "equipo" in df_global.columns else "—")
            col_c.metric("Plantas", df_global["planta_cod"].nunique() if "planta_cod" in df_global.columns else "—")
            if "fecha_muestra" in df_global.columns:
                ultima = df_global["fecha_muestra"].max()
                st.markdown(f"**Análisis más reciente:** {ultima.strftime('%d/%m/%Y') if pd.notna(ultima) else '—'}")
        else:
            st.info("Base de datos vacía.")

        st.markdown("---")
        col_logout, _ = st.columns([1, 4])
        if col_logout.button("🚪 Cerrar sesión"):
            st.session_state.clear()
            st.rerun()

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;color:#37474f;font-size:0.75rem;margin-top:30px;padding-top:10px;border-top:1px solid #1a2d3d">
    TGN · Gerencia de Mantenimiento · División Análisis de Condición · Dashboard v2.0
</div>
""", unsafe_allow_html=True)
