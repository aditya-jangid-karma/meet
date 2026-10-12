"""Talk to the local Qwen model (qwen2.5vl:7b via Ollama). Images in, one JSON
object out. This is the ONLY file that reaches the network. Local AI only --
never a cloud endpoint (see the spec's privacy line).
"""
import json
import urllib.request

MODEL = "qwen2.5vl:7b"
NUM_CTX = 32768            # measured; smaller silently truncates page images
REQUEST_TIMEOUT = 180      # seconds; a 3-page invoice can take ~2 minutes

REQUIRED = ("_reasoning", "vendor", "invoice_number", "invoice_date", "amount")


def build_schema():
    """Ollama 'format' schema. due_date and property are nullable and NOT
    required."""
    return {
        "type": "object",
        "properties": {
            "_reasoning": {
                "type": "string",
                "description": "Explain your logic step-by-step for finding the vendor, dates, and property BEFORE filling out the other fields."
            },
            "vendor": {"type": "string"},
            "invoice_number": {"type": "string"},
            "invoice_date": {"type": "string"},
            "due_date": {"type": ["string", "null"]},
            "amount": {"type": "string"},
            "property": {
                "type": ["string", "null"],
                "description": "The name of the property or building being billed. Extract only the short property name (e.g. 'Battery Lane' or 'Victory Court'). DO NOT include the street address, city, or zip code."
            },
        },
        "required": list(REQUIRED),
        "additionalProperties": False,
    }


def build_prompt(alias_examples=None):
    """The instructions sent to Qwen alongside the page image(s).

    `alias_examples` is an optional list of (raw, correct) pairs -- past
    human corrections from masters\\aliases.csv (see
    vendor_lookup.load_alias_examples), already capped by the caller. When
    given, we append a short "known corrections" block naming the vendors
    Qwen has misread before, so it can get the name right at the SOURCE
    instead of a human catching it every time.

    This is a NUDGE only, not a bypass: even if Qwen now writes the
    corrected name straight away, invoice_reader.py still runs it through
    vendor_lookup.Lookup exactly as before -- alias/exact matches pass
    through, anything else still lands in NEEDS_REVIEW for a human to check.
    The nudge can only reduce how often a human has to fix the same typo
    twice; it can never make a name skip review on its own say-so.

    When alias_examples is None or empty, this returns the EXACT original
    prompt text, unchanged."""
    prompt = (
        "You are reading ONE invoice, shown as page image(s). Return ONLY the "
        "fields in the schema. In the _reasoning field, briefly explain your "
        "step-by-step logic for identifying the vendor, the date, and the "
        "property BEFORE you output the other fields. "
        "vendor = the company that ISSUED the invoice "
        "(the seller / remit-to payee), never the customer being billed. "
        "invoice_number and amount as printed. amount = the invoice total. "
        "due_date ONLY if a due date is printed; otherwise null. Write every "
        "date as MM/DD/YYYY (US format). Keep any leading zeros in "
        "invoice_number. "
        "property = the name of the property or building being billed. ONLY "
        "extract the short property name (e.g. 'Battery Lane' or 'Victory Court'). "
        "DO NOT include the street address, city, or zip code, even if printed "
        "next to the name. If the invoice shows BOTH a Bill To and a Ship To, "
        "take property from the SHIP TO. If no distinct property name is shown, "
        "use null. Do not invent values."
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
    """The single HTTP boundary (monkeypatched in tests). Returns Ollama's
    parsed JSON envelope, whose 'response' field holds the model's text."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        host.rstrip("/") + "/api/generate", data=data,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse(envelope):
    """Pull the model's JSON out of the envelope and validate required keys.
    Raises ValueError if it will not parse or a required field is missing."""
    try:
        obj = json.loads(envelope.get("response", ""))
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError(f"reply was not JSON: {error}")
    missing = [k for k in REQUIRED if not obj.get(k)]
    if missing:
        raise ValueError(f"reply missing {missing}")
    obj.setdefault("due_date", None)
    obj.setdefault("property", None)
    return obj


def extract_invoice(host, images, post=_post, alias_examples=None):
    """One invoice -> its fields, or None if Qwen's reply is unusable twice.
    None means 'send to human review'; the caller writes nothing for it.

    alias_examples is passed straight through to build_prompt() -- see its
    docstring. It only nudges what Qwen writes; vendor_lookup.Lookup still
    validates the result afterwards, so this can never let a name skip
    human review on its own."""
    payload = {
        "model": MODEL,
        "prompt": build_prompt(alias_examples),
        "images": images,
        "stream": False,
        "format": build_schema(),
        "options": {"num_ctx": NUM_CTX},
    }
    for _ in range(2):  # one attempt + one retry
        try:
            return _parse(post(host, payload))
        except ValueError:
            continue
    return None
