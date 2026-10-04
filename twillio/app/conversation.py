from .models import Extraction

QUESTIONS = {
    'house_number': 'What is the house/building number? Include a letter if any. If unknown or not at a building, reply UNKNOWN.',
    'street': 'What is the street name? If unknown, reply UNKNOWN.',
    'city': 'What city or locality are the people needing help in? If unknown, reply UNKNOWN.',
    'postal_code': 'What is the postal/ZIP code for that location (not the telephone area code)? If unknown, reply UNKNOWN.',
    'landmark': 'What nearby landmark or intersection can help locate them? If unknown, reply UNKNOWN.',
}


def next_question(report: Extraction, asked: list[str]):
    # Multiple locations need operator clarification, not an ambiguous automatic address question.
    if len(report.situations) != 1:
        return None
    address = report.situations[0].address
    if report.situations[0].reported_resolution:
        return None
    for field in ('house_number', 'street', 'city', 'postal_code', 'landmark'):
        if field == 'landmark' and address.house_number and address.street and address.city:
            continue
        if not getattr(address, field) and field not in asked and field not in address.unavailable_fields:
            return field, QUESTIONS[field]
    return None
