import os
import io
import random
from math import pow
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go

USE_LLM = bool(os.getenv("OPENAI_API_KEY"))
if USE_LLM:
    try:
        from langchain import PromptTemplate, LLMChain
        from langchain_openai import ChatOpenAI
    except Exception:
        USE_LLM = False  

PDF_AVAILABLE = True
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except Exception:
    PDF_AVAILABLE = False

def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    height_m = height_cm / 100
    bmi = weight_kg / pow(height_m, 2)
    return round(bmi, 2)


def get_bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight"
    elif 18.5 <= bmi < 24.9:
        return "Normal weight"
    elif 25 <= bmi < 29.9:
        return "Overweight"
    else:
        return "Obese"


def ideal_weight_range(height_cm: float):
    h2 = pow(height_cm / 100, 2)
    return round(18.5 * h2, 1), round(24.9 * h2, 1)


def estimate_calories(weight, height, age, gender, activity_level):
    # Mifflin–St Jeor
    if gender == "Male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    activity_factors = {
        "Sedentary": 1.2,
        "Lightly Active": 1.375,
        "Moderately Active": 1.55,
        "Very Active": 1.725,
        "Super Active": 1.9,
    }
    return round(bmr * activity_factors[activity_level])


def daily_water_ml(weight_kg):
   
    return int(weight_kg * 35)

def rule_based_weekly_plan(bmi, category, goal, cuisine, workout_type, calories, water_ml):
    goal_note = {
        "Lose Weight": "Create ~350–500 kcal daily deficit; prioritize protein and veggies; 8–12k steps/day.",
        "Gain Weight": "Create ~250–400 kcal daily surplus; strength train; protein 1.6–2.2 g/kg.",
        "Maintain": "Keep calories near TDEE; balance cardio + strength; consistent sleep and hydration.",
    }[goal]

    base_cuisine = cuisine if cuisine != "Any" else "Balanced"
    gym_or_home = "home-friendly bodyweight & bands" if workout_type == "Home Workout" else "gym-based machines & free weights"

    days = []
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        if d in ["Mon", "Wed", "Fri"]:
            w_desc = f"Strength focus ({gym_or_home}): full-body compound (squat/lunge, push, pull, hinge), 3×8–12; finish with core."
        elif d in ["Tue", "Thu"]:
            w_desc = "Cardio + mobility: 25–35 min brisk walk/jog/cycle + 10 min mobility (hips/ankles/thoracic)."
        else:
            w_desc = "Active recovery: gentle yoga, long walk, light stretch (20–30 min)."

        if base_cuisine == "Indian":
            bf = "Veg omelette/poha/upma + fruit; optional curd."
            ln = "Dal/rajma + roti/brown rice + salad; paneer/chicken; sautéed veggies."
            dn = "Grilled fish/tofu/chicken + quinoa/millet + mixed sabzi."
        elif base_cuisine == "Mediterranean":
            bf = "Greek yogurt + oats + berries + nuts."
            ln = "Chickpea salad/whole-wheat pita + hummus + veggies + olive oil."
            dn = "Grilled fish/chicken/tofu + couscous/quinoa + salad."
        elif base_cuisine == "Vegan":
            bf = "Tofu scramble + whole-grain toast + fruit."
            ln = "Lentil/bean bowl + quinoa + greens + seeds."
            dn = "Stir-fry tofu/tempeh + brown rice + veggies."
        elif base_cuisine == "Keto":
            bf = "Eggs + avocado + sautéed spinach."
            ln = "Paneer/chicken salad with olive oil dressing."
            dn = "Grilled fish/meat/tofu + non-starchy veggies + nuts."
        else:
            bf = "Oats + milk/yogurt + fruit + nuts."
            ln = "Lean protein + whole grains + colorful salad."
            dn = "Protein + complex carbs + veggies."

        snack = "Nuts/fruit/curd/protein smoothie (adjust to goal)."
        if goal == "Lose Weight":
            ln += " (smaller carb portion)."
            dn += " (extra veggies, moderate carbs)."
        elif goal == "Gain Weight":
            ln += " (larger carb portion)."
            dn += " (add healthy fats like olive oil/nuts)."

        days.append(
            f"### {d}\n"
            f"**Workout:** {w_desc}\n"
            f"**Meals:**\n"
            f"- Breakfast: {bf}\n"
            f"- Lunch: {ln}\n"
            f"- Dinner: {dn}\n"
            f"- Snack: {snack}\n"
        )

    motivation = random.choice([
        "Small steps daily beat occasional big efforts.",
        "You don’t need perfect—just consistent.",
        "Strong body, clear mind—keep going!",
        "Fuel right, move smart, sleep well.",
        "Progress over perfection—always."
    ])

    explain = (
        "Plan leverages progressive strength for muscle/strength, cardio for heart health, and recovery to prevent fatigue. "
        "Balanced macronutrients support your goal, with hydration and fiber aiding performance and satiety."
    )

    return (
        f"## Personalized Weekly Plan (Rule-Based)\n\n"
        f"**BMI:** {bmi} ({category})  \n"
        f"**Goal:** {goal} | **Cuisine:** {cuisine} | **Workout:** {workout_type}  \n"
        f"**Calories target (est.):** {calories} kcal/day  \n"
        f"**Water target:** ~{water_ml} ml/day  \n\n"
        f"**Goal note:** {goal_note}\n\n" + "\n".join(days) +
        f"\n---\n**Motivation:** {motivation}\n\n**Why this works:** {explain}\n"
    )

