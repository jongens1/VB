import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Warehouse Consolidator", layout="wide")

st.title("📦 Skladový Konsolidátor")

# --- LOGIKA KONSOLIDÁCIE (VYSVETLENIE) ---
with st.expander("ℹ️ Ako funguje logika hľadania?"):
    st.write("""
    1. **Párovanie:** Prepojí sa stav zásob (Sheet 1) s parametrami lokácií (Sheet 2).
    2. **Filter:** Vyberú sa len aktívne a nezmazané lokácie.
    3. **Identifikácia:** Nájdu sa produkty, ktoré sú fyzicky na 2 alebo viacerých rôznych lokáciách.
    4. **Kapacitný test:** Spočíta sa celkové množstvo kusov produktu na všetkých jeho pozíciách. 
       - Systém overí, či sa toto CELKOVÉ množstvo zmestí na JEDNU z týchto lokácií (podľa stĺpca 'Max zaplnenie').
    5. **Výber cieľa:** Ak sa zmestí, za cieľovú lokáciu sa vyberie tá, kde je už teraz najviac kusov (aby mal skladník čo najmenej práce).
    6. **Návrh:** Ostatné lokácie sa označia ako 'Zdroj' na úplné vyprázdnenie.
    """)

# --- NAČÍTANIE DÁT ---
# 1. Priorita: Súbor v repozitári
# 2. Priorita: Manuálny upload
DEFAULT_FILE = "datavb.xlsx"
df_stock = None
df_master = None

if os.path.exists(DEFAULT_FILE):
    try:
        df_stock = pd.read_excel(DEFAULT_FILE, sheet_name=0)
        df_master = pd.read_excel(DEFAULT_FILE, sheet_name=1)
        st.sidebar.success(f"Načítané automaticky zo súboru: {DEFAULT_FILE}")
    except Exception as e:
        st.sidebar.error(f"Nepodarilo sa načítať {DEFAULT_FILE}: {e}")

uploaded_file = st.sidebar.file_uploader("Alebo nahraj iný Excel súbor", type=["xlsx"])
if uploaded_file:
    df_stock = pd.read_excel(uploaded_file, sheet_name=0)
    df_master = pd.read_excel(uploaded_file, sheet_name=1)

if df_stock is not None and df_master is not None:
    # Čistenie názvov stĺpcov
    df_stock.columns = df_stock.columns.str.strip()
    df_master.columns = df_master.columns.str.strip()

    # Prepojenie
    df = pd.merge(
        df_stock, 
        df_master[['Názov lokácie', 'Max zaplnenie', 'Max počet produktov', 'Aktívne', 'Smazaná']], 
        left_on='Lokace', 
        right_on='Názov lokácie', 
        how='left'
    )

    # --- DEBUG INFO (Prečo máš 0 záznamov?) ---
    with st.sidebar.expander("DEBUG: Hodnoty v stĺpcoch"):
        st.write("Unikátne hodnoty v 'Aktívne':", df['Aktívne'].unique())
        st.write("Unikátne hodnoty v 'Smazaná':", df['Smazaná'].unique())

    # Konverzia na čísla
    df['Množstvo na lokácií'] = pd.to_numeric(df['Množstvo na lokácií'], errors='coerce').fillna(0)
    df['Max zaplnenie'] = pd.to_numeric(df['Max zaplnenie'], errors='coerce').fillna(0)

    # VOĽNEJŠÍ FILTER (ak nevieš presne, čo je v stĺpci Aktívne)
    # Ak stĺpec Aktívne obsahuje 'Ano', 'True', '1', 'A' (ignorujeme veľkosť písma)
    df['is_active'] = df['Aktívne'].astype(str).str.upper().str.strip()
    df['is_deleted'] = df['Smazaná'].astype(str).str.upper().str.strip()

    # Skúsme filter, ktorý nie je taký prísny
    mask = (df['is_active'].isin(['ANO', 'YES', '1', 'TRUE', 'A'])) & \
           (~df['is_deleted'].isin(['ANO', 'YES', '1', 'TRUE', 'A']))
    
    df_filtered = df[mask].copy()

    # Ak filter nič nenašiel, použi všetky dáta (vypni filter) a upozorni užívateľa
    if len(df_filtered) == 0:
        st.warning("⚠️ Filtre 'Aktívne' a 'Smazaná' nevybrali žiadne dáta. Zobrazujem všetky dostupné lokácie bez ohľadu na stav.")
        df_filtered = df.copy()

    st.write(f"Spracovávam **{len(df_filtered)}** záznamov o zásobách.")

    # --- KONSOLIDÁCIA ---
    # Produkty na viacerých lokáciách
    multi_loc = df_filtered.groupby('Produkt').filter(lambda x: x['Lokace'].nunique() > 1)
    
    recommendations = []
    
    for prod, group in multi_loc.groupby('Produkt'):
        total_qty = group['Množstvo na lokácií'].sum()
        
        # Môže sa celok zmestiť aspoň na jednu z aktuálnych lokácií?
        # Podmienka: Max zaplnenie >= celkové množstvo
        potential_targets = group[group['Max zaplnenie'] >= total_qty]
        
        if not potential_targets.empty:
            # Cieľ je tá, kde je najviac kusov teraz
            target_row = potential_targets.sort_values(by='Množstvo na lokácií', ascending=False).iloc[0]
            target_loc = target_row['Lokace']
            
            # Zdroje sú všetky ostatné
            sources = group[group['Lokace'] != target_loc]
            
            for _, row in sources.iterrows():
                recommendations.append({
                    'Produkt': prod,
                    'ZDROJ (Vyprázdniť)': row['Lokace'],
                    'Kusov na presun': row['Množstvo na lokácií'],
                    'CIEĽ (Presunúť sem)': target_loc,
                    'Zaplnenie po presune': f"{int(total_qty)} / {int(target_row['Max zaplnenie'])}"
                })

    if recommendations:
        st.subheader("🚀 Návrhy na optimálne presuny")
        st.dataframe(pd.DataFrame(recommendations), use_container_width=True)
    else:
        st.info("Nenašli sa produkty, ktoré by sa dali skonsolidovať do ich vlastných existujúcich lokácií.")

else:
    st.info("Nahrajte súbor datavb.xlsx na GitHub alebo ho sem vložte manuálne.")
