(function () {
    var root = document.getElementById("blik-pending");
    var statusUrl = root.dataset.statusUrl;
    var retryUrl = root.dataset.retryUrl;
    var loadingEl = document.getElementById("blik-loading");
    var waitingEl = document.getElementById("blik-waiting");
    var failedEl = document.getElementById("blik-failed");
    var pollTimer = null;
    var pollIntervalMs = 2000;
    var maxPollMs = 3 * 60 * 1000;
    var startedAt = Date.now();
    var limitPoll = false

    function showWaiting() {
        loadingEl.style.display = "none";
        waitingEl.style.display = "";
        failedEl.style.display = "none";
    }
    function showFailed() {
        loadingEl.style.display = "none";
        waitingEl.style.display = "none";
        failedEl.style.display = "";
    }

    function poll() {
        if (limitPoll) { 
            if (Date.now() - startedAt > maxPollMs) {
                showFailed();
                return;
            }
        }

        
        fetch(statusUrl, { credentials: "same-origin" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === "succeeded") {
                    window.location.reload();
                    return;
                }
                if (data.status === "failed") {
                    showFailed();
                    return;
                }
                if (data.status === "processing") {
                    showWaiting();
                    limitPoll = true;
                }

                pollTimer = setTimeout(poll, pollIntervalMs);
            })
            .catch(function () {
                pollTimer = setTimeout(poll, pollIntervalMs);
            });
    }
    poll();
})();