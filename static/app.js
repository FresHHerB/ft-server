document.addEventListener('DOMContentLoaded', (event) => {
    const socket = io();
    const logOutput = document.getElementById('log-output');
    const statusElement = document.getElementById('bot-status');

    socket.on('connect', () => {
        console.log('Conectado ao servidor de logs!');
    });

    socket.on('historical_logs', (data) => {
        logOutput.textContent = data.logs;
        logOutput.scrollTop = logOutput.scrollHeight;
    });

    socket.on('new_log_line', (data) => {
        logOutput.textContent += data.line;
        logOutput.scrollTop = logOutput.scrollHeight;
    });

    window.startBot = function() {
        fetch('/start_bot', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                statusElement.textContent = 'Rodando';
            });
    }

    window.stopBot = function() {
        fetch('/stop_bot', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                statusElement.textContent = 'Parado';
            });
    }

    window.saveConfig = function() {
        const configData = {
            FT_USERNAME: document.getElementById('ft_username').value,
            FT_PASSWORD: document.getElementById('ft_password').value,
            JOGO_SLUG: document.getElementById('jogo_slug').value,
            TARGET_SECTOR_SLUG: document.getElementById('target_sector_slug').value,
            DEPENDENTE_ID: document.getElementById('dependente_id').value,
            OPENAI_API_KEY: document.getElementById('openai_api_key').value,
            TWOCAPTCHA_API_KEY: document.getElementById('twocaptcha_api_key').value
        };
        
        // Remove chaves com valores vazios para não sobrescrever
        Object.keys(configData).forEach(key => {
            if (configData[key] === "") {
                delete configData[key];
            }
        });

        fetch('/save_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData)
        })
        .then(res => res.json())
        .then(data => {
            alert(data.message);
            window.location.reload(); // Recarrega para ver as novas configs
        });
    }
});
