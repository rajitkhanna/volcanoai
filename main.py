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

OPENAI_API_KEY = st.secrets["openai"]["api_key"]
llm = OpenAI(api_key=OPENAI_API_KEY)

st.header("Connect your Data Sources")
component_data = pd.read_csv("All Components + Supplier Stryker.csv")
buyer_data = pd.read_csv("Stryker_Buyername_Products.csv", low_memory=False)

with st.expander("Data sources"):
    st.write(component_data)
    st.write(buyer_data)

st.header("Query your Procurement Plan")
user_query = st.text_area("Enter query here", height=150)

# st.write(user_query)

if user_query:
    component_data_json = component_data.to_json(orient='records')
    buyer_data_json = buyer_data.to_json(orient='records')

    response = llm.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"Return the person's name from the following prompt and only the name: {user_query}"},
        ]
    )

    name = response.choices[0].message.content

    response = llm.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"Return the supplier's name from the following prompt and only the name: {user_query}"},
        ]
    )

    supplier_name = response.choices[0].message.content

    filtered_df = buyer_data[(buyer_data["Buyer Number_2"] == name) & (buyer_data["Supplier"] == supplier_name.upper())]
    result = pd.merge(filtered_df, component_data, left_on='Item Number', right_on='Component ID', how='inner')

    # st.write(result)

    response = llm.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": f"Given the following data {result.to_json()} answer the following query: {user_query}. List each item as a bullet point."},
        ]
    )

    # from pprint import pprint
    # pprint(response)

    query_result = response.choices[0].message.content
    st.write(query_result)

    