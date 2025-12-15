# app.py - Sidebar Düzeltilmiş Sürüm (V4.1)

import streamlit as st
from collections import Counter
from fpdf import FPDF

# --- 1. SAYFA AYARLARI VE CSS STİLİ ---
st.set_page_config(
    page_title="Warfarin Asistanı",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded" # Uygulama açılınca sidebar açık gelsin
)

# Özel CSS
st.markdown("""
    <style>
    /* Genel Arka Plan */
    .stApp {
        background-color: #f4f6f9;
    }
    
    /* Sidebar (Yan Menü) Stili */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    
    /* Sidebar Açma/Kapama Butonunun Olduğu Üst Barı GİZLEME (DÜZELTME) */
    /* header {visibility: hidden;}  <-- BU SATIR SİLİNDİ */
    
    /* Sadece sağ üstteki 3 nokta ve 'Deploy' yazısını gizle */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    
    /* Başlıklar */
    h1, h2, h3 {
        color: #0d47a1; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Ana Buton */
    div.stButton > button {
        background-color: #1976d2;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 15px 32px;
        font-size: 18px;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #1565c0;
        transform: translateY(-2px);
    }
    
    /* İkincil Buton */
    div[data-testid="stDownloadButton"] > button {
        background-color: #ffffff;
        color: #1976d2;
        border: 2px solid #1976d2;
        border-radius: 12px;
        font-weight: bold;
    }
    
    /* Kartların Stili */
    .dose-card {
        background-color: white;
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #eee;
        height: 100%;
    }
    </style>
""", unsafe_allow_html=True)


# --- 2. SABİT TANIMLAMALAR ---
DOZ_SEVIYELERI_MG = {
    0: 0.00, 1: 1.25, 2: 2.50, 4: 5.00, 6: 7.50, 8: 10.00
}
HAFTANIN_GUNLERI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
PARCA_ADLARI = {
    0.00: "0 (Hic)", 1.25: "1/4 (Ceyrek)", 2.50: "1/2 (Yarim)", 
    5.00: "1 (Tam)", 7.50: "1+1/2 (Bir Bucuk)", 10.00: "2 (Iki Tam)"
}
POSSIBLE_DAILY_DOSES = sorted(list(set(DOZ_SEVIYELERI_MG.values())))
RUTIN_ADAYLAR = [d for d in POSSIBLE_DAILY_DOSES if d > 0.0]

# --- 3. ALGORİTMA FONKSİYONLARI ---

def homojen_dagit(doz_listesi):
    if not doz_listesi: return []
    sayim = Counter(doz_listesi)
    if len(sayim) != 2: return sorted(doz_listesi, reverse=True)
    sirali = sayim.most_common()
    cogunluk_doz, cogunluk_adet = sirali[0]
    azinlik_doz, azinlik_adet = sirali[1]
    yeni_sema = [cogunluk_doz] * 7
    adim = 7.0 / azinlik_adet
    for i in range(azinlik_adet):
        hedef_index = int((adim / 2) + (i * adim))
        if hedef_index < 7: yeni_sema[hedef_index] = azinlik_doz
    return yeni_sema

def optimal_tablet_dagilimi(hedef_bakim_dozu):
    hedef_bakim_dozu = round(hedef_bakim_dozu, 2)
    best_combo = None
    min_hata = float('inf')
    TOLERANS = 0.15 
    kullanilacak_dozlar = RUTIN_ADAYLAR
    
    for i in range(len(kullanilacak_dozlar)):
        d1 = kullanilacak_dozlar[i]
        combo_hata = abs((d1 * 7) - hedef_bakim_dozu)
        if combo_hata < min_hata:
            min_hata = combo_hata
            best_combo = {d1: 7, "sapma": combo_hata}

        for j in range(i + 1, len(kullanilacak_dozlar)):
            d2 = kullanilacak_dozlar[j]
            if abs(d1 - d2) > 2.51: continue 
            for n1 in range(8): 
                n2 = 7 - n1
                if n2 < 0: continue
                simulasyon_toplam = (n1 * d1) + (n2 * d2)
                combo_hata = abs(simulasyon_toplam - hedef_bakim_dozu)
                if combo_hata < min_hata:
                    min_hata = combo_hata
                    best_combo = {d1: n1, d2: n2, "sapma": combo_hata}
                if combo_hata < TOLERANS: break 
    
    if best_combo:
        ham_liste = []
        for doz, adet in best_combo.items():
            if doz != "sapma" and adet > 0: ham_liste.extend([doz] * adet)
        return {"önerilen_toplam_mg": sum(ham_liste), "hata": min_hata, "doz_listesi": homojen_dagit(ham_liste)}
    return None

