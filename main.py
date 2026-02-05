import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import json
import os
import io
from gemini_service import transcribir_audio_fluido, procesar_pedido_con_ia
from streamlit_mic_recorder import mic_recorder

# --- PERSISTENCIA ---
ARCHIVO_DB = "inventario_repuestos.json"

def guardar_datos(datos):
    with open(ARCHIVO_DB, "w", encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def cargar_datos():
    if os.path.exists(ARCHIVO_DB):
        try:
            with open(ARCHIVO_DB, "r", encoding='utf-8') as f:
                return json.load(f)
        except: return {"Sucursal Centro": [], "Sucursal Norte": [], "Sucursal Sur": []}
    return {"Sucursal Centro": [], "Sucursal Norte": [], "Sucursal Sur": []}

def generar_ticket_pdf(items, total, paga, vuelto, sucursal):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 22)
    pdf.cell(190, 15, "MOTO-REPUESTOS PRO", ln=True, align='C')
    pdf.set_font("helvetica", '', 14)
    pdf.cell(190, 10, f"SUCURSAL: {sucursal.upper()}", ln=True, align='C')
    pdf.cell(190, 10, f"FECHA: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(5); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)
    pdf.set_font("helvetica", 'B', 14)
    for i in items:
        pdf.cell(90, 10, f"{i['Producto'].upper()[:25]}")
        pdf.cell(40, 10, f"x{round(i['Cant'], 2)}")
        pdf.cell(60, 10, f"${round(i['Subtotal'], 2):,.2f}", ln=True, align='R')
    pdf.ln(5); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)
    pdf.set_font("helvetica", 'B', 18)
    pdf.cell(130, 12, "TOTAL:", align='R'); pdf.cell(60, 12, f"${total:,.2f}", ln=True, align='R')
    # Corregido: eliminamos 'font_size' que causaba el crash
    pdf.set_font("helvetica", '', 14) 
    pdf.cell(130, 10, "PAGA CON:", align='R'); pdf.cell(60, 10, f"${paga:,.2f}", ln=True, align='R')
    pdf.cell(130, 12, "VUELTO:", align='R'); pdf.cell(60, 12, f"${vuelto:,.2f}", ln=True, align='R')
    return bytes(pdf.output())

# --- INICIALIZACIÓN ---
if 'db_total' not in st.session_state:
    st.session_state.db_total = cargar_datos()
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'texto_ia' not in st.session_state:
    st.session_state.texto_ia = ""
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

st.set_page_config(layout="wide", page_title="SISTEMA MOTO-REPUESTOS", page_icon="🏍️")

# --- LOGIN ---
if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align:center; color: #FF4B4B;'>🏍️ ACCESO MOTO-REPUESTOS</h1>", unsafe_allow_html=True)
    sucursal_sel = st.selectbox("Seleccione sucursal / Rol:", ["Admin Global"] + list(st.session_state.db_total.keys()))
    password = st.text_input("Contraseña:", type="password")
    if st.button("INGRESAR", use_container_width=True):
        if (sucursal_sel == "Admin Global" and password == "admin123") or (password == "1234"):
            st.session_state.autenticado = True
            st.session_state.sucursal_activa = sucursal_sel
            st.session_state.rol = "admin" if sucursal_sel == "Admin Global" else "sucursal"
            st.rerun()
    st.stop()

# --- SIDEBAR (CIERRE DE SESIÓN) ---
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.sucursal_activa}")
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True):
        st.session_state.autenticado = False; st.session_state.carrito = []; st.session_state.texto_ia = ""; st.rerun()

