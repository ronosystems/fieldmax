/**
 * FIELDMAX - Global Auto-Refresh on Every Click
 * Add this script to your base template before </body>
 */

(function() {
    'use strict';
    
    // Configuration
    const REFRESH_DELAY = 300; // milliseconds before refresh
    const EXCLUDED_CLASSES = ['no-refresh', 'prevent-refresh'];
    const EXCLUDED_IDS = [];
    
    /**
     * Check if element should be excluded from auto-refresh
     */
    function shouldExclude(element) {
        // Check for excluded classes
        for (let className of EXCLUDED_CLASSES) {
            if (element.classList.contains(className)) {
                return true;
            }
        }
        
        // Check for excluded IDs
        if (EXCLUDED_IDS.includes(element.id)) {
            return true;
        }
        
        // Check if element or parent has data-no-refresh attribute
        let current = element;
        while (current) {
            if (current.hasAttribute && current.hasAttribute('data-no-refresh')) {
                return true;
            }
            current = current.parentElement;
        }
        
        return false;
    }
    
    /**
     * Handle click and refresh
     */
    function handleClickAndRefresh(event) {
        const element = event.currentTarget;
        
        // Skip if excluded
        if (shouldExclude(element)) {
            return;
        }
        
        // For links with href="#" or javascript:void(0), refresh immediately
        if (element.tagName === 'A') {
            const href = element.getAttribute('href');
            if (!href || href === '#' || href.startsWith('javascript:')) {
                setTimeout(() => {
                    window.location.reload();
                }, REFRESH_DELAY);
                return;
            }
        }
        
        // For buttons that don't submit forms, refresh after delay
        if (element.tagName === 'BUTTON' && element.type !== 'submit') {
            setTimeout(() => {
                window.location.reload();
            }, REFRESH_DELAY);
        }
        
        // For form submissions, refresh after submission
        if (element.tagName === 'BUTTON' && element.type === 'submit') {
            const form = element.closest('form');
            if (form) {
                // Let the form submit, then refresh
                setTimeout(() => {
                    window.location.reload();
                }, REFRESH_DELAY + 500);
            }
        }
    }
    
    /**
     * Attach listeners to all buttons and links
     */
    function attachListeners() {
        // Get all buttons and links
        const buttons = document.querySelectorAll('button');
        const links = document.querySelectorAll('a');
        
        // Attach to buttons
        buttons.forEach(button => {
            // Remove existing listener if any
            button.removeEventListener('click', handleClickAndRefresh);
            // Add new listener
            button.addEventListener('click', handleClickAndRefresh);
        });
        
        // Attach to links
        links.forEach(link => {
            // Remove existing listener if any
            link.removeEventListener('click', handleClickAndRefresh);
            // Add new listener
            link.addEventListener('click', handleClickAndRefresh);
        });
        
        console.log(`🔄 Auto-refresh enabled for ${buttons.length} buttons and ${links.length} links`);
    }
    
    /**
     * Initialize on DOM ready
     */
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', attachListeners);
        } else {
            attachListeners();
        }
        
        // Re-attach listeners when new content is added (for dynamic content)
        const observer = new MutationObserver((mutations) => {
            let shouldReattach = false;
            
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Element node
                        if (node.tagName === 'BUTTON' || node.tagName === 'A') {
                            shouldReattach = true;
                        } else if (node.querySelectorAll) {
                            const hasButtons = node.querySelectorAll('button, a').length > 0;
                            if (hasButtons) shouldReattach = true;
                        }
                    }
                });
            });
            
            if (shouldReattach) {
                attachListeners();
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Start the auto-refresh system
    init();
    
    // Expose a way to disable refresh for specific elements
    window.FieldMaxAutoRefresh = {
        disable: function(selector) {
            document.querySelectorAll(selector).forEach(el => {
                el.setAttribute('data-no-refresh', 'true');
            });
        },
        enable: function(selector) {
            document.querySelectorAll(selector).forEach(el => {
                el.removeAttribute('data-no-refresh');
            });
        }
    };
    
})();