def llm_weekly_plan(bmi, category, goal, cuisine, workout_type, calories, water_ml, prompt_style):
    if not USE_LLM:
        return None

    system_note = {
        "Coach": "Encouraging, practical, concise. Use bullets and short sections.",
        "Clinical": "Evidence-aware, neutral tone, precise phrasing. Avoid medical claims.",
        "Minimal": "Ultra-concise bullet points. No fluff.",
        "Vegetarian": "Prioritize vegetarian options; eggs optional; avoid meat/fish.",
    }[prompt_style]

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.7)

    template = """
You are an AI fitness coach. Style guideline: {system_note}

User metrics:
- BMI: {bmi} ({category})
- Goal: {goal}
- Cuisine: {cuisine}
- Workout: {workout_type}
- Estimated calories/day: {calories}
- Water target: {water_ml} ml/day

Return markdown with these sections:

1) 📅 Weekly Diet Plan (7 days): breakfast, lunch, dinner, snack.
   - Adapt to cuisine: {cuisine}
   - Align to goal: {goal}
   - Keep portions realistic for {calories} kcal/day

2) 🏋️ Weekly Workout Schedule (7 days):
   - Adapted for: {workout_type}
   - Include strength, cardio, mobility, and recovery suggestions
   - Provide sets/reps or time guidance

3) 💧 Hydration & Micronutrients:
   - Daily water reminder: {water_ml} ml
   - Electrolytes/fruit/veggies tips

4) 🧘 Mental Wellness:
   - 1–2 short, practical practices

5) 💡 Motivation:
   - One-line, punchy quote

6) 📖 Why this works:
   - 3–5 bullet points max, simple rationale
"""
    prompt = PromptTemplate(
        input_variables=[
            "system_note", "bmi", "category", "goal",
            "cuisine", "workout_type", "calories", "water_ml"
        ],
        template=template,
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(
        system_note=system_note,
        bmi=bmi, category=category, goal=goal,
        cuisine=cuisine, workout_type=workout_type,
        calories=calories, water_ml=water_ml
    )

def make_txt(plan_text: str, meta: dict) -> bytes:
    header = (
        f"AI Fitness Coach Plan\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Height: {meta['height']} cm  Weight: {meta['weight']} kg  Age: {meta['age']}\n"
        f"Gender: {meta['gender']}  Activity: {meta['activity']}\n\n"
    )
    return (header + plan_text).encode("utf-8")


def make_pdf(plan_text: str, meta: dict) -> bytes:
    if not PDF_AVAILABLE:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="AI Fitness Coach Plan")
    styles = getSampleStyleSheet()
    story = []

    hdr = (
        f"<b>AI Fitness Coach Plan</b><br/>"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Height: {meta['height']} cm &nbsp;&nbsp; Weight: {meta['weight']} kg &nbsp;&nbsp; Age: {meta['age']}<br/>"
        f"Gender: {meta['gender']} &nbsp;&nbsp; Activity: {meta['activity']}<br/><br/>"
    )
    story.append(Paragraph(hdr, styles["Normal"]))
    for block in plan_text.split("\n\n"):
        story.append(Paragraph(block.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 8))
    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes

st.set_page_config(page_title="AI Fitness Coach", page_icon="💪", layout="wide")
st.title("🤖 AI-Powered Fitness Coach")
st.caption("Enter your details to get BMI, calories, water target, and a full 7-day AI plan. Auto-falls back to a built-in plan if no API key is set.")
with st.sidebar:
    st.subheader("ℹ️ About")
    st.write(
        "- LLM mode: **{}**".format("ON ✅" if USE_LLM else "OFF (fallback) ⚠️")
    )
    st.write("Set `OPENAI_API_KEY` env var to enable LLM mode.")
    st.divider()
    st.subheader("📜 History")
    if "history" not in st.session_state:
        st.session_state.history = []
    if st.session_state.history:
        for i, h in enumerate(reversed(st.session_state.history[-10:]), 1):
            st.write(f"{len(st.session_state.history)- (i-1)}. {h['timestamp']} — BMI {h['bmi']} ({h['category']})")

