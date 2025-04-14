// Authentication related JavaScript

// Add a debug log helper
function authLog(message, data = null) {
    console.log(`[Auth] ${message}`, data || '');
    
    // Send log to server (non-blocking)
    try {
        fetch('/auth/log', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                details: data || {}  // Ensure we always send an object
            })
        }).catch(e => {});
    } catch (e) {}
}

// Global timestamp for token refresh checks
let lastTokenCheck = 0;

document.addEventListener('DOMContentLoaded', () => {
    authLog('Auth script loaded', { path: window.location.pathname });
    
    // Check if we're on the main page
    if (window.location.pathname === '/' || window.location.pathname === '') {
        // Check token validity at page load
        checkAndRefreshToken().then(authenticated => {
            authLog('On main page, authentication check:', authenticated);
            
            if (!authenticated) {
                authLog('Not authenticated on main page, redirecting to login');
                window.location.href = '/login';
                return;
            } else {
                authLog('User is authenticated, proceeding with app initialization');
                // This will happen after all scripts are loaded
                return;
            }
        });
    }
    
    // Handle login form submission
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        authLog('Login form detected');
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorElement = document.getElementById('login-error');
            
            // Form data must be sent as x-www-form-urlencoded for OAuth2 compliance
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);
            
            try {
                errorElement.textContent = '';
                errorElement.classList.remove('active');
                
                authLog('Attempting login for user:', username);
                const response = await fetch('/auth/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: formData
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Login failed. Please check your credentials.');
                }
                
                // Store token in localStorage
                authLog('Login successful, storing token');
                localStorage.setItem('auth_token', data.access_token);
                localStorage.setItem('token_expires', data.expires_at);
                localStorage.setItem('username', username);
                
                // Log token expiration info
                const expiresAt = data.expires_at;
                const now = Math.floor(Date.now() / 1000);
                authLog('Token expiration details', { 
                    expiresAt, 
                    now, 
                    difference: expiresAt - now,
                    expiresDate: new Date(expiresAt * 1000).toLocaleString()
                });
                
                // Hard reload to the main page (bypassing any caching)
                window.location.href = "/?t=" + now;
            } catch (error) {
                authLog('Login error:', error.message);
                errorElement.textContent = error.message;
                errorElement.classList.add('active');
            }
        });
    }
    
    // Handle registration form submission
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        authLog('Register form detected');
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm-password').value;
            const errorElement = document.getElementById('register-error');
            
            // Basic validation
            if (password !== confirmPassword) {
                errorElement.textContent = 'Passwords do not match';
                errorElement.classList.add('active');
                return;
            }
            
            try {
                errorElement.textContent = '';
                errorElement.classList.remove('active');
                
                authLog('Attempting registration for user:', username);
                const response = await fetch('/auth/users', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        username,
                        email,
                        password,
                        is_active: true
                    })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Registration failed');
                }
                
                authLog('Registration successful, redirecting to login');
                // Redirect to login page
                window.location.href = '/login?registered=true';
            } catch (error) {
                authLog('Registration error:', error.message);
                errorElement.textContent = error.message;
                errorElement.classList.add('active');
            }
        });
    }
    
    // Check if we need to show messages
    if (window.location.href.includes('login?registered=true')) {
        const errorElement = document.getElementById('login-error');
        errorElement.textContent = 'Registration successful! Please login with your credentials.';
        errorElement.style.backgroundColor = 'rgba(40, 167, 69, 0.1)';
        errorElement.style.color = '#28a745';
        errorElement.classList.add('active');
    } else if (window.location.href.includes('login?session_expired=true')) {
        const errorElement = document.getElementById('login-error');
        errorElement.textContent = 'Your session has expired. Please login again.';
        errorElement.classList.add('active');
    } else if (window.location.href.includes('login?auth_error=true')) {
        const errorElement = document.getElementById('login-error');
        errorElement.textContent = 'Authentication error. Please login again.';
        errorElement.classList.add('active');
    }
});

// Function to check if token is valid and needs refreshing
async function checkAndRefreshToken() {
    const token = localStorage.getItem('auth_token');
    const expires = localStorage.getItem('token_expires');
    
    if (!token || !expires) {
        authLog('No token found or missing expiration');
        return false;
    }
    
    // Check if token is expired
    const now = Math.floor(Date.now() / 1000);
    const expiresAt = parseInt(expires);
    
    // Only update status once per second max
    if (now - lastTokenCheck < 1) {
        return isAuthenticated();
    }
    
    lastTokenCheck = now;
    
    authLog('Token expiration check', { now, expiresAt, difference: expiresAt - now });
    
    if (now >= expiresAt) {
        // Token expired, clean up
        authLog('Token expired', { now, expiresAt });
        logout(true);
        return false;
    }

    // Check if token will expire soon (within 5 minutes) - could add token refresh logic here
    if (expiresAt - now < 300) {
        authLog('Token expiring soon', { now, expiresAt, timeLeft: expiresAt - now });
        // In a production app, we would refresh the token here
    }
    
    // Validate token with server
    try {
        const response = await fetch('/auth/validate-token', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            authLog('Token validation failed', response.status);
            logout(true);
            return false;
        }
        
        authLog('Token validated successfully');
        return true;
    } catch (error) {
        authLog('Token validation error', error);
        return isAuthenticated(); // Fall back to local check
    }
}

// Function to logout
function logout(expired = false) {
    authLog('Logging out user', expired ? 'Token expired' : 'User initiated');
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expires');
    localStorage.removeItem('username');
    
    if (expired) {
        window.location.href = '/login?session_expired=true';
    } else {
        window.location.href = '/login';
    }
}

// Function to check if user is authenticated
function isAuthenticated() {
    const token = localStorage.getItem('auth_token');
    const expires = localStorage.getItem('token_expires');
    
    if (!token || !expires) {
        authLog('No token found or missing expiration');
        return false;
    }
    
    // Check if token is expired
    const now = Math.floor(Date.now() / 1000);
    const expiresAt = parseInt(expires);
    
    if (now >= expiresAt) {
        // Token expired, clean up
        authLog('Token expired', { now, expiresAt });
        localStorage.removeItem('auth_token');
        localStorage.removeItem('token_expires');
        localStorage.removeItem('username');
        return false;
    }
    
    authLog('User is authenticated, token valid until', new Date(expiresAt * 1000).toLocaleString());
    return true;
}

// Add auth token to all fetch requests
if (typeof window.originalFetch === 'undefined') {
    window.originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        // Only add auth header for API endpoints, not for static assets or auth endpoints
        if (typeof url === 'string' && url.startsWith('/') && 
            !url.startsWith('/static/') && 
            !url.includes('/auth/token') && 
            !url.includes('/auth/log')) {
            
            const token = localStorage.getItem('auth_token');
            
            if (token) {
                options.headers = {
                    ...options.headers,
                    'Authorization': `Bearer ${token}`
                };
            }
        }
        return window.originalFetch(url, options)
            .then(response => {
                // Check for 401 Unauthorized responses
                if (response.status === 401) {
                    // Token might be invalid or expired
                    authLog('Received 401 unauthorized response', { url });
                    
                    // Don't redirect if this is already a validation request
                    if (!url.includes('/auth/validate-token')) {
                        logout(true);
                    }
                }
                return response;
            });
    };
}
