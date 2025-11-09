// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Event Listeners
    document.getElementById('proxy_type').addEventListener('change', toggleProxyConfig);
    document.getElementById('sessionForm').addEventListener('submit', handleSessionSubmit);
    document.getElementById('profileForm').addEventListener('submit', handleProfileSubmit);
    document.getElementById('refreshLogs').addEventListener('click', loadLogs);
    document.getElementById('clearLogs').addEventListener('click', clearLogs);

    // Load initial data
    loadProfiles();
    loadActiveSessions();
    loadLogs();

    // Auto-refresh every 10 seconds
    setInterval(loadActiveSessions, 10000);
    setInterval(loadLogs, 15000);
}

function toggleProxyConfig() {
    const proxyType = document.getElementById('proxy_type').value;
    const proxyConfig = document.getElementById('proxy_config');
    
    if (proxyType === 'direct' || proxyType === 'vpn') {
        proxyConfig.classList.add('hidden');
    } else {
        proxyConfig.classList.remove('hidden');
    }
}

async function handleSessionSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const sessionData = {
        profile_type: formData.get('profile_type'),
        profile_count: parseInt(formData.get('profile_count')),
        target_url: formData.get('target_url'),
        proxy_type: formData.get('proxy_type'),
        proxy_host: formData.get('proxy_host'),
        proxy_port: formData.get('proxy_port'),
        proxy_username: formData.get('proxy_username'),
        proxy_password: formData.get('proxy_password'),
        session_duration: parseInt(formData.get('session_duration'))
    };

    try {
        const response = await fetch('/api/create_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(sessionData)
        });

        const result = await response.json();
        
        if (result.success) {
            showNotification('Session berhasil dibuat!', 'success');
            loadActiveSessions();
            e.target.reset();
        } else {
            showNotification('Gagal membuat session: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function handleProfileSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const profileData = {
        profile_name: formData.get('profile_name'),
        profile_type: formData.get('profile_type'),
        custom_user_agent: formData.get('custom_user_agent')
    };

    try {
        const response = await fetch('/api/create_profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(profileData)
        });

        const result = await response.json();
        
        if (result.success) {
            showNotification('Profil berhasil dibuat!', 'success');
            loadProfiles();
            e.target.reset();
        } else {
            showNotification('Gagal membuat profil: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function loadProfiles() {
    try {
        const response = await fetch('/api/profiles');
        const profiles = await response.json();
        
        const container = document.getElementById('profilesContainer');
        container.innerHTML = profiles.map(profile => `
            <div class="profile-item">
                <strong>${profile.profile_name}</strong> (${profile.profile_type})
                <div>User Agent: ${profile.user_agent.substring(0, 50)}...</div>
                <div>Created: ${new Date(profile.created_at).toLocaleString()}</div>
                <button onclick="deleteProfile('${profile.profile_id}')" class="btn-danger">Delete</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading profiles:', error);
    }
}

async function loadActiveSessions() {
    try {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();
        
        const container = document.getElementById('sessionsContainer');
        container.innerHTML = sessions.map(session => `
            <div class="session-item ${session.status}">
                <strong>Session ${session.session_id}</strong>
                <div>Profile: ${session.profile_name}</div>
                <div>Status: ${session.status} - ${session.current_step}</div>
                <div>Progress: ${session.progress}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${session.progress}%"></div>
                </div>
                <div>Started: ${new Date(session.start_time).toLocaleString()}</div>
                <button onclick="stopSession('${session.session_id}')" class="btn-danger">Stop</button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

async function loadLogs() {
    try {
        const response = await fetch('/api/logs');
        const logs = await response.json();
        
        const container = document.getElementById('logsContainer');
        container.innerHTML = logs.slice(-20).reverse().map(log => `
            <div class="log-item ${log.status}">
                <div class="log-header">
                    <strong>${log.step}</strong> 
                    <span class="log-time">${new Date(log.timestamp).toLocaleString()}</span>
                </div>
                <div>Session: ${log.session_id}</div>
                <div>Status: <span class="status-${log.status}">${log.status}</span></div>
                <div>Message: ${log.message}</div>
                ${log.details ? `<div class="log-details">Details: ${JSON.stringify(log.details)}</div>` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

async function deleteProfile(profileId) {
    if (confirm('Are you sure you want to delete this profile?')) {
        try {
            const response = await fetch(`/api/delete_profile/${profileId}`, {
                method: 'DELETE'
            });
            const result = await response.json();
            
            if (result.success) {
                showNotification('Profil berhasil dihapus!', 'success');
                loadProfiles();
            } else {
                showNotification('Gagal menghapus profil', 'error');
            }
        } catch (error) {
            showNotification('Error: ' + error.message, 'error');
        }
    }
}

async function stopSession(sessionId) {
    try {
        const response = await fetch(`/api/stop_session/${sessionId}`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.success) {
            showNotification('Session dihentikan!', 'success');
            loadActiveSessions();
        } else {
            showNotification('Gagal menghentikan session', 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function clearLogs() {
    if (confirm('Are you sure you want to clear all logs?')) {
        try {
            const response = await fetch('/api/clear_logs', {
                method: 'DELETE'
            });
            const result = await response.json();
            
            if (result.success) {
                showNotification('Logs cleared!', 'success');
                loadLogs();
            }
        } catch (error) {
            showNotification('Error clearing logs', 'error');
        }
    }
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 5px;
        color: white;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    notification.style.background = type === 'success' ? '#2ecc71' : 
                                  type === 'error' ? '#e74c3c' : '#3498db';
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// CSS for notification animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    .status-success { color: #2ecc71; font-weight: bold; }
    .status-error { color: #e74c3c; font-weight: bold; }
    .status-warning { color: #f39c12; font-weight: bold; }
    .status-running { color: #3498db; font-weight: bold; }
    
    .log-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 5px;
    }
    
    .log-time {
        font-size: 0.8em;
        color: #7f8c8d;
    }
    
    .log-details {
        font-size: 0.9em;
        color: #555;
        margin-top: 5px;
        background: #f8f9fa;
        padding: 5px;
        border-radius: 3px;
    }
`;
document.head.appendChild(style);
