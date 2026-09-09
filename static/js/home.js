(function () {
    "use strict";

    const body = document.body;
    const sidebarToggle = document.getElementById("sidebar-toggle");
    const mobileMenu = document.getElementById("mobile-menu");
    const search = document.getElementById("module-search");
    const searchStatus = document.getElementById("search-status");

    function normalize(value) {
        return (value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .trim();
    }

    function setSidebarCollapsed(collapsed) {
        body.classList.toggle("sidebar-collapsed", collapsed);
        if (sidebarToggle) {
            sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        }
        try {
            localStorage.setItem("axion-sidebar-collapsed", collapsed ? "1" : "0");
        } catch (error) {
            // A preferência visual é opcional quando o armazenamento está indisponível.
        }
    }

    try {
        setSidebarCollapsed(localStorage.getItem("axion-sidebar-collapsed") === "1");
    } catch (error) {
        setSidebarCollapsed(false);
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener("click", function () {
            if (window.matchMedia("(max-width: 820px)").matches) {
                body.classList.remove("mobile-nav-open");
                if (mobileMenu) mobileMenu.setAttribute("aria-expanded", "false");
                return;
            }
            setSidebarCollapsed(!body.classList.contains("sidebar-collapsed"));
        });
    }

    if (mobileMenu) {
        mobileMenu.addEventListener("click", function () {
            const open = body.classList.toggle("mobile-nav-open");
            mobileMenu.setAttribute("aria-expanded", String(open));
        });
    }

    document.addEventListener("keydown", function (event) {
        if (search && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            search.focus();
        }
        if (event.key === "Escape") {
            if (search) {
                search.value = "";
                filterModules();
                search.blur();
            }
            body.classList.remove("mobile-nav-open");
            if (mobileMenu) mobileMenu.setAttribute("aria-expanded", "false");
        }
    });

    function filterModules() {
        if (!search || !searchStatus) return;
        const term = normalize(search.value);
        let visibleModules = 0;

        document.querySelectorAll("[data-module]").forEach(function (card) {
            const cardText = normalize(card.dataset.search);
            const cardMatches = !term || cardText.includes(term);
            card.classList.toggle("search-hidden", !cardMatches);
            if (cardMatches) {
                visibleModules += 1;
            }
        });

        document.querySelectorAll("[data-group]").forEach(function (group) {
            const hasVisibleCard = group.querySelector("[data-module]:not(.search-hidden)");
            group.classList.toggle("search-hidden", !hasVisibleCard);
        });

        searchStatus.classList.toggle("visible", Boolean(term));
        searchStatus.textContent = term
            ? visibleModules + (visibleModules === 1 ? " módulo encontrado." : " módulos encontrados.")
            : "";
    }

    if (search) search.addEventListener("input", filterModules);
}());
