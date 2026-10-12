# QuickBooks Online Purchase Order & Sales Estimate Automation

Automated pipeline for international textile order processing, integrating **Email Intake**, **Azure AI Document Intelligence**, **Google Sheets**, and **QuickBooks Online (QBO)**.

Built in exact accordance with:
* **Report 1**: Full Automation Plan (PO + QBO Estimate / Proforma Invoice)
* **Report 2**: Existing Process SOP (Purchase Order + Sales Estimate / Proforma Invoice)

---

## Architecture Overview

```
[Vendor PI / PDF] ──► [Azure AI Doc Intelligence] ──► [Structured JSON]
                                                              │
                                                              ▼
                                               [Google Sheets: PROFORMAS]
                                                              │
                                                              ▼
                                                  [10 Validation Gates]
                                                   ├── Fail ──► [Alert / Slack / Teams]
                                                   └── Pass ──► [Duplicate Check]
                                                                      │
                                                ┌─────────────────────┴─────────────────────┐
                                                ▼                                           ▼
                                    [QBO Purchase Order]                        [QBO Sales Estimate]
                                    - Supplier & Cost                           - Customer: T3 TEXTILES S.A.S
                                    - Attach source PDF                         - Standard Production Notes
                                                                                - Customer Sales Rate
                                                └─────────────────────┬─────────────────────┘
                                                                      ▼
                                                       [Update G Sheet PI # Cell]
                                                                      │
                                                                      ▼
                                                         [SQLite Control Log Entry]
```

---

## Key Features & Safety Guardrails

1. **Non-Invasive Google Sheet Integration**:
   - Zero modifications to the client's spreadsheet columns, headers, or structure.
   - Looks up row by `Order #` and updates only the designated Estimate/PI cell.
2. **10 Deterministic Validation Gates**:
   - Gate 1: Supplier Verification (PDF vs. Master Sheet vs. QBO)
   - Gate 2: Order # Exact Match
   - Gate 3: Item Resolution (Master sheet item code governs)
   - Gate 4: Standardized Description Verification
   - Gate 5: Quantity Verification (Tolerance $\le$ 0.01)
   - Gate 6: Purchase Rate Verification (Tolerance $\le$ 0.005)
   - Gate 7: Customer Margin Check (`Customer Price` $\ge$ `Supplier Price`)
   - Gate 8: Shipping Route Verification (From, To, Ship Via present)
   - Gate 9: Duplicate Transaction Guard (Halts if order already posted)
   - Gate 10: QBO Master Entities Verification
3. **Dual Execution Options**:
   - **Standalone Python Service / CLI**: Run locally, via scheduled cron, or backend webhook.
   - **n8n Workflow Engine**: Importable visual workflow JSON (`workflows/n8n_qbo_po_estimate_workflow.json`).

---

## Directory Structure

```
qbo-po-estimate-automation/
├── config/
│   ├── .env.example              # Sample environment configuration
│   └── settings.py               # Settings loader & constants
├── core/
│   ├── models.py                 # Dataclasses & typed schemas
│   └── validator.py              # 10 Validation Gates logic
├── services/
│   ├── azure_doc_intel.py        # Azure Document Intelligence & PDF extraction
│   ├── google_sheets.py          # Google Sheets PROFORMAS tab integration
│   ├── qbo_client.py             # QuickBooks Online API (PO, Estimate, Attachments)
│   ├── audit_logger.py           # SQLite automation control log (isolated)
│   └── alerter.py                # Slack / Teams / Email exception dispatcher
├── pipeline/
│   └── orchestrator.py           # Master 13-stage workflow orchestrator
├── workflows/
│   └── n8n_qbo_po_estimate_workflow.json # Ready-to-import n8n workflow
├── samples/
│   └── sample_order_7207.json    # Reference Order 7207 from SOP
├── tests/
│   ├── test_validation.py        # Unit tests for validation gates
│   ├── test_orchestrator.py      # Integration test for end-to-end flow
│   └── run_tests.py              # Test runner script
├── main.py                       # CLI application entrypoint
├── requirements.txt              # Python dependencies
└── README.md
```

---

## Quick Start & Verification

### 1. Run Reference Test (Order 7207)
You can run the full end-to-end pipeline with the reference order from Report 2 out of the box:

```bash
python main.py run-sample
```

**Expected output:**
* Evaluates all 10 validation gates (`PASS`).
* Simulates QBO Purchase Order creation (`AT-26209`).
* Generates QBO Sales Estimate (`#1793`) for customer `T3 TEXTILES S.A.S` with fixed production notes.
* Updates Google Sheet cell with `#1793`.
* Commits run into SQLite control log.

### 2. View Audit Log History
```bash
python main.py history
```

### 3. Run Test Suite
```bash
python tests/run_tests.py
```
*(All 7 unit and integration tests will execute and verify pass/fail boundary conditions).*

---

## Configuration for Production

1. Copy `.env.example` to `.env`:
   ```bash
   cp config/.env.example .env
   ```
2. Fill in credentials:
   * **Azure Document Intelligence**: Endpoint & API Key.
   * **Google Sheets**: Spreadsheet ID & Service Account JSON credentials file path.
   * **QuickBooks Online**: Client ID, Client Secret, Realm ID, and Refresh Token.
   * **Slack/Teams Webhook**: For automated exception alerts.

---

## n8n Integration

To run using n8n:
1. Open your n8n workspace.
2. Select **Workflows** $\rightarrow$ **Import from File**.
3. Select `workflows/n8n_qbo_po_estimate_workflow.json`.
4. Configure your credentials for Gmail, Azure AI, Google Sheets, and QuickBooks Online.
