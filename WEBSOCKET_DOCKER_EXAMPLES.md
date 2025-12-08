# 🔌 WebSocket Examples - Docker Setup

Practical examples of using WebSocket in Docker-deployed Django CRM.

## 📋 Quick Access

- **WebSocket URL**: `ws://localhost:8001/ws/chat/<room_name>/`
- **Test Page**: `http://localhost:8000/common/websocket-test/`
- **Production**: `wss://yourdomain.com/ws/chat/<room_name>/`

## 🧪 Testing WebSocket

### 1. Browser Console Test

```javascript
// Connect to chat room
const ws = new WebSocket('ws://localhost:8001/ws/chat/test/');

// Connection opened
ws.onopen = (event) => {
    console.log('✅ Connected to WebSocket');
    
    // Send a message
    ws.send(JSON.stringify({
        message: 'Hello from browser!',
        username: 'TestUser'
    }));
};

// Receive messages
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('📩 Received:', data);
};

// Connection closed
ws.onclose = (event) => {
    console.log('❌ Disconnected');
};

// Error handler
ws.onerror = (error) => {
    console.error('⚠️ WebSocket error:', error);
};
```

### 2. Python Client Test

```python
# test_websocket.py
import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://localhost:8001/ws/chat/test/"
    
    async with websockets.connect(uri) as websocket:
        print("✅ Connected!")
        
        # Send message
        message = {
            'message': 'Hello from Python!',
            'username': 'PythonClient'
        }
        await websocket.send(json.dumps(message))
        print(f"📤 Sent: {message}")
        
        # Receive messages
        try:
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"📩 Received: {data}")
        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection closed")

# Run
asyncio.run(test_chat())
```

Run inside Docker:
```bash
# Install websockets library
docker-compose exec web pip install websockets

# Run test script
docker-compose exec web python test_websocket.py
```

### 3. Using `wscat` (Node.js)

```bash
# Install wscat
npm install -g wscat

# Connect to chat
wscat -c ws://localhost:8001/ws/chat/test/

# Send message
> {"message": "Hello!", "username": "WSCat"}

# You'll see responses in real-time
```

### 4. Using `websocat` (Rust)

```bash
# Install websocat
cargo install websocat

# Or download binary from GitHub

# Connect and interact
websocat ws://localhost:8001/ws/chat/test/

# Type and send JSON
{"message": "Test message", "username": "Websocat"}
```

## 🎯 Real-World Examples

### Example 1: Real-time Chat Room

```javascript
class ChatRoom {
    constructor(roomName, username) {
        this.roomName = roomName;
        this.username = username;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8001/ws/chat/${this.roomName}/`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('✅ Connected to room:', this.roomName);
            this.reconnectAttempts = 0;
            this.onConnect();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('❌ Disconnected from room');
            this.onDisconnect();
            this.reconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('⚠️ WebSocket error:', error);
        };
    }
    
    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            console.log(`🔄 Reconnecting in ${delay/1000}s... (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        }
    }
    
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                message: message,
                username: this.username
            }));
        } else {
            console.error('WebSocket is not connected');
        }
    }
    
    handleMessage(data) {
        switch(data.type) {
            case 'connection_established':
                console.log('👋', data.message);
                break;
            case 'chat':
                this.displayMessage(data.username, data.message);
                break;
            case 'error':
                console.error('Error:', data.message);
                break;
        }
    }
    
    displayMessage(username, message) {
        console.log(`${username}: ${message}`);
        // Update UI here
    }
    
    onConnect() {
        // Called when connected
        document.getElementById('status').textContent = 'Connected';
    }
    
    onDisconnect() {
        // Called when disconnected
        document.getElementById('status').textContent = 'Disconnected';
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Usage
const chat = new ChatRoom('general', 'JohnDoe');
chat.connect();

// Send message
document.getElementById('sendBtn').onclick = () => {
    const message = document.getElementById('messageInput').value;
    chat.sendMessage(message);
};
```

### Example 2: Real-time Notifications

```javascript
class NotificationService {
    constructor() {
        this.ws = null;
        this.callbacks = [];
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8001/ws/notifications/`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('🔔 Notification service connected');
        };
        
        this.ws.onmessage = (event) => {
            const notification = JSON.parse(event.data);
            this.handleNotification(notification);
        };
    }
    
    handleNotification(notification) {
        // Display notification
        if (Notification.permission === 'granted') {
            new Notification(notification.message, {
                body: notification.message,
                icon: '/static/favicon.ico'
            });
        }
        
        // Call registered callbacks
        this.callbacks.forEach(callback => callback(notification));
    }
    
    onNotification(callback) {
        this.callbacks.push(callback);
    }
}

// Usage
const notifService = new NotificationService();
notifService.connect();

