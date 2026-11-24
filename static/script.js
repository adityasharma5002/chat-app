const input = document.getElementById("message-input");
const chatBox = document.getElementById("chat-box");
const sendButton = document.getElementById("send-button");
const clearButton = document.getElementById("clear-button");
const usersList = document.getElementById("users-list");

let selectedUserId = null;
let selectedUsername = null;


// Connect to Socket.IO
const socket = io();

// Make sure we're placed in our personal room every time
// we connect (first load) or reconnect (e.g. after server restart)
socket.on("connect", function() {
    console.log("Socket connected:", socket.id);
    socket.emit("join");
});

socket.on("disconnect", function() {
    console.log("Socket disconnected");
});


// Load registered users
async function loadUsers() {

    const response = await fetch("/users");
    const users = await response.json();

    usersList.innerHTML = "";

    if (users.length === 0) {

        usersList.innerHTML = "No other users registered.";

        return;
    }

    users.forEach(function(user) {

        const userElement = document.createElement("div");

        userElement.className = "user-item";

        userElement.textContent = user.username;

        userElement.addEventListener("click", function() {

            selectUser(user.id, user.username);

        });

        usersList.appendChild(userElement);
    });
}


// Select a user
async function selectUser(userId, username) {

    // Convert user ID to number
    selectedUserId = Number(userId);

    selectedUsername = username;


    // Remove selected class
    const allUsers = document.querySelectorAll(".user-item");

    allUsers.forEach(function(user) {

        user.classList.remove("selected");

    });


    // Highlight selected user
    allUsers.forEach(function(user) {

        if (user.textContent === username) {

            user.classList.add("selected");

        }

    });


    // Clear current chat
    chatBox.innerHTML = "";


    // Get previous messages
    const response = await fetch(
        `/messages/${selectedUserId}`
    );

    const messages = await response.json();


    // Display previous messages
    messages.forEach(function(msg) {

        displayMessage(
            Number(msg.sender_id),
            msg.sender_name,
            msg.message,
            msg.time
        );

    });


    chatBox.scrollTop = chatBox.scrollHeight;
}


// Display message
function displayMessage(
    senderId,
    senderName,
    message,
    time
) {

    const messageElement = document.createElement("div");


    // Convert sender ID to number
    senderId = Number(senderId);


    // Message from selected user
    if (senderId === selectedUserId) {

        messageElement.className = "bot-message";

        messageElement.textContent =
            `${senderName}: ${message}`;

    }

    // Message sent by current user
    else {

        messageElement.className = "user-message";

        messageElement.textContent =
            `You: ${message}`;
    }


    // Add time
    if (time) {

        const timeElement = document.createElement("span");

        timeElement.className = "message-time";

        timeElement.textContent = time;

        messageElement.appendChild(timeElement);
    }


    chatBox.appendChild(messageElement);

    chatBox.scrollTop = chatBox.scrollHeight;
}


// Send private message
async function sendMessage() {

    const message = input.value.trim();


    if (message === "") {
        return;
    }


    if (selectedUserId === null) {

        alert("Please select a user first.");

        return;
    }


    const response = await fetch("/chat", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({

            message: message,

            receiver_id: selectedUserId

        })
    });


    const data = await response.json();


    if (!response.ok) {

        alert(data.error);

        return;
    }


    // Display message for sender
    displayMessage(
        -1,
        "You",
        message,
        data.time
    );


    // Clear input
    input.value = "";


    chatBox.scrollTop = chatBox.scrollHeight;
}


// Receive real-time message
socket.on("receive_message", function(data) {

    // Convert sender ID to number
    const senderId = Number(data.sender_id);


    // Only show if this user is currently selected
    if (selectedUserId === senderId) {

        displayMessage(
            senderId,
            data.sender_name,
            data.message,
            data.time
        );

    }

});


// Send button
sendButton.addEventListener(
    "click",
    sendMessage
);


// Enter key
input.addEventListener(
    "keydown",
    function(event) {

        if (event.key === "Enter") {

            sendMessage();

        }

    }
);


// Clear chat
clearButton.addEventListener(
    "click",
    async function() {

        const confirmDelete =
            confirm("Are you sure you want to clear the chat?");


        if (!confirmDelete) {
            return;
        }


        const response = await fetch(
            "/clear-chat",
            {
                method: "POST"
            }
        );


        const data = await response.json();


        if (data.success) {

            chatBox.innerHTML = "";

        }

    }
);


// Load users when page opens
loadUsers();