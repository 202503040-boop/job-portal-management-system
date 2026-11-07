import streamlit as st
import psycopg2
import pandas as pd
import re
from datetime import date
from db_config import DB_SETTINGS

# Configure page layout
st.set_page_config(
    page_title="Job Portal Management System",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# DATABASE CONNECTION & SCHEMA SAFETY
# ---------------------------------------------------------
def get_connection():
    return psycopg2.connect(**DB_SETTINGS)

def get_pg_version():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            return cur.fetchone()[0]

def init_tables():
    """Ensure companion tables exist without altering pre-existing COMPANY schema."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS JOB (
                    job_id SERIAL PRIMARY KEY,
                    company_id INT REFERENCES COMPANY(company_id) ON DELETE CASCADE,
                    job_title VARCHAR(150) NOT NULL,
                    job_type VARCHAR(50) DEFAULT 'Full-time',
                    min_cgpa NUMERIC(4,2) DEFAULT 0.0,
                    location VARCHAR(100),
                    salary NUMERIC(12,2),
                    category VARCHAR(100),
                    deadline DATE,
                    status VARCHAR(20) DEFAULT 'Active'
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS APPLICATION (
                    application_id SERIAL PRIMARY KEY,
                    applicant_name VARCHAR(150) NOT NULL,
                    applicant_email VARCHAR(150) NOT NULL,
                    applicant_cgpa NUMERIC(4,2),
                    job_id INT REFERENCES JOB(job_id) ON DELETE CASCADE,
                    application_date DATE DEFAULT CURRENT_DATE,
                    status VARCHAR(50) DEFAULT 'Submitted'
                );
            """)
            conn.commit()

# Run initialization safely
try:
    init_tables()
except Exception as e:
    st.sidebar.warning(f"Note on initialization: {e}")

# Verification Banner
try:
    pg_ver = get_pg_version()
    st.sidebar.success(f"🟢 Connected to PostgreSQL\nEngine: {pg_ver.split(',')[0]}")
except Exception as e:
    st.sidebar.error(f"DB Error: {e}")
    st.stop()

# Helper for email format
def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

# ---------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.title("🌐 Job Portal Hub")
st.sidebar.caption("Team 13 | MC212 DBMS Full SRS Architecture")

view_mode = st.sidebar.radio(
    "Choose View / Module",
    [
        "🔍 Job Search & Discovery (Candidate)",
        "📄 Application Status Tracker (Candidate)",
        "💼 Post & Manage Jobs (Recruiter)",
        "📥 Review Inbound Applications (Recruiter)",
        "🏢 Company Administration (CRUD Core)"
    ]
)

