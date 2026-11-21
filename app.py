from pathlib import Path
import sqlite3, hashlib, hmac, os, json, secrets
from datetime import datetime
import joblib
import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / 'fraud_model.joblib'
DEMO_PATH = BASE / 'demo_transactions.csv'
# Use a writable per-user data directory on Windows and hosted Linux services.
# Override with FRAUDGUARD_DATA_DIR if the deployment provides persistent storage.
APP_DATA = Path(os.environ.get('FRAUDGUARD_DATA_DIR', str(Path.home() / '.fraudguard')))
APP_DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DATA / 'fraudguard.db'
SUMMARY_PATH = BASE / 'dataset_summary.json'

st.set_page_config(page_title='FraudGuard | Credit Card Risk Monitor', page_icon='🛡️', layout='wide', initial_sidebar_state='expanded')

st.markdown('''<style>
:root{--ink:#eaf0fb;--muted:#91a0b8;--panel:#111c2e;--line:#263650;--accent:#5eead4}
.stApp{background:linear-gradient(135deg,#08111f 0%,#0c1728 55%,#101b2f 100%);color:var(--ink)}
.block-container{padding-top:1.6rem;max-width:1450px}
[data-testid="stSidebar"]{background:#0b1525;border-right:1px solid #263650}
[data-testid="stMetric"]{background:#111c2e;border:1px solid #263650;padding:18px;border-radius:15px}
[data-testid="stMetricLabel"]{color:#9fb0c9}
[data-testid="stMetricValue"]{color:#f8fafc}
div.stButton>button{border-radius:10px;border:1px solid #31506d;background:#17334a;color:#f5fbff;font-weight:650;min-height:2.7rem}
div.stButton>button:hover{border-color:#5eead4;color:#5eead4}
.card{background:#111c2e;border:1px solid #263650;border-radius:16px;padding:20px 22px;margin-bottom:14px}
.muted{color:#9fb0c9}.brand{font-size:1.75rem;font-weight:800;letter-spacing:-.04em}.pill{display:inline-block;padding:5px 10px;border-radius:999px;background:#163b3b;color:#8ef3dd;font-size:.78rem;font-weight:700}
.result-fraud{border:1px solid #ef4444;background:rgba(127,29,29,.22);border-radius:16px;padding:22px}
.result-safe{border:1px solid #10b981;background:rgba(6,95,70,.22);border-radius:16px;padding:22px}
</style>''', unsafe_allow_html=True)

@st.cache_resource
def load_assets():
    if not MODEL_PATH.exists():
        return None, None
    bundle = joblib.load(MODEL_PATH)
    demo = pd.read_csv(DEMO_PATH) if DEMO_PATH.exists() else pd.DataFrame()
    return bundle, demo


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute('''CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, created_at TEXT, amount REAL, probability REAL, prediction INTEGER, source TEXT)''')
    con.commit()
    return con


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 240000).hex()
    return salt, digest


def ensure_demo_user():
    con = db()
    row = con.execute('SELECT username FROM users WHERE username=?', ('admin@fraudguard.demo',)).fetchone()
    if not row:
        salt, digest = hash_password('Fraud@123')
        con.execute('INSERT INTO users VALUES(?,?,?,?)', ('admin@fraudguard.demo', salt, digest, datetime.now().isoformat(timespec='seconds')))
        con.commit()
    con.close()


def authenticate(username, password):
    con = db()
    row = con.execute('SELECT salt,password_hash FROM users WHERE username=?', (username.strip().lower(),)).fetchone()
    con.close()
    if not row:
        return False
    _, digest = hash_password(password, row[0])
    return hmac.compare_digest(digest, row[1])


def save_prediction(username, amount, probability, prediction, source):
    con = db()
    con.execute('INSERT INTO predictions(username,created_at,amount,probability,prediction,source) VALUES(?,?,?,?,?,?)',
                (username, datetime.now().isoformat(timespec='seconds'), float(amount), float(probability), int(prediction), source))
    con.commit(); con.close()


