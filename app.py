# app.py - Senkronize Dağıtımlı Warfarin Asistanı (V3.3)

import streamlit as st
from collections import Counter
from fpdf import FPDF

# --- 1. Sabit Tanımlamalar ---
DOZ_SEVIYELERI_MG = {
    0: 0.00, 1: 1.25, 2: 2.50, 4: 5.00, 6: 7.50, 8: 10.00
}

HAFTANIN_GUNLERI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

PARCA_ADLARI = {
    0.00: "0 (Hic)", 1.25: "1/4 (Ceyrek)", 2.50: "1/2 (Yarim)", 
    5.00: "1 (Tam)", 7.50: "1+1/2 (Bir Bucuk)", 10.00: "2 (Iki Tam)"
}

POSSIBLE_DAILY_DOSES = sorted(list(set(DOZ_SEVIYELERI_MG.values())))
# 0.0'ı (Hic) rutin hesaplamadan çıkarıyoruz ki rutin planda boş gün olmasın
RUTIN_ADAYLAR = [d for d in POSSIBLE_DAILY_DOSES if d > 0.0]

# --- 2. Algoritma Fonksiyonları ---

def homojen_dagit(doz_listesi):
    """
    Listeyi haftaya en dengeli şekilde yayar.
    Örn: [Tam, Tam, Yarım, Tam, Yarım, Tam, Tam] -> [Tam, Yarım, Tam, Tam, Yarım, Tam, Tam]
    """
    if not doz_listesi: return []
    
    sayim = Counter(doz_listesi)
    # Eğer tek tip doz varsa veya çok karmaşıksa sıralı döndür
    if len(sayim) != 2: 
        return sorted(doz_listesi, reverse=True)
    
    sirali = sayim.most_common()
    cogunluk_doz, cogunluk_adet = sirali[0]
    azinlik_doz, azinlik_adet = sirali[1]
    
    # Önce haftayı çoğunluk dozuyla doldur
    yeni_sema = [cogunluk_doz] * 7
    
    # Azınlık dozlarını aralara serpiştir (Merkezi Dağılım)
    adim = 7.0 / azinlik_adet
    for i in range(azinlik_adet):
        # (adim / 2) ofseti ile başla ki uçlara yığılmasın
        hedef_index = int((adim / 2) + (i * adim))
        if hedef_index < 7:
            yeni_sema[hedef_index] = azinlik_doz
            
    return yeni_sema

def optimal_tablet_dagilimi(hedef_bakim_dozu):
    """
    Sadece İDEAL RUTİN haftayı hesaplar. Atlamalar sonradan uygulanır.
    """
    hedef_bakim_dozu = round(hedef_bakim_dozu, 2)
    
    best_combo = None
    min_hata = float('inf')
    TOLERANS = 0.15 
    
    # Sadece 0 olmayan dozları kullanıyoruz (Rutin bakımda boş gün olmaz varsayımı)
    # Eğer hastanın rutini "bir gün boş" ise o ayrı bir klinik karardır, 
    # burada doz ayarlaması yaptığımız için ilaçlı günlere odaklanıyoruz.
    kullanilacak_dozlar = RUTIN_ADAYLAR
    
    for i in range(len(kullanilacak_dozlar)):
        d1 = kullanilacak_dozlar[i]
        
        # Tek Tip Doz
        combo_hata = abs((d1 * 7) - hedef_bakim_dozu)
        if combo_hata < min_hata:
            min_hata = combo_hata
            best_combo = {d1: 7, "sapma": combo_hata}

        # İki Tip Doz
        for j in range(i + 1, len(kullanilacak_dozlar)):
            d2 = kullanilacak_dozlar[j]
            # Stabilite filtresi: Fark 2.5'ten büyükse atla
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
            if doz != "sapma" and adet > 0:
                ham_liste.extend([doz] * adet)
        
        # Listeyi homojen dağıt
        dagitilmis_liste = homojen_dagit(ham_liste)
        
        return {
            "önerilen_toplam_mg": sum(dagitilmis_liste),
            "hata": min_hata,
            "doz_listesi": dagitilmis_liste
        }
    return None