# ==============================================================================
# MODULE 1: CANDIDATE SEARCH & APPLY (SRS REQ-08, REQ-01)
# ==============================================================================
if view_mode == "🔍 Job Search & Discovery (Candidate)":
    st.title("🎯 Browse & Apply for Openings")
    st.caption("Search across live job vacancies posted by registered employers.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        kw = st.text_input("Search Title or Category", placeholder="e.g. Software, Finance, Design")
    with col2:
        loc = st.text_input("Location", placeholder="e.g. Gandhinagar, Remote, Mumbai")
    with col3:
        min_sal = st.number_input("Minimum Salary (₹)", min_value=0, step=25000, value=0)

    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT j.job_id, j.job_title, c.company_name, j.category, j.location, j.job_type, j.salary, j.min_cgpa, j.deadline
                FROM JOB j
                JOIN COMPANY c ON j.company_id = c.company_id
                WHERE j.status = 'Active'
                  AND (j.job_title ILIKE %s OR j.category ILIKE %s)
                  AND j.location ILIKE %s
                  AND j.salary >= %s
                ORDER BY j.job_id DESC;
            """
            cur.execute(query, (f"%{kw}%", f"%{kw}%", f"%{loc}%", min_sal))
            jobs = cur.fetchall()

    if jobs:
        for j in jobs:
            with st.container():
                st.markdown(f"### {j[1]} — **{j[2]}**")
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"📍 **Location:** {j[4]}")
                c2.write(f"💼 **Type:** {j[5]}")
                c3.write(f"💰 **Salary:** ₹{j[6]:,.0f}" if j[6] else "💰 **Salary:** Disclosed on request")
                c4.write(f"🎯 **Min CGPA:** {j[7]}")
                st.caption(f"Domain: {j[3]} | Deadline: {j[8]}")

                with st.expander(f"Apply for {j[1]}"):
                    with st.form(f"apply_form_{j[0]}"):
                        a_name = st.text_input("Your Full Name")
                        a_email = st.text_input("Your Email Address")
                        a_cgpa = st.number_input("Your Current CGPA", min_value=0.0, max_value=10.0, step=0.01, value=7.5)
                        if st.form_submit_button("Submit Application"):
                            if not a_name or not a_email:
                                st.error("Please fill in your name and email.")
                            elif not validate_email(a_email):
                                st.error("Please provide a valid email format.")
                            elif j[7] and a_cgpa < float(j[7]):
                                st.error(f"Eligibility constraint: This job requires a minimum CGPA of {j[7]}.")
                            else:
                                try:
                                    with get_connection() as c_conn:
                                        with c_conn.cursor() as c_cur:
                                            c_cur.execute("""
                                                SELECT column_name 
                                                FROM information_schema.columns 
                                                WHERE table_name = 'application';
                                            """)
                                            cols_in_db = [r[0] for r in c_cur.fetchall()]

                                            if 'applicant_email' in cols_in_db:
                                                c_cur.execute("SELECT application_id FROM APPLICATION WHERE applicant_email = %s AND job_id = %s;", (a_email, j[0]))
                                                if c_cur.fetchone():
                                                    st.warning("⚠️ REQ-03 Single Application Rule: You have already applied for this opening.")
                                                else:
                                                    c_cur.execute("""
                                                        INSERT INTO APPLICATION (applicant_name, applicant_email, applicant_cgpa, job_id, application_date, status)
                                                        VALUES (%s, %s, %s, %s, CURRENT_DATE, 'Submitted');
                                                    """, (a_name, a_email, a_cgpa, j[0]))
                                                    c_conn.commit()
                                                    st.success("🎉 Application successfully submitted! Track it in the Status Tracker.")
                                            else:
                                                c_cur.execute("""
                                                    INSERT INTO APPLICATION (job_id, application_date, status)
                                                    VALUES (%s, CURRENT_DATE, 'Submitted');
                                                """, (j[0],))
                                                c_conn.commit()
                                                st.success("🎉 Application recorded successfully!")
                                except Exception as err:
                                    st.error(f"Error submitting application: {err}")
                st.markdown("---")
    else:
        st.info("No active job postings match your search filters. Post one from the Recruiter section!")

# ==============================================================================
# MODULE 2: APPLICATION STATUS TRACKER (CANDIDATE)
# ==============================================================================
elif view_mode == "📄 Application Status Tracker (Candidate)":
    st.title("📊 Live Application Lifecycle Tracker")
    st.caption("Real-time candidate view of application progress through recruitment stages.")

    search_term = st.text_input("Filter applications by keyword, candidate name, or status:", placeholder="e.g. Under Review, Submitted, Rahul")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'application'
                    );
                """)
                table_exists = cur.fetchone()[0]

                if not table_exists:
                    st.warning("The 'APPLICATION' table has not been created yet.")
                else:
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'application';
                    """)
                    app_cols = [r[0] for r in cur.fetchall()]

                    cur.execute("SELECT * FROM APPLICATION ORDER BY 1 DESC;")
                    raw_data = cur.fetchall()

                    if raw_data:
                        df_app = pd.DataFrame(raw_data, columns=app_cols)
                        if search_term:
                            mask = df_app.astype(str).apply(lambda row: row.str.contains(search_term, case=False).any(), axis=1)
                            df_app = df_app[mask]
                        st.dataframe(df_app, use_container_width=True)
                        st.info(f"Total matching application records: {len(df_app)}")
                    else:
                        st.info("No applications found in the database.")
    except Exception as e:
        st.error(f"Error loading Application Tracker: {e}")

# ==============================================================================
# MODULE 3: RECRUITER JOB POSTING (SRS REQ-04)
# ==============================================================================
elif view_mode == "💼 Post & Manage Jobs (Recruiter)":
    st.title("💼 Recruiter Job Requisition Desk")
    tabs = st.tabs(["📢 Publish New Job Opening", "📋 View & Close Postings"])

    with tabs[0]:
        st.subheader("Create a Structured Job Requisition")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT company_id, company_name FROM COMPANY ORDER BY company_id ASC;")
                comps = cur.fetchall()

        if comps:
            c_dict = {f"#{c[0]} - {c[1]}": c[0] for c in comps}
            with st.form("new_job_post"):
                col_a, col_b = st.columns(2)
                with col_a:
                    selected_comp = st.selectbox("Hiring Organization", list(c_dict.keys()))
                    j_title = st.text_input("Job Title", placeholder="e.g. Backend Software Engineer")
                    category = st.selectbox("Job Category", ["Engineering", "Data Science", "Product", "Design", "Consulting", "Other"])
                    salary = st.number_input("Annual Package (₹)", min_value=50000, step=25000, value=650000)
                with col_b:
                    location = st.text_input("Job Location / Mode", placeholder="e.g. Gandhinagar / Hybrid")
                    j_type = st.selectbox("Employment Contract", ["Full-time", "Part-time", "Contract", "Internship"])
                    min_cgpa = st.number_input("Minimum Eligibility CGPA", min_value=0.0, max_value=10.0, step=0.1, value=6.5)
                    deadline = st.date_input("Application Deadline", min_value=date.today())

                if st.form_submit_button("Publish Job Opening"):
                    if not j_title or not location:
                        st.error("Title and Location cannot be empty.")
                    else:
                        try:
                            with get_connection() as c_conn:
                                with c_conn.cursor() as c_cur:
                                    c_cur.execute("""
                                        INSERT INTO JOB (company_id, job_title, job_type, min_cgpa, location, salary, category, deadline, status)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Active');
                                    """, (c_dict[selected_comp], j_title, j_type, min_cgpa, location, salary, category, deadline))
                                    c_conn.commit()
                            st.success(f"Job opening '{j_title}' published successfully! (1 row inserted)")
                        except Exception as err:
                            st.error(f"Error publishing job: {err}")
        else:
            st.warning("No companies registered yet.")

    with tabs[1]:
        st.subheader("Active Job Requisitions")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT j.job_id, j.job_title, c.company_name, j.category, j.location, j.salary, j.status
                    FROM JOB j
                    JOIN COMPANY c ON j.company_id = c.company_id
                    ORDER BY j.job_id DESC;
                """)
                job_list = cur.fetchall()
                job_cols = [desc[0] for desc in cur.description]
        if job_list:
            st.dataframe(pd.DataFrame(job_list, columns=job_cols), use_container_width=True)
        else:
            st.info("No job openings currently in the system.")

