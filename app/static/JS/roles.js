// Dropdown submenu, Profil uj szerepkör felvétele!
$('.dropdown-submenu a.dropdown-toggle').on("click", function(e) {
    $(this).next('ul').toggle();
    e.stopPropagation();
    e.preventDefault(); // Megakadályozza a továbbnavigálást
});

// Sportágak frissítése az edzőhöz az egyesület kiválasztásakor

document.getElementById('club_id').addEventListener('change', function() {
    var selectedClubId = this.value;

    fetch('/get_sports/' + selectedClubId)
        .then(response => response.json())
        .then(data => {
            var sportsContainer = document.getElementById('sports-container');
            sportsContainer.innerHTML = '';
            data.sports.forEach(sport => {
                var checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.name = 'sports';
                checkbox.value = sport.id;
                checkbox.id = 'sport-' + sport.id;
                if (sport.is_selected) { // Ellenőrzés, hogy a sportág ki van-e választva
                    checkbox.checked = true;
                }
                var label = document.createElement('label');
                label.htmlFor = 'sport-' + sport.id;
                label.textContent = sport.name;
                sportsContainer.appendChild(checkbox);
                sportsContainer.appendChild(label);
                sportsContainer.appendChild(document.createElement('br'));
            });
        })
        .catch(error => {
            console.error("Hiba történt a sportágak lekérdezésekor:", error);
        });
});
document.getElementById('club_id').addEventListener('change', function() {
    var selectedClubId = this.value;

    fetch('/get_sports/' + selectedClubId)
        .then(response => response.json())
        .then(data => {
            var sportsContainer = document.getElementById('sports-container');
            sportsContainer.innerHTML = '';
            data.sports.forEach(sport => {
                var checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.name = 'sports';
                checkbox.value = sport.id;
                checkbox.id = 'sport-' + sport.id;
                if (sport.is_selected) { // Ellenőrzés, hogy a sportág ki van-e választva
                    checkbox.checked = true;
                }
                var label = document.createElement('label');
                label.htmlFor = 'sport-' + sport.id;
                label.textContent = sport.name;
                sportsContainer.appendChild(checkbox);
                sportsContainer.appendChild(label);
                sportsContainer.appendChild(document.createElement('br'));
            });
        })
        .catch(error => {
            console.error("Hiba történt a sportágak lekérdezésekor:", error);
        });
});

    // Az oldal betöltésekor lekérjük az összes sportágat
fetch('/get_sports/0') // 0-t küldünk, hogy lekérjük az összes sportágat
    .then(response => response.json())
    .then(data => {
        var sportsContainer = document.getElementById('sports-container');
        sportsContainer.innerHTML = ''; // Töröljük a régi sportágakat
        data.sports.forEach(sport => {
            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.name = 'sports';
            checkbox.value = sport.id;
            checkbox.id = 'sport-' + sport.id;
            if (sport.is_selected) { // Ellenőrzés, hogy a sportág ki van-e választva
                checkbox.checked = true;
            }
            var label = document.createElement('label');
            label.htmlFor = 'sport-' + sport.id;
            label.textContent = sport.name;
            sportsContainer.appendChild(checkbox);
            sportsContainer.appendChild(label);
            sportsContainer.appendChild(document.createElement('br'));
        });
    })
    .catch(error => {
        console.error("Hiba történt a sportágak lekérdezésekor:", error);
    });  


    // Sportolói Profil ha 18 év alatti az egyesület kiválasztásakor
document.getElementById('birth_year').addEventListener('change', function() {
    var birthYear = this.value;
    var age = new Date().getFullYear() - new Date(birthYear).getFullYear();
    var parentSelect = document.getElementById('parent-select');
    if (age < 18) {
        parentSelect.style.display = 'block';
    } else {
        parentSelect.style.display = 'none';
    }
});

document.getElementById('coach_id').addEventListener('change', function() {
    var selectedCoachId = this.value;
    var parentSelect = document.getElementById('parent-select');
    var parentCheckboxes = document.getElementById('parent-checkboxes');

    if (selectedCoachId) {
        fetch('/get_parents/' + selectedCoachId)
            .then(response => response.json())
            .then(data => {
                parentCheckboxes.innerHTML = '';
                if (data.parents && data.parents.length > 0) {
                    data.parents.forEach(parent => {
                        var checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.name = 'parents';
                        checkbox.value = parent.id;
                        checkbox.id = 'parent-' + parent.id;
                        var label = document.createElement('label');
                        label.htmlFor = 'parent-' + parent.id;
                        label.textContent = parent.name;
                        parentCheckboxes.appendChild(checkbox);
                        parentCheckboxes.appendChild(label);
                        parentCheckboxes.appendChild(document.createElement('br'));
                    });
                    parentSelect.style.display = 'block';
                } else {
                    parentSelect.style.display = 'none';
                }
            })
            .catch(error => {
                console.error("Hiba történt a szülők lekérdezésekor:", error);
            });
    } else {
        parentSelect.style.display = 'none';
    }
});