const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const typingIndicator =
    document.getElementById("typing-indicator") || {
        classList: { add(){}, remove(){} }
    };
const clearChatBtn = document.getElementById("clear-chat") || null;
const themeToggle = document.getElementById("theme-toggle") || null;

/* -------------------------------------------------
   IMPORTANT FIX: allow raw HTML (iframe, embed)
---------------------------------------------------*/
marked.setOptions({
    breaks: true,
    gfm: true,
    mangle: false,
    headerIds: false,
    sanitize: false
});

// -------------------------------------------------
// PERSISTENT CONVERSATION MEMORY
// -------------------------------------------------
let messages = JSON.parse(localStorage.getItem("gene_history") || "[]");

// Load chat history into UI
messages.forEach(m => renderMessage(m.role, m.content));


// -------------------------------------------------
// HELPER: BUILD SAFE CONTEXT FOR LLM
// -------------------------------------------------
const MAX_CONTEXT_MESSAGES = 20;

function getLlmMessages() {
    return messages.slice(-MAX_CONTEXT_MESSAGES);
}


// -------------------------------------------------
// RENDER A MESSAGE BUBBLE (🔥 MAIN FIX APPLIED HERE)
// -------------------------------------------------
function renderMessage(role, content) {
    const div = document.createElement("div");
    div.className = "message " + (role === "user" ? "user" : "assistant");

    if (role === "user") {
        div.textContent = content;
    } else {

        // ⭐ FIX: detect ANY HTML, not just iframe
        const containsHTML = /<\/?[a-z][\s\S]*>/i.test(content);

        let html = containsHTML
            ? content                       // render raw HTML (STRING/KEGG/PDB)
            : marked.parse(content || "");  // fallback to markdown

        // Fix image styling
        html = html.replace(
            /<img /g,
            "<img style='max-width:100%; height:auto; display:block; margin:10px 0;' "
        );

        div.innerHTML = html;
    }

    setTimeout(() => addCopyButtons(div), 20);

    chatBox.appendChild(div);
    smoothScroll();
}


// -------------------------------------------------
// SMOOTH SCROLL TO BOTTOM
// -------------------------------------------------
function smoothScroll() {
    chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: "smooth" });
}


// -------------------------------------------------
// SEND MESSAGE HANDLER
// -------------------------------------------------
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    sendBtn.disabled = true;
    userInput.disabled = true;

    renderMessage("user", text);
    messages.push({ role: "user", content: text });
    saveHistory();

    userInput.value = "";
    autoGrow();

    typingIndicator.classList.remove("hidden");

    const llmMessages = getLlmMessages();

    const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: llmMessages })
    });

    const data = await res.json();

    typingIndicator.classList.add("hidden");

    if (data.reply) {
        renderMessage("assistant", data.reply);
        messages.push({ role: "assistant", content: data.reply });
    }

    if (data.html) {
        renderMessage("assistant", data.html);
    }

    saveHistory();

    sendBtn.disabled = false;
    userInput.disabled = false;
    userInput.focus();
}


// -------------------------------------------------
// ENABLE COPY BUTTONS ON CODE BLOCKS
// -------------------------------------------------
function addCopyButtons(parent) {
    const blocks = parent.querySelectorAll("pre");
    blocks.forEach(block => {
        if (block.querySelector(".copy-btn")) return;

        const btn = document.createElement("button");
        btn.className = "copy-btn";
        btn.textContent = "Copy";

        btn.onclick = () => {
            navigator.clipboard.writeText(block.innerText);
            btn.textContent = "Copied!";
            setTimeout(() => (btn.textContent = "Copy"), 1000);
        };

        block.appendChild(btn);
    });
}


// -------------------------------------------------
// AUTO-GROW THE TEXTAREA
// -------------------------------------------------
function autoGrow() {
    userInput.style.height = "auto";
    userInput.style.height = (userInput.scrollHeight) + "px";
}
userInput.addEventListener("input", autoGrow);


// -------------------------------------------------
// CLEAR CHAT BUTTON
// -------------------------------------------------
if (clearChatBtn) {
    clearChatBtn.onclick = () => {
        messages = [];
        localStorage.removeItem("gene_history");
        chatBox.innerHTML = "";
    };
}


// -------------------------------------------------
// THEME TOGGLER
// -------------------------------------------------
if (themeToggle) {
    themeToggle.onclick = () => {
        document.body.classList.toggle("light");

        themeToggle.textContent =
            document.body.classList.contains("light") ? "☀️" : "🌙";
    };
}


// -------------------------------------------------
// SAVE MESSAGES TO LOCALSTORAGE
// -------------------------------------------------
function saveHistory() {
    localStorage.setItem("gene_history", JSON.stringify(messages));
}


// -------------------------------------------------
// SEND BUTTON + ENTER KEY
// -------------------------------------------------
sendBtn.addEventListener("click", sendMessage);

userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
