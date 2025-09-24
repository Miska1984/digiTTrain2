# users/utils.py Szerpkör státusz ellenőrzéshez!
from users.models import UserRole

def has_role(user, role_name, club=None, sport=None):
    qs = UserRole.objects.filter(user=user, role__name=role_name, status="approved")
    if club:
        qs = qs.filter(club=club)
    if sport:
        qs = qs.filter(sport=sport)
    return qs.exists()
