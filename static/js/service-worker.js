// static/js/service-worker.js
const CACHE_NAME = 'fieldmax-shop-v4';
const OFFLINE_URL = '/offline/';
const SYNC_TAG = 'sync-offline-data';

// Assets to cache immediately
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/offline-manager.js',
    '/static/js/app.js',
    '/static/images/LOGO.jpg',
    OFFLINE_URL,
    '/api/offline-data/', // Cache API data
    '/manifest.json'
];

self.addEventListener('install', (event) => {
    console.log('Service Worker installing...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    console.log('Service Worker activating...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Enhanced fetch handler with network-first for API, cache-first for static
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // API requests - network first, fallback to cache
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    // Cache successful API responses
                    if (response.ok) {
                        const clonedResponse = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, clonedResponse);
                        });
                    }
                    return response;
                })
                .catch(() => {
                    // Fallback to cache for API
                    return caches.match(event.request);
                })
        );
        return;
    }
    
    // HTML pages - network first, fallback to offline page
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(OFFLINE_URL))
        );
        return;
    }
    
    // Static assets - cache first, fallback to network
    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    // Update cache in background
                    fetch(event.request).then((response) => {
                        if (response.ok) {
                            caches.open(CACHE_NAME).then((cache) => {
                                cache.put(event.request, response);
                            });
                        }
                    });
                    return cachedResponse;
                }
                return fetch(event.request);
            })
    );
});

// Background sync handler
self.addEventListener('sync', (event) => {
    console.log('Background sync:', event.tag);
    
    if (event.tag === SYNC_TAG) {
        event.waitUntil(syncOfflineData());
    }
});

// Periodic sync for background updates
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'update-cache') {
        event.waitUntil(updateCachedData());
    }
});

async function syncOfflineData() {
    console.log('Processing background sync');
    
    // Notify client sync started
    self.clients.matchAll().then((clients) => {
        clients.forEach((client) => {
            client.postMessage({ type: 'SYNC_STARTED' });
        });
    });
    
    try {
        // Get queued data from IndexedDB
        const queue = await getQueuedRequests();
        
        for (const request of queue) {
            try {
                await processQueuedRequest(request);
                await removeFromQueue(request.id);
            } catch (error) {
                console.error('Failed to sync request:', error);
                // Keep failed requests for retry
            }
        }
        
        // Notify success
        self.clients.matchAll().then((clients) => {
            clients.forEach((client) => {
                client.postMessage({ type: 'SYNC_COMPLETED' });
            });
        });
    } catch (error) {
        console.error('Background sync failed:', error);
        self.clients.matchAll().then((clients) => {
            clients.forEach((client) => {
                client.postMessage({ type: 'SYNC_FAILED' });
            });
        });
    }
}

async function updateCachedData() {
    console.log('Updating cached data');
    
    const cache = await caches.open(CACHE_NAME);
    const apiUrls = [
        '/api/offline-data/',
        '/api/categories/',
        '/api/products/'
    ];
    
    for (const url of apiUrls) {
        try {
            const response = await fetch(url);
            if (response.ok) {
                await cache.put(url, response);
            }
        } catch (error) {
            console.error('Failed to update cache for:', url);
        }
    }
}

// IndexedDB for queued requests
const DB_NAME = 'OfflineQueueDB';
const DB_VERSION = 1;
const STORE_NAME = 'requests';

async function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id' });
            }
        };
        
        request.onsuccess = (event) => resolve(event.target.result);
        request.onerror = (event) => reject(event.target.error);
    });
}

async function getQueuedRequests() {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        
        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => reject(request.error);
    });
}

async function removeFromQueue(id) {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(id);
        
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
}