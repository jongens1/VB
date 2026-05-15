import streamlit as st
import pandas as pd

st.set_page_config(page_title="Warehouse Consolidator", layout="wide")

st.title("📦 Skladový Konsolidátor")
st.markdown("""
Tento nástroj identifikuje produkty roztrúsené na viacerých lokáciách a navrhne ich zlúčenie (konsolidáciu) 
s cieľom úplne uvoľniť čo najviac lokácií.
""")

# --- NAHRÁVANIE SÚBOROV ---
st.sidebar.header("Dáta")
uploaded_file = st.sidebar.file_uploader("Nahraj Excel súbor (oba sheety)", type=["xlsx"])

if uploaded_file:
    try:
        # Načítanie sheetov - predpokladáme poradie alebo názvy
        df_stock = pd.read_excel(uploaded_file, sheet_name=0)
        df_master = pd.read_excel(uploaded_file, sheet_name=1)

        st.success("Dáta úspešne načítané!")

        # --- PREPOJENIE DÁT ---
        # Spojíme stav zásob s master dátami lokácií
        df = pd.merge(
            df_stock, 
            df_master[['Názov lokácie', 'Max zaplnenie', 'Max počet produktov', 'Aktívne', 'Smazaná']], 
            left_on='Lokace', 
            right_on='Názov lokácie', 
            how='left'
        )

        # Filtrujeme len aktívne a nezmazané lokácie
        df = df[(df['Aktívne'] == 'Ano') & (df['Smazaná'] == 'Ne')]

        # --- LOGIKA KONSOLIDÁCIE ---
        # 1. Nájdeme produkty, ktoré sú na viac ako jednej lokácii
        product_counts = df.groupby('Produkt')['Lokace'].nunique()
        multi_loc_products = product_counts[product_counts > 1].index.tolist()

        recommendations = []

        for prod in multi_loc_products:
            prod_data = df[df['Produkt'] == prod].copy()
            total_qty = prod_data['Množstvo na lokácií'].sum()
            
            # Pre každý produkt hľadáme "Cieľovú lokáciu" (Target)
            # Podmienky: 
            # - Lokácia musí mať 'Max počet produktov' >= 1 (v našom prípade fixne 1 podľa zadania)
            # - 'Max zaplnenie' (kapacita v ks) musí byť >= Celkové množstvo produktu
            
            possible_targets = prod_data[prod_data['Max zaplnenie'] >= total_qty]

            if not possible_targets.empty:
                # Ako cieľ vyberieme tú, kde je už teraz najviac kusov (najmenej práce s presunom)
                target_loc_row = possible_targets.sort_values(by='Množstvo na lokácií', ascending=False).iloc[0]
                target_loc = target_loc_row['Lokace']
                
                # Ostatné lokácie sú určené na vyprázdnenie
                sources = prod_data[prod_data['Lokace'] != target_loc]
                
                for _, row in sources.iterrows():
                    recommendations.append({
                        'Produkt': prod,
                        'ZDROJ (Vyprázdniť)': row['Lokace'],
                        'Množstvo na presun': row['Množstvo na lokácií'],
                        'CIEĽ (Presunúť sem)': target_loc,
                        'Aktuálne na cieli': target_loc_row['Množstvo na lokácií'],
                        'Kapacita cieľa': target_loc_row['Max zaplnenie'],
                        'Stav po presune': f"{total_qty} / {target_loc_row['Max zaplnenie']}"
                    })

        # --- ZOBRAZENIE VÝSLEDKOV ---
        if recommendations:
            res_df = pd.DataFrame(recommendations)
            
            st.subheader(f"✅ Návrhy na presun (Nájdených {len(res_df)} presunov)")
            
            # KPI Boxy
            col1, col2 = st.columns(2)
            col1.metric("Uvoľniteľné lokácie", len(res_df))
            col2.metric("Počet produktov na konsolidáciu", res_df['Produkt'].nunique())

            st.dataframe(res_df, use_container_width=True)

            # Export do CSV
            csv = res_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("Stiahnuť zoznam presunov", csv, "presuny.csv", "text/csv")
        else:
            st.info("Nenašli sa žiadne vhodné konsolidácie. Sklad je optimálne využitý alebo sú produkty príliš objemné.")

    except Exception as e:
        st.error(f"Chyba pri spracovaní: {e}")
        st.info("Uistite sa, že stĺpce v Exceli sa volajú presne: 'Produkt', 'Lokace', 'Množstvo na lokácií', 'Názov lokácie', 'Max zaplnenie'.")

else:
    st.info("Prosím, nahrajte Excel súbor v bočnom paneli.")
