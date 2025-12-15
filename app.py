# app.py - Doktor İmzalı Warfarin Asistanı (V2.5)

import streamlit as st
from collections import Counter
from fpdf import FPDF

# --- 1. Sabit Tanımlamalar ---
DOZ_SEVIYELERI_MG = {
    0: 0.00, 1: 1.25, 2: 2.50, 4: 5.00, 6: 7.50, 8: 10.00
}

HAFTANIN_GUNLERI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

PARCA_ADLARI = {
    0.00: "0 (Hic)", 
    1.25: "1/4 (Ceyrek)", 
    2.50: "1/2 (Yarim)", 
    5.00: "1 (Tam)", 
    7.50: "1+1/2 (Bir Bucuk)", 
    10.00: "2 (Iki Tam)"
}

POSSIBLE_DAILY_DOSES = sorted(list(set(DOZ_SEVIYELERI_MG.values())))


# --- 2. Algoritma ve Dağıtım Fonksiyonları ---

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
        if hedef_index < 7:
            yeni_sema[hedef_index] = azinlik_doz
    return yeni_sema

def optimal_tablet_dagilimi(hedef_haftalik_doz):
    hedef_haftalik_doz = round(hedef_haftalik_doz, 2)
    kullanilacak_dozlar = POSSIBLE_DAILY_DOSES
    best_combo = None
    min_hata = float('inf')
    TOLERANS = 0.15 
    
    for i in range(len(kullanilacak_dozlar)):
        d1 = kullanilacak_dozlar[i]
        combo_hata = abs((d1 * 7) - hedef_haftalik_doz)
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
                combo_hata = abs(simulasyon_toplam - hedef_haftalik_doz)
                if combo_hata < min_hata:
                    min_hata = combo_hata
                    best_combo = {d1: n1, d2: n2, "sapma": combo_hata}
                if combo_hata < TOLERANS: break 
    
    if best_combo:
        ham_liste = []
        for doz, adet in best_combo.items():
            if doz != "sapma" and adet > 0:
                ham_liste.extend([doz] * adet)
        return {
            "önerilen_toplam_mg": sum(ham_liste),
            "hata": min_hata,
            "doz_listesi": homojen_dagit(ham_liste)
        }
    return None

# --- 3. Gelişmiş PDF Oluşturma Fonksiyonu ---

def temizle(text):
    """Türkçe karakterleri İngilizce karşılıklarına çevirir (PDF hatası olmaması için)"""
    mapping = {'ı': 'i', 'ş': 's', 'ç': 'c', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 
               'İ': 'I', 'Ş': 'S', 'Ç': 'C', 'Ğ': 'G', 'Ü': 'U', 'Ö': 'O'}
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text

def create_pdf(doktor_adi, inr, hedef_alt, hedef_ust, doz_listesi):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Başlık
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Warfarin Doz Takip Cizelgesi", ln=True, align='C')
    pdf.ln(5)
    
    # Doktor ve Hasta Bilgisi
    pdf.set_font("Arial", size=10)
    # Doktor adını temizle
    dr_clean = temizle(doktor_adi)
    pdf.cell(0, 10, txt=f"Duzenleyen Hekim: {dr_clean}", ln=True, align='R')
    
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Guncel INR: {inr} (Hedef Aralik: {hedef_alt} - {hedef_ust})", ln=True, align='L')
    pdf.ln(5)
    
    # Tablo Başlıkları
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 8, "Gun", 1, 0, 'C', 1)
    pdf.cell(60, 8, "Tablet Parcasi", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Doz (mg)", 1, 1, 'C', 1)
    
    # Tablo İçeriği
    pdf.set_font("Arial", size=11)
    toplam = 0
    for i, gun in enumerate(HAFTANIN_GUNLERI):
        mg_val = doz_listesi[i] if i < len(doz_listesi) else 0.0
        gun_temiz = temizle(gun)
        parca_ad = PARCA_ADLARI.get(mg_val, f"{mg_val}")
        
        pdf.cell(40, 8, gun_temiz, 1, 0, 'C')
        pdf.cell(60, 8, parca_ad, 1, 0, 'C')
        pdf.cell(40, 8, f"{mg_val:.2f}", 1, 1, 'C')
        toplam += mg_val
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"Haftalik Toplam Doz: {toplam:.2f} mg", ln=True, align='L')
    
    # İmza Alanı
    pdf.ln(20)
    pdf.set_font("Arial", size=11)
    pdf.cell(120, 10, "", 0, 0) # Boşluk
    pdf.cell(70, 10, "Imza / Kase", "T", 1, 'C') # Üstü çizgili alan
    pdf.cell(120, 10, "", 0, 0)
    pdf.cell(70, 5, dr_clean, 0, 1, 'C')
    
    return pdf.output(dest='S').encode('latin-1')