# --- 3. PDF Fonksiyonu ---
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
        mg_val = doz_listesi[i]
        rutin_mg = standart_liste[i]
        rutin_parca = PARCA_ADLARI.get(rutin_mg, f"{rutin_mg}")
        
        # Tablo Görünümü
        if i < gun_atla_sayisi:
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
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"Bu Hafta Alinacak Toplam Doz: {toplam:.2f} mg", ln=True, align='L')
    
    pdf.ln(20)
    pdf.set_font("Arial", size=11)
    pdf.cell(120, 10, "", 0, 0) 
    pdf.cell(70, 10, "Imza / Kase", "T", 1, 'C') 
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
        doktor_adi = st.text_input("Doktor Adı Soyadı", "Dr. Isim Soyisim")
        st.markdown("---")
        
        st.header("1. Hasta Verileri")
        guncel_inr = st.number_input("Güncel INR", 0.5, 10.0, 2.5, 0.1)
        col1, col2 = st.columns(2)
        hedef_alt = col1.number_input("Min", 1.5, 3.5, 2.0, 0.1)
        hedef_ust = col2.number_input("Max", 2.5, 4.0, 3.0, 0.1)
        
        st.markdown("---")
        st.subheader("⚠️ Risk Kontrolü")
        doz_atlama = st.checkbox("Son 3 günde ilaç atlandı mı?")
        kanama_var = st.checkbox("Aktif kanama / morarma var mı?")
        yeni_ilac = st.checkbox("Yeni ilaç başlandı mı?")

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
    
    st.markdown(f"<p style='text-align:center; color:gray'>Mevcut Haftalık Toplam: {toplam_haftalik_doz:.2f} mg</p>", unsafe_allow_html=True)

    calculate_btn = st.button("Analiz Et ve Doz Öner", use_container_width=True, type="primary")

    if calculate_btn or 'hesaplandi' in st.session_state:
        st.session_state['hesaplandi'] = True
        
        yuzde_degisim = 0.0
        durum_mesaji = ""
        renk = "green"
        klinik_uyari = ""
        gun_atla_sayisi = 0
        
        if kanama_var:
            durum_mesaji = "🚨 ACİL: Kanama Riski"
            klinik_uyari = "Hasta aktif kanama belirtiyor. Warfarin kesilmeli."
            yuzde_degisim = -1.0 
            gun_atla_sayisi = 7 
            renk = "red"
        elif doz_atlama and guncel_inr < hedef_alt:
            durum_mesaji = "⚠️ Düşük INR (Eksik Doz)"
            klinik_uyari = "Düşüklük eksik doza bağlı, artış yapma, eksik dozu tamamla."
            yuzde_degisim = 0.0
            renk = "orange"
        elif yeni_ilac:
            durum_mesaji = "💊 İlaç Etkileşimi"
            klinik_uyari = "Yeni ilaç INR'yi etkileyebilir. Yakın takip."
            renk = "orange"
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
        st.subheader("3. Klinik Analiz")
        st.markdown(f":{renk}[**Durum: {durum_mesaji}**]")
        if klinik_uyari: st.error(f"{klinik_uyari}")

        col1, col2 = st.columns([1, 2])
        col1.metric("Önerilen Bakım Değişimi", f"%{yuzde_degisim*100:.1f}")
        final_bakim_hedef = col2.slider("Haftalık Rutin Bakım Dozu (mg)", 0.0, hedef_bakim_dozu + 20, hedef_bakim_dozu, 1.25)
        
        # --- DÜZELTİLMİŞ MANTIK ---
        # 1. ÖNCE RUTİNİ HESAPLA (Tam 7 gün)
        dagilim_standart = optimal_tablet_dagilimi(final_bakim_hedef)
        
        if dagilim_standart:
            standart_liste = dagilim_standart['doz_listesi']
            
            # 2. GÜNCEL LİSTEYİ RUTİNDEN KOPYALA
            doz_listesi = list(standart_liste)
            
            # 3. ATLANACAK GÜNLERİ "0" YAP (Senkronizasyonu bozma)
            # Eğer 2 gün atlanacaksa, standart listenin ilk 2 gününü 0'a çekiyoruz.
            # Böylece 3. gün (Çarşamba), standart listenin Çarşambası ile aynı kalıyor.
            for i in range(gun_atla_sayisi):
                if i < 7:
                    doz_listesi[i] = 0.0
            
            # Gerçekte alınacak toplamı hesapla
            gercek_toplam = sum(doz_listesi)
            
            st.subheader(f"4. Reçete Planı (Bu hafta alınacak: {gercek_toplam:.2f} mg)")
            
            cols_cal = st.columns(7)
            for i, gun in enumerate(HAFTANIN_GUNLERI):
                with cols_cal[i]:
                    mg = doz_listesi[i]
                    rutin_mg = standart_liste[i]
                    rutin_parca = PARCA_ADLARI.get(rutin_mg, f"{rutin_mg}")
                    
                    if mg == 0.0 and i < gun_atla_sayisi:
                        st.markdown(
                            f"""
                            <div style='background:#ffe6e6;border:1px solid red;border-radius:10px;padding:10px;text-align:center;'>
                                <b>{gun[:3]}</b><br>
                                <span style='color:red;font-size:20px;font-weight:bold;'>⛔ ATLA</span><br>
                                <small style='color:gray;'>Rutin: {rutin_parca}</small>
                            </div>
                            """, unsafe_allow_html=True
                        )
                    else:
                        parca = PARCA_ADLARI.get(mg, f"{mg}")
                        color = "#0068c9" if mg > 0 else "#cccccc"
                        st.markdown(f"<div style='background:#f0f2f6;border-radius:10px;padding:10px;text-align:center;'><b>{gun[:3]}</b><br><span style='color:{color};font-size:20px;font-weight:bold;'>{parca}</span><br><small>{mg} mg</small></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            pdf_bytes = create_pdf(doktor_adi, guncel_inr, hedef_alt, hedef_ust, doz_listesi, standart_liste, klinik_uyari, gun_atla_sayisi)
            
            st.download_button(
                label="📄 İmzalı PDF Reçete İndir",
                data=pdf_bytes,
                file_name=f"warfarin_{doktor_adi.replace(' ', '_')}.pdf",
                mime="application/pdf",
                type="secondary"
            )
# v3.3
if __name__ == "__main__":
    app_arayuzu()