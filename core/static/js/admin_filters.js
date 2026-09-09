(function () {
    "use strict";

    function closeOtherFilters(current) {
        document.querySelectorAll(".axion-filter-dropdown[open]").forEach(function (filter) {
            if (filter !== current) filter.removeAttribute("open");
        });
    }

    document.addEventListener("toggle", function (event) {
        var filter = event.target;
        if (filter.matches && filter.matches(".axion-filter-dropdown[open]")) {
            closeOtherFilters(filter);
        }
    }, true);

    document.addEventListener("click", function (event) {
        if (!event.target.closest(".axion-filter-dropdown")) closeOtherFilters(null);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeOtherFilters(null);
    });
}());
