// static/app.js - Versão Atualizada sem DEPENDENTE_ID
console.log('🚀 Carregando app.js...');

document.addEventListener('DOMContentLoaded', function() {
    console.log('📱 DOM carregado, inicializando dashboard...');
    
    const logOutput = document.getElementById('log-output');
    const statusElement = document.getElementById('bot-status');
    const logInfo = document.getElementById('log-info');
    
    if (!logOutput) {
        console.error('❌ Elemento log-output não encontrado!');
        return;
    }
    
    // Função para scroll automático
    function scrollToBottom() {
        logOutput.scrollTop = logOutput.scrollHeight;
    }
    
    // Carrega logs via API
    async function loadLogsViaAPI() {
        try {
            console.log('🔄 Carregando logs via API...');
            logOutput.textContent = 'Carregando logs via API...';
            
            const response = await fetch('/api/logs');
            if (response.ok) {
                const data = await response.json();
                logOutput.textContent = data.logs || 'Nenhum log disponível';
                if (logInfo) {
                    logInfo.textContent = `${data.file_size} chars • ${new Date().toLocaleTimeString()}`;
                }
                scrollToBottom();
                console.log(`✅ Logs carregados via API (${data.file_size} chars)`);
            } else {
                logOutput.textContent = 'Erro ao carregar logs via API: ' + response.statusText;
                console.error('❌ Erro ao carregar logs via API:', response.statusText);
            }
        } catch (error) {
            logOutput.textContent = 'Erro de conexão ao carregar logs: ' + error.message;
            console.error('❌ Erro na requisição de logs:', error);
        }
    }
    
    // Carrega logs imediatamente
    loadLogsViaAPI();
    
    // Recarrega logs a cada 10 segundos como fallback
    setInterval(loadLogsViaAPI, 10000);
    
    // Inicializa WebSocket se disponível
    if (typeof io !== 'undefined') {
        console.log('🔌 Inicializando WebSocket...');
        
        try {
            const socket = io();
            
            socket.on('connect', function() {
                console.log('✅ WebSocket conectado!');
                logOutput.textContent += '\n🔌 Conectado em tempo real\n';
                scrollToBottom();
            });
            
            socket.on('disconnect', function() {
                console.log('❌ WebSocket desconectado');
                logOutput.textContent += '\n🔌 Desconectado\n';
                scrollToBottom();
            });
            
            socket.on('historical_logs', function(data) {
                console.log('📜 Recebido log histórico via WebSocket');
                logOutput.textContent = data.logs || 'Nenhum log disponível';
                logOutput.textContent += '\n📡 Monitoramento em tempo real ativo\n';
                if (logInfo) {
                    logInfo.textContent = `Tempo real • ${new Date().toLocaleTimeString()}`;
                }
                scrollToBottom();
            });
            
            socket.on('new_log_line', function(data) {
                console.log('📝 Nova linha de log recebida');
                logOutput.textContent += data.line;
                scrollToBottom();
            });
            
            socket.on('log_cleared', function(data) {
                console.log('🧹 Logs foram limpos');
                logOutput.textContent = data.message + '\n\n';
                if (logInfo) {
                    logInfo.textContent = `Limpo • ${new Date().toLocaleTimeString()}`;
                }
                scrollToBottom();
                // Recarrega logs após 2 segundos
                setTimeout(loadLogsViaAPI, 2000);
            });
            
            socket.on('connect_error', function(error) {
                console.error('❌ Erro de conexão WebSocket:', error);
                logOutput.textContent += '\n❌ Erro WebSocket: ' + error + '\n';
                scrollToBottom();
            });
            
        } catch (error) {
            console.error('❌ Erro ao inicializar WebSocket:', error);
        }
    } else {
        console.warn('⚠️ Socket.io não disponível, usando apenas API');
        logOutput.textContent += '\n⚠️ Usando apenas modo API (sem tempo real)\n';
    }
    
    // === FUNÇÕES GLOBAIS PARA OS BOTÕES ===
    
    window.startBot = function() {
        console.log('🚀 Iniciando bot...');
        
        fetch('/start_bot', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                if (statusElement) statusElement.textContent = 'Rodando';
                loadLogsViaAPI();
            })
            .catch(error => {
                console.error('❌ Erro ao iniciar bot:', error);
                alert('Erro ao iniciar bot: ' + error.message);
            });
    };
    
    window.stopBot = function() {
        console.log('⏹️ Parando bot...');
        
        fetch('/stop_bot', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                if (statusElement) statusElement.textContent = 'Parado';
                loadLogsViaAPI();
            })
            .catch(error => {
                console.error('❌ Erro ao parar bot:', error);
                alert('Erro ao parar bot: ' + error.message);
            });
    };
    
    // NOVA FUNÇÃO: Reiniciar Bot
    window.restartBot = function() {
        console.log('🔄 Reiniciando bot...');
        
        if (!confirm('Tem certeza que deseja reiniciar o bot? Os logs atuais serão limpos.')) {
            return;
        }
        
        // Mostra feedback visual
        logOutput.textContent += '\n🔄 REINICIANDO BOT... Aguarde...\n';
        scrollToBottom();
        
        fetch('/restart_bot', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                if (statusElement) statusElement.textContent = 'Rodando';
                // Aguarda um pouco antes de recarregar logs
                setTimeout(loadLogsViaAPI, 3000);
            })
            .catch(error => {
                console.error('❌ Erro ao reiniciar bot:', error);
                alert('Erro ao reiniciar bot: ' + error.message);
                loadLogsViaAPI();
            });
    };
    
    // NOVA FUNÇÃO: Limpar Logs
    window.clearLogs = function() {
        console.log('🧹 Limpando logs...');
        
        if (!confirm('Tem certeza que deseja limpar todos os logs?')) {
            return;
        }
        
        fetch('/clear_logs', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                // O WebSocket vai receber o evento log_cleared e atualizar automaticamente
                // Mas fazemos fallback também
                setTimeout(loadLogsViaAPI, 1000);
            })
            .catch(error => {
                console.error('❌ Erro ao limpar logs:', error);
                alert('Erro ao limpar logs: ' + error.message);
            });
    };
    
    window.saveConfig = function() {
        console.log('💾 Salvando configurações...');
        
        const configData = {
            FT_USERNAME: document.getElementById('ft_username')?.value || '',
            FT_PASSWORD: document.getElementById('ft_password')?.value || '',
            JOGO_SLUG: document.getElementById('jogo_slug')?.value || '',
            TARGET_SECTOR_SLUG: document.getElementById('target_sector_slug')?.value || '',
            // REMOVIDO: DEPENDENTE_ID (agora extraído automaticamente)
            OPENAI_API_KEY: document.getElementById('openai_api_key')?.value || '',
            TWOCAPTCHA_API_KEY: document.getElementById('twocaptcha_api_key')?.value || ''
        };
        
        // Remove valores vazios
        Object.keys(configData).forEach(key => {
            if (configData[key] === "") {
                delete configData[key];
            }
        });
        
        console.log('📋 Dados a salvar:', Object.keys(configData));
        
        fetch('/save_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData)
        })
        .then(res => res.json())
        .then(data => {
            alert(data.message);
            window.location.reload();
        })
        .catch(error => {
            console.error('❌ Erro ao salvar config:', error);
            alert('Erro ao salvar configurações: ' + error.message);
        });
    };
    
    // Função para baixar logs
    window.downloadLogs = function() {
        console.log('📥 Baixando logs...');
        
        const logs = logOutput.textContent;
        const blob = new Blob([logs], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `bot_logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        console.log('✅ Download de logs iniciado');
    };
    
    console.log('✅ Dashboard inicializado com sucesso - Todas as funções carregadas');
    console.log('🆕 Nova funcionalidade: IDs de dependentes são extraídos automaticamente!');
});