notifService.onNotification((notif) => {
    console.log('New notification:', notif);
    // Update UI
});
```

### Example 3: Multiple Rooms with Redux

```javascript
// WebSocket middleware for Redux
const wsMiddleware = (store) => {
    const sockets = {};
    
    return (next) => (action) => {
        switch(action.type) {
            case 'WS_CONNECT':
                const { roomName, username } = action.payload;
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.hostname}:8001/ws/chat/${roomName}/`;
                
                const socket = new WebSocket(wsUrl);
                
                socket.onopen = () => {
                    store.dispatch({ type: 'WS_CONNECTED', payload: { roomName } });
                };
                
                socket.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    store.dispatch({ type: 'WS_MESSAGE', payload: { roomName, data } });
                };
                
                socket.onclose = () => {
                    store.dispatch({ type: 'WS_DISCONNECTED', payload: { roomName } });
                };
                
                sockets[roomName] = socket;
                break;
                
            case 'WS_SEND':
                const room = action.payload.roomName;
                if (sockets[room] && sockets[room].readyState === WebSocket.OPEN) {
                    sockets[room].send(JSON.stringify(action.payload.message));
                }
                break;
                
            case 'WS_DISCONNECT':
                const roomToDisconnect = action.payload.roomName;
                if (sockets[roomToDisconnect]) {
                    sockets[roomToDisconnect].close();
                    delete sockets[roomToDisconnect];
                }
                break;
        }
        
        return next(action);
    };
};
```

## 🐳 Docker-Specific Tips

### 1. Testing from Host Machine

```bash
# WebSocket is exposed on port 8001
ws://localhost:8001/ws/chat/test/

# If using Nginx proxy
ws://localhost/ws/chat/test/
```

### 2. Testing from Another Container

```bash
# Use service name instead of localhost
ws://daphne:8001/ws/chat/test/

# Example: Run a test container
docker run -it --network crm_network python:3.11 bash
pip install websockets
python test_websocket.py
```

### 3. Load Testing with k6

```javascript
// websocket_load_test.js
import ws from 'k6/ws';
import { check } from 'k6';

export let options = {
    stages: [
        { duration: '30s', target: 50 },
        { duration: '1m', target: 100 },
        { duration: '30s', target: 0 },
    ],
};

export default function () {
    const url = 'ws://localhost:8001/ws/chat/load-test/';
    
    const response = ws.connect(url, function (socket) {
        socket.on('open', () => {
            console.log('Connected');
            socket.send(JSON.stringify({
                message: 'Load test message',
                username: 'LoadTester'
            }));
        });
        
        socket.on('message', (data) => {
            console.log('Received:', data);
        });
        
        socket.on('close', () => {
            console.log('Disconnected');
        });
        
        socket.setTimeout(() => {
            socket.close();
        }, 10000);
    });
    
    check(response, { 'status is 101': (r) => r && r.status === 101 });
}
```

Run load test:
```bash
k6 run websocket_load_test.js
```

### 4. Monitoring WebSocket Connections

```bash
# Check active connections in Redis
docker-compose exec redis redis-cli CLIENT LIST

# Monitor channel layer
docker-compose exec redis redis-cli MONITOR

# Check Daphne logs
docker-compose logs -f daphne | grep "WebSocket"

# View connection stats
docker-compose exec web python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> # Check channels
```

## 🔍 Debugging

### Enable Daphne Debug Logging

```yaml
# docker-compose.dev.yml
daphne:
  command: daphne -b 0.0.0.0 -p 8001 -v 2 webcrm.asgi:application
  environment:
    - DJANGO_LOG_LEVEL=DEBUG
```

### Check WebSocket Handshake

```bash
# Using curl
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://localhost:8001/ws/chat/test/
```

### Test with Postman

1. Open Postman
2. Create new WebSocket request
3. URL: `ws://localhost:8001/ws/chat/test/`
4. Click Connect
5. Send JSON messages

## 📊 Performance Tips

### 1. Scale Daphne Instances

```bash
# Run multiple Daphne servers
docker-compose up -d --scale daphne=3

# Nginx will load balance automatically
```

### 2. Optimize Redis

```yaml
redis:
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### 3. Monitor Performance

```bash
# Check Daphne memory usage
docker stats crm_daphne

# Check connection count
docker-compose exec daphne ps aux | grep daphne

# Redis memory usage
docker-compose exec redis redis-cli INFO memory
```

## 🚀 Production Considerations

### 1. Use WSS (Secure WebSocket)

```nginx
# nginx.conf
location /ws/ {
    proxy_pass http://daphne_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    
    # SSL settings
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 2. Set Proper Timeouts

```nginx
# Prevent connection drops
proxy_read_timeout 86400s;
proxy_send_timeout 86400s;
```

### 3. Enable Compression

```python
# webcrm/asgi.py
from channels.http import AsgiHandler

application = ProtocolTypeRouter({
    "http": AsgiHandler(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
```

## 📚 Additional Resources

- [Django Channels Docs](https://channels.readthedocs.io/)
- [Daphne Documentation](https://github.com/django/daphne)
- [WebSocket Protocol](https://tools.ietf.org/html/rfc6455)
- [Redis Pub/Sub](https://redis.io/topics/pubsub)

## 🆘 Common Issues

### Issue: Connection Refused
**Solution**: Check Daphne is running on port 8001
```bash
docker-compose ps daphne
docker-compose logs daphne
```

### Issue: Messages Not Broadcasting
**Solution**: Check Redis connection
```bash
docker-compose exec redis redis-cli ping
docker-compose exec web python manage.py shell
>>> from channels.layers import get_channel_layer
>>> await get_channel_layer().send('test', {'type': 'test'})
```

### Issue: High Memory Usage
**Solution**: Limit connections or scale horizontally
```bash
docker-compose up -d --scale daphne=3
```

---

**Happy WebSocket-ing! 🚀**
