# Transaction Risk Signal Monitor

An additional risk-signal monitor for PesaWay that checks synthetic transactions against explainable rules, assigns a risk score and labels each transaction as Low Risk, Review Required or High Risk. It only flags transactions for human review.

## Status

In development.Data models, admin and model tests are done. The risk rules are in progress. 

## Documentation

- [Project proposal](docs/proposal.md)

## Requirements

- Python 3.12 or newer. Django 6.1 does not run on older versions.
- Tested on Python 3.14.7

## Setup


1. Clone the repository and open the folder:

```
git clone https://github.com/wangari233/-risk-signal-monitor.git risk-signal-monitor
cd risk-signal-monitor
```

2. Create and activate a virtual environment.

Windows (PowerShell):

```
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS or Linux:

```
python3 -m venv venv
source venv/bin/activate
```

3. Install the dependencies:

```
pip install -r requirements.txt
```

4. Create the database tables:

```
python manage.py migrate
```

5. Start the development server:

```
python manage.py runserver
```

Then open http://127.0.0.1:8000 in your browser.

## Data

Synthetic data only. No real customer data, payment credentials or production systems are used.
