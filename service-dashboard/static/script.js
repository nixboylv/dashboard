document.addEventListener('DOMContentLoaded', () => {
    const lastUpdatedElement = document.getElementById('last-updated');
    const charts = {}; // Store chart instances
    const chartColors = {
        onlineBorder: 'rgba(56, 161, 105, 0.7)', // Greenish
        onlineBackground: 'rgba(56, 161, 105, 0.1)',
        errorBorder: 'rgba(221, 107, 32, 0.7)', // Orangish
        errorBackground: 'rgba(221, 107, 32, 0.1)',
        offlineBorder: 'rgba(229, 62, 62, 0.7)', // Reddish
        offlineBackground: 'rgba(229, 62, 62, 0.1)',
    };
    const FETCH_INTERVAL_MS = 60000; // Fetch status every 60 seconds
    const MAX_HISTORY_POINTS = 30; // Match backend history length

    function updateServiceUI(serviceId, data) {
        const card = document.getElementById(`card-${serviceId}`);
        const link = document.getElementById(`link-${serviceId}`);
        // const statusIndicator = document.getElementById(`status-${serviceId}`); // We use card class now
        const statusTextElement = document.getElementById(`status-text-${serviceId}`);
        const chartCanvas = document.getElementById(`chart-${serviceId}`);

        if (!card || !link || !statusTextElement || !chartCanvas) {
            console.warn(`UI elements not found for service ID: ${serviceId}`);
            return;
        }

        // Update Link URL using the display_url from the API
        link.href = data.display_url || '#'; // Fallback href

        // Determine status class and text
        let statusClass = 'status-checking';
        let statusText = 'Checking'; // Default display text

        // Simplify status text display
        if (data.status === 'online') {
            statusClass = 'status-online';
            statusText = 'Online';
        } else if (data.status.startsWith('offline')) {
            statusClass = 'status-offline';
            statusText = 'Offline'; // Simple text, details in tooltip/logs
            // Add specifics if needed, e.g.,
            // if (data.status.includes('timeout')) statusText = 'Timeout';
            // else if (data.status.includes('conn_error')) statusText = 'Conn Err';
        } else if (data.status.startsWith('error')) {
            statusClass = 'status-error';
            statusText = `Error`; // Simple text
             // Add specifics if needed, e.g.,
             // statusText = `Error ${data.status.split('_')[1]}`;
        }

        // Update Card Border class and Status Text
        card.className = `service-card ${statusClass}`; // Reset classes and apply current status class
        statusTextElement.textContent = statusText;

        // --- Update Chart ---
        if (data.history && data.history.length > 0) {
            const ctx = chartCanvas.getContext('2d');

            // Map history to chart data points and store detailed status for tooltips
            const chartDataPoints = [];
            const statusMap = {}; // Map timestamp (ms) to detailed status string
            data.history.forEach(entry => {
                const timestamp = luxon.DateTime.fromISO(entry[0]).valueOf();
                const status = entry[1];
                let yValue = 0; // Default offline
                if (status === 'online') yValue = 1;
                else if (status.startsWith('error')) yValue = 0.5; // Distinguish errors visually

                chartDataPoints.push({ x: timestamp, y: yValue });
                statusMap[timestamp] = status; // Store detailed status text
            });

            // Destroy previous chart instance if it exists
            if (charts[serviceId]) {
                charts[serviceId].destroy();
            }

            // Create new chart
            charts[serviceId] = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [{
                        label: 'Status History',
                        data: chartDataPoints,
                        borderColor: (context) => {
                            // Dynamically set color based on point value (optional, simple border is fine too)
                            const yVal = context.raw?.y;
                            if (yVal === 1) return chartColors.onlineBorder;
                            if (yVal === 0.5) return chartColors.errorBorder;
                            return chartColors.offlineBorder;
                        },
                         backgroundColor: (context) => {
                            const yVal = context.raw?.y;
                            if (yVal === 1) return chartColors.onlineBackground;
                            if (yVal === 0.5) return chartColors.errorBackground;
                            return chartColors.offlineBackground;
                        },
                        borderWidth: 1.5,
                        pointRadius: 0,
                        pointHitRadius: 10, // Easier hover detection
                        fill: true,
                        stepped: true, // Blocky uptime chart
                        tension: 0 // Sharp corners for stepped line
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            adapters: { date: { locale: 'en-GB' } }, // Adjust locale if needed
                            time: {
                                unit: 'minute',
                                tooltipFormat: 'MMM d, HH:mm:ss',
                                displayFormats: { minute: 'HH:mm' }
                            },
                            grid: { display: false },
                            ticks: {
                                display: true,
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 5 // Max 5 time labels
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 1.2, // Give slight space above 'Online'
                            grid: { drawBorder: false, color: '#e2e8f0' },
                            ticks: {
                                stepSize: 0.5, // Show 0, 0.5, 1
                                callback: function(value) {
                                    if (value === 1) return 'Online';
                                    if (value === 0.5) return 'Error';
                                    if (value === 0) return 'Offline';
                                    return ''; // Hide other labels (like 1.0, 0.0)
                                },
                                precision: 0 // Ensure whole numbers for comparison
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            enabled: true,
                            mode: 'nearest', // Show tooltip for nearest point on hover
                            intersect: false,
                            displayColors: false, // Hide color box in tooltip
                            callbacks: {
                                // Title: Show time
                                title: function(tooltipItems) {
                                     const timestamp = tooltipItems[0].parsed.x;
                                     return luxon.DateTime.fromMillis(timestamp).toFormat('MMM d, HH:mm:ss');
                                },
                                // Label: Show detailed status
                                label: function(context) {
                                    const timestamp = context.parsed.x;
                                    const rawStatus = statusMap[timestamp] || 'Unknown';
                                    // Clean up status text for display
                                    let label = rawStatus.replace(/_/g, ' ').replace(/(?:^|\s)\S/g, l => l.toUpperCase()); // Capitalize words
                                    if (label.startsWith('Error ')) label = label.replace('Error ','Error: '); // Add colon
                                    if (label.startsWith('Offline ')) label = label.replace('Offline ','Offline: '); // Add colon
                                    return label;
                                }
                            }
                        }
                    },
                     // Disable animations for performance if needed
                    // animation: false
                }
            });
        } else {
             // Optional: Clear chart or show message if no history
             if (charts[serviceId]) {
                charts[serviceId].destroy();
                delete charts[serviceId];
             }
             // Could display text in canvas: ctx.fillText('No history yet', ...);
        }
    }

    async function fetchAndUpdateStatus() {
        // console.log(`[${new Date().toLocaleTimeString()}] Fetching status...`);
        try {
            const response = await fetch('/api/status'); // Fetch from backend API
            if (!response.ok) {
                 if (response.status === 0) { // Network error likely
                     throw new Error(`Network error (Could not reach backend)`);
                 } else {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                 }
            }
            const data = await response.json();

            // Update UI for each service found in the response
            Object.keys(data).forEach(serviceId => {
                if (data.hasOwnProperty(serviceId)) {
                    updateServiceUI(serviceId, data[serviceId]);
                }
            });

            // Update the "Last Updated" timestamp
            lastUpdatedElement.textContent = `Last updated: ${luxon.DateTime.now().toFormat('HH:mm:ss')}`;

        } catch (error) {
            console.error("Failed to fetch status:", error);
            lastUpdatedElement.textContent = `Update Error`; // Keep it simple
            // Maybe add a visual indicator for the update error itself
        }
    }

    // Initial fetch on page load
    fetchAndUpdateStatus();
    // Set interval to fetch updates periodically
    setInterval(fetchAndUpdateStatus, FETCH_INTERVAL_MS);
});