# --- PDF Fonksiyonu ---
def temizle(text):
    mapping = {'ı': 'i', 'ş': 's', 'ç': 'c', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'İ': 'I', 'Ş': 'S', 'Ç': 'C', 'Ğ': 'G', 'Ü': 'U', 'Ö': 'O'}
    for k, v in mapping.items(): text = text.replace(k, v)
    return text

def create_pdf(doktor_adi, inr, hedef_alt, hedef_ust, doz_listesi, standart_liste, klinik_notlar, gun_atla_sayisi):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Warfarin Doz Takip Cizelgesi", ln=True, align='C')
    pdf.ln(5)
    dr_clean = temizle(doktor_adi)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, txt=f"Duzenleyen Hekim: {dr_clean}", ln=True, align='R')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Guncel INR: {inr} (Hedef: {hedef_alt} - {hedef_ust})", ln=True, align='L')
    
    if gun_atla_sayisi > 0:
        pdf.set_text_color(255, 0, 0)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt=f"DIKKAT: Ilk {gun_atla_sayisi} gun ilac ALINMAYACAKTIR.", ln=True, align='L')
        pdf.set_text_color(0, 0, 0)
    if klinik_notlar:
        pdf.set_font("Arial", 'I', 10)
        pdf.multi_cell(0, 6, txt=f"Not: {temizle(klinik_notlar)}")
    
    pdf.ln(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(35, 8, "Gun", 1, 0, 'C', 1)
    pdf.cell(85, 8, "Uygulanacak Doz", 1, 0, 'C', 1)
    pdf.cell(30, 8, "mg", 1, 1, 'C', 1)
    pdf.set_font("Arial", size=10)
    toplam = 0
    for i, gun in enumerate(HAFTANIN_GUNLERI):
        mg_val = doz_listesi[i]; rutin_mg = standart_liste[i]
        rutin_parca = PARCA_ADLARI.get(rutin_mg, f"{rutin_mg}")
        if mg_val == 0.0 and i < gun_atla_sayisi:
            parca_ad = f"ATLA (Rutin: {rutin_parca})"
            pdf.set_text_color(255, 0, 0) 
        else:
            parca_ad = PARCA_ADLARI.get(mg_val, f"{mg_val}")
            pdf.set_text_color(0, 0, 0)
        gun_temiz = temizle(gun)
        pdf.cell(35, 8, gun_temiz, 1, 0, 'C')
        pdf.cell(85, 8, parca_ad, 1, 0, 'C')
        pdf.cell(30, 8, f"{mg_val:.2f}", 1, 1, 'C')
        toplam += mg_val
        pdf.set_text_color(0, 0, 0)
        
    pdf.ln(5); pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"Bu Hafta Alinacak Toplam Doz: {toplam:.2f} mg", ln=True, align='L')
    pdf.ln(20); pdf.set_font("Arial", size=11)
    pdf.cell(120, 10, "", 0, 0); pdf.cell(70, 10, "Imza / Kase", "T", 1, 'C') 
    pdf.cell(120, 10, "", 0, 0); pdf.cell(70, 5, dr_clean, 0, 1, 'C')
    return pdf.output(dest='S').encode('latin-1')

# --- 4. STREAMLIT ARAYÜZÜ ---

