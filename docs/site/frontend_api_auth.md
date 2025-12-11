# Frontend API Authentication Guide

This guide explains how to configure your React frontend to authenticate with the Django-CRM API using JWT (JSON Web Token) authentication.

## Overview

The Django-CRM API uses JWT authentication for API requests. This means your React application needs to:

1. Obtain JWT tokens by logging in with username/password
2. Store access and refresh tokens securely
3. Send the access token in the Authorization header with every request
4. Refresh tokens when they expire

## Configuration

### 1. Axios Configuration with JWT

```javascript
import axios from 'axios';

// Create an axios instance
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  headers: {
    'Content-Type': 'application/json',
  }
});

// Request interceptor to add JWT token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;
    
    // If token expired, try to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post('http://127.0.0.1:8000/api/token/refresh/', {
          refresh: refreshToken
        });
        
        const { access } = response.data;
        localStorage.setItem('access_token', access);
        
        // Retry original request with new token
        originalRequest.headers['Authorization'] = `Bearer ${access}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;
```

### 2. Fetch API Configuration with JWT

```javascript
// Helper function to get token
const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
};

// Example fetch request
fetch('http://127.0.0.1:8000/api/leads/?page=1&page_size=10', {
  method: 'GET',
  headers: getAuthHeaders(),
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 3. Using the Configured Client

```javascript
// LeadsList.jsx example
import api from './client';

const fetchLeads = async () => {
  try {
    const response = await api.get('/leads/?page=1&page_size=10');
    console.log('Leads:', response.data);
  } catch (error) {
    console.error('Error fetching leads:', error);
  }
};
```

## Authentication Flow

### 1. Login with JWT Tokens

To authenticate with the API, you need to obtain JWT tokens:

```javascript
import axios from 'axios';

const login = async (username, password) => {
  try {
    const response = await axios.post('http://127.0.0.1:8000/api/token/', {
      username,
      password
    });
    
    const { access, refresh } = response.data;
    
    // Store tokens in localStorage
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    
    return response.data;
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
};

// Usage in React component
const handleLogin = async (e) => {
  e.preventDefault();
  try {
    await login(username, password);
    console.log('Login successful!');
    // Redirect to dashboard or home page
    window.location.href = '/dashboard';
  } catch (error) {
    console.error('Login failed:', error.response?.data);
  }
};
```

### 2. Refresh Access Token

Access tokens expire after 60 minutes. Use the refresh token to get a new access token:

```javascript
const refreshAccessToken = async () => {
  try {
    const refreshToken = localStorage.getItem('refresh_token');
    const response = await axios.post('http://127.0.0.1:8000/api/token/refresh/', {
      refresh: refreshToken
    });
    
    const { access } = response.data;
    localStorage.setItem('access_token', access);
    
    return access;
  } catch (error) {
    console.error('Token refresh failed:', error);
    // Redirect to login if refresh fails
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
    throw error;
  }
};
```

### 3. Check Authentication Status

Use the `/api/auth/status/` endpoint to verify authentication:

```javascript
import api from './client';

const checkAuth = async () => {
  try {
    const response = await api.get('/auth/status/');
    console.log('Auth status:', response.data);
    
    if (response.data.authenticated) {
      console.log('User:', response.data.user);
      console.log('Auth method:', response.data.auth_method); // 'JWT'
    } else {
      console.log('Not authenticated');
    }
  } catch (error) {
    console.error('Error checking auth:', error);
  }
};
```

### 4. Logout

To logout, simply remove the tokens from storage:

```javascript
const logout = () => {
  // Remove tokens from localStorage
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  
  // Redirect to login page
  window.location.href = '/login';
};
```

## JWT Token Configuration

The backend JWT settings:

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # 1 hour
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # 7 days
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

## CORS Configuration

The backend is already configured to accept requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:8080`
- `http://127.0.0.1:8080`

If your frontend runs on a different port, add it to `CORS_ALLOWED_ORIGINS` in `webcrm/settings.py`.

## Troubleshooting

### Issue: 401 Unauthorized

**Problem**: API returns 401 error.

**Solution**: 
1. Check that you have valid JWT tokens stored in localStorage
2. Verify token hasn't expired (access tokens expire after 60 minutes)
3. Try logging in again to get fresh tokens
4. Use `/api/auth/status/` to check authentication state

### Issue: Token Expired

**Problem**: Access token expired, getting 401 errors.

**Solution**:
1. Use the refresh token to get a new access token
2. The axios interceptor should handle this automatically
3. If refresh token also expired, user needs to login again

### Issue: Invalid Token

**Problem**: Token is invalid or malformed.

**Solution**:
1. Clear localStorage and login again
2. Check that token is being sent correctly in Authorization header
3. Verify format: `Authorization: Bearer <token>`

### Issue: CORS Errors

**Problem**: Browser blocks requests due to CORS policy.

**Solution**:
1. Add your frontend origin to `CORS_ALLOWED_ORIGINS` in settings
2. Check that response headers include proper CORS headers
3. Verify CORS configuration in backend settings

## Complete Example: client.js

```javascript
import axios from 'axios';

// Create axios instance
const client = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/api',
  headers: {
    'Content-Type': 'application/json',
  }
});

// Request interceptor to add JWT token
client.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// Response interceptor for token refresh and error handling
client.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;
    
    // If 401 and not already retrying, try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }
        
        const response = await axios.post(
          `${process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/api'}/token/refresh/`,
          { refresh: refreshToken }
        );
        
        const { access } = response.data;
        localStorage.setItem('access_token', access);
        
        // Retry original request with new token
        originalRequest.headers['Authorization'] = `Bearer ${access}`;
        return client(originalRequest);
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export default client;
```

## Production Considerations

For production deployment:

1. **Use HTTPS**: Set `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True`
2. **Update CORS origins**: Replace localhost URLs with your production domains
3. **Set SameSite=Strict**: Consider `SESSION_COOKIE_SAMESITE = 'Strict'` for better security
4. **Use environment variables**: Don't hardcode API URLs

```javascript
// .env.production
REACT_APP_API_URL=https://api.yourcrm.com
```

## Testing Authentication

Use this simple script to test if authentication is working:

```javascript
import api from './client';

async function testAuth() {
  console.log('Testing authentication...');
  
  // 1. Check auth status
  try {
    const statusResponse = await api.get('/auth/status/');
    console.log('Auth Status:', statusResponse.data);
    
    if (!statusResponse.data.authenticated) {
      console.error('Not authenticated. Please login via Django admin first.');
      return;
    }
  } catch (error) {
    console.error('Error checking auth status:', error);
    return;
  }
  
  // 2. Try fetching leads
  try {
    const leadsResponse = await api.get('/leads/?page=1&page_size=10');
    console.log('Leads fetched successfully:', leadsResponse.data);
  } catch (error) {
    console.error('Error fetching leads:', error);
  }
}

// Run test
testAuth();
```

## Summary

To use JWT authentication with the Django-CRM API:

1. **Update your client.js** to include JWT token in Authorization header
2. **Login via `/api/token/`** endpoint with username/password to get tokens
3. **Store tokens** in localStorage (access_token and refresh_token)
4. **Send token with requests** in Authorization header: `Bearer <token>`
5. **Handle token refresh** automatically when access token expires
6. **Test with `/api/auth/status/`** to verify authentication

The backend is configured for JWT-only authentication. Session-based authentication has been removed from the API.
