# AW Client Report Portal — V1 demo

Internal portal that replaces EF's full-day quarterly SACS + TCC report prep.
Three-person team, ~6 clients, all data entered manually.

## Run

```bash
# one-time
brew install cairo pango gdk-pixbuf libffi
python3 -m pip install -r requirements.txt

# every time
./run.sh            # starts http://127.0.0.1:5050
```

The `run.sh` wrapper exports `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` so
WeasyPrint can find pango/cairo on Apple-Silicon Macs.

## Seed an example client

```bash
python3 seed.py     # wipes portal.db and seeds The Example Family
```

## Architecture

| Layer        | What                                               |
|--------------|----------------------------------------------------|
| `app.py`     | Flask routes (clients, reports, PDFs)              |
| `db.py`      | sqlite3 helpers                                    |
| `schema.sql` | `clients`, `accounts`, `insurance_deductibles`, `reports`, `account_balances` |
| `calculations.py` | Pure functions: `compute_sacs`, `compute_tcc`, `calc_age` |
| `pdf_generator.py`| Jinja2 + WeasyPrint renderer                  |
| `templates/`      | Server-rendered HTML (Jinja2)                |
| `templates/pdf/`  | SACS + TCC PDF templates (HTML + inline SVG) |
| `static/style.css`| Portal UI                                    |
| `static/pdf.css`  | PDF stylesheet                               |
| `seed.py`        | Demo seed                                     |

## Calculation rules (locked from the customer call, verbatim)

- **SACS excess** = Inflow − Outflow
- **Private Reserve target** = 6 × monthly expenses + Σ insurance deductibles
  (override available at client level)
- **TCC Client 1 / 2 Retirement Total** = Σ retirement balances for that spouse
- **TCC Non-Retirement Total** = Σ non-retirement accounts. **Trust NOT added in.**
- **Grand Total Net Worth** = C1 Retirement + C2 Retirement + Non-Retirement + Trust
- **Liabilities** are shown separately and **NOT subtracted** from net worth

## V1 scope

- Client profiles (single + married)
- Variable account list (retirement / non-retirement / liability, per-spouse or joint)
- Insurance deductibles
- Quarterly report form with last-quarter "use last" chips
- Live totals as you type
- SACS PDF (bubble diagram + page 2 long-term cashflow)
- TCC PDF (variable layout: 1–6 retirement per spouse, joint + solo non-retirement, liabilities table, grand total)

## V1 explicitly excluded (per PRD + customer call)

- Canva export
- Dropbox auto-save
- Monthly email distribution
- Live integrations (RightCapital / Schwab / Pinnacle / Zillow API)
- Authentication (internal-only)
