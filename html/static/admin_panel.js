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
            
            const target = this.getAttribute('data-bs-target');
            const targetPane = document.querySelector(target);
            targetPane.classList.add('show', 'active');
            
            // Обновляем содержимое в зависимости от вкладки
            if (target === '#logs') {
                refreshLogsList();
            } else if (target === '#commands') {
                refreshCommands();
            }
        });
    });

    loadConfig();
    loadFileList();
    setupLogsAutoUpdate();
    refreshLogsList();
    refreshCommands();
    showLatestLog(); // Показываем последний лог при загрузке
});

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        document.getElementById('modelPath').value = config.MODEL_PATH;
        document.getElementById('aiName').value = config.AI_NAME;
        document.getElementById('sampleRate').value = config.SAMPLE_RATE;
        document.getElementById('bufferSize').value = config.BUFFER_SIZE;
        document.getElementById('frameDuration').value = config.FRAME_DURATION_MS;
        document.getElementById('vadMode').value = config.VAD_MODE;
        document.getElementById('defaultCity').value = config.DEFAULT_CITY;
        document.getElementById('defaultCurrency').value = config.DEFAULT_CURRENCY;
        document.getElementById('restartTimeout').value = config.RESTART_TIMEOUT;
        document.getElementById('loggingEnabled').checked = config.logging_enabled;
    } catch (e) {
        console.error('Ошибка при загрузке конфигурации:', e);
    }
}

async function saveConfig() {
    const config = {
        MODEL_PATH: document.getElementById('modelPath').value,
        AI_NAME: document.getElementById('aiName').value,
        SAMPLE_RATE: parseInt(document.getElementById('sampleRate').value),
        BUFFER_SIZE: parseInt(document.getElementById('bufferSize').value),
        FRAME_DURATION_MS: parseInt(document.getElementById('frameDuration').value),
        VAD_MODE: parseInt(document.getElementById('vadMode').value),
        DEFAULT_CITY: document.getElementById('defaultCity').value,
        DEFAULT_CURRENCY: document.getElementById('defaultCurrency').value,
        RESTART_TIMEOUT: parseInt(document.getElementById('restartTimeout').value),
        logging_enabled: document.getElementById('loggingEnabled').checked,
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            alert('Конфигурация успешно сохранена');
        } else {
            alert('Ошибка при сохранении конфигурации');
        }
    } catch (e) {
        console.error('Ошибка при сохранении конфигурации:', e);
        alert('Ошибка при сохранении конфигурации');
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

async function showLatestLog() {
    try {
        const response = await fetch('/api/logs/list');
        const data = await response.json();
        if (data.files && data.files.length > 0) {
            const latestLog = data.files.sort((a, b) => {
                const dateA = a.split('.')[0];
                const dateB = b.split('.')[0];
                return dateB.localeCompare(dateA);
            })[0];
            
            await viewLog(latestLog);
        }
    } catch (e) {
        console.error('Ошибка при загрузке последнего лога:', e);
    }
}

async function refreshLogsList() {
    try {
        const response = await fetch('/api/logs/list');
        const data = await response.json();
        const logsList = document.getElementById('logsList');
        
        const sortedFiles = data.files.sort((a, b) => {
            const dateA = a.split('.')[0];
            const dateB = b.split('.')[0];
            return dateB.localeCompare(dateA);
        });
        
        logsList.innerHTML = sortedFiles.map(file => `
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

        if (sortedFiles.length > 0 && !document.getElementById('logViewer').textContent) {
            await viewLog(sortedFiles[0]);
        }
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

async function refreshCommands() {
    try {
        const response = await fetch('/api/commands');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const commandsList = document.getElementById('commandsList');
        
        if (!data || !data.commands) {
            commandsList.innerHTML = '<div class="alert alert-info">Нет добавленных команд</div>';
            return;
        }
        
        const commandsHtml = Object.entries(data.commands).map(([command, response]) => `
            <div class="command-item">
                <div class="command-content">
                    <div class="command-name">${command}</div>
                    <div class="command-response">${response}</div>
                </div>
                <div class="command-actions">
                    <button class="btn btn-sm btn-danger" onclick="deleteCommand('${command}')">
                        Удалить
                    </button>
                </div>
            </div>
        `).join('');
        
        commandsList.innerHTML = commandsHtml || '<div class="alert alert-info">Нет добавленных команд</div>';
    } catch (e) {
        console.error('Ошибка при загрузке команд:', e);
        const commandsList = document.getElementById('commandsList');
        commandsList.innerHTML = '<div class="alert alert-danger">Ошибка при загрузке команд</div>';
    }
}

async function addCommand() {
    const command = document.getElementById('newCommand').value.trim();
    const response = document.getElementById('newResponse').value.trim();
    
    if (!command || !response) {
        alert('Пожалуйста, заполните все поля');
        return;
    }
    
    try {
        const result = await fetch('/api/commands', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command, response })
        });
        
        if (!result.ok) {
            throw new Error(`HTTP error! status: ${result.status}`);
        }
        
        document.getElementById('newCommand').value = '';
        document.getElementById('newResponse').value = '';
        await refreshCommands();
    } catch (e) {
        alert('Ошибка при добавлении команды: ' + e.message);
    }
}

async function deleteCommand(command) {
    if (!confirm(`Удалить команду "${command}"?`)) return;
    
    try {
        await fetch(`/api/commands/${encodeURIComponent(command)}`, {
            method: 'DELETE'
        });
        refreshCommands();
    } catch (e) {
        alert('Ошибка при удалении команды: ' + e.message);
    }
}

loadFileList(); 