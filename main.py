import streamlit as st
import pandas as pd
from openai import OpenAI
from datetime import datetime, timedelta
import random
import calendar
from time import sleep

OPENAI_API_KEY = st.secrets["openai"]["api_key"]
random.seed(42)

@st.cache_resource
def load_model():
    return OpenAI(api_key=OPENAI_API_KEY)

@st.cache_data
def get_current_month():
    return datetime.now().strftime("%m")

@st.cache_data
def load_data():
    bom = pd.read_csv("data/bom.csv")
    current_stock = pd.read_csv("data/current_stock.csv")
    incoming_po = pd.read_csv("data/incoming_po.csv")
    safety_stock = pd.read_csv("data/safety_stock.csv")
    supplier_list = pd.read_csv("data/supplier_list.csv")
    usage_forecast = pd.read_csv("data/usage_forecast.csv")
    return bom, current_stock, incoming_po, safety_stock, supplier_list, usage_forecast

@st.cache_data
def handle_user_query(user_query, bom, current_stock, incoming_po, safety_stock, supplier_list, usage_forecast):
    if not user_query:
        return ""

    llm = load_model()

    bom_json, current_stock_json, incoming_po_json, safety_stock_json, supplier_list_json, usage_forecast_json = bom.to_json(), current_stock.to_json(), incoming_po.to_json(), safety_stock.to_json(), supplier_list.to_json(), usage_forecast.to_json()
    
    context_message = f"You are a helpful assistant here to help someone answer questions about their procurement plan. Here is all of the information you need to know: BOM: {bom_json}, Current Stock: {current_stock_json}, Incoming PO: {incoming_po_json}, Safety Stock: {safety_stock_json}, Supplier List: {supplier_list_json}, Usage Forecast: {usage_forecast_json}"
    
    completion = llm.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": context_message},
            {"role": "user", "content": user_query}
        ]
    )

    response = completion.choices[0].message.content

    return response

def get_days_in_curr_month(curr_month, curr_year):
    _, num_days = calendar.monthrange(curr_year, curr_month)
    return num_days

@st.cache_data
def get_days_until_next_month():
    today = datetime.now()

    if today.month == 12:
        first_day_next_month = datetime(today.year + 1, 1, 1)
    else:
        first_day_next_month = datetime(today.year, today.month + 1, 1)

    days_until_next_month = (first_day_next_month - today).days
    return days_until_next_month

@st.cache_data
def get_build_capacity(part_id, bom, current_stock, incoming_po):
    per_unit_quantity =  bom[bom["Item ID"] == part_id]["Quantity"].values[0]
    current_stock_value = current_stock[current_stock['Item ID'] == part_id]['Current Stock'].values[0]
    return per_unit_quantity * current_stock_value 

@st.cache_data
def get_current_stock(part_id, current_stock):
    return current_stock[current_stock['Item ID'] == part_id]['Current Stock'].values[0]

@st.cache_data
def get_safety_stock(part_id, safety_stock):
    return safety_stock[safety_stock['Item ID'] == part_id]['Safety Stock'].values[0]

@st.cache_data
def get_supplier_information(part_id, supplier_list):
    supplier_info = []
    supplier_list = supplier_list[supplier_list['Item ID'] == part_id]
    for row in supplier_list.itertuples():
        _, _, _, supplier_id, supplier_name, reorder_quantity, lead_time = row
        reliability_score = random.randint(60, 100)

        supplier_info.append((
            supplier_id,
            supplier_name,
            lead_time,
            reorder_quantity,
            reliability_score,
        ))
    
    supplier_info = sorted(supplier_info, key=lambda x: x[-1], reverse=True)
    
    return pd.DataFrame(supplier_info, columns=["Supplier ID", "Supplier Name", "Lead Time (days)", "Reorder Quantity", "Reliability Score"])

def get_good_until_date(part_id, build_capacity, usage_forecast, safety_stock):
    incoming_po = st.session_state["incoming_po"]

    curr_month = datetime.now().month
    curr_year = datetime.now().year

    forecast = usage_forecast[(usage_forecast['Month'] == curr_month) & (usage_forecast['Year'] == curr_year)]['Usage'].values[0]
    safety_stock_value = get_safety_stock(part_id, safety_stock)
    
    days_filter = get_days_until_next_month() 
    incoming_po_curr_month = incoming_po[(incoming_po['Item ID'] == part_id) & (incoming_po['Arrive Time (days)'] <= days_filter)]['Stock Due'].sum()
    build_capacity += incoming_po_curr_month

    while build_capacity - forecast >= safety_stock_value:
        build_capacity -= forecast

        if curr_month == 12:
            curr_year += 1
        curr_month = (curr_month % 12) + 1

        incoming_po_curr_month = incoming_po[
            (incoming_po['Item ID'] == part_id) &
            (incoming_po['Arrive Time (days)'] > days_filter) &
            (incoming_po['Arrive Time (days)'] <= days_filter + get_days_in_curr_month(curr_month, curr_year))
        ]['Stock Due'].sum()
        build_capacity += incoming_po_curr_month
        days_filter += get_days_in_curr_month(curr_month, curr_year)

        forecast = usage_forecast[(usage_forecast['Month'] == curr_month) & (usage_forecast['Year'] == curr_year)]['Usage'].values[0]

    return datetime(curr_year, curr_month, 1)