def get_history(username=None):
    con = db()
    if username:
        data = pd.read_sql_query('SELECT id,created_at,amount,probability,prediction,source FROM predictions WHERE username=? ORDER BY id DESC', con, params=(username,))
    else:
        data = pd.read_sql_query('SELECT id,created_at,amount,probability,prediction,source FROM predictions ORDER BY id DESC', con)
    con.close()
    return data


def predict(features, bundle):
    frame = pd.DataFrame([features], columns=bundle['features'])
    frame.loc[:, ['Time','Amount']] = bundle['scaler'].transform(frame[['Time','Amount']])
    probability = float(bundle['model'].predict_proba(frame)[0,1])
    threshold = float(st.session_state.get('threshold', bundle.get('threshold',0.5)))
    return probability, int(probability >= threshold)


def login_screen():
    left, right = st.columns([1.1, .9], gap='large')
    with left:
        st.markdown('<div class="brand">🛡️ FraudGuard</div><p class="muted">Credit Card Fraud Detection & Transaction Risk Monitoring</p>', unsafe_allow_html=True)
        st.markdown('''<div class="card"><span class="pill">MACHINE LEARNING POWERED</span><h1 style="margin-top:18px">See suspicious activity<br>before it becomes a loss.</h1><p class="muted">A student-built fraud analytics prototype using a Random Forest classifier trained on anonymised transaction data.</p><hr style="border-color:#263650"><p>✓ Transaction risk scoring</p><p>✓ Fraud monitoring dashboard</p><p>✓ Prediction history and analytics</p></div>''', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader('Welcome back')
        st.caption('Sign in to open your fraud monitoring workspace.')
        with st.form('login_form'):
            username = st.text_input('Login ID / Email', placeholder='admin@fraudguard.demo')
            password = st.text_input('Password', type='password', placeholder='Enter password')
            submitted = st.form_submit_button('Sign in', use_container_width=True)
        if submitted:
            if authenticate(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username.strip().lower()
                st.rerun()
            else:
                st.error('Incorrect Login ID or password.')
        st.markdown('</div>', unsafe_allow_html=True)
        st.info('Demo access\n\nLogin ID: `admin@fraudguard.demo`\n\nPassword: `Fraud@123`')


def main_app(bundle, demo):
    username = st.session_state.username
    with st.sidebar:
        st.markdown('<div class="brand">🛡️ FraudGuard</div><p class="muted">FRAUD MONITORING SYSTEM</p>', unsafe_allow_html=True)
        st.markdown(f'**Signed in as**  \n{username}')
        page = st.radio('WORKSPACE', ['Overview','Check a Transaction','Transaction History','Analytics','Model Information'], label_visibility='visible')
        st.markdown('---')
        st.caption('Risk threshold')
        st.session_state.threshold = st.slider('Flag if fraud probability ≥', 0.05, 0.95, float(st.session_state.get('threshold', bundle.get('threshold',0.5))), 0.05, format='%.2f')
        st.caption('Lower thresholds detect more potential fraud but may increase false alerts.')
        if st.button('Sign out', use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.username = ''
            st.rerun()

    history = get_history(username)
    summary = json.loads(SUMMARY_PATH.read_text()) if SUMMARY_PATH.exists() else {}
    st.markdown(f'<div class="brand">{page}</div><p class="muted">Credit Card Fraud Detection · Secure analysis workspace</p>', unsafe_allow_html=True)

    if page == 'Overview':
        total = len(history); flagged = int((history.prediction == 1).sum()) if total else 0
        legitimate = total - flagged
        c1,c2,c3,c4 = st.columns(4)
        c1.metric('Transactions checked', f'{total:,}')
        c2.metric('Flagged as suspicious', f'{flagged:,}')
        c3.metric('Marked legitimate', f'{legitimate:,}')
        c4.metric('Fraud alert rate', f'{(flagged/total*100):.1f}%' if total else '0.0%')
        st.markdown('<div class="card"><h3>Welcome to your monitoring workspace</h3><p class="muted">Use “Check a Transaction” to enter a transaction or load an anonymised demonstration record. The model returns a fraud probability and a decision based on the threshold in the sidebar.</p></div>', unsafe_allow_html=True)
        a,b = st.columns(2)
        with a:
            st.markdown('<div class="card"><h4>Dataset overview</h4>', unsafe_allow_html=True)
            st.metric('Original dataset records', f"{summary.get('rows_original',284807):,}")
            st.metric('Fraud records in dataset', f"{summary.get('fraud_original',492):,}")
            st.caption('These are source-dataset statistics, not live bank transactions.')
            st.markdown('</div>', unsafe_allow_html=True)
        with b:
            st.markdown('<div class="card"><h4>Quick action</h4><p class="muted">Start a new transaction risk check.</p></div>', unsafe_allow_html=True)
            if st.button('＋ Check a transaction', use_container_width=True):
                st.session_state.goto_check = True; st.rerun()
        if total:
            st.subheader('Recent activity')
            show = history.head(6).copy(); show['Status'] = show.prediction.map({0:'Legitimate',1:'Potential fraud'})
            show['Fraud probability'] = (show.probability*100).round(2).astype(str)+'%'
            st.dataframe(show[['created_at','amount','Status','Fraud probability','source']], use_container_width=True, hide_index=True)
        else:
            st.info('No transactions have been checked yet. Try the demo transaction to see the system in action.')

    elif page == 'Check a Transaction' or st.session_state.pop('goto_check', False):
        st.markdown('<div class="card"><h3>Transaction input</h3><p class="muted">Choose a demo record for a one-click walkthrough, or enter the numerical model features manually. This public dataset contains anonymised PCA variables V1–V28; it does not contain card number, customer name or merchant details.</p></div>', unsafe_allow_html=True)
        mode = st.radio('Input method', ['Use a demo transaction','Enter feature values manually'], horizontal=True)
        values = {c:0.0 for c in bundle['features']}
        source = 'Manual entry'
        if mode == 'Use a demo transaction':
            if demo.empty:
                st.error('Demo transaction file is missing. Run train_model.py to regenerate it.'); return
            choices = list(range(len(demo)))
            selected = st.selectbox('Select anonymised example', choices, format_func=lambda x: f"Example TX-{x+1:03d} · amount {demo.iloc[x]['Amount']:.2f}")
            row = demo.iloc[selected]
            values = {c:float(row[c]) for c in bundle['features']}
            source = f'Demo TX-{selected+1:03d}'
            st.caption('The sample is drawn from the held-out portion of the public dataset. The model prediction is calculated live when you click Analyse.')
        else:
            col1,col2 = st.columns(2)
            with col1:
                values['Amount'] = st.number_input('Transaction amount (dataset units)', min_value=0.0, value=120.0, step=10.0)
            with col2:
                values['Time'] = st.number_input('Time (seconds from first recorded transaction)', min_value=0.0, value=3600.0, step=60.0)
            with st.expander('Advanced anonymised features (V1–V28)', expanded=False):
                st.caption('Enter the PCA feature values supplied by your data source. Leave at 0 only if that is the actual feature value; arbitrary values can produce misleading results.')
                cols = st.columns(4)
                for i in range(1,29):
                    with cols[(i-1)%4]:
                        values[f'V{i}'] = st.number_input(f'V{i}', value=0.0, format='%.5f', key=f'v{i}')
        with st.expander('Review model input'):
            st.dataframe(pd.DataFrame([values]), use_container_width=True, hide_index=True)
        if st.button('🔍 Analyse transaction', type='primary', use_container_width=True):
            probability, prediction = predict(values, bundle)
            save_prediction(username, values['Amount'], probability, prediction, source)
            st.session_state.last_result = {'probability':probability,'prediction':prediction,'amount':values['Amount'],'source':source,'threshold':st.session_state.threshold}
        result = st.session_state.get('last_result')
        if result:
            st.markdown('---')
            if result['prediction'] == 1:
                st.markdown(f'''<div class="result-fraud"><h2 style="color:#fca5a5">⚠ Potential Fraud Detected</h2><h1>{result['probability']*100:.2f}%</h1><p>Estimated fraud probability · decision threshold {result['threshold']:.2f}</p><p><b>Recommended action:</b> Hold for manual review. Do not treat this model output as a final banking decision.</p></div>''', unsafe_allow_html=True)
            else:
                st.markdown(f'''<div class="result-safe"><h2 style="color:#6ee7b7">✓ Likely Legitimate</h2><h1>{result['probability']*100:.2f}%</h1><p>Estimated fraud probability · decision threshold {result['threshold']:.2f}</p><p>The model did not flag this transaction at the selected threshold. This does not guarantee that it is safe.</p></div>''', unsafe_allow_html=True)
            st.progress(min(max(result['probability'],0.0),1.0), text='Fraud probability')
            st.caption(f"Amount: {result['amount']:.2f} · Input: {result['source']} · A prediction has been saved to your history.")

    elif page == 'Transaction History':
        st.subheader('Your prediction log')
        if history.empty: st.info('No prediction history yet. Run a transaction check first.')
        else:
            view = history.copy(); view['Result'] = view.prediction.map({0:'Likely legitimate',1:'Potential fraud'}); view['Fraud probability']=(view.probability*100).round(2).astype(str)+'%'
            st.dataframe(view[['id','created_at','amount','Result','Fraud probability','source']], use_container_width=True, hide_index=True)
            csv = view.to_csv(index=False).encode('utf-8')
            st.download_button('Download history as CSV', csv, 'fraudguard_prediction_history.csv', 'text/csv')

    elif page == 'Analytics':
        st.subheader('Prediction analytics')
        if history.empty: st.info('Analytics will appear after you check some transactions.')
        else:
            c1,c2 = st.columns(2)
            counts = history.prediction.map({0:'Likely legitimate',1:'Potential fraud'}).value_counts().rename_axis('Result').reset_index(name='Count')
            with c1:
                st.markdown('**Prediction distribution**'); st.bar_chart(counts.set_index('Result'))
            with c2:
                st.markdown('**Fraud probability distribution**'); st.histogram if False else None
                st.bar_chart(pd.cut(history.probability, bins=[0,.1,.25,.5,.75,1.0], include_lowest=True).value_counts().sort_index())
            st.markdown('**Recent prediction trend**')
            trend = history.copy(); trend['date'] = pd.to_datetime(trend.created_at).dt.date
            trend = trend.groupby(['date','prediction']).size().unstack(fill_value=0).rename(columns={0:'Legitimate',1:'Potential fraud'})
            st.line_chart(trend)
            st.caption('Charts describe only the predictions recorded in this app account, not live bank-wide activity.')

    elif page == 'Model Information':
        st.subheader('Model and dataset information')
        st.markdown('<div class="card"><h3>Random Forest Classifier</h3><p class="muted">The model receives Time, Amount and 28 anonymised PCA features (V1–V28). Time and Amount are standardised using a scaler fitted on training data. The classifier returns a fraud probability; the configurable threshold converts it into a binary flag.</p></div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        c1.metric('Model', 'Random Forest'); c2.metric('Input features', '30'); c3.metric('Default threshold', '0.50')
        st.warning('Prototype model note: this downloadable web demo uses all fraud rows plus a 30,000-row random sample of legitimate transactions to keep the bundled training process practical. Its evaluation scores are not the same as the full-dataset results reported in the written report. Do not present these demo-model scores as the report results.')
        st.markdown('**Dataset fields**')
        st.write('Time · V1 to V28 · Amount · Class (0 = legitimate, 1 = fraud).')
        st.markdown('**Limitations**')
        st.write('- Input features are anonymised; ordinary customer/card details cannot be mapped to V1–V28.\n- The app is an academic demonstration, not a production banking system.\n- A low fraud probability does not guarantee a transaction is genuine.\n- Model decisions should be reviewed by a qualified analyst.')


ensure_demo_user()
bundle, demo = load_assets()
if bundle is None:
    st.error('Model file not found. Keep fraud_model.joblib in the same folder as app.py, then refresh.')
    st.stop()
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'username' not in st.session_state: st.session_state.username = ''
if st.session_state.authenticated:
    main_app(bundle, demo)
else:
    login_screen()
