import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import glob
import os

st.set_page_config(page_title="Dashboard SUMO - Análise de Viagens", layout="wide")

@st.cache_data
def processar_arquivos_sumo():
    dados = []
    arquivos = glob.glob("output_trips_*.xml")
    
    for arquivo in arquivos:
        nome_base = os.path.basename(arquivo).replace(".xml", "")
        partes = nome_base.split("_")
        
        if len(partes) >= 4:
            cenario = partes[2]  # P0, P1, P2, P3
            periodo = partes[3].capitalize()  # Manha, Tarde
        else:
            continue
            
        try:
            tree = ET.parse(arquivo)
            root = tree.getroot()
            
            # Contadores Gerais
            soma_tempo_seg_geral = 0.0
            qtd_viagens_geral = 0
            
            # Contadores Ônibus
            soma_tempo_seg_bus = 0.0
            qtd_viagens_bus = 0
            
            for trip in root.findall('tripinfo'):
                # Calcula duração da viagem
                duration = trip.get('duration')
                if duration:
                    tempo_viagem = float(duration)
                else:
                    arrival = trip.get('arrival')
                    depart = trip.get('depart')
                    if arrival and depart:
                        tempo_viagem = (float(arrival) - float(depart))
                    else:
                        tempo_viagem = 0.0
                        
                if tempo_viagem > 0:
                    # Acumula para TODOS os veículos
                    qtd_viagens_geral += 1
                    soma_tempo_seg_geral += tempo_viagem
                    
                    # Verifica se é ônibus (vType="bus" ou se a palavra 'bus' estiver no ID caso seu sumo esteja configurado diferente)
                    vType = trip.get('vType', '').lower()
                    vid = trip.get('id', '').lower()
                    
                    if vType == 'bus' or 'bus' in vType or 'bus' in vid:
                        qtd_viagens_bus += 1
                        soma_tempo_seg_bus += tempo_viagem
            
            # Calcula as médias (evitando divisão por zero)
            tempo_medio_geral = (soma_tempo_seg_geral / qtd_viagens_geral) if qtd_viagens_geral > 0 else 0
            tempo_medio_bus = (soma_tempo_seg_bus / qtd_viagens_bus) if qtd_viagens_bus > 0 else 0
            
            # Registra a linha "Todos os Veículos"
            dados.append({
                "Cenário": cenario,
                "Período": periodo,
                "Filtro": "Todos os Veículos",
                "Viagens Concluídas": qtd_viagens_geral,
                "Tempo Total (Horas)": soma_tempo_seg_geral / 3600,
                "Tempo Médio por Viagem (Minutos)": tempo_medio_geral / 60
            })
            
            # Registra a linha "Apenas Ônibus"
            dados.append({
                "Cenário": cenario,
                "Período": periodo,
                "Filtro": "Apenas Ônibus",
                "Viagens Concluídas": qtd_viagens_bus,
                "Tempo Total (Horas)": soma_tempo_seg_bus / 3600,
                "Tempo Médio por Viagem (Minutos)": tempo_medio_bus / 60
            })
            
        except Exception as e:
            st.error(f"Erro ao processar {arquivo}: {e}")
            
    return pd.DataFrame(dados)

def colorir_variacao_tempo(valor):
    if pd.isna(valor): return ''
    if valor < 0: return 'color: #00CC00; font-weight: bold;'
    elif valor > 0: return 'color: #FF4B4B; font-weight: bold;'
    return 'color: gray;'

def colorir_variacao_viagens(valor):
    if pd.isna(valor): return ''
    if valor > 0: return 'color: #00CC00; font-weight: bold;'
    elif valor < 0: return 'color: #FF4B4B; font-weight: bold;'
    return 'color: gray;'

# --- Construção do Dashboard ---

st.title("Análise de Outputs do SUMO 🚗🚌")
st.markdown("Comparativo de desempenho da rede considerando **Tempo de Viagem** e **Veículos que chegaram ao destino**.")

# O cache carrega ambos os filtros de uma vez
df_resultados_completos = processar_arquivos_sumo()

if not df_resultados_completos.empty:
    
    st.divider()
    
    # Controle para alternar entre as visões
    opcao_filtro = st.radio(
        "Selecione o tipo de veículo para análise:",
        options=["Todos os Veículos", "Apenas Ônibus"],
        horizontal=True
    )
    
    # Filtra o dataframe para exibir apenas o selecionado
    df_resultados = df_resultados_completos[df_resultados_completos["Filtro"] == opcao_filtro].copy()
    
    st.divider()
    
    aba1, aba2, aba3 = st.tabs(["⏱️ Tempo Total (Horas)", "🚗 Viagens Concluídas", "📊 Tempo Médio por Viagem (Minutos)"])
    
    def gerar_tabela_metrica(df, metrica, funcao_cor, formato_base, formato_var="{:+.2f}%"):
        df_pivot = df.pivot(index="Cenário", columns="Período", values=metrica)
        periodos = df_pivot.columns.tolist()
        colunas_var = []
        
        if 'P0' in df_pivot.index:
            for p in periodos:
                base = df_pivot.loc['P0', p]
                
                # Evita divisão por zero caso a base não tenha veículos registrados
                if pd.notna(base) and base != 0:
                    nome_col_var = f"Var. P0 (%) - {p}"
                    df_pivot[nome_col_var] = ((df_pivot[p] - base) / base) * 100
                    colunas_var.append(nome_col_var)
        
        formatacao = {p: formato_base for p in periodos}
        formatacao.update({c: formato_var for c in colunas_var})
        
        styled_df = df_pivot.style.format(formatacao, na_rep="-")
        if colunas_var:
            styled_df = styled_df.map(funcao_cor, subset=colunas_var)
            
        return styled_df

    with aba1:
        st.subheader(f"Tempo Total de Viagem - {opcao_filtro}")
        st.markdown("*Atenção: Quedas drásticas aqui podem indicar que os veículos não conseguiram terminar a viagem.*")
        st.dataframe(gerar_tabela_metrica(df_resultados, "Tempo Total (Horas)", colorir_variacao_tempo, "{:.2f} h"), use_container_width=True)

    with aba2:
        st.subheader(f"Total de Viagens Concluídas - {opcao_filtro}")
        st.markdown("*Se a variação for negativa e ficar vermelha, menos veículos conseguiram chegar ao destino.*")
        st.dataframe(gerar_tabela_metrica(df_resultados, "Viagens Concluídas", colorir_variacao_viagens, "{:,.0f} veículos"), use_container_width=True)

    with aba3:
        st.subheader(f"Tempo Médio por Viagem - {opcao_filtro}")
        st.markdown("*Tempo médio dos veículos que finalizaram a rota.*")
        st.dataframe(gerar_tabela_metrica(df_resultados, "Tempo Médio por Viagem (Minutos)", colorir_variacao_tempo, "{:.1f} min"), use_container_width=True)

else:
    st.warning("Nenhum arquivo 'output_trips_*.xml' foi encontrado na pasta.")