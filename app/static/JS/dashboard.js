// Spotág lenyílása
function toggleSports(clubName) {
    var sportsList = document.getElementById(clubName);
    if (sportsList.style.display === "none") {
        sportsList.style.display = "block";
    } else {
        sportsList.style.display = "none";
    }
}

document.getElementById('add-parents-button').addEventListener('click', function() {
    // Átirányítás az oldalra, ahol a szülőket lehet kiválasztani
    window.location.href = "{{ url_for('routes.add_parents_to_athlete) }}";
});

 