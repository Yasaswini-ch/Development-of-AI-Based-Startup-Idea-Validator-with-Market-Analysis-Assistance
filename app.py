import streamlit as st


st.set_page_config(
    page_title="AI Startup Idea Validator",
    page_icon="AI",
    layout="wide",
)

st.title("AI Based Startup Idea Validator")
st.caption("Market Analysis Assistance")

st.write(
    "This is the first deployed version of the project. "
    "Use this page to collect a startup idea and show an initial validation result."
)

with st.form("idea_form"):
    idea = st.text_area("Startup idea", placeholder="Example: An AI tool that validates business ideas using market data")
    target_customer = st.text_input("Target customer", placeholder="Example: early-stage founders")
    problem = st.text_area("Problem being solved", placeholder="What painful problem does this startup solve?")
    submitted = st.form_submit_button("Validate idea")

if submitted:
    if not idea.strip():
        st.warning("Please enter a startup idea before validating.")
    else:
        st.subheader("Initial Validation")
        st.success("The idea has been captured successfully.")

        col1, col2, col3 = st.columns(3)
        col1.metric("Problem Clarity", "Good")
        col2.metric("Market Potential", "To Analyze")
        col3.metric("Competition", "To Research")

        st.write("**Idea:**", idea)
        if target_customer:
            st.write("**Target customer:**", target_customer)
        if problem:
            st.write("**Problem:**", problem)

        st.info(
            "Next development step: connect AI and market-analysis APIs to generate "
            "scores, competitor insights, and recommendations."
        )

