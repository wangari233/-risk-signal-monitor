**TRANSACTION RISK SIGNAL MONITOR PROJECT**

**Problem Statement**

Currently, PesaWay uses configurable, rule-based screening on both collections and payouts. These checks cover transaction limits, short-period volume, shared destinations, rapid corporate activity, unusually large first transactions and risk lists. Each decision records the triggered rule, the reason and the review outcome.

Some risk signals are not currently covered as screening rules such as repeated failed attempts. Duplicate references and failed provider transactions are controlled operationally but they are not tracked as part of an overall risk picture. Without visibility into these signals, unusual activity may be noticed afterwards. Unusual activity is a risk signal that needs investigation, not proof of fraud.

The ones affected in the company are:

- **PesaWay:** It will impact to financial loss, extra investigation work and reputational risk.

- **Corporates:** It will result to payments that are later reversed and exposure to misuse of their accounts.

- **Customers:** It results to being wrongly charged and having their accounts misused.

For this case I will build a Transaction Risk Signal Monitor that checks each transaction against a small set of explainable rules, assigns a risk score, and shows the triggered rules with a result of Low Risk, Review Required, or High Risk. It will only flag transactions for human review. It will not automatically block, accuse or penalize anyone.

The project uses synthetic data only and does not connect to production systems, real customer data or payment credentials.

**Selected Risk Signals**

The monitor checks each transaction against the rules below. Each triggered rule adds points to a risk score.

| **Number** | **Risk signal** | **What it detects** | **Activation** | **Points** |
|----|----|----|----|----|
| 1 | Repeated failed attempts. | Several failed attempts from one account to another in a short time. | 3 or more failed attempts within 10 minutes. You can flag only if the next attempt succeeds. | 30 |
| 2 | Duplicate reference. | The same transaction reference is submitted more than once. | A reference that already exists is submitted again. | 40 |
| 3 | Amount far from normal activity. | A transaction much larger than the account’s own usual activity. | Amount is more than 5 times the account’s average of previous successful transactions. | 25 |
| 4 | Rapid funding then payout. | Money coming in and going out immediately. | A payout of 80% or more of a recent deposit within 30 minutes. | 30 |

**Scoring and results**

The score is the sum of the points of all triggered rules limited at 100.

| **Score** | **Result**      |
|-----------|-----------------|
| 0 to 24   | Low Risk        |
| 25 to 59  | Review Required |
| 60 to 100 | High Risk       |

**Why each rule was chosen**

The rules were chosen because they are simple, explainable and testable with synthetic data.

1.  **Repeated failed attempts**

Many failed attempts followed by a success can suggest that someone is guessing details until one works.

3 failures in 10 minutes are above normal user error but still early enough to be useful.

2.  **Duplicate reference**

A repeated reference can mean that the same transaction reference is submitted more than once.

A reference that already exists is either a duplicate or it isn’t, which is why it carries the highest points.

3.  **Amount far from normal**

PesaWay’s current checks include fixed limits and unusually large first transactions. This rule compares a transaction with the account’s own history so it can catch an amount that is normal for one account but unusual for another.

4.  **Rapid funding then payout**

Money coming in and leaving almost immediately is a recognized risk pattern because it leaves little time for a problem to be noticed.

**Proposed Data Model**

The monitor stores incoming transactions and for each one, the risk assessment it produced, the individual rules that fired and the outcome of the human review.

1.  **Corporate**

| **Field** | **Type** | **Notes** |
|----|----|----|
| ID | Integer, Primary Key |  |
| Name | Text | Synthetic name only |
| created_at | Datetime | Used to tell new accounts from established ones. |

2.  **Transaction**

