

// ============================================
// SALE REVERSAL - COMPREHENSIVE DEBUG VERSION
// ============================================
// ============================================
document.addEventListener("DOMContentLoaded", function() {
    console.log("🔄 Sale Reversal JS Loaded");

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            document.cookie.split(";").forEach(cookie => {
                cookie = cookie.trim();
                if (cookie.startsWith(name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                }
            });
        }
        return cookieValue;
    }

    const csrftoken = getCookie("csrftoken");
    console.log("🔐 CSRF Token:", csrftoken ? "Found ✓" : "Missing ✗");

    document.addEventListener("click", function(event) {
        const button = event.target.closest(".reverse-sale-btn");
        if (!button) return;

        event.preventDefault();
        event.stopPropagation();

        const saleId = button.dataset.saleId;
        if (!saleId) {
            alert("Error: Sale ID not found on link");
            return;
        }

        const confirmed = confirm(
            `⚠️ Are you sure you want to reverse sale #${saleId}?`
        );
        if (!confirmed) return;

        const reason = prompt("Reason for reversal:", "Customer return");
        if (reason === null) return;

        button.classList.add("disabled");
        const originalText = button.innerHTML;
        button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';

        fetch(`/sales/reverse/${saleId}/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": csrftoken,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: new URLSearchParams({ reason: reason })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert(`✅ ${data.message}`);
                // Optionally update the table row visually
                const row = document.querySelector(`#sale-row-${saleId}`);
                if (row) row.style.opacity = "0.6";
                button.innerHTML = "Reversed";
            } else {
                alert(`❌ ${data.message}`);
                button.innerHTML = originalText;
                button.classList.remove("disabled");
            }
        })
        .catch(err => {
            console.error(err);
            alert("❌ Error reversing sale. Check console.");
            button.innerHTML = originalText;
            button.classList.remove("disabled");
        });
    });
});


// ============================================
// UPDATE SALES STATS FUNCTION
// ============================================
function updateSalesStats() {
    const allRows = document.querySelectorAll(".sale-row");
    const activeRows = document.querySelectorAll('.sale-row[data-status="active"]');
    const reversedRows = document.querySelectorAll('.sale-row[data-status="reversed"]');

    const totalCount = document.getElementById("totalSalesCount");
    const activeCount = document.getElementById("activeSalesCount");
    const reversedCount = document.getElementById("reversedSalesCount");

    if (totalCount) totalCount.textContent = allRows.length;
    if (activeCount) activeCount.textContent = activeRows.length;
    if (reversedCount) reversedCount.textContent = reversedRows.length;
}




