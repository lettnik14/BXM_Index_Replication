# BXM Index Replication

Python implementation for replicating the daily **BXM index level** from an Excel input workbook.

The script reads daily market and option-related inputs, determines whether each observation is a roll date, calculates the appropriate daily return, and compounds those returns into a replicated BXM index level.

> **Note:** This project implements the methodology represented by the supplied input data and formulas. It is intended as a research/replication tool and is not an official calculation agent for the BXM index.

---

## Project Overview

The replication uses two calculation paths:

* **Non-roll dates**
* **Roll dates**

For non-roll dates, the daily return is calculated as:

```text
1 + R_t = (S_t + Div_t - C_t) / (S_{t-1} - C_{t-1})
```

For roll dates, the total return is decomposed into three components:

```text
1 + R_t = (1 + R_a)(1 + R_b)(1 + R_c)
```

Where:

```text
R_a = (SSOQ_t + Div_t - CSettle) / (S_{t-1} - C_{t-1}) - 1

R_b = SVWAV / SSOQ_t - 1

R_c = (S_t - C_t) / (SVWAV - CVWAP) - 1
```

The three roll components are stored separately as:

* `retA`
* `retB`
* `retC`

The combined daily return is stored as:

* `ret`

The resulting replicated index level is stored as:

* `Index close`

---

## Files

A typical repository structure is:

```text
BXM/
│
├── bxm_index_replication.py
├── BXM.xlsx
├── BXM_replication_output.xlsx
├── README.md
├── requirements.txt
└── .gitignore
```

The input and output Excel workbooks are optional repository files depending on whether the underlying market data is appropriate to distribute.

---

## Requirements

* Python 3.10+
* pandas
* openpyxl

Install the dependencies with:

```bash
pip install pandas openpyxl
```

Or, if a `requirements.txt` file is included:

```bash
pip install -r requirements.txt
```

---

## Input Workbook

The script expects an Excel workbook containing the following columns:

```text
date
expr_date
spx_10am
soq
settle
k
vwap
spx_vwap
spx_close
div
bid
ask
mid
retA
retB
retC
ret
Index close
```

The calculation validates the following required input fields:

```text
date
spx_10am
soq
settle
k
vwap
spx_vwap
spx_close
div
bid
ask
mid
```

Some fields are retained as part of the supplied dataset even though they are not directly used in every calculation step.

---

## Running the Replication

With the default filenames:

```bash
python bxm_index_replication.py
```

The script expects:

```text
BXM.xlsx
```

and creates:

```text
BXM_replication_output.xlsx
```

### Specify an input and output file

```bash
python bxm_index_replication.py \
    --input BXM.xlsx \
    --output BXM_replication_output.xlsx
```

### Specify a different starting index level

```bash
python bxm_index_replication.py \
    --input BXM.xlsx \
    --output BXM_replication_output.xlsx \
    --initial-index 2517.98
```

---

## Initial Index Level

The default starting index level is:

```text
2517.98
```

This represents the supplied **August 20, 2026 anchor** used by the replication.

The first observation is assigned:

```text
ret = 0.0
Index close = 2517.98
```

Subsequent index levels are compounded from the calculated daily returns.

---

## Calculation Process

### 1. Load the workbook

The script reads the Excel workbook using pandas:

```python
df = pd.read_excel(input_file)
```

### 2. Validate required fields

The script checks that all required columns are present.

If a required column is missing, execution stops with an error identifying the missing fields.

### 3. Clean and sort dates

The `date` column is converted to pandas datetime values.

Invalid dates are removed, and the observations are sorted chronologically.

### 4. Determine option expiration

For each observation, the script determines the applicable third-Friday expiration date.

If the observation occurs before or on the third Friday, that month's third Friday is used.

If the observation occurs after the third Friday, the following month's third Friday is used.

The resulting expiration date is stored in:

```text
expr_date
```

### 5. Identify roll observations

A row is treated as a roll observation when all of the following fields contain values:

```text
soq
settle
vwap
spx_vwap
```

The roll calculation is then applied.

### 6. Calculate daily return

For non-roll observations:

```text
ret = ((spx_close + div - mid) /
       (previous_spx_close - previous_mid)) - 1
```

For roll observations, the three component returns are calculated and compounded:

```text
retA
retB
retC
```

followed by:

```text
ret = (1 + retA)(1 + retB)(1 + retC) - 1
```

### 7. Compound the index

The index level is updated using:

```text
Index_t = Index_(t-1) × (1 + ret_t)
```

The resulting value is stored in:

```text
Index close
```

### 8. Export results

The completed DataFrame is written to the specified output workbook.

---

## Output

The output workbook retains the supplied market data and adds/calculates:

| Field         | Description                         |
| ------------- | ----------------------------------- |
| `expr_date`   | Applicable option expiration        |
| `retA`        | First roll-period return component  |
| `retB`        | Second roll-period return component |
| `retC`        | Third roll-period return component  |
| `ret`         | Total daily return                  |
| `Index close` | Replicated BXM index level          |

The script also prints a summary to the terminal:

```text
      date expr_date       ret  Index close
2026-08-20 ...
2026-08-21 ...
...
```

---

## Methodology

The implementation separates ordinary daily index movement from the roll process.

### Non-roll observations

The non-roll calculation uses the underlying SPX close, option-related mid value, and dividend adjustment:

```text
1 + R_t = (S_t + Div_t - C_t) / (S_{t-1} - C_{t-1})
```

### Roll observations

The roll is decomposed into three sequential components:

```text
1 + R_t = (1 + R_a)(1 + R_b)(1 + R_c)
```

This allows the contribution of each stage of the roll to be inspected independently.

---

## Error Handling

The script raises an error when required columns are missing.

It also checks for missing numerical inputs needed for the applicable calculation.

For example:

```text
ValueError:
Missing numeric value required for roll calculation on YYYY-MM-DD
```

This is intended to prevent the replication from silently producing an index level from incomplete input data.

---

## Reproducibility

The replication is deterministic given:

1. The same input workbook
2. The same initial index level
3. The same Python/pandas calculation environment

The output should therefore be reproducible from the supplied inputs.

---

## Development Notes

The implementation is intentionally kept relatively transparent so that the calculation process can be reviewed against the underlying methodology.

Key areas of the implementation include:

```python
_third_friday()
```

Determines the third Friday associated with an observation.

```python
calculate_bxm()
```

Runs the complete replication process.

```python
_as_number()
```

Validates numerical inputs before they enter the calculations.

---

## Validation

For validation, the calculated output should be reviewed at several levels:

### Data validation

Confirm that:

* Dates are correctly ordered.
* Required fields are populated.
* Roll observations contain the necessary roll inputs.
* Numerical fields contain valid values.

### Return validation

Review:

```text
retA
retB
retC
ret
```

on roll observations.

Confirm that:

```text
(1 + retA)(1 + retB)(1 + retC) - 1
```

matches the reported `ret`.

### Index validation

Confirm that:

```text
Index_t = Index_(t-1) × (1 + ret_t)
```

for every observation after the initial anchor.

---

## Disclaimer

This repository is a technical implementation for research, educational, and replication purposes.

It is not affiliated with or endorsed by the relevant index provider unless explicitly stated elsewhere in the repository.

The calculations depend on the quality, completeness, and interpretation of the supplied input data and methodology.

---

## Author

Developed as a Python-based financial market index replication project, with an emphasis on:

* Financial data processing
* Index methodology implementation
* Derivatives and options data
* Return calculation
* Excel/Python workflow automation
* Reproducible quantitative research