def app_arayuzu():
    # Logo ve Başlık
    col1, col2 = st.columns([1, 6])
    with col1:
        st.markdown("<div style='font-size: 40px; text-align: center;'>❤️</div>", unsafe_allow_html=True)
    with col2:
        st.title("Warfarin Klinik Asistanı")
        st.caption("Profesyonel Doz Hesaplama ve Takip Sistemi")
    
    st.markdown("---")

    # --- YAN MENÜ (SIDEBAR) ---
    with st.sidebar:
        st.markdown("### 👨‍⚕️ Hekim Ayarları")
        doktor_adi = st.text_input("Doktor Adı Soyadı", "Dr. Isim Soyisim")
        
        st.markdown("---")
        st.markdown("### 📊 Hasta Verileri")
        guncel_inr = st.number_input("Güncel INR Değeri", 0.5, 10.0, 2.5, 0.1)
        
        st.markdown("### 🎯 Hedef Aralık")
        c1, c2 = st.columns(2)
        hedef_alt = c1.number_input("Min", 1.5, 3.5, 2.0, 0.1)
        hedef_ust = c2.number_input("Max", 2.5, 4.0, 3.0, 0.1)
        
        st.info(f"Hedef: **{hedef_alt} - {hedef_ust}**")
        
        st.markdown("---")
        st.markdown("### ⚠️ Risk Faktörleri")
        doz_atlama = st.checkbox("Son 3 günde ilaç atlandı")
        kanama_var = st.checkbox("Aktif kanama / morarma")
        yeni_ilac = st.checkbox("Yeni ilaç / etkileşim")

    # --- ANA EKRAN ---
    st.subheader("💊 Mevcut Haftalık Doz")
    
    with st.container():
        st.markdown('<div style="background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">', unsafe_allow_html=True)
        
        doz_secenekleri = {k: PARCA_ADLARI.get(v, f"{v:.2f} mg") for k, v in DOZ_SEVIYELERI_MG.items()}
        gunluk_dozlar_mg = {}
        toplam_haftalik_doz = 0.0
        
        cols = st.columns(7)
        for i, gun in enumerate(HAFTANIN_GUNLERI):
            with cols[i]:
                st.markdown(f"<div style='text-align:center; font-weight:bold; color:#555;'>{gun[:3]}</div>", unsafe_allow_html=True)
                secim_key = st.selectbox("Doz", list(doz_secenekleri.keys()), format_func=lambda x: doz_secenekleri[x], key=f"doz_{gun}", label_visibility="collapsed")
                toplam_haftalik_doz += DOZ_SEVIYELERI_MG[secim_key]
        
        st.markdown(f"<div style='text-align:right; color:#1976d2; margin-top:15px; font-size:18px;'><b>Mevcut Toplam: {toplam_haftalik_doz:.2f} mg</b></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("") 
    calculate_btn = st.button("ANALİZ ET VE REÇETE OLUŞTUR")

    if calculate_btn or 'hesaplandi' in st.session_state:
        st.session_state['hesaplandi'] = True
        
        # MANTIK
        yuzde_degisim = 0.0; durum_mesaji = ""; renk = "green"; klinik_uyari = ""; gun_atla_sayisi = 0
        if kanama_var:
            durum_mesaji = "ACİL: KANAMA RİSKİ"; klinik_uyari = "Hasta aktif kanama belirtiyor. Warfarin kesilmeli."; yuzde_degisim = -1.0; gun_atla_sayisi = 7; renk = "red"
        elif doz_atlama and guncel_inr < hedef_alt:
            durum_mesaji = "Düşük INR (Eksik Doz)"; klinik_uyari = "Düşüklük eksik doza bağlı. Artış yapma, eksik dozu tamamla."; yuzde_degisim = 0.0; renk = "orange"
        elif yeni_ilac:
            durum_mesaji = "İlaç Etkileşimi Riski"; klinik_uyari = "Yeni ilaç INR'yi etkileyebilir. Yakın takip."; renk = "orange"
            if guncel_inr >= 4.5: yuzde_degisim = -0.20; gun_atla_sayisi = 2
            elif guncel_inr > hedef_ust: yuzde_degisim = -0.125; gun_atla_sayisi = 1
            elif guncel_inr < (hedef_alt - 0.3): yuzde_degisim = 0.15
            elif guncel_inr < hedef_alt: yuzde_degisim = 0.075
        else:
            if guncel_inr >= 4.5: yuzde_degisim = -0.20; gun_atla_sayisi = 2; renk = "red"; durum_mesaji = "Yüksek INR: 2 GÜN ATLA"
            elif guncel_inr > hedef_ust: yuzde_degisim = -0.125; gun_atla_sayisi = 1; renk = "orange"; durum_mesaji = "Hafif Yüksek: 1 GÜN ATLA"
            elif guncel_inr < (hedef_alt - 0.3): yuzde_degisim = 0.15; renk = "red"; durum_mesaji = "Düşük INR: Artır"
            elif guncel_inr < hedef_alt: yuzde_degisim = 0.075; renk = "orange"; durum_mesaji = "Hafif Düşük: Artır"
            else: durum_mesaji = "Hedef Aralıkta"; renk = "green"

        hedef_bakim_dozu = toplam_haftalik_doz * (1 + yuzde_degisim)
        if kanama_var: hedef_bakim_dozu = 0

        st.markdown("---")
        
        # Sonuç Kartı
        renk_kodu = "#d32f2f" if renk == "red" else "#f57c00" if renk == "orange" else "#2e7d32"
        st.markdown(f"""
            <div style="background-color: {renk_kodu}; color: white; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h3 style="color: white; margin:0; font-size: 24px;">{durum_mesaji}</h3>
                <p style="margin:5px 0 0 0; opacity: 0.9;">Önerilen Değişim: %{yuzde_degisim*100:.1f}</p>
            </div>
        """, unsafe_allow_html=True)
        
        if klinik_uyari: st.error(f"**Klinik Not:** {klinik_uyari}")

        col_slider, _ = st.columns([2, 1])
        with col_slider:
            final_bakim_hedef = st.slider("Haftalık Rutin Bakım Dozu (mg)", 0.0, hedef_bakim_dozu + 20, hedef_bakim_dozu, 1.25)
        
        dagilim_standart = optimal_tablet_dagilimi(final_bakim_hedef)
        
        if dagilim_standart:
            standart_liste = dagilim_standart['doz_listesi']
            doz_listesi = list(standart_liste)
            for i in range(gun_atla_sayisi):
                if i < 7: doz_listesi[i] = 0.0
            
            gercek_toplam = sum(doz_listesi)
            
            st.markdown(f"### 🗓️ Reçete Planı (Bu Hafta: {gercek_toplam:.2f} mg)")
            
            cols_cal = st.columns(7)
            for i, gun in enumerate(HAFTANIN_GUNLERI):
                with cols_cal[i]:
                    mg = doz_listesi[i]; rutin_mg = standart_liste[i]
                    rutin_parca = PARCA_ADLARI.get(rutin_mg, f"{rutin_mg}")
                    
                    if mg == 0.0 and i < gun_atla_sayisi:
                        st.markdown(f"""
                            <div class="dose-card" style="border: 2px solid #ef5350; background-color: #ffebee;">
                                <div style="font-weight:bold; color:#c62828; margin-bottom:5px;">{gun[:3]}</div>
                                <div style="color:#d32f2f; font-size:20px; font-weight:bold;">⛔ ATLA</div>
                                <div style="font-size:11px; color:#b71c1c; margin-top:5px;">Rutin: {rutin_parca}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        parca = PARCA_ADLARI.get(mg, f"{mg}")
                        bg_color = "#e3f2fd" if mg > 0 else "#f5f5f5"
                        text_color = "#1565c0" if mg > 0 else "#bdbdbd"
                        border_color = "#bbdefb" if mg > 0 else "#eeeeee"
                        
                        st.markdown(f"""
                            <div class="dose-card" style="background-color: {bg_color}; border: 1px solid {border_color};">
                                <div style="font-weight:bold; color:#455a64; margin-bottom:5px;">{gun[:3]}</div>
                                <div style="color:{text_color}; font-size:22px; font-weight:bold;">{parca}</div>
                                <div style="font-size:12px; color:#546e7a; margin-top:5px;">{mg} mg</div>
                            </div>
                        """, unsafe_allow_html=True)
            
            st.write("")
            st.write("")
            
            pdf_bytes = create_pdf(doktor_adi, guncel_inr, hedef_alt, hedef_ust, doz_listesi, standart_liste, klinik_uyari, gun_atla_sayisi)
            
            st.download_button(
                label="📄 PDF Reçete İndir",
                data=pdf_bytes,
                file_name=f"warfarin_{doktor_adi.replace(' ', '_')}.pdf",
                mime="application/pdf",
                type="secondary",
                use_container_width=True
            )

if __name__ == "__main__":
    app_arayuzu()