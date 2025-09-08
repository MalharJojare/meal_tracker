# 🍽️ Meal Tracker Dashboard

A simple **Streamlit app** to track meals, calories, and protein intake.  
Built with **Python + Streamlit + SQLite**, designed for **single-user login** and persistent storage.  

---

## ✨ Features
- 🔑 **Login system** (only you can log in)  
- 📥 **Add meals**: enter new items or pick from previously logged items  
- ⚖️ Auto-calculates **calories & protein** based on weight vs serving size  
- 📊 **Daily summary** with total calories & protein  
- 📜 **Meal history** (stored in SQLite, persists across sessions)  
- 💾 **Local database** (`meals.db`) for storage  

---

## 📂 Project Structure
MealTracker/
│
├── meal_tracker.py # Main Streamlit app
├── meals.db # SQLite database (auto-created on first run)
├── requirements.txt # Dependencies
└── README.md # Project documentation

## 🚀 Getting Started

### 1. Clone repo
```bash
git clone https://github.com/yourusername/meal-tracker.git
cd meal-tracker
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run meal_tracker.py
```

## 🧑 Author
**Malhar Jojare**  
🔗 [LinkedIn](https://linkedin.com/malharjojare) | [GitHub](https://github.com/MalharJojare)

