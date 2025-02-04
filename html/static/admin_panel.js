let editor;
let currentFile = '';
let logsUpdateInterval;

require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor/min/vs' }});
require(['vs/editor/editor.main'], function() {
    editor = monaco.editor.create(document.getElementById('jsonEditor'), {
        value: '',
        language: 'json',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: false }
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const tabElements = document.querySelectorAll('.nav-link');
    tabElements.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();

            tabElements.forEach(t => t.classList.remove('active'));

            this.classList.add('active');

            document.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('show', 'active');
            });
            
            // Показываем нужную панель
            const target = this.getAttribute('data-bs-target');
            document.querySelector(target).classList.add('show', 'active');
            
            // Если это вкладка логов, обновляем список
            if (target === '#logs') {
                refreshLogsList();
            }
        });
    });

    loadConfig();
    loadFileList();
    setupLogsAutoUpdate();
});

async function loadConfig() {
    const response = await fetch('/config');
    const data = await response.json();
    document.getElementById('aiName').value = data.AI_NAME;
    document.getElementById('defaultCity').value = data.DEFAULT_CITY;
}

async function saveConfig() {
    const config = {
        AI_NAME: document.getElementById('aiName').value,
        DEFAULT_CITY: document.getElementById('defaultCity').value
    };
    
    try {
        await fetch('/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        alert('Конфигурация сохранена');
    } catch (e) {
        alert('Ошибка при сохранении: ' + e.message);
    }
}

function setupLogsAutoUpdate() {
    const logsTab = document.getElementById('logs-tab');
    if (logsTab) {
        logsTab.addEventListener('shown.bs.tab', function (e) {
            refreshLogs();
            logsUpdateInterval = setInterval(refreshLogs, 5000);
        });

        logsTab.addEventListener('hidden.bs.tab', function (e) {
            clearInterval(logsUpdateInterval);
        });
    }
}

async function refreshLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();
        const logViewer = document.getElementById('logViewer');
        if (logViewer) {
            logViewer.innerHTML = data.logs.join('\n');
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    } catch (e) {
        console.error('Ошибка при обновлении логов:', e);
    }
}

async function loadFileList() {
    const response = await fetch('/api/files');
    const data = await response.json();
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = data.files.map(file => 
        `<a class="list-group-item list-group-item-action" onclick="loadFile('${file}')">${file}</a>`
    ).join('');
}

async function loadFile(filename) {
    currentFile = filename;
    try {
        const response = await fetch(`/api/files/${filename}`);
        const data = await response.json();
        editor.setValue(JSON.stringify(data, null, 2));

        const editorTab = document.querySelector('#editor-tab');
        if (editorTab) {
            const tab = new bootstrap.Tab(editorTab);
            tab.show();
        }
    } catch (e) {
        console.error('Ошибка при загрузке файла:', e);
    }
}

async function saveCurrentFile() {
    if (!currentFile) return;
    try {
        const content = JSON.parse(editor.getValue());
        await fetch(`/api/files/${currentFile}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(content)
        });
        alert('Файл успешно сохранен');
    } catch (e) {
        alert('Ошибка при сохранении: ' + e.message);
    }
}

async function restartAssistant() {
    try {
        await fetch('/api/restart', { method: 'POST' });
        alert('Ассистент перезапущен');
    } catch (e) {
        alert('Ошибка при перезапуске: ' + e.message);
    }
}

async function updateAdminCredentials() {
    const newUsername = document.getElementById('newUsername').value;
    const newPassword = document.getElementById('newPassword').value;
    
    if (!newUsername || !newPassword) {
        alert('Пожалуйста, заполните все поля');
        return;
    }
    
    try {
        const response = await fetch('/api/update_credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: newUsername,
                password: newPassword
            })
        });
        
        if (response.ok) {
            alert('Учетные данные успешно обновлены. Пожалуйста, войдите заново.');
            window.location.reload();
        } else {
            const error = await response.json();
            alert('Ошибка: ' + error.detail);
        }
    } catch (e) {
        alert('Ошибка при обновлении учетных данных: ' + e.message);
    }
}

async function refreshLogsList() {
    try {
        const response = await fetch('/api/logs/list');
        const data = await response.json();
        const logsList = document.getElementById('logsList');
        
        logsList.innerHTML = data.files.map(file => `
            <div class="list-group-item log-item">
                <span>${file}</span>
                <div class="log-actions">
                    <button class="btn btn-sm btn-primary" onclick="viewLog('${file}')">
                        Просмотр
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteLog('${file}')">
                        Удалить
                    </button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Ошибка при загрузке списка логов:', e);
    }
}

async function viewLog(filename) {
    try {
        const response = await fetch(`/api/logs/view/${filename}`);
        const data = await response.json();
        const logViewer = document.getElementById('logViewer');
        logViewer.textContent = data.content;
        logViewer.scrollTop = logViewer.scrollHeight;
    } catch (e) {
        console.error('Ошибка при чтении лога:', e);
    }
}

async function deleteLog(filename) {
    if (!confirm(`Удалить файл ${filename}?`)) return;
    
    try {
        await fetch(`/api/logs/delete/${filename}`, { method: 'DELETE' });
        refreshLogsList();
    } catch (e) {
        console.error('Ошибка при удалении лога:', e);
        alert('Ошибка при удалении файла');
    }
}

loadFileList(); 