@st.experimental_dialog("Order Impact")
def order(part_id, part_description, supplier_info):
    quantity = st.number_input("Quantity", min_value=1, value=1)
    st.write(f"Ordering {supplier_info['Reorder Quantity'] * quantity} units from {supplier_info['Supplier Name']}")
    st.write(f"Expected delivery in {supplier_info['Lead Time (days)']} days")
    
    if st.button("Submit Order"):
        st.session_state["incoming_po"].loc[len(st.session_state["incoming_po"])] = [
            part_id,
            part_description,
            supplier_info['Reorder Quantity'] * quantity,
            supplier_info['Lead Time (days)'],
            supplier_info['Supplier ID']
        ]

        st.success("Order submitted successfully")
        sleep(5)
        handle_user_query.clear()
        st.rerun()

def get_days_until_trouble(part_id, good_until_date, supplier_list):
    bail_out_days = supplier_list[supplier_list['Item ID'] == part_id]['Lead Time (days)'].min()
    days_until_trouble = (good_until_date - datetime.now()).days - bail_out_days
    return int(days_until_trouble)

def get_danger_level(days_until_trouble):
    if days_until_trouble < 0:
        danger_level = 1.0
    elif days_until_trouble < 7:
        danger_level = 0.75
    elif days_until_trouble < 30:
        danger_level = 0.5
    else:
        danger_level = 0.25
    return danger_level

def get_danger_bar_html(danger_level):
    if danger_level >= 1.0:
        color = "#ff4d4d" # critical
    elif danger_level >= 0.75:
        color = "#ffcc00" # warning
    elif danger_level >= 0.5:
        color = "#4CAF50" # normal
    else:
        color = "#2196F3" # good
        
    danger_bar_html = f"""
    <div style='background-color: #f0f0f0; width: 100%; height: 0.5rem; flex: 1 1 0%; display: flex; flex-direction: column; border-radius: 0.25rem; overflow: hidden;'>
        <div style='background-color: {color}; width: {danger_level * 100}%; height: 100%; border-radius: 0.25rem;'></div>
    </div>
    """
    return danger_bar_html

def main():
    st.set_page_config(layout="wide")

    st.header("Connect your Data Sources")
    st.markdown("[Link your ERP]() or [Upload Manually]()")
    bom, current_stock, incoming_po, safety_stock, supplier_list, usage_forecast = load_data()
    
    with st.expander("Bill of Materials"):
        st.write(bom)
    with st.expander("Current Stock"):
        st.write(current_stock)
    with st.expander("Incoming PO"):
        if "incoming_po" not in st.session_state:
            st.session_state["incoming_po"] = incoming_po
        st.write(st.session_state["incoming_po"])
    with st.expander("Safety Stock"):
        st.write(safety_stock)
    with st.expander("Supplier List"):
        st.write(supplier_list)
    with st.expander("Usage Forecast"):
        st.write(usage_forecast)

    st.write("### Chat with your Procurement Plan")

    if "user_query" not in st.session_state:
        st.session_state["user_query"] = ""

    question_columns = st.columns(3)

    q1, q2, q3 = "How many heart pumps are we making this July?", "When is the order from Rajit's Pumps coming?", "How much have I already ordered from Ben's Motors?"
    with question_columns[0]:
        if st.button(q1):
            st.session_state["user_query"] = q1
    with question_columns[1]:
        if st.button(q2):
            st.session_state["user_query"] = q2
    with question_columns[2] :
        if st.button(q3):
            st.session_state["user_query"] = q3

    st.write(f"#### User query: {st.session_state['user_query']}")

    response = handle_user_query(st.session_state["user_query"], bom, current_stock, st.session_state["incoming_po"], safety_stock, supplier_list, usage_forecast)

    st.write(f"#### Response: {response}")

    st.header("What do I need to order this week?")

    for _, row in bom.iterrows():
        part_id = row["Item ID"]
        build_capacity = get_build_capacity(part_id, bom, current_stock, incoming_po)
        good_until_date = get_good_until_date(part_id, build_capacity, usage_forecast, safety_stock)
        days_until_trouble = get_days_until_trouble(part_id, good_until_date, supplier_list)
        last_order_date = datetime.now() + timedelta(days=days_until_trouble)

        st.write(f"### {row['Description']}")
        description_columns = st.columns([1, 3])

        with description_columns[0]:
            st.latex(f"\\text{{Need to order by {last_order_date.strftime('%B %d, %Y')} }} \quad \\text{{(}} {days_until_trouble} \\text{{ days left)}}")
        with description_columns[1]:
            danger_level = get_danger_level(days_until_trouble)
            st.markdown(get_danger_bar_html(danger_level), unsafe_allow_html=True)

        with st.expander("Supplier Information"):
            supplier_info = get_supplier_information(part_id, supplier_list)
            num_buttons = len(supplier_info)

            supplier_table, order_buttons = st.columns(2)
            
            with supplier_table:
                st.table(supplier_info)

            with order_buttons:
                for button in range(num_buttons):
                    reliability_score = supplier_info['Reliability Score'].iloc[button]
                    
                    if reliability_score >= 90:
                        button_label = ":green[Order]"
                        description = "High reliability score"
                    elif reliability_score >= 70:
                        button_label = ":orange[Order]"
                        description = "Medium reliability score"
                    else:
                        button_label = ":red[Order]"
                        description = "Low reliability score"
    
                    if st.button(button_label, help=description, key=supplier_info['Supplier ID'].iloc[button], disabled=datetime.now() + timedelta(days=int(supplier_info.iloc[button]["Lead Time (days)"])) > good_until_date):
                        order(part_id, row["Description"], supplier_info.iloc[button])
        
if __name__ == "__main__":
    main()