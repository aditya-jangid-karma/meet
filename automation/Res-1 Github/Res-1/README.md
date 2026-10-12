# Res-1

# Invoice Indexer — how it fits together

Four diagrams, for anyone picking this project up. No engineering background needed.
Every diagram is a Mermaid block: GitHub, VS Code (with a Mermaid extension) and
mermaid.live all render these as pictures rather than text.

---

## 1. End-to-end pipeline

The project is two halves that meet in the middle at one spreadsheet. The READER
turns PDFs into rows. The RECORDER types those rows into Bottomline and stops.

```mermaid
flowchart TB
    subgraph READ["READER - Qwen fills the spreadsheet"]
        A["Invoice PDFs<br/>Z drive, input/pdfs"] --> B["reader_pdf.py<br/>renders pages to PNG<br/>200 DPI, max 3 pages"]
        B --> C["reader_qwen.py<br/>the ONLY file that touches the network"]
        C <--> D[("Ollama and qwen2.5vl:7b<br/>local AI, never a cloud endpoint")]
        C --> E["invoice_reader.py<br/>writes one row per invoice"]
        E --> F["vendor_lookup.py<br/>match the name"]
        F --> G["master_index.py<br/>fetch the code"]
        G --> E
    end

    subgraph REC["RECORDER - types the sheet into Bottomline"]
        H["invoice_recorder.py<br/>Playwright driving Chromium"] --> I["queue_navigator.py<br/>finds Images to be Indexed"]
        H --> J["fill_plan.py<br/>which package, and in what order"]
    end

    M[("masters folder<br/>vendors.csv, properties.csv, aliases.csv")] --> F
    M --> G
    M --> H
    E --> X[("invoices.xlsx<br/>Invoices sheet")]
    X --> H
    H --> K["Bottomline Nexus<br/>image indexing screen"]
    K --> STOP["STOPS before Convert to Invoice<br/>a human checks it and presses Convert"]
```

---

## 2. Module map — which file uses which

The middle box is the important one: that logic has no browser and no network, so it
can be proved correct on a laptop with the `selftest_*.py` scripts.

```mermaid
flowchart LR
    subgraph entry["Entry points - the two .bat launchers"]
        IREAD["invoice_reader.py"]
        IREC["invoice_recorder.py"]
    end
    subgraph shared["Shared matching - no browser, no network, provable offline"]
        VL["vendor_lookup.py"]
        MID["master_index.py"]
    end
    subgraph ro["Reader only"]
        RPDF["reader_pdf.py"]
        RQ["reader_qwen.py"]
        RD["reader_directory.py"]
        PQ["probe_qwen.py<br/>diagnostic, not part of a run"]
    end
    subgraph rc["Recorder only"]
        FP["fill_plan.py"]
        QN["queue_navigator.py"]
    end

    IREAD --> RPDF
    IREAD --> RQ
    IREAD --> RD
    IREAD --> VL
    IREAD --> MID
    IREC --> FP
    IREC --> QN
    IREC --> VL
    IREC --> MID
    FP --> MID
    MID --> VL
    PQ --> RQ
```

---

## 3. How a name becomes a code — the safety rule

A name is only ever **replaced** on a confident match, and never **erased** for failing
to match. An uncertain name can never drag a confident-looking code along with it.

```mermaid
flowchart TD
    S["Raw name Qwen read"] --> Q1{"Blank or null?"}
    Q1 -->|yes| BLANK["Cell left blank<br/>NEEDS_REVIEW"]
    Q1 -->|no| Q2{"Known correction<br/>in aliases.csv?"}
    Q2 -->|yes| OK1["Use the corrected name<br/>READ_OK"]
    Q2 -->|no| Q3{"Exact match in the master?<br/>ignoring case and spaces"}
    Q3 -->|yes| OK2["Use the master spelling<br/>READ_OK"]
    Q3 -->|no| Q4{"Similar to a master name?<br/>0.90 similarity"}
    Q4 -->|yes| RV1["Keep the RAW name<br/>NEEDS_REVIEW plus a suggestion"]
    Q4 -->|no| RV2["Keep the RAW name<br/>NEEDS_REVIEW"]

    OK1 --> CODE["master_index.py<br/>look up ERP Vendor ID or Property Code"]
    OK2 --> CODE
    RV1 --> NOCODE["No code written<br/>a blank cell is your review queue"]
    RV2 --> NOCODE
    BLANK --> NOCODE
    CODE --> W["Vendor Code or Property Code<br/>written into the sheet"]
```

---

## 4. Recorder phases — how the package is proved

The script never assumes an invoice belongs to Yardi or Intacct. It proves it: a
property only appears in the dropdown if it belongs to the package on screen, so that
dropdown is the test.

```mermaid
flowchart TD
    ST["Open the indexing screen"] --> V{"Image Name on screen<br/>matches the spreadsheet row?"}
    V -->|no| STOPX["STOP<br/>this is what makes it impossible to index<br/>one vendor's invoice against another's document"]
    V -->|yes| PA["PHASE A - prove the integration package"]

    PA --> P1["Select YARDI or INTACCT"]
    P1 --> P2["Type the property"]
    P2 --> P3{"Dropdown matches?"}
    P3 -->|exactly 1| CONF["CONFIRMED<br/>a property only appears if it<br/>belongs to this package"]
    P3 -->|more than 1| AMB["Ambiguous<br/>the operator picks in the browser"]
    P3 -->|none| NEXT["Not under this package<br/>try the other one"]
    NEXT --> P1

    CONF --> PB["PHASE B - the vendor<br/>ERP Vendor ID first, name as fallback"]
    AMB --> PB
    PB --> PC["PHASE C - invoice number, dates, amount"]
    PC --> FIN["Boxes filled, then STOPS<br/>never clicks Convert, Save or Delete"]
```

---

## Notes on accuracy (as of 2026-09-07)

- `probe_qwen.py` is a diagnostic tool, not part of a normal run.
- In Phase B the code-first path is wired for **vendors only**. The Property Code box
  is not connected yet, so properties are still searched by name.
- Property codes exist for **Yardi properties only** (16 of 152). Intacct properties
  have no code and are always matched by name — that is correct, not a gap.
