(function () {
    var form = document.getElementById("id_stripe_blik_code").closest("form");
    var root = document.getElementById("blik-confirm");
    var stashUrl = root.dataset.stashUrl;

    form.addEventListener("submit", function (ev) {
        var input = document.getElementById("id_stripe_blik_code");
        if (!/^\d{6}$/.test(input.value)) {
            return; // niech HTML5 walidacja/required pokaże błąd
        }

        // Jeśli kod już zapisany dla tej wartości, nie blokuj ponownie
        if (form.dataset.blikStashed === input.value) {
            return;
        }

        ev.preventDefault();

        var fd = new FormData();
        fd.append("code", input.value);
        fd.append(
            "csrfmiddlewaretoken",
            document.querySelector('[name=csrfmiddlewaretoken]').value
        );

        fetch(stashUrl, { method: "POST", credentials: "same-origin", body: fd })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                var errEl = document.getElementById("blik-stash-error");
                if (!res.ok) {
                    errEl.textContent = res.d.error || "{% trans 'Błąd' %}";
                    return;
                }
                errEl.textContent = "";
                form.dataset.blikStashed = input.value;
                form.submit(); // dopiero teraz właściwe złożenie zamówienia
            })
            .catch(function () {
                document.getElementById("blik-stash-error").textContent =
                    "{% trans 'Błąd połączenia, spróbuj ponownie.' %}";
            });
    });
})();