// Sportágak betöltése
// Az oldal betöltésekor lekérjük az összes sportágat
fetch('/get_upgrade_sport/0') // 0-t küldünk, hogy lekérjük az összes sportágat
.then(response => response.json())
.then(data => {
    var sportsContainer = document.getElementById('sports-container-upgrade');
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
