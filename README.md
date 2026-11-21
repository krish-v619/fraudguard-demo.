# FraudGuard — Credit Card Fraud Detection Demo

A Streamlit demonstration app for an academic credit-card fraud detection project. It uses an included trained model and anonymised demo transactions. It is not connected to banks or payment networks and must not be used for real financial decisions.

## Deploy on Streamlit Community Cloud

1. Create a new **public** GitHub repository named `fraudguard-demo` (or another name).
2. Upload all files in this folder to the repository root (not the enclosing ZIP folder).
3. Open https://share.streamlit.io/ and sign in with GitHub.
4. Choose **Create app**, select your repository, branch `main`, and main file path `app.py`.
5. Click **Deploy** and wait for dependencies to install.
6. Streamlit will provide a public `*.streamlit.app` URL.

## Demo login

- Login ID: `admin@fraudguard.demo`
- Password: `Fraud@123`

Change or remove demo credentials before using any public-facing deployment. This is a classroom prototype, not a production authentication system.

## Included files

- `app.py` — Streamlit application
- `fraud_model.joblib` — trained model bundle
- `demo_transactions.csv` — anonymised demo records
- `dataset_summary.json` — dataset summary
- `requirements.txt` — Python dependencies

The prediction model expects the anonymised dataset feature format (Time, Amount, and V1–V28). Do not enter real card numbers or personal banking data.