| **Field**   | **Type**                 | **Notes**                         |
|-------------|--------------------------|-----------------------------------|
| ID          | Integer, Primary Key     |                                   |
| Corporate   | Foreign key to corporate |                                   |
| Reference   | Text                     | Unique per saved transaction      |
| Type        | Choice                   | Collection or Payout              |
| Amount      | Decimal                  | Never a float                     |
| Currency    | Text                     | e.g. KES                          |
| Status      | Choice                   | Successful or Failed              |
| Destination | Text                     | Synthetic phone or account        |
| created_at  | Datetime                 | Used by all the time-window rules |

3.  **Submission Log**

| **Field**   | **Type**             | **Notes**                              |
|-------------|----------------------|----------------------------------------|
| ID          | Integer, Primary Key |                                        |
| Reference   | Text                 | Not unique, so repeats can be recorded |
| received_at | Datetime             |                                        |
| Accepted    | Boolean              | False if rejected as duplicate         |

4.  **Risk Assessment**

| **Field** | **Type** | **Notes** |
|----|----|----|
| ID | Integer, Primary Key |  |
| Transaction | One-to-one transaction |  |
| Score | Integer, 0 to 100 | Sum of triggered points that are restricted |
| Result | Choice | Low Risk, Review Required, High Risk |
| review_status | Choice | Pending, Confirmed, Cleared |
| review_note | Text, Optional | Reviewer’s comment |
| reviewed_at | Datetime, Optional |  |
| assessed_at | Datetime |  |

5.  **Triggered rule**

| **Field** | **Type** | **Notes** |
|----|----|----|
| ID | Integer, Primary Key |  |
| Assessment | Foreign key to Risk Assessment |  |
| rule code | Text | e.g. REPEATED_FAILURES, DUPLICATE_REF |
| Points | Integer |  |
| Reason | Text | Plain-language explanation, e.g. “4 failed attempts in 10 minutes” |

**Expected Inputs and Outputs**

**Inputs**

1.  **Transaction record**

| **Field**   | **Example**          | **Rules**                            |
|-------------|----------------------|--------------------------------------|
| Corporate   | “Corporate A”        | Must exist                           |
| Reference   | “TXN-000123”         | Required, text                       |
| Type        | Collection or Payout | Required                             |
| Amount      | 25000.00             | Required, decimal, greater than zero |
| Currency    | KES                  | Required                             |
| Status      | Successful or failed | Required                             |
| Destination | “0700000000”         | Synthetic only                       |
| created_at  | 2026-11-12 10.20.00  | Required                             |

2.  **Rule settings**

For example: failed attempts = 3, window = 10 minutes, points = 30

3.  **Transaction history**

The monitor reads earlier transactions and submissions for the same corporate to check the time-window rules, the average amount and duplicate references.

**How the data arrives:** Either one transaction at a time from a Comma-Separated Value file of synthetic transactions.

**Outputs**

| **Output** | **Example** |
|----|----|
| Score | 65 |
| Result | High Risk |
| Triggered rules | REPEATED_FAILURES (30), RAPID_FUNDING_PAYOUT (35) |
| Reason per rule | “4 failed attempts within 10 minutes”; “Payout was 90% of a deposit made 15 minutes earlier” |
| Review status | Pending |

**Error handling**

**Invalid input:** Is rejected with a clear message and not recorded as a normal transaction.

**Duplicate reference:** Is logged in Submission Log, flagged with the duplicate rile and no second transaction is created.

**New account with fewer than 5 transactions** skips the amount rule and the output says so.

**Exactly at a threshold** e.g. 3 failures triggers, 2 does not and tested.

**\**

**Testing Approach**

The monitor will be tested with synthetic data only.

**Tools:** Python with Django’s built-in test framework using a temporary test database so no demonstration is touched.

1.  **Unit tests for each rule**

| **Rule** | **Should activate** | **Should not activate** | **Boundary** |
|----|----|----|----|
| Repeated failed attempts | 3 failures within 10 minutes | 2 failures | Exactly 3 failures; failure at exactly 10 minutes |
| Duplicate reference | Same reference submitted twice | Two different references | Same reference after a long gap |
| Amount far from normal | 6 times the average with 5 or more past transactions | 2 times the average | Exactly 5 times the average; exactly 5 past transactions. |
| Rapid funding then payout | Payout of 90% of a deposit within 20 minutes | Payout of 50%; payout 2 hours later | Exactly 80% exactly 30 minutes |

