import os
from pathlib import Path
import shutil

def on_cloud() -> bool:
    # Allow override via Secrets: FORCE_CLOUD = "1"
    if os.environ.get("FORCE_CLOUD", "") == "1":
        return True
    return os.path.isdir("/mount/data")

IS_CLOUD = on_cloud()
DATA_DIR = Path("/mount/data") if IS_CLOUD else Path(".")
# Only create locally; /mount/data exists on Cloud and shouldn't be mkdir'ed by the app
if not IS_CLOUD:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "meals.db"
REMEMBER_PATH = DATA_DIR / "remember.json"

# --- Safe, optional seed (won't crash if missing or unwritable) ---
SEED_DB = Path("seed/meals.db")
if IS_CLOUD and (not DB_PATH.exists()) and SEED_DB.exists():
    try:
        # Parent should already exist on Cloud; if not, don't crash
        shutil.copy(str(SEED_DB), str(DB_PATH))
    except Exception as e:
        # Just continue: SQLite will create the DB on connect
        pass

import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd
import json, os
from zoneinfo import ZoneInfo
from datetime import date as _date
# ---------- DB Setup ----------

conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
c = conn.cursor()
c.execute("PRAGMA journal_mode=WAL;")  # better for concurrent reads


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
c.execute('''CREATE TABLE IF NOT EXISTS goals (
                username TEXT PRIMARY KEY,
                calories REAL,
                protein REAL
            )''')
try:
    # Normalize rows where meal_type is NULL or empty
    c.execute("UPDATE meals SET meal_type='Other' WHERE meal_type IS NULL OR TRIM(meal_type)=''")
    conn.commit()
except sqlite3.OperationalError:
    # This can happen if the column is missing in old DB schema
    pass
try:
    c.execute("ALTER TABLE meals ADD COLUMN meal_type TEXT DEFAULT 'Other'")
    conn.commit()
except sqlite3.OperationalError:
    # This happens if the column already exists
    pass
conn.commit()

# ---------- Auth ----------
CRED_FILE = str(REMEMBER_PATH)
LOCAL_TZ = ZoneInfo("America/Chicago")  # set once at top of file

def save_remember(username):
    with open(CRED_FILE, "w") as f:
        json.dump({"username": username}, f)

def load_remember():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r") as f:
            return json.load(f).get("username")
    return None

def clear_remember():
    if os.path.exists(CRED_FILE):
        os.remove(CRED_FILE)
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
def set_goal(username, calories, protein):
    c.execute("INSERT OR REPLACE INTO goals VALUES (?, ?, ?)", (username, calories, protein))
    conn.commit()

def get_goal(username):
    c.execute("SELECT calories, protein FROM goals WHERE username=?", (username,))
    return c.fetchone()

def get_item_defaults(username, item):
    """Return (serving_size_default, calories_per_serving_default, protein_per_serving_default)
       derived from the most recent matching meal with valid weight/serving_size."""
    if not item:
        return 1.0, 0.0, 0.0
    c.execute(
        """
        SELECT serving_size, calories, protein, weight
        FROM meals
        WHERE username=? AND TRIM(item)=TRIM(?) AND weight > 0 AND serving_size > 0
        ORDER BY id DESC
        LIMIT 1
        """,
        (username, item)
    )
    row = c.fetchone()
    if row:
        prev_serving, cal_total, pro_total, prev_weight = row
        cal_per_serv = (cal_total / prev_weight) * prev_serving
        pro_per_serv = (pro_total / prev_weight) * prev_serving
        return float(prev_serving), float(cal_per_serv), float(pro_per_serv)
    return 1.0, 0.0, 0.0

remembered_user = load_remember()
if remembered_user and not st.session_state.get("logged_in", False):
    st.session_state.logged_in = True
    st.session_state.username = remembered_user

def user_count():
    c.execute("SELECT COUNT(*) FROM users")
    return c.fetchone()[0] or 0

if user_count() == 0:
    # Prefer pulling these from secrets or env for safety:
    # admin_user = st.secrets.get("ADMIN_USER", "msjojare")
    # admin_pass = st.secrets.get("ADMIN_PASS", "CHANGE_ME")
    admin_user = "msjojare"
    admin_pass = "GokuMtu@12345"  # change later!
    add_user(admin_user, admin_pass)
    st.info(f"First-time setup: created user **{admin_user}**. Log in, then change the password.")
# ---------- UI ----------
st.title("🍽️ Meal Tracker Dashboard")

# Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
with st.expander("🔎 Debug Storage Info"):
    st.write("Cloud environment:", IS_CLOUD)
    st.write("DB path in use:", DB_PATH)
    st.write("Remember path:", REMEMBER_PATH)

