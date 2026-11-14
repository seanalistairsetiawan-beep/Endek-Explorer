import re
from io import StringIO

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh


# ============================================================
# 1. PAGE SETTINGS AND GOOGLE SHEETS CONNECTION
# ============================================================

st.set_page_config(
    page_title="ENDEK EXPLORER",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPREADSHEET_ID = "1V-jUCTVuCh1KfhrrbeHKWmadxRUl7rc1PpdZ9TAe9co"
SHEET_GID = "799504308"
REFRESH_SECONDS = 60

SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/"
    f"{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"
)

STANDARD_COLUMNS = [
    "Prior awareness",
    "Seen or worn at school events",
    "Familiarity score",
    "Interest score",
    "Preferred learning method",
    "Believes learning supports unity",
]


# ============================================================
# 2. DESIGN
# ============================================================

NAVY = "#243B50"
CREAM = "#F2E9D8"
TERRA = "#B96F50"
GOLD = "#C5A05B"
TEAL = "#2A8C82"
WHITE = "#FFFFFF"

# Muted page colours keep the interface calm while making sections easier to recognise.
PAGE_BACKGROUNDS = {
    "Home": "#F2E9D8",
    "One Community Issue": "#F3E8DC",
    "Research and Evidence": "#EAF0F3",
    "School Data": "#EAF1E8",
    "Citizenship Connection": "#E8F0F3",
    "Computational Thinking Solution": "#EFEDF4",
    "Technology Solution": "#E9EFF4",
    "Universal Values": "#EDF1E8",
    "Action Plan": "#F3ECE2",
    "Reflection and Conclusion": "#F0EBE5",
    "Ask the Endek Guide": "#F3EEE5",
    "Endek Heritage Game": "#E8F0ED",
    "References": "#EEF0F1",
}

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {CREAM};
    }}
    [data-testid="stSidebar"] {{
        background-color: {NAVY};
    }}
    [data-testid="stSidebar"] * {{
        color: white;
    }}
    h1, h2, h3 {{
        color: {NAVY};
    }}
    .hero {{
        background: linear-gradient(120deg, {NAVY}, {TEAL});
        padding: 35px;
        border-radius: 18px;
        color: white;
        margin-bottom: 25px;
    }}
    .hero h1 {{
        color: white;
        font-size: 42px;
    }}
    .hero p {{
        color: white;
        font-size: 17px;
    }}
    .footer {{
        text-align: center;
        color: {NAVY};
        padding: 20px 0 10px 0;
        font-size: 13px;
        opacity: 0.8;
    }}
    div[data-testid="stMetric"] {{
        background: rgba(255,255,255,0.65);
        padding: 15px;
        border-radius: 12px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. LIVE GOOGLE SHEETS DATA
# ============================================================

@st.cache_data(ttl=25)
def download_sheet():
    """Download the selected Google Sheets tab as CSV."""
    response = requests.get(
        SHEET_URL,
        timeout=25,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    text_start = response.text[:300].lower()

    if "text/html" in content_type or "<html" in text_start:
        raise ValueError(
            "Google returned a webpage instead of CSV data. "
            "Check that the spreadsheet is shared as "
            "'Anyone with the link – Viewer' and that the tab GID is correct."
        )

    raw = pd.read_csv(StringIO(response.content.decode("utf-8-sig")))

    if raw.empty and len(raw.columns) == 0:
        raise ValueError("The selected Google Sheets tab appears to be empty.")

    return raw


def normalise(value):
    """Lowercase text and remove punctuation for reliable comparison."""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def find_column(columns, aliases):
    """
    Match a real Google Forms heading to one standard survey field.
    Exact heading aliases are tried first, then distinctive phrases,
    then a conservative token match.
    """
    pairs = [(column, normalise(column)) for column in columns]

    # 1. Exact normalised matches.
    for alias in aliases:
        target = normalise(alias)
        for original, cleaned in pairs:
            if target and cleaned == target:
                return original

    # 2. Full phrase contained in the heading.
    for alias in aliases:
        target = normalise(alias)
        if len(target) < 5:
            continue
        for original, cleaned in pairs:
            if target and target in cleaned:
                return original

    # 3. Match all words from a sufficiently distinctive alias.
    for alias in aliases:
        words = normalise(alias).split()
        if len(words) < 2:
            continue
        for original, cleaned in pairs:
            if all(word in cleaned.split() for word in words):
                return original

    return None


def numeric_score(series):
    """Read a 1–5 score, including answers such as '4 - Interested'."""
    extracted = series.astype(str).str.extract(r"^\s*([1-5])(?:\D|$)")[0]
    return pd.to_numeric(extracted, errors="coerce")


def clean_answer_series(series):
    """Remove blank and spreadsheet NaN-like answers."""
    cleaned = series.astype("string").str.strip()
    return cleaned[cleaned.notna() & (cleaned != "") & (cleaned.str.lower() != "nan")]


def prepare_survey(raw):
    """Convert Google Forms headings into consistent app column names."""
    raw = raw.dropna(axis=1, how="all").copy()

    # Remove timestamp from the analysis and displayed response table.
    timestamp_columns = [
        col for col in raw.columns
        if "timestamp" in normalise(col)
    ]
    raw = raw.drop(columns=timestamp_columns, errors="ignore")

    # These aliases include the wording of the current Google Form.
    mapping = {
        "Prior awareness": [
            "Before this questionnaire had you heard of Kain Endek Bali",
            "had you heard of kain endek bali",
            "heard of kain endek",
            "heard of endek",
            "prior awareness",
        ],
        "Seen or worn at school events": [
            "Have you ever worn or seen Endek worn during school cultural events or festivities",
            "seen or worn endek worn during school cultural events",
            "school cultural events or festivities",
            "seen endek at school",
            "school events",
        ],
        "Familiarity score": [
            "How familiar are you with the cultural meaning and purpose of Kain Endek Bali",
            "cultural meaning and purpose of kain endek bali",
            "how familiar",
            "familiarity",
        ],
        "Interest score": [
            "How interested are you in learning more about Kain Endek Bali",
            "interested in learning more about kain endek bali",
            "how interested",
            "interest score",
        ],
        "Preferred learning method": [
            "Which learning method would help you understand Kain Endek Bali best",
            "learning method would help you understand kain endek bali",
            "preferred learning method",
            "learning method",
        ],
        "Believes learning supports unity": [
            "Do you believe understanding traditional crafts like Endek helps strengthen unity and respect within our school community",
            "understanding traditional crafts like endek helps strengthen unity",
            "strengthen unity and respect within our school community",
            "respect within our school community",
            "unity belief",
        ],
    }

    selected = {}
    missing = []

    for standard_name, aliases in mapping.items():
        original_name = find_column(raw.columns, aliases)
        if original_name is None:
            missing.append(standard_name)
        else:
            selected[standard_name] = original_name

    if missing:
        headings = "\n".join(f"• {col}" for col in raw.columns)
        raise ValueError(
            "The app could not match these survey question(s): "
            + ", ".join(missing)
            + "\n\nHeadings received from Google Sheets:\n"
            + headings
        )

    df = pd.DataFrame({
        standard_name: raw[original_name]
        for standard_name, original_name in selected.items()
    })

    # Remove rows where all six answers are empty.
    df = df.dropna(how="all").reset_index(drop=True)

    # Anonymous labels only; no names, emails, or timestamps are displayed.
    df.insert(0, "Respondent", [f"R{i:02d}" for i in range(1, len(df) + 1)])

    df["Familiarity score"] = numeric_score(df["Familiarity score"])
    df["Interest score"] = numeric_score(df["Interest score"])

    return df


def load_survey():
    return prepare_survey(download_sheet())


# Refresh the page periodically so new form responses can appear.
st_autorefresh(
    interval=REFRESH_SECONDS * 1000,
    key="survey_refresh",
)

try:
    df = load_survey()
    data_error = None
except Exception as error:
    df = pd.DataFrame(columns=["Respondent"] + STANDARD_COLUMNS)
    data_error = str(error)


# ============================================================
# 4. DATA CALCULATIONS
# ============================================================

def response_counts(column):
    if df.empty:
        return pd.Series(dtype="int64")
    return clean_answer_series(df[column]).value_counts()


total_responses = len(df) if data_error is None else 0

familiarity_values = (
    df["Familiarity score"].dropna()
    if data_error is None else pd.Series(dtype="float64")
)
interest_values = (
    df["Interest score"].dropna()
    if data_error is None else pd.Series(dtype="float64")
)

familiarity_mean = familiarity_values.mean() if not familiarity_values.empty else None
interest_mean = interest_values.mean() if not interest_values.empty else None
familiarity_n = len(familiarity_values)
interest_n = len(interest_values)

if data_error is None:
    awareness_counts = response_counts("Prior awareness")
    event_counts = response_counts("Seen or worn at school events")
    method_counts = response_counts("Preferred learning method")
    unity_counts = response_counts("Believes learning supports unity")
else:
    awareness_counts = pd.Series(dtype="int64")
    event_counts = pd.Series(dtype="int64")
    method_counts = pd.Series(dtype="int64")
    unity_counts = pd.Series(dtype="int64")

method_valid_n = int(method_counts.sum())
if method_valid_n:
    most_popular_method = str(method_counts.index[0])
    most_popular_method_count = int(method_counts.iloc[0])
else:
    most_popular_method = "No valid answers yet"
    most_popular_method_count = 0

awareness_yes = int(awareness_counts.get("Yes", 0))
demonstration_count = int(
    method_counts.get("Traditional clothing or fabric demonstration", 0)
)


# ============================================================
# 5. REFERENCES
# ============================================================

sources = [
    (
        "Bali Provincial Government (30 May 2026)",
        "Concern about the future of young Endek weavers",
        "https://www.baliprov.go.id/web/putri-koster-krisis-penenun-muda-ancam-masa-depan-endek-bali/",
    ),
    (
        "Bali Provincial Government (1 September 2026)",
        "Gerakan Peduli Endek and support for local industries",
        "https://www.baliprov.go.id/web/asn-bali-didorong-jadi-penggerak-ikm-lewat-gerakan-peduli-endek/",
    ),
    (
        "Journal of Visual Art and Design (2024)",
        "Sustainable Endek weaving in Jinengdalem",
        "https://garuda.kemdiktisaintek.go.id/documents/detail/4738929",
    ),
    (
        "Segara Widya, ISI Denpasar (2024)",
        "Contemporary fashion design using Endek",
        "https://jurnal.isi-dps.ac.id/index.php/segarawidya/article/view/3048",
    ),
    (
        "Asian Art Museum",
        "Nobleman's ceremonial overwrap: kampuh Endek or saput Endek",
        "https://searchcollection.asianart.org/objects/21490/noblemans-ceremonial-overwrap-kampuh-endek-or-saput-endek",
    ),
    (
        "IDN Times (28 September 2026)",
        "Photograph of Kain Endek fabrics used on the Home page",
        "https://www.idntimes.com/travel/journal/kain-endek-menyimpan-cerita-02-hs754-d6k1sl",
    ),
    (
        "Directorate General of Intellectual Property",
        "Bali registers Endek and Songket as communal intellectual property",
        "https://dgip.go.id/index.php/artikel/detail-artikel-berita/bali-catatkan-kain-endek-dan-songket-sebagai-kekayaan-intelektual-komunal?kategori=ki-komunal",
    ),
    (
        "JDIH Secretariat General of the Indonesian House of Representatives (DPR RI)",
        "The 1945 Constitution of the Republic of Indonesia (Articles 28I and 32)",
        "https://jdih.dpr.go.id/index/uu1945",
    ),
]


def show_references():
    st.subheader("References")
    for publisher, description, link in sources:
        st.markdown(
            f"**{publisher}**  \n"
            f"{description}  \n"
            f"[Open source]({link})"
        )


# ============================================================
# 6. HELPER FUNCTIONS
# ============================================================

def require_data():
    """Show the connection error on data-dependent pages without stopping the app."""
    if data_error is not None:
        st.warning(
            "Live survey data is currently unavailable. "
            "This page needs the questionnaire connection to display results."
        )
        with st.expander("Technical details"):
            st.code(data_error)
        return False
    return True


def bar_chart(column, title, color=NAVY):
    counts = (
        clean_answer_series(df[column])
        .value_counts()
        .rename_axis("Response")
        .reset_index(name="Number of responses")
    )

    if counts.empty:
        st.info("No valid responses are available for this question.")
        return

    fig = px.bar(
        counts,
        x="Response",
        y="Number of responses",
        text="Number of responses",
        title=title,
        color_discrete_sequence=[color],
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=NAVY,
        title_font_color=NAVY,
    )
    st.plotly_chart(fig, use_container_width=True)


def score_chart(column, title):
    counts = (
        df[column]
        .dropna()
        .value_counts()
        .sort_index()
        .rename_axis("Score")
        .reset_index(name="Responses")
    )

    if counts.empty:
        st.info("No valid score responses are available.")
        return

    fig = px.bar(
        counts,
        x="Score",
        y="Responses",
        text="Responses",
        title=title,
        color_discrete_sequence=[TEAL],
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=NAVY,
    )
    st.plotly_chart(fig, use_container_width=True)


def show_footer():
    st.divider()
    st.markdown(
        """
        <div class="footer">
            ENDEK EXPLORER · Threads of Bali, Stories of Heritage<br>
            Created by <b>Sean Alistair Setiawan</b>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 7. NAVIGATION
# ============================================================

pages = [
    "Home",
    "One Community Issue",
    "Research and Evidence",
    "School Data",
    "Citizenship Connection",
    "Computational Thinking Solution",
    "Technology Solution",
    "Universal Values",
    "Action Plan",
    "Reflection and Conclusion",
    "Ask the Endek Guide",
    "Endek Heritage Game",
    "References",
]

st.sidebar.title("🧵 ENDEK EXPLORER")
st.sidebar.caption("Threads of Bali, Stories of Heritage.")
st.sidebar.markdown("---")

page = st.sidebar.radio("Explore the project", pages)

if st.session_state.get("_previous_page") != page:
    components.html(
        """<script>
        const parentWindow = window.parent;
        parentWindow.scrollTo({top: 0, left: 0, behavior: 'instant'});
        const mainArea = parentWindow.document.querySelector('[data-testid="stMain"]');
        if (mainArea) mainArea.scrollTo({top: 0, left: 0, behavior: 'instant'});
        const appView = parentWindow.document.querySelector('[data-testid="stAppViewContainer"]');
        if (appView) appView.scrollTo({top: 0, left: 0, behavior: 'instant'});
        </script>""",
        height=0,
    )
    st.session_state["_previous_page"] = page

st.markdown(
    f"<style>.stApp {{ background-color: {PAGE_BACKGROUNDS.get(page, CREAM)}; }}</style>",
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")
st.sidebar.caption("Live questionnaire connection")
st.sidebar.caption(f"Refreshes every {REFRESH_SECONDS} seconds")

if data_error is None:
    st.sidebar.success(f"{total_responses} responses loaded")
else:
    st.sidebar.error("Survey data could not be loaded")


# ============================================================
# 8. HOME
# ============================================================

if page == "Home":
    st.markdown(
        """
        <div class="hero">
            <h1>ENDEK EXPLORER 🧵</h1>
            <p>Threads of Bali, Stories of Heritage.</p>
            <p>
                Discover Kain Endek Bali, explore cultural research,
                understand my school questionnaire, and learn how
                cultural knowledge can strengthen unity in diversity.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("🎬 ENDEK EXPLORER TOUR")
    st.write(
        "Watch this short guided tour to discover the website, its research, "
        "interactive features, and the ideas behind the project."
    )
    components.html(
        """
        <div style="width:100%; max-width:100%;">
            <div style="position:relative; width:100%; padding-top:56.25%; overflow:hidden; border-radius:14px; background:#17212b;">
                <iframe
                    src="https://drive.google.com/file/d/1_9j0tV7S3Tqf2Sg4KcWZg3dFK3XmBT4T/preview"
                    title="ENDEK EXPLORER TOUR"
                    allow="autoplay; fullscreen; picture-in-picture"
                    allowfullscreen
                    webkitallowfullscreen
                    mozallowfullscreen
                    style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;"
                ></iframe>
            </div>
        </div>
        """,
        height=560,
        scrolling=False,
    )
    st.caption(
        "Use the fullscreen control in the video player for a larger viewing experience. "
        "If the video does not load, check that its Google Drive sharing setting is "
        "‘Anyone with the link — Viewer’."
    )

    st.image(
        "https://image.idn.media/post/20260928/shutterstock_2635975371-1_bcc40480-b110-4abb-8d95-538681310774.jpg",
        use_container_width=True,
        caption="Kain Endek Bali — photograph published by IDN Times. Image source: IDN Times, ‘Kain Endek: Makna Motif, Warna, dan Tradisi’ (28 September 2026).",
    )
    st.markdown(
        "[View the original image article](https://www.idntimes.com/travel/journal/kain-endek-menyimpan-cerita-02-hs754-d6k1sl)"
    )

    if data_error is None:
        a, b, c = st.columns(3)
        a.metric("Survey responses", total_responses)
        b.metric(
            "Average familiarity",
            f"{familiarity_mean:.2f}/5" if familiarity_mean is not None else "No data",
        )
        c.metric(
            "Average interest",
            f"{interest_mean:.2f}/5" if interest_mean is not None else "No data",
        )
        st.info(
            f"The questionnaire currently contains {total_responses} responses. "
            "Results describe the people who answered, not all students in Indonesia."
        )
    else:
        st.warning("The live survey data is unavailable, but you can still explore the other project pages.")
        with st.expander("Why are the statistics unavailable?"):
            st.code(data_error)

    st.subheader("Explore the project")
    st.write(
        "This website introduces Kain Endek Bali, explains a community issue, "
        "presents research, and shares findings from an anonymous student questionnaire."
    )
    st.subheader("Why does Endek matter?")
    st.write(
        "Kain Endek is part of Bali's textile heritage. Its continuation depends "
        "on cultural appreciation, knowledge, and the skills of textile artisans."
    )


# ============================================================
# 9. ONE COMMUNITY ISSUE
# ============================================================

elif page == "One Community Issue":
    st.title("One Community Issue")
    st.subheader("Kain Endek Bali")
    st.write(
        "Kain Endek is a traditional woven textile associated with Bali. "
        "It is part of the island's textile heritage and depends on the "
        "knowledge and skills of textile artisans."
    )
    st.subheader("The issue")
    st.write(
        "A documented concern is the future regeneration of Endek weavers. "
        "In May 2026, the Bali Provincial Government reported concern about "
        "fewer young people being interested in becoming Endek weavers."
    )
    st.write(
        "This does not mean Endek has disappeared or that every young person "
        "has lost interest. It means that the continuation of weaving skills deserves attention."
    )
    st.subheader("Why should schools care?")
    st.write(
        "Schools can help by introducing students and the wider community to "
        "traditional crafts, encouraging respectful learning, and sharing accurate cultural information."
    )
    show_references()


# ============================================================
# 10. RESEARCH AND EVIDENCE
# ============================================================

elif page == "Research and Evidence":
    st.title("Research and Evidence")
    st.write(
        "Published research and official information provide evidence about "
        "Endek weaving, its promotion, and its continuation."
    )
    st.subheader("Main findings from published sources")
    st.markdown(
        """
        - **Fact:** In May 2026, the Bali Provincial Government reported concern about fewer young people being interested in becoming Endek weavers.
        - **Fact:** The Bali Provincial Government has also promoted Endek and local small industries through public initiatives.
        - **Research finding:** A 2024 study discusses sustainable Endek weaving practices in Jinengdalem, Buleleng.
        - **Research finding:** Another 2024 study explores contemporary fashion designs using Endek.
        """
    )
    st.subheader("Facts and opinions are different")
    st.write(
        "A fact is a statement that can be checked using evidence. For example, the Bali Provincial Government published information about concerns over the future number of young Endek weavers in 2026. "
        "An opinion is a personal view. For example, saying that schools should teach more about Endek is a recommendation, not proof that every student wants the same lesson."
    )
    st.write(
        "My questionnaire is another source of evidence, but it only describes the people who answered it. Its results should not be treated as facts about every student in Bali or Indonesia."
    )
    st.subheader("Different viewpoints")
    st.markdown(
        """
        - **Weavers and artisans:** Their skills, working conditions, income, and opportunities to pass on knowledge are important when discussing the future of Endek.
        - **Students and young people:** They may need clear, interesting ways to learn about Endek and understand its cultural meaning. My questionnaire records the views of its respondents, not all young people.
        - **Schools and the wider community:** They can help introduce cultural heritage through lessons, demonstrations, and reliable information, while respecting the knowledge of artisans.
        """
    )
    st.caption("These are relevant stakeholder perspectives to consider; they are not presented as direct interview quotations from this project.")
    if require_data():
        st.subheader("Questionnaire evidence")
        st.write(
            f"My questionnaire currently contains {total_responses} responses. "
            "It provides a picture of what these respondents know and how they prefer to learn. "
            "It does not represent every student or young person in Bali."
        )
    show_references()


# ============================================================
# 11. SCHOOL DATA
# ============================================================

elif page == "School Data":
    st.title("My School's Findings")
    st.write("Results from the anonymous questionnaire.")

    if require_data():
        a, b, c, d = st.columns(4)
        a.metric("Responses", total_responses)
        b.metric(
            "Heard of Endek",
            f"{awareness_yes}/{int(awareness_counts.sum())}"
            if awareness_counts.sum() else "No data",
        )
        c.metric(
            "Average familiarity",
            f"{familiarity_mean:.2f}/5" if familiarity_mean is not None else "No data",
        )
        d.metric(
            "Average interest",
            f"{interest_mean:.2f}/5" if interest_mean is not None else "No data",
        )

        st.caption(
            f"Familiarity average uses {familiarity_n} valid answers; "
            f"interest average uses {interest_n} valid answers."
        )

        st.subheader("Awareness")
        bar_chart("Prior awareness", "Had you heard of Kain Endek before?")
        bar_chart(
            "Seen or worn at school events",
            "Have you seen or worn Endek at school events?",
            TERRA,
        )

        st.subheader("Familiarity and interest")
        score_chart("Familiarity score", "Familiarity score distribution")
        score_chart("Interest score", "Interest score distribution")

        st.subheader("Preferred learning method")
        bar_chart(
            "Preferred learning method",
            "Which learning method would help you understand Endek best?",
            TERRA,
        )

        st.subheader("Cultural unity")
        bar_chart(
            "Believes learning supports unity",
            "Does learning about traditional crafts support unity?",
        )

        st.subheader("Interpretation")
        if awareness_counts.sum():
            st.write(
                f"{awareness_yes} out of {int(awareness_counts.sum())} "
                "valid answers said they had heard of Endek before."
            )
        else:
            st.write("There are no valid awareness answers yet.")

        if method_valid_n:
            st.write(
                f"{demonstration_count} out of {method_valid_n} valid answers "
                "preferred a traditional clothing or fabric demonstration."
            )
        else:
            st.write("There are no valid learning-method answers yet.")

        st.subheader("Anonymous response table")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.download_button(
            "Download survey data (without timestamps)",
            df.to_csv(index=False).encode("utf-8"),
            "endek_survey.csv",
            "text/csv",
        )

        st.subheader("Limitations")
        st.markdown(
            """
            1. The sample is small and does not represent all students or young people in Indonesia.
            2. Responses are self-reported, so some answers may be rushed or may not fully reflect each person's knowledge.
            3. The questionnaire does not record grade levels, so younger and older students cannot be compared.
            """
        )


# ============================================================
# 12. CITIZENSHIP CONNECTION
# ============================================================

elif page == "Citizenship Connection":
    st.title("Citizenship Connection")
    st.subheader("Indonesia: Unity in Diversity")
    st.write(
        "Indonesia is an archipelagic country made up of thousands of islands and "
        "many cultural communities. Bhinneka Tunggal Ika means Unity in Diversity: "
        "people can maintain different regional traditions while sharing one national identity."
    )
    st.subheader("Explore Indonesia's Five Major Islands")
    st.write(
        "This map focuses on Indonesia only. Select or hover over the island markers "
        "to see their names, then read the island profiles below. Bali is marked because "
        "it is the cultural home of Kain Endek."
    )

    island_points = pd.DataFrame({
        "Island": ["Sumatra", "Java", "Kalimantan", "Sulawesi", "Papua"],
        "Latitude": [0.5, -7.3, 0.5, -1.5, -4.0],
        "Longitude": [101.0, 110.5, 114.0, 121.0, 138.0],
        "Description": [
            "Western Indonesia; Barisan Mountains, Lake Toba and important rainforest habitats.",
            "Indonesia's most populous island, with major cities, volcanoes and historic temples.",
            "The Indonesian part of Borneo, known for rainforests, rivers and Dayak communities.",
            "A distinctive K-shaped island with unusual wildlife and diverse cultures.",
            "Indonesia's part of New Guinea, known for high mountains and rich Indigenous diversity.",
        ],
    })
    bali_point = pd.DataFrame({
        "Place": ["Bali — Endek heritage"],
        "Latitude": [-8.40],
        "Longitude": [115.15],
        "Description": ["Bali is the cultural home highlighted for Kain Endek in this project."],
    })

    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        locations=["IDN"],
        z=[1],
        locationmode="ISO-3",
        colorscale=[[0, "#D7B56D"], [1, "#D7B56D"]],
        showscale=False,
        marker_line_color="#765B32",
        marker_line_width=1.1,
        name="Indonesia",
        hovertemplate="Indonesia<extra></extra>",
    ))
    fig.add_trace(go.Scattergeo(
        lon=island_points["Longitude"],
        lat=island_points["Latitude"],
        text=island_points["Island"],
        customdata=island_points[["Description"]],
        mode="markers+text",
        textposition=["top center", "bottom center", "top center", "top center", "top center"],
        marker=dict(size=8, color="#243B50", line=dict(width=1, color="#FFFFFF")),
        name="Five major islands",
        hovertemplate="<b>%{text}</b><br>%{customdata[0]}<extra></extra>",
    ))
    fig.add_trace(go.Scattergeo(
        lon=bali_point["Longitude"],
        lat=bali_point["Latitude"],
        text=["BALI · ENDEK"],
        mode="markers+text",
        textposition="bottom right",
        marker=dict(size=13, color="#B42318", symbol="star", line=dict(width=1.5, color="#FFFFFF")),
        name="Endek heritage location",
        hovertemplate="<b>Bali — Endek heritage</b><br>Traditional Kain Endek is associated with Bali.<extra></extra>",
    ))
    fig.update_geos(
        scope="asia",
        projection_type="mercator",
        fitbounds="locations",
        showland=False,
        showocean=True,
        oceancolor="#EAF3F7",
        showlakes=False,
        showcountries=False,
        showcoastlines=False,
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=610,
        margin=dict(l=0, r=0, t=15, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01),
        font=dict(color="#243B50"),
        dragmode="pan",
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": True, "displayModeBar": True, "doubleClick": "reset"},
    )
    st.caption(
        "Map guide: scroll to zoom, drag to pan, and use the map controls to reset the view. "
        "The map highlights Indonesia rather than displaying a world map. Island markers are "
        "approximate locations; the map is for learning, not legal boundary measurement."
    )

    st.markdown("### Island profiles")
    island_profiles = [
        (
            "Java",
            "Java is Indonesia's most populous island and an important centre of the country's "
            "political, economic and cultural life. More than half of Indonesia's population "
            "lives there, including people in major cities such as Jakarta, Surabaya and Bandung. "
            "A chain of volcanoes runs across the island, including Mount Bromo and Mount Merapi; "
            "volcanic ash helps create fertile soil in many areas. Java also has important "
            "historical sites, including Borobudur, a major Buddhist temple, and Prambanan, "
            "a large Hindu temple complex."
        ),
        (
            "Sumatra",
            "Sumatra is one of Indonesia's largest islands and lies in the western part of the "
            "archipelago, with the equator crossing its northern half. The Barisan Mountains "
            "run along much of its western side, and the island is known for Lake Toba, a vast "
            "lake formed in a volcanic caldera. Sumatra's tropical forests provide habitats for "
            "rare wildlife, including Sumatran tigers, elephants, rhinoceroses and orangutans. "
            "These forests face pressure from land clearing and plantation development, making "
            "forest protection important for both wildlife and local communities."
        ),
        (
            "Kalimantan (Indonesian Borneo)",
            "Kalimantan is the Indonesian region of Borneo, the world's third-largest island, "
            "which is shared by Indonesia, Malaysia and Brunei. Much of the region is covered "
            "by tropical rainforest and crossed by large rivers, including the Kapuas and "
            "Mahakam. Kalimantan is home to many Indigenous Dayak communities, whose cultures "
            "and languages are diverse, as well as important orangutan habitats. The region "
            "also contains natural resources such as timber and coal. Nusantara, Indonesia's "
            "planned new capital, is being developed in East Kalimantan."
        ),
        (
            "Sulawesi",
            "Sulawesi lies east of Kalimantan and has a distinctive shape with several long "
            "peninsulas that make it look roughly like the letter K. Its long separation from "
            "other land areas helped create unusual wildlife found nowhere else, including "
            "the babirusa, anoa and several kinds of tarsier. Sulawesi is also home to many "
            "different cultural communities. The Toraja people of South Sulawesi are known "
            "for distinctive funeral ceremonies and traditional houses, while Bunaken "
            "National Park in North Sulawesi is famous for its coral reefs and marine life."
        ),
        (
            "Papua (Indonesian New Guinea)",
            "Papua refers to the Indonesian part of New Guinea, the world's second-largest "
            "island; the eastern part belongs to Papua New Guinea. Indonesia's Papua region "
            "has dramatic landscapes, from coastal wetlands and tropical forests to the "
            "Maoke Mountains, where Puncak Jaya rises to nearly 4,900 metres. The region is "
            "home to many Indigenous peoples and a remarkable range of local languages and "
            "traditions. Offshore, the Raja Ampat islands are known internationally for their "
            "rich coral reefs and marine biodiversity."
        ),
    ]
    for island_name, island_description in island_profiles:
        with st.container(border=True):
            st.subheader(island_name)
            st.write(island_description)

    st.caption(
        "Background references: Statistics Indonesia (BPS), Indonesia Travel, WWF, and "
        "the Ministry of Foreign Affairs of Indonesia."
    )
    st.markdown(
        "Sources for further reading: "
        "[BPS — Area and number of islands by province (2025)](https://www.bps.go.id/en/statistics-table/3/VUZwV01tSlpPVlpsWlRKbmMxcFhhSGhEVjFoUFFUMDkjMw%3D%3D/total-area-and-number-of-islands-by-province--2023.html) · "
        "[Indonesia Travel — Five largest islands](https://www.indonesia.travel/id/id/travel-ideas/adventure/pulau-terbesar-di-indonesia) · "
        "[WWF — Borneo and Sumatra](https://www.worldwildlife.org/places/borneo-and-sumatra/)"
    )

    st.subheader("The Proclamation")
    st.write(
        "The Proclamation established Indonesia as an independent nation. Learning about "
        "regional traditions helps citizens appreciate the diversity within Indonesia."
    )
    st.subheader("Wawasan Nusantara")
    st.write(
        "Wawasan Nusantara views Indonesia as one united archipelagic nation. "
        "Learning about Endek can encourage respect for cultural traditions from other islands too."
    )

    st.divider()
    st.subheader("Connection to Pancasila")
    st.write(
        "The strongest connection is the third principle of Pancasila, *Persatuan Indonesia* (The Unity of Indonesia). "
        "Respecting Kain Endek helps us appreciate Bali's cultural identity as part of Indonesia's wider national diversity. "
        "It also connects to the second principle, *Kemanusiaan yang Adil dan Beradab*, because we should respect the dignity, knowledge, and work of the artisans who make it."
    )

    st.subheader("Connection to the 1945 Constitution (UUD 1945)")
    st.write(
        "Article 32(1) says that the state advances Indonesia's national culture amid world civilisation while guaranteeing the freedom of the community to preserve and develop its cultural values. "
        "Article 28I(3) states that cultural identities and the rights of traditional communities are respected in line with the development of the times and civilisation. "
        "These articles show why cultural heritage and the people who maintain it deserve respect."
    )

    st.subheader("Rights and responsibilities")
    st.markdown(
        """
        - **Rights:** People should be able to learn about Indonesia's cultural heritage. Artisans and cultural communities deserve respect for their identity, knowledge, and traditions.
        - **Responsibilities:** We should respect cultural practices, check information before sharing it, avoid stereotypes, protect people's privacy, and support responsible efforts to preserve heritage.
        """
    )

    st.subheader("Connection to school rules")
    st.write(
        "At school, I can apply these ideas by respecting classmates from different cultural backgrounds, listening without making fun of traditions, following rules for respectful behaviour, and using digital information responsibly. "
        "This helps make the school a safe place where different cultures are valued."
    )


# ============================================================
# 13. COMPUTATIONAL THINKING
# ============================================================

elif page == "Computational Thinking Solution":
    st.title("Computational Thinking Solution")
    st.write(
        "I used computational thinking to plan and develop ENDEK EXPLORER, with the "
        "website as the main part of my project. The educational video is a short "
        "introduction that directs viewers to the website for the fuller explanation, "
        "research, live questionnaire findings, and interactive activities."
    )

    st.subheader("1. Decomposition")
    st.write(
        "Decomposition means splitting a large task into smaller, manageable parts. "
        "I applied it by dividing the main website into clear sections instead of "
        "trying to build everything at once. First, I planned the pages: the community "
        "issue, research and evidence, school data, citizenship connection, computational "
        "thinking, technology, values, action plan, reflection, chatbot, game, and references. "
        "I then worked on the features separately, such as connecting Google Sheets, "
        "cleaning questionnaire responses, calculating results, creating charts, and "
        "building the Endek Guide and heritage game. This made the website easier to "
        "develop, test, and improve one part at a time."
    )

    st.subheader("2. Pattern recognition")
    st.write(
        "Pattern recognition means looking for repeated features or similarities in "
        "information. In this project, I used it mainly when examining the questionnaire "
        "responses. I compared repeated answer categories, such as prior awareness, "
        "familiarity scores, interest scores, and preferred learning methods, to identify "
        "which answers appeared most often and what the overall results suggested. "
        "The website uses Pandas to count repeated answers and calculate averages, then "
        "uses charts to make those patterns easier to see. I also looked for repeated "
        "website needs, such as clear navigation and regularly updated data, so I could "
        "use a consistent layout and data-display approach across the pages."
    )

    st.subheader("3. Abstraction")
    st.write(
        "Abstraction means focusing on the information needed to solve a problem and "
        "leaving out details that are not necessary. I applied it by keeping the website "
        "focused on the main issue: how students can learn about and appreciate Kain Endek "
        "Bali. For the questionnaire analysis, I used relevant answers such as awareness, "
        "familiarity, interest, learning preferences, and views about cultural unity. I "
        "left out timestamps and did not display names, email addresses, or other personal "
        "details because they were not needed to understand the results. I also selected "
        "reliable cultural information and explained the limits of the survey instead of "
        "including unsupported claims. This kept the website useful, clear, and respectful "
        "of respondent privacy."
    )

    st.subheader("4. Algorithm")
    st.write(
        "An algorithm is an ordered set of steps used to complete a task. I used an "
        "algorithm to organise how I developed the project, from collecting and analysing "
        "the questionnaire data to building and checking the website. The website was my "
        "main product, so most of the development steps focus on its pages, data connection, "
        "charts, and interactive features. I also planned, drafted, and briefly improved "
        "the educational video, which introduces Kain Endek and guides viewers to the website "
        "rather than explaining every section of the project. The flowchart below shows the "
        "order of these steps and the checks I made before publishing."
    )

    st.markdown("**Project-development algorithm flowchart**")

    project_flow = r"""digraph ProjectDevelopment {
        graph [rankdir=TB, bgcolor="transparent", pad="0.2", nodesep="0.28", ranksep="0.38", splines=ortho];
        node [fontname="Arial", fontsize=10, style="filled", color="#526779", penwidth=1.3, margin="0.13,0.09", fontcolor="#172B3A"];
        edge [fontname="Arial", fontsize=9, color="#526779", penwidth=1.2, arrowsize=0.75];

        start [label="START", shape=oval, fillcolor="#DCEFE5"];
        collect [label="1. Collect data\nGoogle Forms questionnaire", shape=parallelogram, fillcolor="#E8F1FA"];
        process [label="2. Process the data\nClean and organise responses", shape=box, fillcolor="#F1F4F7"];
        analyse [label="3. Analyse the data\nFind patterns, counts and averages", shape=box, fillcolor="#F1F4F7"];
        draftsite [label="4. Build rough website draft\nCreate pages and basic layout", shape=box, fillcolor="#F1F4F7"];
        sitecheck [label="Does the website work\nand show the information clearly?", shape=diamond, fillcolor="#FFF1CC"];
        improvesite [label="5. Improve first prototype\nFix layout, content and functions", shape=box, fillcolor="#F1F4F7"];
        planvideo [label="6. Plan the video\nChoose message and sequence", shape=box, fillcolor="#F1F4F7"];
        draftvideo [label="7. Draft the video\nCreate a short animation and brief narration", shape=box, fillcolor="#F1F4F7"];
        videocheck [label="Is the video clear, accurate\nand ready to share?", shape=diamond, fillcolor="#FFF1CC"];
        improvevideo [label="8. Improve the short video\nMake any needed timing, visual or wording edits", shape=box, fillcolor="#F1F4F7"];
        github [label="9. Upload website to GitHub\nStore and publish website files", shape=parallelogram, fillcolor="#E8F1FA"];
        publish [label="10. Publish the short video and website\nShare the video and website link", shape=parallelogram, fillcolor="#E8F1FA"];
        end [label="END", shape=oval, fillcolor="#DCEFE5"];

        start -> collect -> process -> analyse -> draftsite -> sitecheck;
        sitecheck -> planvideo [label="Yes"];
        sitecheck -> improvesite [label="No"];
        improvesite -> sitecheck [label="Check again"];
        planvideo -> draftvideo -> videocheck;
        videocheck -> github [label="Yes"];
        videocheck -> improvevideo [label="No"];
        improvevideo -> videocheck [label="Check again"];
        github -> publish -> end;
    }"""
    st.graphviz_chart(project_flow, use_container_width=True)
    st.markdown(
        "**Flowchart key:** Oval = start/end · Rectangle = process · "
        "Parallelogram = input/output or sharing step · Diamond = decision · Arrow = direction of work."
    )
    st.caption(
        "The decision diamonds show that I checked the website and video before moving on. "
        "If something needed improvement, I revised it and checked again."
    )


# ============================================================
# 14. TECHNOLOGY SOLUTION
# ============================================================

elif page == "Technology Solution":
    st.title("Technology Solution")
    st.write(
        "ENDEK EXPLORER is a browser-based educational application created "
        "using Python and Streamlit. It connects to a Google Sheet to display updated questionnaire results."
    )
    st.subheader("Main technologies")
    st.markdown(
        """
        - Python: programming language
        - Streamlit: interactive application
        - Pandas: organising and analysing survey data
        - Plotly: interactive charts
        - Google Sheets: storing questionnaire responses
        - Requests: retrieving spreadsheet data
        - Streamlit Community Cloud: publishing the app
        """
    )
    st.subheader("How the technology works")
    st.code(
        """VISITOR opens ENDEK EXPLORER
            ---> Streamlit displays the Home page and navigation
            ---> App connects to the Google Sheets response sheet
            ---> Requests retrieves the latest questionnaire data
            ---> Pandas cleans and organises the answers
            ---> App counts answers and calculates averages
            ---> Plotly turns the results into charts
            ---> Visitor explores the research, values, action plan and game
            ---> App refreshes the survey data periodically""",
        language="text",
    )
    st.caption(
        "In simple terms: Google Forms collects responses ---> Google Sheets stores them "
        "---> ENDEK EXPLORER processes them ---> visitors see updated results."
    )

    st.divider()
    st.subheader("Questionnaire evidence: preferred learning method")

    if require_data():
        valid_methods = clean_answer_series(df["Preferred learning method"])
        valid_n = len(valid_methods)
        st.metric("Valid answers for this question", f"n = {valid_n}")

        if valid_n:
            chart_data = (
                valid_methods.value_counts()
                .rename_axis("Learning method")
                .reset_index(name="Responses")
            )
            fig = px.pie(
                chart_data,
                names="Learning method",
                values="Responses",
                title="Preferred learning method",
                hole=0.35,
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font_color=NAVY,
            )
            st.plotly_chart(fig, use_container_width=True)

            top_method = str(chart_data.iloc[0]["Learning method"])
            top_count = int(chart_data.iloc[0]["Responses"])
            top_percentage = top_count / valid_n * 100

            st.subheader("Conclusion")
            st.write(
                f"The most selected learning method was **{top_method}**, "
                f"chosen by {top_count} out of {valid_n} valid respondents "
                f"({top_percentage:.1f}%). This suggests that this method may "
                "be a useful way to introduce students to Kain Endek. However, "
                "the results describe the respondents only."
            )

            st.subheader("Recommendation")
            st.write(
                f"Schools could consider organising an activity based on **{top_method.lower()}**. "
                "A short follow-up questionnaire could check whether students understand more after the activity."
            )
        else:
            st.info("There are not enough valid answers to create this chart yet.")

    st.subheader("Limitations")
    st.markdown(
        """
        1. The questionnaire uses a small, non-random sample of respondents, so the findings cannot represent all students.
        2. The answers show what respondents prefer, but they do not prove that a learning method will improve their knowledge.
        """
    )
    st.subheader("Source note")
    st.write(
        "Questionnaire: anonymous responses collected through Google Forms and stored "
        "in the connected Google Sheets response spreadsheet. Cultural background "
        "information: Bali Provincial Government publications and the research sources listed on the References page."
    )
    st.caption(
        "The chart, response count, conclusion, and recommendation update when new valid questionnaire responses are available."
    )
    st.subheader("Privacy")
    st.write(
        "The questionnaire should remain anonymous. Do not collect names, emails, student IDs, or other identifying information."
    )


# ============================================================
# 15. UNIVERSAL VALUES
# ============================================================

elif page == "Universal Values":
    st.title("Universal Values")
    st.write(
        "Universal values are principles that people from different backgrounds can share. "
        "Catholic values are guided by the teachings of Jesus and the Catholic Church. "
        "Both can guide how I learn about and protect Kain Endek."
    )
    st.subheader("Five universal values")
    universal_values = {
        "Respect": "Listen to artisans, respect cultural practices, and avoid making unsupported claims.",
        "Unity": "Recognise that different traditions can bring people together while respecting their differences.",
        "Responsibility": "Check information carefully, protect survey privacy, and think about the effects of what I publish.",
        "Appreciation": "Recognise the creativity, time, knowledge, and skill involved in making Endek.",
        "Open-mindedness": "Be willing to learn about traditions that may be unfamiliar to me.",
    }
    for name, description in universal_values.items():
        with st.expander(name):
            st.write(description)

    st.divider()
    st.subheader("My chosen universal value: Responsibility")
    st.write(
        "I chose responsibility because I needed to make sure that the information I shared was accurate and that the people who answered my questionnaire were respected. "
        "I checked information against sources, kept the questionnaire anonymous and optional, and avoided claiming that my website had already changed people's knowledge or attitudes. "
        "Responsibility means being careful about the effects of my choices, both online and in the community."
    )

    st.subheader("Five Catholic values")
    catholic_values = {
        "Human dignity": "Every person has worth. I should respect the weavers, students, and community members who contribute to keeping cultural knowledge alive.",
        "Stewardship": "I am entrusted with caring for what I have been given. I can help look after cultural heritage and pass knowledge on responsibly.",
        "Compassion": "I should care about the challenges faced by artisans and support efforts that respect their work and livelihoods.",
        "Solidarity": "I stand with others and work together for the good of the community, including supporting the people who preserve Endek traditions.",
        "Truthfulness": "I should be honest, check my sources, present survey findings accurately, and avoid claiming results I have not measured.",
    }
    for name, description in catholic_values.items():
        with st.expander(name):
            st.write(description)


# ============================================================
# 16. ACTION PLAN
# ============================================================

elif page == "Action Plan":
    st.title("Action Plan")
    st.write(
        "This section records the three actions I completed and the outcomes of each one."
    )

    st.subheader("Completed action 1: Create and run the questionnaire")
    st.success("Status: Completed")
    st.write(
        "I created a six-question Google Forms questionnaire. It was anonymous and optional, "
        "and its description included a consent statement. I shared it with friends and "
        "students from different grades, collected their responses, removed timestamps "
        "from the analysis, and organised the answers."
    )
    if data_error is None:
        st.metric("Responses currently in the connected sheet", total_responses)
        st.caption("This is the current live response count; it may change as new responses arrive.")
    else:
        st.info("The questionnaire was carried out, but its live response count cannot be confirmed right now.")
    st.write(
        "Actual outcome: I obtained questionnaire responses that I could use to examine "
        "awareness, familiarity, interest, preferred learning methods, and views about unity. "
        "The results describe the people who responded, not the whole school community."
    )

    st.divider()
    st.subheader("Completed action 2: Create and share an educational animation")
    st.success("Status: Completed")
    st.write(
        "I created a short, entertaining educational animation about Kain Endek. I used an "
        "attention-grabbing hook, then briefly introduced what Kain Endek is. I included a "
        "link to my ENDEK EXPLORER website so viewers could explore the topic further and try "
        "the interactive activities. I checked the information against two sources and posted "
        "the animation publicly on Instagram with my parent's permission."
    )
    st.write(
        "Actual outcome: The animation was published publicly on Instagram and directed "
        "viewers to the website for more information and interactive activities."
    )

    st.divider()
    st.subheader("Completed action 3: Build the ENDEK EXPLORER website")
    st.success("Status: Completed — website developed")
    st.write(
        "I built this website to bring together the community issue, research, questionnaire "
        "data, and project action plan in one place."
    )
    st.write(
        "Actual outcome: The website provides a digital information space where visitors "
        "can explore the project. It does not yet prove that visitors' knowledge or attitudes changed."
    )



# ============================================================
# 17. REFLECTION AND CONCLUSION
# ============================================================

elif page == "Reflection and Conclusion":
    st.title("Reflection and Conclusion")
    st.subheader("Conclusion")
    st.write(
        "Published sources show that Endek weaving continues to be promoted, "
        "while concerns about the regeneration of weavers have also been reported."
    )

    if data_error is None:
        familiarity_text = (
            f"The average familiarity score was {familiarity_mean:.2f}/5 "
            f"from {familiarity_n} valid answers."
            if familiarity_mean is not None
            else "There were not enough valid familiarity answers to calculate an average."
        )
        interest_text = (
            f"The average interest score was {interest_mean:.2f}/5 "
            f"from {interest_n} valid answers."
            if interest_mean is not None
            else "There were not enough valid interest answers to calculate an average."
        )
        st.write(
            f"My questionnaire currently has {total_responses} responses. "
            f"{familiarity_text} {interest_text}"
        )
        if method_valid_n:
            st.write(
                f"The most popular learning method was {most_popular_method}, "
                f"selected by {most_popular_method_count} respondents."
            )
    else:
        st.warning("The live survey statistics are unavailable at the moment.")
        with st.expander("Technical details"):
            st.code(data_error)

    st.write(
        "These findings can help guide learning activities, but they do not prove "
        "that the entire school community has low cultural knowledge or that a website alone can solve artisan regeneration."
    )

    st.divider()
    st.subheader("What I learned")
    st.write(
        "Through this project, I learned that Kain Endek Bali is more than a cloth. "
        "It is part of Indonesia's cultural identity, and it shows what Bhinneka "
        "Tunggal Ika means: different traditions making one nation. I also learned "
        "that sources do not always agree. For example, they gave different dates "
        "for when Endek began, so I had to compare them before trusting one."
    )
    if data_error is None:
        st.write(
            f"My survey currently has {total_responses} responses. "
            + (
                f"The average interest score is {interest_mean:.2f}/5 from {interest_n} valid answers."
                if interest_mean is not None
                else "There are not enough valid interest answers to calculate an average."
            )
        )
        st.write(
            (
                f"The average familiarity score is {familiarity_mean:.2f}/5 from {familiarity_n} valid answers."
                if familiarity_mean is not None
                else "There are not enough valid familiarity answers to calculate an average."
            )
        )
        if method_valid_n:
            st.write(
                f"{most_popular_method_count} out of {method_valid_n} respondents preferred "
                f"{most_popular_method.lower()}. This showed me that interest and knowledge "
                "are not the same, and that people may need the right way to learn."
            )

    st.write(
        "I also learned that taking responsibility for a tradition means checking facts, not just repeating them."
    )

    st.subheader("What I did")
    st.write(
        "I planned and wrote a six-question questionnaire in Google Forms. I made it "
        "anonymous and used multiple-choice questions so people could answer easily. "
        "I put the consent statement in the description so nobody felt pressured. "
        "I collected responses from friends and peers in different grades, removed "
        "the timestamp column from my analysis, and organised the results."
    )
    st.write(
        "I also made a short, entertaining animation about Kain Endek. It starts with an "
        "attention-grabbing hook and briefly explains what Kain Endek is. I included a link "
        "to my ENDEK EXPLORER website so viewers could explore the topic further and try the "
        "interactive activities. After checking the information against two sources, I posted "
        "the animation publicly on Instagram with my parent's permission."
    )
    st.write(
        "The value that guided me was responsibility, which means looking after what "
        "I have been trusted with. Because anyone could watch the video, I felt more "
        "responsible for making the information accurate, so I checked facts across "
        "two sources before sharing them. I also protected my classmates' privacy by "
        "keeping the survey anonymous and optional, and I kept every response so my results stayed honest."
    )
    st.write(
        "This connects to the Catholic value of stewardship, because cultural heritage "
        "is something I am trusted to look after and pass on to others. A public post "
        "lets me share it beyond my classroom. Then I made a website to show my research, my data, and my action plan."
    )

    st.divider()
    st.subheader("How can my solution help others?")
    st.write(
        "The animation can introduce Kain Endek in a short and accessible way, while the website brings the issue, research, questionnaire findings, and interactive learning activities together. "
        "This gives students and other visitors a place to learn more and explore the topic. However, I have not measured whether visitors' knowledge or attitudes changed, so I cannot claim that the project has already solved the issue."
    )

    st.subheader("How will I continue applying these values?")
    st.write(
        "I can continue showing responsibility by checking sources before sharing information, protecting people's privacy, and being honest about what my data can and cannot show. "
        "I can show respect and appreciation by listening to artisans and learning about their work without making unsupported claims. "
        "I can also practise unity by respecting traditions from different parts of Indonesia and sharing reliable information with others."
    )

    st.subheader("How I can improve")
    st.write(
        "My data has limits. The respondents were mostly friends and peers, so my "
        "results only describe the people who answered and not all students in Indonesia. "
        "I did not record grade levels, so I cannot compare younger and older students."
    )
    st.write(
        "A few people said they had never heard of Endek but still rated their "
        "familiarity as moderate, so some answers may have been rushed or unclear. "
        "One question also asked about wearing and seeing Endek at the same time, "
        "which made it harder to interpret."
    )
    st.write(
        "Next time, I would test the form first, ask a wider mix of students, and ask "
        "one thing per question. I also cannot measure how the video was received, "
        "so next time I would track views and comments. Being responsible also means "
        "improving my work, so I will continue to check who wrote a source before I use it."
    )


# ============================================================
# 18. ASK THE ENDEK GUIDE
# ============================================================

elif page == "Ask the Endek Guide":
    st.title("Ask the Endek Guide")
    st.write(
        "Ask questions in everyday language. The Endek Guide is designed to help with "
        "Kain Endek and Balinese culture first, while also covering general learning topics "
        "such as Indonesian geography, science, technology and school concepts."
    )
    st.info(
        "This version uses a built-in knowledge library and programmed responses. "
        "It is not yet connected to a generative AI model, so it cannot answer every "
        "possible question or browse the internet. It will tell you when a question is outside its knowledge."
    )

    def endek_reply(message):
        q = message.lower().strip()
        words = set(re.findall(r"[a-z0-9]+", q))

        # Friendly conversation.
        if q in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hola"}:
            return "Hello! 👋 I'm the Endek Guide. You can ask me about Kain Endek, Indonesian culture, geography, science, technology or other learning topics."
        if any(phrase in q for phrase in ["thank you", "thanks", "terima kasih"]):
            return "You're welcome! 🧵 What else would you like to explore?"
        if any(phrase in q for phrase in ["tell me a joke", "make me laugh", "joke"]):
            return "Why did the textile pattern get good grades? Because it always had a good weave of ideas! 😄"
        if any(phrase in q for phrase in ["who are you", "your name", "what can you do"]):
            return "I'm the Endek Guide. I focus on Kain Endek and Balinese heritage, and I can also explain selected general topics such as Indonesian geography, science, technology and school concepts."

        # Explain survey terminology before interpreting questions about this project's live results.
        if any(x in q for x in ["what is a survey", "what is survey", "what is a questionnaire", "what does questionnaire mean"]):
            return "A survey or questionnaire is a set of questions used to collect information from people. Clear wording, privacy and a suitable range of respondents help make the results more useful."

        # Survey questions are handled before broad cultural or school questions.
        strong_data_terms = {"respondents", "statistics", "findings", "average", "percentage"}
        school_data_request = (
            bool(words & strong_data_terms)
            or any(x in q for x in [
                "school data", "survey result", "survey finding", "survey response",
                "questionnaire result", "questionnaire response", "how many responses",
                "what did respondents answer", "what did people answer in the survey",
                "show me the results", "survey says", "from the survey"
            ])
        )
        if school_data_request:
            if data_error is not None:
                return (
                    "The questionnaire asks about prior awareness, seeing or wearing Endek at school events, "
                    "familiarity, interest, preferred learning methods, and whether learning traditional crafts "
                    "can support unity. The live spreadsheet is unavailable right now, so I won't guess the numbers."
                )
            if any(x in q for x in ["familiar", "interest", "average", "score", "rating"]):
                parts = []
                if familiarity_mean is not None:
                    parts.append(f"average familiarity is {familiarity_mean:.2f}/5 (from {familiarity_n} valid answers)")
                if interest_mean is not None:
                    parts.append(f"average interest is {interest_mean:.2f}/5 (from {interest_n} valid answers)")
                return ("In the live questionnaire, " + "; ".join(parts) + ". " if parts else
                        "There are not enough valid numeric answers to calculate these averages. ") + "These results describe respondents, not the whole school population."
            if any(x in q for x in ["method", "learn", "demonstration", "video", "poster"]):
                return (f"The most selected learning method is a traditional clothing or fabric demonstration: "
                        f"{demonstration_count} out of {method_valid_n} valid answers. "
                        "This records what respondents preferred; it does not prove that everyone would learn best this way.")
            if any(x in q for x in ["unity", "respect", "community"]):
                counts = df["Believes learning supports unity"].value_counts() if "Believes learning supports unity" in df.columns else pd.Series(dtype=int)
                summary = ", ".join(f"{str(k)}: {int(v)}" for k, v in counts.items())
                return (f"For the unity question, the live responses are: {summary}. " if summary else
                        "There are no valid answers recorded for the unity question yet. ") + "These are respondents' opinions, not proof that a learning activity has already increased unity."
            if any(x in q for x in ["seen", "worn", "event", "festivit"]):
                counts = df["Seen or worn at school events"].value_counts() if "Seen or worn at school events" in df.columns else pd.Series(dtype=int)
                summary = ", ".join(f"{str(k)}: {int(v)}" for k, v in counts.items())
                return (f"For seeing or wearing Endek at school events, the responses are: {summary}. " if summary else
                        "There are no valid answers recorded for that question yet.")
            if any(x in q for x in ["heard", "aware", "awareness"]):
                counts = df["Prior awareness"].value_counts() if "Prior awareness" in df.columns else pd.Series(dtype=int)
                summary = ", ".join(f"{str(k)}: {int(v)}" for k, v in counts.items())
                return (f"For prior awareness of Kain Endek, the responses are: {summary}. " if summary else
                        "There are no valid answers recorded for prior awareness yet.")
            return (f"The live questionnaire currently has {total_responses} responses. It covers awareness, school-event exposure, "
                    "familiarity, interest, preferred learning method, and beliefs about unity. Ask about one area for its specific result. "
                    "The sample describes respondents only, not every student.")

        # Kain Endek and Balinese heritage remain the assistant's main focus.
        if any(x in q for x in ["what is endek", "what's endek", "define endek", "kain endek", "endek mean"]):
            return "Kain Endek is a traditional Balinese woven textile. Its patterns are made using an ikat process, in which sections of yarn are tied and dyed before weaving. It is an important part of Bali's textile heritage."
        if any(x in q for x in ["made", "weav", "ikat", "process", "technique"]):
            return "In the ikat process used for Endek, sections of yarn are tied so dye cannot reach those parts. The yarn is dyed, arranged and woven to create a pattern. For Endek, the pattern is dyed into the crosswise weft threads, which must be carefully aligned during weaving."
        if any(x in q for x in ["pattern", "motif", "design", "symbol", "colour", "color"]):
            return "Endek designs can include geometric, plant, animal and culturally inspired motifs. The meaning depends on the particular design and its context, so it would be inaccurate to claim that every pattern has one fixed meaning."
        if any(x in q for x in ["important", "why preserve", "why matter", "heritage", "culture"]):
            return "Endek matters because it carries textile knowledge, artistic skill and cultural heritage from Bali. Supporting it means respecting artisans and helping younger generations understand the tradition."
        if any(x in q for x in ["disappear", "dying", "young weaver", "weaver", "crisis"]):
            return "It would be inaccurate to say Endek has disappeared. However, the Bali Provincial Government has raised concern about the future regeneration of young Endek weavers. Passing on weaving knowledge and supporting artisans therefore matters."
        if any(x in q for x in ["unity", "together", "bhinneka", "diversity"]):
            return "Learning about traditional crafts can help people respect different cultural traditions. This connects with Bhinneka Tunggal Ika: unity while recognising Indonesia's diversity."
        if any(x in q for x in ["student", "school", "help", "support", "preserve"]):
            return "Students can learn from reliable sources and local artisans, appreciate Endek respectfully, share accurate information and take part in school activities. They can also explain why traditional weaving skills deserve recognition."

        # Selected general-knowledge topics.
        if any(x in q for x in ["indonesia", "indonesian archipelago", "how many islands"]):
            return "Indonesia is an archipelagic country in Southeast Asia, between the Indian and Pacific Oceans. It has thousands of islands and many cultural and language communities. Its five major islands commonly highlighted are Sumatra, Java, Kalimantan, Sulawesi and Papua."
        if "java" in words and any(x in q for x in ["island", "where", "population", "tell me about"]):
            return "Java is Indonesia's most populous island and a major centre of government, business and culture. It includes Jakarta, Surabaya and Bandung, as well as volcanoes such as Mount Bromo and historic sites such as Borobudur and Prambanan."
        if "sumatra" in words:
            return "Sumatra is a large island in western Indonesia. It has the Barisan mountain range, Lake Toba and important tropical forests that support wildlife such as orangutans, elephants, rhinoceroses and tigers."
        if "kalimantan" in words or "borneo" in words:
            return "Kalimantan is the Indonesian part of Borneo, an island shared with Malaysia and Brunei. It is known for tropical rainforests, large rivers, Dayak communities and orangutan habitats. Nusantara, Indonesia's planned new capital, is being developed in East Kalimantan."
        if "sulawesi" in words:
            return "Sulawesi is an Indonesian island with a distinctive K-like shape. It is known for wildlife such as babirusa and anoa, the Toraja cultural region, and coral reefs around Bunaken National Park."
        if "papua" in words or "new guinea" in q:
            return "Papua is the Indonesian part of New Guinea, the world's second-largest island. Its landscapes include tropical forests and the Maoke Mountains, and it is home to many Indigenous communities, languages and traditions."
        if any(x in q for x in ["volcano", "volcanoes", "why does indonesia have volcanoes"]):
            return "Indonesia has many volcanoes because it lies where several tectonic plates meet. As plates move and one plate can sink beneath another, magma may rise and form volcanoes. This is part of the Pacific Ring of Fire."
        if any(x in q for x in ["rainforest", "rain forest", "biodiversity", "endemic"]):
            return "Tropical rainforests are warm, wet forests with many kinds of plants and animals. Indonesia's forests support high biodiversity, including species found naturally only in particular regions. Protecting habitats helps protect these species and the communities that depend on forests."
        if any(x in q for x in ["what is a survey", "questionnaire", "survey mean"]):
            return "A survey is a way to collect information by asking people questions. Good surveys use clear, neutral questions, protect respondents' privacy and avoid claiming that a small sample represents everyone."
        if any(x in q for x in ["what is python", "python programming", "programming language"]):
            return "Python is a programming language used to write instructions for computers. It is popular for data analysis, automation, websites and artificial intelligence because its code is often readable for beginners."
        if any(x in q for x in ["what is streamlit", "streamlit"]):
            return "Streamlit is a Python tool for creating interactive data apps and websites. In ENDEK EXPLORER, it displays the pages, charts, questionnaire results and interactive activities."
        if any(x in q for x in ["what is computational thinking", "computational thinking"]):
            return "Computational thinking is a way to solve problems using four main ideas: decomposition (break a problem into parts), pattern recognition (spot similarities), abstraction (focus on important information) and algorithms (write clear steps)."
        if any(x in q for x in ["what is ai", "artificial intelligence", "what is artificial intelligence"]):
            return "Artificial intelligence (AI) is technology that can perform tasks that usually require human-like abilities, such as recognising patterns, understanding language or making predictions. AI systems can make mistakes, so important information should be checked against reliable sources."
        if any(x in q for x in ["source", "reference", "where did", "evidence"]):
            return "Useful sources for this project include Statistics Indonesia (BPS), the Bali Provincial Government, the Asian Art Museum, the Journal of Visual Art and Design, and Segara Widya from ISI Denpasar. Open the References page to visit the project's sources."

        return (
            "I don't have a reliable built-in answer for that question yet. I can help with Kain Endek, "
            "Balinese heritage, Indonesian geography, selected science topics, Python, Streamlit and "
            "computational thinking. Try asking in a different way, or choose a topic from that list."
        )

    if "endek_chat_history" not in st.session_state:
        st.session_state.endek_chat_history = [
            {"role": "assistant", "content": "Hello! 👋 I'm the Endek Guide. Ask me about Kain Endek or a general learning topic."}
        ]

    st.subheader("Try asking")
    st.caption("Choose a suggested question or type your own below.")
    helper_questions = [
        "What is Kain Endek?",
        "How is Kain Endek made?",
        "Why is Kain Endek important?",
        "What makes Java important to Indonesia?",
        "Why does Indonesia have volcanoes?",
        "What is computational thinking?",
    ]
    helper_cols = st.columns(3)
    for i, question in enumerate(helper_questions):
        if helper_cols[i % 3].button(question, key=f"endek_helper_{i}", use_container_width=True):
            st.session_state.endek_chat_history.append({"role": "user", "content": question})
            st.session_state.endek_chat_history.append({"role": "assistant", "content": endek_reply(question)})
            st.rerun()

    for item in st.session_state.endek_chat_history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    prompt = st.chat_input("Ask about Endek or another learning topic...")
    if prompt:
        st.session_state.endek_chat_history.append({"role": "user", "content": prompt})
        reply = endek_reply(prompt)
        st.session_state.endek_chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.button("Clear chat"):
        st.session_state.endek_chat_history = [
            {"role": "assistant", "content": "Chat cleared! Ask me about Kain Endek or a general learning topic."}
        ]
        st.rerun()


# ============================================================
# 19. ENDEK HERITAGE GAME
# ============================================================

elif page == "Endek Heritage Game":
    import random
    import copy

    st.title("Endek Guardian: The Living Heritage Challenge 🧵")
    st.write(
        "A replayable mini-adventure. Each round brings a new situation from a rotating set of "
        "project challenges. Earn points, build a community reputation, and see a different set "
        "of events when you play again."
    )

    scenario_bank = [
        {"area":"Research", "title":"Two sources disagree", "story":"Two sources give different dates for the history of Endek. Your presentation is due soon.", "choices":[("Compare the original sources and explain the disagreement",3,"Good research means checking evidence and being honest when sources differ."),("Pick the date that looks most interesting",0,"A more exciting answer is not necessarily an accurate one."),("Invent a date that fits the presentation",0,"Never invent historical information.")]},
        {"area":"Research", "title":"A suspicious online claim", "story":"A social media post makes a dramatic claim about an Endek motif but gives no source.", "choices":[("Check reliable sources or ask a knowledgeable artisan",3,"You checked the claim before sharing it."),("Share it because it has many likes",0,"Popularity is not proof."),("Repeat it but say you are not sure",1,"A warning helps, but checking before sharing is stronger.")]},
        {"area":"Community", "title":"Plan a school activity", "story":"Your questionnaire suggests a fabric demonstration is a popular learning method.", "choices":[("Ask a teacher about inviting a local artisan",3,"This connects the activity to the survey and practical knowledge."),("Assume every student wants the same activity",1,"The survey is useful, but it does not represent everyone."),("Cancel the activity without asking anyone",0,"You can explore the idea before deciding.")]},
        {"area":"Community", "title":"A student feels left out", "story":"A new student does not know much about Endek and feels nervous joining the activity.", "choices":[("Invite them in and explain the activity without judging",3,"Welcoming others makes cultural learning more inclusive."),("Tell them they should already know it",0,"People have different experiences and knowledge."),("Ignore them and continue",0,"You missed a chance to make the activity welcoming.")]},
        {"area":"Digital", "title":"Ready to publish", "story":"Your team has finished an educational Endek animation and wants to post it online.", "choices":[("Fact-check it, credit materials, and get required adult permission",3,"Responsible publishing protects accuracy and respects others."),("Use any image found online without credit",0,"Images need appropriate permission and credit."),("Publish first and check later",0,"Errors can spread once something is public.")]},
        {"area":"Digital", "title":"A photo needs a caption", "story":"You found a photograph of Endek fabric for the Home page.", "choices":[("Use the original source and add a clear credit",3,"Good attribution helps visitors trace the image."),("Write that your I took the photo",0,"That would misrepresent who created it."),("Leave out the source",0,"Visitors should be able to identify where the image came from.")]},
        {"area":"Impact", "title":"What did the video achieve?", "story":"Your video is published, but you have not measured its viewers or learning impact.", "choices":[("Report that it was published and say impact is not yet measured",3,"You separated a completed action from an unmeasured outcome."),("Claim everyone learned something",0,"You do not have evidence for that claim."),("Make up a viewer number",0,"Never invent data.")]},
        {"area":"Impact", "title":"A small survey sample", "story":"Most questionnaire responses came from people in your school network.", "choices":[("Explain that the findings describe respondents, not all young people in Bali",3,"That is an accurate limitation."),("Claim it represents every young person in Bali",0,"The sample is not broad enough for that conclusion."),("Hide the sample limitation",0,"Limitations should be reported honestly.")]},
        {"area":"Craft", "title":"Meet a weaver", "story":"A local artisan is willing to explain the weaving process to students.", "choices":[("Prepare respectful questions and listen carefully",3,"You are learning directly and respectfully."),("Interrupt and rush through the demonstration",0,"Give the artisan time to explain their knowledge."),("Assume you already know everything",0,"There is always more to learn from practical experience.")]},
        {"area":"Craft", "title":"A motif is misunderstood", "story":"A classmate says every Endek motif has exactly the same meaning.", "choices":[("Explain that meanings depend on the design and context",3,"Avoiding overgeneralisation is culturally respectful."),("Agree without checking",0,"That claim may be inaccurate."),("Make up a symbolic meaning",0,"Do not invent cultural meanings.")]},
        {"area":"Community", "title":"Different learning preferences", "story":"Some students prefer videos while others prefer demonstrations.", "choices":[("Offer more than one way to learn if resources allow",3,"A mix can include more students."),("Only offer the method you personally like",1,"Your preference may not match everyone's."),("Tell students their preferences are wrong",0,"Different learners can prefer different methods.")]},
        {"area":"Impact", "title":"Plan the next research step", "story":"You want to understand whether your educational video improved knowledge.", "choices":[("Use a short before-and-after check with clear questions",3,"A simple evaluation can provide better evidence of learning."),("Assume views automatically mean learning",0,"Watching does not prove understanding."),("Ask only your closest friend and generalise",1,"One opinion is useful feedback, not broad evidence.")]},
    ]

    if "endek_game_round" not in st.session_state:
        st.session_state.endek_game_round = 0
        st.session_state.endek_game_points = 0
        st.session_state.endek_game_log = []
        st.session_state.endek_game_events = random.sample(copy.deepcopy(scenario_bank), 5)
        for game_event in st.session_state.endek_game_events:
            random.shuffle(game_event["choices"])

    total_rounds = len(st.session_state.endek_game_events)
    round_no = st.session_state.endek_game_round
    if round_no < total_rounds:
        event = st.session_state.endek_game_events[round_no]
        st.progress(round_no / total_rounds, text=f"Round {round_no + 1} of {total_rounds}")
        a, b, c = st.columns(3)
        a.metric("Heritage points", st.session_state.endek_game_points)
        b.metric("Reputation", f"{min(100, st.session_state.endek_game_points * 7)} / 100")
        c.metric("Events completed", round_no)
        st.caption(f"CHALLENGE AREA · {event['area'].upper()}")
        st.subheader(event["title"])
        st.write(event["story"])
        options = [item[0] for item in event["choices"]]
        choice = st.radio("What will you do?", options, key=f"endek_game_choice_{round_no}")
        if st.button("Lock in my decision", key=f"endek_game_submit_{round_no}"):
            points, feedback = next((score, note) for label, score, note in event["choices"] if label == choice)
            st.session_state.endek_game_points += points
            st.session_state.endek_game_log.append({"title":event["title"], "area":event["area"], "choice":choice, "points":points, "feedback":feedback})
            st.session_state.endek_game_round += 1
            st.rerun()
    else:
        final_points = st.session_state.endek_game_points
        st.progress(1.0, text="Challenge complete")
        st.subheader("Your community report 🏅")
        st.metric("Final heritage points", f"{final_points} / {total_rounds * 3}")
        if final_points >= total_rounds * 3 * 0.8:
            st.success("Heritage Guardian! You made thoughtful, responsible decisions.")
        elif final_points >= total_rounds * 3 * 0.5:
            st.info("Community Builder! You made several strong choices. Review the feedback to improve.")
        else:
            st.warning("Your journey has started. Review the feedback and try a new set of events.")
        for i, item in enumerate(st.session_state.endek_game_log, 1):
            with st.expander(f"Round {i}: {item['title']} · {item['points']} points"):
                st.caption(item["area"])
                st.write(f"Your decision: {item['choice']}")
                st.write(item["feedback"])
        if st.button("Start a new adventure", type="primary"):
            st.session_state.endek_game_round = 0
            st.session_state.endek_game_points = 0
            st.session_state.endek_game_log = []
            st.session_state.endek_game_events = random.sample(copy.deepcopy(scenario_bank), 5)
            for game_event in st.session_state.endek_game_events:
                random.shuffle(game_event["choices"])
            st.rerun()


# ============================================================
# 20. REFERENCES PAGE
# ============================================================

elif page == "References":
    st.title("References")
    st.write(
        "The following sources provide background information for this project. "
        "Open the original publications to check their authors, dates, and claims "
        "before citing them in your final school submission."
    )
    show_references()


# ============================================================
# 21. FOOTER
# ============================================================

show_footer()
