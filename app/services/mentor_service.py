from app.models import User

APPROVED_MENTOR_EMAILS = [
    'praveen@antimatrix.co.in',
    'satishkumar@antimatrix.co.in',
    'rohit@antimatrix.co.in',
    'bharatbabu@antimatrix.co.in',
]

APPROVED_MENTOR_NAMES = {
    'praveen@antimatrix.co.in': 'Praveen',
    'satishkumar@antimatrix.co.in': 'Satish Kumar',
    'rohit@antimatrix.co.in': 'Rohit',
    'bharatbabu@antimatrix.co.in': 'Bharat Babu',
}


def get_approved_mentors():
    """
    Retrieve the four approved mentors from the database in canonical order.
    Guarantees exact canonical names and excludes any unauthorized or legacy mentors.
    """
    mentors = User.query.filter(
        User.role == 'mentor',
        User.email.in_(APPROVED_MENTOR_EMAILS)
    ).all()
    order_map = {email: idx for idx, email in enumerate(APPROVED_MENTOR_EMAILS)}
    return sorted(mentors, key=lambda m: order_map.get(m.email, 99))


def is_approved_mentor(user):
    """Check if a User object is one of the four approved mentors."""
    if not user or not getattr(user, 'email', None):
        return False
    return user.email in APPROVED_MENTOR_EMAILS


def get_canonical_mentor_name(user):
    """Return the exact canonical display name for an approved mentor, or None."""
    if not user or not getattr(user, 'email', None):
        return None
    return APPROVED_MENTOR_NAMES.get(user.email)


APPROVED_MENTOR_OFFICIAL_EMAILS = {
    'Praveen': 'praveen@antimatrix.co.in',
    'Satish Kumar': 'satishkumar@antimatrix.co.in',
    'Rohit': 'rohit@antimatrix.co.in',
    'Bharat Babu': 'bharathbabu@antimatrix.co.in',
}


def get_canonical_mentor_email(mentor_or_name):
    """
    Return the official Anti-Matrix mentor email for an approved mentor.
    Accepts a User object, canonical mentor name string, or mentor email string.
    Returns None if the mentor is not an approved mentor or unassigned.
    """
    if not mentor_or_name:
        return None
    if isinstance(mentor_or_name, str):
        name = mentor_or_name.strip()
        if name in APPROVED_MENTOR_OFFICIAL_EMAILS:
            return APPROVED_MENTOR_OFFICIAL_EMAILS[name]
        if name in APPROVED_MENTOR_NAMES:
            canon_name = APPROVED_MENTOR_NAMES[name]
            return APPROVED_MENTOR_OFFICIAL_EMAILS.get(canon_name)
        for k, v in APPROVED_MENTOR_OFFICIAL_EMAILS.items():
            if k.lower() == name.lower():
                return v
        return None
    if is_approved_mentor(mentor_or_name):
        canonical_name = get_canonical_mentor_name(mentor_or_name)
        return APPROVED_MENTOR_OFFICIAL_EMAILS.get(canonical_name)
    return None

