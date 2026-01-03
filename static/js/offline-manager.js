// static/js/offline-manager.js - Enhanced with IndexedDB
class OfflineManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.syncInProgress = false;
        this.db = null;
        this.init();
    }

    async init() {
        await this.initDatabase();
        await this.registerServiceWorker();
        this.setupEventListeners();
        this.updateConnectionStatus();
        
        // Check for pending syncs
        if (this.isOnline) {
            const queueSize = await this.getQueueSize();
            if (queueSize > 0) {
                this.syncOfflineData();
            }
        }
        
        // Cache critical data
        await this.cacheOfflineData();
    }

    async initDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('FieldmaxOfflineDB', 2);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Requests queue
                if (!db.objectStoreNames.contains('requests')) {
                    const store = db.createObjectStore('requests', { 
                        keyPath: 'id',
                        autoIncrement: true 
                    });
                    store.createIndex('timestamp', 'timestamp');
                    store.createIndex('priority', 'priority');
                }
                
                // Cache for API responses
                if (!db.objectStoreNames.contains('cache')) {
                    db.createObjectStore('cache', { keyPath: 'url' });
                }
                
                // Failed requests for debugging
                if (!db.objectStoreNames.contains('failed')) {
                    db.createObjectStore('failed', { keyPath: 'id' });
                }
            };
            
            request.onsuccess = (event) => {
                this.db = event.target.result;
                console.log('IndexedDB initialized');
                resolve();
            };
            
            request.onerror = (event) => {
                console.error('IndexedDB error:', event.target.error);
                reject(event.target.error);
            };
        });
    }

    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/js/service-worker.js');
                console.log('Service Worker registered:', registration.scope);
                
                // Check for updates daily
                if (registration.active) {
                    registration.addEventListener('updatefound', () => {
                        const newWorker = registration.installing;
                        console.log('Service Worker update found');
                        
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                this.showNotification('New version available. Refresh to update.', 'info');
                            }
                        });
                    });
                }
                
                // Register periodic sync for cache updates
                if ('periodicSync' in registration) {
                    try {
                        await registration.periodicSync.register('update-cache', {
                            minInterval: 24 * 60 * 60 * 1000 // Once per day
                        });
                        console.log('Periodic sync registered');
                    } catch (error) {
                        console.log('Periodic sync not supported:', error);
                    }
                }
                
                return registration;
            } catch (error) {
                console.error('Service Worker registration failed:', error);
                throw error;
            }
        }
    }

    setupEventListeners() {
        // Network status
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
        
        // Service worker messages
        navigator.serviceWorker?.addEventListener('message', (event) => {
            this.handleServiceWorkerMessage(event.data);
        });
        
        // Visibility change for sync on tab focus
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isOnline) {
                this.syncOfflineData();
            }
        });
        
        // Store page data before unload
        window.addEventListener('beforeunload', () => {
            this.saveCurrentPageState();
        });
    }

    async cacheOfflineData() {
        if (!this.isOnline) return;
        
        try {
            const response = await fetch('/api/offline-data/', {
                headers: {
                    'Cache-Control': 'max-age=3600' // Cache for 1 hour
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                await this.storeInCache('/api/offline-data/', data);
                
                // Also cache critical pages
                await this.cacheCriticalPages();
            }
        } catch (error) {
            console.error('Failed to cache offline data:', error);
        }
    }

    async cacheCriticalPages() {
        const pages = ['/', '/shop/', '/categories/'];
        
        for (const page of pages) {
            try {
                const response = await fetch(page);
                if (response.ok) {
                    const cache = await caches.open('fieldmax-pages');
                    await cache.put(page, response);
                }
            } catch (error) {
                console.error('Failed to cache page:', page, error);
            }
        }
    }

    async queueRequest(method, url, data = null, priority = 'normal') {
        const request = {
            id: Date.now() + '-' + Math.random().toString(36).substr(2, 9),
            method,
            url,
            data,
            timestamp: new Date().toISOString(),
            priority: this.getPriorityValue(priority),
            retries: 0,
            maxRetries: 3
        };

        await this.addToQueue(request);
        await this.updateQueueCounter();
        
        this.showNotification('Action saved for offline sync', 'info');
        
        // Register background sync if online
        if (this.isOnline) {
            await this.registerBackgroundSync();
        }
        
        return request.id;
    }

    getPriorityValue(priority) {
        const priorities = {
            'critical': 0,
            'high': 1,
            'normal': 2,
            'low': 3
        };
        return priorities[priority] || 2;
    }

    async addToQueue(request) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['requests'], 'readwrite');
            const store = transaction.objectStore('requests');
            const addRequest = store.add(request);
            
            addRequest.onsuccess = () => resolve();
            addRequest.onerror = (event) => reject(event.target.error);
        });
    }

    async getQueueSize() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['requests'], 'readonly');
            const store = transaction.objectStore('requests');
            const countRequest = store.count();
            
            countRequest.onsuccess = () => resolve(countRequest.result);
            countRequest.onerror = (event) => reject(event.target.error);
        });
    }

    async syncOfflineData() {
        if (this.syncInProgress || !this.isOnline) return;
        
        this.syncInProgress = true;
        this.showNotification('Syncing offline data...', 'info');
        
        try {
            const requests = await this.getQueuedRequests();
            let successCount = 0;
            let failCount = 0;
            
            for (const request of requests) {
                try {
                    await this.processQueuedRequest(request);
                    await this.removeFromQueue(request.id);
                    successCount++;
                    
                    // Emit event for UI updates
                    this.emitSyncEvent('request-synced', { request, success: true });
                } catch (error) {
                    console.error('Failed to sync request:', error);
                    request.retries++;
                    
                    if (request.retries >= request.maxRetries) {
                        await this.moveToFailed(request, error.message);
                        await this.removeFromQueue(request.id);
                    } else {
                        await this.updateRequest(request);
                    }
                    
                    failCount++;
                    this.emitSyncEvent('request-failed', { request, error: error.message });
                }
                
                // Small delay between requests
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            // Show summary
            if (successCount > 0) {
                this.showNotification(
                    `Synced ${successCount} ${successCount === 1 ? 'item' : 'items'}`,
                    'success'
                );
            }
            
            if (failCount > 0) {
                this.showNotification(
                    `${failCount} ${failCount === 1 ? 'item' : 'items'} failed to sync`,
                    'warning'
                );
            }
            
        } catch (error) {
            console.error('Sync process failed:', error);
            this.showNotification('Sync failed. Will retry later.', 'error');
        } finally {
            this.syncInProgress = false;
            await this.updateQueueCounter();
        }
    }

    async getQueuedRequests(limit = 50) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['requests'], 'readonly');
            const store = transaction.objectStore('requests');
            const index = store.index('priority');
            const requests = [];
            
            index.openCursor().onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor && requests.length < limit) {
                    requests.push(cursor.value);
                    cursor.continue();
                } else {
                    resolve(requests);
                }
            };
            
            index.openCursor().onerror = (event) => reject(event.target.error);
        });
    }

    async removeFromQueue(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['requests'], 'readwrite');
            const store = transaction.objectStore('requests');
            const deleteRequest = store.delete(id);
            
            deleteRequest.onsuccess = () => resolve();
            deleteRequest.onerror = (event) => reject(event.target.error);
        });
    }

    async moveToFailed(request, error) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['failed'], 'readwrite');
            const store = transaction.objectStore('failed');
            const failedRequest = {
                ...request,
                error,
                failedAt: new Date().toISOString()
            };
            
            const addRequest = store.add(failedRequest);
            addRequest.onsuccess = () => resolve();
            addRequest.onerror = (event) => reject(event.target.error);
        });
    }

    async updateQueueCounter() {
        const count = await this.getQueueSize();
        const counter = document.getElementById('offline-queue-counter');
        const badge = document.querySelector('.offline-queue-badge');
        
        if (counter) {
            counter.textContent = count;
        }
        
        if (badge) {
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
        
        // Update badge with animation if count changed
        if (count > 0) {
            counter?.classList.add('pulse');
            setTimeout(() => counter?.classList.remove('pulse'), 1000);
        }
    }

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

    async storeInCache(key, data) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['cache'], 'readwrite');
            const store = transaction.objectStore('cache');
            const item = {
                url: key,
                data: data,
                timestamp: new Date().toISOString(),
                expires: Date.now() + (24 * 60 * 60 * 1000) // 24 hours
            };
            
            const request = store.put(item);
            request.onsuccess = () => resolve();
            request.onerror = (event) => reject(event.target.error);
        });
    }

    async getFromCache(key) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['cache'], 'readonly');
            const store = transaction.objectStore('cache');
            const request = store.get(key);
            
            request.onsuccess = () => {
                const item = request.result;
                if (item && item.expires > Date.now()) {
                    resolve(item.data);
                } else {
                    resolve(null);
                }
            };
            
            request.onerror = (event) => reject(event.target.error);
        });
    }

    emitSyncEvent(eventName, detail) {
        const event = new CustomEvent(eventName, { detail });
        window.dispatchEvent(event);
    }

    // Existing utility methods remain the same...
    handleOnline() { /* ... */ }
    handleOffline() { /* ... */ }
    updateConnectionStatus() { /* ... */ }
    processQueuedRequest(request) { /* ... */ }
    handleServiceWorkerMessage(message) { /* ... */ }
    showNotification(message, type = 'info') { /* ... */ }
    getCookie(name) { /* ... */ }
    saveCurrentPageState() { /* ... */ }
}

// Initialize
let offlineManager;
document.addEventListener('DOMContentLoaded', async () => {
    try {
        offlineManager = new OfflineManager();
        window.offlineManager = offlineManager;
        console.log('Offline Manager initialized');
    } catch (error) {
        console.error('Failed to initialize Offline Manager:', error);
    }
});