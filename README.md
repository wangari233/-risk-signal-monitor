# Transaction Risk Signal Monitor

An additional risk-signal monitor for PesaWay. It checks synthetic transactions against explainable rules, adds up a risk score, and labels each transaction Low Risk, Review Required or High Risk. It only flags transactions for human review. It never blocks or accuses anyone, and a flag is a risk signal, not proof of fraud.

## Status

In development. The data models, admin, scoring, three risk rules, the demo data and the demo command are built and tested. The duplicate reference rule is planned.

## Documentation

- [Project proposal](docs/proposal.md)

## How it works

Each transaction is run through every rule. Each rule that fires adds points, the total is capped at 100, and the total decides the label. The assessment is saved with one record per rule that fired, including a plain-language reason.

| Rule | Fires when | Points |
|---|---|---|
| Repeated failed attempts | The same corporate has 3 or more failed attempts within the 10 minutes up to and including this transaction | 30 |
| Amount far from normal | The amount is more than 5 times the average of the corporate's earlier successful transactions, and there are at least 5 of them | 25 |
| Rapid funding then payout | A successful payout is 80% or more of the successful collections in the 30 minutes before it | 35 |

| Score | Result |
|---|---|
| 0 to 24 | Low Risk |
| 25 to 59 | Review Required |
| 60 to 100 | High Risk |

All thresholds, windows, points and result bands are in `monitor/rule_settings.py`.

## Handling of money

- Amounts are stored and compared as exact decimals, never floats.
- A database rule rejects zero and negative amounts.
- Records are protected from deletion, and transactions are read-only in the admin.

## Requirements

- Python 3.12 or newer. Django 6.1 does not run on older versions.
- Tested on Python 3.14.7.

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

## Run the demonstration

The sample data is made up: 88 transactions across ten demo corporates. To check every row against its expected result, then undo everything:

```
python manage.py run_demo
```

Every row is validated before it is saved. The last lines should read:

```
Rows: 88 | Matched: 88 | Mismatched: 0 | Rejected: 0
Rolled back: nothing was saved.
```

To keep the data and browse the results in the admin:

```
python manage.py createsuperuser
python manage.py run_demo --keep
python manage.py runserver
```

Then open http://127.0.0.1:8000/admin and look at Risk assessments. Running `--keep` twice on the same database rejects every row, because references must be unique. Delete `db.sqlite3` and run `migrate` again to start over.

To recreate the sample file, run `python scripts/generate_data.py`. It uses a fixed seed, so the same file is produced every time.

## Run the tests

```
python manage.py test
```

## Project layout

```
config/                         Django settings
monitor/
  models.py                     transactions, assessments, triggered rules
  rules.py                      one function per rule
  scoring.py                    runs the rules and saves the assessment
  rule_settings.py              every threshold and point value
  admin.py                      read-only admin
  management/commands/run_demo.py
  tests.py, test_run_demo.py
scripts/generate_data.py        synthetic data generator
data/sample_transactions.csv    88 made-up transactions
docs/proposal.md                project proposal
```

## Data

Synthetic data only. No real customer data, payment credentials or production systems are used.