2.  **Scoring and result tests**

- No rules activated gives score 0 and Low Risk.

- One rule gives its own points and the correct result.

- Several rules add up correctly.

- The score never goes above 100.

- Scores at the band edges (24, 25, 59, 60) give the correct result label.

3.  **Money correctness tests**

- Amounts are stored and compared as decimal never floats.

- Averages and percentages are computed without rounding errors.

- Zero, negative and extremely large amounts are handled correctly.

- Amounts with more than two decimal places are rejected or rounded in a defined way.

- The amount in the output matches the amount in the input exactly.

4.  **Failure tests**

- Missing or invalid fields are rejected with a clear error.

- Unknown corporate is rejected.

- Duplicate reference is logged and flagged and no second transaction is created.

- A new account with fewer than 5 past transactions skips the amount rule.

- Two transactions with the same timestamp.

- An empty history.

- A malformed row in a CSV file does not stop the rest of the batch.

5.  **Integration and end-to-end tests**

- A CSV file of synthetic transactions is processed from start to finish with the expected results compared to the actual results.

- A flagged transaction can be reviewed and the review is stored.

- The original transaction is never changed or deleted by the monitor.

6.  **Measuring how well the rules work**

Using a labelled synthetic dataset, record:

- How many risky transactions were flagged and how many were missed.

- How many normal transactions were flagged by mistake.

- What you changed after seeing the results and why.

**Synthetic Data Plan**

1.  **Rules for the data**

Corporate names are created e.g. Corporate A, Corporate B.

Phone numbers and accounts are fake patterns e.g. 0700000001.

References follow a made-up format e.g. TXN-000001

Amounts are decimal values with two decimal places in Kenyan Shillings.

2.  **Dataset structure**

| **Column** | **Purpose** |
|----|----|
| Corporate, reference, type, amount, currency, status, destination, created_at | The transaction input fields |
| expected_result | The result you expect is Low Risk, Reviewed Required or High Risk which is used to check the monitor’s output |
| Scenario | A short label such as normal or rapid_funding_payout so that you can see what each row is meant to test |

3.  **Scenarios to generate**

| **Scenario** | **What the data looks like** |
|----|----|
| Normal activity | Several corporates with regular collections and payouts as steady amounts. |
| Repeated failures | One account with 3 or more failed attempts in 10 minutes then a success. |
| Duplicate reference | The same reference is submitted twice. |
| Unusual amount | An account suddenly sending 6 times its average. |
| Rapid funding then payout | A deposit followed by a payout of 80% or more within 30 minutes |
| Combined risk | A transaction that activates two or more rules to test scoring and high risk. |
| Bad input | Missing fields, zero or negative amounts, unknown corporate and invalid dates |

4.  **Size**

> **Test fixtures:** A few rows per scenario written by hand so each test is easy to understand.
>
> **Demonstration dataset:** Around 200 to 500 generated transactions across 5 to 10 corporates with about 10 to 15 percent deliberately risky.

5.  **How the data is generated**

A Python script builds normal activity first.

It then inserts the risky scenarios at known points.

It writes the CSV with expected_result filled in.

Hand-written fixtures cover the boundary and bad-input cases, since exact values matter there.

6.  **Where it lives in the project**

<img src="media/image1.png" style="width:6.05833in;height:2.05833in" />

7.  **Limits**

- Synthetic data shows that the rules work as designed but it cannot show how accurate they would be on real PesaWay’s traffic.

- The proportion of risky data is invented and does not reflect real fraud rates.

- A possible next step beyond this project is to review the rules with Risk/Compliance or Operations using approved data.
