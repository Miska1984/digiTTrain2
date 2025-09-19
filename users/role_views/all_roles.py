# users/role_views/all_roles.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from users.models import UserRole
# from users.forms import UserRoleEditForm # Létre kell hozni egy ilyen űrlapot

@login_required
def edit_user_role(request, role_id):
    """
    Generikus nézet a felhasználói szerepkörök szerkesztésére
    """
    user_role = get_object_or_404(UserRole, id=role_id, user=request.user)
    
    # Ha a kérése POST, kezeljük az űrlapot
    # if request.method == 'POST':
    #     form = UserRoleEditForm(request.POST, instance=user_role)
    #     if form.is_valid():
    #         form.save()
    #         return redirect('users:role_dashboard')
    # else:
    #     form = UserRoleEditForm(instance=user_role)

    context = {
        'user_role': user_role,
        # 'form': form,
    }
    return render(request, 'users/edit_user_role.html', context)