# --- CSS ESTILO MORITA ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@700&display=swap');
        .titulo-contenedor { background-color: #1E1E1E; padding: 20px; border-radius: 15px; border-bottom: 8px solid #FF4B4B; margin-bottom: 25px; }
        .titulo-texto { font-family: 'Oswald', sans-serif !important; font-size: 50px !important; color: #FFFFFF !important; text-align: center; text-transform: uppercase; margin: 0; }
        div.stButton > button { background-color: #FF4B4B !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; }
        .box-entendi { background-color: #E8F5E9; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50; font-weight: bold; margin: 10px 0; font-size: 1.2rem; color: #1B5E20; }
    </style>
""", unsafe_allow_html=True)

st.markdown(f'<div class="titulo-contenedor"><h1 class="titulo-texto">{st.session_state.sucursal_activa}</h1></div>', unsafe_allow_html=True)

# --- VISTA ADMIN GLOBAL ---
if st.session_state.rol == "admin":
    tab_admin1, tab_admin2 = st.tabs(["📈 VISTA GENERAL", "⚙️ GESTIÓN DE PRODUCTOS"])
    
    with tab_admin1:
        st.subheader("📊 DASHBOARD DE STOCK")
        lista_global = []
        for suc, items in st.session_state.db_total.items():
            for i in items:
                item_copy = i.copy(); item_copy['Sucursal'] = suc; lista_global.append(item_copy)
        st.dataframe(pd.DataFrame(lista_global), use_container_width=True)

    with tab_admin2:
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            st.write("### ➕ Enviar Nuevo Repuesto")
            with st.form("admin_add", clear_on_submit=True):
                dest = st.selectbox("Destino:", list(st.session_state.db_total.keys()))
                n_nom = st.text_input("Nombre")
                n_pre = st.number_input("Precio", min_value=0.0)
                n_sto = st.number_input("Stock Inicial", min_value=0.0)
                if st.form_submit_button("REGISTRAR"):
                    st.session_state.db_total[dest].append({"Producto": n_nom, "Precio": n_pre, "Stock": n_sto, "Rubro": "Gral"})
                    guardar_datos(st.session_state.db_total); st.rerun()
        
        with col_adm2:
            st.write("### 🗑️ Editar / Borrar")
            suc_edit = st.selectbox("Sucursal:", list(st.session_state.db_total.keys()))
            items_suc = st.session_state.db_total[suc_edit]
            prod_edit = st.selectbox("Producto:", [""] + [p['Producto'] for p in items_suc])
            if prod_edit:
                p_idx = next(i for i, p in enumerate(items_suc) if p['Producto'] == prod_edit)
                new_p = st.number_input("Precio:", value=float(items_suc[p_idx]['Precio']))
                new_s = st.number_input("Stock:", value=float(items_suc[p_idx]['Stock']))
                if st.button("💾 ACTUALIZAR"):
                    st.session_state.db_total[suc_edit][p_idx]['Precio'] = new_p
                    st.session_state.db_total[suc_edit][p_idx]['Stock'] = new_s
                    guardar_datos(st.session_state.db_total); st.rerun()
                if st.button("🗑️ ELIMINAR"):
                    st.session_state.db_total[suc_edit].pop(p_idx)
                    guardar_datos(st.session_state.db_total); st.rerun()

# --- VISTA SUCURSAL ---
else:
    tabs = st.tabs(["🛒 CAJA DE VENTAS", "📦 INVENTARIO LOCAL"])
    inv_local = st.session_state.db_total[st.session_state.sucursal_activa]

    with tabs[0]: 
        col1, col2 = st.columns([1, 1.4])
        with col1:
            st.subheader("🎙️ VOZ")
            audio = mic_recorder(start_prompt="🎤 HABLAR", stop_prompt="🛑 DETENER", key='rec')
            if audio:
                with open("temp.wav", "wb") as f: f.write(audio['bytes'])
                st.session_state.texto_ia = procesar_pedido_con_ia(transcribir_audio_fluido("temp.wav"), str(inv_local))
            
            if st.session_state.texto_ia:
                st.markdown(f'<div class="box-entendi">ENTENDÍ:<br>{st.session_state.texto_ia}</div>', unsafe_allow_html=True)
                if st.button("✅ CARGAR A DETALLE", use_container_width=True):
                    for l in st.session_state.texto_ia.split('\n'):
                        if '|' in l:
                            p, c, s = l.split('|')
                            st.session_state.carrito.append({"Producto": p.strip(), "Cant": float(c), "Subtotal": float(s)})
                    st.session_state.texto_ia = ""; st.rerun()
            
            st.divider()
            st.subheader("⌨️ MANUAL")
            s_p = st.selectbox("BUSCAR:", [""] + sorted([p['Producto'] for p in inv_local]))
            if s_p:
                p_data = next(i for i in inv_local if i["Producto"] == s_p)
                st.info(f"STOCK: {p_data['Stock']} | ${p_data['Precio']}")
                c_v = st.number_input("CANTIDAD:", min_value=0.01, value=1.0)
                if st.button("➕ AÑADIR"):
                    st.session_state.carrito.append({"Producto": s_p, "Cant": c_v, "Subtotal": round(p_data['Precio'] * c_v, 2)})
                    st.rerun()

        with col2:
            st.subheader("🧾 DETALLE")
            if st.session_state.carrito:
                total_f = round(sum(i['Subtotal'] for i in st.session_state.carrito), 2)
                for idx, item in enumerate(st.session_state.carrito):
                    c_f1, c_f2, c_f3, c_f4 = st.columns([3, 1, 1, 0.5])
                    c_f1.write(f"**{item['Producto'].upper()}**")
                    c_f2.write(f"x{round(item['Cant'], 2)}")
                    c_f3.write(f"${item['Subtotal']:,.2f}")
                    if c_f4.button("❌", key=f"del_{idx}"): st.session_state.carrito.pop(idx); st.rerun()
                
                st.markdown(f"## TOTAL: ${total_f:,.2f}")
                paga = st.number_input("PAGA CON ($):", min_value=0.0, value=float(total_f))
                vuelto = round(max(0.0, paga - total_f), 2)
                st.success(f"VUELTO: ${vuelto:,.2f}")
                
                # --- BOTONES DE ACCIÓN (Corregida la alineación) ---
                b1, b2, b3 = st.columns(3)
                if b1.button("⚡ VENTA", use_container_width=True):
                    for it in st.session_state.carrito:
                        for p in inv_local:
                            if p['Producto'].lower() == it['Producto'].lower(): p['Stock'] -= it['Cant']
                    guardar_datos(st.session_state.db_total); st.session_state.carrito = []; st.rerun()
                
                pdf_t = generar_ticket_pdf(st.session_state.carrito, total_f, paga, vuelto, st.session_state.sucursal_activa)
                b2.download_button("🖨️ TICKET", data=pdf_t, file_name="ticket.pdf", mime="application/pdf", use_container_width=True)
                
                if b3.button("🔄 RESET", use_container_width=True):
                    st.session_state.carrito = []; st.session_state.texto_ia = ""; st.rerun()
            else: st.info("Caja vacía.")

    with tabs[1]:
        st.subheader("📦 STOCK LOCAL")
        edited_df = st.data_editor(pd.DataFrame(inv_local), use_container_width=True)
        if st.button("💾 GUARDAR TABLA"):
            st.session_state.db_total[st.session_state.sucursal_activa] = edited_df.to_dict(orient='records')
            guardar_datos(st.session_state.db_total); st.success("Guardado"); st.rerun()
