PROJECT: Rule-Based Invoice Boundary Detection Engine

[Content]

Objective Build a Python-based, rule-driven invoice boundary detection
engine.

The first objective is NOT to split PDFs. Instead, determine where each
invoice starts within a multi-invoice PDF and validate prediction
accuracy before enabling automatic splitting.

Problem Statement - OneDrive receives PDFs. - Each PDF may contain one
or multiple invoices. - Invoice lengths vary and are unknown. - Goal:
identify every page where a new invoice begins.

Development Philosophy Do not begin by splitting PDFs. First answer:
“Does this page belong to the current invoice or does a new invoice
begin here?”

Development Roadmap

Phase 1 – OCR & Text Extraction - Read every page. - OCR where needed. -
Preserve page order. - Store extracted text.

Phase 2 – Feature Extraction Extract fields such as: - Invoice Number -
Vendor Name - Invoice Date - PO Number - Customer Name - Invoice Total -
Currency - Bill To / Ship To - Tax ID - Payment Terms

Phase 3 – Rule Engine Independent rules, not long if-else chains.
Examples: - Invoice number changed? - Vendor changed? - Continuation
page? Each rule returns a score.

Phase 4 – Confidence Engine Combine scores from all rules. Example:
Invoice Number Changed +100 Vendor Changed +40 Invoice Header +30 Same
Vendor -20 Continuation Pattern -40

Decision thresholds determine Break Here vs Continue.

Phase 5 – Prediction Mode Do NOT split PDFs. Generate Excel
containing: - PDF Name - Page Number - Prediction (Break / Continue) -
Confidence - Score - Triggered Rules

Each prediction should explain WHY it was made.

Human Validation Compare script predictions against manual review to
create ground truth.

Accuracy Metrics - Total Pages - Total Boundaries - Correct
Predictions - False Positives - False Negatives - Precision - Recall -
F1 Score - Boundary Detection Accuracy

Review Mode High-confidence predictions: Auto-approved

Low-confidence predictions: Manual Review

Phase 6 – PDF Splitting Only after achieving consistently high
accuracy: - Use predicted boundaries. - Split into separate invoice
PDFs.

Exception Handling Support: - Blank pages - OCR failures - Rotated
pages - Landscape pages - Separator sheets - Credit notes - Statements -
Packing slips - Duplicate pages - Missing pages - Low OCR confidence -
Mixed invoice formats

Design Principles - Modular - Extensible - Easy to test - Easy to
debug - Configuration-driven - Well documented

Future Enhancements - AI document understanding - Machine learning -
Vendor-specific rules - OneDrive automation - OCR providers -
Buildertrend/Nexus integration - Human review UI - Analytics dashboard

Success Criteria 1. Read multi-invoice PDFs. 2. Analyze every page. 3.
Predict invoice boundaries. 4. Explain predictions. 5. Export Excel for
validation. 6. Measure accuracy. 7. Enable splitting only after
validation.

Before Coding Design: - Folder structure - Modules - Data models -
Configuration - Logging - Testing - Plug-in rule architecture
