
import pandas as pd
import streamlit as st
import random
import requests
import io
from PIL import Image
from sentence_transformers.util import semantic_search
import torch


# In[2]:

def get_data():

    df_oct = pd.read_csv("data/vumonic_india_food_delivery_20231001_20231031.csv", low_memory=False)
    df_nov = pd.read_csv("data/vumonic_india_food_delivery_20231101_20231130.csv", low_memory=False)

    # with open('data/vumonic_india_food_delivery_20231201_20231231.csv', 'r') as f:
    #     first_line = f.readline()
    # columns = first_line.replace('\n', '').split(',')
    columns = df_nov.columns

    df_dec = pd.read_csv('data/vumonic_india_food_delivery_20231201_20231231.csv', usecols=columns, encoding='latin-1', low_memory=False)

    df = pd.concat([df_dec, df_nov, df_oct], ignore_index=True)
    drop_columns = ['mid', 'sender_id', 'year', 'month', 'day', 'order_promotion_discount', 
                    'order_coupon_discount', 'order_seller_discount', 'order_delivery_discount',
                    'order_status', 'order_delivery_discount', 'delivery_address_postal_code', 'order_payment_currency',
                    'restaurant_address_postal_code', 'user_dob', 'user_address_postal_code', 'user_address_country']
    df =  df.drop(drop_columns, axis=1)
    df = df[df['user_age'] != 'male']
    
    return df


def get_cities(df, city):
    ty = df.astype('str').unique().tolist()
    if 'nan' in ty:
        ty.remove('nan')
        
    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_id}"
    headers = {"Authorization": "Bearer hf_api_token"}

    def query(texts):
        response = requests.post(api_url, headers=headers, json={"inputs": texts, "options":{"wait_for_model":True}})
        return response.json()

    output = query(ty)
    eb = pd.DataFrame(data={"City":ty, "Embedding":output})
    question = [city]
    query_output = query(question)

    hits = semantic_search(torch.FloatTensor(query_output), torch.FloatTensor(eb['Embedding'].tolist()), top_k=4)
    city_options = [eb["City"][hits[0][i]['corpus_id']] for i in range(len(hits[0]))]
    return city_options


def select_items(df_city):


    df_itemcount = df_city[~df_city.product_name.str.lower().str.contains('no ', na=False)].product_name.value_counts().head(15).reset_index().rename(columns={'product_name': 'count', 'index': 'product_name'})


    # Min-Max Normalization
    # df_itemcount['count_minmax'] = (df_itemcount['count'] - 0) / (df_itemcount['count'].max() - 0)
    df_itemcount['count_minmax'] = df_itemcount['count'] / df_itemcount['count'].sum()

    # In[120]:
    

    items = ["Random"] + df_itemcount['product_name'].tolist()

    
    itemchoice_select = st.selectbox("Select Food Product", items)

    if itemchoice_select == "Random":
        itemchoice = random.choices(items[1:], weights=df_itemcount['count_minmax'], k=1)[0]
    else:
        itemchoice = itemchoice_select


    df_city_item = df_city[df_city.product_name == itemchoice]
    
    restaurants = ["Random"] + df_city_item.restaurant_name.value_counts(dropna=False).head(5).index.tolist()
    
    res_choice = "Random"
    
    if itemchoice_select != "Random":
        res_choice = st.selectbox("Select Restaurant", restaurants)
    
    if res_choice == "Random":
        res_choice = random.choice(restaurants)


    column_names = [
        'company', 'product_name', 'product_price', 
        'product_quantity', 'product_total', 'order_convenience_fee', 
        'order_packaging_fee', 'order_delivery_fee', 'order_taxes', 'order_discount',
        'order_discount_code', 'premium_membership', 
        'premium_membership_type', 'free_delivery',
        'delivery_address_city', 'delivery_address_state', 'restaurant_name', 
        'restaurant_address_city', 'restaurant_address_state'
    ]

    df_print = df_city_item[df_city_item.restaurant_name == res_choice].sample(n=1)[column_names].reset_index(drop=True)
    
    
    order_details = ""
    for i in df_print:
        order_details += f"{i.title()}: {str(df_print[i][0])}\n\n"
    
    if st.button('Generate food item order'):
        generate_order(itemchoice, res_choice, order_details)
    
    

def generate_order(itemchoice, res_choice, order_details):


    image_generation_string = f"Food item {itemchoice} from restaurant {res_choice}"


    API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
    headers = {"Authorization": "Bearer hf_api_token"}

    def query(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.content
    image_bytes = query({
        "inputs": image_generation_string,
    })
    # You can access the image with PIL.Image for example

    image = Image.open(io.BytesIO(image_bytes))

    st.image(image)


    prompt = f"Create a delicious product description of Food item {itemchoice} from restaurant {res_choice} in around 100 words..\n(Write your food item review with good keywords)"


    # API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-v0.1"
    # API_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf"
    API_URL = "https://api-inference.huggingface.co/models/google/gemma-7b-it"
    # headers = {"Authorization": "Bearer hf_api_token"}

    def query(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.json()

    output = query({
        "inputs": prompt,
    })


    # In[217]:

    st.subheader('\n\n'+image_generation_string)
    
    st.caption(f"{output[0]['generated_text'].replace(prompt, '')}\n\n")
    
    st.write("Order details-")
    st.info(order_details)
    
    
df = get_data()

city = st.text_input('Enter your City', 'New Delhi')


if city:
    df_city = df[df.delivery_address_city.str.lower() == city.lower()]
    if len(df_city) == 0:
        st.write("City does not exist in data. Did you mean:")
        city_options = get_cities(df.delivery_address_city, city.lower())
        city_radio = st.radio("City options",
                                city_options)
        df_city = df[df.delivery_address_city.str.lower() == city_radio.lower()]
        select_items(df_city)
    else:
        select_items(df_city)
        
