document.addEventListener('DOMContentLoaded', function () {
    const processButton = document.getElementById('process');
    const clearHighlightsButton = document.getElementById('clearHighlights');
    const doneMessage = document.getElementById('doneMessage');
    const output = document.getElementById('output');

    processButton.addEventListener('click', function () {
        // Remove any existing dynamically created progress bars
        const existingProgressBarContainer = document.querySelector('.progressBarContainer');
        if (existingProgressBarContainer) {
            existingProgressBarContainer.remove();
        }

        // Dynamically create a new progress bar container and progress bar
        const progressBarContainer = document.createElement('div');
        progressBarContainer.className = 'progressBarContainer';

        const progressBar = document.createElement('div');
        progressBar.className = 'progressBar';
        progressBar.innerText = '0%';  // Initial text

        // Append the progress bar to the container and add it to the document body
        progressBarContainer.appendChild(progressBar);
        document.body.insertBefore(progressBarContainer, doneMessage);

        // Show the progress bar and hide the "Done." message initially
        doneMessage.style.display = 'none';
        output.style.display = 'none';  // Hide #output initially
        output.innerText = '';  // Clear any previous output content

        chrome.storage.local.get(['videoId'], function (result) {
            if (chrome.runtime.lastError) {
                console.error("Error retrieving video ID:", chrome.runtime.lastError);
                output.innerText = 'Storage Error: ' + chrome.runtime.lastError.message;
                output.style.display = 'block';  // Show #output if there is an error message
                progressBarContainer.style.display = 'none';  // Hide progress bar on error
                return;
            }
            if (result.videoId) {
                const query = document.getElementById('query').value;

                // Start simulating the progress bar fill-up
                simulateProgressBar(progressBar);

                fetch('http://localhost:8080/process_video', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ video_id: result.videoId, query: query })
                })
                .then(response => response.json())
                .then(data => {
                    // Fill progress bar completely and show "Done."
                    clearInterval(simulateProgressBar.interval);  // Stop the simulation
                    progressBar.style.width = '100%';
                    progressBar.innerText = '100%';
                    doneMessage.style.display = 'block';

                    // Send data to content script to handle video highlighting
                    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
                        chrome.tabs.sendMessage(tabs[0].id, {
                            type: 'highlightSegments',
                            segments: data
                        });
                    });

                    // Optional: You can uncomment this if you want to display a success message instead of JSON
                    // output.innerText = 'Video processed successfully.';
                    // output.style.display = 'block'; // Show the success message
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    output.innerText = 'Fetch error: ' + error.message;
                    output.style.display = 'block';  // Show #output if there is an error message
                    clearInterval(simulateProgressBar.interval);  // Stop the simulation on error
                    progressBarContainer.style.display = 'none';  // Hide progress bar on error
                });
            } else {
                output.innerText = 'Error: No video ID found in storage';
                output.style.display = 'block';  // Show #output if no video ID is found
                progressBarContainer.style.display = 'none';  // Hide progress bar if no video ID
            }
        });
    });
    clearHighlightsButton.addEventListener('click', function () {
        // Send a message to the content script to clear all highlights
        chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
            chrome.tabs.sendMessage(tabs[0].id, { type: 'clearHighlights' });
        });
    });
});

// Refactored `processVideo` function without JSON printing
function processVideo(videoId) {
    const query = document.getElementById('query').value;
    const doneMessage = document.getElementById('doneMessage');
    const output = document.getElementById('output');

    // Show the progress bar and hide the "Done." message initially
    const progressBar = document.querySelector('.progressBar');
    progressBar.style.width = '0%';  // Reset the progress bar width
    doneMessage.style.display = 'none';
    output.style.display = 'none';  // Hide #output initially
    output.innerText = '';  // Clear any previous output content

    // Start simulating the progress bar fill-up
    simulateProgressBar(progressBar);

    fetch('http://localhost:8080/process_video', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ video_id: videoId, query: query })
    })
        .then(response => response.json())
        .then(data => {
            // Fill progress bar completely and show "Done."
            clearInterval(simulateProgressBar.interval);  // Stop the simulation
            progressBar.style.width = '100%';
            progressBar.innerText = '100%';
            doneMessage.style.display = 'block';

            // Optional: Uncomment this if you want to show a message
            // output.innerText = 'Video processed successfully.';
            // output.style.display = 'block'; // Show the success message
        })
        .catch(error => {
            console.error('Error fetching data:', error);
            output.innerText = 'Fetch error: ' + error.message;
            output.style.display = 'block';  // Show #output if there is an error message
            clearInterval(simulateProgressBar.interval);  // Stop the simulation on error
        });
}

// Simulate progress bar fill-up
function simulateProgressBar(progressBar) {
    let width = 0;
    simulateProgressBar.interval = setInterval(() => {  // Store the interval ID
        if (width >= 80) {  // Cap at 80% until fetching is complete
            clearInterval(simulateProgressBar.interval);
        } else {
            width += 10;
            progressBar.style.width = width + '%';
            progressBar.innerText = width + '%';
        }
    }, 500);  // Update every 500ms
}
