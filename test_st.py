import streamlit as st
import pandas as pd

df = pd.DataFrame([{"A": 1}])
st.data_editor(df, width="stretch")
