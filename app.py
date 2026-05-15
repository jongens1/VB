import streamlit as st
import pandas as pd

st.set_page_config(page_title="Warehouse Consolidator", layout="wide")

st.title("📦 Skladový Konsolidátor")

uploaded_file = st.sidebar.file_uploader("Nahraj Excel súbor", type=["xlsx"])

if uploaded_file:
    try:
        df_stock = pd.read_excel(uploaded_file, sheet_name=0)
        df_master = pd.read_excel(uploaded_file, sheet_name=1)

        # Čistenie názvov stĺpcov (odstránenie medzier)
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

        # Prevod na čísla (ak by boli v Exceli ako text)
        df['Množstvo na lokácií'] = pd.to_numeric(df['Množstvo na lokácií'], errors='coerce').fillna(0)
        df['Max zaplnenie'] = pd.to_numeric(df['Max zaplnenie'], errors='coerce').fillna(0)

        # Flexibilnejší filter na Aktívne/Smazaná
        df['Aktívne'] = df['Aktívne'].astype(str).str.upper()
        df['Smazaná'] = df['Smazaná'].astype(str).str.upper()
        
        # Filtrujeme len relevantné (upravené na podmienku, aby to nebolo príliš prísne)
        df_filtered = df[(df['Aktívne'].isin(['ANO', 'YES', '1', 'TRUE'])) & 
                         (~df['Smazaná'].isin(['ANO', 'YES', '1', 'TRUE']))]

        st.success(f"Dáta načítané. Celkovo {len(df_filtered)} záznamov na aktívnych lokáciách.")

        # LOGIKA
        product_counts = df_filtered.groupby('Produkt')['Lokace'].nunique()
        multi_loc_products = product_counts[product_counts > 1].index.tolist()

        if not multi_loc_products:
            st.warning("V dátach sa nenachádzajú žiadne produkty, ktoré by boli na viac ako jednej aktívnej lokácii.")
        else:
            recommendations = []
            diagnostika = []

            for prod in multi_loc_products:
                prod_data = df_filtered[df_filtered['Produkt'] == prod]
                total_qty = prod_data['Množstvo na lokácií'].sum()
                max_capacity_available = prod_data['Max zaplnenie'].max()
                
                if max_capacity_available >= total_qty:
                    target_loc_row = prod_data.sort_values(by='Množstvo na lokácií', ascending=False).iloc[0]
                    target_loc = target_loc_row['Lokace']
                    sources = prod_data[prod_data['Lokace'] != target_loc]
                    
                    for _, row in sources.iterrows():
                        recommendations.append({
                            'Produkt': prod,
                            'ZDROJ (Zrušiť)': row['Lokace'],
                            'Množstvo': row['Množstvo na presun'],
                            'CIEĽ': target_loc,
                            'Využitie cieľa po presune': f"{int(total_qty)} / {int(target_loc_row['Max zaplnenie'])}"
                        })
                else:
                    diagnostika.append({
                        'Produkt': prod,
                        'Celkovo ks': total_qty,
                        'Najväčšia lokácia má kapacitu': max_capacity_available,
                        'Dôvod': 'Nezmestí sa na žiadnu zo súčasných lokácií'
                    })

            # Zobrazenie výsledkov
            if recommendations:
                st.subheader("✅ Návrhy na presun")
                st.dataframe(pd.DataFrame(recommendations), use_container_width=True)
            
            if diagnostika:
                with st.expander("🔍 Produkty na viacerých miestach, ktoré sa nedajú zlúčiť"):
                    st.write("Tieto produkty sú roztrúsené, ale ich celkové množstvo presahuje kapacitu ktorejkoľvek jednej lokácie, kde sa nachádzajú.")
                    st.dataframe(pd.DataFrame(diagnostika), use_container_width=True)

    except Exception as e:
        st.error(f"Chyba: {e}")
