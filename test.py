"""
Sample query: 

Hi my name is Barbara Barr, and I order a lot of components from Argon Medical 
Devices and I want to know how much I need to order from them this week across 
all parts that I am responsible for in order to my products going below safety 
stock. (Also, how much have I already ordered? Make sure it’s part of my 
calculations).
"""

import streamlit as st
import pandas as pd
# import requests
from openai import OpenAI

# st.markdown("""
#             <style>
#             footer.st-emotion-cache-cio0dv.ea3mdgi1 {
#                 display: none;
#             }
#             """, unsafe_allow_html=True)

OPENAI_API_KEY = st.secrets["openai"]["api_key"]
llm = OpenAI(api_key=OPENAI_API_KEY)

st.header("Connect your Data Sources")
bom = pd.read_csv("data/bom.csv")
current_stock = pd.read_csv("data/current_stock.csv")
incoming_po = pd.read_csv("data/incoming_po.csv")
safety_stock = pd.read_csv("data/safety_stock.csv")
supplier_list = pd.read_csv("data/supplier_list.csv")
usage_forecast = pd.read_csv("data/usage_forecast.csv")

with st.expander("Bill of Materials"):
    st.write(bom)
with st.expander("Current Stock"):
    st.write(current_stock)
with st.expander("Incoming PO"):
    st.write(incoming_po)
with st.expander("Safety Stock"):
    st.write(safety_stock)
with st.expander("Supplier List"):
    st.write(supplier_list)
with st.expander("Usage Forecast"):
    st.write(usage_forecast)

st.header("Query your Procurement Plan")
user_query = ""
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("What do I need to order this week?"):
        user_query = "What do I need to order this week?"
with col2:
    if st.button("When is the order from Rajit's Pumps coming?"):
        user_query = "When is the order from Rajit's Pumps coming?"
with col3:
    if st.button("How much have I already ordered from Ben's Motors?"):
        user_query = "How much have I already ordered from Ben's Motors?"

# user_query = st.text_area("Enter query here", value=user_query, height=150)

st.write(f"### User query: {user_query}")

if user_query:
    response = llm.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"Given the following data {bom.to_json()} {current_stock.to_json()} {incoming_po.to_json()} {safety_stock.to_json()} {supplier_list.to_json()} {usage_forecast.to_json()} answer the following query: {user_query}. List each item as a bullet point."},
        ]
    )
    st.write(response.choices[0].message.content)
