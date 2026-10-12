# automation/

Python scripts that do the work.

| File | What it does |
|---|---|
| `selector_recorder.py` | Watches you index one invoice by hand and writes down the internal names of the boxes you used. Never records what you type. |
| `invoice_recorder.py` | Reads the spreadsheet and types each invoice into Bottomline. Stops before Save. |
| `selectors_recorded.json` | Raw output of the recorder. Evidence, not used directly. |
| `selectors.json` | The clean field map, hand-checked. This is what the filling script reads. |

**Not yet built.** This is a placeholder. A full technical README covering every library and design decision is written once the scripts exist.

## Off limits
- `.bottomline_session.json` is a **credential**. Anyone holding it can act as you in Bottomline until it expires. Never share it, never open it.