if not st.session_state.get("logged_in", False):
     # If no users yet, show a small setup form
    if user_count() == 0:
        st.warning("No users exist yet. Create the first account:")
        with st.form("first_user"):
            nu = st.text_input("New username")
            np = st.text_input("New password", type="password")
            create_btn = st.form_submit_button("Create account")
        if create_btn:
            if nu.strip() and np.strip():
                add_user(nu.strip(), np)
                st.success("Account created! Please log in below.")
            else:
                st.error("Username and password are required.")

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember Me")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        if check_login(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username

            if remember_me:
                save_remember(username)  # ✅ Persist login
            else:
                clear_remember()

            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials")

else:
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    menu = st.sidebar.radio("Menu", ["Add Meal", "View History", "Daily Summary", "Logout"])

    if menu == "Logout":
        clear_remember()  # ✅ Remove saved login
        st.session_state.logged_in = False
        st.rerun()
    # ---------- Add Meal ----------
    elif menu == "Add Meal":
        st.subheader("Add a Meal")

        # 1) Pick item OUTSIDE the form so selection triggers a rerun
        c.execute("SELECT DISTINCT item FROM meals WHERE username=?", (st.session_state.username,))
        prev_items = sorted([ (r[0] or "").strip() for r in c.fetchall() if r[0] ])

        item_choice = st.selectbox("Choose from previous items", [""] + prev_items, key="add_item_choice")
        new_item = st.text_input("Or enter a new item name", key="add_new_item")

        # Decide which item to use (trim to avoid space mismatches)
        effective_item = (new_item.strip() or item_choice.strip())

        # 2) Compute defaults from DB (if any)
        serving_default, cal_serv_default, pro_serv_default = get_item_defaults(st.session_state.username, effective_item)

        # 3) The actual form (weights etc.)
        # Use keys that depend on the selected item → resets values when item changes
        with st.form("add_meal"):
            entry_date = st.date_input(
                "Date",
                value=datetime.now(LOCAL_TZ).date(),  # default to local today
                key=f"add_date_{effective_item or 'none'}"
            )
            weight = st.number_input(
                "Weight (g)", min_value=0.0, step=1.0,
                key=f"add_weight_{effective_item or 'none'}"
            )
            serving_size = st.number_input(
                "Serving Size (g)", min_value=1.0, step=1.0, value=float(serving_default),
                key=f"add_serving_{effective_item or 'none'}"
            )
            calories_per_serving = st.number_input(
                "Calories per Serving", min_value=0.0, step=1.0, value=float(cal_serv_default),
                key=f"add_cal_serv_{effective_item or 'none'}"
            )
            protein_per_serving = st.number_input(
                "Protein per Serving (g)", min_value=0.0, step=0.1, value=float(pro_serv_default),
                key=f"add_pro_serv_{effective_item or 'none'}"
            )
            meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"], index=0)

            # Totals (auto)
            calories = (weight / serving_size) * calories_per_serving if serving_size > 0 else 0.0
            protein  = (weight / serving_size) * protein_per_serving if serving_size > 0 else 0.0

            st.write(f"**Calculated Calories:** {calories:.2f}")
            st.write(f"**Calculated Protein:** {protein:.2f} g")

            submitted = st.form_submit_button("Add Meal")

        # 4) Submit handler
        if submitted:
            if not effective_item:
                st.error("Please enter or select an item name.")
            else:
                # Decide which item name to use
                item = new_item.strip() if new_item.strip() != "" else item_choice.strip()
                c.execute('''INSERT INTO meals (username, date, item, weight, serving_size, calories, protein, meal_type)                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    st.session_state.username,
                    entry_date.isoformat(),        # ✅ store the chosen date
                    item, weight, serving_size, calories, protein, meal_type
                ))
                conn.commit()
                st.success(f"Meal '{effective_item}' added!")
                st.rerun()

    # ---------- History ----------
    elif menu == "View History":
        st.subheader("Meal History")

        # Fetch meals including meal_type
        c.execute(
            """SELECT id, date, item, weight, serving_size, calories, protein, meal_type
            FROM meals 
            WHERE username=? 
            ORDER BY date DESC""",
            (st.session_state.username,)
        )
        rows = c.fetchall()
        df = pd.DataFrame(
            rows,
            columns=["ID", "Date", "Item", "Weight (g)", "Serving Size", "Calories", "Protein (g)", "Meal Type"]
        )

        if df.empty:
            st.info("No meals logged yet.")
        else:
            # Group by Date
            for date, group in df.groupby("Date"):
                st.markdown(f"### 📅 {date}")

                for _, row in group.iterrows():
                    with st.expander(f"{row['Meal Type']} – {row['Item']}"):
                        st.write(f"**Weight:** {row['Weight (g)']} g")
                        st.write(f"**Serving Size:** {row['Serving Size']} g")
                        st.write(f"**Calories:** {row['Calories']:.1f}")
                        st.write(f"**Protein:** {row['Protein (g)']:.1f} g")

                        col1, col2 = st.columns(2)

                        # --- Edit button ---
                        # when edit button is clicked
                        if col1.button("✏️ Edit", key=f"edit_{row['ID']}"):
                            st.session_state.editing_id = row["ID"]

                        # render form only if this row is being edited
                        if st.session_state.get("editing_id") == row["ID"]:
                            with st.form(f"edit_form_{row['ID']}"):
                                current_date = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                                new_date = st.date_input("Date", value=current_date, key=f"date_{row['ID']}")

                                new_weight = st.number_input("New Weight (g)", value=row["Weight (g)"], step=1.0, key=f"weight_{row['ID']}")
                                new_serving = st.number_input("New Serving Size (g)", value=row["Serving Size"], step=1.0, key=f"serving_{row['ID']}")
                                new_protein = st.number_input("New Protein (g)", value=row["Protein (g)"], step=0.1, key=f"protein_{row['ID']}")

                                meal_types = ["Breakfast", "Lunch", "Dinner", "Snack", "Other"]
                                current_type = row["Meal Type"] if row["Meal Type"] in meal_types else "Other"
                                new_meal_type = st.selectbox("Meal Type", meal_types, index=meal_types.index(current_type), key=f"type_{row['ID']}")

                                save_btn = st.form_submit_button("Save Changes")
                                cancel_btn = st.form_submit_button("Cancel")

                            if save_btn:
                                c.execute(
                                    "UPDATE meals SET date=?, weight=?, serving_size=?, protein=?, meal_type=? WHERE id=? AND username=?",
                                    (new_date.isoformat(), new_weight, new_serving, new_protein, new_meal_type, row["ID"], st.session_state.username)
                                )
                                conn.commit()
                                st.success("Meal updated!")
                                st.session_state.editing_id = None
                                st.rerun()

                            if cancel_btn:
                                st.session_state.editing_id = None
                                st.rerun()

                        # --- Delete button ---
                        if col2.button("🗑️ Delete", key=f"delete_{row['ID']}"):
                            c.execute("DELETE FROM meals WHERE id=? AND username=?", (row["ID"], st.session_state.username))
                            conn.commit()
                            st.warning(f"Deleted {row['Item']}")
                            st.rerun()

    # ---------- Daily Summary ----------
    elif menu == "Daily Summary":
        st.subheader("Daily Summary")
          # --- Goal Setting Form ---
        current_goal = get_goal(st.session_state.username)
        with st.form("set_goal_form"):
            goal_cal = st.number_input(
                "Target Calories", 
                min_value=0.0, step=10.0, 
                value=current_goal[0] if current_goal else 2000.0
            )
            goal_pro = st.number_input(
                "Target Protein (g)", 
                min_value=0.0, step=1.0, 
                value=current_goal[1] if current_goal else 100.0
            )
            save_goal = st.form_submit_button("💾 Save Goal")

        if save_goal:
            set_goal(st.session_state.username, goal_cal, goal_pro)
            st.success(f"Goal saved! {goal_cal:.0f} calories, {goal_pro:.0f} g protein")
            st.rerun()
        df = pd.read_sql_query(
            "SELECT date, calories, protein FROM meals WHERE username=?",
            conn, params=(st.session_state.username,)
        )

        if df.empty:
            st.info("No meals logged yet.")
        else:
            df["Date"] = pd.to_datetime(df["date"])
            period = st.selectbox("Group By", ["Day", "Week", "Month"])

            if period == "Day":
                grouped = df.groupby(df["Date"].dt.date).sum(numeric_only=True)
            elif period == "Week":
                grouped = df.groupby(df["Date"].dt.isocalendar().week).sum(numeric_only=True)
            else:  # Month
                grouped = df.groupby(df["Date"].dt.to_period("M")).sum(numeric_only=True)

            # Always rename actuals
            grouped = grouped.rename(columns={"calories": "Actual Calories", "protein": "Actual Protein"})

            # If goals exist → add them
            goal = get_goal(st.session_state.username)
            if goal:
                g_cal, g_pro = goal
                grouped["Target Calories"] = g_cal
                grouped["Target Protein"] = g_pro
                grouped = grouped[["Actual Calories", "Actual Protein", "Target Calories", "Target Protein"]]
            else:
                grouped = grouped[["Actual Calories", "Actual Protein"]]

            st.dataframe(grouped)
