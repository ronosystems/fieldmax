// static/js/service-worker.js
const CACHE_NAME = 'fieldmax-v1';
const OFFLINE_URL = '/offline/';
const API_CACHE = 'fieldmax-api-v1';

// Files to cache for offline use
const STATIC_CACHE_URLS = [
    '/',
    '/offline/',
    '/static/css/main.css',
    '/static/js/app.js',
    '/static/js/offline-manager.js',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Caching static assets');
                return cache.addAll(STATIC_CACHE_URLS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== API_CACHE) {
                        console.log('[ServiceWorker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Handle API requests
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleAPIRequest(request));
        return;
    }

    // Handle navigation requests
    if (request.mode === 'navigate') {
        event.respondWith(handleNavigationRequest(request));
        return;
    }

    // Handle static assets
    event.respondWith(handleStaticRequest(request));
});

// Handle API requests with network-first strategy
async function handleAPIRequest(request) {
    try {
        // Try network first
        const response = await fetch(request);
        
        // If successful, update cache
        if (response.ok) {
            const cache = await caches.open(API_CACHE);
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        console.log('[ServiceWorker] Network failed, trying cache:', request.url);
        
        // If network fails, try cache
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // If both fail, return offline response
        return new Response(JSON.stringify({
            error: 'offline',
            message: 'You are currently offline. This request will be synced when connection is restored.',
            timestamp: new Date().toISOString()
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Handle navigation requests
async function handleNavigationRequest(request) {
    try {
        const response = await fetch(request);
        return response;
    } catch (error) {
        console.log('[ServiceWorker] Navigation failed, serving offline page');
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match(OFFLINE_URL);
        return cachedResponse || new Response('Offline - Please check your connection');
    }
}

// Handle static assets with cache-first strategy
async function handleStaticRequest(request) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        console.log('[ServiceWorker] Static request failed:', request.url);
        return new Response('Resource not available offline', { status: 404 });
    }
}

// Background Sync - sync queued requests when online
self.addEventListener('sync', (event) => {
    console.log('[ServiceWorker] Background sync triggered:', event.tag);
    
    if (event.tag === 'sync-offline-data') {
        event.waitUntil(syncOfflineData());
    }
});

async function syncOfflineData() {
    console.log('[ServiceWorker] Syncing offline data...');
    
    try {
        // Notify all clients that sync is starting
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'SYNC_STARTED',
                timestamp: new Date().toISOString()
            });
        });

        // Trigger sync in the main app
        const response = await fetch('/api/sync-offline-queue/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            console.log('[ServiceWorker] Sync completed successfully');
            clients.forEach(client => {
                client.postMessage({
                    type: 'SYNC_COMPLETED',
                    timestamp: new Date().toISOString()
                });
            });
        } else {
            throw new Error('Sync failed');
        }
    } catch (error) {
        console.error('[ServiceWorker] Sync error:', error);
        
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'SYNC_FAILED',
                error: error.message,
                timestamp: new Date().toISOString()
            });
        });
    }
}

// Listen for messages from main app
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => caches.delete(cacheName))
                );
            })
        );
    }
});
