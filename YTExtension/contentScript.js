(() => {
    const waitForElement = (selector, retryInterval = 100, maxAttempts = 50) => {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const interval = setInterval(() => {
                if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    reject(new Error(`Element ${selector} not found after ${maxAttempts} attempts`));
                }
                const element = document.querySelector(selector);
                if (element) {
                    clearInterval(interval);
                    resolve(element);
                }
                attempts++;
            }, retryInterval);
        });
    };

    const addMarkersToPlayer = async (segments) => {
        try {
            const progressBar = await waitForElement('.ytp-progress-bar');
            console.log("Progress Bar Element: ", progressBar);
            const videoPlayer = await waitForElement('video'); // Ensure the video element is available
            if (!videoPlayer || !progressBar) {
                console.error("Required elements not found.");
                return;
            }

            // Check if video duration is valid
            if (videoPlayer.duration <= 0) {
                console.error("Invalid video duration. Markers cannot be added.");
                return;
            }

            console.log("Video duration:", videoPlayer.duration);
            console.log("Segments to highlight:", segments);

            // Remove existing markers
            const existingMarkers = progressBar.querySelectorAll('.custom-seek-marker');
            existingMarkers.forEach(marker => marker.remove());

            // Create and add markers based on segments
            segments.forEach(segment => {
                const startTime = parseFloat(segment.start_time);
                const positionPercent = (startTime / videoPlayer.duration) * 100;

                // Verify calculated position
                console.log(`Start time: ${startTime}, Position: ${positionPercent}%`);

                // Create marker
                const marker = document.createElement('div');
                marker.className = 'custom-seek-marker';
                marker.style.position = 'absolute';
                marker.style.left = `${positionPercent}%`;
                marker.style.width = '4px';
                marker.style.height = '100%';
                marker.style.backgroundColor = '#00FFFF';
                marker.style.opacity = '0.7';
                marker.style.zIndex = '1000';

                // Append marker to the progress bar
                progressBar.appendChild(marker);
            });

            console.log("Markers added successfully.");
        } catch (error) {
            console.error("Error adding markers:", error);
        }
    };

    const clearMarkersFromPlayer = async () => {
        try {
            const progressBar = await waitForElement('.ytp-progress-bar');
            const existingMarkers = progressBar.querySelectorAll('.custom-seek-marker');
            existingMarkers.forEach(marker => marker.remove());
            console.log("All markers cleared successfully.");
        } catch (error) {
            console.error("Error clearing markers:", error);
        }
    };

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'highlightSegments') {
            addMarkersToPlayer(message.segments);
        } else if (message.type === 'clearHighlights') {
            clearMarkersFromPlayer(); // Call function to remove all markers
        }
    });

    console.log('Content script loaded and listening for segment data...');
})();

