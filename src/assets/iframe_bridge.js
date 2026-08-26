console.log("iframe_bridge.js loaded");

(function installRewildIframeBridge() {
    if (window.rewildIframeBridgeInstalled) {
        console.log("ReWild iframe bridge already installed");
        return;
    }

    window.rewildIframeBridgeInstalled = true;

    function setDashInputValue(element, value) {
        const valueSetter =
            Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype,
                "value"
            ).set;

        valueSetter.call(element, value);

        element.dispatchEvent(
            new Event("input", {
                bubbles: true
            })
        );

        element.dispatchEvent(
            new Event("change", {
                bubbles: true
            })
        );
    }

    function sendSelectionToDash(message, attempt) {
        const currentAttempt = attempt || 0;
        const maxAttempts = 30;

        const input = document.getElementById(
            "selected-map-feature-json"
        );

        if (input) {
            const selectedFeature = {
                featureType: message.featureType,
                properties: message.properties || {},
                sentAt: message.sentAt || Date.now()
            };

            console.log(
                "Sending selected feature through Dash input:",
                selectedFeature
            );

            setDashInputValue(
                input,
                JSON.stringify(selectedFeature)
            );

            return;
        }

        if (currentAttempt >= maxAttempts) {
            console.error(
                "Could not find #selected-map-feature-json after " +
                maxAttempts +
                " attempts."
            );
            return;
        }

        window.setTimeout(
            function () {
                sendSelectionToDash(
                    message,
                    currentAttempt + 1
                );
            },
            100
        );
    }

    window.addEventListener("message", function (event) {
        const message = event.data;

        if (
            !message ||
            message.source !== "rewild-qgis-map"
        ) {
            return;
        }

        const mapFrame =
            document.getElementById("qgis-map-frame");

        if (
            mapFrame &&
            event.source !== mapFrame.contentWindow
        ) {
            console.warn(
                "Rejected map message from an unexpected window."
            );
            return;
        }

        console.log(
            "Parent received ReWild iframe message:",
            message
        );

        /*
        * Ordinary parent-page scrolling message.
        * This message is not expected to include a feature.
        */
        if (message.action === "scroll-parent") {
            window.scrollBy({
                left: Number(message.deltaX) || 0,
                top: Number(message.deltaY) || 0,
                behavior: "auto"
            });

            return;
        }

        /*
        * Process a selected site or planting first.
        * This allows one message to both update the details
        * and request scrolling to the detail panel.
        */
        const containsFeature =
            message.featureType === "site" ||
            message.featureType === "planting";

        if (containsFeature) {
            if (
                !message.properties ||
                typeof message.properties !== "object"
            ) {
                console.warn(
                    "Map selection did not contain feature properties:",
                    message
                );
            } else {
                sendSelectionToDash(message, 0);
            }
        }

        /*
        * Scroll only after passing the selected feature to Dash.
        * Do not return before the selection is processed.
        */
        if (message.action === "scroll-to-project-details") {
            const detailPanel =
                document.getElementById(
                    "project-detail-panel"
                );

            if (detailPanel) {
                /*
                * Give Dash a moment to render the newly selected
                * record before scrolling to the panel.
                */
                window.setTimeout(function () {
                    detailPanel.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });
                }, 100);
            }

            return;
        }

        if (!containsFeature) {
            console.log(
                "ReWild message contained no recognised feature:",
                message
            );
        }
    });

    console.log("ReWild iframe bridge installed");
})();