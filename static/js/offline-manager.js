// static/js/offline-manager.js
class OfflineManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.offlineQueue = this.loadQueue();
        this.syncInProgress = false;
        this.init();
    }

    init() {
        // Register service worker
        this.registerServiceWorker();

        // Set up online/offline listeners
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());

        // Listen for service worker messages
        navigator.serviceWorker?.addEventListener('message', (event) => {
            this.handleServiceWorkerMessage(event.data);
        });

        // Initial UI update
        this.updateConnectionStatus();

        // Check for pending syncs on load
        if (this.isOnline && this.offlineQueue.length > 0) {
            this.syncOfflineData();
        }
    }

    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/js/service-worker.js');
                console.log('Service Worker registered:', registration.scope);

                // Check for updates
                registration.addEventListener('updatefound', () => {
                    console.log('Service Worker update found');
                });
            } catch (error) {
                console.error('Service Worker registration failed:', error);
            }
        }
    }

    handleOnline() {
        console.log('Connection restored');
        this.isOnline = true;
        this.updateConnectionStatus();
        this.showNotification('Connection restored', 'success');
        
        // Sync offline data
        if (this.offlineQueue.length > 0) {
            this.syncOfflineData();
        }
    }

    handleOffline() {
        console.log('Connection lost');
        this.isOnline = false;
        this.updateConnectionStatus();
        this.showNotification('You are offline. Changes will be synced when connection is restored.', 'warning');
    }

    updateConnectionStatus() {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            if (this.isOnline) {
                statusElement.className = 'connection-status online';
                statusElement.innerHTML = '<i class="fas fa-wifi"></i> Online';
            } else {
                statusElement.className = 'connection-status offline';
                statusElement.innerHTML = '<i class="fas fa-wifi-slash"></i> Offline';
            }
        }

        // Update queue counter
        this.updateQueueCounter();
    }

    updateQueueCounter() {
        const counter = document.getElementById('offline-queue-counter');
        if (counter) {
            const count = this.offlineQueue.length;
            if (count > 0) {
                counter.textContent = count;
                counter.style.display = 'inline-block';
            } else {
                counter.style.display = 'none';
            }
        }
    }

    // Queue a request for later syncing
    queueRequest(method, url, data = null) {
        const request = {
            id: this.generateId(),
            method,
            url,
            data,
            timestamp: new Date().toISOString(),
            retries: 0
        };

        this.offlineQueue.push(request);
        this.saveQueue();
        this.updateQueueCounter();

        console.log('Request queued:', request);
        this.showNotification('Action saved. Will sync when online.', 'info');

        return request.id;
    }

    // Sync all queued requests
    async syncOfflineData() {
        if (this.syncInProgress || !this.isOnline) {
            console.log('Sync skipped - already in progress or offline');
            return;
        }

        if (this.offlineQueue.length === 0) {
            console.log('No data to sync');
            return;
        }

        this.syncInProgress = true;
        this.showNotification('Syncing offline data...', 'info');

        const syncResults = {
            success: 0,
            failed: 0,
            total: this.offlineQueue.length
        };

        // Process queue
        const queueCopy = [...this.offlineQueue];
        this.offlineQueue = [];

        for (const request of queueCopy) {
            try {
                await this.processQueuedRequest(request);
                syncResults.success++;
            } catch (error) {
                console.error('Failed to sync request:', error);
                request.retries++;
                
                // Re-queue if under retry limit
                if (request.retries < 3) {
                    this.offlineQueue.push(request);
                }
                syncResults.failed++;
            }
        }

        this.saveQueue();
        this.syncInProgress = false;
        this.updateQueueCounter();

        // Show results
        if (syncResults.failed === 0) {
            this.showNotification(
                `Successfully synced ${syncResults.success} ${syncResults.success === 1 ? 'item' : 'items'}`,
                'success'
            );
        } else {
            this.showNotification(
                `Synced ${syncResults.success}/${syncResults.total} items. ${syncResults.failed} failed.`,
                'warning'
            );
        }

        // Register background sync for any remaining items
        if (this.offlineQueue.length > 0) {
            this.registerBackgroundSync();
        }
    }

    async processQueuedRequest(request) {
        const response = await fetch(request.url, {
            method: request.method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: request.data ? JSON.stringify(request.data) : null
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return await response.json();
    }

    // Register background sync
    async registerBackgroundSync() {
        if ('serviceWorker' in navigator && 'sync' in navigator.serviceWorker) {
            try {
                const registration = await navigator.serviceWorker.ready;
                await registration.sync.register('sync-offline-data');
                console.log('Background sync registered');
            } catch (error) {
                console.error('Background sync registration failed:', error);
            }
        }
    }

    // Handle messages from service worker
    handleServiceWorkerMessage(message) {
        switch (message.type) {
            case 'SYNC_STARTED':
                console.log('Background sync started');
                break;
            case 'SYNC_COMPLETED':
                this.showNotification('Offline data synced successfully', 'success');
                this.offlineQueue = [];
                this.saveQueue();
                this.updateQueueCounter();
                break;
            case 'SYNC_FAILED':
                this.showNotification('Sync failed. Will retry later.', 'error');
                break;
        }
    }

    // Storage helpers
    loadQueue() {
        try {
            const stored = localStorage.getItem('offlineQueue');
            return stored ? JSON.parse(stored) : [];
        } catch (error) {
            console.error('Failed to load queue:', error);
            return [];
        }
    }

    saveQueue() {
        try {
            localStorage.setItem('offlineQueue', JSON.stringify(this.offlineQueue));
        } catch (error) {
            console.error('Failed to save queue:', error);
        }
    }

    // Utility functions
    generateId() {
        return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        // Add to page
        const container = document.getElementById('notification-container') || document.body;
        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

// Initialize on page load
let offlineManager;
document.addEventListener('DOMContentLoaded', () => {
    offlineManager = new OfflineManager();
});

// Export for use in other scripts
window.offlineManager = offlineManager;
