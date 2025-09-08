import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd

# ---------- DB Setup ----------
conn = sqlite3.connect("meals.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                date TEXT,
                item TEXT,
                weight REAL,
                serving_size REAL,
                calories REAL,
                protein REAL
            )''')
conn.commit()

# ---------- Auth ----------
def make_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", 
              (username, make_hash(password)))
    return c.fetchone()

def add_user(username, password):
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, make_hash(password)))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

# Create your account (one-time setup)
# add_user("msjojare", "GokuMtu@12345")  # change password here

# ---------- UI ----------
st.title("🍽️ Meal Tracker Dashboard")

# Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        if check_login(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Login successful!")
        else:
            st.error("Invalid credentials")
else:
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    menu = st.sidebar.radio("Menu", ["Add Meal", "View History", "Daily Summary", "Logout"])

    if menu == "Logout":
        st.session_state.logged_in = False
        st.rerun()

    # ---------- Add Meal ----------
    # ---------- Add Meal ----------
    elif menu == "Add Meal":
        st.subheader("Add a Meal")

        # Fetch distinct items from history
        c.execute("SELECT DISTINCT item FROM meals WHERE username=?", (st.session_state.username,))
        prev_items = [r[0] for r in c.fetchall()]

        with st.form("add_meal"):
            item_choice = st.selectbox("Choose from previous items (or type new below)", [""] + prev_items)
            new_item = st.text_input("Or enter a new item name")

            # Decide which item to use
            item = new_item if new_item.strip() != "" else item_choice

            weight = st.number_input("Weight (g)", min_value=0.0, step=1.0)
            serving_size = st.number_input("Serving Size (g)", min_value=1.0, step=1.0)
            calories_per_serving = st.number_input("Calories per Serving", min_value=0.0, step=1.0)
            protein_per_serving = st.number_input("Protein per Serving (g)", min_value=0.0, step=0.1)

            # Auto adjustment
            calories = (weight / serving_size) * calories_per_serving if serving_size > 0 else 0
            protein = (weight / serving_size) * protein_per_serving if serving_size > 0 else 0

            st.write(f"**Calculated Calories:** {calories:.2f}")
            st.write(f"**Calculated Protein:** {protein:.2f} g")

            submit_meal = st.form_submit_button("Add Meal")

        if submit_meal:
            if item.strip() == "":
                st.error("Please enter or select an item name.")
            else:
                c.execute('''INSERT INTO meals (username, date, item, weight, serving_size, calories, protein) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (st.session_state.username, datetime.today().strftime("%Y-%m-%d"),
                           item, weight, serving_size, calories, protein))
                conn.commit()
                st.success(f"Meal '{item}' added!")

    # ---------- History ----------
    elif menu == "View History":
        st.subheader("Meal History")
        c.execute("SELECT date, item, weight, calories, protein FROM meals WHERE username=? ORDER BY date DESC",
                  (st.session_state.username,))
        rows = c.fetchall()
        df = pd.DataFrame(rows, columns=["Date", "Item", "Weight (g)", "Calories", "Protein (g)"])
        st.dataframe(df)

    # ---------- Daily Summary ----------
    elif menu == "Daily Summary":
        st.subheader("Daily Summary")
        today = datetime.today().strftime("%Y-%m-%d")
        c.execute("SELECT SUM(calories), SUM(protein) FROM meals WHERE username=? AND date=?",
                  (st.session_state.username, today))
        result = c.fetchone()
        total_cal, total_pro = result if result else (0, 0)
        st.metric("Total Calories", f"{total_cal:.2f}")
        st.metric("Total Protein", f"{total_pro:.2f} g")

        # Breakdown
        c.execute("SELECT item, calories, protein FROM meals WHERE username=? AND date=?",
                  (st.session_state.username, today))
        rows = c.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["Item", "Calories", "Protein (g)"])
            st.table(df)
        else:
            st.info("No meals logged today.")
