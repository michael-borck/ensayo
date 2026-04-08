/**
 * Ensayo Keyword Chatbot — client-side keyword-matching chat engine.
 * Reads keywords.json for each employee and provides deterministic responses.
 */

function initKeywordChatbot(config) {
    const { slug, name, role, keywordsUrl } = config;
    let keywords = null;
    let chatOpen = false;

    // Load keywords
    fetch(keywordsUrl)
        .then(r => r.json())
        .then(data => { keywords = data; })
        .catch(() => {
            console.warn('Could not load keywords for', slug);
            keywords = { responses: {}, default: "I'm sorry, I can't respond right now." };
        });

    // Create FAB
    const fab = document.createElement('button');
    fab.className = 'chat-fab';
    fab.textContent = '💬';
    fab.title = 'Chat with ' + name;
    document.body.appendChild(fab);

    // Create panel
    const panel = document.createElement('div');
    panel.className = 'chat-panel';
    panel.innerHTML = `
        <div class="chat-header">
            <strong>${name}</strong>
            <span class="chat-role">${role}</span>
            <button class="chat-close">&times;</button>
        </div>
        <div class="chat-messages"></div>
        <div class="chat-input-row">
            <input type="text" class="chat-input" placeholder="Type a message...">
            <button class="chat-send">Send</button>
        </div>
    `;
    document.body.appendChild(panel);

    const messages = panel.querySelector('.chat-messages');
    const input = panel.querySelector('.chat-input');
    const sendBtn = panel.querySelector('.chat-send');
    const closeBtn = panel.querySelector('.chat-close');

    function toggleChat() {
        chatOpen = !chatOpen;
        panel.classList.toggle('chat-panel-open', chatOpen);
        fab.classList.toggle('chat-fab-hidden', chatOpen);
        if (chatOpen && messages.children.length === 0) {
            addMessage(keywords?.greeting || `Hello, I'm ${name}. How can I help you?`, 'assistant');
        }
    }

    function addMessage(text, type) {
        const msg = document.createElement('div');
        msg.className = 'chat-msg chat-msg-' + type;
        if (type === 'assistant') {
            msg.innerHTML = '<span class="chat-msg-name">' + name + '</span>' + text;
        } else {
            msg.textContent = text;
        }
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    function getResponse(userText) {
        if (!keywords) return "I'm still loading, please try again in a moment.";
        const lower = userText.toLowerCase();
        for (const [keyword, response] of Object.entries(keywords.responses || {})) {
            if (lower.includes(keyword.toLowerCase())) return response;
        }
        return keywords.default || "I'm not sure about that. Could you rephrase?";
    }

    function handleSend() {
        const text = input.value.trim();
        if (!text) return;
        addMessage(text, 'user');
        input.value = '';
        // Slight delay for realism
        setTimeout(() => addMessage(getResponse(text), 'assistant'), 300 + Math.random() * 500);
    }

    fab.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);
    sendBtn.addEventListener('click', handleSend);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSend(); });
}
