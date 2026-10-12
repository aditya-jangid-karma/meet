"""Talk to the local Qwen model for UTILITY BILLS. Images in, one JSON object out. Local AI only."""
import json
import urllib.request

MODEL = "qwen2.5vl:7b"
NUM_CTX = 32768
REQUEST_TIMEOUT = 180

REQUIRED = ("_reasoning", "vendor", "account_number", "invoice_date", "current_charges", "service_address", "service_period_start", "service_period_end", "utility_type")

def build_schema():
    return {
        "type": "object",
        "properties": {
            "_reasoning": {
                "type": "string",
                "description": "Explain logic for finding account number, service address, dates, and specifically how you calculated current_charges by EXCLUDING past due balances. If there is a late fee, state it."
            },
            "vendor": {"type": "string"},
            "account_number": {"type": "string"},
            "invoice_date": {"type": "string"},
            "due_date": {"type": ["string", "null"]},
            "current_charges": {
                "type": "string",
                "description": "The pure CURRENT charges for this period + any current Late Fees/Miscellaneous. Exclude 'Balance Forward', 'Previous Balance', and 'Past Due'."
            },
            "late_fee": {
                "type": ["string", "null"],
                "description": "Any late fee, miscellaneous fee, or deposit charge printed on the bill. Null if none."
            },
            "service_address": {
                "type": "string",
                "description": "The physical address receiving the service. Often labeled 'Service Address' or 'Service At'. Do not use the mailing address."
            },
            "service_period_start": {"type": "string", "description": "MM/DD/YYYY"},
            "service_period_end": {"type": "string", "description": "MM/DD/YYYY"},
            "utility_type": {
                "type": "string",
                "enum": ["Electric", "Gas", "Water", "Trash", "Phone/Internet", "Other"]
            }
        },
        "required": list(REQUIRED),
        "additionalProperties": False,
    }

def build_prompt(alias_examples=None):
    prompt = (
        "You are reading ONE utility bill, shown as page image(s). Return ONLY the "
        "fields in the schema. In the _reasoning field, briefly explain your "
        "step-by-step logic for identifying the account number, service address, "
        "and exactly how you determined the current_charges by EXCLUDING any past due balances. "
        "vendor = the utility company (e.g. Pepco, Washington Gas, WSSC, Verizon). "
        "account_number = the main account number. Keep all digits and hyphens. "
        "invoice_date = the bill date or issue date. "
        "current_charges = ONLY the charges for the current billing period. Exclude 'Balance Forward', 'Previous Balance', and 'Past Due'. If the bill lists 'Current Charges' and 'Late Fees' separately, add them together. If there is an overall account credit making the bill negative or $0, but the current charges for usage exist, extract the current charges. "
        "late_fee = any late fee, miscellaneous fee, or deposit charge listed. Use null if none. "
        "service_address = the physical property address receiving the service. "
        "service_period_start / service_period_end = the start and end dates of the billing cycle, usage period, or cycle from/to. "
        "Write every date as MM/DD/YYYY (US format). Do not invent values."
    )
    if alias_examples:
        lines = [
            '- you read "{}" but the correct vendor is "{}"'.format(raw, correct)
            for raw, correct in alias_examples
        ]
        prompt += (
            "\n\nKNOWN CORRECTIONS -- you have misread these vendors before. "
            "If the invoice is from the same seller, use the corrected "
            "name:\n" + "\n".join(lines)
        )
    return prompt

def _post(host, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        host.rstrip("/") + "/api/generate", data=data,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))

def _parse(envelope):
    try:
        obj = json.loads(envelope.get("response", ""))
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError(f"reply was not JSON: {error}")
    missing = [k for k in REQUIRED if not obj.get(k)]
    if missing:
        raise ValueError(f"reply missing {missing}")
    obj.setdefault("due_date", None)
    obj.setdefault("late_fee", None)
    return obj

def extract_utility_invoice(host, images, post=_post, alias_examples=None):
    payload = {
        "model": MODEL,
        "prompt": build_prompt(alias_examples),
        "images": images,
        "stream": False,
        "format": build_schema(),
        "options": {"num_ctx": NUM_CTX},
    }
    for _ in range(2):
        try:
            return _parse(post(host, payload))
        except ValueError:
            continue
    return None