# --- 4. Streamlit Arayüzü ---

def app_arayuzu():
    st.set_page_config(page_title="Warfarin Asistanı", layout="wide")
    st.title("🫀 Warfarin Klinik Asistanı")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Ayarlar")
        # --- YENİ EKLENEN DOKTOR ALANI ---
        doktor_adi = st.text_input("Doktor Adı Soyadı", "Dr. Isim Soyisim")
        st.markdown("---")
        
        st.header("1. Hasta Verileri")
        guncel_inr = st.number_input("Güncel INR", 0.5, 8.0, 2.5, 0.1)
        col1, col2 = st.columns(2)
        hedef_alt = col1.number_input("Min", 1.5, 3.5, 2.0, 0.1)
        hedef_ust = col2.number_input("Max", 2.5, 4.0, 3.0, 0.1)
        st.success("🛡️ **Stabilite Modu Aktif**")

    # Doz Girişi
    st.subheader("2. Mevcut Kullanım")
    doz_secenekleri = {k: PARCA_ADLARI.get(v, f"{v:.2f} mg") for k, v in DOZ_SEVIYELERI_MG.items()}
    gunluk_dozlar_mg = {}
    toplam_haftalik_doz = 0.0
    cols = st.columns(7)
    for i, gun in enumerate(HAFTANIN_GUNLERI):
        with cols[i]:
            st.markdown(f"**{gun}**")
            secim_key = st.selectbox("Doz", list(doz_secenekleri.keys()), format_func=lambda x: doz_secenekleri[x], key=f"doz_{gun}", label_visibility="collapsed")
            toplam_haftalik_doz += DOZ_SEVIYELERI_MG[secim_key]
    
    calculate_btn = st.button("Analiz Et ve Doz Öner", use_container_width=True, type="primary")

    if calculate_btn or 'hesaplandi' in st.session_state:
        st.session_state['hesaplandi'] = True
        
        # Basit Algoritma
        yuzde_degisim = 0.0
        if guncel_inr >= 4.5: yuzde_degisim = -0.20 
        elif guncel_inr > hedef_ust: yuzde_degisim = -0.125
        elif guncel_inr < (hedef_alt - 0.3): yuzde_degisim = 0.15
        elif guncel_inr < hedef_alt: yuzde_degisim = 0.075
        
        algoritma_onerisi = toplam_haftalik_doz * (1 + yuzde_degisim)

        col1, col2 = st.columns([1, 2])
        col1.metric("Önerilen Değişim", f"%{yuzde_degisim*100:.1f}")
        final_hedef = col2.slider("Haftalık Hedef (mg)", 0.0, algoritma_onerisi + 20, algoritma_onerisi, 1.25)
        
        dagilim = optimal_tablet_dagilimi(final_hedef)
        
        if dagilim:
            st.markdown("---")
            doz_listesi = dagilim['doz_listesi']
            
            # Kart Görünümü
            st.subheader("3. Yeni Reçete Planı")
            cols_cal = st.columns(7)
            for i, gun in enumerate(HAFTANIN_GUNLERI):
                with cols_cal[i]:
                    mg = doz_listesi[i]
                    parca = PARCA_ADLARI.get(mg, f"{mg}")
                    color = "#0068c9" if mg > 0 else "#cccccc"
                    st.markdown(f"<div style='background:#f0f2f6;border-radius:10px;padding:10px;text-align:center;'><b>{gun[:3]}</b><br><span style='color:{color};font-size:20px;font-weight:bold;'>{parca}</span><br><small>{mg} mg</small></div>", unsafe_allow_html=True)
            
            st.caption(f"Toplam: {dagilim['önerilen_toplam_mg']:.2f} mg")
            
            # --- PDF İNDİRME ---
            st.markdown("---")
            # Doktor adını da fonksiyona gönderiyoruz
            pdf_bytes = create_pdf(doktor_adi, guncel_inr, hedef_alt, hedef_ust, doz_listesi)
            
            st.download_button(
                label="📄 İmzalı PDF Reçete İndir",
                data=pdf_bytes,
                file_name=f"warfarin_takvimi_{doktor_adi.replace(' ', '_')}.pdf",
                mime="application/pdf",
                type="secondary"
            )

if __name__ == "__main__":
    app_arayuzu()