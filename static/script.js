document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const historyList = document.getElementById('history-list');
    const fileUpload = document.getElementById('file-upload');
    const themeToggle = document.getElementById('theme-checkbox');
    const micBtn = document.getElementById('mic-btn');
    const menuToggleBtn = document.getElementById('menu-toggle-btn');
    const sidebar = document.querySelector('.sidebar');

    let currentConversationId = null;

    // --- Event Listeners ---
    chatForm.addEventListener('submit', handleFormSubmit);
    fileUpload.addEventListener('change', handleFileUpload);
    themeToggle.addEventListener('change', handleThemeToggle);
    micBtn.addEventListener('click', handleVoiceInput);
    menuToggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('show');
    });

    // --- Initial Setup ---
    loadConversations();
    initializeTheme();

    // --- Feature Implementations ---

    // Dark Mode
    function initializeTheme() {
        const isDarkMode = localStorage.getItem('darkMode') === 'true';
        themeToggle.checked = isDarkMode;
        document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
    }

    function handleThemeToggle() {
        const isDarkMode = themeToggle.checked;
        localStorage.setItem('darkMode', isDarkMode);
        document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
    }

    // Voice to Text
    function handleVoiceInput() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            addMessageToChat('bot', 'Sorry, your browser does not support voice recognition.');
            return;
        }
        
        const recognition = new SpeechRecognition();
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        micBtn.classList.add('listening');
        
        recognition.start();

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            // Automatically submit the form after successful recognition
            if (transcript) handleFormSubmit(new Event('submit'));
        };

        recognition.onerror = (event) => {
            addMessageToChat('bot', `Voice recognition error: ${event.error}`);
        };

        recognition.onend = () => {
            micBtn.classList.remove('listening');
        };
    }

    // Conversation Management (with Delete functionality)
    async function loadConversations() {
        try {
            const response = await fetch('/get_conversations');
            const conversations = await response.json();
            historyList.innerHTML = '';

            const newConvBtn = document.createElement('li');
            newConvBtn.innerHTML = `<span>➕ New Conversation</span>`;
            newConvBtn.classList.add('new-conversation');
            newConvBtn.addEventListener('click', createNewConversation);
            historyList.appendChild(newConvBtn);

            conversations.forEach(conv => {
                const historyItem = document.createElement('li');
                historyItem.dataset.id = conv.id;
                
                const titleSpan = document.createElement('span');
                titleSpan.textContent = conv.title || `Conversation ${conv.id}`;
                titleSpan.classList.add('history-title');

                const deleteBtn = document.createElement('button');
                deleteBtn.innerHTML = `&times;`;
                deleteBtn.classList.add('delete-conv-btn');
                deleteBtn.title = 'Delete conversation';

                historyItem.appendChild(titleSpan);
                historyItem.appendChild(deleteBtn);

                titleSpan.addEventListener('click', () => setActiveConversation(conv.id));
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    confirmAndDelete(conv.id, conv.title);
                });

                historyList.appendChild(historyItem);
            });
        } catch (error) {
            console.error("Error loading conversations:", error);
        }
    }

    async function confirmAndDelete(conversationId, title) {
        // Custom confirmation instead of window.confirm
        addMessageToChat('bot', `Are you sure you want to delete "${title}"? This cannot be undone. 
            <button class="btn btn-danger btn-sm m-1" onclick="performDelete(${conversationId})">Yes, Delete</button>`);
    }

    window.performDelete = async (conversationId) => {
        try {
            const response = await fetch(`/delete_conversation/${conversationId}`, { method: 'DELETE' });
            if (response.ok) {
                // If deleting the active chat, reset the view
                if (currentConversationId === conversationId) {
                    createNewConversation();
                }
                loadConversations(); // Refresh the list
            } else {
                const data = await response.json();
                addMessageToChat('bot', `Error deleting chat: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    }

    async function createNewConversation() {
        currentConversationId = null;
        chatMessages.innerHTML = '<div class="message bot"><div class="message-content">New chat started. Ask me anything!</div></div>';
        document.querySelectorAll('#history-list li').forEach(li => li.classList.remove('active'));
    }

    async function setActiveConversation(conversationId) {
        currentConversationId = conversationId;
        document.querySelectorAll('#history-list li').forEach(li => li.classList.remove('active'));
        const activeItem = [...historyList.children].find(li => li.dataset?.id == conversationId);
        if (activeItem) activeItem.classList.add('active');

        try {
            const response = await fetch(`/get_chat/${conversationId}`);
            if (response.status === 401) { window.location.href = '/login'; return; }
            const messages = await response.json();
            chatMessages.innerHTML = '';
            messages.forEach(msg => addMessageToChat(msg.sender, msg.message));
        } catch (error) {
            console.error("Error loading chat history:", error);
        }
    }

    // Message Handling
    function handleFormSubmit(event) {
        event.preventDefault();
        const message = userInput.value.trim();
        if (message) {
            addMessageToChat('user', message);
            sendMessageToServer(message);
            userInput.value = '';
        }
    }

    function handleFileUpload(event) {
        const file = event.target.files[0];
        if (file) {
            const userMessage = userInput.value.trim() || `Summarize this document: ${file.name}`;
            addMessageToChat('user', `Uploading file: ${file.name}`);
            sendMessageToServer(userMessage, file);
            userInput.value = '';
        }
        fileUpload.value = ''; // Reset file input
    }

    function addMessageToChat(sender, text) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender);
        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');
        
        // Basic Markdown + Button handling
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        contentElement.innerHTML = text.replace(/\n/g, '<br>');

        messageElement.appendChild(contentElement);
        chatMessages.appendChild(messageElement);
        scrollToBottom();
    }

    function showTypingIndicator() {
        if(document.getElementById('typing-indicator')) return;
        const indicator = document.createElement('div');
        indicator.id = 'typing-indicator';
        indicator.classList.add('message', 'bot');
        indicator.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
        chatMessages.appendChild(indicator);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    async function sendMessageToServer(message, file = null) {
        showTypingIndicator();
        const formData = new FormData();
        if (message) formData.append('message', message);
        if (file) formData.append('file', file);
        if (currentConversationId) formData.append('conversation_id', currentConversationId);

        try {
            const response = await fetch('/chat', { method: 'POST', body: formData });
            removeTypingIndicator();
            if (!response.ok) {
                if (response.status === 401) window.location.href = '/login';
                throw new Error(`Server error: ${response.statusText}`);
            }
            const data = await response.json();
            addMessageToChat('bot', data.response);

            if (!currentConversationId && data.conversation_id) {
                currentConversationId = data.conversation_id;
                await loadConversations();
                const activeItem = [...historyList.children].find(li => li.dataset?.id == currentConversationId);
                if (activeItem) activeItem.classList.add('active');
            }
        } catch (error) {
            removeTypingIndicator();
            console.error("Fetch Error:", error);
            addMessageToChat("bot", "Sorry, an error occurred. Please try again.");
        }
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});