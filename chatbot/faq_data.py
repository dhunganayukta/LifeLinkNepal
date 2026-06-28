# chatbot/faq_data.py
"""
FAQ knowledge base for the LifeLink Nepal chatbot.

SOURCE OF TRUTH: Nepal Red Cross Society (NRCS) - https://nrcs.org/donate-blood/
NRCS is Nepal's nationally designated blood transfusion service deliverer,
so their published criteria are treated as authoritative here.

IMPORTANT: Do not let the chatbot freely generate eligibility answers from
a general-purpose model. Always match against this curated list first.
If nothing matches, fall back to "please confirm with a hospital/blood bank"
rather than guessing - especially for medical eligibility questions.

To update: edit the entries below. Each entry has:
- keywords: words/phrases used to match a user's question (lowercase)
- answer: the exact text to show the user
- category: used for analytics / grouping (optional, not required for matching)
"""

FAQ_ENTRIES = [
    {
        "id": "what_is_this_site",
        "keywords": [
            "what is this", "what is lifelink", "what does this site do",
            "what is this site", "what is this page", "what does this do",
            "purpose of this site", "what is this app"
        ],
        "category": "general",
        "answer": (
            "LifeLink Nepal connects blood donors with hospitals across Nepal "
            "during emergencies. Donors register with their blood type and "
            "location; hospitals post blood requests; we match nearby, "
            "compatible, eligible donors and notify them quickly."
        ),
    },
    {
        "id": "is_it_free",
        "keywords": ["free", "cost", "price", "fee", "charge", "pay"],
        "category": "general",
        "answer": (
            "Yes, LifeLink Nepal is completely free to use for both donors "
            "and hospitals. There is no cost to register, donate, or request blood."
        ),
    },
    {
        "id": "age_requirement",
        "keywords": ["age", "how old", "minimum age", "maximum age", "years old"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, donors must be between "
            "18 and 60 years old."
        ),
    },
    {
        "id": "weight_requirement",
        "keywords": ["weight", "kg", "how much should i weigh", "minimum weight"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, donors must weigh "
            "above 45 kg."
        ),
    },
    {
        "id": "hemoglobin_requirement",
        "keywords": ["hemoglobin", "haemoglobin", "hb level", "hb count"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, donors must have "
            "hemoglobin above 12 gm/dl."
        ),
    },
    {
        "id": "blood_pressure_requirement",
        "keywords": ["blood pressure", "bp", "pulse"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, donors should have "
            "blood pressure within 110-160 / 70-96 mmHg."
        ),
    },
    {
        "id": "donation_frequency",
        "keywords": [
            "how often", "how many times", "donation interval",
            "when can i donate again", "frequency", "90 days", "3 months"
        ],
        "category": "eligibility",
        "answer": (
            "You can donate blood once every three months (90 days), "
            "per Nepal Red Cross Society guidelines."
        ),
    },
    {
        "id": "pregnancy_breastfeeding",
        "keywords": ["pregnant", "pregnancy", "breastfeeding", "menstruation", "period"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, you should not donate "
            "while pregnant or breastfeeding. If menstruating, at least "
            "8 days should have passed since the start of your most "
            "recent period before donating."
        ),
    },
    {
        "id": "recent_surgery",
        "keywords": ["surgery", "operation", "operated"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, you should not have "
            "had medical surgery within the last 2 years before donating."
        ),
    },
    {
        "id": "medication",
        "keywords": ["medicine", "medication", "drugs", "antibiotics", "pills"],
        "category": "eligibility",
        "answer": (
            "Recent use of strong medicines can restrict donation, anywhere "
            "from one week up to 2 years depending on the medication, per "
            "Nepal Red Cross Society guidelines. Please check with your "
            "nearest blood bank about your specific medication."
        ),
    },
    {
        "id": "diabetes",
        "keywords": ["diabetes", "diabetic", "blood sugar", "sugar patient"],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, diabetes is listed as "
            "a condition that restricts blood donation. We'd recommend "
            "confirming directly with your nearest blood bank or hospital, "
            "as some centers may evaluate this case by case."
        ),
    },
    {
        "id": "restricted_conditions",
        "keywords": [
            "cancer", "heart disease", "hiv", "aids", "hepatitis",
            "hemophilia", "thalassemia", "liver disease", "asthma",
            "hormonal disorder", "endocrine", "not eligible", "disqualify",
            "what conditions", "medical condition"
        ],
        "category": "eligibility",
        "answer": (
            "Per Nepal Red Cross Society guidelines, the following "
            "conditions currently restrict blood donation: cancer, heart "
            "disease, HIV/AIDS, hepatitis B or C, hemophilia, thalassemia, "
            "liver disease, Polycythemia Vera, asthma, and endocrine or "
            "hormonal disorders. If you have a condition not listed here, "
            "please check with your nearest blood bank."
        ),
    },
    {
        "id": "how_matching_works",
        "keywords": [
            "matching work", "how do you match", "how does it work",
            "donors selected", "priority decided", "choose donors",
            "how it works"
        ],
        "category": "platform",
        "answer": (
            "When a hospital posts a request, we filter donors by blood "
            "compatibility and distance, then rank the eligible donors "
            "using factors like distance, donation history, and time "
            "since their last donation - so the most suitable nearby "
            "donors are notified first."
        ),
    },
    {
        "id": "data_privacy",
        "keywords": ["privacy", "data safe", "who sees my", "my information", "personal data"],
        "category": "platform",
        "answer": (
            "Your personal information is only shared with hospitals when "
            "you're matched to a request you can help with. We don't sell "
            "or share your data with third parties."
        ),
    },
    {
        "id": "how_to_register_donor",
        "keywords": [
            "register as a donor", "register as donor", "sign up as donor",
            "become a donor", "i want to donate", "register donor",
            "want to donate", "donor registration"
        ],
        "category": "routing",
        "answer": (
            "Great - registering as a donor takes just a couple of minutes. "
            "You'll need your blood type, location, and a phone number for "
            "hospitals to reach you."
        ),
        "action": "route_donor",
    },
    {
        "id": "how_to_register_hospital",
        "keywords": [
            "register as a hospital", "register as hospital", "sign up as hospital",
            "register hospital", "i'm a hospital", "post a request",
            "need blood", "hospital account", "hospital registration"
        ],
        "category": "routing",
        "answer": (
            "Hospitals can register to post blood requests and reach "
            "compatible nearby donors quickly. You'll need your hospital's "
            "name, address, and contact details."
        ),
        "action": "route_hospital",
    },
]


def find_best_match(user_message: str):
    """
    Very simple keyword-overlap matcher: returns the FAQ entry whose
    keywords best match the user's message, or None if nothing matches
    well enough.

    This is intentionally NOT an LLM call - eligibility answers must come
    from the curated list above, not be freely generated, since wrong
    medical guidance here has real consequences.
    """
    if not user_message:
        return None

    message = user_message.lower().strip()

    best_entry = None
    best_score = 0

    for entry in FAQ_ENTRIES:
        score = 0
        for keyword in entry["keywords"]:
            if keyword in message:
                # Longer keyword matches count more (more specific match)
                score += len(keyword.split())
        if score > best_score:
            best_score = score
            best_entry = entry

    # Require at least some match - avoid returning a random entry
    # for completely unrelated input
    if best_score == 0:
        return None

    return best_entry


FALLBACK_ANSWER = (
    "I'm not sure about that one. For medical or eligibility questions "
    "specific to your situation, please check with your nearest hospital "
    "or blood bank directly. Would you like to register as a donor or "
    "a hospital instead?"
)