document.addEventListener('DOMContentLoaded', () => {
    const serviceGrid = document.getElementById('service-grid');
    const lastUpdatedElement = document.getElementById('last-updated');
    const charts = {}; // Store chart instances

    // Function to generate a safe ID from service name
    function generateId(name) {
        return name.replace(/\s+/g, '-').replace(/[()]/g, '').toLowerCase();
    }

    // Function to update the UI for a single service
    function updateServiceUI(name, data) {
        const serviceId = generateId(name);
        const card = document.getElementById(`card-${serviceId}`);
        if (!card) {
            console.warn(`Card element not found for service ID: card-${serviceId}`);
            return;
        }

        const statusIndicator = document.getElementById(`status-${serviceId}`);
        const serviceLink = document.getElementById(`link-${serviceId}`);
        const chartCanvas = document.getElementById(`chart-${serviceId}`);

        // Update status indicator class
        statusIndicator.className = 'status-indicator'; // Reset classes
        if (data.status === 'online') {
            statusIndicator.classList.add('online');
            statusIndicator.title = 'Online';
        } else if (data.status.startsWith('offline')) {
            statusIndicator.classList.add('offline');
            statusIndicator.title = `Offline (${data.status.split('_')[1]})`;
        } else if (data.status.startsWith('error')) {
             statusIndicator.classList.add('error');
             statusIndicator.title = `Error (${data.status.split('_')[1]})`;
        } else {
            statusIndicator.classList.add('checking'); // Default/checking state
            statusIndicator.title = 'Checking';
        }

        // Update link
        serviceLink.href = data.url;

        // --- Update Chart ---
        if (chartCanvas && data.history && data.history.length > 0) {
            const ctx = chartCanvas.getContext('2d');

            // Prepare chart data
            // Map status to numerical values for the chart (e.g., 1 for online, 0 for others)
            const chartData = data.history.map(entry => ({
                x: luxon.DateTime.fromISO(entry[0]).valueOf(), // Use timestamp as X
                y: entry[1] === 'online' ? 1 : 0 // Y value: 1 = online, 0 = offline/error
            }));


            // Destroy previous chart instance if it exists
            if (charts[serviceId]) {
                charts[serviceId].destroy();
            }

            // Create new chart
            charts[serviceId] = new Chart(ctx, {
                type: 'line', // Use line or bar chart for history
                data: {
                    datasets: [{
                        label: 'Status (1=Online, 0=Offline/Error)',
                        data: chartData,
                        borderColor: 'rgba(74, 144, 226, 0.8)', // Blue line
                        backgroundColor: 'rgba(74, 144, 226, 0.2)', // Light blue fill
                        stepped: true, // Makes it look like uptime blocks
                        pointRadius: 0, // Hide points for cleaner look
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false, // Important for fixed height container
                    scales: {
                        x: {
                            type: 'time', // Use time scale
                            time: {
                                unit: 'minute', // Adjust based on history length/frequency
                                tooltipFormat: 'MMM d, yyyy HH:mm:ss ZZZZ', // Luxon format for tooltip
                                 displayFormats: {
                                    minute: 'HH:mm' // Display format on the axis
                                }
                            },
                            title: {
                                display: false, // Hide x-axis title
                            },
                            ticks: {
                                maxTicksLimit: 6, // Limit number of time labels
                                autoSkip: true,
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 1.2, // Give some space above the line
                            ticks: {
                                stepSize: 1, // Only show 0 and 1
                                callback: function(value, index, values) {
                                    return value === 1 ? 'Online' : (value === 0 ? 'Offline' : '');
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false // Hide dataset label legend
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                 label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    const status = context.parsed.y === 1 ? 'Online' : 'Offline/Error';
                                    label += status;
                                    // Find original status string from history for more detail in tooltip
                                    const timestampISO = luxon.DateTime.fromMillis(context.parsed.x).toISO();
                                    const historyEntry = data.history.find(h => luxon.DateTime.fromISO(h[0]).valueOf() === context.parsed.x);
                                    if (historyEntry) {
                                         label = `${historyEntry[1].replace('_', ' ')}`; // Show detailed status like 'offline timeout'
                                    }

                                    return label;
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    // Function to fetch status data from the backend
    async function fetchAndUpdateStatus() {
        console.log("Fetching status...");
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Update UI for each service
            for (const serviceName in data) {
                if (data.hasOwnProperty(serviceName)) {
                    updateServiceUI(serviceName, data[serviceName]);
                }
            }

            // Update last updated time
            lastUpdatedElement.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;

        } catch (error) {
            console.error("Failed to fetch status:", error);
            lastUpdatedElement.textContent = `Error updating status: ${error.message}`;
            // Optionally: set all indicators to an error state or show a global error message
        }
    }

    // Initial fetch
    fetchAndUpdateStatus();

    // Optionally: Refresh data every 60 seconds (adjust interval as needed)
    // The backend already checks every 5 mins, this just updates the UI without a page reload.
    setInterval(fetchAndUpdateStatus, 60000); // 60000ms = 1 minute
});