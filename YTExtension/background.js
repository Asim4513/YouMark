chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
    if (changeInfo.status === 'complete' && tab.url.includes('youtube.com/watch?v=')) {
        const urlParams = new URLSearchParams(new URL(tab.url).search);
        const videoId = urlParams.get('v');
        if (videoId) {
            chrome.storage.local.set({videoId: videoId});
        }
    }
});

chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
        if (request.contentScriptQuery === 'queryVideo') {
            fetch('http://localhost:8080/process_video', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    video_id: request.videoId,
                    query: request.query
                })
            })
            .then(response => response.json())
            .then(data => {
                chrome.tabs.sendMessage(sender.tab.id, {type: 'highlightSegments', segments: data});
                sendResponse({result: data});
            })
            .catch(error => {
                console.error('Fetch error:', error);
                sendResponse({error: error.message});
            });
            return true;  // Will respond asynchronously.
        }
    }
);