# ==============================================================================
# MODULE 4: RECRUITER INBOUND PIPELINE & REVIEW
# ==============================================================================
elif view_mode == "📥 Review Inbound Applications (Recruiter)":
    st.title("📥 Candidate Evaluation & Stage Transition")
    st.caption("Manage stages: Submitted ➔ Under Review ➔ Shortlisted ➔ Selected / Rejected")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'application'
                    );
                """)
                if not cur.fetchone()[0]:
                    st.info("No application records found yet.")
                else:
                    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'application';")
                    cols = [r[0] for r in cur.fetchall()]

                    cur.execute("SELECT * FROM APPLICATION ORDER BY 1 DESC;")
                    all_apps = cur.fetchall()

                    if all_apps:
                        stages = ["Submitted", "Under Review", "Shortlisted", "Selected", "Rejected"]
                        for idx, row in enumerate(all_apps):
                            row_dict = dict(zip(cols, row))
                            app_pk = row[0]
                            current_status = str(row_dict.get('status', 'Submitted'))
                            default_index = stages.index(current_status) if current_status in stages else 0

                            with st.expander(f"Application Record #{app_pk} | Current Stage: {current_status}"):
                                c1, c2 = st.columns([2, 1])
                                with c1:
                                    for col_name, val in row_dict.items():
                                        if col_name != 'status':
                                            st.write(f"**{col_name.replace('_', ' ').title()}:** {val}")

                                with c2:
                                    new_stage = st.selectbox(
                                        "Change Stage", 
                                        stages, 
                                        index=default_index, 
                                        key=f"stage_box_{app_pk}_{idx}"
                                    )
                                    if st.button("Update Stage", key=f"btn_upd_{app_pk}_{idx}"):
                                        with get_connection() as update_conn:
                                            with update_conn.cursor() as update_cur:
                                                update_cur.execute(
                                                    f"UPDATE APPLICATION SET status = %s WHERE {cols[0]} = %s;",
                                                    (new_stage, app_pk)
                                                )
                                                update_conn.commit()
                                        st.success(f"Status updated to '{new_stage}'! (1 row updated)")
                    else:
                        st.info("No inbound applications received yet.")
    except Exception as e:
        st.error(f"Error loading Applications Review: {e}")

# ==============================================================================
# MODULE 5: COMPANY ADMINISTRATION (LAB 11 CORE CRUD)
# ==============================================================================
elif view_mode == "🏢 Company Administration (CRUD Core)":
    st.title("🏢 Company / Employer Master Records")
    st.caption("Full Parameterized CRUD operations on the COMPANY anchor relation.")

    tabs = st.tabs(["📋 View & Search Companies", "➕ Register Company", "✏️ Edit Company", "🗑️ Delete Company"])

    INDUSTRIES = ["Technology", "Finance", "Healthcare", "Education", "Manufacturing", "E-commerce", "Consulting", "Other"]

    # 1. READ (SELECT)
    with tabs[0]:
        st.subheader("Registered Companies")
        q = st.text_input("Search Company by Name, City, or Industry", placeholder="Type keywords...")
        with get_connection() as conn:
            with conn.cursor() as cur:
                if q:
                    cur.execute("""
                        SELECT company_id, company_name, industry, email, phone_no, city
                        FROM COMPANY
                        WHERE company_name ILIKE %s OR city ILIKE %s OR industry ILIKE %s
                        ORDER BY company_id ASC;
                    """, (f"%{q}%", f"%{q}%", f"%{q}%"))
                else:
                    cur.execute("SELECT company_id, company_name, industry, email, phone_no, city FROM COMPANY ORDER BY company_id ASC;")
                c_data = cur.fetchall()
                c_cols = [desc[0] for desc in cur.description]
        st.dataframe(pd.DataFrame(c_data, columns=c_cols), use_container_width=True)
        st.info(f"Total Companies Loaded: {len(c_data)}")

    # 2. CREATE (INSERT)
    with tabs[1]:
        st.subheader("Register New Employer")
        with st.form("add_comp_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                cid = st.number_input("Company ID (PK)", min_value=1, step=1, value=105)
                cname = st.text_input("Company Name", value="Google India")
                ind = st.selectbox("Industry Domain", INDUSTRIES, index=0)
            with c2:
                cemail = st.text_input("Corporate Email", value="contact@google.com")
                cphone = st.text_input("Contact Phone Number (10 digits)", value="9876543210")
                ccity = st.text_input("Headquarters City", value="Bengaluru")

            submitted = st.form_submit_button("Submit Registration")
            if submitted:
                if not cname or not cemail or not cphone or not ccity:
                    st.warning("All fields are mandatory.")
                elif not validate_email(cemail):
                    st.error("Please enter a valid email address.")
                else:
                    try:
                        with get_connection() as c_conn:
                            with c_conn.cursor() as c_cur:
                                c_cur.execute("""
                                    INSERT INTO COMPANY (company_id, company_name, industry, email, phone_no, city)
                                    VALUES (%s, %s, %s, %s, %s, %s);
                                """, (cid, cname, ind, cemail, cphone, ccity))
                                c_conn.commit()
                                rows_affected = c_cur.rowcount
                        # PERSISTENT GREEN ALERT FOR SCREENSHOT
                        st.success(f"✅ Company '{cname}' created successfully! (Rows affected: {rows_affected})")
                        st.toast(f"Company '{cname}' created successfully!", icon="✅")
                    except Exception as err:
                        st.error(f"Database Error: {err}")

    # 3. UPDATE
    with tabs[2]:
        st.subheader("Update Company Information")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT company_id, company_name, industry, email, phone_no, city FROM COMPANY ORDER BY company_id ASC;")
                all_c = cur.fetchall()

        if all_c:
            c_picker = {f"#{r[0]} - {r[1]}": r for r in all_c}
            chosen_c = st.selectbox("Select Company to Modify", list(c_picker.keys()))
            c_row = c_picker[chosen_c]

            with st.form("upd_comp_form"):
                u1, u2 = st.columns(2)
                with u1:
                    new_n = st.text_input("Company Name", value=c_row[1])
                    ind_idx = INDUSTRIES.index(c_row[2]) if c_row[2] in INDUSTRIES else len(INDUSTRIES)-1
                    new_i = st.selectbox("Industry Domain", INDUSTRIES, index=ind_idx)
                with u2:
                    new_e = st.text_input("Corporate Email", value=c_row[3])
                    new_p = st.text_input("Phone Number", value=c_row[4])
                    new_c = st.text_input("Headquarters City", value=c_row[5])

                upd_submitted = st.form_submit_button("Save Changes")
                if upd_submitted:
                    try:
                        with get_connection() as c_conn:
                            with c_conn.cursor() as c_cur:
                                c_cur.execute("""
                                    UPDATE COMPANY SET company_name = %s, industry = %s, email = %s, phone_no = %s, city = %s
                                    WHERE company_id = %s;
                                """, (new_n, new_i, new_e, new_p, new_c, c_row[0]))
                                c_conn.commit()
                                rows_affected = c_cur.rowcount
                        # PERSISTENT GREEN ALERT FOR SCREENSHOT
                        st.success(f"✅ Company #{c_row[0]} updated successfully! (Rows affected: {rows_affected})")
                        st.toast(f"Company #{c_row[0]} updated successfully!", icon="✅")
                    except Exception as err:
                        st.error(f"Database Error: {err}")
        else:
            st.info("No companies found.")

    # 4. DELETE
    with tabs[3]:
        st.subheader("Delete Company Record")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT company_id, company_name FROM COMPANY ORDER BY company_id ASC;")
                del_c = cur.fetchall()

        if del_c:
            d_picker = {f"#{r[0]} - {r[1]}": r[0] for r in del_c}
            to_delete = st.selectbox("Select Company to Remove", list(d_picker.keys()))
            confirm = st.checkbox("Confirm permanent deletion of this company and its associated postings.")
            
            if st.button("Delete Company", type="primary"):
                if confirm:
                    try:
                        with get_connection() as c_conn:
                            with c_conn.cursor() as c_cur:
                                c_cur.execute("DELETE FROM COMPANY WHERE company_id = %s;", (d_picker[to_delete],))
                                c_conn.commit()
                                rows_affected = c_cur.rowcount
                        # PERSISTENT ALERT FOR SCREENSHOT
                        st.warning(f"🗑️ Company #{d_picker[to_delete]} deleted successfully. (Rows affected: {rows_affected})")
                        st.toast(f"Company #{d_picker[to_delete]} deleted successfully.", icon="🗑️")
                    except Exception as err:
                        st.error(f"Integrity Error: {err}")
                else:
                    st.error("Please tick the confirmation checkbox.")
        else:
            st.info("No companies to delete.")