col1, col2, col3 = st.columns(3)
with col1:
    height = st.number_input("📏 Height (cm)", min_value=100, max_value=250, step=1, value=170)
with col2:
    weight = st.number_input("⚖️ Weight (kg)", min_value=20, max_value=300, step=1, value=70)
with col3:
    age = st.number_input("🎂 Age", min_value=10, max_value=100, step=1, value=25)

row2c1, row2c2, row2c3 = st.columns(3)
with row2c1:
    gender = st.radio("👤 Gender", ["Male", "Female"], horizontal=True)
with row2c2:
    activity_level = st.selectbox("🏃 Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Super Active"])
with row2c3:
    goal = st.selectbox("🎯 Goal", ["Lose Weight", "Gain Weight", "Maintain"])

row3c1, row3c2, row3c3 = st.columns(3)
with row3c1:
    cuisine = st.selectbox("🍲 Preferred Cuisine", ["Any", "Indian", "Mediterranean", "Vegan", "Keto"])
with row3c2:
    workout_type = st.radio("🏋️ Workout Preference", ["Home Workout", "Gym Workout"], horizontal=True)
with row3c3:
    prompt_style = st.selectbox("🧰 Prompt Style (LLM)", ["Coach", "Clinical", "Minimal", "Vegetarian"])

go_btn = st.button("🚀 Analyze & Generate Plan")

if go_btn:
    if height <= 0 or weight <= 0:
        st.warning("Please enter valid height and weight.")
    else:
        bmi = calculate_bmi(height, weight)
        category = get_bmi_category(bmi)
        iw_min, iw_max = ideal_weight_range(height)
        calories = estimate_calories(weight, height, age, gender, activity_level)
        water = daily_water_ml(weight)
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=bmi,
            title={'text': "BMI"},
            gauge={'axis': {'range': [10, 40]},
                   'bar': {'color': "darkblue"},
                   'steps': [
                       {'range': [10, 18.5], 'color': "lightblue"},
                       {'range': [18.5, 24.9], 'color': "green"},
                       {'range': [25, 29.9], 'color': "orange"},
                       {'range': [30, 40], 'color': "red"}]}))
        st.plotly_chart(fig, use_container_width=True)

        colA, colB, colC = st.columns(3)
        with colA:
            st.metric("BMI", bmi, help="Body Mass Index")
            st.write(f"**Category:** {category}")
        with colB:
            st.metric("Daily Calories (est.)", f"{calories} kcal")
            st.write(f"**Water target:** ~{water} ml/day")
        with colC:
            st.metric("Ideal Weight Min", f"{iw_min} kg")
            st.metric("Ideal Weight Max", f"{iw_max} kg")

        with st.spinner("Generating your 7-day plan..."):
            plan = None
            if USE_LLM:
                try:
                    plan = llm_weekly_plan(bmi, category, goal, cuisine, workout_type, calories, water, prompt_style)
                except Exception as e:
                    st.info(f"LLM unavailable ({e}). Using built-in plan instead.")
                    plan = None
            if not plan:
                plan = rule_based_weekly_plan(bmi, category, goal, cuisine, workout_type, calories, water)

        st.divider()
        st.subheader("📅 Your Weekly Plan")
        st.markdown(plan)
        st.session_state.history.append({
            "timestamp": datetime.now().strftime("%d-%b %H:%M"),
            "bmi": bmi,
            "category": category,
            "plan": plan
        })
        meta = dict(height=height, weight=weight, age=age, gender=gender, activity=activity_level)
        txt_bytes = make_txt(plan, meta)
        st.download_button("⬇️ Download as TXT", data=txt_bytes, file_name="ai_fitness_plan.txt", mime="text/plain")

        if PDF_AVAILABLE:
            pdf_bytes = make_pdf(plan, meta)
            if pdf_bytes:
                st.download_button("⬇️ Download as PDF", data=pdf_bytes, file_name="ai_fitness_plan.pdf", mime="application/pdf")
        else:
            st.caption("PDF export requires `reportlab`. Install with `pip install reportlab`.")
st.caption("This app provides general wellness guidance and is not a substitute for professional medical advice.")
