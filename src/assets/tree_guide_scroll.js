(function installTreeGuideScrolling() {
    if (window.__rewildTreeGuideScrollingInstalled) {
        return;
    }

    window.__rewildTreeGuideScrollingInstalled = true;

    function parsePatternId(element) {
        if (!element || !element.id) {
            return null;
        }

        try {
            return JSON.parse(element.id);
        } catch (error) {
            return null;
        }
    }

    function animateWoodlandArrival(section) {
        if (!section) {
            return;
        }

        section.classList.remove("is-arriving");

        // Force the browser to recognise removal before adding it again.
        void section.offsetWidth;

        section.classList.add("is-arriving");

        window.setTimeout(function () {
            section.classList.remove("is-arriving");
        }, 900);
    }

    function scrollToWoodland() {
        const woodlandSection = document.getElementById(
            "tree-guide-growth-section"
        );

        if (!woodlandSection) {
            return;
        }

        woodlandSection.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });

        animateWoodlandArrival(woodlandSection);
    }

    document.addEventListener("click", function (event) {
        const selector = event.target.closest(".tree-selector-card");

        if (!selector) {
            return;
        }

        const selectorId = parsePatternId(selector);

        if (
            !selectorId ||
            selectorId.type !== "tree-guide-selector"
        ) {
            return;
        }

        /*
         * First centre the chosen card in the horizontal tree rail.
         */
        selector.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
            inline: "center",
        });

        /*
         * Allow the Dash callback enough time to render the selected
         * woodland before moving the page down to it.
         */
        window.setTimeout(scrollToWoodland, 220);
    });
})();